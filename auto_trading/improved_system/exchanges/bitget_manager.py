"""
Enhanced Bitget Exchange Manager with Improved Error Handling and Performance
Author: Enhanced by Claude Code
Version: 4.0
"""

import asyncio
import logging
import time
import json
import hmac
import hashlib
import base64
from typing import Dict, List, Optional, Any, Tuple
from datetime import datetime, timedelta
from collections import deque, defaultdict
import websockets
import aiohttp
import ccxt
from cachetools import TTLCache
import backoff

from ..core.exceptions import (
    ExchangeConnectionError, ExchangeAPIError, ExchangeRateLimitError,
    TradingError, DataError, WebSocketError, handle_async_exceptions
)
from ..core.config import TradingConfig

logger = logging.getLogger(__name__)

class RateLimiter:
    """Advanced rate limiter with multiple windows"""
    
    def __init__(self, requests_per_minute: int = 30, requests_per_second: int = 2):
        self.requests_per_minute = requests_per_minute
        self.requests_per_second = requests_per_second
        self.minute_window = deque(maxlen=requests_per_minute)
        self.second_window = deque(maxlen=requests_per_second)
        self._lock = asyncio.Lock()
    
    async def acquire(self):
        """Acquire rate limit permission"""
        async with self._lock:
            current_time = time.time()
            
            # Clean old entries
            while self.minute_window and current_time - self.minute_window[0] > 60:
                self.minute_window.popleft()
            
            while self.second_window and current_time - self.second_window[0] > 1:
                self.second_window.popleft()
            
            # Check limits
            if len(self.minute_window) >= self.requests_per_minute:
                sleep_time = 60 - (current_time - self.minute_window[0])
                logger.warning(f"Rate limit hit (minute), sleeping {sleep_time:.2f}s")
                await asyncio.sleep(sleep_time)
                return await self.acquire()
            
            if len(self.second_window) >= self.requests_per_second:
                sleep_time = 1 - (current_time - self.second_window[0])
                logger.warning(f"Rate limit hit (second), sleeping {sleep_time:.2f}s")
                await asyncio.sleep(sleep_time)
                return await self.acquire()
            
            # Add to windows
            self.minute_window.append(current_time)
            self.second_window.append(current_time)

class CircuitBreaker:
    """Circuit breaker for API failures"""
    
    def __init__(self, failure_threshold: int = 5, timeout: int = 60):
        self.failure_threshold = failure_threshold
        self.timeout = timeout
        self.failure_count = 0
        self.last_failure_time = None
        self.state = 'closed'  # closed, open, half-open
    
    async def call(self, func, *args, **kwargs):
        """Execute function with circuit breaker protection"""
        if self.state == 'open':
            if time.time() - self.last_failure_time > self.timeout:
                self.state = 'half-open'
                logger.info("Circuit breaker moving to half-open state")
            else:
                raise ExchangeConnectionError("Circuit breaker is open")
        
        try:
            result = await func(*args, **kwargs)
            
            if self.state == 'half-open':
                self.state = 'closed'
                self.failure_count = 0
                logger.info("Circuit breaker closed")
            
            return result
            
        except Exception as e:
            self.failure_count += 1
            self.last_failure_time = time.time()
            
            if self.failure_count >= self.failure_threshold:
                self.state = 'open'
                logger.error(f"Circuit breaker opened after {self.failure_count} failures")
            
            raise e

class WebSocketManager:
    """Enhanced WebSocket manager with reconnection"""
    
    def __init__(self, config: TradingConfig):
        self.config = config
        self.websocket = None
        self.connected = False
        self.subscriptions = set()
        self.data_handlers = {}
        self.reconnect_attempts = 0
        self.max_reconnect_attempts = config.MAX_RECONNECT_ATTEMPTS
        self.reconnect_delay = config.WS_RECONNECT_DELAY
        
        # Data storage
        self.price_data = {}
        self.orderbook_data = {}
        self.trade_data = defaultdict(list)
        
        # Metrics
        self.messages_received = 0
        self.last_message_time = None
        self.connection_start_time = None
    
    async def connect(self):
        """Connect to WebSocket"""
        if self.connected:
            return
        
        try:
            self.websocket = await websockets.connect(
                "wss://ws.bitget.com/spot/v1/stream",
                ping_interval=20,
                ping_timeout=10
            )
            
            self.connected = True
            self.reconnect_attempts = 0
            self.connection_start_time = time.time()
            
            logger.info("WebSocket connected successfully")
            
            # Start message handler
            asyncio.create_task(self._handle_messages())
            
            # Resubscribe to channels
            await self._resubscribe()
            
        except Exception as e:
            self.connected = False
            raise WebSocketError(f"Failed to connect WebSocket: {str(e)}")
    
    async def disconnect(self):
        """Disconnect WebSocket"""
        if self.websocket:
            await self.websocket.close()
        
        self.connected = False
        self.websocket = None
        logger.info("WebSocket disconnected")
    
    async def subscribe(self, channel: str, symbol: str = None):
        """Subscribe to WebSocket channel"""
        if not self.connected:
            await self.connect()
        
        subscription_data = {
            "op": "subscribe",
            "args": [{
                "instType": "sp",
                "channel": channel,
                "instId": symbol if symbol else "default"
            }]
        }
        
        await self.websocket.send(json.dumps(subscription_data))
        self.subscriptions.add((channel, symbol))
        
        logger.info(f"Subscribed to {channel} for {symbol}")
    
    async def _resubscribe(self):
        """Resubscribe to all channels after reconnection"""
        for channel, symbol in self.subscriptions:
            try:
                await self.subscribe(channel, symbol)
            except Exception as e:
                logger.error(f"Failed to resubscribe to {channel}: {e}")
    
    async def _handle_messages(self):
        """Handle incoming WebSocket messages"""
        try:
            async for message in self.websocket:
                try:
                    data = json.loads(message)
                    await self._process_message(data)
                    
                    self.messages_received += 1
                    self.last_message_time = time.time()
                    
                except json.JSONDecodeError as e:
                    logger.error(f"Failed to decode WebSocket message: {e}")
                except Exception as e:
                    logger.error(f"Error processing WebSocket message: {e}")
                    
        except websockets.exceptions.ConnectionClosed:
            logger.warning("WebSocket connection closed")
            self.connected = False
            await self._reconnect()
        except Exception as e:
            logger.error(f"WebSocket error: {e}")
            self.connected = False
            await self._reconnect()
    
    async def _process_message(self, data: Dict[str, Any]):
        """Process WebSocket message"""
        if 'data' in data:
            channel = data.get('arg', {}).get('channel')
            symbol = data.get('arg', {}).get('instId')
            
            if channel == 'ticker':
                await self._handle_ticker_data(symbol, data['data'])
            elif channel == 'books':
                await self._handle_orderbook_data(symbol, data['data'])
            elif channel == 'trade':
                await self._handle_trade_data(symbol, data['data'])
    
    async def _handle_ticker_data(self, symbol: str, data: List[Dict]):
        """Handle ticker data"""
        if data and symbol:
            ticker = data[0]
            self.price_data[symbol] = {
                'symbol': symbol,
                'price': float(ticker['last']),
                'bid': float(ticker['bidPx']),
                'ask': float(ticker['askPx']),
                'volume': float(ticker['vol24h']),
                'timestamp': time.time()
            }
    
    async def _handle_orderbook_data(self, symbol: str, data: List[Dict]):
        """Handle orderbook data"""
        if data and symbol:
            orderbook = data[0]
            self.orderbook_data[symbol] = {
                'symbol': symbol,
                'bids': [[float(bid[0]), float(bid[1])] for bid in orderbook.get('bids', [])],
                'asks': [[float(ask[0]), float(ask[1])] for ask in orderbook.get('asks', [])],
                'timestamp': time.time()
            }
    
    async def _handle_trade_data(self, symbol: str, data: List[Dict]):
        """Handle trade data"""
        if data and symbol:
            for trade in data:
                trade_info = {
                    'symbol': symbol,
                    'price': float(trade['px']),
                    'size': float(trade['sz']),
                    'side': trade['side'],
                    'timestamp': int(trade['ts'])
                }
                
                self.trade_data[symbol].append(trade_info)
                
                # Keep only last 1000 trades per symbol
                if len(self.trade_data[symbol]) > 1000:
                    self.trade_data[symbol] = self.trade_data[symbol][-1000:]
    
    async def _reconnect(self):
        """Reconnect WebSocket with exponential backoff"""
        if self.reconnect_attempts >= self.max_reconnect_attempts:
            logger.error("Max reconnection attempts reached")
            return
        
        self.reconnect_attempts += 1
        delay = self.reconnect_delay * (2 ** (self.reconnect_attempts - 1))
        
        logger.info(f"Reconnecting WebSocket in {delay}s (attempt {self.reconnect_attempts})")
        await asyncio.sleep(delay)
        
        try:
            await self.connect()
        except Exception as e:
            logger.error(f"Reconnection failed: {e}")
            await self._reconnect()

class EnhancedBitgetExchangeManager:
    """Enhanced Bitget exchange manager with improved error handling"""
    
    def __init__(self, config: TradingConfig):
        self.config = config
        self.logger = logging.getLogger(__name__)
        
        # Initialize CCXT exchange
        self.exchange = ccxt.bitget({
            'apiKey': config.BITGET_API_KEY,
            'secret': config.BITGET_SECRET_KEY,
            'password': config.BITGET_PASSPHRASE,
            'enableRateLimit': True,
            'rateLimit': 50,
            'options': {
                'defaultType': 'swap',
                'adjustForTimeDifference': True
            }
        })
        
        # Initialize components
        self.rate_limiter = RateLimiter()
        self.circuit_breaker = CircuitBreaker()
        self.websocket_manager = WebSocketManager(config)
        
        # Cache
        self.cache = TTLCache(maxsize=config.INDICATOR_CACHE_SIZE, ttl=config.CACHE_TTL)
        
        # Metrics
        self.api_calls_count = 0
        self.errors_count = 0
        self.last_health_check = None
    
    async def initialize(self):
        """Initialize exchange manager"""
        try:
            # Test API connection
            await self._test_connection()
            
            # Start WebSocket connection
            await self.websocket_manager.connect()
            
            # Subscribe to price feeds
            for symbol in self.config.SYMBOLS:
                await self.websocket_manager.subscribe('ticker', symbol)
                await self.websocket_manager.subscribe('books', symbol)
            
            logger.info("Bitget exchange manager initialized successfully")
            
        except Exception as e:
            raise ExchangeConnectionError(f"Failed to initialize exchange manager: {str(e)}")
    
    @handle_async_exceptions()
    async def _test_connection(self):
        """Test API connection"""
        try:
            await self.rate_limiter.acquire()
            balance = await self._make_api_call(self.exchange.fetch_balance)
            logger.info("API connection test successful")
            return balance
        except Exception as e:
            raise ExchangeAPIError(f"API connection test failed: {str(e)}")
    
    @backoff.on_exception(
        backoff.expo,
        (ExchangeAPIError, ExchangeRateLimitError),
        max_tries=3,
        max_time=60
    )
    async def _make_api_call(self, func, *args, **kwargs):
        """Make API call with rate limiting and error handling"""
        await self.rate_limiter.acquire()
        
        try:
            result = await self.circuit_breaker.call(func, *args, **kwargs)
            self.api_calls_count += 1
            return result
            
        except ccxt.RateLimitExceeded as e:
            self.errors_count += 1
            raise ExchangeRateLimitError(f"Rate limit exceeded: {str(e)}")
        except ccxt.NetworkError as e:
            self.errors_count += 1
            raise ExchangeConnectionError(f"Network error: {str(e)}")
        except ccxt.ExchangeError as e:
            self.errors_count += 1
            raise ExchangeAPIError(f"Exchange error: {str(e)}")
        except Exception as e:
            self.errors_count += 1
            raise ExchangeAPIError(f"Unexpected error: {str(e)}")
    
    # Market data methods
    @handle_async_exceptions()
    async def get_ticker(self, symbol: str) -> Dict[str, Any]:
        """Get ticker data"""
        # Try WebSocket data first
        if symbol in self.websocket_manager.price_data:
            ws_data = self.websocket_manager.price_data[symbol]
            if time.time() - ws_data['timestamp'] < 10:  # Data is fresh
                return ws_data
        
        # Fallback to API
        cache_key = f"ticker_{symbol}"
        if cache_key in self.cache:
            return self.cache[cache_key]
        
        ticker = await self._make_api_call(self.exchange.fetch_ticker, symbol)
        self.cache[cache_key] = ticker
        return ticker
    
    @handle_async_exceptions()
    async def get_orderbook(self, symbol: str, limit: int = 20) -> Dict[str, Any]:
        """Get orderbook data"""
        # Try WebSocket data first
        if symbol in self.websocket_manager.orderbook_data:
            ws_data = self.websocket_manager.orderbook_data[symbol]
            if time.time() - ws_data['timestamp'] < 5:  # Fresh orderbook data
                return ws_data
        
        # Fallback to API
        orderbook = await self._make_api_call(self.exchange.fetch_order_book, symbol, limit)
        return orderbook
    
    @handle_async_exceptions()
    async def get_ohlcv(self, symbol: str, timeframe: str = '1m', limit: int = 100) -> List[List]:
        """Get OHLCV data"""
        cache_key = f"ohlcv_{symbol}_{timeframe}_{limit}"
        if cache_key in self.cache:
            return self.cache[cache_key]
        
        ohlcv = await self._make_api_call(self.exchange.fetch_ohlcv, symbol, timeframe, limit=limit)
        self.cache[cache_key] = ohlcv
        return ohlcv
    
    @handle_async_exceptions()
    async def get_recent_trades(self, symbol: str, limit: int = 50) -> List[Dict]:
        """Get recent trades"""
        # Try WebSocket data first
        if symbol in self.websocket_manager.trade_data:
            ws_trades = self.websocket_manager.trade_data[symbol][-limit:]
            if ws_trades:
                return ws_trades
        
        # Fallback to API
        trades = await self._make_api_call(self.exchange.fetch_trades, symbol, limit=limit)
        return trades
    
    # Trading methods
    @handle_async_exceptions()
    async def create_order(self, symbol: str, order_type: str, side: str, 
                          amount: float, price: Optional[float] = None, 
                          params: Optional[Dict] = None) -> Dict[str, Any]:
        """Create order"""
        try:
            order = await self._make_api_call(
                self.exchange.create_order,
                symbol, order_type, side, amount, price, params or {}
            )
            
            logger.info(f"Order created: {order['id']} - {side} {amount} {symbol} @ {price}")
            return order
            
        except Exception as e:
            raise TradingError(
                f"Failed to create order: {str(e)}",
                symbol=symbol,
                context={'side': side, 'amount': amount, 'price': price}
            )
    
    @handle_async_exceptions()
    async def cancel_order(self, order_id: str, symbol: str) -> Dict[str, Any]:
        """Cancel order"""
        try:
            result = await self._make_api_call(self.exchange.cancel_order, order_id, symbol)
            logger.info(f"Order cancelled: {order_id}")
            return result
        except Exception as e:
            raise TradingError(f"Failed to cancel order: {str(e)}", order_id=order_id, symbol=symbol)
    
    @handle_async_exceptions()
    async def get_order(self, order_id: str, symbol: str) -> Dict[str, Any]:
        """Get order status"""
        try:
            order = await self._make_api_call(self.exchange.fetch_order, order_id, symbol)
            return order
        except Exception as e:
            raise TradingError(f"Failed to fetch order: {str(e)}", order_id=order_id, symbol=symbol)
    
    @handle_async_exceptions()
    async def get_open_orders(self, symbol: Optional[str] = None) -> List[Dict[str, Any]]:
        """Get open orders"""
        try:
            orders = await self._make_api_call(self.exchange.fetch_open_orders, symbol)
            return orders
        except Exception as e:
            raise TradingError(f"Failed to fetch open orders: {str(e)}", symbol=symbol)
    
    @handle_async_exceptions()
    async def get_positions(self, symbol: Optional[str] = None) -> List[Dict[str, Any]]:
        """Get positions"""
        try:
            positions = await self._make_api_call(self.exchange.fetch_positions, [symbol] if symbol else None)
            return [pos for pos in positions if pos['contracts'] > 0]
        except Exception as e:
            raise TradingError(f"Failed to fetch positions: {str(e)}", symbol=symbol)
    
    @handle_async_exceptions()
    async def get_balance(self) -> Dict[str, Any]:
        """Get account balance"""
        try:
            balance = await self._make_api_call(self.exchange.fetch_balance)
            return balance
        except Exception as e:
            raise TradingError(f"Failed to fetch balance: {str(e)}")
    
    # Health and monitoring
    async def health_check(self) -> Dict[str, Any]:
        """Check exchange manager health"""
        try:
            start_time = time.time()
            await self._test_connection()
            response_time = time.time() - start_time
            
            self.last_health_check = datetime.utcnow()
            
            return {
                'status': 'healthy',
                'response_time': response_time,
                'api_calls': self.api_calls_count,
                'errors': self.errors_count,
                'websocket_connected': self.websocket_manager.connected,
                'websocket_messages': self.websocket_manager.messages_received,
                'circuit_breaker_state': self.circuit_breaker.state,
                'last_check': self.last_health_check.isoformat()
            }
        except Exception as e:
            return {
                'status': 'unhealthy',
                'error': str(e),
                'last_check': self.last_health_check.isoformat() if self.last_health_check else None
            }
    
    async def cleanup(self):
        """Cleanup resources"""
        try:
            await self.websocket_manager.disconnect()
            logger.info("Exchange manager cleanup completed")
        except Exception as e:
            logger.error(f"Error during cleanup: {e}")
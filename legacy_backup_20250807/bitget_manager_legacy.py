"""
Enhanced Bitget Exchange Manager
Complete exchange operations and WebSocket management
"""

import asyncio
import logging
import json
import time
from typing import Dict, List, Optional, Any
from datetime import datetime
from collections import deque
import numpy as np
import pandas as pd
import websockets
import ccxt
import backoff
from cachetools import TTLCache

# Import handling for both direct and package imports
try:
    from ..config.config import TradingConfig
    from ..utils.errors import ExchangeError
except ImportError:
    import sys
    import os
    sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    from config.config import TradingConfig
    from utils.errors import ExchangeError


class EnhancedBitgetExchangeManager:
    """Bitget exchange manager with fixed WebSocket implementation"""
    
    def __init__(self, config: TradingConfig):
        self.config = config
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
        self.logger = logging.getLogger(__name__)
        
        # WebSocket data
        self.ws_connected = False
        self.price_data = {}
        self.orderbook_data = {}
        self.ws_task = None
        self.ws_health_task = None  # Health monitor task 참조 저장
        self.ws_reconnect_attempts = 0
        
        # Enhanced WebSocket monitoring
        self.last_ws_message_time = None
        self.ws_health_check_interval = self.config.WS_HEALTH_CHECK_INTERVAL
        self.ws_message_timeout = self.config.WS_MESSAGE_TIMEOUT
        
        # Circuit breaker
        self.error_count = 0
        self.max_errors = 5
        self.last_error_time = None
        
        # Cache
        self.cache = TTLCache(maxsize=config.INDICATOR_CACHE_SIZE, ttl=config.CACHE_TTL)
        
        # Rate limiting
        self.rate_limiter = self._create_rate_limiter()
    
    def _create_rate_limiter(self):
        """Create rate limiter"""
        return {
            'calls': deque(maxlen=30),
            'max_calls': 30,
            'time_window': 60
        }
    
    async def _check_rate_limit(self):
        """Check and enforce rate limits"""
        current_time = time.time()
        
        # Remove old calls
        while self.rate_limiter['calls'] and self.rate_limiter['calls'][0] < current_time - self.rate_limiter['time_window']:
            self.rate_limiter['calls'].popleft()
        
        # Check if limit exceeded
        if len(self.rate_limiter['calls']) >= self.rate_limiter['max_calls']:
            sleep_time = self.rate_limiter['calls'][0] + self.rate_limiter['time_window'] - current_time
            if sleep_time > 0:
                self.logger.warning(f"Rate limit 도달, {sleep_time:.2f}초 대기")
                await asyncio.sleep(sleep_time)
        
        # Add current call
        self.rate_limiter['calls'].append(current_time)
    
    async def initialize(self):
        """Initialize exchange connection"""
        try:
            # Test connection
            await self.get_balance()
            
            # Set position mode to One-way for all symbols
            await self._set_position_mode_oneway()
            
            # Start WebSocket if enabled
            if self.config.USE_WEBSOCKET:
                self.ws_task = asyncio.create_task(self._websocket_manager())
                # Start health check task
                self.ws_health_task = asyncio.create_task(self._websocket_health_monitor())
                
            self.logger.info("거래소 매니저 초기화 완료")
            
        except Exception as e:
            self.logger.error(f"거래소 초기화 실패: {e}")
            raise
    
    async def _websocket_manager(self):
        """Enhanced WebSocket manager with better error handling and fallback mode"""
        max_consecutive_failures = 5
        consecutive_failures = 0
        fallback_mode = False
        
        while True:
            try:
                if not fallback_mode:
                    await self._connect_websocket()
                    consecutive_failures = 0
                    if fallback_mode:
                        self.logger.info("🔄 WebSocket 연결 복구 - 실시간 모드 재개")
                        fallback_mode = False
                else:
                    # Fallback mode: use REST API instead of WebSocket
                    await self._fallback_price_update()
                    await asyncio.sleep(5)
                    
            except Exception as e:
                self.ws_connected = False
                consecutive_failures += 1
                self.ws_reconnect_attempts += 1
                
                error_type = type(e).__name__
                self.logger.error(f"🚫 WebSocket 오류 ({error_type}) - 시도 {self.ws_reconnect_attempts}: {str(e)[:100]}")
                
                # Activate fallback mode after consecutive failures
                if consecutive_failures >= max_consecutive_failures and not fallback_mode:
                    self.logger.warning(f"[WARNING] WebSocket 연속 실패 {consecutive_failures}회 - 대체 모드 활성화")
                    fallback_mode = True
                    consecutive_failures = 0
                    await asyncio.sleep(10)
                    continue
                    
                # Calculate wait time based on error type
                if 'rate limit' in str(e).lower() or 'too many requests' in str(e).lower():
                    wait_time = 60  # 1 minute for rate limiting
                elif 'network' in str(e).lower() or 'timeout' in str(e).lower():
                    wait_time = self.config.NETWORK_RETRY_WAIT  # 네트워크 재시도 대기시간
                else:
                    # Exponential backoff with jitter
                    base_wait = min(120, 10 * (1.5 ** min(consecutive_failures, 5)))
                    jitter = base_wait * 0.2 * (0.5 - np.random.random())
                    wait_time = base_wait + jitter
                
                self.logger.info(f"[RETRY] {wait_time:.1f}초 후 WebSocket 재연결 시도...")
                await asyncio.sleep(wait_time)
    
    async def _connect_websocket(self):
        """Enhanced WebSocket connection with multiple URL fallbacks (Fixed)"""
        ws_urls = [
            "wss://ws.bitget.com/v2/ws/public",
            "wss://ws.bitgetapi.com/v2/ws/public", 
            "wss://ws.bitget.com/mix/v1/stream"
        ]
        
        for i, ws_url in enumerate(ws_urls):
            try:
                self.logger.info(f"🔌 WebSocket 연결 시도 ({i+1}/{len(ws_urls)}): {ws_url}")
                
                # Fixed: Remove extra_headers parameter
                async with websockets.connect(
                    ws_url,
                    ping_interval=20,
                    ping_timeout=10,
                    close_timeout=10,
                    max_size=2**20  # 1MB message size limit
                ) as websocket:
                    self.ws_connected = True
                    self.ws_reconnect_attempts = 0
                    self.logger.info(f"[SUCCESS] WebSocket 연결 성공: {ws_url}")
                    
                    # Subscribe to channels
                    await self._subscribe_channels(websocket)
                    
                    # Message handling loop with health checks
                    await self._handle_websocket_messages(websocket)
                    
            except (websockets.exceptions.ConnectionClosed, 
                   websockets.exceptions.InvalidURI,
                   websockets.exceptions.InvalidHandshake) as e:
                self.logger.warning(f"[FAIL] WebSocket URL {i+1} 실패: {type(e).__name__} - {str(e)[:50]}")
                if i == len(ws_urls) - 1:  # Last URL failed
                    raise e
                continue
                
            except Exception as e:
                self.logger.error(f"❌ 예상치 못한 WebSocket 오류: {type(e).__name__}")
                if i == len(ws_urls) - 1:
                    raise e
                continue
        
        self.ws_connected = False
        raise ConnectionError("모든 WebSocket URL 연결 실패")
    
    async def _websocket_health_monitor(self):
        """WebSocket 연결 상태 모니터링"""
        while True:
            try:
                await asyncio.sleep(self.ws_health_check_interval)
                
                if self.ws_connected and self.last_ws_message_time:
                    # 마지막 메시지로부터 경과 시간 확인
                    time_since_last_message = (datetime.now() - self.last_ws_message_time).total_seconds()
                    
                    if time_since_last_message > self.ws_message_timeout:
                        self.logger.warning(f"⚠️ WebSocket 응답 없음 ({time_since_last_message:.0f}초) - 재연결 필요")
                        self.ws_connected = False
                        
                        # WebSocket 태스크 재시작
                        if self.ws_task and not self.ws_task.done():
                            self.ws_task.cancel()
                        self.ws_task = asyncio.create_task(self._websocket_manager())
                        
                elif not self.ws_connected:
                    self.logger.debug("🔍 WebSocket 연결 대기 중...")
                    
            except Exception as e:
                self.logger.error(f"❌ WebSocket 헬스체크 오류: {e}")
                await asyncio.sleep(10)
        
    async def _handle_websocket_messages(self, websocket):
        """Handle WebSocket messages with enhanced monitoring"""
        last_message_time = datetime.now()
        heartbeat_timeout = 90  # 1.5 minutes
        message_count = 0
        
        async for message in websocket:
            try:
                current_time = datetime.now()
                last_message_time = current_time
                message_count += 1
                
                await self._handle_ws_message(message)
                
                # Log connection health every 100 messages
                if message_count % 100 == 0:
                    self.logger.info(f"📊 WebSocket 건강 상태: {message_count}개 메시지 수신 완료")
                
                # Enhanced stale connection check
                if (current_time - last_message_time).total_seconds() > heartbeat_timeout:
                    self.logger.warning(f"⏰ WebSocket 응답 없음 ({heartbeat_timeout}초) - 재연결 실행")
                    break
                    
            except asyncio.CancelledError:
                self.logger.info("🚫 WebSocket 작업 취소됨")
                break
            except Exception as msg_error:
                self.logger.error(f"❌ WebSocket 메시지 처리 오류: {type(msg_error).__name__}: {str(msg_error)[:100]}")
                continue
                
    async def _fallback_price_update(self):
        """Fallback price updates using REST API when WebSocket fails"""
        try:
            for symbol in self.config.SYMBOLS:
                try:
                    # Use REST API to get current price
                    ticker = await asyncio.get_event_loop().run_in_executor(
                        None, self.exchange.fetch_ticker, self._format_symbol(symbol)
                    )
                    
                    if ticker:
                        self.price_data[symbol] = {
                            'last': ticker['last'],
                            'bid': ticker['bid'],
                            'ask': ticker['ask'],
                            'timestamp': ticker['timestamp'],
                            'source': 'REST_FALLBACK'
                        }
                        
                except Exception as e:
                    self.logger.error(f"❌ REST API 가격 업데이트 실패 {symbol}: {e}")
                    
            if self.price_data:
                self.logger.debug(f"🔄 대체 모드: {len(self.price_data)}개 종목 가격 업데이트 완료")
                
        except Exception as e:
            self.logger.error(f"❌ 대체 가격 업데이트 실패: {e}")
    
    async def _subscribe_channels(self, websocket):
        """Subscribe to WebSocket channels with correct Bitget format"""
        for symbol in self.config.SYMBOLS:
            # Bitget v2 API 올바른 구독 형식 (선물)
            # UMCBL 대신 DMCBL 사용 또는 심볼 형식 변경
            formatted_symbol = self._format_symbol_for_ws(symbol)
            subscribe_msg = {
                "op": "subscribe",
                "args": [
                    {
                        "instType": "SUSDT-FUTURES",  # SUSDT 선물거래
                        "channel": "ticker",
                        "instId": formatted_symbol  # 올바른 심볼 형식 사용
                    }
                ]
            }
            await websocket.send(json.dumps(subscribe_msg))
            self.logger.info(f"📡 구독 요청: {formatted_symbol} ticker (UMCBL)")
            await asyncio.sleep(0.2)  # 요청 간 딜레이 증가
    
    async def _handle_ws_message(self, message: str):
        """Handle WebSocket message"""
        try:
            # 🔄 메시지 수신 시간 업데이트
            self.last_ws_message_time = datetime.now()
            
            data = json.loads(message)
            
            if data.get('event') == 'error':
                self.logger.error(f"WebSocket 오류: {data}")
                return
            
            if 'data' in data:
                for item in data['data']:
                    if data.get('arg', {}).get('channel') == 'ticker':
                        symbol = item.get('instId')
                        self.price_data[symbol] = {
                            'last': float(item.get('last', 0)),
                            'bid': float(item.get('bidPx', 0)),
                            'ask': float(item.get('askPx', 0)),
                            'volume': float(item.get('vol24h', 0)),
                            'timestamp': int(item.get('ts', 0))
                        }
                    
                    elif data.get('arg', {}).get('channel') == 'books5':
                        symbol = item.get('instId')
                        self.orderbook_data[symbol] = {
                            'bids': item.get('bids', []),
                            'asks': item.get('asks', []),
                            'timestamp': int(item.get('ts', 0))
                        }
                        
        except Exception as e:
            self.logger.error(f"WebSocket 메시지 처리 오류: {e}")
    
    @backoff.on_exception(backoff.expo, Exception, max_tries=3)
    async def fetch_ohlcv_with_cache(self, symbol: str, timeframe: str, limit: int = 1000) -> pd.DataFrame:
        """Fetch OHLCV with caching and retry"""
        cache_key = f"ohlcv:{symbol}:{timeframe}"
        
        # Check cache first
        cached = self.cache.get(cache_key)
        if cached is not None:
            return cached
        
        # Fetch from exchange
        df = await self.fetch_ohlcv(symbol, timeframe, limit)
        
        # Cache if successful
        if df is not None and not df.empty:
            self.cache[cache_key] = df
        
        return df
    
    async def fetch_ohlcv(self, symbol: str, timeframe: str, limit: int = 1000) -> pd.DataFrame:
        """Fetch OHLCV data with error handling"""
        await self._check_rate_limit()
        
        try:
            market_symbol = self._format_symbol(symbol)
            
            ohlcv = await asyncio.get_event_loop().run_in_executor(
                None,
                self.exchange.fetch_ohlcv,
                market_symbol,
                timeframe,
                None,
                limit
            )
            
            if not ohlcv:
                return pd.DataFrame()
            
            df = pd.DataFrame(ohlcv, columns=['timestamp', 'open', 'high', 'low', 'close', 'volume'])
            df['timestamp'] = pd.to_datetime(df['timestamp'], unit='ms')
            df.set_index('timestamp', inplace=True)
            
            # Reset error count on success
            self.error_count = 0
            
            return df
            
        except Exception as e:
            self._handle_error(e)
            return pd.DataFrame()
    
    def _handle_error(self, error: Exception):
        """Handle errors with circuit breaker"""
        self.error_count += 1
        self.last_error_time = datetime.now()
        
        if self.error_count >= self.max_errors:
            self.logger.critical(f"{self.max_errors}개 오류 후 회로 차단기 작동")
            raise ExchangeError("거래소 회로 차단기 작동")
        
        self.logger.error(f"거래소 오류 ({self.error_count}/{self.max_errors}): {error}")
    
    async def get_balance(self) -> Dict:
        """Get account balance"""
        await self._check_rate_limit()
        
        try:
            balance = await asyncio.get_event_loop().run_in_executor(
                None,
                self.exchange.fetch_balance
            )
            self.error_count = 0
            return balance
        except Exception as e:
            self._handle_error(e)
            return {}
    
    async def get_positions(self, symbol: Optional[str] = None) -> List[Dict]:
        """Get open positions"""
        await self._check_rate_limit()
        
        try:
            positions = await asyncio.get_event_loop().run_in_executor(
                None,
                self.exchange.fetch_positions,
                [self._format_symbol(symbol)] if symbol else None
            )
            self.error_count = 0
            return positions
        except Exception as e:
            self._handle_error(e)
            return []
    
    async def place_order(self, symbol: str, side: str, amount: float, 
                         order_type: str = 'market', price: Optional[float] = None,
                         params: Optional[Dict] = None) -> Dict:
        """Place order with enhanced parameters"""
        await self._check_rate_limit()
        
        # 🛡️ PAPER_TRADING 모드 체크
        if self.config.PAPER_TRADING:
            self.logger.info(f"🟡 PAPER_TRADING: {symbol} {side} {amount} @ {price or '시장가'} (모의 주문)")
            # 시뮬레이션 주문 응답 생성
            return {
                'id': f'paper_{int(time.time())}',
                'symbol': symbol,
                'side': side,
                'amount': amount,
                'price': price or (self.get_current_price(symbol) or 50000),
                'filled': amount,
                'status': 'closed',
                'paper_trade': True,
                'timestamp': int(time.time() * 1000)
            }
        
        try:
            market_symbol = self._format_symbol(symbol)
            
            # Set leverage
            leverage = self.config.LEVERAGE.get(symbol, 10)
            await self.set_leverage(symbol, leverage)
            
            # Calculate slippage for market orders
            if order_type == 'market' and self.ws_connected:
                price_data = self.price_data.get(symbol, {})
                if side == 'buy' and 'ask' in price_data:
                    estimated_price = price_data['ask']
                elif side == 'sell' and 'bid' in price_data:
                    estimated_price = price_data['bid']
                else:
                    estimated_price = price_data.get('last', price)
            else:
                estimated_price = price
            
            # Bitget specific parameters for futures trading
            # One-way position mode - positionSide 파라미터 제거 (Bitget 요구사항)
            order_params = {
                'marginMode': 'isolated',  # isolated margin mode
                'timeInForce': 'IOC',      # Immediate or Cancel
                **(params or {})
            }
            
            # One-way 모드에서는 positionSide를 명시하지 않음
            # 이는 Bitget API의 요구사항임
            
            # Place order
            order = await asyncio.get_event_loop().run_in_executor(
                None,
                self.exchange.create_order,
                market_symbol,
                order_type,
                side,
                amount,
                price,
                order_params
            )
            
            # Calculate actual slippage
            if order_type == 'market' and estimated_price:
                actual_price = order.get('price', estimated_price)
                slippage = abs(actual_price - estimated_price) / estimated_price
                order['slippage'] = slippage
            
            self.error_count = 0
            self.logger.info(f"주문 실행: {symbol} {side} {amount} @ {price or '시장가'}")
            return order
            
        except Exception as e:
            self._handle_error(e)
            return {}
    
    async def place_stop_loss_order(self, symbol: str, side: str, amount: float, 
                                   stop_price: float) -> Dict:
        """Place stop loss order"""
        params = {
            'stopPrice': stop_price,
            'triggerType': 'market_price',
            'timeInForce': 'GTC'
        }
        
        return await self.place_order(
            symbol, 
            side, 
            amount, 
            order_type='stop',
            params=params
        )
    
    async def modify_stop_loss(self, symbol: str, order_id: str, new_stop_price: float) -> Dict:
        """Modify existing stop loss order"""
        await self._check_rate_limit()
        
        try:
            market_symbol = self._format_symbol(symbol)
            
            # Cancel old order
            await asyncio.get_event_loop().run_in_executor(
                None,
                self.exchange.cancel_order,
                order_id,
                market_symbol
            )
            
            # Get position to determine side and amount
            positions = await self.get_positions(symbol)
            if positions:
                position = positions[0]
                side = 'sell' if position['side'] == 'long' else 'buy'
                amount = position['contracts']
                
                # Place new stop loss
                return await self.place_stop_loss_order(symbol, side, amount, new_stop_price)
            
            return {}
            
        except Exception as e:
            self.logger.error(f"손절가 수정 실패: {e}")
            return {}
    
    async def close_position(self, symbol: str, reason: str = "manual") -> Dict:
        """Close position with reason"""
        try:
            positions = await self.get_positions(symbol)
            
            for position in positions:
                if position['contracts'] > 0:
                    side = 'sell' if position['side'] == 'long' else 'buy'
                    amount = position['contracts']
                    
                    order = await self.place_order(symbol, side, amount)
                    
                    self.logger.info(f"포지션 마감: {symbol} - 사유: {reason}")
                    return order
            
            return {}
            
        except Exception as e:
            self._handle_error(e)
            return {}
    
    async def set_leverage(self, symbol: str, leverage: int):
        """Set leverage for symbol"""
        await self._check_rate_limit()
        
        try:
            market_symbol = self._format_symbol(symbol)
            
            await asyncio.get_event_loop().run_in_executor(
                None,
                self.exchange.set_leverage,
                leverage,
                market_symbol
            )
            
            self.error_count = 0
            
        except Exception as e:
            self.logger.error(f"레버리지 설정 실패: {e}")
    
    def _format_symbol(self, symbol: str) -> str:
        """Format symbol for Bitget"""
        # BTCUSDT -> BTC/USDT:USDT
        base = symbol[:-4]
        return f"{base}/USDT:USDT"
    
    def _format_symbol_for_ws(self, symbol: str) -> str:
        """Format symbol for WebSocket subscription"""
        # WebSocket에서는 BTCUSDT 형식 그대로 사용
        return symbol
    
    async def calculate_position_size(self, symbol: str, position_value: float) -> float:
        """Calculate position size in contracts"""
        try:
            # Use WebSocket price if available
            if self.ws_connected and symbol in self.price_data:
                current_price = self.price_data[symbol]['last']
            else:
                ticker = await asyncio.get_event_loop().run_in_executor(
                    None,
                    self.exchange.fetch_ticker,
                    self._format_symbol(symbol)
                )
                current_price = ticker['last']
            
            contract_size = self._get_contract_size(symbol)
            
            # Prevent division by zero
            denominator = current_price * contract_size
            if denominator == 0:
                self.logger.warning(f"가격 또는 계약 크기가 0입니다. symbol: {symbol}, price: {current_price}, contract_size: {contract_size}")
                return 0
                
            contracts = position_value / denominator
            
            return round(contracts, self._get_precision(symbol))
            
        except Exception as e:
            self.logger.error(f"포지션 크기 계산 실패: {e}")
            return 0
    
    def _get_contract_size(self, symbol: str) -> float:
        """Get contract size for symbol"""
        contract_sizes = {
            "BTCUSDT": 0.001,
            "ETHUSDT": 0.01,
            "XRPUSDT": 1
        }
        return contract_sizes.get(symbol, 0.01)
    
    def _get_precision(self, symbol: str) -> int:
        """Get precision for symbol"""
        precisions = {
            "BTCUSDT": 3,
            "ETHUSDT": 2,
            "XRPUSDT": 0
        }
        return precisions.get(symbol, 2)
    
    def get_current_price(self, symbol: str) -> Optional[float]:
        """Get current price from WebSocket or cache"""
        if self.ws_connected and symbol in self.price_data:
            return self.price_data[symbol]['last']
        return None
    
    async def _set_position_mode_oneway(self):
        """Set position mode to One-way for all symbols"""
        try:
            for symbol in self.config.SYMBOLS:
                try:
                    # Bitget API call to set position mode
                    market_symbol = self._format_symbol(symbol)
                    
                    # Set position mode to One-way (net position)
                    await asyncio.get_event_loop().run_in_executor(
                        None,
                        lambda: self.exchange.set_position_mode(False, market_symbol)  # False = One-way mode
                    )
                    
                    self.logger.info(f"✅ {symbol} 포지션 모드를 One-way로 설정됨")
                    
                except Exception as symbol_error:
                    # 이미 One-way 모드로 설정된 경우 오류가 발생할 수 있음
                    self.logger.warning(f"⚠️ {symbol} 포지션 모드 설정 실패 (이미 설정되었을 수 있음): {symbol_error}")
                    
                # API 레이트 리미팅 방지
                await asyncio.sleep(0.5)
                
        except Exception as e:
            self.logger.warning(f"포지션 모드 설정 중 오류 (계속 진행): {e}")
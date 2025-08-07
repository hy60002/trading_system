"""
Bitget Data Manager
Handles data fetching, caching, and market data operations
"""

import asyncio
import logging
import time
from typing import Dict, List, Optional, Any
import pandas as pd
from cachetools import TTLCache

try:
    from ...config.config import TradingConfig
    from ...utils.errors import ExchangeError
except ImportError:
    import sys
    import os
    sys.path.append(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
    from config.config import TradingConfig
    from utils.errors import ExchangeError


class DataManager:
    """Manages market data fetching and caching"""
    
    def __init__(self, config: TradingConfig, exchange, utils, ws_manager=None):
        self.config = config
        self.exchange = exchange
        self.utils = utils
        self.ws_manager = ws_manager
        self.logger = logging.getLogger(__name__)
        
        # Cache
        self.cache = TTLCache(maxsize=config.INDICATOR_CACHE_SIZE, ttl=config.CACHE_TTL)
        
        # Error tracking
        self.error_count = 0
        self.max_errors = 5
    
    async def fetch_ohlcv_with_cache(self, symbol: str, timeframe: str, limit: int = 1000) -> pd.DataFrame:
        """Fetch OHLCV data with caching"""
        cache_key = f"{symbol}_{timeframe}_{limit}"
        
        # Check cache first
        if cache_key in self.cache:
            self.logger.debug(f"캐시에서 데이터 반환: {cache_key}")
            return self.cache[cache_key]
        
        # Fetch fresh data
        df = await self.fetch_ohlcv(symbol, timeframe, limit)
        
        # Cache the result
        if not df.empty:
            self.cache[cache_key] = df
            self.logger.debug(f"데이터 캐시됨: {cache_key}")
        
        return df
    
    async def fetch_ohlcv(self, symbol: str, timeframe: str, limit: int = 1000) -> pd.DataFrame:
        """Fetch OHLCV data from exchange"""
        try:
            await self.utils.check_rate_limit(self.utils.create_rate_limiter())
            
            market_symbol = self.utils.format_symbol(symbol)
            
            # Fetch OHLCV data
            ohlcv = await asyncio.get_event_loop().run_in_executor(
                None,
                self.exchange.fetch_ohlcv,
                market_symbol,
                timeframe,
                None,
                limit
            )
            
            if not ohlcv:
                self.logger.warning(f"OHLCV 데이터 없음: {symbol} {timeframe}")
                return pd.DataFrame()
            
            # Convert to DataFrame
            df = pd.DataFrame(ohlcv, columns=['timestamp', 'open', 'high', 'low', 'close', 'volume'])
            df['timestamp'] = pd.to_datetime(df['timestamp'], unit='ms')
            df.set_index('timestamp', inplace=True)
            
            # Data validation
            if len(df) < 50:
                self.logger.warning(f"충분하지 않은 데이터: {symbol} {timeframe} ({len(df)}개)")
            
            self.error_count = 0
            return df
            
        except Exception as e:
            self.error_count = self.utils.handle_error(e, self.error_count, self.max_errors)
            return pd.DataFrame()
    
    async def get_balance(self) -> Dict:
        """Get account balance"""
        try:
            await self.utils.check_rate_limit(self.utils.create_rate_limiter())
            
            # 🛡️ PAPER_TRADING 모드 체크
            if self.config.PAPER_TRADING:
                self.logger.debug("🟡 PAPER_TRADING: 모의 잔고 반환")
                return {
                    'USDT': {'free': 10000.0, 'used': 0.0, 'total': 10000.0},
                    'total': 10000.0,
                    'paper_trading': True
                }
            
            balance = await asyncio.get_event_loop().run_in_executor(
                None,
                self.exchange.fetch_balance
            )
            
            self.error_count = 0
            return balance
            
        except Exception as e:
            self.error_count = self.utils.handle_error(e, self.error_count, self.max_errors)
            return {}
    
    async def get_positions(self, symbol: Optional[str] = None) -> List[Dict]:
        """Get current positions"""
        try:
            await self.utils.check_rate_limit(self.utils.create_rate_limiter())
            
            # 🛡️ PAPER_TRADING 모드 체크
            if self.config.PAPER_TRADING:
                self.logger.debug("🟡 PAPER_TRADING: 모의 포지션 반환")
                return []
            
            positions = await asyncio.get_event_loop().run_in_executor(
                None,
                self.exchange.fetch_positions,
                [self.utils.format_symbol(symbol)] if symbol else None
            )
            
            self.error_count = 0
            return positions
            
        except Exception as e:
            self.error_count = self.utils.handle_error(e, self.error_count, self.max_errors)
            return []
    
    async def get_ticker(self, symbol: str) -> Dict:
        """Get ticker data for symbol"""
        try:
            await self.utils.check_rate_limit(self.utils.create_rate_limiter())
            
            market_symbol = self.utils.format_symbol(symbol)
            
            ticker = await asyncio.get_event_loop().run_in_executor(
                None,
                self.exchange.fetch_ticker,
                market_symbol
            )
            
            self.error_count = 0
            return ticker
            
        except Exception as e:
            self.error_count = self.utils.handle_error(e, self.error_count, self.max_errors)
            return {}
    
    async def get_orderbook(self, symbol: str, limit: int = 50) -> Dict:
        """Get orderbook data"""
        try:
            await self.utils.check_rate_limit(self.utils.create_rate_limiter())
            
            market_symbol = self.utils.format_symbol(symbol)
            
            orderbook = await asyncio.get_event_loop().run_in_executor(
                None,
                self.exchange.fetch_order_book,
                market_symbol,
                limit
            )
            
            self.error_count = 0
            return orderbook
            
        except Exception as e:
            self.error_count = self.utils.handle_error(e, self.error_count, self.max_errors)
            return {}
    
    async def get_market_info(self, symbol: str) -> Dict:
        """Get market information for symbol"""
        try:
            await self.utils.check_rate_limit(self.utils.create_rate_limiter())
            
            market_symbol = self.utils.format_symbol(symbol)
            
            # Load markets if not already loaded
            if not hasattr(self.exchange, 'markets') or not self.exchange.markets:
                await asyncio.get_event_loop().run_in_executor(
                    None,
                    self.exchange.load_markets
                )
            
            market_info = self.exchange.markets.get(market_symbol, {})
            
            self.error_count = 0
            return market_info
            
        except Exception as e:
            self.error_count = self.utils.handle_error(e, self.error_count, self.max_errors)
            return {}
    
    async def get_trading_fees(self, symbol: str) -> Dict:
        """Get trading fees for symbol"""
        try:
            market_info = await self.get_market_info(symbol)
            
            # Default fees if not available
            fees = {
                'maker': self.config.MAKER_FEE,
                'taker': self.config.TAKER_FEE
            }
            
            # Update with actual fees if available
            if 'maker' in market_info:
                fees['maker'] = market_info['maker']
            if 'taker' in market_info:
                fees['taker'] = market_info['taker']
            
            return fees
            
        except Exception as e:
            self.logger.error(f"수수료 정보 조회 실패 {symbol}: {e}")
            return {
                'maker': self.config.MAKER_FEE,
                'taker': self.config.TAKER_FEE
            }
    
    def get_current_price(self, symbol: str) -> Optional[float]:
        """Get current price for symbol"""
        # Try WebSocket first
        if self.ws_manager and self.ws_manager.is_connected():
            price = self.ws_manager.get_current_price(symbol)
            if price:
                return price
        
        # Fallback to cache
        cache_key = f"price_{symbol}"
        if cache_key in self.cache:
            return self.cache[cache_key]
        
        return None
    
    async def update_price_cache(self, symbol: str, price: float):
        """Update price cache"""
        cache_key = f"price_{symbol}"
        self.cache[cache_key] = price
    
    async def get_recent_trades(self, symbol: str, limit: int = 100) -> List[Dict]:
        """Get recent trades for symbol"""
        try:
            await self.utils.check_rate_limit(self.utils.create_rate_limiter())
            
            market_symbol = self.utils.format_symbol(symbol)
            
            trades = await asyncio.get_event_loop().run_in_executor(
                None,
                self.exchange.fetch_trades,
                market_symbol,
                None,
                limit
            )
            
            self.error_count = 0
            return trades
            
        except Exception as e:
            self.error_count = self.utils.handle_error(e, self.error_count, self.max_errors)
            return []
    
    def clear_cache(self):
        """Clear all cached data"""
        self.cache.clear()
        self.logger.info("데이터 캐시 클리어됨")
    
    def get_cache_stats(self) -> Dict:
        """Get cache statistics"""
        return {
            'size': len(self.cache),
            'maxsize': self.cache.maxsize,
            'ttl': self.cache.ttl,
            'hits': getattr(self.cache, 'hits', 0),
            'misses': getattr(self.cache, 'misses', 0)
        }
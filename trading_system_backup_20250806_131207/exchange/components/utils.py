"""
Bitget Exchange Utilities
Utility functions for exchange operations
"""

import asyncio
import time
from collections import deque
from typing import Dict, Optional
import logging


class ExchangeUtils:
    """Utility functions for exchange operations"""
    
    def __init__(self, config):
        self.config = config
        self.logger = logging.getLogger(__name__)
    
    def create_rate_limiter(self) -> Dict:
        """Create rate limiter"""
        return {
            'calls': deque(maxlen=30),
            'max_calls': 30,
            'time_window': 60
        }
    
    async def check_rate_limit(self, rate_limiter: Dict):
        """Check and enforce rate limits"""
        current_time = time.time()
        
        # Remove old calls
        while rate_limiter['calls'] and rate_limiter['calls'][0] < current_time - rate_limiter['time_window']:
            rate_limiter['calls'].popleft()
        
        # Check if limit exceeded
        if len(rate_limiter['calls']) >= rate_limiter['max_calls']:
            sleep_time = rate_limiter['calls'][0] + rate_limiter['time_window'] - current_time
            if sleep_time > 0:
                self.logger.warning(f"Rate limit 도달, {sleep_time:.2f}초 대기")
                await asyncio.sleep(sleep_time)
        
        # Add current call
        rate_limiter['calls'].append(current_time)
    
    def format_symbol(self, symbol: str) -> str:
        """Format symbol for Bitget API"""
        if 'USDT' in symbol:
            return symbol
        return symbol + 'USDT'
    
    def format_symbol_for_ws(self, symbol: str) -> str:
        """Format symbol specifically for WebSocket subscriptions"""
        return symbol.replace('USDT', 'USDT_UMCBL')
    
    async def calculate_position_size(self, symbol: str, position_value: float, exchange) -> float:
        """Calculate position size based on value and contract specifications"""
        try:
            # Get contract size
            contract_size = self._get_contract_size(symbol)
            
            # Calculate quantity
            current_price = await self._get_current_price_fallback(symbol, exchange)
            if not current_price:
                raise Exception(f"가격 정보를 가져올 수 없습니다: {symbol}")
            
            # Calculate quantity in contracts
            quantity = position_value / (current_price * contract_size)
            
            # Apply precision
            precision = self._get_precision(symbol)
            quantity = round(quantity, precision)
            
            return max(quantity, contract_size)  # Ensure minimum contract size
        
        except Exception as e:
            self.logger.error(f"포지션 크기 계산 오류 {symbol}: {e}")
            raise
    
    def _get_contract_size(self, symbol: str) -> float:
        """Get contract size for symbol"""
        contract_sizes = {
            'BTCUSDT': 0.001,
            'ETHUSDT': 0.01,
            'XRPUSDT': 1.0
        }
        return contract_sizes.get(symbol, 0.001)
    
    def _get_precision(self, symbol: str) -> int:
        """Get decimal precision for symbol"""
        precisions = {
            'BTCUSDT': 3,
            'ETHUSDT': 2,
            'XRPUSDT': 0
        }
        return precisions.get(symbol, 3)
    
    async def _get_current_price_fallback(self, symbol: str, exchange) -> Optional[float]:
        """Get current price with fallback methods"""
        try:
            # Try WebSocket data first
            if hasattr(exchange, 'price_data') and symbol in exchange.price_data:
                return exchange.price_data[symbol].get('price')
            
            # Fallback to REST API
            ticker = await self._fetch_ticker_rest(symbol, exchange)
            if ticker and 'last' in ticker:
                return float(ticker['last'])
            
            return None
        except Exception as e:
            self.logger.error(f"가격 조회 실패 {symbol}: {e}")
            return None
    
    async def _fetch_ticker_rest(self, symbol: str, exchange):
        """Fetch ticker via REST API"""
        try:
            formatted_symbol = self.format_symbol(symbol)
            ticker = await asyncio.get_event_loop().run_in_executor(
                None, exchange.fetch_ticker, formatted_symbol
            )
            return ticker
        except Exception as e:
            self.logger.error(f"REST API 티커 조회 실패 {symbol}: {e}")
            return None
    
    def handle_error(self, error: Exception, error_count: int, max_errors: int = 5) -> int:
        """Handle and count errors with circuit breaker logic"""
        error_count += 1
        self.logger.error(f"거래소 오류 ({error_count}/{max_errors}): {error}")
        
        if error_count >= max_errors:
            self.logger.error("최대 오류 횟수 도달, 시스템 일시 중지")
            # Return error count for circuit breaker decision
        
        return error_count
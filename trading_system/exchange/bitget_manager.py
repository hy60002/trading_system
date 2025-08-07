"""
Enhanced Bitget Exchange Manager - Modularized Version
Main orchestrator for all exchange operations
"""

import asyncio
import logging
import ccxt
from typing import Dict, List, Optional, Any

# Import handling for both direct and package imports
try:
    from ..config.config import TradingConfig
    from ..utils.errors import ExchangeError
    from ..utils.balance_safe_handler import balance_handler
    from .components.utils import ExchangeUtils
    from .components.websocket_manager import WebSocketManager
    from .components.order_manager import OrderManager
    from .components.data_manager import DataManager
except ImportError:
    import sys
    import os
    sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    from config.config import TradingConfig
    from utils.errors import ExchangeError
    from utils.balance_safe_handler import balance_handler
    from .components.utils import ExchangeUtils
    from .components.websocket_manager import WebSocketManager
    from .components.order_manager import OrderManager
    from .components.data_manager import DataManager


class EnhancedBitgetExchangeManager:
    """Modularized Bitget exchange manager"""
    
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
        self.utils = ExchangeUtils(config)
        self.ws_manager = WebSocketManager(config)
        self.order_manager = OrderManager(config, self.exchange, self.utils, self.ws_manager)
        self.data_manager = DataManager(config, self.exchange, self.utils, self.ws_manager)
        
        # Rate limiting
        self.rate_limiter = self.utils.create_rate_limiter()
        
        # Circuit breaker
        self.error_count = 0
        self.max_errors = 5
        self.last_error_time = None
    
    async def initialize(self):
        """Initialize exchange manager and all components"""
        try:
            self.logger.info("🚀 Bitget Exchange Manager 초기화 시작")
            
            # Set position mode to one-way
            await self.order_manager.set_position_mode_oneway()
            
            # Start WebSocket manager
            await self.ws_manager.start()
            
            # Wait a bit for initial WebSocket connection
            await asyncio.sleep(2)
            
            self.logger.info("✅ Bitget Exchange Manager 초기화 완료")
            return True
            
        except Exception as e:
            self.logger.error(f"❌ 초기화 실패: {e}")
            return False
    
    async def shutdown(self):
        """Shutdown exchange manager and all components"""
        try:
            self.logger.info("🛑 Bitget Exchange Manager 종료 시작")
            
            # Stop WebSocket manager
            await self.ws_manager.stop()
            
            # Clear caches
            self.data_manager.clear_cache()
            
            self.logger.info("✅ Bitget Exchange Manager 종료 완료")
            
        except Exception as e:
            self.logger.error(f"❌ 종료 중 오류: {e}")
    
    # Delegate methods to appropriate components
    
    # WebSocket methods
    def is_ws_connected(self) -> bool:
        """Check if WebSocket is connected"""
        return self.ws_manager.is_connected()
    
    def get_current_price(self, symbol: str) -> Optional[float]:
        """Get current price for symbol"""
        return self.data_manager.get_current_price(symbol)
    
    # Order management methods
    async def place_order(self, symbol: str, side: str, amount: float, 
                         order_type: str = 'market', price: Optional[float] = None,
                         params: Optional[Dict] = None) -> Dict:
        """Place order"""
        return await self.order_manager.place_order(symbol, side, amount, order_type, price, params)
    
    async def place_stop_loss_order(self, symbol: str, side: str, amount: float, 
                                   stop_price: float) -> Dict:
        """Place stop loss order"""
        return await self.order_manager.place_stop_loss_order(symbol, side, amount, stop_price)
    
    async def modify_stop_loss(self, symbol: str, order_id: str, new_stop_price: float) -> Dict:
        """Modify existing stop loss order"""
        return await self.order_manager.modify_stop_loss(symbol, order_id, new_stop_price)
    
    async def close_position(self, symbol: str, reason: str = "manual") -> Dict:
        """Close all positions for symbol"""
        return await self.order_manager.close_position(symbol, reason)
    
    async def set_leverage(self, symbol: str, leverage: int):
        """Set leverage for symbol"""
        return await self.order_manager.set_leverage(symbol, leverage)
    
    # Data management methods
    async def fetch_ohlcv(self, symbol: str, timeframe: str, limit: int = 1000):
        """Fetch OHLCV data"""
        return await self.data_manager.fetch_ohlcv(symbol, timeframe, limit)
    
    async def fetch_ohlcv_with_cache(self, symbol: str, timeframe: str, limit: int = 1000):
        """Fetch OHLCV data with caching"""
        return await self.data_manager.fetch_ohlcv_with_cache(symbol, timeframe, limit)
    
    async def get_balance(self) -> Dict:
        """Get account balance - BalanceSafeHandler 적용"""
        return await balance_handler.get_safe_balance(self)
    
    async def get_balance_async(self) -> Dict:
        """직접 잔고 조회 (BalanceSafeHandler에서 사용)"""
        return await self.data_manager.get_balance()
    
    async def get_positions(self, symbol: Optional[str] = None) -> List[Dict]:
        """Get current positions"""
        return await self.data_manager.get_positions(symbol)
    
    async def get_ticker(self, symbol: str) -> Dict:
        """Get ticker data"""
        return await self.data_manager.get_ticker(symbol)
    
    async def get_orderbook(self, symbol: str, limit: int = 50) -> Dict:
        """Get orderbook data"""
        return await self.data_manager.get_orderbook(symbol, limit)
    
    async def get_market_info(self, symbol: str) -> Dict:
        """Get market information"""
        return await self.data_manager.get_market_info(symbol)
    
    async def get_trading_fees(self, symbol: str) -> Dict:
        """Get trading fees"""
        return await self.data_manager.get_trading_fees(symbol)
    
    async def get_recent_trades(self, symbol: str, limit: int = 100) -> List[Dict]:
        """Get recent trades"""
        return await self.data_manager.get_recent_trades(symbol, limit)
    
    # Utility methods
    async def calculate_position_size(self, symbol: str, position_value: float) -> float:
        """Calculate position size"""
        return await self.utils.calculate_position_size(symbol, position_value, self.exchange)
    
    def format_symbol(self, symbol: str) -> str:
        """Format symbol for Bitget API"""
        return self.utils.format_symbol(symbol)
    
    def format_symbol_for_ws(self, symbol: str) -> str:
        """Format symbol for WebSocket"""
        return self.utils.format_symbol_for_ws(symbol)
    
    # Error handling
    def handle_error(self, error: Exception):
        """Handle and count errors"""
        self.error_count = self.utils.handle_error(error, self.error_count, self.max_errors)
        return self.error_count
    
    # Rate limiting
    async def check_rate_limit(self):
        """Check and enforce rate limits"""
        await self.utils.check_rate_limit(self.rate_limiter)
    
    # Health check methods
    def get_health_status(self) -> Dict:
        """Get overall health status"""
        return {
            'ws_connected': self.ws_manager.is_connected(),
            'error_count': self.error_count,
            'max_errors': self.max_errors,
            'cache_stats': self.data_manager.get_cache_stats(),
            'components': {
                'utils': 'active',
                'websocket': 'active' if self.ws_manager.is_connected() else 'inactive',
                'order_manager': 'active',
                'data_manager': 'active'
            }
        }
    
    def get_component_stats(self) -> Dict:
        """Get statistics from all components"""
        return {
            'websocket': {
                'connected': self.ws_manager.is_connected(),
                'reconnect_attempts': self.ws_manager.ws_reconnect_attempts,
                'last_message_time': self.ws_manager.last_ws_message_time
            },
            'cache': self.data_manager.get_cache_stats(),
            'error_count': self.error_count
        }
    
    # Backward compatibility methods (deprecated but maintained for compatibility)
    async def _check_rate_limit(self):
        """Deprecated: Use check_rate_limit() instead"""
        await self.check_rate_limit()
    
    def _format_symbol(self, symbol: str) -> str:
        """Deprecated: Use format_symbol() instead"""
        return self.format_symbol(symbol)
    
    def _format_symbol_for_ws(self, symbol: str) -> str:
        """Deprecated: Use format_symbol_for_ws() instead"""
        return self.format_symbol_for_ws(symbol)
    
    def _handle_error(self, error: Exception):
        """Deprecated: Use handle_error() instead"""
        return self.handle_error(error)
    
    async def _set_position_mode_oneway(self):
        """Deprecated: Use order_manager.set_position_mode_oneway() instead"""
        return await self.order_manager.set_position_mode_oneway()
    
    # Property accessors for backward compatibility
    @property
    def ws_connected(self) -> bool:
        """Backward compatibility property"""
        return self.ws_manager.is_connected()
    
    @property
    def price_data(self) -> Dict:
        """Backward compatibility property"""
        return self.ws_manager.price_data
    
    @property
    def orderbook_data(self) -> Dict:
        """Backward compatibility property"""
        return self.ws_manager.orderbook_data
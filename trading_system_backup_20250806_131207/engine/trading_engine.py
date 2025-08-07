"""
Base Trading Engine
기본 거래 엔진 클래스 - AdvancedTradingEngine의 베이스
"""

import asyncio
import logging
from datetime import datetime
from typing import Dict

try:
    from ..config.config import TradingConfig
    from ..database.db_manager import EnhancedDatabaseManager
    from ..exchange.bitget_manager import EnhancedBitgetExchangeManager
except ImportError:
    import sys
    import os
    sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    from config.config import TradingConfig
    from database.db_manager import EnhancedDatabaseManager
    from exchange.bitget_manager import EnhancedBitgetExchangeManager


class TradingEngine:
    """Base trading engine class"""
    
    def __init__(self, config: TradingConfig):
        self.config = config
        self.logger = logging.getLogger(__name__)
        self.is_running = False
        self.startup_time = datetime.now()
        
        # Initialize basic components
        self.db = EnhancedDatabaseManager(config.DATABASE_PATH)
        self.exchange = EnhancedBitgetExchangeManager(config)
    
    async def initialize(self):
        """Initialize the trading engine"""
        self.logger.info("기본 거래 엔진 초기화 중...")
        await self.exchange.initialize()
        self.logger.info("기본 거래 엔진 초기화 완료")
    
    async def run_trading_cycle(self):
        """Run one trading cycle - to be implemented by subclasses"""
        raise NotImplementedError("Subclasses must implement run_trading_cycle")
    
    def get_system_status(self) -> Dict:
        """Get basic system status"""
        return {
            'status': 'running' if self.is_running else 'stopped',
            'startup_time': self.startup_time.isoformat(),
            'exchange_connected': getattr(self.exchange, 'ws_connected', False)
        }
    
    async def shutdown(self):
        """Shutdown the trading engine"""
        self.logger.info("거래 엔진 종료 중...")
        self.is_running = False
        self.logger.info("거래 엔진 종료 완료")
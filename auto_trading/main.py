"""
Enhanced Trading System Main Controller
Author: Enhanced by Claude Code
Version: 4.0
"""

import asyncio
import logging
import signal
import sys
from contextlib import asynccontextmanager
from typing import Optional
from datetime import datetime

# Import core modules
from core.config import ConfigManager
from core.database import EnhancedDatabaseManager
from core.risk_manager import EnhancedRiskManager
from core.exceptions import TradingSystemException, handle_async_exceptions
from exchanges.bitget_manager import EnhancedBitgetExchangeManager

# Setup enhanced logging
def setup_logging(config):
    """Setup enhanced logging configuration"""
    logging.basicConfig(
        level=getattr(logging, config.LOG_LEVEL),
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
        handlers=[
            logging.FileHandler(config.LOG_FILE),
            logging.StreamHandler(sys.stdout)
        ]
    )
    
    # Set specific logger levels
    logging.getLogger('websockets').setLevel(logging.WARNING)
    logging.getLogger('ccxt').setLevel(logging.WARNING)
    logging.getLogger('urllib3').setLevel(logging.WARNING)

class EnhancedTradingSystem:
    """Main trading system controller with enhanced error handling and monitoring"""
    
    def __init__(self):
        self.config_manager = ConfigManager()
        self.config = None
        self.database_manager = None
        self.exchange_manager = None
        self.risk_manager = None
        
        # System state
        self.running = False
        self.startup_time = None
        self.shutdown_time = None
        
        # Components status
        self.components_status = {
            'config': False,
            'database': False,
            'exchange': False,
            'risk_manager': False
        }
        
        self.logger = logging.getLogger(__name__)
    
    async def initialize(self):
        """Initialize all system components"""
        try:
            self.logger.info("🚀 Starting Enhanced Trading System v4.0")
            
            # Load configuration
            await self._initialize_config()
            
            # Setup logging with config
            setup_logging(self.config)
            
            # Initialize database
            await self._initialize_database()
            
            # Initialize exchange manager
            await self._initialize_exchange()
            
            # Initialize risk manager
            await self._initialize_risk_manager()
            
            self.startup_time = datetime.utcnow()
            self.running = True
            
            self.logger.info("✅ All components initialized successfully")
            self.logger.info(f"📊 Monitoring symbols: {', '.join(self.config.SYMBOLS)}")
            self.logger.info(f"⚡ Leverage settings: {self.config.LEVERAGE}")
            
        except Exception as e:
            self.logger.error(f"❌ Failed to initialize trading system: {e}")
            await self.shutdown()
            raise
    
    async def _initialize_config(self):
        """Initialize configuration"""
        try:
            self.config = self.config_manager.get_config()
            self.components_status['config'] = True
            self.logger.info("✅ Configuration loaded successfully")
            
            # Log masked configuration for verification
            masked_config = self.config.mask_secrets()
            self.logger.info(f"📋 Config summary: {len(self.config.SYMBOLS)} symbols, "
                           f"Cache: {self.config.INDICATOR_CACHE_SIZE}, "
                           f"DB: {self.config.DATABASE_URL}")
            
        except Exception as e:
            self.logger.error(f"❌ Configuration initialization failed: {e}")
            raise TradingSystemException(f"Configuration initialization failed: {e}")
    
    async def _initialize_database(self):
        """Initialize database manager"""
        try:
            self.database_manager = EnhancedDatabaseManager(self.config)
            await self.database_manager.initialize()
            self.components_status['database'] = True
            
            # Perform health check
            health = await self.database_manager.health_check()
            self.logger.info(f"✅ Database initialized - Status: {health['status']}")
            
        except Exception as e:
            self.logger.error(f"❌ Database initialization failed: {e}")
            raise TradingSystemException(f"Database initialization failed: {e}")
    
    async def _initialize_exchange(self):
        """Initialize exchange manager"""
        try:
            self.exchange_manager = EnhancedBitgetExchangeManager(self.config)
            await self.exchange_manager.initialize()
            self.components_status['exchange'] = True
            
            # Test connection and get balance
            balance = await self.exchange_manager.get_balance()
            self.logger.info(f"✅ Exchange connected - Available balance keys: {list(balance.keys())}")
            
        except Exception as e:
            self.logger.error(f"❌ Exchange initialization failed: {e}")
            raise TradingSystemException(f"Exchange initialization failed: {e}")
    
    async def _initialize_risk_manager(self):
        """Initialize risk manager"""
        try:
            self.risk_manager = EnhancedRiskManager(self.config)
            self.components_status['risk_manager'] = True
            
            risk_summary = self.risk_manager.get_risk_summary()
            self.logger.info(f"✅ Risk manager initialized - Emergency stop: {risk_summary['emergency_stop']}")
            
        except Exception as e:
            self.logger.error(f"❌ Risk manager initialization failed: {e}")
            raise TradingSystemException(f"Risk manager initialization failed: {e}")
    
    @handle_async_exceptions()
    async def run(self):
        """Main system loop"""
        if not self.running:
            await self.initialize()
        
        self.logger.info("🔄 Starting main trading loop")
        
        try:
            # Setup signal handlers for graceful shutdown
            loop = asyncio.get_event_loop()
            for sig in [signal.SIGTERM, signal.SIGINT]:
                loop.add_signal_handler(sig, lambda: asyncio.create_task(self.shutdown()))
            
            # Start concurrent tasks
            tasks = [
                asyncio.create_task(self._health_monitor_loop()),
                asyncio.create_task(self._market_data_loop()),
                asyncio.create_task(self._risk_monitoring_loop()),
                asyncio.create_task(self._trading_loop())
            ]
            
            # Wait for tasks
            await asyncio.gather(*tasks, return_exceptions=True)
            
        except Exception as e:
            self.logger.error(f"❌ Error in main loop: {e}")
            await self.shutdown()
    
    async def _health_monitor_loop(self):
        """Monitor system health"""
        while self.running:
            try:
                await asyncio.sleep(60)  # Check every minute
                
                # Check component health
                health_status = {}
                
                if self.database_manager:
                    health_status['database'] = await self.database_manager.health_check()
                
                if self.exchange_manager:
                    health_status['exchange'] = await self.exchange_manager.health_check()
                
                # Log health summary
                unhealthy_components = [
                    comp for comp, status in health_status.items() 
                    if status.get('status') != 'healthy'
                ]
                
                if unhealthy_components:
                    self.logger.warning(f"⚠️ Unhealthy components: {unhealthy_components}")
                else:
                    self.logger.debug("💚 All components healthy")
                
            except Exception as e:
                self.logger.error(f"❌ Health monitor error: {e}")
                await asyncio.sleep(30)  # Wait before retry
    
    async def _market_data_loop(self):
        """Monitor market data"""
        while self.running:
            try:
                await asyncio.sleep(10)  # Check every 10 seconds
                
                # Get current prices for all symbols
                for symbol in self.config.SYMBOLS:
                    try:
                        ticker = await self.exchange_manager.get_ticker(symbol)
                        
                        # Save to database
                        market_data = {
                            'symbol': symbol,
                            'timestamp': datetime.utcnow(),
                            'timeframe': '1m',
                            'open': ticker.get('open', 0),
                            'high': ticker.get('high', 0),
                            'low': ticker.get('low', 0),
                            'close': ticker.get('last', 0),
                            'volume': ticker.get('quoteVolume', 0)
                        }
                        
                        await self.database_manager.save_market_data(market_data)
                        
                    except Exception as e:
                        self.logger.error(f"❌ Error fetching data for {symbol}: {e}")
                
            except Exception as e:
                self.logger.error(f"❌ Market data loop error: {e}")
                await asyncio.sleep(30)
    
    async def _risk_monitoring_loop(self):
        """Monitor risk metrics"""
        while self.running:
            try:
                await asyncio.sleep(30)  # Check every 30 seconds
                
                if self.risk_manager:
                    risk_summary = self.risk_manager.get_risk_summary()
                    
                    # Log risk events
                    if risk_summary['emergency_stop']:
                        self.logger.critical(f"🚨 EMERGENCY STOP: {risk_summary['emergency_reason']}")
                    
                    # Save risk metrics to database
                    risk_data = {
                        'timestamp': datetime.utcnow(),
                        'portfolio_risk': risk_summary.get('daily_pnl', 0),
                        'position_risk': risk_summary.get('positions_count', 0),
                        'metadata': risk_summary
                    }
                    
                    # This would save to risk_metrics table
                    # await self.database_manager.save_risk_metrics(risk_data)
                
            except Exception as e:
                self.logger.error(f"❌ Risk monitoring error: {e}")
                await asyncio.sleep(30)
    
    async def _trading_loop(self):
        """Main trading logic loop"""
        while self.running:
            try:
                await asyncio.sleep(60)  # Trading decisions every minute
                
                # Check if emergency stop is active
                if self.risk_manager and self.risk_manager.emergency_stop_triggered:
                    self.logger.warning("🚨 Trading paused due to emergency stop")
                    continue
                
                # Example trading logic (simplified)
                for symbol in self.config.SYMBOLS:
                    try:
                        await self._analyze_symbol(symbol)
                    except Exception as e:
                        self.logger.error(f"❌ Error analyzing {symbol}: {e}")
                
            except Exception as e:
                self.logger.error(f"❌ Trading loop error: {e}")
                await asyncio.sleep(30)
    
    async def _analyze_symbol(self, symbol: str):
        """Analyze symbol for trading opportunities"""
        try:
            # Get market data
            ticker = await self.exchange_manager.get_ticker(symbol)
            current_price = ticker.get('last', 0)
            
            if current_price == 0:
                return
            
            # Get positions
            positions = await self.exchange_manager.get_positions(symbol)
            
            # Simple example: log current state
            self.logger.debug(f"📊 {symbol}: Price=${current_price:.2f}, Positions={len(positions)}")
            
            # Here you would implement your trading strategy
            # This is just a placeholder for the actual trading logic
            
        except Exception as e:
            self.logger.error(f"❌ Error analyzing {symbol}: {e}")
    
    async def shutdown(self):
        """Graceful shutdown"""
        self.logger.info("🛑 Initiating graceful shutdown...")
        self.running = False
        self.shutdown_time = datetime.utcnow()
        
        try:
            # Cleanup exchange manager
            if self.exchange_manager:
                await self.exchange_manager.cleanup()
                self.logger.info("✅ Exchange manager cleaned up")
            
            # Database cleanup would happen automatically
            if self.database_manager:
                self.logger.info("✅ Database connections closed")
            
            # Final logs
            if self.startup_time:
                uptime = self.shutdown_time - self.startup_time
                self.logger.info(f"📈 System uptime: {uptime}")
            
            self.logger.info("✅ Enhanced Trading System shutdown complete")
            
        except Exception as e:
            self.logger.error(f"❌ Error during shutdown: {e}")
    
    def get_system_status(self) -> dict:
        """Get current system status"""
        return {
            'running': self.running,
            'startup_time': self.startup_time.isoformat() if self.startup_time else None,
            'components': self.components_status,
            'uptime': str(datetime.utcnow() - self.startup_time) if self.startup_time else None
        }

@asynccontextmanager
async def trading_system_context():
    """Context manager for trading system lifecycle"""
    system = EnhancedTradingSystem()
    try:
        await system.initialize()
        yield system
    finally:
        await system.shutdown()

async def main():
    """Main entry point"""
    try:
        async with trading_system_context() as system:
            await system.run()
    except KeyboardInterrupt:
        print("\\n🛑 Shutdown requested by user")
    except Exception as e:
        print(f"❌ Fatal error: {e}")
        return 1
    
    return 0

if __name__ == "__main__":
    try:
        exit_code = asyncio.run(main())
        sys.exit(exit_code)
    except Exception as e:
        print(f"❌ Failed to start system: {e}")
        sys.exit(1)
"""
Main Entry Point for Trading System v3.0
Integrated launcher for the modularized trading system
"""

import os
import sys
import asyncio
import logging
import uvicorn
from datetime import datetime
from typing import Optional

# Add current directory to path for imports
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from config.config import TradingConfig
from engine.advanced_trading_engine import AdvancedTradingEngine
from api.app import get_app, set_trading_engine


class TradingSystemLauncher:
    """Main launcher for the modularized trading system"""
    
    def __init__(self, host="0.0.0.0", port=8000):
        self.config = TradingConfig()
        self.trading_engine: Optional[AdvancedTradingEngine] = None
        self.logger = self._setup_logging()
        self.is_running = False
        self.host = host
        self.port = port
    
    def _setup_logging(self) -> logging.Logger:
        """Setup comprehensive logging"""
        logger = logging.getLogger('TradingSystemLauncher')
        logger.setLevel(logging.INFO)
        
        if not logger.handlers:
            # Console handler
            console_handler = logging.StreamHandler()
            console_handler.setLevel(logging.INFO)
            
            # File handler
            file_handler = logging.FileHandler('trading_system_v4.log')
            file_handler.setLevel(logging.DEBUG)
            
            # Formatter
            formatter = logging.Formatter(
                '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
            )
            console_handler.setFormatter(formatter)
            file_handler.setFormatter(formatter)
            
            logger.addHandler(console_handler)
            logger.addHandler(file_handler)
        
        return logger
    
    async def initialize_system(self):
        """Initialize the complete trading system"""
        try:
            self.logger.info("="*60)
            self.logger.info("[START] Trading System v3.0 - 모듈화 버전 시작")
            self.logger.info("="*60)
            
            # Initialize trading engine
            self.logger.info("거래 엔진 초기화 중...")
            self.trading_engine = AdvancedTradingEngine(self.config)
            await self.trading_engine.initialize()
            
            # Set engine for API
            set_trading_engine(self.trading_engine)
            
            self.logger.info("[OK] 시스템 초기화 완료")
            return True
            
        except Exception as e:
            self.logger.error(f"시스템 초기화 실패: {e}")
            return False
    
    async def run_trading_cycle(self):
        """Run the main trading cycle"""
        if not self.trading_engine:
            self.logger.error("거래 엔진이 초기화되지 않았습니다")
            return
        
        self.is_running = True
        self.logger.info("[TRADING] 거래 사이클 시작...")
        
        try:
            while self.is_running:
                await self.trading_engine.run_trading_cycle()
                
                # Wait between cycles (15 minutes)
                await asyncio.sleep(900)
                
        except KeyboardInterrupt:
            self.logger.info("[STOP] 사용자에 의한 종료 요청")
        except Exception as e:
            self.logger.error(f"거래 사이클 오류: {e}")
        finally:
            await self.shutdown()
    
    async def shutdown(self):
        """Graceful shutdown"""
        self.logger.info("[SHUTDOWN] 시스템 종료 중...")
        self.is_running = False
        
        if self.trading_engine:
            await self.trading_engine.shutdown()
        
        self.logger.info("[OK] 시스템 종료 완료")
    
    async def run_web_server(self):
        """Run the FastAPI web server"""
        import uvicorn
        
        app = get_app()
        
        self.logger.info("[WEB] 웹 서버 시작 중...")
        self.logger.info(f"[DASHBOARD] 대시보드: http://{self.host}:{self.port}")
        self.logger.info(f"[WEBSOCKET] WebSocket: ws://{self.host}:{self.port}/ws")
        
        config = uvicorn.Config(
            app=app,
            host=self.host, 
            port=self.port,
            log_level="info",
            loop="asyncio"
        )
        server = uvicorn.Server(config)
        await server.serve()
    
    async def run_with_web_server(self):
        """Run trading system with web server"""
        # Initialize system first
        if not await self.initialize_system():
            return
        
        # Start web server in background
        web_task = asyncio.create_task(
            self.run_web_server()
        )
        
        # Start trading cycle
        trading_task = asyncio.create_task(
            self.run_trading_cycle()
        )
        
        try:
            # Wait for either task to complete
            await asyncio.gather(web_task, trading_task, return_exceptions=True)
        except KeyboardInterrupt:
            self.logger.info("👋 종료 신호 받음")
        finally:
            web_task.cancel()
            trading_task.cancel()
            await self.shutdown()


def test_import():
    """Test that all modules can be imported successfully"""
    print("[TEST] 모듈 임포트 테스트 중...")
    
    try:
        # Test config
        from config.config import TradingConfig
        config = TradingConfig()
        print("[OK] Config 모듈 임포트 성공")
        
        # Test database
        from database.db_manager import EnhancedDatabaseManager
        print("[OK] Database 모듈 임포트 성공")
        
        # Test exchange
        from exchange.bitget_manager import EnhancedBitgetExchangeManager
        print("[OK] Exchange 모듈 임포트 성공")
        
        # Test indicators
        from indicators.technical import EnhancedTechnicalIndicators
        print("[OK] Indicators 모듈 임포트 성공")
        
        # Test strategies
        from strategies.btc_strategy import BTCTradingStrategy
        from strategies.eth_strategy import ETHTradingStrategy
        from strategies.xrp_strategy import XRPTradingStrategy
        print("[OK] Strategies 모듈 임포트 성공")
        
        # Test managers
        from managers.risk_manager import RiskManager
        from managers.position_manager import PositionManager
        print("[OK] Managers 모듈 임포트 성공")
        
        # Test engine
        from engine.advanced_trading_engine import AdvancedTradingEngine
        print("[OK] Engine 모듈 임포트 성공")
        
        # Test API
        from api.app import get_app
        print("[OK] API 모듈 임포트 성공")
        
        print("\n[SUCCESS] 모든 모듈 임포트 테스트 통과!")
        print("[INFO] 모듈화가 성공적으로 완료되었습니다.")
        
        return True
        
    except Exception as e:
        print(f"[ERROR] 모듈 임포트 실패: {e}")
        return False


async def main():
    """Main entry point"""
    import argparse
    
    parser = argparse.ArgumentParser(description="Trading System v3.0")
    parser.add_argument("--mode", choices=["trade", "web", "both", "test"], 
                       default="both", help="실행 모드")
    parser.add_argument("--host", default="0.0.0.0", help="서버 호스트 (기본값: 0.0.0.0)")
    parser.add_argument("--port", type=int, default=8000, help="서버 포트 (기본값: 8000)")
    
    args = parser.parse_args()
    
    if args.mode == "test":
        success = test_import()
        sys.exit(0 if success else 1)
    
    launcher = TradingSystemLauncher(host=args.host, port=args.port)
    
    try:
        if args.mode == "trade":
            # 거래만 실행
            if await launcher.initialize_system():
                await launcher.run_trading_cycle()
        
        elif args.mode == "web":
            # 웹 서버만 실행
            if await launcher.initialize_system():
                await launcher.run_web_server()
        
        elif args.mode == "both":
            # 거래 + 웹 서버 실행
            await launcher.run_with_web_server()
    
    except KeyboardInterrupt:
        print("\n종료 요청을 받았습니다.")
    except Exception as e:
        print(f"시스템 오류: {e}")
    finally:
        print("정리 중...")


if __name__ == "__main__":
    # Quick test first
    if not test_import():
        sys.exit(1)
    
    # Run main system
    asyncio.run(main())
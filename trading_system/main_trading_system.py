"""
Main Trading System Orchestrator
통합 거래 시스템 오케스트레이터 - 모든 구성 요소를 통합하여 실행
"""

import asyncio
import logging
import signal
import sys
import os
from datetime import datetime
from typing import Optional

# Windows Unicode 지원을 위한 설정
if sys.platform == "win32":
    import codecs
    sys.stdout = codecs.getwriter('utf-8')(sys.stdout.detach())
    sys.stderr = codecs.getwriter('utf-8')(sys.stderr.detach())
    os.environ['PYTHONIOENCODING'] = 'utf-8'

from config.config import TradingConfig
from engine.advanced_trading_engine import AdvancedTradingEngine
from api.app import set_trading_engine, get_app


class TradingSystemOrchestrator:
    """Main Trading System Orchestrator - 완전 통합 거래 시스템"""
    
    def __init__(self, config_path: Optional[str] = None):
        # Load config from environment variables (.env file)
        self.config = TradingConfig.from_env()
        self.logger = self._setup_logging()
        self.trading_engine: Optional[AdvancedTradingEngine] = None
        self.web_server_task: Optional[asyncio.Task] = None
        self.trading_task: Optional[asyncio.Task] = None
        self.is_running = False
        
        # Setup signal handlers for graceful shutdown
        signal.signal(signal.SIGINT, self._signal_handler)
        signal.signal(signal.SIGTERM, self._signal_handler)
    
    def _setup_logging(self) -> logging.Logger:
        """Set up comprehensive logging"""
        logger = logging.getLogger("TradingSystem")
        logger.setLevel(logging.INFO)
        
        # Console handler
        console_handler = logging.StreamHandler(sys.stdout)
        console_handler.setLevel(logging.INFO)
        
        # File handler with UTF-8 encoding
        file_handler = logging.FileHandler('trading_system.log', encoding='utf-8')
        file_handler.setLevel(logging.DEBUG)
        
        # Windows Unicode 지원을 위한 추가 설정 제거 (이미 위에서 처리됨)
        
        # 이모지 제거 함수
        class EmojiFilter(logging.Filter):
            def filter(self, record):
                # 이모지 제거
                import re
                record.msg = re.sub(r'[^\u0000-\u007F\uAC00-\uD7AF\u3131-\u3163]', '', str(record.msg))
                return True
        
        # Formatter
        formatter = logging.Formatter(
            '%(asctime)s - %(name)s - %(levelname)s - %(message)s',
            datefmt='%Y-%m-%d %H:%M:%S'
        )
        
        # 이모지 필터 추가
        emoji_filter = EmojiFilter()
        console_handler.addFilter(emoji_filter)
        
        console_handler.setFormatter(formatter)
        file_handler.setFormatter(formatter)
        
        logger.addHandler(console_handler)
        logger.addHandler(file_handler)
        
        return logger
    
    def _signal_handler(self, signum, frame):
        """Handle shutdown signals"""
        self.logger.info(f"신호 {signum} 수신됨, 종료 프로세스 시작...")
        self.is_running = False
    
    async def initialize(self):
        """Initialize the complete trading system"""
        self.logger.info("="*80)
        self.logger.info("🚀 Bitget Trading System v3.0 - 완전 모듈화 버전")
        self.logger.info("="*80)
        self.logger.info(f"📅 시작 시간: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        
        try:
            # Initialize trading engine
            self.logger.info("🔧 거래 엔진 초기화 중...")
            self.trading_engine = AdvancedTradingEngine(self.config)
            await self.trading_engine.initialize()
            
            # Set up FastAPI with trading engine
            self.logger.info("🌐 웹 서버 설정 중...")
            set_trading_engine(self.trading_engine)
            
            self.logger.info("✅ 시스템 초기화 완료!")
            self.logger.info("="*80)
            
        except Exception as e:
            self.logger.critical(f"❌ 시스템 초기화 실패: {e}")
            raise
    
    async def start_web_server(self):
        """Start the FastAPI web server"""
        try:
            import uvicorn
            from api.app import get_app
            
            app = get_app()
            config = uvicorn.Config(
                app, 
                host="0.0.0.0", 
                port=8000,  # Standard dashboard port 
                log_level="info",
                access_log=False
            )
            server = uvicorn.Server(config)
            
            self.logger.info("🌐 웹 서버 시작됨 - http://localhost:8000")
            await server.serve()
            
        except ImportError:
            self.logger.warning("Uvicorn이 설치되지 않음 - 웹 서버 비활성화")
        except Exception as e:
            self.logger.error(f"웹 서버 시작 실패: {e}")
    
    async def start_trading(self):
        """Start the main trading loop"""
        self.logger.info("📈 거래 루프 시작...")
        
        while self.is_running:
            try:
                # Run one complete trading cycle
                await self.trading_engine.run_trading_cycle()
                
                # Wait before next cycle (configurable interval)
                await asyncio.sleep(self.config.TRADING_CYCLE_INTERVAL)
                
            except Exception as e:
                self.logger.error(f"거래 사이클 오류: {e}")
                await asyncio.sleep(60)  # Wait 1 minute before retry
    
    async def run(self):
        """Run the complete trading system"""
        try:
            # Initialize system
            await self.initialize()
            
            self.is_running = True
            
            # Start both web server and trading engine concurrently
            self.logger.info("🚀 모든 서비스 시작...")
            
            tasks = []
            
            # Start web server
            web_task = asyncio.create_task(self.start_web_server())
            tasks.append(web_task)
            self.logger.info("✅ 웹 서버 태스크 생성됨 - http://localhost:8000")
            
            # Start trading loop
            trading_task = asyncio.create_task(self.start_trading())
            tasks.append(trading_task)
            self.logger.info("✅ 거래 루프 태스크 생성됨")
            
            # Log startup success
            self.logger.info("🎯 모든 시스템 구성 요소 활성화됨:")
            self.logger.info("   📊 멀티 타임프레임 분석")
            self.logger.info("   🤖 머신러닝 예측 엔진")
            
            # 비용 최적화 상태 표시
            if hasattr(self.config, 'ENABLE_COST_OPTIMIZATION') and self.config.ENABLE_COST_OPTIMIZATION:
                model_name = "GPT-3.5-turbo" if not self.config.USE_GPT_4 else "GPT-4"
                interval_min = self.config.NEWS_ANALYSIS_INTERVAL // 60
                self.logger.info(f"   📰 뉴스 감성 분석 ({model_name}, {interval_min}분 간격)")
                self.logger.info("   💰 비용 최적화 모드 활성화 (월 $25 예상)")
            else:
                self.logger.info("   📰 실시간 뉴스 감성 분석")
            
            self.logger.info("   📈 시장 체제 분석")
            self.logger.info("   🔍 차트 패턴 인식")
            self.logger.info("   ⚖️ Kelly Criterion 포지션 사이징")
            self.logger.info("   🔔 실시간 알림 시스템")
            self.logger.info("   🌐 실시간 웹 대시보드")
            self.logger.info("🚀 Bitget Trading System v3.0 완전 가동 중!")
            
            # Wait for either task to complete or signal to stop
            done, pending = await asyncio.wait(
                tasks, 
                return_when=asyncio.FIRST_COMPLETED
            )
            
            # Cancel remaining tasks
            for task in pending:
                task.cancel()
                try:
                    await task
                except asyncio.CancelledError:
                    pass
            
        except KeyboardInterrupt:
            self.logger.info("키보드 인터럽트 - 종료 중...")
        except Exception as e:
            self.logger.critical(f"시스템 실행 중 오류: {e}")
        finally:
            await self.shutdown()
    
    async def shutdown(self):
        """Graceful shutdown"""
        self.logger.info("🛑 시스템 종료 중...")
        
        try:
            if self.trading_engine:
                # Send shutdown notification
                if hasattr(self.trading_engine, 'notifier'):
                    await self.trading_engine.notifier.send_notification(
                        "🛑 **거래 시스템 종료**\n\n"
                        f"종료 시간: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n"
                        "모든 포지션을 확인하고 수동으로 관리하세요.",
                        priority='high'
                    )
                
                # Stop notification system
                if hasattr(self.trading_engine, 'notifier'):
                    await self.trading_engine.notifier.shutdown()
                
                self.logger.info("✅ 거래 엔진 종료 완료")
            
            self.logger.info("✅ 시스템 완전 종료됨")
            
        except Exception as e:
            self.logger.error(f"종료 중 오류: {e}")
    
    def get_system_status(self) -> dict:
        """Get comprehensive system status"""
        if not self.trading_engine:
            return {
                'status': 'not_initialized',
                'message': '시스템이 초기화되지 않았습니다'
            }
        
        try:
            return self.trading_engine.get_system_status()
        except Exception as e:
            return {
                'status': 'error',
                'message': f'상태 조회 오류: {str(e)}'
            }


async def main():
    """Main entry point"""
    print("Bitget Trading System v3.0 시작 중...")
    
    # Create and run the trading system
    system = TradingSystemOrchestrator()
    
    try:
        await system.run()
    except KeyboardInterrupt:
        print("\n👋 사용자 중단으로 시스템 종료")
    except Exception as e:
        print(f"❌ 시스템 오류: {e}")
    finally:
        print("🛑 시스템 종료 완료")


if __name__ == "__main__":
    # Run the trading system
    asyncio.run(main())
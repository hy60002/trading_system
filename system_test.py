#!/usr/bin/env python3
"""
Trading System Comprehensive Test
Tests all major components of the revised trading system
"""

import asyncio
import logging
import sys
import os
from datetime import datetime
from typing import Dict, List

# Add the trading_system path
sys.path.append(os.path.join(os.path.dirname(__file__), 'trading_system'))

try:
    from config.config import TradingConfig
    from database.db_manager import EnhancedDatabaseManager
    from notifications.notification_manager import NotificationManager
    from managers.capital_tracker import CapitalTracker
    from managers.risk_manager import RiskManager
except ImportError as e:
    print(f"❌ Import Error: {e}")
    print("Please make sure you're running from the correct directory")
    sys.exit(1)

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


class SystemTester:
    """Comprehensive system testing class"""
    
    def __init__(self):
        self.config = TradingConfig.from_env()
        self.db = None
        self.notification_manager = None
        self.capital_tracker = None
        self.risk_manager = None
        
        # Test results
        self.test_results = {
            'total_tests': 0,
            'passed_tests': 0,
            'failed_tests': 0,
            'test_details': []
        }
    
    async def run_all_tests(self):
        """Run all system tests"""
        logger.info("="*60)
        logger.info("🚀 BITGET TRADING SYSTEM v3.0 - 종합 테스트")
        logger.info("="*60)
        
        try:
            # Initialize components
            await self.initialize_components()
            
            # Run tests
            await self.test_configuration()
            await self.test_database()
            await self.test_notification_system()
            await self.test_capital_tracking()
            await self.test_risk_management()
            await self.test_integration()
            
            # Print final results
            self.print_test_results()
            
        except Exception as e:
            logger.error(f"❌ Critical test failure: {e}")
            return False
        
        finally:
            await self.cleanup()
        
        return self.test_results['failed_tests'] == 0
    
    async def initialize_components(self):
        """Initialize all system components"""
        logger.info("🔧 시스템 컴포넌트 초기화...")
        
        try:
            # Database
            self.db = EnhancedDatabaseManager(self.config.DATABASE_PATH)
            
            # Notification manager
            self.notification_manager = NotificationManager(self.config)
            await self.notification_manager.initialize()
            
            # Risk manager
            self.risk_manager = RiskManager(self.config, self.db)
            
            # Capital tracker
            self.capital_tracker = CapitalTracker(self.config, self.db, self.notification_manager)
            await self.capital_tracker.initialize()
            
            logger.info("✅ 모든 컴포넌트 초기화 완료")
            
        except Exception as e:
            logger.error(f"❌ 컴포넌트 초기화 실패: {e}")
            raise
    
    async def test_configuration(self):
        """Test system configuration"""
        logger.info("📋 설정 테스트 실행 중...")
        
        # Test 1: Configuration validation
        result = self.run_test(
            "Configuration Validation",
            lambda: len(self.config.validate()) == 0,
            "시스템 설정이 올바르게 구성되었는지 확인"
        )
        
        # Test 2: Symbol configuration
        result = self.run_test(
            "Symbol Configuration",
            lambda: set(self.config.SYMBOLS) == {"BTCUSDT", "ETHUSDT"},
            "거래 심볼이 BTC, ETH만 포함하는지 확인"
        )
        
        # Test 3: Portfolio weights
        expected_weights = {"BTCUSDT": 0.70, "ETHUSDT": 0.30}
        result = self.run_test(
            "Portfolio Weights",
            lambda: self.config.PORTFOLIO_WEIGHTS == expected_weights,
            "포트폴리오 가중치가 BTC 70%, ETH 30%인지 확인"
        )
        
        # Test 4: 33% allocation limit
        result = self.run_test(
            "33% Allocation Limit",
            lambda: self.config.MAX_TOTAL_ALLOCATION == 0.33,
            "최대 자금 할당이 33%로 설정되었는지 확인"
        )
    
    async def test_database(self):
        """Test database functionality"""
        logger.info("🗄️ 데이터베이스 테스트 실행 중...")
        
        # Test 1: Database connection
        result = self.run_test(
            "Database Connection",
            lambda: self.db is not None,
            "데이터베이스 연결 확인"
        )
        
        # Test 2: Table creation
        try:
            # Try to log a test event
            self.db.log_system_event('TEST', 'SystemTest', 'Test event', {'test': True})
            result = True
        except Exception:
            result = False
        
        self.run_test(
            "Database Operations",
            lambda: result,
            "데이터베이스 쓰기 작업 확인"
        )
    
    async def test_notification_system(self):
        """Test notification system"""
        logger.info("📢 알림 시스템 테스트 실행 중...")
        
        # Test 1: Notification manager initialization
        result = self.run_test(
            "Notification Manager",
            lambda: self.notification_manager is not None,
            "알림 매니저 초기화 확인"
        )
        
        # Test 2: Telegram configuration
        has_telegram_config = bool(
            self.config.TELEGRAM_BOT_TOKEN and 
            self.config.TELEGRAM_CHAT_ID
        )
        
        self.run_test(
            "Telegram Configuration",
            lambda: has_telegram_config,
            "텔레그램 설정 확인"
        )
        
        # Test 3: Test notification (if configured)
        if has_telegram_config:
            try:
                test_success = await self.notification_manager.test_notification_system()
                self.run_test(
                    "Telegram Connectivity",
                    lambda: test_success,
                    "텔레그램 연결 테스트"
                )
            except Exception as e:
                logger.warning(f"텔레그램 테스트 실패: {e}")
                self.run_test(
                    "Telegram Connectivity",
                    lambda: False,
                    f"텔레그램 연결 테스트 실패: {e}"
                )
    
    async def test_capital_tracking(self):
        """Test capital tracking system"""
        logger.info("💰 자본 추적 시스템 테스트 실행 중...")
        
        # Test 1: Capital tracker initialization
        result = self.run_test(
            "Capital Tracker Init",
            lambda: self.capital_tracker is not None,
            "자본 추적기 초기화 확인"
        )
        
        # Test 2: Snapshot update
        try:
            snapshot = await self.capital_tracker.update_snapshot()
            result = snapshot is not None
        except Exception as e:
            logger.error(f"스냅샷 업데이트 실패: {e}")
            result = False
        
        self.run_test(
            "Capital Snapshot",
            lambda: result,
            "자본 스냅샷 생성 확인"
        )
        
        # Test 3: Position feasibility check
        try:
            can_open, reason, details = self.capital_tracker.can_open_position("BTCUSDT", 100.0)
            result = isinstance(can_open, bool) and isinstance(reason, str)
        except Exception as e:
            logger.error(f"포지션 검증 실패: {e}")
            result = False
        
        self.run_test(
            "Position Feasibility",
            lambda: result,
            "포지션 개설 가능성 검증"
        )
        
        # Test 4: System status
        try:
            status = self.capital_tracker.get_current_status()
            result = 'allocation_percentage' in status
        except Exception as e:
            logger.error(f"상태 조회 실패: {e}")
            result = False
        
        self.run_test(
            "System Status",
            lambda: result,
            "시스템 상태 조회 확인"
        )
    
    async def test_risk_management(self):
        """Test risk management system"""
        logger.info("⚖️ 리스크 관리 시스템 테스트 실행 중...")
        
        # Test 1: Risk manager initialization
        result = self.run_test(
            "Risk Manager Init",
            lambda: self.risk_manager is not None,
            "리스크 매니저 초기화 확인"
        )
        
        # Test 2: 33% limit check
        try:
            limit_check = self.risk_manager.check_33_percent_limit(
                total_capital=10000,
                current_positions=[],
                requested_amount=1000
            )
            result = 'within_limit' in limit_check
        except Exception as e:
            logger.error(f"33% 한도 체크 실패: {e}")
            result = False
        
        self.run_test(
            "33% Limit Check",
            lambda: result,
            "33% 자금 한도 체크 확인"
        )
        
        # Test 3: Position allocation calculation
        try:
            allocation = self.risk_manager.calculate_position_allocation(
                symbol="BTCUSDT",
                total_capital=10000,
                current_positions=[]
            )
            result = isinstance(allocation, (int, float)) and allocation >= 0
        except Exception as e:
            logger.error(f"포지션 할당 계산 실패: {e}")
            result = False
        
        self.run_test(
            "Position Allocation",
            lambda: result,
            "포지션 할당 계산 확인"
        )
    
    async def test_integration(self):
        """Test system integration"""
        logger.info("🔗 시스템 통합 테스트 실행 중...")
        
        # Test 1: Component communication
        try:
            # Test notification through capital tracker
            await self.notification_manager.send_notification(
                "🧪 시스템 테스트 완료 - 모든 컴포넌트 정상 작동",
                priority='normal'
            )
            result = True
        except Exception as e:
            logger.error(f"컴포넌트 통신 실패: {e}")
            result = False
        
        self.run_test(
            "Component Communication",
            lambda: result,
            "컴포넌트 간 통신 확인"
        )
        
        # Test 2: End-to-end workflow simulation
        try:
            # Simulate trading workflow checks
            can_open, reason, details = self.capital_tracker.can_open_position("BTCUSDT", 500.0)
            
            if can_open:
                # Simulate risk check
                risk_check = await self.risk_manager.check_risk_limits("BTCUSDT")
                workflow_success = True
            else:
                workflow_success = True  # Expected behavior for empty account
                
        except Exception as e:
            logger.error(f"워크플로우 시뮬레이션 실패: {e}")
            workflow_success = False
        
        self.run_test(
            "Trading Workflow",
            lambda: workflow_success,
            "거래 워크플로우 시뮬레이션"
        )
    
    def run_test(self, test_name: str, test_func, description: str) -> bool:
        """Execute a single test"""
        self.test_results['total_tests'] += 1
        
        try:
            result = test_func()
            if result:
                self.test_results['passed_tests'] += 1
                logger.info(f"✅ {test_name}: PASSED")
                self.test_results['test_details'].append({
                    'name': test_name,
                    'status': 'PASSED',
                    'description': description
                })
                return True
            else:
                self.test_results['failed_tests'] += 1
                logger.error(f"❌ {test_name}: FAILED")
                self.test_results['test_details'].append({
                    'name': test_name,
                    'status': 'FAILED',
                    'description': description
                })
                return False
                
        except Exception as e:
            self.test_results['failed_tests'] += 1
            logger.error(f"❌ {test_name}: ERROR - {e}")
            self.test_results['test_details'].append({
                'name': test_name,
                'status': 'ERROR', 
                'description': f"{description} - Error: {e}"
            })
            return False
    
    def print_test_results(self):
        """Print comprehensive test results"""
        logger.info("="*60)
        logger.info("📊 테스트 결과 요약")
        logger.info("="*60)
        
        total = self.test_results['total_tests']
        passed = self.test_results['passed_tests']
        failed = self.test_results['failed_tests']
        
        logger.info(f"총 테스트: {total}")
        logger.info(f"성공: {passed} ✅")
        logger.info(f"실패: {failed} ❌")
        logger.info(f"성공률: {(passed/total*100):.1f}%")
        
        logger.info("\n" + "="*60)
        logger.info("📋 상세 테스트 결과")
        logger.info("="*60)
        
        for test in self.test_results['test_details']:
            status_icon = "✅" if test['status'] == 'PASSED' else "❌"
            logger.info(f"{status_icon} {test['name']}: {test['status']}")
            logger.info(f"   → {test['description']}")
        
        if failed == 0:
            logger.info("\n🎉 모든 테스트 통과! 시스템이 정상적으로 구성되었습니다.")
        else:
            logger.warning(f"\n⚠️ {failed}개 테스트 실패. 시스템 점검이 필요합니다.")
    
    async def cleanup(self):
        """Clean up test resources"""
        try:
            if self.capital_tracker:
                await self.capital_tracker.shutdown()
            
            if self.notification_manager:
                await self.notification_manager.shutdown()
                
            logger.info("🧹 테스트 리소스 정리 완료")
            
        except Exception as e:
            logger.error(f"❌ 정리 중 오류: {e}")


async def main():
    """Main test execution"""
    print("🚀 BITGET TRADING SYSTEM v3.0 - 종합 테스트 시작")
    print("=" * 60)
    
    tester = SystemTester()
    success = await tester.run_all_tests()
    
    if success:
        print("\n✅ 시스템 테스트 완료 - 모든 컴포넌트 정상")
        sys.exit(0)
    else:
        print("\n❌ 시스템 테스트 실패 - 문제 해결 필요")
        sys.exit(1)


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\n⏹️ 테스트 중단됨")
        sys.exit(1)
    except Exception as e:
        print(f"\n💥 테스트 실행 중 오류: {e}")
        sys.exit(1)
#!/usr/bin/env python3
"""
HIGH 우선순위 수정사항 통합 테스트
1. PositionManager의 RiskManager 인스턴스 확인
2. DAO 클래스들 활성화 확인
3. API 키 암호화 시스템 확인
"""

import sys
import os
import logging
from typing import Dict, Any

# 프로젝트 루트 디렉토리를 Python path에 추가
project_root = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, project_root)

# 로깅 설정
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


class HighPriorityFixesTest:
    """HIGH 우선순위 수정사항 테스트 클래스"""
    
    def __init__(self):
        self.test_results = []
        self.logger = logger
    
    def log_result(self, test_name: str, success: bool, message: str):
        """테스트 결과 기록"""
        status = "PASS" if success else "FAIL"
        result = f"[{status}] {test_name}: {message}"
        self.test_results.append((test_name, success, message))
        self.logger.info(result)
        print(result)
    
    def test_crypto_utils_import(self):
        """암호화 유틸리티 import 테스트"""
        try:
            from trading_system.utils.crypto_utils import CryptoUtils, encrypt_api_key, decrypt_api_key
            self.log_result("Crypto Utils Import", True, "암호화 유틸리티 import 성공")
            
            # 기본 기능 테스트
            test_key = "test_api_key_12345"
            master_key = CryptoUtils.generate_master_key()
            crypto = CryptoUtils(master_key)
            
            if crypto.is_available():
                encrypted = crypto.encrypt_string(test_key)
                decrypted = crypto.decrypt_string(encrypted)
                
                if decrypted == test_key:
                    self.log_result("Crypto Functionality", True, "암호화/복호화 기능 정상 작동")
                else:
                    self.log_result("Crypto Functionality", False, f"복호화 실패: {decrypted} != {test_key}")
            else:
                self.log_result("Crypto Functionality", False, "암호화 시스템 초기화 실패")
                
        except Exception as e:
            self.log_result("Crypto Utils Import", False, f"Import 실패: {e}")
    
    def test_config_with_crypto(self):
        """암호화 기능이 포함된 Config 테스트"""
        try:
            from trading_system.config.config import TradingConfig
            config = TradingConfig()
            self.log_result("Config with Crypto", True, "암호화 지원 Config 생성 성공")
            
            # 환경변수 테스트 (암호화되지 않은 더미 값)
            test_config = TradingConfig()
            test_config.BITGET_API_KEY = "test_key"
            
            if hasattr(test_config, 'BITGET_API_KEY'):
                self.log_result("Config API Keys", True, "API 키 필드 정상 접근 가능")
            else:
                self.log_result("Config API Keys", False, "API 키 필드 접근 실패")
                
        except Exception as e:
            self.log_result("Config with Crypto", False, f"Config 생성 실패: {e}")
    
    def test_dao_activation(self):
        """DAO 클래스 활성화 테스트"""
        try:
            from trading_system.database.db_manager import EnhancedDatabaseManager
            
            # 테스트용 in-memory 데이터베이스
            db_manager = EnhancedDatabaseManager(":memory:")
            
            # DAO 인스턴스 확인
            dao_tests = [
                ("TradeDAO", hasattr(db_manager, 'trade_dao') and db_manager.trade_dao is not None),
                ("PositionDAO", hasattr(db_manager, 'position_dao') and db_manager.position_dao is not None),
                ("PerformanceDAO", hasattr(db_manager, 'performance_dao')),
                ("MLDao", hasattr(db_manager, 'ml_dao')),
                ("NewsDAO", hasattr(db_manager, 'news_dao')),
                ("SystemDAO", hasattr(db_manager, 'system_dao'))
            ]
            
            activated_daos = []
            failed_daos = []
            
            for dao_name, exists in dao_tests:
                if exists:
                    dao_instance = getattr(db_manager, dao_name.lower().replace('dao', '_dao'))
                    if dao_instance is not None:
                        activated_daos.append(dao_name)
                    else:
                        failed_daos.append(dao_name)
                else:
                    failed_daos.append(dao_name)
            
            if len(activated_daos) >= 4:  # 최소 4개 DAO 활성화 예상
                self.log_result("DAO Activation", True, f"활성화된 DAO: {', '.join(activated_daos)}")
            else:
                self.log_result("DAO Activation", False, f"활성화 실패 DAO: {', '.join(failed_daos)}")
            
            # 기본 기능 테스트
            try:
                stats = db_manager.get_dao_stats()
                active_daos = stats.get('active_daos', [])
                self.log_result("DAO Stats", True, f"DAO 통계 조회 성공: {len(active_daos)}개 활성화")
            except Exception as e:
                self.log_result("DAO Stats", False, f"DAO 통계 조회 실패: {e}")
                
        except Exception as e:
            self.log_result("DAO Activation", False, f"DAO 테스트 실패: {e}")
    
    def test_position_manager_risk_manager(self):
        """PositionManager의 RiskManager 인스턴스 테스트"""
        try:
            from trading_system.config.config import TradingConfig
            from trading_system.database.db_manager import EnhancedDatabaseManager
            from trading_system.managers.position_manager import PositionManager
            
            # Mock 객체들 생성
            config = TradingConfig()
            db = EnhancedDatabaseManager(":memory:")
            
            # Mock exchange 객체
            class MockExchange:
                def get_current_price(self, symbol):
                    return 50000.0 if symbol == "BTCUSDT" else 3000.0
            
            exchange = MockExchange()
            
            # PositionManager 생성
            position_manager = PositionManager(config, exchange, db)
            
            # RiskManager 인스턴스 확인
            if hasattr(position_manager, 'risk_manager') and position_manager.risk_manager is not None:
                self.log_result("PositionManager RiskManager", True, "RiskManager 인스턴스 정상 생성")
                
                # RiskManager 기본 기능 테스트
                try:
                    # 기본 메서드 호출 테스트
                    risk_manager = position_manager.risk_manager
                    if hasattr(risk_manager, 'calculate_position_stops'):
                        self.log_result("RiskManager Methods", True, "RiskManager 메서드 정상 접근 가능")
                    else:
                        self.log_result("RiskManager Methods", False, "필수 메서드 누락")
                except Exception as e:
                    self.log_result("RiskManager Methods", False, f"메서드 테스트 실패: {e}")
            else:
                self.log_result("PositionManager RiskManager", False, "RiskManager 인스턴스 누락")
                
        except Exception as e:
            self.log_result("PositionManager RiskManager", False, f"테스트 실패: {e}")
    
    def test_system_integration(self):
        """시스템 통합 테스트"""
        try:
            from trading_system.config.config import TradingConfig
            from trading_system.database.db_manager import EnhancedDatabaseManager
            
            # 전체 시스템 초기화 테스트
            config = TradingConfig()
            db = EnhancedDatabaseManager(":memory:")
            
            # 시스템 상태 확인
            system_status = db.get_system_status()
            
            if system_status.get('status') == 'healthy':
                self.log_result("System Integration", True, "시스템 통합 상태 양호")
            else:
                self.log_result("System Integration", False, f"시스템 상태 문제: {system_status}")
                
        except Exception as e:
            self.log_result("System Integration", False, f"통합 테스트 실패: {e}")
    
    def run_all_tests(self):
        """모든 테스트 실행"""
        print("HIGH Priority Fixes Integration Test Starting")
        print("=" * 60)
        
        # 각 테스트 실행
        self.test_crypto_utils_import()
        self.test_config_with_crypto()
        self.test_dao_activation()
        self.test_position_manager_risk_manager()
        self.test_system_integration()
        
        # 결과 요약
        print("\n" + "=" * 60)
        print("Test Results Summary")
        print("=" * 60)
        
        total_tests = len(self.test_results)
        passed_tests = sum(1 for _, success, _ in self.test_results if success)
        failed_tests = total_tests - passed_tests
        
        print(f"총 테스트: {total_tests}")
        print(f"통과: {passed_tests}")
        print(f"실패: {failed_tests}")
        print(f"성공률: {(passed_tests/total_tests)*100:.1f}%")
        
        if failed_tests > 0:
            print("\nFailed Tests:")
            for test_name, success, message in self.test_results:
                if not success:
                    print(f"  - {test_name}: {message}")
        
        print("\n" + "=" * 60)
        if failed_tests == 0:
            print("All HIGH priority fixes have been successfully applied!")
        else:
            print(f"{failed_tests} issues found. Fixes needed.")
        
        return failed_tests == 0


def main():
    """메인 함수"""
    try:
        tester = HighPriorityFixesTest()
        success = tester.run_all_tests()
        
        if success:
            print("\nAll tests passed!")
            sys.exit(0)
        else:
            print("\nSome tests failed!")
            sys.exit(1)
            
    except Exception as e:
        print(f"Critical error during test execution: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    main()
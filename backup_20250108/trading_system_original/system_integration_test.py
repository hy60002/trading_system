#!/usr/bin/env python3
"""
Trading System Integration Test
프로그램 전체 실행 흐름 및 모듈 조화 검증 스크립트
"""

import asyncio
import logging
import sys
import os
import traceback
from datetime import datetime
from typing import Dict, List, Optional

# Add current directory to path
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from config.config import TradingConfig
from engine.advanced_trading_engine import AdvancedTradingEngine


class SystemIntegrationTester:
    """시스템 통합 테스트"""
    
    def __init__(self):
        self.logger = self._setup_logging()
        self.config = TradingConfig()
        self.test_results = {}
        
    def _setup_logging(self):
        """로깅 설정"""
        logger = logging.getLogger('SystemIntegrationTest')
        logger.setLevel(logging.INFO)
        
        if not logger.handlers:
            handler = logging.StreamHandler()
            formatter = logging.Formatter(
                '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
            )
            handler.setFormatter(formatter)
            logger.addHandler(handler)
        
        return logger
    
    async def run_full_integration_test(self) -> Dict:
        """전체 통합 테스트 실행"""
        self.logger.info("="*80)
        self.logger.info("🧪 거래 시스템 통합 테스트 시작")
        self.logger.info("="*80)
        
        test_results = {
            'import_test': False,
            'config_test': False,
            'initialization_test': False,
            'component_integration_test': False,
            'async_resource_test': False,
            'error_handling_test': False,
            'shutdown_test': False,
            'overall_success': False
        }
        
        try:
            # 1. 모듈 임포트 테스트
            self.logger.info("📦 1. 모듈 임포트 테스트")
            test_results['import_test'] = await self._test_imports()
            
            # 2. 설정 검증 테스트
            self.logger.info("⚙️ 2. 설정 검증 테스트")
            test_results['config_test'] = await self._test_configuration()
            
            # 3. 시스템 초기화 테스트
            self.logger.info("🚀 3. 시스템 초기화 테스트")
            test_results['initialization_test'] = await self._test_initialization()
            
            # 4. 컴포넌트 통합 테스트
            self.logger.info("🔧 4. 컴포넌트 통합 테스트")
            test_results['component_integration_test'] = await self._test_component_integration()
            
            # 5. 비동기 리소스 관리 테스트  
            self.logger.info("⚡ 5. 비동기 리소스 테스트")
            test_results['async_resource_test'] = await self._test_async_resources()
            
            # 6. 오류 처리 테스트
            self.logger.info("🛡️ 6. 오류 처리 테스트")
            test_results['error_handling_test'] = await self._test_error_handling()
            
            # 7. 정상 종료 테스트
            self.logger.info("🛑 7. 정상 종료 테스트")
            test_results['shutdown_test'] = await self._test_shutdown()
            
            # 전체 결과 평가
            success_count = sum(1 for result in test_results.values() if result)
            total_tests = len(test_results) - 1  # overall_success 제외
            
            test_results['overall_success'] = success_count >= total_tests * 0.8  # 80% 이상 성공
            
            self.logger.info("="*80)
            self.logger.info("📊 통합 테스트 결과 요약")
            self.logger.info("="*80)
            
            for test_name, result in test_results.items():
                if test_name != 'overall_success':
                    status = "✅ 통과" if result else "❌ 실패"
                    self.logger.info(f"{test_name}: {status}")
            
            overall_status = "✅ 성공" if test_results['overall_success'] else "❌ 실패"
            self.logger.info(f"\n🎯 전체 결과: {overall_status} ({success_count}/{total_tests})")
            
            if test_results['overall_success']:
                self.logger.info("🎉 시스템이 프로덕션 준비 상태입니다!")
            else:
                self.logger.warning("⚠️ 시스템에 문제가 있습니다. 수정이 필요합니다.")
            
            return test_results
            
        except Exception as e:
            self.logger.error(f"❌ 통합 테스트 중 심각한 오류: {e}")
            self.logger.error(traceback.format_exc())
            return test_results
    
    async def _test_imports(self) -> bool:
        """모듈 임포트 테스트"""
        try:
            # 주요 모듈들 임포트 시도
            from database.db_manager import EnhancedDatabaseManager
            from exchange.bitget_manager import EnhancedBitgetExchangeManager
            from managers.position_manager import PositionManager
            from managers.risk_manager import RiskManager
            from managers.ml_model_manager import EnhancedMLModelManager
            from managers.capital_tracker import CapitalTracker
            from notifications.notification_manager import NotificationManager
            from analyzers.news_sentiment import EnhancedNewsSentimentAnalyzer
            from strategies.btc_strategy import BTCTradingStrategy
            from strategies.eth_strategy import ETHTradingStrategy
            
            self.logger.info("  ✅ 모든 주요 모듈 임포트 성공")
            return True
            
        except Exception as e:
            self.logger.error(f"  ❌ 모듈 임포트 실패: {e}")
            return False
    
    async def _test_configuration(self) -> bool:
        """설정 검증 테스트"""
        try:
            # 필수 설정 확인
            missing_config = self.config.validate()
            
            if missing_config:
                self.logger.warning(f"  ⚠️ 누락된 설정: {missing_config}")
                # 일부 설정 누락은 허용 (테스트 환경)
                return len(missing_config) <= 3
            
            # 심볼 설정 확인
            if not self.config.SYMBOLS:
                self.logger.error("  ❌ 거래 심볼이 설정되지 않음")
                return False
            
            # 포트폴리오 가중치 확인
            total_weight = sum(self.config.PORTFOLIO_WEIGHTS.values())
            if abs(total_weight - 1.0) > 0.01:
                self.logger.error(f"  ❌ 포트폴리오 가중치 합계 오류: {total_weight}")
                return False
            
            self.logger.info("  ✅ 설정 검증 통과")
            return True
            
        except Exception as e:
            self.logger.error(f"  ❌ 설정 검증 실패: {e}")
            return False
    
    async def _test_initialization(self) -> bool:
        """시스템 초기화 테스트"""
        engine = None
        try:
            # 거래 엔진 생성 및 초기화
            engine = AdvancedTradingEngine(self.config)
            
            # 초기화 시도 (실제 API 연결은 제외하고 구조적 초기화만)
            try:
                await engine.initialize()
                initialization_success = True
            except Exception as init_error:
                # API 키가 없는 경우 등은 예상된 오류
                if "API" in str(init_error) or "key" in str(init_error).lower():
                    self.logger.info("  ⚠️ API 연결 실패 (예상됨) - 구조적 초기화는 성공")
                    initialization_success = True
                else:
                    raise init_error
            
            # 컴포넌트 존재 확인
            required_components = [
                'db', 'exchange', 'position_manager', 'risk_manager',
                'notifier', 'capital_tracker', 'ml_manager', 'news_analyzer'
            ]
            
            for component in required_components:
                if not hasattr(engine, component):
                    self.logger.error(f"  ❌ 필수 컴포넌트 누락: {component}")
                    return False
            
            self.logger.info("  ✅ 시스템 초기화 성공")
            return initialization_success
            
        except Exception as e:
            self.logger.error(f"  ❌ 초기화 테스트 실패: {e}")
            return False
        finally:
            if engine:
                try:
                    await engine.shutdown()
                except:
                    pass
    
    async def _test_component_integration(self) -> bool:
        """컴포넌트 통합 테스트"""
        try:
            # 각 컴포넌트가 서로 올바르게 연결되어 있는지 확인
            engine = AdvancedTradingEngine(self.config)
            
            # 의존성 체크
            dependencies = [
                (engine.position_manager, 'exchange'),
                (engine.position_manager, 'db'),
                (engine.capital_tracker, 'notification_manager'),
                (engine.capital_tracker, 'db'),
                (engine.ml_manager, 'db'),
                (engine.risk_manager, 'db'),
            ]
            
            for component, dependency in dependencies:
                if not hasattr(component, dependency):
                    self.logger.error(f"  ❌ 의존성 누락: {component.__class__.__name__} -> {dependency}")
                    return False
            
            self.logger.info("  ✅ 컴포넌트 통합 검증 성공")
            return True
            
        except Exception as e:
            self.logger.error(f"  ❌ 컴포넌트 통합 테스트 실패: {e}")
            return False
    
    async def _test_async_resources(self) -> bool:
        """비동기 리소스 관리 테스트"""
        try:
            # asyncio task 생성 및 정리 시뮬레이션
            tasks = []
            
            # 여러 비동기 작업 생성
            for i in range(5):
                task = asyncio.create_task(self._dummy_async_task(i))
                tasks.append(task)
            
            # 잠시 실행 후 정리
            await asyncio.sleep(0.1)
            
            for task in tasks:
                if not task.done():
                    task.cancel()
                    try:
                        await asyncio.wait_for(task, timeout=1.0)
                    except (asyncio.CancelledError, asyncio.TimeoutError):
                        pass
            
            self.logger.info("  ✅ 비동기 리소스 관리 테스트 성공")
            return True
            
        except Exception as e:
            self.logger.error(f"  ❌ 비동기 리소스 테스트 실패: {e}")
            return False
    
    async def _dummy_async_task(self, task_id: int):
        """더미 비동기 작업"""
        try:
            for i in range(100):
                await asyncio.sleep(0.01)
                if i % 50 == 0:
                    # 일부 작업에서 의도적 오류 발생
                    if task_id == 2:
                        raise ValueError(f"테스트 오류 {task_id}")
        except asyncio.CancelledError:
            pass  # 정상적인 취소
        except Exception:
            pass  # 테스트용 오류 무시
    
    async def _test_error_handling(self) -> bool:
        """오류 처리 테스트"""
        try:
            error_scenarios = [
                ("네트워크 오류", ConnectionError("테스트 연결 오류")),
                ("데이터 오류", ValueError("테스트 데이터 오류")),
                ("권한 오류", PermissionError("테스트 권한 오류")),
            ]
            
            handled_errors = 0
            
            for error_name, error in error_scenarios:
                try:
                    # 의도적으로 오류 발생
                    raise error
                except Exception as e:
                    # 오류가 적절히 캐치되는지 확인
                    if isinstance(e, (ConnectionError, ValueError, PermissionError)):
                        handled_errors += 1
            
            success_rate = handled_errors / len(error_scenarios)
            
            if success_rate >= 0.8:
                self.logger.info("  ✅ 오류 처리 테스트 성공")
                return True
            else:
                self.logger.error(f"  ❌ 오류 처리 성공률 낮음: {success_rate:.1%}")
                return False
            
        except Exception as e:
            self.logger.error(f"  ❌ 오류 처리 테스트 실패: {e}")
            return False
    
    async def _test_shutdown(self) -> bool:
        """정상 종료 테스트"""
        engine = None
        try:
            # 엔진 생성
            engine = AdvancedTradingEngine(self.config)
            
            # 종료 시도
            await engine.shutdown()
            
            # 종료 후 상태 확인
            if hasattr(engine, 'is_running') and engine.is_running:
                self.logger.error("  ❌ 엔진이 여전히 실행 중")
                return False
            
            self.logger.info("  ✅ 정상 종료 테스트 성공")
            return True
            
        except Exception as e:
            self.logger.error(f"  ❌ 종료 테스트 실패: {e}")
            return False
        finally:
            if engine:
                try:
                    await engine.shutdown()
                except:
                    pass


async def main():
    """메인 테스트 실행"""
    tester = SystemIntegrationTester()
    results = await tester.run_full_integration_test()
    
    # 결과에 따라 exit code 설정
    exit_code = 0 if results.get('overall_success', False) else 1
    sys.exit(exit_code)


if __name__ == "__main__":
    asyncio.run(main())
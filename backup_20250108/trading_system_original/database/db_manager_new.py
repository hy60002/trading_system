"""
Enhanced Database Manager - DAO Pattern Implementation
DAO 패턴을 적용한 데이터베이스 매니저
"""

import logging
from typing import Dict, List, Optional, Any
from datetime import datetime

# DAO 모듈들 import
from .dao.trade_dao import TradeDAO
from .dao.position_dao import PositionDAO
# from .dao.performance_dao import PerformanceDAO
# from .dao.ml_dao import MLDao
# from .dao.news_dao import NewsDAO
# from .dao.system_dao import SystemDAO


class EnhancedDatabaseManager:
    """
    DAO 패턴을 적용한 향상된 데이터베이스 매니저
    
    기존 811줄의 거대한 단일 클래스를 다음과 같이 분리:
    - TradeDAO: 거래 관련 데이터 접근
    - PositionDAO: 포지션 관련 데이터 접근  
    - PerformanceDAO: 성과 관련 데이터 접근
    - MLDao: 머신러닝 모델 관련 데이터 접근
    - NewsDAO: 뉴스 관련 데이터 접근
    - SystemDAO: 시스템 로그 관련 데이터 접근
    """
    
    def __init__(self, db_path: str):
        self.db_path = db_path
        self.logger = logging.getLogger(__name__)
        
        # DAO 인스턴스들 초기화
        self.trade_dao = TradeDAO(db_path)
        self.position_dao = PositionDAO(db_path)
        # self.performance_dao = PerformanceDAO(db_path) # TODO: 다음 단계에서 구현
        # self.ml_dao = MLDao(db_path) # TODO: 다음 단계에서 구현
        # self.news_dao = NewsDAO(db_path) # TODO: 다음 단계에서 구현
        # self.system_dao = SystemDAO(db_path) # TODO: 다음 단계에서 구현
        
        # 임시로 레거시 매니저 참조 (호환성을 위해)
        from .db_manager_legacy import DatabaseManager
        self._legacy_manager = None
        try:
            self._legacy_manager = DatabaseManager(db_path)
        except Exception as e:
            self.logger.warning(f"레거시 매니저 초기화 실패: {e}")
        
        self.logger.info("✅ DAO 패턴 데이터베이스 매니저 초기화 완료")
    
    async def initialize(self):
        """데이터베이스 초기화 (비동기 호환성)"""
        self.logger.info("데이터베이스 초기화 완료")
        return True
    
    # =============================================================================
    # 거래 관련 메서드들 (TradeDAO로 위임)
    # =============================================================================
    
    def add_trade(self, symbol: str, side: str, price: float, amount: float, **kwargs) -> int:
        """거래 기록 추가"""
        trade_data = {
            'symbol': symbol,
            'side': side,
            'price': price, 
            'amount': amount,
            **kwargs
        }
        return self.trade_dao.add_trade(trade_data)
    
    def get_trades(self, symbol: str = None, limit: int = 100) -> List[Dict[str, Any]]:
        """거래 내역 조회"""
        if symbol:
            return self.trade_dao.get_trades_by_symbol(symbol, limit)
        else:
            # 전체 거래 조회는 TradeDAO에 추가 메서드 필요
            return []
    
    def get_symbol_trades_today(self, symbol: str) -> Dict[str, Any]:
        """심볼별 오늘 거래 통계 (중복 제거됨)"""
        return self.trade_dao.get_symbol_trades_today(symbol)
    
    def add_trade_to_history(self, **kwargs) -> int:
        """거래 히스토리 추가"""
        return self.trade_dao.add_trade_history(kwargs)
    
    def get_trade_history(self, symbol: str = None, days: int = 30) -> List[Dict[str, Any]]:
        """거래 히스토리 조회"""
        return self.trade_dao.get_trade_history(symbol, days)
    
    def get_trade_statistics(self, symbol: str = None, days: int = 30) -> Dict[str, Any]:
        """거래 통계 조회"""
        return self.trade_dao.get_trade_statistics(symbol, days)
    
    # =============================================================================
    # 포지션 관련 메서드들 (PositionDAO로 위임)
    # =============================================================================
    
    def add_position(self, **kwargs) -> int:
        """포지션 추가"""
        return self.position_dao.add_position(kwargs)
    
    def get_active_positions(self, symbol: str = None) -> List[Dict[str, Any]]:
        """활성 포지션 조회"""
        return self.position_dao.get_active_positions(symbol)
    
    def update_position(self, position_id: int, **update_data) -> bool:
        """포지션 업데이트"""
        return self.position_dao.update_position(position_id, update_data)
    
    def close_position(self, position_id: int, exit_price: float, exit_reason: str = 'manual') -> bool:
        """포지션 종료"""
        return self.position_dao.close_position(position_id, exit_price, exit_reason)
    
    def get_position_summary(self, symbol: str = None) -> Dict[str, Any]:
        """포지션 요약 정보"""
        return self.position_dao.get_position_summary(symbol)
    
    def save_balance(self, **balance_data) -> int:
        """잔액 기록 저장"""
        return self.position_dao.add_balance_record(balance_data)
    
    def get_latest_balance(self) -> Optional[Dict[str, Any]]:
        """최신 잔액 조회"""
        return self.position_dao.get_latest_balance()
    
    # =============================================================================
    # 임시 호환성 메서드들 (점진적 마이그레이션을 위해)
    # =============================================================================
    
    def log_system_event(self, level: str, component: str, message: str, details: Dict = None):
        """시스템 이벤트 로깅 (임시 구현)"""
        try:
            self.logger.info(f"[{level}] {component}: {message}")
            if details:
                self.logger.debug(f"Details: {details}")
        except Exception as e:
            self.logger.error(f"시스템 이벤트 로깅 실패: {e}")
    
    def save_prediction(self, **kwargs):
        """예측 데이터 저장 (임시 구현)"""
        # TODO: MLDao로 이동 예정
        pass
    
    def get_kelly_data(self, symbol: str) -> Dict[str, Any]:
        """Kelly 데이터 조회 (임시 구현)"""
        # TODO: PerformanceDAO로 이동 예정
        return {'total_trades': 0, 'winning_trades': 0}
    
    def update_kelly_tracking(self, symbol: str, **kwargs):
        """Kelly 추적 업데이트 (임시 구현)"""
        # TODO: PerformanceDAO로 이동 예정
        pass
    
    def save_daily_performance(self, **kwargs):
        """일일 성과 저장 (임시 구현)"""
        # TODO: PerformanceDAO로 이동 예정
        pass
    
    def update_daily_performance(self, date: str, performance_data: Dict[str, Any]):
        """
        일일 성과 업데이트 - 호환성을 위한 메서드
        
        Args:
            date: 날짜 문자열 (YYYY-MM-DD)
            performance_data: 성과 데이터 딕셔너리
        """
        try:
            if self._legacy_manager:
                # 레거시 매니저의 update_daily_performance 사용
                return self._legacy_manager.update_daily_performance(date, performance_data)
            else:
                # 레거시 매니저가 없으면 로깅만
                self.logger.info(f"일일 성과 업데이트: {date}, 데이터: {performance_data}")
                return True
                
        except Exception as e:
            self.logger.error(f"일일 성과 업데이트 실패: {e}")
            # 오류가 발생해도 시스템은 계속 동작하도록 함
            return False
    
    def get_recent_news(self, limit: int = 10) -> List[Dict[str, Any]]:
        """최근 뉴스 조회 (임시 구현)"""
        # TODO: NewsDAO로 이동 예정
        return []
    
    def save_news(self, **kwargs):
        """뉴스 저장 (임시 구현)"""
        # TODO: NewsDAO로 이동 예정
        pass
    
    # =============================================================================
    # 시스템 정보 메서드들
    # =============================================================================
    
    def get_dao_stats(self) -> Dict[str, Any]:
        """DAO 시스템 통계"""
        return {
            'dao_pattern': 'active',
            'available_daos': [
                'TradeDAO', 'PositionDAO'
            ],
            'pending_daos': [
                'PerformanceDAO', 'MLDao', 'NewsDAO', 'SystemDAO'
            ],
            'database_path': self.db_path,
            'status': 'partial_migration'
        }
    
    def get_system_status(self) -> Dict[str, Any]:
        """시스템 상태 조회"""
        try:
            # 각 DAO의 상태 확인
            trade_count = len(self.trade_dao.get_trades_by_symbol('BTCUSDT', 1))
            position_count = len(self.position_dao.get_active_positions())
            
            return {
                'status': 'healthy',
                'dao_system': 'active',
                'active_positions': position_count,
                'recent_trades': trade_count >= 0,
                'database_accessible': True
            }
        except Exception as e:
            self.logger.error(f"시스템 상태 확인 실패: {e}")
            return {
                'status': 'error',
                'error': str(e),
                'database_accessible': False
            }


# 하위 호환성을 위한 별칭
DatabaseManager = EnhancedDatabaseManager
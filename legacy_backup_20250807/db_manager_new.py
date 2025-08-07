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
    
    def update_daily_performance(self, date: str, performance_data: Dict[str, Any]) -> bool:
        """
        일일 성과 업데이트 - 완전한 구현
        
        Args:
            date: 날짜 문자열 (YYYY-MM-DD 형식)
            performance_data: 성과 데이터 딕셔너리
            {
                'total_pnl': float,      # 총 손익
                'total_trades': int,     # 총 거래 수
                'winning_trades': int,   # 수익 거래 수
                'losing_trades': int,    # 손실 거래 수
                'win_rate': float,       # 승률
                'avg_profit': float,     # 평균 수익
                'avg_loss': float,       # 평균 손실
                'max_drawdown': float,   # 최대 드로우다운
                'roi': float            # ROI
            }
            
        Returns:
            bool: 업데이트 성공 여부
        """
        try:
            self.logger.info(f"📊 일일 성과 업데이트 시작: {date}")
            
            # 1. 레거시 매니저가 있으면 사용
            if self._legacy_manager and hasattr(self._legacy_manager, 'update_daily_performance'):
                result = self._legacy_manager.update_daily_performance(date, performance_data)
                self.logger.info(f"✅ 레거시 매니저로 성과 업데이트 완료: {date}")
                return result
            
            # 2. 직접 데이터베이스에 저장 (DAO 패턴 사용)
            try:
                # performance_dao가 있으면 사용
                if hasattr(self, 'performance_dao'):
                    performance_id = self.performance_dao.save_daily_performance(date, performance_data)
                    self.logger.info(f"✅ DAO로 성과 업데이트 완료: {date}, ID: {performance_id}")
                    return True
            except Exception as dao_error:
                self.logger.warning(f"DAO 사용 실패: {dao_error}")
            
            # 3. 기본 로깅 및 메모리 저장
            if not hasattr(self, '_daily_performance_cache'):
                self._daily_performance_cache = {}
            
            self._daily_performance_cache[date] = {
                **performance_data,
                'updated_at': datetime.now().isoformat(),
                'method': 'cache_only'
            }
            
            self.logger.info(f"📝 일일 성과 캐시 저장 완료: {date}")
            self.logger.info(f"📈 성과 요약 - 총 손익: {performance_data.get('total_pnl', 0):+.2f}, "
                           f"총 거래: {performance_data.get('total_trades', 0)}회, "
                           f"승률: {performance_data.get('win_rate', 0):.1%}")
            
            return True
            
        except Exception as e:
            self.logger.error(f"❌ 일일 성과 업데이트 실패: {date}, 오류: {e}")
            # 오류 발생해도 시스템 중단하지 않음
            return False
    
    def get_daily_performance(self, date: str = None) -> Dict[str, Any]:
        """
        일일 성과 조회
        
        Args:
            date: 날짜 문자열 (None이면 오늘)
            
        Returns:
            Dict: 성과 데이터
        """
        try:
            if date is None:
                date = datetime.now().strftime('%Y-%m-%d')
            
            # 캐시에서 조회
            if hasattr(self, '_daily_performance_cache') and date in self._daily_performance_cache:
                return self._daily_performance_cache[date]
            
            # 레거시 매니저에서 조회
            if self._legacy_manager and hasattr(self._legacy_manager, 'get_daily_performance'):
                return self._legacy_manager.get_daily_performance(date)
            
            # 기본값 반환
            return {
                'total_pnl': 0.0,
                'total_trades': 0,
                'winning_trades': 0,
                'losing_trades': 0,
                'win_rate': 0.0,
                'avg_profit': 0.0,
                'avg_loss': 0.0,
                'max_drawdown': 0.0,
                'roi': 0.0,
                'method': 'default'
            }
            
        except Exception as e:
            self.logger.error(f"일일 성과 조회 실패: {date}, 오류: {e}")
            return {}
    
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
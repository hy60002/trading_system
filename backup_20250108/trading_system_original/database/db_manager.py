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
from .dao.performance_dao import PerformanceDAO
from .dao.ml_dao import MLDao
from .dao.news_dao import NewsDAO
from .dao.system_dao import SystemDAO


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
        try:
            self.trade_dao = TradeDAO(db_path)
            self.position_dao = PositionDAO(db_path)
            self.performance_dao = PerformanceDAO(db_path)
            self.ml_dao = MLDao(db_path)
            self.news_dao = NewsDAO(db_path)
            self.system_dao = SystemDAO(db_path)
            self.logger.info("✅ 모든 DAO 인스턴스 생성 완료")
        except Exception as e:
            self.logger.error(f"❌ DAO 초기화 오류: {e}")
            # 최소한 필수 DAO는 생성
            self.trade_dao = TradeDAO(db_path)
            self.position_dao = PositionDAO(db_path)
            # 선택적 DAO들은 None으로 초기화
            self.performance_dao = None
            self.ml_dao = None
            self.news_dao = None
            self.system_dao = None
        
        self.logger.info("✅ DAO 패턴 데이터베이스 매니저 초기화 완료")
    
    async def initialize(self):
        """데이터베이스 초기화 (비동기 호환성)"""
        self.logger.info("데이터베이스 초기화 완료")
        return True
    
    def initialize_database(self):
        """데이터베이스 초기화 (동기 버전)"""
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
    
    def get_open_positions(self, symbol: str = None) -> List[Dict[str, Any]]:
        """열린 포지션 조회 (별칭)"""
        return self.get_active_positions(symbol)
    
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
    
    def save_trade(self, trade_data: Dict) -> int:
        """거래 데이터 저장"""
        return self.trade_dao.add_trade(trade_data)
    
    def save_position(self, position_data: Dict) -> int:
        """포지션 데이터 저장"""
        return self.position_dao.add_position(position_data)
    
    def update_trade(self, trade_id: int, update_data: Dict) -> bool:
        """거래 데이터 업데이트"""
        return self.trade_dao.update_trade(trade_id, update_data)
    
    def get_kelly_fraction(self, symbol: str) -> float:
        """Kelly fraction 조회"""
        try:
            if self.performance_dao:
                kelly_data = self.performance_dao.get_kelly_data(symbol)
                # Kelly fraction 계산 로직 (간단한 구현)
                total_trades = kelly_data.get('total_trades', 0)
                winning_trades = kelly_data.get('winning_trades', 0)
                if total_trades > 0:
                    win_rate = winning_trades / total_trades
                    return min(win_rate, 0.25)  # 최대 25%로 제한
                return 0.1  # 기본값
            return 0.1
        except Exception as e:
            self.logger.error(f"Kelly fraction 조회 실패: {e}")
            return 0.1
    
    def execute_query(self, query: str, params: tuple = None):
        """SQL 쿼리 실행"""
        try:
            with self._get_connection() as conn:
                cursor = conn.cursor()
                if params:
                    cursor.execute(query, params)
                else:
                    cursor.execute(query)
                conn.commit()
                return cursor.fetchall()
        except Exception as e:
            self.logger.error(f"쿼리 실행 실패: {e}")
            return None
    
    def get_latest_balance(self) -> Optional[Dict[str, Any]]:
        """최신 잔액 조회"""
        return self.position_dao.get_latest_balance()
    
    # =============================================================================
    # 임시 호환성 메서드들 (점진적 마이그레이션을 위해)
    # =============================================================================
    
    def log_system_event(self, level: str, component: str, message: str, details: Dict = None):
        """시스템 이벤트 로깅"""
        try:
            if self.system_dao:
                # SystemDAO를 사용하여 데이터베이스에 저장
                self.system_dao.log_event(
                    event_type=level,
                    component=component,
                    message=message,
                    details=details
                )
            else:
                # Fallback: 로거에만 기록
                self.logger.info(f"[{level}] {component}: {message}")
                if details:
                    self.logger.debug(f"Details: {details}")
        except Exception as e:
            self.logger.error(f"시스템 이벤트 로깅 실패: {e}")
    
    def save_prediction(self, **kwargs):
        """예측 데이터 저장"""
        try:
            if self.ml_dao:
                return self.ml_dao.save_prediction(kwargs)
            else:
                self.logger.warning("MLDao가 사용할 수 없어 예측 데이터를 저장할 수 없습니다")
        except Exception as e:
            self.logger.error(f"예측 데이터 저장 실패: {e}")
    
    def get_kelly_data(self, symbol: str) -> Dict[str, Any]:
        """Kelly 데이터 조회"""
        try:
            if self.performance_dao:
                return self.performance_dao.get_kelly_data(symbol)
            else:
                return {'total_trades': 0, 'winning_trades': 0}
        except Exception as e:
            self.logger.error(f"Kelly 데이터 조회 실패: {e}")
            return {'total_trades': 0, 'winning_trades': 0}
    
    def update_kelly_tracking(self, symbol: str, **kwargs):
        """Kelly 추적 업데이트"""
        try:
            if self.performance_dao:
                return self.performance_dao.update_kelly_tracking(symbol, kwargs)
        except Exception as e:
            self.logger.error(f"Kelly 추적 업데이트 실패: {e}")
    
    def save_daily_performance(self, **kwargs):
        """일일 성과 저장"""
        try:
            if self.performance_dao:
                return self.performance_dao.save_daily_performance(kwargs)
        except Exception as e:
            self.logger.error(f"일일 성과 저장 실패: {e}")
    
    def get_daily_performance(self, days: int = 30) -> Dict[str, Any]:
        """일일 성과 조회"""
        try:
            if self.performance_dao:
                return self.performance_dao.get_daily_performance(days)
            else:
                return {
                    'total_pnl': 0.0,
                    'daily_returns': [],
                    'win_rate': 0.0,
                    'total_trades': 0
                }
        except Exception as e:
            self.logger.error(f"일일 성과 조회 실패: {e}")
            return {
                'total_pnl': 0.0,
                'daily_returns': [],
                'win_rate': 0.0,
                'total_trades': 0
            }
    
    def _get_connection(self):
        """데이터베이스 연결 (백워드 호환성)"""
        # 기존 코드와의 호환성을 위해 TradeDAO의 연결을 사용
        return self.trade_dao._get_connection()
    
    def get_recent_news(self, limit: int = 10) -> List[Dict[str, Any]]:
        """최근 뉴스 조회"""
        try:
            if self.news_dao:
                return self.news_dao.get_recent_news(limit)
            else:
                return []
        except Exception as e:
            self.logger.error(f"뉴스 조회 실패: {e}")
            return []
    
    def save_news(self, **kwargs):
        """뉴스 저장"""
        try:
            if self.news_dao:
                return self.news_dao.save_news(kwargs)
        except Exception as e:
            self.logger.error(f"뉴스 저장 실패: {e}")
    
    # =============================================================================
    # 시스템 정보 메서드들
    # =============================================================================
    
    def get_dao_stats(self) -> Dict[str, Any]:
        """DAO 시스템 통계"""
        active_daos = ['TradeDAO', 'PositionDAO']
        failed_daos = []
        
        # 활성화된 DAO 확인
        if self.performance_dao:
            active_daos.append('PerformanceDAO')
        else:
            failed_daos.append('PerformanceDAO')
            
        if self.ml_dao:
            active_daos.append('MLDao')
        else:
            failed_daos.append('MLDao')
            
        if self.news_dao:
            active_daos.append('NewsDAO')
        else:
            failed_daos.append('NewsDAO')
            
        if self.system_dao:
            active_daos.append('SystemDAO')
        else:
            failed_daos.append('SystemDAO')
        
        return {
            'dao_pattern': 'active',
            'active_daos': active_daos,
            'failed_daos': failed_daos,
            'database_path': self.db_path,
            'status': 'full_migration' if not failed_daos else 'partial_migration'
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
"""
Enhanced Database Manager - Additional Features from trading_system2
trading_system2의 향상된 기능들을 기존 시스템에 추가
"""

import logging
from typing import Dict, Any
from datetime import datetime


class EnhancedDatabaseManager:
    """
    trading_system2에서 가져온 향상된 데이터베이스 매니저
    기존 DAO 기반 시스템과 함께 사용할 수 있는 추가 기능들 제공
    """
    
    def __init__(self, db_connection):
        self.db = db_connection
        self.logger = logging.getLogger(self.__class__.__name__)
        
    def update_daily_performance(self, symbol: str, performance: dict):
        """
        일일 성과 추적 기능 - trading_system2에서 가져온 기능
        기존 시스템의 성과 추적을 보완하는 간단한 일일 요약 기능
        """
        try:
            # SQLite 호환 쿼리로 수정 (PostgreSQL 구문에서 변경)
            sql = """
            INSERT OR REPLACE INTO daily_performance (symbol, date, pnl, trades)
            VALUES (?, ?, ?, ?)
            """
            params = (
                symbol,
                performance.get("date", datetime.now().strftime('%Y-%m-%d')),
                performance.get("pnl", 0.0),
                performance.get("trades", 0),
            )
            
            cursor = self.db.cursor()
            cursor.execute(sql, params)
            self.db.commit()
            cursor.close()
            
            self.logger.info(f"✅ {symbol} 일일 성과 업데이트 완료")
            
        except Exception as e:
            self.logger.error(f"❌ update_daily_performance 오류: {e}", exc_info=True)
            
    def get_daily_summary(self, symbol: str, date: str = None) -> Dict[str, Any]:
        """
        일일 요약 조회 기능 - 추가된 유틸리티 메서드
        """
        if date is None:
            date = datetime.now().strftime('%Y-%m-%d')
            
        try:
            sql = "SELECT * FROM daily_performance WHERE symbol = ? AND date = ?"
            cursor = self.db.cursor()
            cursor.execute(sql, (symbol, date))
            result = cursor.fetchone()
            cursor.close()
            
            if result:
                return {
                    "symbol": result[0],
                    "date": result[1], 
                    "pnl": result[2],
                    "trades": result[3]
                }
            else:
                return {"symbol": symbol, "date": date, "pnl": 0.0, "trades": 0}
                
        except Exception as e:
            self.logger.error(f"❌ get_daily_summary 오류: {e}")
            return {"symbol": symbol, "date": date, "pnl": 0.0, "trades": 0}

    def ensure_daily_performance_table(self):
        """
        daily_performance 테이블이 존재하지 않을 경우 생성
        """
        try:
            sql = """
            CREATE TABLE IF NOT EXISTS daily_performance (
                symbol TEXT,
                date TEXT,
                pnl REAL,
                trades INTEGER,
                PRIMARY KEY (symbol, date)
            )
            """
            cursor = self.db.cursor()
            cursor.execute(sql)
            self.db.commit()
            cursor.close()
            self.logger.info("✅ daily_performance 테이블 준비 완료")
            
        except Exception as e:
            self.logger.error(f"❌ daily_performance 테이블 생성 오류: {e}")
"""
News DAO
뉴스 관련 데이터베이스 접근 객체
"""

from typing import Dict, List, Optional, Any
from datetime import datetime, timedelta
from .base_dao import BaseDAO


class NewsDAO(BaseDAO):
    """뉴스 관련 데이터베이스 접근 객체"""
    
    def __init__(self, db_path: str):
        super().__init__(db_path)
        self._ensure_tables()
    
    def _ensure_tables(self):
        """뉴스 관련 테이블 생성"""
        tables = {
            'news_articles': '''
                CREATE TABLE IF NOT EXISTS news_articles (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    timestamp DATETIME DEFAULT CURRENT_TIMESTAMP,
                    title TEXT NOT NULL,
                    content TEXT,
                    source TEXT NOT NULL,
                    url TEXT UNIQUE,
                    published_at DATETIME,
                    symbols TEXT,
                    sentiment_score REAL DEFAULT 0,
                    confidence REAL DEFAULT 0,
                    relevance_score REAL DEFAULT 0,
                    is_processed BOOLEAN DEFAULT 0,
                    category TEXT DEFAULT 'general'
                )
            ''',
            'sentiment_analysis': '''
                CREATE TABLE IF NOT EXISTS sentiment_analysis (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    timestamp DATETIME DEFAULT CURRENT_TIMESTAMP,
                    symbol TEXT NOT NULL,
                    timeframe TEXT DEFAULT '1h',
                    overall_sentiment REAL DEFAULT 0,
                    positive_count INTEGER DEFAULT 0,
                    negative_count INTEGER DEFAULT 0,
                    neutral_count INTEGER DEFAULT 0,
                    weighted_sentiment REAL DEFAULT 0,
                    news_count INTEGER DEFAULT 0,
                    avg_confidence REAL DEFAULT 0
                )
            ''',
            'keyword_tracking': '''
                CREATE TABLE IF NOT EXISTS keyword_tracking (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    timestamp DATETIME DEFAULT CURRENT_TIMESTAMP,
                    keyword TEXT NOT NULL,
                    symbol TEXT NOT NULL,
                    mentions INTEGER DEFAULT 1,
                    sentiment_impact REAL DEFAULT 0,
                    price_correlation REAL DEFAULT 0
                )
            '''
        }
        
        for table_name, create_sql in tables.items():
            self._execute_query(create_sql, fetch_all=False)
    
    def add_news_article(self, article_data: Dict[str, Any]) -> int:
        """뉴스 기사 추가"""
        required_fields = ['title', 'source']
        self._validate_required_fields(article_data, required_fields)
        
        sanitized_data = self._sanitize_data(article_data)
        
        query = '''
            INSERT OR IGNORE INTO news_articles (
                title, content, source, url, published_at, symbols,
                sentiment_score, confidence, relevance_score, category
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        '''
        
        params = (
            sanitized_data['title'],
            sanitized_data.get('content', ''),
            sanitized_data['source'],
            sanitized_data.get('url'),
            sanitized_data.get('published_at', datetime.now().isoformat()),
            sanitized_data.get('symbols', ''),
            sanitized_data.get('sentiment_score', 0),
            sanitized_data.get('confidence', 0),
            sanitized_data.get('relevance_score', 0),
            sanitized_data.get('category', 'general')
        )
        
        return self._execute_insert(query, params)
    
    def get_recent_news(self, symbol: str = None, hours: int = 24, limit: int = 50) -> List[Dict[str, Any]]:
        """최근 뉴스 조회"""
        cache_key = f"recent_news:{symbol or 'all'}:hours:{hours}:limit:{limit}"
        cached_data = self._get_cached_data(cache_key)
        if cached_data:
            return cached_data
        
        if symbol:
            query = '''
                SELECT * FROM news_articles 
                WHERE (symbols LIKE ? OR symbols = '') 
                AND timestamp >= datetime('now', '-{} hours')
                ORDER BY published_at DESC, relevance_score DESC
                LIMIT ?
            '''.format(hours)
            params = (f'%{symbol}%', limit)
        else:
            query = '''
                SELECT * FROM news_articles 
                WHERE timestamp >= datetime('now', '-{} hours')
                ORDER BY published_at DESC, relevance_score DESC
                LIMIT ?
            '''.format(hours)
            params = (limit,)
        
        result = self._execute_query(query, params)
        self._set_cached_data(cache_key, result, ttl=600)  # 10분 캐시
        return result
    
    def get_sentiment_analysis(self, symbol: str, timeframe: str = '1h') -> Dict[str, Any]:
        """감정 분석 결과 조회"""
        cache_key = f"sentiment_analysis:{symbol}:{timeframe}"
        cached_data = self._get_cached_data(cache_key)
        if cached_data:
            return cached_data
        
        query = '''
            SELECT * FROM sentiment_analysis 
            WHERE symbol = ? AND timeframe = ?
            ORDER BY timestamp DESC 
            LIMIT 1
        '''
        
        result = self._execute_query(query, (symbol, timeframe), fetch_one=True)
        
        if result:
            sentiment = dict(result)
        else:
            sentiment = {
                'symbol': symbol,
                'timeframe': timeframe,
                'overall_sentiment': 0.0,
                'positive_count': 0,
                'negative_count': 0,
                'neutral_count': 0,
                'weighted_sentiment': 0.0,
                'news_count': 0,
                'avg_confidence': 0.0
            }
        
        self._set_cached_data(cache_key, sentiment, ttl=900)  # 15분 캐시
        return sentiment
    
    def update_sentiment_analysis(self, sentiment_data: Dict[str, Any]) -> bool:
        """감정 분석 결과 업데이트"""
        required_fields = ['symbol', 'timeframe']
        self._validate_required_fields(sentiment_data, required_fields)
        
        sanitized_data = self._sanitize_data(sentiment_data)
        
        # 캐시 무효화
        symbol = sanitized_data['symbol']
        timeframe = sanitized_data['timeframe']
        self._clear_cache_pattern(f"sentiment_analysis:{symbol}:{timeframe}")
        
        query = '''
            INSERT OR REPLACE INTO sentiment_analysis (
                symbol, timeframe, overall_sentiment, positive_count, negative_count,
                neutral_count, weighted_sentiment, news_count, avg_confidence
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        '''
        
        params = (
            symbol,
            timeframe,
            sanitized_data.get('overall_sentiment', 0),
            sanitized_data.get('positive_count', 0),
            sanitized_data.get('negative_count', 0),
            sanitized_data.get('neutral_count', 0),
            sanitized_data.get('weighted_sentiment', 0),
            sanitized_data.get('news_count', 0),
            sanitized_data.get('avg_confidence', 0)
        )
        
        result = self._execute_query(query, params, fetch_all=False)
        return result > 0
    
    def mark_article_processed(self, article_id: int) -> bool:
        """기사 처리 완료 표시"""
        query = '''
            UPDATE news_articles 
            SET is_processed = 1 
            WHERE id = ?
        '''
        
        result = self._execute_query(query, (article_id,), fetch_all=False)
        
        # 캐시 무효화
        self._clear_cache_pattern("recent_news:*")
        
        return result > 0
    
    def get_unprocessed_articles(self, limit: int = 100) -> List[Dict[str, Any]]:
        """미처리 기사 조회"""
        query = '''
            SELECT * FROM news_articles 
            WHERE is_processed = 0 
            ORDER BY published_at DESC, relevance_score DESC
            LIMIT ?
        '''
        
        return self._execute_query(query, (limit,))
    
    def add_keyword_tracking(self, keyword: str, symbol: str, sentiment_impact: float = 0) -> bool:
        """키워드 추적 추가"""
        # 기존 키워드가 있는지 확인 후 업데이트 또는 생성
        query = '''
            INSERT OR REPLACE INTO keyword_tracking (
                keyword, symbol, mentions, sentiment_impact, timestamp
            ) VALUES (
                ?, ?, 
                COALESCE((SELECT mentions FROM keyword_tracking WHERE keyword = ? AND symbol = ?), 0) + 1,
                ?, 
                CURRENT_TIMESTAMP
            )
        '''
        
        params = (keyword, symbol, keyword, symbol, sentiment_impact)
        
        result = self._execute_query(query, params, fetch_all=False)
        return result > 0
    
    def get_trending_keywords(self, symbol: str = None, hours: int = 24, limit: int = 20) -> List[Dict[str, Any]]:
        """트렌딩 키워드 조회"""
        cache_key = f"trending_keywords:{symbol or 'all'}:hours:{hours}:limit:{limit}"
        cached_data = self._get_cached_data(cache_key)
        if cached_data:
            return cached_data
        
        if symbol:
            query = '''
                SELECT keyword, symbol, SUM(mentions) as total_mentions, 
                       AVG(sentiment_impact) as avg_sentiment
                FROM keyword_tracking 
                WHERE symbol = ? AND timestamp >= datetime('now', '-{} hours')
                GROUP BY keyword, symbol
                ORDER BY total_mentions DESC, avg_sentiment DESC
                LIMIT ?
            '''.format(hours)
            params = (symbol, limit)
        else:
            query = '''
                SELECT keyword, symbol, SUM(mentions) as total_mentions, 
                       AVG(sentiment_impact) as avg_sentiment
                FROM keyword_tracking 
                WHERE timestamp >= datetime('now', '-{} hours')
                GROUP BY keyword, symbol
                ORDER BY total_mentions DESC, avg_sentiment DESC
                LIMIT ?
            '''.format(hours)
            params = (limit,)
        
        result = self._execute_query(query, params)
        self._set_cached_data(cache_key, result, ttl=1800)  # 30분 캐시
        return result
    
    def get_news_impact_score(self, symbol: str, hours: int = 6) -> float:
        """뉴스 임팩트 점수 계산"""
        cache_key = f"news_impact:{symbol}:hours:{hours}"
        cached_data = self._get_cached_data(cache_key)
        if cached_data is not None:
            return cached_data
        
        query = '''
            SELECT 
                COUNT(*) as news_count,
                AVG(sentiment_score) as avg_sentiment,
                AVG(confidence) as avg_confidence,
                AVG(relevance_score) as avg_relevance
            FROM news_articles 
            WHERE (symbols LIKE ? OR symbols = '') 
            AND timestamp >= datetime('now', '-{} hours')
            AND confidence > 0.6
        '''.format(hours)
        
        result = self._execute_query(query, (f'%{symbol}%',), fetch_one=True)
        
        if result and result['news_count'] > 0:
            # 뉴스 개수, 감정 점수, 신뢰도, 관련성을 종합한 임팩트 점수
            news_count = result['news_count']
            avg_sentiment = result['avg_sentiment'] or 0
            avg_confidence = result['avg_confidence'] or 0.5
            avg_relevance = result['avg_relevance'] or 0.5
            
            # 로그 스케일링 적용 (뉴스 개수가 많을수록 임팩트 증가하지만 점진적으로 감소)
            import math
            count_factor = math.log(news_count + 1) / 10  # 0~1 범위로 정규화
            
            # 최종 임팩트 점수 = 감정점수 * 신뢰도 * 관련성 * 뉴스개수팩터
            impact_score = avg_sentiment * avg_confidence * avg_relevance * (1 + count_factor)
            
            # -1 ~ 1 범위로 클램핑
            impact_score = max(-1, min(1, impact_score))
        else:
            impact_score = 0.0
        
        self._set_cached_data(cache_key, impact_score, ttl=900)  # 15분 캐시
        return impact_score
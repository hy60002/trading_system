"""
Enhanced News Sentiment Analyzer - Modularized Version
뉴스 감성 분석 시스템 (모듈화된 버전)

이 파일은 기존 단일 파일(927줄)을 다음 모듈들로 분리했습니다:
- news/news_fetcher.py: RSS 피드 수집 및 파싱
- news/sentiment_analyzer.py: GPT 기반 감성 분석  
- news/news_filter.py: 뉴스 필터링 및 신뢰도 평가
- news/news_manager.py: 통합 관리자
"""

# Import handling for both direct and package imports
try:
    from ..config.config import TradingConfig
    from ..database.db_manager import EnhancedDatabaseManager
except ImportError:
    import sys
    import os
    sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    from config.config import TradingConfig
    from database.db_manager import EnhancedDatabaseManager

# 새로운 모듈 시스템 사용
from .news.news_manager import NewsManager


class EnhancedNewsSentimentAnalyzer:
    """
    Enhanced news sentiment analysis with filtering and reliability scoring
    
    이제 모듈화된 시스템을 사용합니다:
    - 코드 분리로 유지보수성 향상
    - 개별 모듈 테스트 가능
    - 책임 분리로 코드 품질 향상
    - 과민반응 문제 해결된 필터링 시스템
    """
    
    def __init__(self, config: TradingConfig, db: EnhancedDatabaseManager = None):
        """
        초기화 - 내부적으로 NewsManager 사용
        
        Args:
            config: 거래 시스템 설정
            db: 데이터베이스 매니저 (선택사항)
        """
        # 새로운 모듈화된 시스템으로 위임
        self._news_manager = NewsManager(config, db)
        
        # 하위 호환성을 위한 속성들
        self.config = config
        self.db = db
        self.logger = self._news_manager.logger
    
    async def initialize(self):
        """뉴스 분석 시스템 초기화"""
        return await self._news_manager.initialize()
    
    async def analyze_sentiment(self, symbol: str = None) -> dict:
        """
        뉴스 감성 분석 수행
        
        Args:
            symbol: 분석할 심볼 (예: 'BTCUSDT', 'ETHUSDT')
            
        Returns:
            dict: 감성 분석 결과
            {
                'sentiment': float,      # -1.0 ~ 1.0
                'impact': str,          # 'low', 'medium', 'high'  
                'confidence': float,    # 0.0 ~ 1.0
                'keywords': list,       # 주요 키워드들
                'summary': str,         # 분석 요약
                'emergency': dict,      # 긴급 상황 정보
                'news_metadata': dict,  # 뉴스 메타데이터
                'processing_time': float,  # 처리 시간
                'news_count': int       # 분석된 뉴스 수
            }
        """
        return await self._news_manager.analyze_sentiment(symbol)
    
    async def cleanup(self):
        """시스템 정리"""
        await self._news_manager.cleanup()
    
    def get_stats(self) -> dict:
        """시스템 통계 반환"""
        return self._news_manager.get_comprehensive_stats()
    
    # 하위 호환성을 위한 기존 메서드들 (deprecated)
    async def _fetch_news(self, symbol: str = None):
        """Deprecated: 직접 NewsManager 사용을 권장"""
        return await self._news_manager.fetcher.fetch_news(symbol)
    
    def _filter_reliable_news(self, news_items: list):
        """Deprecated: 직접 NewsManager 사용을 권장"""
        return self._news_manager.filter.filter_reliable_news(news_items)
    
    def _check_emergency_keywords(self, news_items: list):
        """Deprecated: 직접 NewsManager 사용을 권장"""
        return self._news_manager.filter.check_emergency_keywords(news_items)


# 하위 호환성을 위한 별칭
NewsSentimentAnalyzer = EnhancedNewsSentimentAnalyzer
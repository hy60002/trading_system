"""
Legacy News Sentiment Analyzer (Backup)
기존 단일 파일 백업용
"""

# 기존 파일을 백업으로 이동하고 새로운 모듈 시스템 사용
from .news.news_manager import NewsManager

# 하위 호환성을 위한 별칭
EnhancedNewsSentimentAnalyzer = NewsManager
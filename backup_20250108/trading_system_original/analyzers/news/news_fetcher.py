"""
News Fetcher Module
RSS 피드 수집 및 파싱 전담 모듈
"""

import asyncio
import logging
import time
import feedparser
from typing import Dict, List, Optional, Any
from cachetools import TTLCache

# Import handling for both direct and package imports
try:
    from ...config.config import TradingConfig
except ImportError:
    import sys
    import os
    sys.path.append(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
    from config.config import TradingConfig


class NewsFetcher:
    """RSS 피드 수집 및 파싱 전담 클래스"""
    
    def __init__(self, config: TradingConfig):
        self.config = config
        self.logger = logging.getLogger(__name__)
        self._news_cache = TTLCache(maxsize=100, ttl=300)  # 5분 캐시
        
        # Enhanced news sources with reliability scores
        self.news_sources = {
            # Tier 1: Highly reliable sources (weight: 1.0)
            "https://feeds.feedburner.com/CoinDesk": {
                "weight": 1.0, "reliability": 0.88, "name": "CoinDesk"
            },
            "https://www.theblockcrypto.com/rss.xml": {
                "weight": 1.0, "reliability": 0.85, "name": "The Block"
            },
            
            # Tier 2: Moderately reliable sources (weight: 0.8)
            "https://cointelegraph.com/rss": {
                "weight": 0.8, "reliability": 0.78, "name": "Cointelegraph"
            },
            "https://bitcoinist.com/feed/": {
                "weight": 0.8, "reliability": 0.75, "name": "Bitcoinist"
            },
            
            # Tier 3: Less reliable but useful sources (weight: 0.6)
            "https://www.newsbtc.com/feed/": {
                "weight": 0.6, "reliability": 0.65, "name": "NewsBTC"
            },
            "https://cryptopotato.com/feed/": {
                "weight": 0.6, "reliability": 0.62, "name": "CryptoPotato"
            },
            
            # Additional quality sources
            "https://decrypt.co/feed": {
                "weight": 0.9, "reliability": 0.82, "name": "Decrypt"
            }
        }
        
        # 뉴스 중복 방지를 위한 제목 해시 저장
        self._seen_news = set()
        
    async def fetch_news(self, symbol: Optional[str] = None) -> List[Dict[str, Any]]:
        """RSS 피드에서 뉴스 수집"""
        cache_key = f"news:{symbol or 'all'}"
        cached_result = self._news_cache.get(cache_key)
        if cached_result:
            return cached_result
            
        try:
            all_news = []
            
            # 각 뉴스 소스에서 병렬로 수집
            tasks = []
            for url, source_info in self.news_sources.items():
                task = self._fetch_from_source(url, source_info, symbol)
                tasks.append(task)
            
            # 병렬 실행으로 속도 향상
            results = await asyncio.gather(*tasks, return_exceptions=True)
            
            for result in results:
                if isinstance(result, list):
                    all_news.extend(result)
                elif isinstance(result, Exception):
                    self.logger.warning(f"뉴스 소스 수집 실패: {result}")
            
            # 중복 제거 및 정렬
            unique_news = self._remove_duplicates(all_news)
            sorted_news = sorted(unique_news, key=lambda x: x.get('timestamp', 0), reverse=True)
            
            # 최신 20개만 유지
            result = sorted_news[:20]
            
            # 캐시 저장
            self._news_cache[cache_key] = result
            
            self.logger.info(f"뉴스 수집 완료: {len(result)}개 ({symbol or '전체'})")
            return result
            
        except Exception as e:
            self.logger.error(f"뉴스 수집 중 오류: {e}")
            return []
    
    async def _fetch_from_source(self, url: str, source_info: Dict, symbol: Optional[str]) -> List[Dict[str, Any]]:
        """개별 RSS 소스에서 뉴스 수집"""
        try:
            # RSS 파싱 (비동기 처리를 위해 executor 사용)
            loop = asyncio.get_event_loop()
            feed = await loop.run_in_executor(None, feedparser.parse, url)
            
            if not feed.entries:
                return []
            
            news_items = []
            for entry in feed.entries[:10]:  # 소스당 최대 10개
                try:
                    # 기본 정보 추출
                    title = entry.get('title', '').strip()
                    description = entry.get('description', '').strip()
                    link = entry.get('link', '')
                    
                    if not title:
                        continue
                    
                    # 심볼 필터링
                    if symbol and not self._is_relevant_to_symbol(title + ' ' + description, symbol):
                        continue
                    
                    # 타임스탬프 처리
                    timestamp = time.time()
                    if hasattr(entry, 'published_parsed') and entry.published_parsed:
                        try:
                            timestamp = time.mktime(entry.published_parsed)
                        except:
                            pass
                    
                    news_item = {
                        'title': title,
                        'description': description,
                        'link': link,
                        'source': source_info['name'],
                        'source_weight': source_info['weight'],
                        'source_reliability': source_info['reliability'],
                        'timestamp': timestamp,
                        'content': title + ' ' + description
                    }
                    
                    news_items.append(news_item)
                    
                except Exception as e:
                    self.logger.debug(f"뉴스 항목 처리 실패 ({source_info['name']}): {e}")
                    continue
            
            return news_items
            
        except Exception as e:
            self.logger.warning(f"RSS 소스 수집 실패 ({source_info['name']}): {e}")
            return []
    
    def _is_relevant_to_symbol(self, content: str, symbol: str) -> bool:
        """뉴스가 특정 심볼과 관련있는지 확인"""
        content_lower = content.lower()
        
        # 심볼별 키워드 매핑
        symbol_keywords = {
            'BTCUSDT': ['bitcoin', 'btc', 'satoshi'],
            'ETHUSDT': ['ethereum', 'eth', 'ether', 'vitalik'],
            'XRPUSDT': ['ripple', 'xrp', 'sec']
        }
        
        keywords = symbol_keywords.get(symbol, [])
        if not keywords:
            return True  # 매핑되지 않은 심볼은 모든 뉴스 포함
        
        return any(keyword in content_lower for keyword in keywords)
    
    def _remove_duplicates(self, news_items: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """중복 뉴스 제거"""
        unique_news = []
        seen_titles = set()
        
        for item in news_items:
            title = item.get('title', '').lower().strip()
            
            # 제목의 핵심 부분으로 중복 검사 (첫 50자)
            title_key = title[:50]
            
            if title_key not in seen_titles:
                seen_titles.add(title_key)
                unique_news.append(item)
        
        return unique_news
    
    def get_source_stats(self) -> Dict[str, Any]:
        """뉴스 소스 통계 반환"""
        return {
            'total_sources': len(self.news_sources),
            'tier1_sources': len([s for s in self.news_sources.values() if s['weight'] >= 1.0]),
            'tier2_sources': len([s for s in self.news_sources.values() if s['weight'] >= 0.8]),
            'tier3_sources': len([s for s in self.news_sources.values() if s['weight'] < 0.8]),
            'avg_reliability': sum(s['reliability'] for s in self.news_sources.values()) / len(self.news_sources),
            'sources': list(self.news_sources.values())
        }
"""
News Manager Module
뉴스 분석 시스템 통합 관리자
"""

import asyncio
import logging
import time
from typing import Dict, List, Optional, Any
from cachetools import TTLCache

from .news_fetcher import NewsFetcher
from .sentiment_analyzer import SentimentAnalyzer
from .news_filter import NewsFilter

# Import handling for both direct and package imports
try:
    from ...config.config import TradingConfig
    from ...database.db_manager import EnhancedDatabaseManager
    from ...utils.safe_data_handler import safe_handler
except ImportError:
    import sys
    import os
    sys.path.append(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
    from config.config import TradingConfig
    from database.db_manager import EnhancedDatabaseManager
    from utils.safe_data_handler import safe_handler


class NewsManager:
    """뉴스 분석 시스템 통합 관리자"""
    
    def __init__(self, config: TradingConfig, db: EnhancedDatabaseManager = None):
        self.config = config
        self.db = db
        self.logger = logging.getLogger(__name__)
        
        # 모듈 초기화
        self.fetcher = NewsFetcher(config)
        self.analyzer = SentimentAnalyzer(config)
        self.filter = NewsFilter(config)
        
        # 결과 캐시
        self._result_cache = TTLCache(maxsize=20, ttl=600)  # 10분 캐시
        
        # 검증 시스템
        self.verification_stats = {
            'total_analyses': 0,
            'successful_analyses': 0,
            'emergency_detections': 0,
            'false_alarms': 0,
            'avg_confidence': 0.0
        }
        
        # 비용 최적화
        self._last_analysis_time = 0
        
        # 검증 태스크
        self.verification_task = None
    
    async def initialize(self):
        """뉴스 분석 시스템 초기화"""
        try:
            # 검증 모니터링 태스크 시작
            self.verification_task = asyncio.create_task(self._verification_loop())
            self.logger.info("🔍 뉴스 분석 시스템 초기화 완료")
            return True
        except Exception as e:
            self.logger.error(f"❌ 뉴스 분석 시스템 초기화 실패: {e}")
            return False
    
    async def analyze_sentiment(self, symbol: Optional[str] = None) -> Dict[str, Any]:
        """통합 감성 분석 수행"""
        # 캐시 확인
        cache_key = f"news_analysis:{symbol or 'all'}"
        cached_result = self._result_cache.get(cache_key)
        if cached_result:
            return cached_result
        
        # 비용 최적화: 분석 간격 체크
        if self._should_skip_analysis():
            return self._get_cached_or_default_result(symbol)
        
        try:
            start_time = time.time()
            
            # 단계 1: 뉴스 수집
            self.logger.info(f"🔍 {symbol or '전체'} 뉴스 수집 시작")
            news_items = await self.fetcher.fetch_news(symbol)
            
            if not news_items:
                self.logger.info(f"📰 {symbol or '전체'} 수집된 뉴스 없음")
                result = self._get_default_sentiment()
                self._result_cache[cache_key] = result
                return result
            
            self.logger.info(f"📰 {symbol or '전체'} 뉴스 수집 완료: {len(news_items)}개")
            
            # 단계 2: 뉴스 필터링
            self.logger.debug(f"🧹 뉴스 필터링 시작 ({len(news_items)}개 -> 신뢰도 검증)")
            reliable_news = self.filter.filter_reliable_news(news_items)
            
            if not reliable_news:
                self.logger.warning(f"⚠️ 필터링 후 신뢰할 만한 뉴스가 없습니다 (원본: {len(news_items)}개)")
                result = self._get_default_sentiment()
                self._result_cache[cache_key] = result
                return result
            
            filtered_ratio = len(reliable_news) / len(news_items) * 100
            self.logger.info(f"✅ 뉴스 필터링 완료: {len(reliable_news)}개 선택 ({filtered_ratio:.1f}% 신뢰도)")
            
            # 단계 3: 긴급 상황 체크 (개선된 알고리즘)
            has_emergency, emergency_severity = self.filter.check_emergency_keywords(reliable_news)
            
            if has_emergency:
                self.logger.warning(f"🚨 긴급 뉴스 감지: 심각도 {emergency_severity}")
            else:
                self.logger.debug(f"✅ 긴급 상황 없음: 정상 분석 진행")
            
            # 단계 4: 감성 분석
            self.logger.info(f"💭 감성 분석 시작 ({len(reliable_news)}개 뉴스)")
            sentiment_result = await self.analyzer.analyze_sentiment(reliable_news, symbol)
            
            # 원시 감성 점수 로깅
            raw_sentiment = sentiment_result.get('sentiment_score', 0.0)
            self.logger.debug(f"📊 원시 감성 점수: {raw_sentiment:.3f}")
            
            # 단계 5: 결과 통합 및 조정
            final_result = self._integrate_analysis_results(
                sentiment_result, has_emergency, emergency_severity, reliable_news
            )
            
            # NEWS_WEIGHT 적용된 최종 점수 로깅
            final_sentiment = final_result.get('sentiment_score', 0.0)
            news_weight = self.config.NEWS_WEIGHT
            weighted_sentiment = final_sentiment * news_weight
            
            self.logger.info(f"📈 감성 분석 결과: 원시={raw_sentiment:.3f}, 최종={final_sentiment:.3f}")
            self.logger.info(f"⚖️ 가중치 적용: {final_sentiment:.3f} × {news_weight} = {weighted_sentiment:.3f}")
            
            # 가중치 적용된 점수를 결과에 추가
            final_result['weighted_sentiment'] = weighted_sentiment
            final_result['news_weight_applied'] = news_weight
            
            # 처리 시간 기록
            processing_time = time.time() - start_time
            final_result['processing_time'] = processing_time
            final_result['news_count'] = len(reliable_news)
            
            # 캐시 저장
            self._result_cache[cache_key] = final_result
            
            # 안전 처리된 결과로 통계 업데이트
            safe_result = safe_handler.ensure_analysis_result_keys(final_result)
            self._update_verification_stats(safe_result)
            
            # 분석 시간 업데이트
            self._last_analysis_time = time.time()
            
            self.logger.info(f"✅ {symbol or '전체'} 뉴스 분석 완료 ({processing_time:.1f}초)")
            return final_result
            
        except Exception as e:
            self.logger.error(f"뉴스 분석 중 오류: {e}")
            return self._get_default_sentiment()
    
    def _should_skip_analysis(self) -> bool:
        """분석을 건너뛸지 결정 (비용 최적화)"""
        if not (hasattr(self.config, 'ENABLE_COST_OPTIMIZATION') and self.config.ENABLE_COST_OPTIMIZATION):
            return False
        
        current_time = time.time()
        interval = getattr(self.config, 'NEWS_ANALYSIS_INTERVAL', 900)  # 기본 15분
        
        return (current_time - self._last_analysis_time) < interval
    
    def _get_cached_or_default_result(self, symbol: Optional[str]) -> Dict[str, Any]:
        """캐시된 결과 또는 기본값 반환"""
        # 최근 결과 찾기
        for cache_key in self._result_cache.keys():
            if symbol and symbol in cache_key:
                return self._result_cache[cache_key]
            elif not symbol and 'all' in cache_key:
                return self._result_cache[cache_key]
        
        return self._get_default_sentiment()
    
    def _integrate_analysis_results(
        self, 
        sentiment_result: Dict[str, Any], 
        has_emergency: bool, 
        emergency_severity: float,
        news_items: List[Dict[str, Any]]
    ) -> Dict[str, Any]:
        """분석 결과들을 통합하여 최종 결과 생성"""
        
        # 기본 감성 결과 복사
        result = sentiment_result.copy()
        
        # 긴급 상황 정보 추가
        result['emergency'] = {
            'detected': has_emergency,
            'severity': emergency_severity,
            'threshold': 1.2  # 현재 임계값
        }
        
        # 긴급 상황일 때 감성 점수 조정 (하지만 과민반응 방지)
        if has_emergency and emergency_severity >= 1.5:  # 더 높은 임계값
            # 감성 점수를 더 보수적으로 조정
            adjustment_factor = min(0.3, emergency_severity * 0.1)  # 최대 30% 조정
            
            if result['sentiment'] > 0:
                result['sentiment'] = max(0, result['sentiment'] - adjustment_factor)
            else:
                result['sentiment'] = min(0, result['sentiment'] - adjustment_factor)
            
            # 신뢰도 증가 (긴급 상황은 중요)
            result['confidence'] = min(1.0, result['confidence'] + 0.2)
            
            # 영향 수준 상향 조정
            if result['impact'] == 'low':
                result['impact'] = 'medium'
            elif result['impact'] == 'medium':
                result['impact'] = 'high'
        
        # 뉴스 메타데이터 추가
        result['news_metadata'] = {
            'total_sources': len(set(item.get('source', '') for item in news_items)),
            'avg_reliability': sum(item.get('source_reliability', 0.5) for item in news_items) / len(news_items),
            'time_range_hours': self._calculate_time_range(news_items),
            'top_sources': self._get_top_sources(news_items)
        }
        
        return result
    
    def _calculate_time_range(self, news_items: List[Dict[str, Any]]) -> float:
        """뉴스들의 시간 범위 계산 (시간 단위)"""
        if not news_items:
            return 0.0
        
        timestamps = [item.get('timestamp', time.time()) for item in news_items]
        return (max(timestamps) - min(timestamps)) / 3600.0  # 시간 단위로 변환
    
    def _get_top_sources(self, news_items: List[Dict[str, Any]]) -> List[str]:
        """주요 뉴스 소스 목록 반환"""
        source_counts = {}
        
        for item in news_items:
            source = item.get('source', 'Unknown')
            source_counts[source] = source_counts.get(source, 0) + 1
        
        # 빈도순으로 정렬하여 상위 3개 반환
        sorted_sources = sorted(source_counts.items(), key=lambda x: x[1], reverse=True)
        return [source for source, count in sorted_sources[:3]]
    
    def _get_default_sentiment(self) -> Dict[str, Any]:
        """기본 중성 감성 반환"""
        return {
            'sentiment': 0.0,
            'impact': 'low',
            'confidence': 0.1,
            'keywords': [],
            'summary': '분석 가능한 뉴스 없음',
            'analysis_type': 'default',
            'emergency': {'detected': False, 'severity': 0.0, 'threshold': 1.2},
            'news_metadata': {
                'total_sources': 0,
                'avg_reliability': 0.0,
                'time_range_hours': 0.0,
                'top_sources': []
            },
            'processing_time': 0.0,
            'news_count': 0
        }
    
    async def _verification_loop(self):
        """뉴스 분석 품질 검증 루프"""
        while True:
            try:
                await asyncio.sleep(3600)  # 1시간마다 검증
                
                # 분석 통계 수집
                stats = self.get_comprehensive_stats()
                
                if self.db:
                    await self._log_verification_results(stats)
                
                self.logger.info(f"📊 뉴스 분석 시스템 상태: 성공률 {stats['success_rate']:.1%}")
                
            except asyncio.CancelledError:
                break
            except Exception as e:
                self.logger.error(f"검증 루프 오류: {e}")
                await asyncio.sleep(300)  # 5분 후 재시도
    
    async def _log_verification_results(self, stats: Dict[str, Any]):
        """검증 결과 데이터베이스 저장"""
        try:
            if self.db:
                self.db.log_system_event(
                    level="INFO",
                    component="NewsAnalysis",
                    message="뉴스 분석 시스템 성능 리포트",
                    details=stats
                )
        except Exception as e:
            self.logger.debug(f"검증 결과 저장 실패: {e}")
    
    def _update_verification_stats(self, result: Dict[str, Any]):
        """검증 통계 업데이트 - SafeDataHandler 적용"""
        try:
            # 안전한 데이터 접근
            result = safe_handler.ensure_analysis_result_keys(result)
            
            self.verification_stats['total_analyses'] += 1
            
            if safe_handler.safe_get(result, 'confidence', 0) > 0.3:
                self.verification_stats['successful_analyses'] += 1
            
            if safe_handler.safe_get(result, 'emergency', {}).get('detected', False):
                self.verification_stats['emergency_detections'] += 1
            
            # 평균 신뢰도 업데이트 - KeyError 방지
            total = self.verification_stats['total_analyses']
            current_avg = safe_handler.safe_get(self.verification_stats, 'avg_confidence', 0.5)
            new_confidence = safe_handler.safe_get(result, 'avg_confidence', 0.5)
            
            self.verification_stats['avg_confidence'] = (
                (current_avg * (total - 1) + new_confidence) / total
            )
            
        except Exception as e:
            self.logger.debug(f"통계 업데이트 실패: {e}")
    
    def get_comprehensive_stats(self) -> Dict[str, Any]:
        """종합 통계 반환 - SafeDataHandler 적용"""
        total = max(self.verification_stats['total_analyses'], 1)
        
        stats = {
            'success_rate': self.verification_stats['successful_analyses'] / total,
            'avg_confidence': safe_handler.safe_get(self.verification_stats, 'avg_confidence', 0.5),
            'emergency_detection_rate': self.verification_stats['emergency_detections'] / total,
            'total_analyses': total,
            'fetcher_stats': self.fetcher.get_source_stats(),
            'analyzer_stats': self.analyzer.get_analysis_stats(),
            'filter_stats': self.filter.get_filter_stats(),
            'cache_hit_ratio': len(self._result_cache) / max(total, 1)
        }
        
        # 안전한 결과 키 보장
        return safe_handler.ensure_analysis_result_keys(stats)
    
    async def cleanup(self):
        """시스템 정리"""
        try:
            if self.verification_task:
                self.verification_task.cancel()
                try:
                    await self.verification_task
                except asyncio.CancelledError:
                    pass
            
            self.logger.info("뉴스 분석 시스템 정리 완료")
        except Exception as e:
            self.logger.error(f"시스템 정리 중 오류: {e}")
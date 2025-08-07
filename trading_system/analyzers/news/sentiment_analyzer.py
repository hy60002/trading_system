"""
Sentiment Analyzer Module
GPT 기반 감성 분석 전담 모듈
"""

import logging
import openai
import json
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


class SentimentAnalyzer:
    """GPT 기반 감성 분석 전담 클래스"""
    
    def __init__(self, config: TradingConfig):
        self.config = config
        self.logger = logging.getLogger(__name__)
        self.openai_client = openai.OpenAI(api_key=config.OPENAI_API_KEY) if config.OPENAI_API_KEY else None
        self._analysis_cache = TTLCache(maxsize=50, ttl=600)  # 10분 캐시
        
        # GPT 분석 품질 추적
        self.analysis_stats = {
            'gpt_analysis_success_rate': 0.0,
            'analysis_quality_scores': [],
            'fallback_usage_rate': 0.0
        }
    
    async def analyze_sentiment(self, news_items: List[Dict[str, Any]], symbol: Optional[str] = None) -> Dict[str, Any]:
        """뉴스 리스트의 감성 분석 수행"""
        if not news_items:
            return self._get_default_sentiment()
        
        # 캐시 확인
        cache_key = f"sentiment_analysis:{symbol or 'all'}:{hash(str([n['title'] for n in news_items]))}"
        cached_result = self._analysis_cache.get(cache_key)
        if cached_result:
            return cached_result
        
        try:
            # GPT 분석 시도
            if self.openai_client:
                analysis = await self._get_gpt_analysis(news_items, symbol)
                if analysis:
                    self._analysis_cache[cache_key] = analysis
                    return analysis
            
            # GPT 실패 시 폴백 분석
            fallback_analysis = self._get_fallback_analysis(news_items)
            self._analysis_cache[cache_key] = fallback_analysis
            return fallback_analysis
            
        except Exception as e:
            self.logger.error(f"감성 분석 중 오류: {e}")
            return self._get_default_sentiment()
    
    async def _get_gpt_analysis(self, news_items: List[Dict[str, Any]], symbol: Optional[str]) -> Optional[Dict[str, Any]]:
        """GPT를 사용한 고급 감성 분석"""
        try:
            # 뉴스 텍스트 준비
            news_text = self._prepare_news_text(news_items)
            
            # GPT 프롬프트 구성
            prompt = self._build_analysis_prompt(news_text, symbol)
            
            # GPT-3.5-turbo 사용 (비용 최적화)
            model = "gpt-3.5-turbo" if not self.config.USE_GPT_4 else "gpt-4"
            
            response = await self._call_openai_api(prompt, model)
            
            if response:
                analysis = self._parse_gpt_response(response)
                if analysis:
                    self._update_analysis_stats(True)
                    return analysis
            
            self._update_analysis_stats(False)
            return None
            
        except Exception as e:
            self.logger.error(f"GPT 분석 실패: {e}")
            self._update_analysis_stats(False)
            return None
    
    async def _call_openai_api(self, prompt: str, model: str) -> Optional[str]:
        """OpenAI API 호출"""
        try:
            response = self.openai_client.chat.completions.create(
                model=model,
                messages=[
                    {"role": "system", "content": "You are a professional cryptocurrency market analyst."},
                    {"role": "user", "content": prompt}
                ],
                max_tokens=300,
                temperature=0.3,
                timeout=30
            )
            
            return response.choices[0].message.content.strip()
            
        except Exception as e:
            if 'rate limit' in str(e).lower():
                self.logger.error("OpenAI API 요청 한도 초과")
            elif 'api key' in str(e).lower():
                self.logger.error("OpenAI API 키 문제")
            elif 'timeout' in str(e).lower():
                self.logger.error("OpenAI API 응답 시간 초과")
            else:
                self.logger.error(f"OpenAI API 호출 실패: {e}")
            raise
    
    def _prepare_news_text(self, news_items: List[Dict[str, Any]]) -> str:
        """GPT 분석을 위한 뉴스 텍스트 준비"""
        # 신뢰도가 높은 뉴스 우선
        sorted_news = sorted(news_items, key=lambda x: x.get('source_reliability', 0.5), reverse=True)
        
        # 최대 5개 뉴스만 사용 (토큰 제한)
        selected_news = sorted_news[:5]
        
        news_text = ""
        for i, item in enumerate(selected_news, 1):
            title = item.get('title', '')
            description = item.get('description', '')
            source = item.get('source', '')
            reliability = item.get('source_reliability', 0.5)
            
            news_text += f"{i}. [{source} (신뢰도: {reliability:.1f})] {title}\\n"
            if description and len(description) < 200:
                news_text += f"   {description}\\n"
            news_text += "\\n"
        
        return news_text
    
    def _build_analysis_prompt(self, news_text: str, symbol: Optional[str]) -> str:
        """GPT 분석 프롬프트 구성"""
        symbol_name = {
            'BTCUSDT': 'Bitcoin (BTC)',
            'ETHUSDT': 'Ethereum (ETH)',
            'XRPUSDT': 'Ripple (XRP)'
        }.get(symbol, '암호화폐')
        
        return f"""
다음 {symbol_name} 관련 뉴스들을 분석하고 JSON 형태로 결과를 반환해주세요:

{news_text}

분석 기준:
1. 전체적인 시장 감성 (-1.0 ~ +1.0)
2. 영향 수준 (low/medium/high)  
3. 신뢰도 (0.0 ~ 1.0)
4. 주요 키워드 (최대 5개)
5. 간단한 요약 (50자 이내)

응답 형식:
{{
    "sentiment": <숫자>,
    "impact": "<문자열>",
    "confidence": <숫자>,
    "keywords": [<문자열 배열>],
    "summary": "<문자열>"
}}

중요: 반드시 유효한 JSON 형태로만 응답하세요.
"""
    
    def _parse_gpt_response(self, response: str) -> Optional[Dict[str, Any]]:
        """GPT 응답 파싱"""
        try:
            # JSON 추출 시도
            response = response.strip()
            
            # JSON 시작/끝 찾기
            start = response.find('{')
            end = response.rfind('}') + 1
            
            if start >= 0 and end > start:
                json_str = response[start:end]
                data = json.loads(json_str)
                
                # 데이터 검증 및 정규화
                sentiment = float(data.get('sentiment', 0.0))
                sentiment = max(-1.0, min(1.0, sentiment))  # -1.0 ~ 1.0 범위 제한
                
                impact = data.get('impact', 'medium').lower()
                if impact not in ['low', 'medium', 'high']:
                    impact = 'medium'
                
                confidence = float(data.get('confidence', 0.5))
                confidence = max(0.0, min(1.0, confidence))  # 0.0 ~ 1.0 범위 제한
                
                keywords = data.get('keywords', [])
                if not isinstance(keywords, list):
                    keywords = []
                keywords = keywords[:5]  # 최대 5개
                
                summary = str(data.get('summary', ''))[:100]  # 최대 100자
                
                return {
                    'sentiment': sentiment,
                    'impact': impact,
                    'confidence': confidence,
                    'keywords': keywords,
                    'summary': summary,
                    'analysis_type': 'gpt'
                }
            
            return None
            
        except Exception as e:
            self.logger.debug(f"GPT 응답 파싱 실패: {e}")
            return None
    
    def _get_fallback_analysis(self, news_items: List[Dict[str, Any]]) -> Dict[str, Any]:
        """GPT 실패 시 간단한 키워드 기반 분석"""
        try:
            # 키워드 기반 감성 스코어 계산
            positive_keywords = ['bull', 'up', 'rise', 'gain', 'positive', 'buy', 'adoption', 'growth']
            negative_keywords = ['bear', 'down', 'fall', 'loss', 'negative', 'sell', 'crash', 'drop']
            
            total_score = 0.0
            total_weight = 0.0
            
            for item in news_items:
                content = (item.get('title', '') + ' ' + item.get('description', '')).lower()
                weight = item.get('source_reliability', 0.5)
                
                score = 0.0
                for keyword in positive_keywords:
                    score += content.count(keyword) * 0.1
                for keyword in negative_keywords:
                    score -= content.count(keyword) * 0.1
                
                total_score += score * weight
                total_weight += weight
            
            # 평균 감성 스코어 계산
            avg_sentiment = total_score / max(total_weight, 1.0)
            avg_sentiment = max(-1.0, min(1.0, avg_sentiment))
            
            # 영향 수준 결정
            if abs(avg_sentiment) > 0.5:
                impact = 'high'
            elif abs(avg_sentiment) > 0.2:
                impact = 'medium'  
            else:
                impact = 'low'
            
            return {
                'sentiment': avg_sentiment,
                'impact': impact,
                'confidence': 0.4,  # 폴백 분석은 낮은 신뢰도
                'keywords': [],
                'summary': f'키워드 기반 분석: {len(news_items)}개 뉴스',
                'analysis_type': 'fallback'
            }
            
        except Exception as e:
            self.logger.error(f"폴백 분석 실패: {e}")
            return self._get_default_sentiment()
    
    def _get_default_sentiment(self) -> Dict[str, Any]:
        """기본 중립 감성 반환"""
        return {
            'sentiment': 0.0,
            'impact': 'low',
            'confidence': 0.1,
            'keywords': [],
            'summary': '분석 데이터 없음',
            'analysis_type': 'default'
        }
    
    def _update_analysis_stats(self, success: bool):
        """분석 통계 업데이트"""
        try:
            if not hasattr(self, '_total_analyses'):
                self._total_analyses = 0
                self._successful_analyses = 0
            
            self._total_analyses += 1
            if success:
                self._successful_analyses += 1
            
            self.analysis_stats['gpt_analysis_success_rate'] = (
                self._successful_analyses / self._total_analyses if self._total_analyses > 0 else 0.0
            )
            
        except Exception as e:
            self.logger.debug(f"통계 업데이트 실패: {e}")
    
    def get_analysis_stats(self) -> Dict[str, Any]:
        """분석 통계 반환"""
        return self.analysis_stats.copy()
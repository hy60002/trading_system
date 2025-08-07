"""
GPT Analyzer
GPT-based market analysis
"""

import asyncio
import logging
from typing import Dict

# OpenAI import handling
try:
    import openai
    OPENAI_AVAILABLE = True
except ImportError:
    OPENAI_AVAILABLE = False

# Import handling for both direct and package imports
try:
    from ..config.config import TradingConfig
except ImportError:
    import sys
    import os
    sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    from config.config import TradingConfig


class GPTAnalyzer:
    """GPT-based market analysis"""
    
    def __init__(self, config: TradingConfig, logger=None):
        self.config = config
        self.logger = logger or logging.getLogger(__name__)
        self.openai_client = None
        
        if not OPENAI_AVAILABLE:
            self.logger.warning("OpenAI 라이브러리가 설치되지 않았습니다. GPT 분석을 비활성화합니다.")
            return
        
        if config.OPENAI_API_KEY:
            try:
                self.openai_client = openai.OpenAI(api_key=config.OPENAI_API_KEY)
                self.logger.info("GPT 분석기 초기화 완료")
            except Exception as e:
                self.logger.warning(f"OpenAI 초기화 실패: {e}")
    
    async def analyze_market(self, symbol: str, data: Dict) -> Dict:
        """Market analysis using GPT"""
        if not self.openai_client:
            return {
                "analysis": "GPT를 사용할 수 없습니다",
                "confidence": 0.0,
                "direction": "neutral",
                "reasoning": "OpenAI API 키가 설정되지 않았거나 라이브러리가 없습니다"
            }
        
        # 비용 최적화: 분석 간격 체크
        if hasattr(self.config, 'ENABLE_COST_OPTIMIZATION') and self.config.ENABLE_COST_OPTIMIZATION:
            import time
            current_time = time.time()
            last_analysis_time = getattr(self, '_last_technical_analysis_time', 0)
            if current_time - last_analysis_time < self.config.TECHNICAL_ANALYSIS_INTERVAL:
                # 이전 결과 반환 (캐시된 결과가 없으면 기본값)
                return {
                    "analysis": "분석 대기 중 (비용 최적화)",
                    "confidence": 0.5,
                    "direction": "neutral",
                    "reasoning": "15분 간격 분석 적용 중"
                }
            self._last_technical_analysis_time = current_time
        
        try:
            # Prepare market data summary
            data_summary = self._prepare_data_summary(symbol, data)
            
            prompt = f"""
암호화폐 시장 데이터를 분석하고 거래 방향을 제안해주세요.

심볼: {symbol}
{data_summary}

다음 형식으로 분석을 제공해주세요:
1. 시장 분석 (2-3줄 요약)
2. 거래 방향: buy/sell/hold
3. 신뢰도: 0.0-1.0
4. 핵심 근거 (간단히)

간결하고 실용적인 분석을 제공해주세요.
            """
            
            # Get GPT analysis
            response = await asyncio.get_event_loop().run_in_executor(
                None,
                lambda: self.openai_client.chat.completions.create(
                    model="gpt-4" if self.config.USE_GPT_4 else "gpt-3.5-turbo",
                    messages=[
                        {"role": "system", "content": "당신은 전문 암호화폐 트레이더입니다. 기술적 분석을 바탕으로 간결하고 정확한 거래 조언을 제공합니다."},
                        {"role": "user", "content": prompt}
                    ],
                    temperature=0.3,
                    max_tokens=300
                )
            )
            
            # Parse response
            analysis_text = response.choices[0].message.content
            parsed_result = self._parse_gpt_response(analysis_text)
            
            return {
                "analysis": parsed_result.get('analysis', analysis_text),
                "confidence": parsed_result.get('confidence', 0.5),
                "direction": parsed_result.get('direction', 'neutral'),
                "reasoning": parsed_result.get('reasoning', ''),
                "raw_response": analysis_text
            }
            
        except Exception as e:
            self.logger.error(f"GPT 분석 오류: {e}")
            return {
                "analysis": "분석 실패",
                "confidence": 0.0,
                "direction": "neutral",
                "reasoning": f"오류: {str(e)}"
            }
    
    def _prepare_data_summary(self, symbol: str, data: Dict) -> str:
        """Prepare data summary for GPT analysis"""
        summary_parts = []
        
        # Price information
        if 'current_price' in data:
            summary_parts.append(f"현재 가격: ${data['current_price']:,.2f}")
        
        # Technical indicators
        if 'indicators' in data:
            indicators = data['indicators']
            if 'rsi' in indicators:
                summary_parts.append(f"RSI: {indicators['rsi']:.1f}")
            if 'macd_signal' in indicators:
                summary_parts.append(f"MACD 신호: {'상승' if indicators['macd_signal'] > 0 else '하락'}")
            if 'bb_position' in indicators:
                if indicators['bb_position'] > 0.8:
                    summary_parts.append("볼린저 밴드: 상단 근처")
                elif indicators['bb_position'] < 0.2:
                    summary_parts.append("볼린저 밴드: 하단 근처")
                else:
                    summary_parts.append("볼린저 밴드: 중간")
        
        # Trend information
        if 'trend' in data:
            trend = data['trend']
            if isinstance(trend, dict):
                direction = trend.get('direction', 'neutral')
                strength = trend.get('strength', 0)
                summary_parts.append(f"추세: {direction} (강도: {strength:.2f})")
            else:
                summary_parts.append(f"추세: {trend}")
        
        # Volume
        if 'volume_ratio' in data:
            volume_ratio = data['volume_ratio']
            if volume_ratio > 1.5:
                summary_parts.append("거래량: 평균 대비 높음")
            elif volume_ratio < 0.7:
                summary_parts.append("거래량: 평균 대비 낮음")
            else:
                summary_parts.append("거래량: 평균 수준")
        
        # News sentiment
        if 'news_sentiment' in data:
            sentiment = data['news_sentiment']
            if isinstance(sentiment, dict):
                sentiment_score = sentiment.get('sentiment', 0)
                if sentiment_score > 0.3:
                    summary_parts.append("뉴스 감성: 긍정적")
                elif sentiment_score < -0.3:
                    summary_parts.append("뉴스 감성: 부정적")
                else:
                    summary_parts.append("뉴스 감성: 중립적")
        
        return "\n".join(summary_parts) if summary_parts else "데이터 없음"
    
    def _parse_gpt_response(self, response_text: str) -> Dict:
        """Parse GPT response text"""
        result = {
            'analysis': '',
            'direction': 'neutral',
            'confidence': 0.5,
            'reasoning': ''
        }
        
        lines = response_text.split('\n')
        
        for line in lines:
            line = line.strip()
            if not line:
                continue
            
            # Extract direction
            if '거래 방향' in line or 'direction' in line.lower():
                if 'buy' in line.lower() or '매수' in line or '상승' in line:
                    result['direction'] = 'buy'
                elif 'sell' in line.lower() or '매도' in line or '하락' in line:
                    result['direction'] = 'sell'
                elif 'hold' in line.lower() or '보유' in line or '중립' in line:
                    result['direction'] = 'hold'
            
            # Extract confidence
            if '신뢰도' in line or 'confidence' in line.lower():
                import re
                numbers = re.findall(r'0\.\d+|\d+\.\d+', line)
                if numbers:
                    try:
                        confidence = float(numbers[0])
                        if confidence > 1:
                            confidence = confidence / 100  # Convert percentage
                        result['confidence'] = min(max(confidence, 0.0), 1.0)
                    except ValueError:
                        pass
            
            # Extract analysis (first substantial line)
            if not result['analysis'] and len(line) > 20 and not any(keyword in line for keyword in ['거래 방향', '신뢰도', 'direction', 'confidence']):
                result['analysis'] = line
            
            # Extract reasoning
            if '근거' in line or 'reasoning' in line.lower() or '이유' in line:
                result['reasoning'] = line
        
        # Fallback for analysis
        if not result['analysis']:
            result['analysis'] = response_text[:100] + "..." if len(response_text) > 100 else response_text
        
        return result
    
    def analyze_news_impact(self, symbol: str, news_items: list) -> Dict:
        """Analyze impact of news on symbol price"""
        if not self.openai_client or not news_items:
            return {
                "impact": "neutral",
                "confidence": 0.0,
                "summary": "분석 불가"
            }
        
        try:
            # Prepare news summary
            news_text = "\n".join([f"- {item.get('title', '')}" for item in news_items[:5]])
            
            prompt = f"""
{symbol}에 대한 다음 뉴스들이 가격에 미칠 영향을 분석해주세요:

{news_text}

영향도를 다음 중 하나로 분류해주세요:
- positive: 가격 상승 요인
- negative: 가격 하락 요인  
- neutral: 중립적 영향

신뢰도 (0.0-1.0)와 간단한 근거도 제공해주세요.
            """
            
            # This would be implemented similar to analyze_market
            # For now, return a basic structure
            return {
                "impact": "neutral",
                "confidence": 0.5,
                "summary": "뉴스 영향 분석 준비 중"
            }
            
        except Exception as e:
            self.logger.error(f"뉴스 영향 분석 오류: {e}")
            return {
                "impact": "neutral", 
                "confidence": 0.0,
                "summary": f"분석 실패: {str(e)}"
            }
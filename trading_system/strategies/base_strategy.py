"""
Base Trading Strategy
추상 기본 클래스 - 모든 거래 전략의 공통 인터페이스 정의
"""

import logging
from abc import ABC, abstractmethod
from typing import Dict, Optional, Any
import pandas as pd
import numpy as np


class BaseTradingStrategy(ABC):
    """모든 거래 전략의 기본 클래스"""
    
    def __init__(self, config):
        self.config = config
        self.logger = logging.getLogger(self.__class__.__name__)
        
        # 기본 파라미터
        self.signal_threshold = 0.3
        self.min_confidence = 50
        self.stop_loss_pct = 0.02
        self.take_profit_pct = 0.04
        
    @abstractmethod
    async def analyze(self, symbol: str, df: pd.DataFrame, indicators: Dict) -> Dict:
        """
        시장 분석을 수행하고 거래 신호를 생성
        
        Args:
            symbol: 거래 심볼 (예: 'BTCUSDT')
            df: OHLCV 데이터
            indicators: 기술적 지표 딕셔너리
            
        Returns:
            Dict: 분석 결과 포함
                - direction: 'long', 'short', 'neutral'
                - score: -1.0 ~ 1.0 신호 강도
                - confidence: 0 ~ 100 신뢰도
                - signals: 개별 신호 목록
        """
        pass
    
    async def analyze_market(self, symbol: str, df: pd.DataFrame, indicators: Dict) -> Dict:
        """
        analyze() 메서드의 래퍼 - 엔진 호환성을 위함
        """
        return await self.analyze(symbol, df, indicators)
    
    @abstractmethod
    def generate_signal(self, symbol: str, df: pd.DataFrame, indicators: Dict) -> Dict:
        """
        거래 신호 생성
        
        Returns:
            Dict: 거래 신호
                - action: 'buy', 'sell', 'hold'
                - strength: 0.0 ~ 1.0
                - stop_loss: 손절가
                - take_profit: 익절가
        """
        pass
    
    def should_buy(self, analysis_result: Dict) -> bool:
        """매수 조건 확인"""
        return (
            analysis_result.get('direction') == 'long' and
            analysis_result.get('score', 0) > self.signal_threshold and
            analysis_result.get('confidence', 0) >= self.min_confidence
        )
    
    def should_sell(self, analysis_result: Dict) -> bool:
        """매도 조건 확인"""
        return (
            analysis_result.get('direction') == 'short' and
            analysis_result.get('score', 0) < -self.signal_threshold and
            analysis_result.get('confidence', 0) >= self.min_confidence
        )
    
    def calculate_position_size(self, capital: float, price: float, 
                              risk_pct: float = 0.01) -> float:
        """포지션 크기 계산"""
        risk_amount = capital * risk_pct
        position_value = capital * 0.1  # 기본 10% 할당
        return min(position_value / price, risk_amount / (price * self.stop_loss_pct))
    
    def get_stop_loss_price(self, entry_price: float, direction: str) -> float:
        """손절가 계산"""
        if direction == 'long':
            return entry_price * (1 - self.stop_loss_pct)
        else:
            return entry_price * (1 + self.stop_loss_pct)
    
    def get_take_profit_price(self, entry_price: float, direction: str) -> float:
        """익절가 계산"""
        if direction == 'long':
            return entry_price * (1 + self.take_profit_pct)
        else:
            return entry_price * (1 - self.take_profit_pct)
    
    def validate_analysis_result(self, result: Dict) -> bool:
        """분석 결과 검증"""
        required_keys = ['direction', 'score', 'confidence']
        
        for key in required_keys:
            if key not in result:
                self.logger.error(f"분석 결과에 필수 키 '{key}' 누락")
                return False
        
        # 값 범위 검증
        if result['direction'] not in ['long', 'short', 'neutral']:
            return False
        
        if not (-1.0 <= result['score'] <= 1.0):
            return False
        
        if not (0 <= result['confidence'] <= 100):
            return False
        
        return True
    
    def format_analysis_summary(self, result: Dict) -> str:
        """분석 결과 요약 포맷"""
        return (
            f"방향: {result.get('direction', 'N/A')}, "
            f"점수: {result.get('score', 0):.3f}, "
            f"신뢰도: {result.get('confidence', 0):.1f}%"
        )


class TrendFollowingMixin:
    """트렌드 추종 전략용 믹스인"""
    
    def detect_trend(self, df: pd.DataFrame, indicators: Dict) -> Dict:
        """트렌드 감지"""
        # EMA 기반 트렌드
        ema_20 = indicators.get('ema_20')
        ema_50 = indicators.get('ema_50')
        
        if ema_20 is None or ema_50 is None or len(ema_20) < 10:
            return {'trend': 'neutral', 'strength': 0}
        
        current_20 = ema_20.iloc[-1]
        current_50 = ema_50.iloc[-1]
        
        # 트렌드 방향
        if current_20 > current_50:
            trend = 'up'
            strength = min(1.0, (current_20 - current_50) / current_50)
        elif current_20 < current_50:
            trend = 'down'
            strength = min(1.0, (current_50 - current_20) / current_50)
        else:
            trend = 'neutral'
            strength = 0
        
        return {
            'trend': trend,
            'strength': abs(strength),
            'ema_20': current_20,
            'ema_50': current_50
        }


class MomentumMixin:
    """모멘텀 기반 분석 믹스인"""
    
    def analyze_momentum(self, df: pd.DataFrame, indicators: Dict) -> Dict:
        """모멘텀 분석"""
        rsi = indicators.get('rsi')
        macd = indicators.get('macd')
        macd_signal = indicators.get('macd_signal')
        
        momentum_signals = []
        momentum_score = 0
        
        # RSI 분석
        if rsi is not None and len(rsi) > 0:
            current_rsi = rsi.iloc[-1]
            
            if current_rsi > 70:
                momentum_signals.append({'type': 'rsi', 'signal': 'overbought', 'value': current_rsi})
                momentum_score -= 0.3
            elif current_rsi < 30:
                momentum_signals.append({'type': 'rsi', 'signal': 'oversold', 'value': current_rsi})
                momentum_score += 0.3
        
        # MACD 분석
        if macd is not None and macd_signal is not None and len(macd) > 1:
            current_macd = macd.iloc[-1]
            current_signal = macd_signal.iloc[-1]
            prev_macd = macd.iloc[-2]
            prev_signal = macd_signal.iloc[-2]
            
            # MACD 크로스오버
            if prev_macd <= prev_signal and current_macd > current_signal:
                momentum_signals.append({'type': 'macd', 'signal': 'bullish_crossover'})
                momentum_score += 0.4
            elif prev_macd >= prev_signal and current_macd < current_signal:
                momentum_signals.append({'type': 'macd', 'signal': 'bearish_crossover'})
                momentum_score -= 0.4
        
        return {
            'momentum_score': np.clip(momentum_score, -1, 1),
            'signals': momentum_signals,
            'rsi_level': rsi.iloc[-1] if rsi is not None and len(rsi) > 0 else None,
            'macd_histogram': (macd.iloc[-1] - macd_signal.iloc[-1]) if macd is not None and macd_signal is not None and len(macd) > 0 else None
        }


class VolumeMixin:
    """볼륨 분석 믹스인"""
    
    def analyze_volume(self, df: pd.DataFrame, indicators: Dict) -> Dict:
        """볼륨 분석"""
        volume_ratio = indicators.get('volume_ratio', pd.Series([1.0]))
        obv = indicators.get('obv')
        
        volume_signals = []
        volume_score = 0
        
        # 볼륨 비율 분석
        if len(volume_ratio) > 0:
            current_volume_ratio = volume_ratio.iloc[-1]
            
            if current_volume_ratio > 1.5:
                volume_signals.append({'type': 'volume_spike', 'ratio': current_volume_ratio})
                volume_score += 0.2
            elif current_volume_ratio < 0.5:
                volume_signals.append({'type': 'volume_low', 'ratio': current_volume_ratio})
                volume_score -= 0.1
        
        # OBV 트렌드
        if obv is not None and len(obv) >= 5:
            recent_obv = obv.iloc[-5:].values
            if len(recent_obv) >= 5:
                obv_trend = np.polyfit(range(5), recent_obv, 1)[0]
                
                if obv_trend > 0:
                    volume_signals.append({'type': 'obv', 'signal': 'accumulation'})
                    volume_score += 0.15
                elif obv_trend < 0:
                    volume_signals.append({'type': 'obv', 'signal': 'distribution'})
                    volume_score -= 0.15
        
        return {
            'volume_score': np.clip(volume_score, -1, 1),
            'signals': volume_signals,
            'current_volume_ratio': volume_ratio.iloc[-1] if len(volume_ratio) > 0 else 1.0
        }


# 편의를 위한 베이스 클래스들
class TrendStrategy(BaseTradingStrategy, TrendFollowingMixin):
    """트렌드 추종 전략 베이스"""
    pass


class MomentumStrategy(BaseTradingStrategy, MomentumMixin):
    """모멘텀 전략 베이스"""
    pass


class ComprehensiveStrategy(BaseTradingStrategy, TrendFollowingMixin, MomentumMixin, VolumeMixin):
    """종합 전략 베이스 - 모든 분석 기법 포함"""
    pass


print('BaseTradingStrategy.py loaded - Abstract base class + mixins')
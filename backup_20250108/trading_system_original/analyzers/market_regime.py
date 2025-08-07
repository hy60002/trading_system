"""
Market Regime Analyzer
Enhanced market regime detection with ML integration
"""

import logging
import numpy as np
import pandas as pd
from typing import Dict
from cachetools import TTLCache


class MarketRegimeAnalyzer:
    """Enhanced market regime detection with ML integration"""
    
    def __init__(self):
        self.regimes = ['trending_up', 'trending_down', 'ranging', 'volatile']
        self.logger = logging.getLogger(__name__)
        self._regime_cache = TTLCache(maxsize=100, ttl=300)
    
    def analyze_regime(self, df: pd.DataFrame, indicators: Dict) -> Dict:
        """Analyze current market regime with caching"""
        # Create cache key from recent price data
        cache_key = f"regime:{df.index[-1]}:{df['close'].iloc[-1]}"
        cached_result = self._regime_cache.get(cache_key)
        if cached_result:
            return cached_result
        
        # Price position analysis
        price_score = self._analyze_price_position(df, indicators)
        
        # Momentum analysis
        momentum_score = self._analyze_momentum(indicators)
        
        # Trend strength
        trend_strength = self._analyze_trend_strength(indicators)
        
        # Volatility analysis
        volatility_score = self._analyze_volatility(df, indicators)
        
        # Volume profile
        volume_score = self._analyze_volume_profile(df, indicators)
        
        # Determine regime
        regime = self._determine_regime(
            price_score, momentum_score, trend_strength, volatility_score, volume_score
        )
        
        # Calculate confidence
        confidence = self._calculate_confidence(
            price_score, momentum_score, trend_strength, volatility_score
        )
        
        # Get regime-specific parameters
        regime_params = self._get_regime_parameters(regime, volatility_score)
        
        result = {
            'regime': regime,
            'confidence': confidence,
            'characteristics': self._get_regime_characteristics(regime),
            'parameters': regime_params,
            'scores': {
                'price': price_score,
                'momentum': momentum_score,
                'trend': trend_strength,
                'volatility': volatility_score,
                'volume': volume_score
            }
        }
        
        # Cache result
        self._regime_cache[cache_key] = result
        
        return result
    
    def _analyze_price_position(self, df: pd.DataFrame, indicators: Dict) -> float:
        """Analyze price position relative to key levels"""
        score = 0
        current_price = df['close'].iloc[-1]
        
        # Position relative to EMAs
        weights = {'ema_20': 0.3, 'ema_50': 0.25, 'sma_200': 0.2}
        for ma, weight in weights.items():
            if ma in indicators and not indicators[ma].empty:
                if current_price > indicators[ma].iloc[-1]:
                    score += weight
                else:
                    score -= weight
        
        # EMA alignment
        if (indicators['ema_20'].iloc[-1] > indicators['ema_50'].iloc[-1] > indicators.get('sma_200', indicators['ema_50']).iloc[-1]):
            score += 0.25
        elif (indicators['ema_20'].iloc[-1] < indicators['ema_50'].iloc[-1] < indicators.get('sma_200', indicators['ema_50']).iloc[-1]):
            score -= 0.25
        
        return np.clip(score, -1, 1)
    
    def _analyze_momentum(self, indicators: Dict) -> float:
        """Analyze momentum indicators"""
        score = 0
        
        # RSI
        rsi = indicators['rsi'].iloc[-1]
        if rsi > 70:
            score -= 0.3  # Overbought
        elif rsi > 50:
            score += 0.2
        elif rsi < 30:
            score += 0.3  # Oversold bounce potential
        else:
            score -= 0.2
        
        # MACD
        if indicators['macd'].iloc[-1] > indicators['macd_signal'].iloc[-1]:
            score += 0.3
            # MACD histogram momentum
            if indicators['macd_hist'].iloc[-1] > indicators['macd_hist'].iloc[-2]:
                score += 0.2
        else:
            score -= 0.3
            if indicators['macd_hist'].iloc[-1] < indicators['macd_hist'].iloc[-2]:
                score -= 0.2
        
        # MFI
        if 'mfi' in indicators:
            mfi = indicators['mfi'].iloc[-1]
            if mfi > 80:
                score -= 0.2
            elif mfi < 20:
                score += 0.2
        
        return np.clip(score, -1, 1)
    
    def _analyze_trend_strength(self, indicators: Dict) -> float:
        """Analyze trend strength using multiple indicators"""
        components = []
        
        # ADX
        adx = indicators['adx'].iloc[-1]
        if adx > 40:
            adx_score = 1.0
        elif adx > 25:
            adx_score = 0.7
        elif adx > 20:
            adx_score = 0.4
        else:
            adx_score = 0.2
        components.append(adx_score * 0.4)
        
        # Directional movement
        if indicators['plus_di'].iloc[-1] > indicators['minus_di'].iloc[-1]:
            di_score = min((indicators['plus_di'].iloc[-1] - indicators['minus_di'].iloc[-1]) / 50, 1)
        else:
            di_score = -min((indicators['minus_di'].iloc[-1] - indicators['plus_di'].iloc[-1]) / 50, 1)
        components.append(di_score * 0.3)
        
        # Supertrend
        if 'supertrend_direction' in indicators:
            st_direction = indicators['supertrend_direction'].iloc[-1]
            components.append(st_direction * 0.3)
        
        return np.clip(sum(components), -1, 1)
    
    def _analyze_volatility(self, df: pd.DataFrame, indicators: Dict) -> float:
        """Analyze market volatility"""
        # ATR ratio
        atr = indicators['atr'].iloc[-1]
        price = df['close'].iloc[-1]
        atr_ratio = atr / price
        
        # Historical comparison
        atr_sma = indicators['atr'].rolling(50).mean().iloc[-1]
        current_vs_historical = atr / atr_sma if atr_sma > 0 else 1
        
        # Bollinger Band width
        bb_width = (indicators['bb_upper'].iloc[-1] - indicators['bb_lower'].iloc[-1]) / indicators['bb_middle'].iloc[-1]
        bb_width_sma = ((indicators['bb_upper'] - indicators['bb_lower']) / indicators['bb_middle']).rolling(20).mean().iloc[-1]
        bb_squeeze = bb_width / bb_width_sma if bb_width_sma > 0 else 1
        
        # Calculate volatility score
        if current_vs_historical > 2:
            vol_score = 1.0
        elif current_vs_historical > 1.5:
            vol_score = 0.7
        elif current_vs_historical > 1.2:
            vol_score = 0.5
        elif bb_squeeze < 0.7:  # Bollinger squeeze
            vol_score = 0.3
        else:
            vol_score = 0.4
        
        return vol_score
    
    def _analyze_volume_profile(self, df: pd.DataFrame, indicators: Dict) -> float:
        """Analyze volume patterns"""
        score = 0
        
        # Volume trend
        recent_volume = df['volume'].iloc[-5:].mean()
        avg_volume = indicators['volume_sma'].iloc[-1]
        
        if recent_volume > avg_volume * 1.5:
            # High volume
            if df['close'].iloc[-1] > df['close'].iloc[-5]:
                score += 0.5  # Bullish volume
            else:
                score -= 0.5  # Bearish volume
        
        # OBV trend
        try:
            if 'obv' in indicators and len(indicators['obv']) > 20:
                obv_values = indicators['obv'].iloc[-20:].values
                if len(obv_values) >= 20:
                    obv_slope = np.polyfit(range(20), obv_values, 1)[0]
                    if obv_slope > 0:
                        score += 0.3
                    else:
                        score -= 0.3
        except Exception as e:
            # If OBV analysis fails, continue without it
            pass
        
        # Volume ratio consistency
        vol_ratios = indicators.get('volume_ratio', pd.Series())
        if not vol_ratios.empty:
            vol_consistency = vol_ratios.iloc[-10:].std()
            if vol_consistency < 0.5:  # Consistent volume
                score *= 0.8  # Reduce score magnitude
        
        return np.clip(score, -1, 1)
    
    def _determine_regime(self, price: float, momentum: float, trend: float, 
                         volatility: float, volume: float) -> str:
        """Determine market regime based on scores"""
        # Strong trend detection
        if trend > 0.6:
            if price > 0.4 and momentum > 0:
                return 'trending_up'
            elif price < -0.4 and momentum < 0:
                return 'trending_down'
        
        # High volatility overrides other signals
        if volatility > 0.7:
            return 'volatile'
        
        # Weak trend with momentum
        if abs(trend) < 0.4:
            if abs(price) < 0.3:
                return 'ranging'
        
        # Default based on price and momentum
        combined_score = (price + momentum) / 2
        if combined_score > 0.3:
            return 'trending_up'
        elif combined_score < -0.3:
            return 'trending_down'
        
        return 'ranging'
    
    def _calculate_confidence(self, price: float, momentum: float,
                            trend: float, volatility: float) -> float:
        """Calculate regime confidence"""
        # Base confidence on consistency of signals
        scores = [price, momentum, trend]
        
        # Check alignment
        aligned_positive = sum(1 for s in scores if s > 0.3)
        aligned_negative = sum(1 for s in scores if s < -0.3)
        
        if aligned_positive >= 3 or aligned_negative >= 3:
            base_confidence = 85
        elif aligned_positive >= 2 or aligned_negative >= 2:
            base_confidence = 70
        else:
            base_confidence = 50
        
        # Adjust for trend strength
        base_confidence += abs(trend) * 15
        
        # Reduce for high volatility
        if volatility > 0.8:
            base_confidence *= 0.8
        elif volatility > 0.6:
            base_confidence *= 0.9
        
        return min(95, max(20, base_confidence))
    
    def _get_regime_parameters(self, regime: str, volatility: float) -> Dict:
        """Get regime-specific trading parameters"""
        params = {
            'trending_up': {
                'position_size_multiplier': 1.2,
                'stop_loss_multiplier': 0.9,
                'take_profit_multiplier': 1.1,
                'max_positions': 3,
                'preferred_timeframes': ['4h', '1h'],
                'signal_threshold_multiplier': 0.9
            },
            'trending_down': {
                'position_size_multiplier': 0.8,
                'stop_loss_multiplier': 0.8,
                'take_profit_multiplier': 1.0,
                'max_positions': 1,
                'preferred_timeframes': ['1h', '30m'],
                'signal_threshold_multiplier': 1.1
            },
            'ranging': {
                'position_size_multiplier': 1.0,
                'stop_loss_multiplier': 1.0,
                'take_profit_multiplier': 0.8,
                'max_positions': 2,
                'preferred_timeframes': ['30m', '15m'],
                'signal_threshold_multiplier': 1.0
            },
            'volatile': {
                'position_size_multiplier': 0.6,
                'stop_loss_multiplier': 1.2,
                'take_profit_multiplier': 0.7,
                'max_positions': 1,
                'preferred_timeframes': ['15m', '5m'],
                'signal_threshold_multiplier': 1.3
            }
        }
        
        # Further adjust for extreme volatility
        if volatility > 0.9:
            params[regime]['position_size_multiplier'] *= 0.7
            params[regime]['stop_loss_multiplier'] *= 1.2
        
        return params.get(regime, params['ranging'])
    
    def _get_regime_characteristics(self, regime: str) -> Dict:
        """Get regime characteristics"""
        characteristics = {
            'trending_up': {
                'description': '강한 상승 추세',
                'kr_description': '강한 상승 추세',
                'risk_level': 0.3,
                'position_bias': 'long',
                'suggested_strategy': 'trend_following',
                'key_indicators': ['ADX', '이동평균선', 'MACD'],
                'warnings': ['과매수 상태 주의', '추적손절 설정']
            },
            'trending_down': {
                'description': '강한 하락 추세',
                'kr_description': '강한 하락 추세',
                'risk_level': 0.7,
                'position_bias': 'short',
                'suggested_strategy': 'trend_following',
                'key_indicators': ['ADX', '이동평균선', 'MACD'],
                'warnings': ['고위험 환경', '타이트한 손절 사용']
            },
            'ranging': {
                'description': '횡보/박스권',
                'kr_description': '횡보/박스권',
                'risk_level': 0.5,
                'position_bias': 'neutral',
                'suggested_strategy': 'mean_reversion',
                'key_indicators': ['RSI', '볼린저 밴드', '지지/저항'],
                'warnings': ['브레이크아웃 가짜 신호 주의', '레인지 내 거래']
            },
            'volatile': {
                'description': '고변동성',
                'kr_description': '고변동성',
                'risk_level': 0.8,
                'position_bias': 'neutral',
                'suggested_strategy': 'scalping',
                'key_indicators': ['ATR', '볼린저 밴드', '거래량'],
                'warnings': ['포지션 크기 축소', '넓은 손절 필요']
            }
        }
        
        return characteristics.get(regime, characteristics['ranging'])
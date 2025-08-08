"""
BTC Trading Strategy
Bitcoin-specific trading strategy with trend following and technical analysis
"""

import logging
import numpy as np
import pandas as pd
from typing import Dict

# Import handling for both direct and package imports
try:
    from ..config.config import TradingConfig
    from .base_strategy import BaseTradingStrategy, TrendFollowingMixin, MomentumMixin, VolumeMixin
except ImportError:
    import sys
    import os
    sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    from config.config import TradingConfig
    from strategies.base_strategy import BaseTradingStrategy, TrendFollowingMixin, MomentumMixin, VolumeMixin


class BTCTradingStrategy(BaseTradingStrategy, TrendFollowingMixin, MomentumMixin, VolumeMixin):
    """BTC-specific trading strategy"""
    
    def __init__(self, config: TradingConfig):
        super().__init__(config)
        self.logger = logging.getLogger(__name__)
    
    async def analyze(self, symbol: str, df: pd.DataFrame, indicators: Dict) -> Dict:
        """Analyze BTC with multiple signals"""
        result = {
            'direction': 'neutral',
            'score': 0,
            'confidence': 50,
            'components': {}
        }
        
        # 1. Trend Following
        trend_score = self._analyze_trend(df, indicators)
        result['components']['trend'] = trend_score
        
        # 2. Mean Reversion
        mr_score = self._analyze_mean_reversion(df, indicators)
        result['components']['mean_reversion'] = mr_score
        
        # 3. Momentum
        momentum_score = self._analyze_momentum(df, indicators)
        result['components']['momentum'] = momentum_score
        
        # 4. Volume Analysis
        volume_score = self._analyze_volume(df, indicators)
        result['components']['volume'] = volume_score
        
        # 5. Support/Resistance
        sr_score = self._analyze_support_resistance(df, indicators)
        result['components']['support_resistance'] = sr_score
        
        # Combine scores with weights
        weights = {
            'trend': 0.35,
            'mean_reversion': 0.15,
            'momentum': 0.25,
            'volume': 0.15,
            'support_resistance': 0.10
        }
        
        total_score = sum(result['components'][k] * weights[k] for k in weights)
        result['score'] = np.clip(total_score, -1, 1)
        
        # Determine direction
        if result['score'] > 0.3:
            result['direction'] = 'long'
        elif result['score'] < -0.3:
            result['direction'] = 'short'
        
        # Calculate confidence
        result['confidence'] = self._calculate_confidence(result['components'], indicators)
        
        return result
    
    def _analyze_trend(self, df: pd.DataFrame, indicators: Dict) -> float:
        """Analyze trend following signals"""
        score = 0
        current_price = df['close'].iloc[-1]
        
        # EMA alignment
        if indicators['ema_20'].iloc[-1] > indicators['ema_50'].iloc[-1]:
            score += 0.3
        else:
            score -= 0.3
        
        # Price vs MA
        if current_price > indicators['sma_200'].iloc[-1]:
            score += 0.2
        else:
            score -= 0.2
        
        # ADX trend strength
        if indicators['adx'].iloc[-1] > 25:
            score *= 1.2
        
        return np.clip(score, -1, 1)
    
    def _analyze_mean_reversion(self, df: pd.DataFrame, indicators: Dict) -> float:
        """Analyze mean reversion signals"""
        score = 0
        
        # RSI
        rsi = indicators['rsi'].iloc[-1]
        if rsi < 30:
            score += 0.5
        elif rsi > 70:
            score -= 0.5
        
        # Bollinger Bands
        price_position = indicators['price_position'].iloc[-1]
        if price_position < 0.2:
            score += 0.3
        elif price_position > 0.8:
            score -= 0.3
        
        return np.clip(score, -1, 1)
    
    def _analyze_momentum(self, df: pd.DataFrame, indicators: Dict) -> float:
        """Analyze momentum signals"""
        score = 0
        
        # MACD
        if indicators['macd'].iloc[-1] > indicators['macd_signal'].iloc[-1]:
            score += 0.4
            if indicators['macd_hist'].iloc[-1] > indicators['macd_hist'].iloc[-2]:
                score += 0.2
        else:
            score -= 0.4
            if indicators['macd_hist'].iloc[-1] < indicators['macd_hist'].iloc[-2]:
                score -= 0.2
        
        # Stochastic RSI
        if indicators['stoch_rsi'].iloc[-1] < 20:
            score += 0.2
        elif indicators['stoch_rsi'].iloc[-1] > 80:
            score -= 0.2
        
        return np.clip(score, -1, 1)
    
    def _analyze_volume(self, df: pd.DataFrame, indicators: Dict) -> float:
        """Analyze volume signals"""
        score = 0
        
        # Volume trend
        if indicators['volume_ratio'].iloc[-1] > 1.5:
            # High volume
            if df['close'].iloc[-1] > df['close'].iloc[-2]:
                score += 0.3
            else:
                score -= 0.3
        
        # OBV trend
        try:
            if 'obv' in indicators and len(indicators['obv']) > 20:
                obv_values = indicators['obv'].iloc[-20:].values
                if len(obv_values) >= 20:
                    obv_slope = np.polyfit(range(20), obv_values, 1)[0]
                    if obv_slope > 0:
                        score += 0.2
                    else:
                        score -= 0.2
        except Exception as e:
            # If OBV analysis fails, continue without it
            pass
        
        return np.clip(score, -1, 1)
    
    def _analyze_support_resistance(self, df: pd.DataFrame, indicators: Dict) -> float:
        """Analyze support/resistance levels"""
        score = 0
        current_price = df['close'].iloc[-1]
        
        # Ichimoku Cloud
        if current_price > indicators['ichimoku_cloud_top'].iloc[-26]:
            score += 0.3
        elif current_price < indicators['ichimoku_cloud_bottom'].iloc[-26]:
            score -= 0.3
        
        # VWAP
        if current_price > indicators['vwap'].iloc[-1]:
            score += 0.2
        else:
            score -= 0.2
        
        return np.clip(score, -1, 1)
    
    def _calculate_confidence(self, components: Dict, indicators: Dict) -> float:
        """Calculate signal confidence"""
        # Base confidence on component agreement
        positive_count = sum(1 for v in components.values() if v > 0.1)
        negative_count = sum(1 for v in components.values() if v < -0.1)
        
        if positive_count >= 4 or negative_count >= 4:
            confidence = 80
        elif positive_count >= 3 or negative_count >= 3:
            confidence = 65
        else:
            confidence = 50
        
        # Adjust for trend strength
        trend_strength = indicators['trend_strength'].iloc[-1]
        confidence += trend_strength * 10
        
        # Adjust for volatility
        volatility = indicators['atr_percent'].iloc[-1]
        if volatility > 3:
            confidence *= 0.8
        
        return min(95, max(30, confidence))
    
    def generate_signal(self, symbol: str, df: pd.DataFrame, indicators: Dict) -> Dict:
        """Generate trading signal based on analysis"""
        try:
            # Use the analyze method to get the full analysis (sync version for signal generation)
            import asyncio
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            analysis = loop.run_until_complete(self.analyze(symbol, df, indicators))
            loop.close()
            
            # Convert analysis to trading signal
            action = 'hold'
            strength = 0.0
            
            if analysis['direction'] == 'long' and analysis['confidence'] >= self.min_confidence:
                action = 'buy'
                strength = min(1.0, analysis['score'])
            elif analysis['direction'] == 'short' and analysis['confidence'] >= self.min_confidence:
                action = 'sell'
                strength = min(1.0, abs(analysis['score']))
            
            # Calculate stop loss and take profit prices
            current_price = df['close'].iloc[-1]
            stop_loss = self.get_stop_loss_price(current_price, analysis['direction'])
            take_profit = self.get_take_profit_price(current_price, analysis['direction'])
            
            return {
                'action': action,
                'strength': strength,
                'stop_loss': stop_loss,
                'take_profit': take_profit,
                'confidence': analysis['confidence'],
                'analysis_components': analysis['components'],
                'timestamp': pd.Timestamp.now(),
                'symbol': symbol
            }
            
        except Exception as e:
            self.logger.error(f"Error generating signal for {symbol}: {e}")
            return {
                'action': 'hold',
                'strength': 0.0,
                'stop_loss': None,
                'take_profit': None,
                'confidence': 0,
                'error': str(e)
            }
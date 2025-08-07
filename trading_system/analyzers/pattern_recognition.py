"""
Pattern Recognition System
Advanced pattern recognition for chart patterns
"""

import logging
import numpy as np
import pandas as pd
from typing import Dict
from cachetools import TTLCache


class PatternRecognitionSystem:
    """Advanced pattern recognition for chart patterns"""
    
    def __init__(self):
        self.logger = logging.getLogger(__name__)
        self.pattern_cache = TTLCache(maxsize=100, ttl=300)
    
    def identify_patterns(self, df: pd.DataFrame, indicators: Dict) -> Dict[str, Dict]:
        """Identify various chart patterns"""
        # Check cache
        cache_key = f"patterns:{df.index[-1]}:{df['close'].iloc[-1]}"
        cached_patterns = self.pattern_cache.get(cache_key)
        if cached_patterns:
            return cached_patterns
        
        patterns = {}
        
        # Price action patterns
        patterns.update(self._identify_candlestick_patterns(df))
        
        # Chart patterns
        patterns.update(self._identify_chart_patterns(df))
        
        # Indicator patterns
        patterns.update(self._identify_indicator_patterns(df, indicators))
        
        # Cache results
        self.pattern_cache[cache_key] = patterns
        
        return patterns
    
    def _identify_candlestick_patterns(self, df: pd.DataFrame) -> Dict[str, Dict]:
        """Identify candlestick patterns"""
        patterns = {}
        
        # Get recent candles
        recent = df.tail(10)
        
        # Hammer/Hanging Man
        hammer = self._detect_hammer(recent)
        if hammer['detected']:
            patterns['hammer'] = hammer
        
        # Doji
        doji = self._detect_doji(recent)
        if doji['detected']:
            patterns['doji'] = doji
        
        # Engulfing
        engulfing = self._detect_engulfing(recent)
        if engulfing['detected']:
            patterns['engulfing'] = engulfing
        
        # Three White Soldiers / Three Black Crows
        three_pattern = self._detect_three_pattern(recent)
        if three_pattern['detected']:
            patterns['three_pattern'] = three_pattern
        
        return patterns
    
    def _identify_chart_patterns(self, df: pd.DataFrame) -> Dict[str, Dict]:
        """Identify chart patterns like triangles, flags, etc."""
        patterns = {}
        
        # Support and Resistance
        sr_levels = self._find_support_resistance(df)
        if sr_levels['detected']:
            patterns['support_resistance'] = sr_levels
        
        # Triangle patterns
        triangle = self._detect_triangle(df)
        if triangle['detected']:
            patterns['triangle'] = triangle
        
        # Double Top/Bottom
        double_pattern = self._detect_double_pattern(df)
        if double_pattern['detected']:
            patterns['double_pattern'] = double_pattern
        
        return patterns
    
    def _identify_indicator_patterns(self, df: pd.DataFrame, indicators: Dict) -> Dict[str, Dict]:
        """Identify patterns in indicators"""
        patterns = {}
        
        # RSI Divergence
        rsi_div = self._detect_rsi_divergence(df, indicators)
        if rsi_div['detected']:
            patterns['rsi_divergence'] = rsi_div
        
        # MACD Cross
        macd_cross = self._detect_macd_cross(indicators)
        if macd_cross['detected']:
            patterns['macd_cross'] = macd_cross
        
        # Bollinger Band Squeeze
        bb_squeeze = self._detect_bollinger_squeeze(indicators)
        if bb_squeeze['detected']:
            patterns['bb_squeeze'] = bb_squeeze
        
        return patterns
    
    def _detect_hammer(self, df: pd.DataFrame) -> Dict:
        """Detect hammer/hanging man pattern"""
        last_candle = df.iloc[-1]
        body = abs(last_candle['close'] - last_candle['open'])
        lower_shadow = min(last_candle['open'], last_candle['close']) - last_candle['low']
        upper_shadow = last_candle['high'] - max(last_candle['open'], last_candle['close'])
        
        # Hammer criteria
        is_hammer = (
            lower_shadow > body * 2 and
            upper_shadow < body * 0.5 and
            body > 0
        )
        
        if is_hammer:
            # Determine if bullish or bearish based on trend
            trend = df['close'].iloc[-10:-1].mean()
            if last_candle['close'] < trend:
                return {
                    'detected': True,
                    'type': 'hammer',
                    'bullish': True,
                    'confidence': 0.7,
                    'expected_move': 0.02
                }
            else:
                return {
                    'detected': True,
                    'type': 'hanging_man',
                    'bullish': False,
                    'confidence': 0.6,
                    'expected_move': -0.02
                }
        
        return {'detected': False}
    
    def _detect_doji(self, df: pd.DataFrame) -> Dict:
        """Detect doji pattern"""
        last_candle = df.iloc[-1]
        body = abs(last_candle['close'] - last_candle['open'])
        total_range = last_candle['high'] - last_candle['low']
        
        if total_range > 0 and body / total_range < 0.1:
            return {
                'detected': True,
                'type': 'doji',
                'indecision': True,
                'confidence': 0.5,
                'expected_move': 0
            }
        
        return {'detected': False}
    
    def _detect_engulfing(self, df: pd.DataFrame) -> Dict:
        """Detect engulfing pattern"""
        if len(df) < 2:
            return {'detected': False}
        
        prev_candle = df.iloc[-2]
        last_candle = df.iloc[-1]
        
        prev_body = abs(prev_candle['close'] - prev_candle['open'])
        last_body = abs(last_candle['close'] - last_candle['open'])
        
        # Bullish engulfing
        if (prev_candle['close'] < prev_candle['open'] and
            last_candle['close'] > last_candle['open'] and
            last_candle['open'] < prev_candle['close'] and
            last_candle['close'] > prev_candle['open'] and
            last_body > prev_body):
            return {
                'detected': True,
                'type': 'bullish_engulfing',
                'bullish': True,
                'confidence': 0.75,
                'expected_move': 0.03
            }
        
        # Bearish engulfing
        elif (prev_candle['close'] > prev_candle['open'] and
              last_candle['close'] < last_candle['open'] and
              last_candle['open'] > prev_candle['close'] and
              last_candle['close'] < prev_candle['open'] and
              last_body > prev_body):
            return {
                'detected': True,
                'type': 'bearish_engulfing',
                'bullish': False,
                'confidence': 0.75,
                'expected_move': -0.03
            }
        
        return {'detected': False}
    
    def _detect_three_pattern(self, df: pd.DataFrame) -> Dict:
        """Detect three white soldiers or three black crows"""
        if len(df) < 3:
            return {'detected': False}
        
        last_three = df.tail(3)
        
        # Check if all bullish or bearish
        all_bullish = all(candle['close'] > candle['open'] for _, candle in last_three.iterrows())
        all_bearish = all(candle['close'] < candle['open'] for _, candle in last_three.iterrows())
        
        if all_bullish:
            # Check if progressively higher
            if (last_three['close'].iloc[0] < last_three['close'].iloc[1] < last_three['close'].iloc[2]):
                return {
                    'detected': True,
                    'type': 'three_white_soldiers',
                    'bullish': True,
                    'confidence': 0.8,
                    'expected_move': 0.04
                }
        elif all_bearish:
            # Check if progressively lower
            if (last_three['close'].iloc[0] > last_three['close'].iloc[1] > last_three['close'].iloc[2]):
                return {
                    'detected': True,
                    'type': 'three_black_crows',
                    'bullish': False,
                    'confidence': 0.8,
                    'expected_move': -0.04
                }
        
        return {'detected': False}
    
    def _find_support_resistance(self, df: pd.DataFrame) -> Dict:
        """Find support and resistance levels"""
        # Look for price levels that have been tested multiple times
        highs = df['high'].rolling(window=20).max()
        lows = df['low'].rolling(window=20).min()
        
        current_price = df['close'].iloc[-1]
        
        # Find nearest support and resistance
        recent_highs = highs.iloc[-100:].value_counts().head(3)
        recent_lows = lows.iloc[-100:].value_counts().head(3)
        
        resistance = None
        support = None
        
        for level, count in recent_highs.items():
            if level > current_price and count >= 2:
                resistance = level
                break
        
        for level, count in recent_lows.items():
            if level < current_price and count >= 2:
                support = level
                break
        
        if resistance or support:
            return {
                'detected': True,
                'resistance': resistance,
                'support': support,
                'current_price': current_price,
                'near_resistance': resistance and (resistance - current_price) / current_price < 0.01,
                'near_support': support and (current_price - support) / current_price < 0.01,
                'confidence': 0.6,
                'expected_move': 0
            }
        
        return {'detected': False}
    
    def _detect_triangle(self, df: pd.DataFrame) -> Dict:
        """Detect triangle patterns"""
        if len(df) < 50:
            return {'detected': False}
        
        # Get recent highs and lows
        recent = df.tail(50)
        highs = recent['high'].rolling(window=5).max()
        lows = recent['low'].rolling(window=5).min()
        
        # Check for converging trendlines
        high_slope = np.polyfit(range(len(highs)), highs.values, 1)[0]
        low_slope = np.polyfit(range(len(lows)), lows.values, 1)[0]
        
        # Ascending triangle
        if abs(high_slope) < 0.001 and low_slope > 0:
            return {
                'detected': True,
                'type': 'ascending_triangle',
                'bullish': True,
                'confidence': 0.7,
                'expected_move': 0.03
            }
        
        # Descending triangle
        elif high_slope < 0 and abs(low_slope) < 0.001:
            return {
                'detected': True,
                'type': 'descending_triangle',
                'bullish': False,
                'confidence': 0.7,
                'expected_move': -0.03
            }
        
        # Symmetrical triangle
        elif abs(high_slope + low_slope) < 0.001:
            return {
                'detected': True,
                'type': 'symmetrical_triangle',
                'neutral': True,
                'confidence': 0.5,
                'expected_move': 0
            }
        
        return {'detected': False}
    
    def _detect_double_pattern(self, df: pd.DataFrame) -> Dict:
        """Detect double top/bottom patterns"""
        if len(df) < 100:
            return {'detected': False}
        
        # Find local maxima and minima
        highs = df['high'].rolling(window=10).max()
        lows = df['low'].rolling(window=10).min()
        
        # Look for two similar peaks or troughs
        recent_peaks = []
        recent_troughs = []
        
        for i in range(20, len(df) - 5):
            if highs.iloc[i] == df['high'].iloc[i]:
                recent_peaks.append((i, df['high'].iloc[i]))
            if lows.iloc[i] == df['low'].iloc[i]:
                recent_troughs.append((i, df['low'].iloc[i]))
        
        # Check for double top
        if len(recent_peaks) >= 2:
            last_two_peaks = recent_peaks[-2:]
            price_diff = abs(last_two_peaks[0][1] - last_two_peaks[1][1]) / last_two_peaks[0][1]
            if price_diff < 0.02:  # Within 2%
                return {
                    'detected': True,
                    'type': 'double_top',
                    'bearish': True,
                    'confidence': 0.75,
                    'expected_move': -0.04
                }
        
        # Check for double bottom
        if len(recent_troughs) >= 2:
            last_two_troughs = recent_troughs[-2:]
            price_diff = abs(last_two_troughs[0][1] - last_two_troughs[1][1]) / last_two_troughs[0][1]
            if price_diff < 0.02:  # Within 2%
                return {
                    'detected': True,
                    'type': 'double_bottom',
                    'bullish': True,
                    'confidence': 0.75,
                    'expected_move': 0.04
                }
        
        return {'detected': False}
    
    def _detect_rsi_divergence(self, df: pd.DataFrame, indicators: Dict) -> Dict:
        """Detect RSI divergence"""
        if 'rsi' not in indicators or len(df) < 50:
            return {'detected': False}
        
        # Get recent data
        recent_price = df['close'].tail(50)
        recent_rsi = indicators['rsi'].tail(50)
        
        # Find peaks and troughs
        price_peaks = []
        rsi_peaks = []
        
        for i in range(5, len(recent_price) - 5):
            if recent_price.iloc[i] > recent_price.iloc[i-5:i].max() and recent_price.iloc[i] > recent_price.iloc[i+1:i+6].max():
                price_peaks.append((i, recent_price.iloc[i]))
            if recent_rsi.iloc[i] > recent_rsi.iloc[i-5:i].max() and recent_rsi.iloc[i] > recent_rsi.iloc[i+1:i+6].max():
                rsi_peaks.append((i, recent_rsi.iloc[i]))
        
        # Check for bearish divergence
        if len(price_peaks) >= 2 and len(rsi_peaks) >= 2:
            if price_peaks[-1][1] > price_peaks[-2][1] and rsi_peaks[-1][1] < rsi_peaks[-2][1]:
                return {
                    'detected': True,
                    'type': 'bearish_divergence',
                    'bearish': True,
                    'confidence': 0.7,
                    'expected_move': -0.02
                }
        
        # Similar check for bullish divergence with troughs
        # (Implementation similar to above but with troughs)
        
        return {'detected': False}
    
    def _detect_macd_cross(self, indicators: Dict) -> Dict:
        """Detect MACD crossover"""
        if 'macd' not in indicators or 'macd_signal' not in indicators:
            return {'detected': False}
        
        macd = indicators['macd'].iloc[-2:]
        signal = indicators['macd_signal'].iloc[-2:]
        
        if len(macd) < 2 or len(signal) < 2:
            return {'detected': False}
        
        # Bullish cross
        if macd.iloc[0] < signal.iloc[0] and macd.iloc[1] > signal.iloc[1]:
            return {
                'detected': True,
                'type': 'macd_bullish_cross',
                'bullish': True,
                'confidence': 0.65,
                'expected_move': 0.02
            }
        
        # Bearish cross
        elif macd.iloc[0] > signal.iloc[0] and macd.iloc[1] < signal.iloc[1]:
            return {
                'detected': True,
                'type': 'macd_bearish_cross',
                'bearish': True,
                'confidence': 0.65,
                'expected_move': -0.02
            }
        
        return {'detected': False}
    
    def _detect_bollinger_squeeze(self, indicators: Dict) -> Dict:
        """Detect Bollinger Band squeeze"""
        if 'bb_upper' not in indicators or 'bb_lower' not in indicators:
            return {'detected': False}
        
        # Calculate band width
        band_width = indicators['bb_upper'] - indicators['bb_lower']
        avg_width = band_width.rolling(window=50).mean()
        
        current_width = band_width.iloc[-1]
        avg = avg_width.iloc[-1]
        
        if avg > 0 and current_width / avg < 0.7:
            return {
                'detected': True,
                'type': 'bollinger_squeeze',
                'volatility_expansion_expected': True,
                'confidence': 0.6,
                'expected_move': 0  # Direction unclear
            }
        
        return {'detected': False}
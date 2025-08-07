"""
Enhanced Technical Indicators
Comprehensive technical indicators library with caching
"""

import hashlib
import numpy as np
import pandas as pd
from functools import lru_cache
from typing import Dict, Any, Tuple
from cachetools import TTLCache

# Optional technical analysis import
try:
    import talib
except ImportError:
    talib = None
    print("⚠️  Warning: talib not installed. Some technical indicators may not work.")


class EnhancedTechnicalIndicators:
    """Comprehensive technical indicators library with caching"""
    
    _cache = TTLCache(maxsize=1000, ttl=60)
    
    @classmethod
    @lru_cache(maxsize=128)
    def _calculate_cached_indicator(cls, data_hash: str, indicator_name: str, *args, **kwargs):
        """Cache wrapper for indicator calculations"""
        return None  # Will be overridden by actual calculations
    
    @classmethod
    def calculate_all_indicators(cls, df: pd.DataFrame) -> Dict[str, Any]:
        """Calculate all technical indicators with caching"""
        if talib is None:
            return cls._calculate_indicators_without_talib(df)
            
        # Create hash of dataframe for caching
        df_hash = hashlib.md5(pd.util.hash_pandas_object(df).values).hexdigest()
        
        indicators = {}
        
        # Trend Indicators
        indicators['sma_20'] = talib.SMA(df['close'], timeperiod=20)
        indicators['sma_50'] = talib.SMA(df['close'], timeperiod=50)
        indicators['sma_200'] = talib.SMA(df['close'], timeperiod=200)
        indicators['ema_20'] = talib.EMA(df['close'], timeperiod=20)
        indicators['ema_50'] = talib.EMA(df['close'], timeperiod=50)
        
        # MACD
        indicators['macd'], indicators['macd_signal'], indicators['macd_hist'] = talib.MACD(
            df['close'], fastperiod=12, slowperiod=26, signalperiod=9
        )
        
        # RSI with multiple periods
        indicators['rsi'] = talib.RSI(df['close'], timeperiod=14)
        indicators['rsi_6'] = talib.RSI(df['close'], timeperiod=6)
        indicators['rsi_24'] = talib.RSI(df['close'], timeperiod=24)
        
        # Stochastic RSI
        indicators['stoch_rsi'], indicators['stoch_rsi_d'] = talib.STOCHRSI(
            df['close'], timeperiod=14, fastk_period=3, fastd_period=3
        )
        
        # Bollinger Bands
        indicators['bb_upper'], indicators['bb_middle'], indicators['bb_lower'] = talib.BBANDS(
            df['close'], timeperiod=20, nbdevup=2, nbdevdn=2
        )
        
        # Keltner Channels
        indicators['kc_upper'], indicators['kc_middle'], indicators['kc_lower'] = cls.calculate_keltner_channels(df)
        
        # ATR
        indicators['atr'] = talib.ATR(df['high'], df['low'], df['close'], timeperiod=14)
        indicators['atr_percent'] = indicators['atr'] / df['close'] * 100
        
        # ADX
        indicators['adx'] = talib.ADX(df['high'], df['low'], df['close'], timeperiod=14)
        indicators['plus_di'] = talib.PLUS_DI(df['high'], df['low'], df['close'], timeperiod=14)
        indicators['minus_di'] = talib.MINUS_DI(df['high'], df['low'], df['close'], timeperiod=14)
        
        # Volume Indicators
        indicators['obv'] = talib.OBV(df['close'], df['volume'])
        indicators['volume_sma'] = talib.SMA(df['volume'], timeperiod=20)
        indicators['volume_ratio'] = df['volume'] / indicators['volume_sma']
        
        # MFI
        indicators['mfi'] = talib.MFI(df['high'], df['low'], df['close'], df['volume'], timeperiod=14)
        
        # Ichimoku Cloud
        ichimoku = cls.calculate_ichimoku(df)
        indicators.update(ichimoku)
        
        # VWAP
        indicators['vwap'] = cls.calculate_vwap(df)
        
        # CMF
        indicators['cmf'] = cls.calculate_cmf(df)
        
        # Supertrend
        indicators['supertrend'], indicators['supertrend_direction'] = cls.calculate_supertrend(df)
        
        # Custom indicators
        indicators['price_position'] = cls.calculate_price_position(df, indicators)
        indicators['trend_strength'] = cls.calculate_trend_strength(indicators)
        indicators['volatility_ratio'] = cls.calculate_volatility_ratio(df, indicators)
        
        return indicators
    
    @classmethod
    def _calculate_indicators_without_talib(cls, df: pd.DataFrame) -> Dict[str, Any]:
        """Calculate basic indicators without talib"""
        indicators = {}
        
        # Basic moving averages
        indicators['sma_20'] = df['close'].rolling(window=20).mean()
        indicators['sma_50'] = df['close'].rolling(window=50).mean()
        indicators['sma_200'] = df['close'].rolling(window=200).mean()
        indicators['ema_20'] = df['close'].ewm(span=20).mean()
        indicators['ema_50'] = df['close'].ewm(span=50).mean()
        
        # Basic RSI
        indicators['rsi'] = cls._calculate_rsi(df['close'], 14)
        
        # Basic Bollinger Bands
        indicators['bb_upper'], indicators['bb_middle'], indicators['bb_lower'] = cls._calculate_bollinger_bands(df['close'])
        
        # Volume indicators
        indicators['volume_sma'] = df['volume'].rolling(window=20).mean()
        indicators['volume_ratio'] = df['volume'] / indicators['volume_sma']
        
        # VWAP and other custom indicators
        indicators['vwap'] = cls.calculate_vwap(df)
        indicators['cmf'] = cls.calculate_cmf(df)
        
        return indicators
    
    @staticmethod
    def _calculate_rsi(prices: pd.Series, period: int = 14) -> pd.Series:
        """Calculate RSI without talib"""
        delta = prices.diff()
        gain = (delta.where(delta > 0, 0)).rolling(window=period).mean()
        loss = (-delta.where(delta < 0, 0)).rolling(window=period).mean()
        rs = gain / loss
        rsi = 100 - (100 / (1 + rs))
        return rsi
    
    @staticmethod
    def _calculate_bollinger_bands(prices: pd.Series, period: int = 20, std_dev: int = 2) -> Tuple[pd.Series, pd.Series, pd.Series]:
        """Calculate Bollinger Bands without talib"""
        middle = prices.rolling(window=period).mean()
        std = prices.rolling(window=period).std()
        upper = middle + (std * std_dev)
        lower = middle - (std * std_dev)
        return upper, middle, lower
    
    @staticmethod
    def calculate_keltner_channels(df: pd.DataFrame, period: int = 20, multiplier: float = 2.0) -> Tuple[pd.Series, pd.Series, pd.Series]:
        """Calculate Keltner Channels"""
        typical_price = (df['high'] + df['low'] + df['close']) / 3
        
        if talib:
            middle = talib.EMA(typical_price, timeperiod=period)
            atr = talib.ATR(df['high'], df['low'], df['close'], timeperiod=period)
        else:
            middle = typical_price.ewm(span=period).mean()
            high_low = df['high'] - df['low']
            high_close = np.abs(df['high'] - df['close'].shift())
            low_close = np.abs(df['low'] - df['close'].shift())
            true_range = pd.concat([high_low, high_close, low_close], axis=1).max(axis=1)
            atr = true_range.rolling(window=period).mean()
        
        upper = middle + (multiplier * atr)
        lower = middle - (multiplier * atr)
        
        return upper, middle, lower
    
    @staticmethod
    def calculate_ichimoku(df: pd.DataFrame) -> Dict[str, pd.Series]:
        """Calculate Ichimoku Cloud"""
        high_9 = df['high'].rolling(window=9).max()
        low_9 = df['low'].rolling(window=9).min()
        tenkan_sen = (high_9 + low_9) / 2
        
        high_26 = df['high'].rolling(window=26).max()
        low_26 = df['low'].rolling(window=26).min()
        kijun_sen = (high_26 + low_26) / 2
        
        senkou_span_a = ((tenkan_sen + kijun_sen) / 2).shift(26)
        
        high_52 = df['high'].rolling(window=52).max()
        low_52 = df['low'].rolling(window=52).min()
        senkou_span_b = ((high_52 + low_52) / 2).shift(26)
        
        chikou_span = df['close'].shift(-26)
        
        return {
            'ichimoku_tenkan': tenkan_sen,
            'ichimoku_kijun': kijun_sen,
            'ichimoku_senkou_a': senkou_span_a,
            'ichimoku_senkou_b': senkou_span_b,
            'ichimoku_chikou': chikou_span,
            'ichimoku_cloud_top': pd.Series(np.maximum(senkou_span_a, senkou_span_b)),
            'ichimoku_cloud_bottom': pd.Series(np.minimum(senkou_span_a, senkou_span_b))
        }
    
    @staticmethod
    def calculate_vwap(df: pd.DataFrame) -> pd.Series:
        """Calculate VWAP"""
        typical_price = (df['high'] + df['low'] + df['close']) / 3
        vwap = (typical_price * df['volume']).cumsum() / df['volume'].cumsum()
        return vwap
    
    @staticmethod
    def calculate_cmf(df: pd.DataFrame, period: int = 21) -> pd.Series:
        """Calculate Chaikin Money Flow"""
        mf_multiplier = ((df['close'] - df['low']) - (df['high'] - df['close'])) / (df['high'] - df['low'])
        mf_multiplier = mf_multiplier.fillna(0)
        mf_volume = mf_multiplier * df['volume']
        
        cmf = mf_volume.rolling(window=period).sum() / df['volume'].rolling(window=period).sum()
        return cmf
    
    @staticmethod
    def calculate_supertrend(df: pd.DataFrame, period: int = 10, multiplier: float = 3.0) -> Tuple[pd.Series, pd.Series]:
        """Calculate Supertrend"""
        hl_avg = (df['high'] + df['low']) / 2
        
        if talib:
            atr = talib.ATR(df['high'], df['low'], df['close'], timeperiod=period)
        else:
            high_low = df['high'] - df['low']
            high_close = np.abs(df['high'] - df['close'].shift())
            low_close = np.abs(df['low'] - df['close'].shift())
            true_range = pd.concat([high_low, high_close, low_close], axis=1).max(axis=1)
            atr = true_range.rolling(window=period).mean()
        
        upper_band = hl_avg + (multiplier * atr)
        lower_band = hl_avg - (multiplier * atr)
        
        supertrend = pd.Series(index=df.index, dtype=float)
        direction = pd.Series(index=df.index, dtype=int)
        
        for i in range(period, len(df)):
            if df['close'].iloc[i] <= upper_band.iloc[i]:
                supertrend.iloc[i] = upper_band.iloc[i]
                direction.iloc[i] = -1
            else:
                supertrend.iloc[i] = lower_band.iloc[i]
                direction.iloc[i] = 1
                
            if i > period:
                if direction.iloc[i] == 1:
                    if supertrend.iloc[i] < supertrend.iloc[i-1]:
                        supertrend.iloc[i] = supertrend.iloc[i-1]
                else:
                    if supertrend.iloc[i] > supertrend.iloc[i-1]:
                        supertrend.iloc[i] = supertrend.iloc[i-1]
        
        return supertrend, direction
    
    @staticmethod
    def calculate_price_position(df: pd.DataFrame, indicators: Dict) -> pd.Series:
        """Calculate price position relative to key levels"""
        current_price = df['close']
        
        # Calculate position between 0 and 1
        position = pd.Series(index=df.index, dtype=float)
        
        # Bollinger Band position
        if 'bb_upper' in indicators and 'bb_lower' in indicators:
            bb_position = (current_price - indicators['bb_lower']) / (indicators['bb_upper'] - indicators['bb_lower'])
        else:
            bb_position = pd.Series(0.5, index=df.index)
        
        # Moving average position
        if 'sma_200' in indicators and 'sma_20' in indicators:
            ma_range = indicators['sma_200'] - indicators['sma_20']
            ma_position = (current_price - indicators['sma_20']) / ma_range.replace(0, 1)
        else:
            ma_position = pd.Series(0.5, index=df.index)
        
        # Combine positions
        position = (bb_position + ma_position) / 2
        
        return position.clip(0, 1)
    
    @staticmethod
    def calculate_trend_strength(indicators: Dict) -> pd.Series:
        """Calculate overall trend strength"""
        # Default to neutral trend if indicators missing
        if 'sma_20' not in indicators:
            return pd.Series(0.5, index=indicators.get('rsi', pd.Series()).index)
            
        index = indicators['sma_20'].index
        
        # ADX-based trend strength
        if 'adx' in indicators:
            adx_strength = indicators['adx'] / 100
        else:
            adx_strength = pd.Series(0.5, index=index)
        
        # Moving average alignment
        ma_alignment = pd.Series(index=index, dtype=float)
        if all(key in indicators for key in ['ema_20', 'ema_50', 'sma_200']):
            ma_alignment[(indicators['ema_20'] > indicators['ema_50']) & 
                        (indicators['ema_50'] > indicators['sma_200'])] = 1
            ma_alignment[(indicators['ema_20'] < indicators['ema_50']) & 
                        (indicators['ema_50'] < indicators['sma_200'])] = -1
        ma_alignment.fillna(0, inplace=True)
        
        # MACD strength
        if 'macd' in indicators:
            macd_strength = np.sign(indicators['macd']) * np.minimum(np.abs(indicators['macd']) / indicators['macd'].std(), 1)
        else:
            macd_strength = pd.Series(0, index=index)
        
        # Combine
        trend_strength = (adx_strength + np.abs(ma_alignment) + np.abs(macd_strength)) / 3
        
        return trend_strength.clip(0, 1)
    
    @staticmethod
    def calculate_volatility_ratio(df: pd.DataFrame, indicators: Dict) -> pd.Series:
        """Calculate volatility ratio"""
        # ATR-based volatility
        if 'atr' in indicators:
            atr_ratio = indicators['atr'] / df['close']
        else:
            atr_ratio = pd.Series(0.02, index=df.index)  # Default 2%
        
        # Bollinger Band width
        if all(key in indicators for key in ['bb_upper', 'bb_lower', 'bb_middle']):
            bb_width = (indicators['bb_upper'] - indicators['bb_lower']) / indicators['bb_middle']
        else:
            bb_width = pd.Series(0.05, index=df.index)  # Default 5%
        
        # Historical volatility
        returns = df['close'].pct_change()
        hist_vol = returns.rolling(window=20).std()
        
        # Combine
        volatility_ratio = (atr_ratio + bb_width + hist_vol) / 3
        
        return volatility_ratio
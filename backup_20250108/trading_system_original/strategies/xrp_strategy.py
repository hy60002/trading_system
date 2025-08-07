"""
XRP Trading Strategy
Ripple-specific trading strategy with extreme RSI focus
"""

import logging
import numpy as np
import pandas as pd
from typing import Dict

# Import handling for both direct and package imports
try:
    from ..config.config import TradingConfig
except ImportError:
    import sys
    import os
    sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    from config.config import TradingConfig


class XRPTradingStrategy:
    """XRP-specific trading strategy"""
    
    def __init__(self, config: TradingConfig):
        self.config = config
        self.logger = logging.getLogger(__name__)
    
    async def analyze(self, symbol: str, df: pd.DataFrame, indicators: Dict) -> Dict:
        """Analyze XRP with extreme RSI focus"""
        result = {
            'direction': 'neutral',
            'score': 0,
            'confidence': 50,
            'components': {}
        }
        
        # XRP is more volatile, focus on extreme conditions
        rsi = indicators['rsi'].iloc[-1]
        
        # Only trade on extreme RSI
        if rsi < 25:
            result['direction'] = 'long'
            result['score'] = 0.7
            result['confidence'] = 75
        elif rsi > 75:
            result['direction'] = 'short'
            result['score'] = -0.7
            result['confidence'] = 75
        else:
            # Don't trade unless extreme
            result['direction'] = 'neutral'
            result['score'] = 0
            result['confidence'] = 30
        
        # Additional confirmation from other indicators
        if result['direction'] != 'neutral':
            # Check MACD alignment
            if indicators['macd'].iloc[-1] > indicators['macd_signal'].iloc[-1] and result['direction'] == 'long':
                result['score'] = min(1.0, result['score'] + 0.2)
                result['confidence'] = min(90, result['confidence'] + 10)
            elif indicators['macd'].iloc[-1] < indicators['macd_signal'].iloc[-1] and result['direction'] == 'short':
                result['score'] = max(-1.0, result['score'] - 0.2)
                result['confidence'] = min(90, result['confidence'] + 10)
        
        return result
"""
ETH Trading Strategy
Ethereum-specific trading strategy with momentum focus
"""

import logging
import numpy as np
import pandas as pd
from typing import Dict

# Import handling for both direct and package imports
try:
    from ..config.config import TradingConfig
    from .btc_strategy import BTCTradingStrategy
except ImportError:
    import sys
    import os
    sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    from config.config import TradingConfig
    from strategies.btc_strategy import BTCTradingStrategy


class ETHTradingStrategy:
    """ETH-specific trading strategy"""
    
    def __init__(self, config: TradingConfig):
        self.config = config
        self.logger = logging.getLogger(__name__)
    
    async def analyze(self, symbol: str, df: pd.DataFrame, indicators: Dict) -> Dict:
        """Analyze ETH with BTC correlation consideration"""
        # Similar structure to BTC but with additional correlation checks
        btc_strategy = BTCTradingStrategy(self.config)
        result = await btc_strategy.analyze(symbol, df, indicators)
        
        # ETH-specific adjustments
        # More sensitive to momentum
        result['components']['momentum'] *= 1.2
        
        # Less weight on mean reversion
        result['components']['mean_reversion'] *= 0.8
        
        # Recalculate score
        weights = {
            'trend': 0.3,
            'mean_reversion': 0.1,
            'momentum': 0.35,
            'volume': 0.15,
            'support_resistance': 0.10
        }
        
        total_score = sum(result['components'][k] * weights.get(k, 0.2) for k in result['components'])
        result['score'] = np.clip(total_score, -1, 1)
        
        # Higher threshold for ETH
        if result['score'] > 0.5:
            result['direction'] = 'long'
        elif result['score'] < -0.5:
            result['direction'] = 'short'
        else:
            result['direction'] = 'neutral'
        
        return result
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
    from .base_strategy import BaseTradingStrategy, TrendFollowingMixin, MomentumMixin, VolumeMixin
    from .btc_strategy import BTCTradingStrategy
except ImportError:
    import sys
    import os
    sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    from config.config import TradingConfig
    from strategies.base_strategy import BaseTradingStrategy, TrendFollowingMixin, MomentumMixin, VolumeMixin
    from strategies.btc_strategy import BTCTradingStrategy


class ETHTradingStrategy(BaseTradingStrategy, TrendFollowingMixin, MomentumMixin, VolumeMixin):
    """ETH-specific trading strategy"""
    
    def __init__(self, config: TradingConfig):
        super().__init__(config)
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
    
    def generate_signal(self, symbol: str, df: pd.DataFrame, indicators: Dict) -> Dict:
        """Generate trading signal based on ETH analysis"""
        try:
            # Use the analyze method to get the full analysis (sync version for signal generation)
            import asyncio
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            analysis = loop.run_until_complete(self.analyze(symbol, df, indicators))
            loop.close()
            
            # Convert analysis to trading signal with ETH-specific thresholds
            action = 'hold'
            strength = 0.0
            
            # ETH has higher threshold requirements due to volatility
            min_confidence_eth = max(self.min_confidence, 60)
            
            if analysis['direction'] == 'long' and analysis['confidence'] >= min_confidence_eth:
                action = 'buy'
                strength = min(1.0, analysis['score'])
            elif analysis['direction'] == 'short' and analysis['confidence'] >= min_confidence_eth:
                action = 'sell'
                strength = min(1.0, abs(analysis['score']))
            
            # Calculate stop loss and take profit prices with ETH-specific adjustments
            current_price = df['close'].iloc[-1]
            
            # ETH has higher volatility, so wider stops
            eth_stop_loss_pct = self.stop_loss_pct * 1.5
            eth_take_profit_pct = self.take_profit_pct * 1.2
            
            if analysis['direction'] == 'long':
                stop_loss = current_price * (1 - eth_stop_loss_pct)
                take_profit = current_price * (1 + eth_take_profit_pct)
            elif analysis['direction'] == 'short':
                stop_loss = current_price * (1 + eth_stop_loss_pct)
                take_profit = current_price * (1 - eth_take_profit_pct)
            else:
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
                'symbol': symbol,
                'strategy_type': 'ETH_momentum_focused'
            }
            
        except Exception as e:
            self.logger.error(f"Error generating ETH signal for {symbol}: {e}")
            return {
                'action': 'hold',
                'strength': 0.0,
                'stop_loss': None,
                'take_profit': None,
                'confidence': 0,
                'error': str(e)
            }
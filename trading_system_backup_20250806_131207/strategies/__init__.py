"""
Trading Strategies module for the trading system
"""

from .btc_strategy import BTCTradingStrategy
from .eth_strategy import ETHTradingStrategy
from .xrp_strategy import XRPTradingStrategy

__all__ = ['BTCTradingStrategy', 'ETHTradingStrategy', 'XRPTradingStrategy']
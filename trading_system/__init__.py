"""
Trading System v4.0 - Modularized Version
Enterprise-Grade Cryptocurrency Trading System

This is the modularized version of the original trading_system2.py
All original functionality is preserved and enhanced through proper separation of concerns.
"""

__version__ = "4.0.0"
__author__ = "Enhanced by Claude Code"

# Main module exports for convenience
from .config.config import TradingConfig
from .utils.errors import TradingError, ExchangeError, RiskLimitError, DataError
from .engine.advanced_trading_engine import AdvancedTradingEngine
from .database.db_manager import EnhancedDatabaseManager
from .exchange.bitget_manager import EnhancedBitgetExchangeManager

__all__ = [
    'TradingConfig',
    'TradingError', 
    'ExchangeError', 
    'RiskLimitError', 
    'DataError',
    'AdvancedTradingEngine',
    'EnhancedDatabaseManager',
    'EnhancedBitgetExchangeManager'
]
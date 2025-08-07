"""
Enhanced Trading System v4.0
Author: Enhanced by Claude Code

A comprehensive cryptocurrency trading system with:
- Modular architecture
- Enhanced security
- Comprehensive error handling
- Advanced risk management
- Real-time monitoring
- Performance optimization
"""

__version__ = "4.0.0"
__author__ = "Enhanced by Claude Code"
__description__ = "Enhanced Cryptocurrency Trading System"

# Core imports
from .core.config import TradingConfig, ConfigManager
from .core.exceptions import TradingSystemException
from .core.database import EnhancedDatabaseManager
from .core.risk_manager import EnhancedRiskManager

# Exchange imports
from .exchanges.bitget_manager import EnhancedBitgetExchangeManager

# Main system
from .main import EnhancedTradingSystem, trading_system_context

__all__ = [
    "TradingConfig",
    "ConfigManager", 
    "TradingSystemException",
    "EnhancedDatabaseManager",
    "EnhancedRiskManager",
    "EnhancedBitgetExchangeManager",
    "EnhancedTradingSystem",
    "trading_system_context"
]
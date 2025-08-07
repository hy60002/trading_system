"""
Trading System Error Classes
All custom exceptions used throughout the trading system
"""


class TradingError(Exception):
    """Base trading error"""
    pass


class ExchangeError(TradingError):
    """Exchange related errors"""
    pass


class RiskLimitError(TradingError):
    """Risk limit exceeded"""
    pass


class DataError(TradingError):
    """Data related errors"""
    pass
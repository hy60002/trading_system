"""
API module for the trading system
FastAPI web dashboard and endpoints
"""

from .app import get_app, set_trading_engine

__all__ = ['get_app', 'set_trading_engine']
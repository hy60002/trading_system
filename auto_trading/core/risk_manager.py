"""
Enhanced Risk Management System
Author: Enhanced by Claude Code
Version: 4.0
"""

import asyncio
import logging
import numpy as np
import pandas as pd
from typing import Dict, List, Optional, Tuple, Any
from datetime import datetime, timedelta
from dataclasses import dataclass
from enum import Enum

from .exceptions import (
    RiskLimitExceededError, PositionLimitError, InsufficientFundsError,
    ValidationError, handle_async_exceptions
)
from .config import TradingConfig

logger = logging.getLogger(__name__)

class RiskLevel(Enum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"

@dataclass
class RiskMetrics:
    """Risk metrics container"""
    portfolio_risk: float = 0.0
    position_risk: float = 0.0
    var_1d: float = 0.0  # Value at Risk 1 day
    var_7d: float = 0.0  # Value at Risk 7 days
    correlation_risk: float = 0.0
    leverage_risk: float = 0.0
    liquidity_risk: float = 0.0
    concentration_risk: float = 0.0
    drawdown_risk: float = 0.0
    volatility_risk: float = 0.0
    
    def overall_risk_level(self) -> RiskLevel:
        """Calculate overall risk level"""
        risk_score = (
            self.portfolio_risk * 0.3 +
            self.position_risk * 0.2 +
            self.leverage_risk * 0.2 +
            self.concentration_risk * 0.15 +
            self.volatility_risk * 0.15
        )
        
        if risk_score < 0.3:
            return RiskLevel.LOW
        elif risk_score < 0.6:
            return RiskLevel.MEDIUM
        elif risk_score < 0.8:
            return RiskLevel.HIGH
        else:
            return RiskLevel.CRITICAL

@dataclass
class PositionRisk:
    """Individual position risk metrics"""
    symbol: str
    size: float
    entry_price: float
    current_price: float
    leverage: float
    unrealized_pnl: float
    risk_percentage: float
    stop_loss: Optional[float] = None
    take_profit: Optional[float] = None
    
    @property
    def potential_loss(self) -> float:
        """Calculate potential loss if stop loss is hit"""
        if self.stop_loss:
            return abs(self.entry_price - self.stop_loss) * self.size
        return self.size * self.entry_price * 0.1  # 10% default risk

class EnhancedRiskManager:
    """Enhanced risk management system with comprehensive controls"""
    
    def __init__(self, config: TradingConfig):
        self.config = config
        self.logger = logging.getLogger(__name__)
        
        # Risk limits
        self.max_portfolio_risk = 0.02  # 2% max portfolio risk per trade
        self.max_daily_loss = 0.05  # 5% max daily loss
        self.max_drawdown = 0.15  # 15% max drawdown
        self.max_leverage = 20  # Max leverage
        self.max_position_size = 0.3  # 30% max position size
        self.max_correlation = 0.7  # Max correlation between positions
        
        # Tracking
        self.daily_pnl = 0.0
        self.total_pnl = 0.0
        self.max_equity = 0.0
        self.current_drawdown = 0.0
        self.positions = {}
        self.trade_history = []
        self.risk_events = []
        
        # Volatility tracking
        self.price_history = {}
        self.volatility_window = 20
        
        # Emergency stop
        self.emergency_stop_triggered = False
        self.emergency_stop_reason = None
    
    @handle_async_exceptions()
    async def validate_trade(self, symbol: str, side: str, size: float, 
                           price: float, leverage: int = 1) -> Tuple[bool, str]:
        """Validate a trade before execution"""
        try:
            # Basic validation
            if size <= 0:
                raise ValidationError("Trade size must be positive", field_name="size", field_value=size)
            
            if leverage < 1 or leverage > self.max_leverage:
                raise ValidationError(
                    f"Leverage must be between 1 and {self.max_leverage}",
                    field_name="leverage", field_value=leverage
                )
            
            # Check emergency stop
            if self.emergency_stop_triggered:
                return False, f"Emergency stop active: {self.emergency_stop_reason}"
            
            # Risk checks
            portfolio_value = await self._get_portfolio_value()
            if portfolio_value <= 0:
                return False, "Portfolio value is zero or negative"
            
            # Position size check
            position_value = size * price * leverage
            position_percentage = position_value / portfolio_value
            
            if position_percentage > self.max_position_size:
                return False, f"Position size {position_percentage:.2%} exceeds maximum {self.max_position_size:.2%}"
            
            # Portfolio risk check
            risk_amount = position_value * self.max_portfolio_risk
            if risk_amount > portfolio_value * self.max_portfolio_risk:
                return False, f"Trade risk exceeds maximum portfolio risk of {self.max_portfolio_risk:.2%}"
            
            # Daily loss check
            if self.daily_pnl < -portfolio_value * self.max_daily_loss:
                return False, f"Daily loss limit of {self.max_daily_loss:.2%} exceeded"
            
            # Drawdown check
            if self.current_drawdown > self.max_drawdown:
                return False, f"Maximum drawdown of {self.max_drawdown:.2%} exceeded"
            
            # Symbol-specific checks
            symbol_limits = self.config.POSITION_SIZE_RANGE.get(symbol, {})
            if symbol_limits:
                max_symbol_size = symbol_limits.get('max', 0.1)
                if position_percentage > max_symbol_size:
                    return False, f"Position size for {symbol} exceeds maximum {max_symbol_size:.2%}"
            
            # Leverage check for symbol
            max_symbol_leverage = self.config.LEVERAGE.get(symbol, 1)
            if leverage > max_symbol_leverage:
                return False, f"Leverage {leverage} exceeds maximum {max_symbol_leverage} for {symbol}"
            
            # Correlation check
            correlation_risk = await self._calculate_correlation_risk(symbol, position_value)
            if correlation_risk > self.max_correlation:
                return False, f"Correlation risk {correlation_risk:.2f} exceeds maximum {self.max_correlation}"
            
            return True, "Trade validated successfully"
            
        except Exception as e:
            self.logger.error(f"Error validating trade: {e}")
            return False, f"Validation error: {str(e)}"
    
    @handle_async_exceptions()
    async def calculate_position_size(self, symbol: str, risk_percentage: float, 
                                    entry_price: float, stop_loss: float,
                                    portfolio_value: float) -> float:
        """Calculate optimal position size based on risk"""
        try:
            if risk_percentage <= 0 or risk_percentage > self.max_portfolio_risk:
                risk_percentage = self.max_portfolio_risk
            
            # Calculate risk amount
            risk_amount = portfolio_value * risk_percentage
            
            # Calculate price difference
            price_diff = abs(entry_price - stop_loss)
            if price_diff == 0:
                price_diff = entry_price * 0.02  # 2% default stop loss
            
            # Calculate position size
            position_size = risk_amount / price_diff
            
            # Apply symbol-specific limits
            symbol_limits = self.config.POSITION_SIZE_RANGE.get(symbol, {})
            if symbol_limits:
                max_size = portfolio_value * symbol_limits.get('max', 0.1) / entry_price
                position_size = min(position_size, max_size)
            
            # Apply leverage
            leverage = self.config.LEVERAGE.get(symbol, 1)
            max_position_with_leverage = portfolio_value * self.max_position_size / entry_price * leverage
            position_size = min(position_size, max_position_with_leverage)
            
            return max(0, position_size)
            
        except Exception as e:
            self.logger.error(f"Error calculating position size: {e}")
            return 0
    
    @handle_async_exceptions()
    async def update_position(self, symbol: str, side: str, size: float, 
                            price: float, leverage: int = 1):
        """Update position in risk tracking"""
        try:
            position_key = f"{symbol}_{side}"
            
            if position_key in self.positions:
                # Update existing position
                pos = self.positions[position_key]
                total_size = pos['size'] + size
                avg_price = (pos['entry_price'] * pos['size'] + price * size) / total_size
                
                self.positions[position_key].update({
                    'size': total_size,
                    'entry_price': avg_price,
                    'last_update': datetime.utcnow()
                })
            else:
                # New position
                self.positions[position_key] = {
                    'symbol': symbol,
                    'side': side,
                    'size': size,
                    'entry_price': price,
                    'leverage': leverage,
                    'opened_at': datetime.utcnow(),
                    'last_update': datetime.utcnow()
                }
            
            # Update risk metrics
            await self._update_risk_metrics()
            
        except Exception as e:
            self.logger.error(f"Error updating position: {e}")
    
    @handle_async_exceptions()
    async def close_position(self, symbol: str, side: str, size: float, price: float):
        """Close or reduce position"""
        try:
            position_key = f"{symbol}_{side}"
            
            if position_key in self.positions:
                pos = self.positions[position_key]
                
                if size >= pos['size']:
                    # Close entire position
                    pnl = self._calculate_pnl(pos, price)
                    self._record_trade(pos, price, pnl)
                    del self.positions[position_key]
                else:
                    # Reduce position
                    pnl = self._calculate_pnl_partial(pos, price, size)
                    self._record_trade(pos, price, pnl, size)
                    self.positions[position_key]['size'] -= size
                
                await self._update_risk_metrics()
            
        except Exception as e:
            self.logger.error(f"Error closing position: {e}")
    
    def _calculate_pnl(self, position: Dict, exit_price: float) -> float:
        """Calculate PnL for position"""
        size = position['size']
        entry_price = position['entry_price']
        leverage = position.get('leverage', 1)
        
        if position['side'] == 'long':
            pnl = (exit_price - entry_price) * size * leverage
        else:
            pnl = (entry_price - exit_price) * size * leverage
        
        return pnl
    
    def _calculate_pnl_partial(self, position: Dict, exit_price: float, close_size: float) -> float:
        """Calculate PnL for partial position close"""
        entry_price = position['entry_price']
        leverage = position.get('leverage', 1)
        
        if position['side'] == 'long':
            pnl = (exit_price - entry_price) * close_size * leverage
        else:
            pnl = (entry_price - exit_price) * close_size * leverage
        
        return pnl
    
    def _record_trade(self, position: Dict, exit_price: float, pnl: float, size: Optional[float] = None):
        """Record completed trade"""
        trade_record = {
            'symbol': position['symbol'],
            'side': position['side'],
            'size': size or position['size'],
            'entry_price': position['entry_price'],
            'exit_price': exit_price,
            'pnl': pnl,
            'leverage': position.get('leverage', 1),
            'opened_at': position['opened_at'],
            'closed_at': datetime.utcnow(),
            'duration': datetime.utcnow() - position['opened_at']
        }
        
        self.trade_history.append(trade_record)
        self.total_pnl += pnl
        
        # Update daily PnL
        today = datetime.utcnow().date()
        if not hasattr(self, 'last_pnl_date') or self.last_pnl_date != today:
            self.daily_pnl = 0
            self.last_pnl_date = today
        
        self.daily_pnl += pnl
    
    async def _get_portfolio_value(self) -> float:
        """Get current portfolio value"""
        # This would typically fetch from exchange or database
        # For now, return a default value
        return 10000.0  # $10,000 default
    
    async def _calculate_correlation_risk(self, symbol: str, position_value: float) -> float:
        """Calculate correlation risk with existing positions"""
        if not self.positions:
            return 0.0
        
        # Simplified correlation calculation
        # In production, this would use historical price data
        correlation_symbols = set()
        for pos_key, pos in self.positions.items():
            correlation_symbols.add(pos['symbol'])
        
        if symbol in correlation_symbols:
            return 0.8  # High correlation with existing position
        
        # Check for related symbols (e.g., BTC-ETH correlation)
        related_pairs = {
            'BTCUSDT': ['ETHUSDT'],
            'ETHUSDT': ['BTCUSDT'],
            'XRPUSDT': []
        }
        
        related = related_pairs.get(symbol, [])
        for related_symbol in related:
            if any(pos['symbol'] == related_symbol for pos in self.positions.values()):
                return 0.6  # Medium correlation
        
        return 0.2  # Low correlation
    
    async def _update_risk_metrics(self):
        """Update all risk metrics"""
        try:
            portfolio_value = await self._get_portfolio_value()
            
            # Calculate portfolio risk
            total_exposure = sum(
                pos['size'] * pos['entry_price'] * pos.get('leverage', 1)
                for pos in self.positions.values()
            )
            portfolio_risk = total_exposure / portfolio_value if portfolio_value > 0 else 0
            
            # Calculate drawdown
            if portfolio_value > self.max_equity:
                self.max_equity = portfolio_value
            
            self.current_drawdown = (self.max_equity - portfolio_value) / self.max_equity if self.max_equity > 0 else 0
            
            # Calculate other metrics
            leverage_risk = self._calculate_leverage_risk()
            concentration_risk = self._calculate_concentration_risk()
            volatility_risk = await self._calculate_volatility_risk()
            
            # Create risk metrics object
            risk_metrics = RiskMetrics(
                portfolio_risk=portfolio_risk,
                leverage_risk=leverage_risk,
                concentration_risk=concentration_risk,
                drawdown_risk=self.current_drawdown,
                volatility_risk=volatility_risk
            )
            
            # Check for emergency stop conditions
            await self._check_emergency_conditions(risk_metrics)
            
            self.logger.info(f"Risk metrics updated - Overall risk: {risk_metrics.overall_risk_level().value}")
            
        except Exception as e:
            self.logger.error(f"Error updating risk metrics: {e}")
    
    def _calculate_leverage_risk(self) -> float:
        """Calculate leverage risk"""
        if not self.positions:
            return 0.0
        
        avg_leverage = np.mean([pos.get('leverage', 1) for pos in self.positions.values()])
        return min(avg_leverage / self.max_leverage, 1.0)
    
    def _calculate_concentration_risk(self) -> float:
        """Calculate concentration risk"""
        if not self.positions:
            return 0.0
        
        # Calculate concentration by symbol
        symbol_exposure = {}
        total_exposure = 0
        
        for pos in self.positions.values():
            symbol = pos['symbol']
            exposure = pos['size'] * pos['entry_price'] * pos.get('leverage', 1)
            symbol_exposure[symbol] = symbol_exposure.get(symbol, 0) + exposure
            total_exposure += exposure
        
        if total_exposure == 0:
            return 0.0
        
        # Calculate concentration ratio (Herfindahl index)
        concentration = sum((exposure / total_exposure) ** 2 for exposure in symbol_exposure.values())
        return concentration
    
    async def _calculate_volatility_risk(self) -> float:
        """Calculate volatility risk"""
        # Simplified volatility calculation
        # In production, this would use historical price data
        return 0.3  # Default medium volatility
    
    async def _check_emergency_conditions(self, risk_metrics: RiskMetrics):
        """Check for emergency stop conditions"""
        emergency_conditions = [
            (risk_metrics.overall_risk_level() == RiskLevel.CRITICAL, "Critical risk level reached"),
            (self.current_drawdown > self.max_drawdown, f"Maximum drawdown {self.max_drawdown:.2%} exceeded"),
            (self.daily_pnl < -await self._get_portfolio_value() * self.max_daily_loss, 
             f"Daily loss limit {self.max_daily_loss:.2%} exceeded"),
            (risk_metrics.leverage_risk > 0.9, "Excessive leverage risk"),
            (risk_metrics.concentration_risk > 0.8, "Excessive concentration risk")
        ]
        
        for condition, reason in emergency_conditions:
            if condition and not self.emergency_stop_triggered:
                await self._trigger_emergency_stop(reason)
                break
    
    async def _trigger_emergency_stop(self, reason: str):
        """Trigger emergency stop"""
        self.emergency_stop_triggered = True
        self.emergency_stop_reason = reason
        
        self.risk_events.append({
            'timestamp': datetime.utcnow(),
            'event_type': 'emergency_stop',
            'reason': reason,
            'portfolio_value': await self._get_portfolio_value(),
            'positions_count': len(self.positions)
        })
        
        self.logger.critical(f"EMERGENCY STOP TRIGGERED: {reason}")
    
    def reset_emergency_stop(self):
        """Reset emergency stop (manual intervention required)"""
        self.emergency_stop_triggered = False
        self.emergency_stop_reason = None
        self.logger.info("Emergency stop reset")
    
    def get_risk_summary(self) -> Dict[str, Any]:
        """Get comprehensive risk summary"""
        return {
            'emergency_stop': self.emergency_stop_triggered,
            'emergency_reason': self.emergency_stop_reason,
            'daily_pnl': self.daily_pnl,
            'total_pnl': self.total_pnl,
            'current_drawdown': self.current_drawdown,
            'positions_count': len(self.positions),
            'total_trades': len(self.trade_history),
            'max_equity': self.max_equity,
            'risk_events': len(self.risk_events)
        }
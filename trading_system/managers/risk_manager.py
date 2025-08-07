"""
Risk Manager
Comprehensive risk management system with dynamic Kelly Criterion
"""

import logging
from datetime import datetime, timedelta
from typing import Dict, List

# Import handling for both direct and package imports
try:
    from ..config.config import TradingConfig
    from ..database.db_manager import EnhancedDatabaseManager
    from ..utils.atr_calculator import ATRCalculator
except ImportError:
    import sys
    import os
    sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    from config.config import TradingConfig
    from database.db_manager import EnhancedDatabaseManager
    from utils.atr_calculator import ATRCalculator


class RiskManager:
    """Comprehensive risk management system with dynamic Kelly Criterion"""
    
    def __init__(self, config: TradingConfig, db: EnhancedDatabaseManager):
        self.config = config
        self.db = db
        self.logger = logging.getLogger(__name__)
        
        # 🔥 ATR 계산기 초기화
        self.atr_calculator = ATRCalculator(config)
        
        # Track risk metrics
        self.risk_metrics = {
            'daily_pnl': 0,
            'weekly_pnl': 0,
            'peak_equity': 0,
            'current_drawdown': 0,
            'correlation_matrix': {}
        }
    
    async def check_risk_limits(self, symbol: str) -> Dict[str, bool]:
        """Check all risk limits before trading"""
        checks = {
            'daily_loss': await self._check_daily_loss_limit(),
            'weekly_loss': await self._check_weekly_loss_limit(),
            'symbol_trades': await self._check_symbol_trade_limits(symbol),
            'position_limits': await self._check_position_limits(symbol),
            'correlation': await self._check_correlation_limits(),
            'drawdown': await self._check_drawdown_limit(),
            'cooldown': await self._check_cooldown_period(symbol),
            'market_conditions': await self._check_market_conditions()
        }
        
        # Overall decision
        can_trade = all(checks.values())
        
        if not can_trade:
            failed_checks = [k for k, v in checks.items() if not v]
            self.logger.warning(f"{symbol} 리스크 체크 실패: {failed_checks}")
            self.db.log_system_event('WARNING', 'RiskManager', 
                                   f"{symbol} 리스크 체크 실패", 
                                   {'failed_checks': failed_checks})
        
        return {
            'can_trade': can_trade,
            'checks': checks
        }
    
    async def _check_daily_loss_limit(self) -> bool:
        """Check if daily loss limit exceeded"""
        today_performance = self.db.get_daily_performance()
        
        if today_performance['total_pnl_percent'] <= -self.config.DAILY_LOSS_LIMIT:
            self.logger.warning(f"일일 손실 한도 도달: {today_performance['total_pnl_percent']:.2%}")
            return False
        
        return True
    
    async def _check_weekly_loss_limit(self) -> bool:
        """Check weekly loss limit"""
        # Get last 7 days performance
        weekly_pnl = 0
        for i in range(7):
            date = (datetime.now() - timedelta(days=i)).strftime('%Y-%m-%d')
            daily_perf = self.db.get_daily_performance(date)
            weekly_pnl += daily_perf.get('total_pnl_percent', 0)
        
        if weekly_pnl <= -self.config.WEEKLY_LOSS_LIMIT:
            self.logger.warning(f"주간 손실 한도 도달: {weekly_pnl:.2%}")
            return False
        
        return True
    
    async def _check_symbol_trade_limits(self, symbol: str) -> bool:
        """Check symbol-specific trade limits"""
        limits = self.config.DAILY_TRADE_LIMITS[symbol]
        today_trades = self.db.get_symbol_trades_today(symbol)
        
        # Check total trades
        if today_trades['total'] >= limits['max_trades']:
            self.logger.warning(f"{symbol} 일일 거래 한도 도달: {today_trades['total']}")
            return False
        
        # Check loss trades
        if today_trades['losses'] >= limits['max_loss_trades']:
            self.logger.warning(f"{symbol} 일일 손실 거래 한도 도달: {today_trades['losses']}")
            return False
        
        return True
    
    async def _check_cooldown_period(self, symbol: str) -> bool:
        """Check if in cooldown period"""
        limits = self.config.DAILY_TRADE_LIMITS[symbol]
        today_trades = self.db.get_symbol_trades_today(symbol)
        
        if today_trades['last_trade']:
            last_trade_time = datetime.fromisoformat(today_trades['last_trade'])
            cooldown_end = last_trade_time + timedelta(minutes=limits['cooldown_minutes'])
            
            if datetime.now() < cooldown_end:
                remaining = (cooldown_end - datetime.now()).seconds / 60
                self.logger.info(f"{symbol} 쿨다운 중 - 남은 시간: {remaining:.1f}분")
                return False
        
        return True
    
    async def _check_position_limits(self, symbol: str) -> bool:
        """Check position limits"""
        open_positions = self.db.get_open_positions(symbol)
        max_positions = self.config.MAX_POSITIONS[symbol]
        
        if len(open_positions) >= max_positions:
            self.logger.warning(f"{symbol} 포지션 한도 도달: {len(open_positions)}")
            return False
        
        return True
    
    async def _check_correlation_limits(self) -> bool:
        """Check correlation between positions"""
        # Get all open positions
        all_positions = self.db.get_open_positions()
        
        if not all_positions:
            return True
        
        # Group by direction
        long_positions = [p for p in all_positions if p['side'] == 'long']
        short_positions = [p for p in all_positions if p['side'] == 'short']
        
        # Simple check: avoid all positions in same direction
        if len(long_positions) >= len(self.config.SYMBOLS) or len(short_positions) >= len(self.config.SYMBOLS):
            self.logger.warning("모든 포지션이 같은 방향 - 상관관계 리스크 회피")
            return False
        
        return True
    
    async def _check_drawdown_limit(self) -> bool:
        """Check maximum drawdown"""
        # This would track peak equity and calculate drawdown
        # For now, simplified implementation
        today_performance = self.db.get_daily_performance()
        
        if today_performance['max_drawdown'] >= self.config.MAX_DRAWDOWN:
            self.logger.warning(f"최대 낙폭 도달: {today_performance['max_drawdown']:.2%}")
            return False
        
        return True
    
    async def _check_market_conditions(self) -> bool:
        """Check overall market conditions"""
        # Could check VIX, funding rates, etc.
        # For now, always return True
        return True
    
    def calculate_position_allocation(self, symbol: str, total_capital: float, 
                                    current_positions: List[Dict]) -> float:
        """Calculate position allocation using Kelly Criterion with full allocated capital"""
        # 💰 OPTIMIZED: Use full allocated capital (already pre-allocated by user)
        max_allowed_capital = total_capital * self.config.MAX_TOTAL_ALLOCATION
        
        # Check current total allocation across all positions (with defensive checks)
        current_total_used = 0
        for pos in current_positions:
            quantity = pos.get('quantity')
            entry_price = pos.get('entry_price')
            
            # Defensive programming: skip invalid positions
            if quantity is None or entry_price is None:
                self.logger.warning(f"⚠️ 유효하지 않은 포지션 데이터 무시: quantity={quantity}, entry_price={entry_price}")
                continue
                
            try:
                # 올바른 선물 포지션 증거금 계산
                symbol = pos.get('symbol', '')
                nominal_value = float(quantity) * float(entry_price)
                
                # 레버리지로 나누어 실제 증거금 계산
                leverage = self.config.LEVERAGE.get(symbol, 10)
                actual_margin = nominal_value / leverage
                
                current_total_used += actual_margin
                
            except (ValueError, TypeError) as e:
                self.logger.warning(f"⚠️ 포지션 값 계산 오류 무시: {e}")
                continue
        
        # Available capital within allocated limit
        available_under_limit = max_allowed_capital - current_total_used
        
        if available_under_limit <= 0:
            self.logger.warning(f"⛔ 할당 자금 한도 초과! 현재 사용: ${current_total_used:.2f}, 한도: ${max_allowed_capital:.2f}")
            return 0
        
        # Base allocation within allocated limit
        symbol_allocation = self.config.PORTFOLIO_WEIGHTS[symbol]
        target_symbol_allocation = max_allowed_capital * symbol_allocation
        
        # Adjust for existing positions (with defensive checks)
        symbol_positions = [p for p in current_positions if p.get('symbol') == symbol]
        used_allocation = 0
        for p in symbol_positions:
            quantity = p.get('quantity')
            entry_price = p.get('entry_price')
            if quantity is not None and entry_price is not None:
                try:
                    # 올바른 선물 포지션 증거금 계산
                    nominal_value = float(quantity) * float(entry_price)
                    leverage = self.config.LEVERAGE.get(symbol, 10)
                    actual_margin = nominal_value / leverage
                    used_allocation += actual_margin
                except (ValueError, TypeError) as e:
                    self.logger.warning(f"⚠️ 심볼 포지션 값 계산 오류: {e}")
                    continue
        
        remaining_allocation = target_symbol_allocation - used_allocation
        
        # Ensure we don't over-allocate
        max_position_size = target_symbol_allocation / self.config.MAX_POSITIONS[symbol]
        
        # Get Kelly fraction from database
        kelly_fraction = self.db.get_kelly_fraction(symbol)
        
        # Apply safety margin (use only 25% of Kelly suggestion)
        safe_kelly = kelly_fraction * self.config.KELLY_FRACTION
        
        # Calculate position size
        kelly_allocation = remaining_allocation * safe_kelly
        
        # Apply additional constraints
        final_allocation = min(
            remaining_allocation, 
            max_position_size, 
            kelly_allocation,
            available_under_limit  # 할당 한도 내에서만
        )
        
        # Log Kelly calculation with allocation limit
        self.logger.info(
            f"💰 {symbol} 자금 할당:\n"
            f"   Kelly 지수: {kelly_fraction:.3f} -> 안전 Kelly: {safe_kelly:.3f}\n" 
            f"   할당 한도: ${max_allowed_capital:.2f} (현재 사용: ${current_total_used:.2f})\n"
            f"   최종 할당: ${final_allocation:.2f}"
        )
        
        return final_allocation
    
    def calculate_tp_sl(self, symbol: str, entry_price: float, direction: str) -> Dict[str, float]:
        """
        ATR 기반 동적 TP/SL 계산
        
        Args:
            symbol: 거래 심볼 (e.g., "BTCUSDT")
            entry_price: 진입가격
            direction: 거래 방향 ("long" or "short")
            
        Returns:
            Dict containing stop_loss, take_profit prices
        """
        try:
            # ATR 설정값 가져오기
            atr_settings = self.config.ATR_SETTINGS_SIMPLE.get(symbol, {})
            if not atr_settings:
                self.logger.warning(f"⚠️ {symbol} ATR 설정 없음, 기본값 사용")
                atr_settings = {"period": 14, "stop_multiplier": 2.0, "profit_multiplier": 3.0}
            
            # ATR 값 계산 (기존 calculator 활용)
            period = int(atr_settings.get("period", 14))
            # 임시로 고정값 사용 (실제로는 candle 데이터가 필요)
            atr_value = entry_price * 0.01  # 1% as placeholder
            
            stop_multiplier = atr_settings.get("stop_multiplier", 2.0)
            profit_multiplier = atr_settings.get("profit_multiplier", 3.0)
            
            # 방향에 따른 TP/SL 계산
            if direction.lower() == "long":
                stop_loss = entry_price - (atr_value * stop_multiplier)
                take_profit = entry_price + (atr_value * profit_multiplier)
            else:  # short
                stop_loss = entry_price + (atr_value * stop_multiplier)
                take_profit = entry_price - (atr_value * profit_multiplier)
            
            # 기존 FALLBACK 설정과 병합 (더 보수적인 값 사용)
            fallback_sl_pct = self.config.FALLBACK_STOP_LOSS.get(symbol, 0.02)
            fallback_tp_pct = self.config.FALLBACK_TAKE_PROFIT.get(symbol, 0.04)
            
            if direction.lower() == "long":
                fallback_sl = entry_price * (1 - fallback_sl_pct)
                fallback_tp = entry_price * (1 + fallback_tp_pct)
                # 더 보수적인 값 선택
                final_sl = max(stop_loss, fallback_sl)
                final_tp = min(take_profit, fallback_tp)
            else:  # short
                fallback_sl = entry_price * (1 + fallback_sl_pct)
                fallback_tp = entry_price * (1 - fallback_tp_pct)
                # 더 보수적인 값 선택
                final_sl = min(stop_loss, fallback_sl)
                final_tp = max(take_profit, fallback_tp)
            
            result = {
                "stop_loss": final_sl,
                "take_profit": final_tp,
                "atr_value": atr_value,
                "stop_multiplier": stop_multiplier,
                "profit_multiplier": profit_multiplier
            }
            
            self.logger.debug(f"📊 {symbol} TP/SL 계산 완료: ATR={atr_value:.6f}, SL={final_sl:.6f}, TP={final_tp:.6f}")
            return result
            
        except Exception as e:
            self.logger.error(f"❌ {symbol} TP/SL 계산 오류: {e}", exc_info=True)
            # 오류 시 기본값 반환
            fallback_sl_pct = self.config.FALLBACK_STOP_LOSS.get(symbol, 0.02)
            fallback_tp_pct = self.config.FALLBACK_TAKE_PROFIT.get(symbol, 0.04)
            
            if direction.lower() == "long":
                return {
                    "stop_loss": entry_price * (1 - fallback_sl_pct),
                    "take_profit": entry_price * (1 + fallback_tp_pct),
                    "atr_value": 0,
                    "stop_multiplier": 0,
                    "profit_multiplier": 0
                }
            else:
                return {
                    "stop_loss": entry_price * (1 + fallback_sl_pct),
                    "take_profit": entry_price * (1 - fallback_tp_pct),
                    "atr_value": 0,
                    "stop_multiplier": 0,
                    "profit_multiplier": 0
                }
    
    def update_kelly_after_trade(self, symbol: str, trade_pnl_percent: float):
        """Update Kelly tracking after trade closes"""
        self.db.update_kelly_tracking(symbol, trade_pnl_percent)
    
    def get_current_total_allocation_ratio(self, total_capital: float, current_positions: List[Dict]) -> float:
        """현재 총 자금 사용 비율 계산 (defensive)"""
        current_total_used = 0
        for pos in current_positions:
            quantity = pos.get('quantity')
            entry_price = pos.get('entry_price')
            
            if quantity is not None and entry_price is not None:
                try:
                    # 올바른 선물 포지션 증거금 계산
                    symbol = pos.get('symbol', '')
                    nominal_value = float(quantity) * float(entry_price)
                    leverage = self.config.LEVERAGE.get(symbol, 10)
                    actual_margin = nominal_value / leverage
                    current_total_used += actual_margin
                except (ValueError, TypeError) as e:
                    self.logger.warning(f"⚠️ 할당 비율 계산 중 포지션 오류 무시: {e}")
                    continue
                    
        return current_total_used / total_capital if total_capital > 0 else 0
    
    def check_allocation_limit(self, total_capital: float, current_positions: List[Dict], 
                              requested_amount: float) -> Dict[str, any]:
        """할당 자금 한도 체크 (defensive)"""
        max_allowed = total_capital * self.config.MAX_TOTAL_ALLOCATION
        
        # Safe calculation of current used capital
        current_used = 0
        for pos in current_positions:
            quantity = pos.get('quantity')
            entry_price = pos.get('entry_price')
            
            if quantity is not None and entry_price is not None:
                try:
                    # 올바른 선물 포지션 증거금 계산
                    symbol = pos.get('symbol', '')
                    nominal_value = float(quantity) * float(entry_price)
                    leverage = self.config.LEVERAGE.get(symbol, 10)
                    actual_margin = nominal_value / leverage
                    current_used += actual_margin
                except (ValueError, TypeError) as e:
                    self.logger.warning(f"⚠️ 할당 한도 체크 중 포지션 오류 무시: {e}")
                    continue
        
        would_exceed = (current_used + requested_amount) > max_allowed
        
        return {
            'within_limit': not would_exceed,
            'current_used': current_used,
            'max_allowed': max_allowed,
            'current_ratio': current_used / total_capital if total_capital > 0 else 0,
            'would_be_ratio': (current_used + requested_amount) / total_capital if total_capital > 0 else 0,
            'available': max_allowed - current_used
        }
    
    # 🔥 ATR 기반 동적 손절/익절 시스템
    def calculate_position_stops(self, symbol: str, entry_price: float, 
                                position_side: str, recent_candles: List[Dict]) -> Dict[str, float]:
        """ATR 기반 포지션별 동적 손절/익절 계산"""
        try:
            # ATR 계산
            atr_period = self.config.ATR_SETTINGS[symbol]['period']
            current_atr = self.atr_calculator.calculate_atr(recent_candles, atr_period)
            
            if current_atr <= 0 or not self.atr_calculator.validate_atr_quality(current_atr, recent_candles):
                self.logger.warning(f"⚠️ {symbol} ATR 품질 불량, 폴백 모드 사용")
                return self._get_fallback_stops(symbol, entry_price, position_side)
            
            # 동적 손절/익절 계산
            stops = self.atr_calculator.calculate_dynamic_stops(
                symbol, entry_price, current_atr, position_side
            )
            
            # 레버리지 검증
            if not self.validate_stop_levels_with_leverage(symbol, stops['stop_distance_pct']):
                # 손절 거리 조정
                stops = self.adjust_stops_for_leverage(symbol, stops, entry_price, position_side)
            
            # 상세 로깅
            self.logger.info(
                f"💎 {symbol} ATR 기반 손절/익절 설정:\n"
                f"   현재 ATR: ${current_atr:.6f}\n"
                f"   손절 거리: {stops['stop_distance_pct']:.2f}%\n"
                f"   익절 거리: {stops['profit_distance_pct']:.2f}%\n"
                f"   손절가: ${stops['stop_loss']:.6f}\n"
                f"   익절가: ${stops['take_profit']:.6f}\n"
                f"   R:R 비율: 1:{stops['profit_distance_pct']/max(stops['stop_distance_pct'], 0.001):.1f}"
            )
            
            return stops
            
        except Exception as e:
            self.logger.error(f"ATR 손절/익절 계산 오류: {e}")
            return self._get_fallback_stops(symbol, entry_price, position_side)
    
    def validate_stop_levels_with_leverage(self, symbol: str, stop_distance_pct: float) -> bool:
        """레버리지 대비 손절 거리 검증"""
        try:
            leverage = self.config.LEVERAGE[symbol]
            max_allowed_loss = 0.8  # 포지션의 80%까지만 손실 허용
            
            # 레버리지 고려한 실제 손실률
            actual_loss_rate = (stop_distance_pct / 100) * leverage
            
            if actual_loss_rate > max_allowed_loss:
                self.logger.warning(
                    f"⚠️ {symbol} 손절 거리 과도함:\n"
                    f"   레버리지: {leverage}x\n"
                    f"   손절 거리: {stop_distance_pct:.2f}%\n"
                    f"   실제 손실률: {actual_loss_rate:.1%} (한도: {max_allowed_loss:.1%})"
                )
                return False
            
            self.logger.debug(f"✅ {symbol} 손절 거리 검증 통과: {actual_loss_rate:.1%}")
            return True
            
        except Exception as e:
            self.logger.error(f"손절 거리 검증 오류: {e}")
            return False
    
    def adjust_stops_for_leverage(self, symbol: str, original_stops: Dict[str, float], 
                                 entry_price: float, position_side: str) -> Dict[str, float]:
        """레버리지 고려한 손절 거리 조정"""
        try:
            leverage = self.config.LEVERAGE[symbol]
            max_allowed_loss = 0.7  # 70%로 더 보수적 설정
            
            # 최대 허용 손절 거리 계산
            max_stop_distance_pct = (max_allowed_loss / leverage) * 100
            
            # 조정된 손절 거리
            adjusted_stop_distance_pct = min(original_stops['stop_distance_pct'], max_stop_distance_pct)
            
            # 조정된 손절가 계산
            if position_side.lower() in ['long', 'buy']:
                adjusted_stop_loss = entry_price * (1 - adjusted_stop_distance_pct / 100)
            else:
                adjusted_stop_loss = entry_price * (1 + adjusted_stop_distance_pct / 100)
            
            # 익절은 기존 유지 또는 비례 조정
            profit_ratio = original_stops['profit_distance_pct'] / original_stops['stop_distance_pct']
            adjusted_profit_distance_pct = adjusted_stop_distance_pct * profit_ratio
            
            if position_side.lower() in ['long', 'buy']:
                adjusted_take_profit = entry_price * (1 + adjusted_profit_distance_pct / 100)
            else:
                adjusted_take_profit = entry_price * (1 - adjusted_profit_distance_pct / 100)
            
            adjusted_stops = {
                'stop_loss': round(adjusted_stop_loss, 8),
                'take_profit': round(adjusted_take_profit, 8),
                'stop_distance_pct': round(adjusted_stop_distance_pct, 3),
                'profit_distance_pct': round(adjusted_profit_distance_pct, 3),
                'atr_value': original_stops.get('atr_value', 0.0)
            }
            
            self.logger.info(
                f"🔧 {symbol} 레버리지 조정:\n"
                f"   원본 손절: {original_stops['stop_distance_pct']:.2f}% → "
                f"조정 손절: {adjusted_stop_distance_pct:.2f}%\n"
                f"   실제 손실률: {(adjusted_stop_distance_pct/100)*leverage:.1%}"
            )
            
            return adjusted_stops
            
        except Exception as e:
            self.logger.error(f"손절 조정 오류: {e}")
            return original_stops
    
    def _get_fallback_stops(self, symbol: str, entry_price: float, position_side: str) -> Dict[str, float]:
        """ATR 실패 시 폴백 손절/익절"""
        try:
            stop_pct = self.config.FALLBACK_STOP_LOSS[symbol]
            profit_pct = self.config.FALLBACK_TAKE_PROFIT[symbol]
            
            if position_side.lower() in ['long', 'buy']:
                stop_loss = entry_price * (1 - stop_pct)
                take_profit = entry_price * (1 + profit_pct)
            else:
                stop_loss = entry_price * (1 + stop_pct)
                take_profit = entry_price * (1 - profit_pct)
            
            self.logger.warning(
                f"⚠️ {symbol} 폴백 손절/익절 적용: {stop_pct:.1%}/{profit_pct:.1%}"
            )
            
            return {
                'stop_loss': round(stop_loss, 8),
                'take_profit': round(take_profit, 8),
                'stop_distance_pct': round(stop_pct * 100, 3),
                'profit_distance_pct': round(profit_pct * 100, 3),
                'atr_value': 0.0
            }
            
        except Exception as e:
            self.logger.error(f"폴백 손절/익절 계산 오류: {e}")
            # 최후 폴백
            return {
                'stop_loss': entry_price * 0.99 if position_side.lower() in ['long', 'buy'] else entry_price * 1.01,
                'take_profit': entry_price * 1.02 if position_side.lower() in ['long', 'buy'] else entry_price * 0.98,
                'stop_distance_pct': 1.0,
                'profit_distance_pct': 2.0,
                'atr_value': 0.0
            }
    
    def update_trailing_stop(self, position: Dict, current_price: float) -> Dict[str, any]:
        """개선된 ATR 기반 트레일링 스톱 로직"""
        try:
            symbol = position['symbol']
            entry_price = position['entry_price']
            position_side = position['side']
            
            # 현재 수익률 계산
            if position_side.lower() in ['long', 'buy']:
                profit_pct = (current_price - entry_price) / entry_price
            else:
                profit_pct = (entry_price - current_price) / entry_price
            
            trailing_config = self.config.TRAILING_STOP[symbol]
            
            # 낮아진 활성화 조건 확인 (1%/1.5%)
            if profit_pct >= trailing_config['activate']:
                # 트레일링 스톱 계산
                trailing_distance = current_price * trailing_config['distance']
                
                if position_side.lower() in ['long', 'buy']:
                    new_stop = current_price - trailing_distance
                    # 기존 손절보다 높을 때만 업데이트
                    if new_stop > position.get('stop_loss', 0):
                        profit_locked = profit_pct - trailing_config['distance']
                        self.logger.info(
                            f"📈 {symbol} 트레일링 스톱 업데이트: "
                            f"${position.get('stop_loss', 0):.6f} → ${new_stop:.6f} "
                            f"(수익 확정: {profit_locked:.1%})"
                        )
                        return {
                            'update': True,
                            'new_stop': new_stop,
                            'profit_locked': profit_locked
                        }
                else:
                    new_stop = current_price + trailing_distance
                    if new_stop < position.get('stop_loss', float('inf')):
                        profit_locked = profit_pct - trailing_config['distance']
                        self.logger.info(
                            f"📉 {symbol} 트레일링 스톱 업데이트: "
                            f"${position.get('stop_loss', float('inf')):.6f} → ${new_stop:.6f} "
                            f"(수익 확정: {profit_locked:.1%})"
                        )
                        return {
                            'update': True,
                            'new_stop': new_stop,
                            'profit_locked': profit_locked
                        }
            
            return {'update': False}
            
        except Exception as e:
            self.logger.error(f"트레일링 스톱 업데이트 오류: {e}")
            return {'update': False}
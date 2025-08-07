"""
Position Manager
Advanced position management with complete trailing stop implementation
"""

import asyncio
import json
import logging
import numpy as np
from datetime import datetime
from typing import Dict, List, Optional

# Import handling for both direct and package imports
try:
    from ..config.config import TradingConfig
    from ..database.db_manager import EnhancedDatabaseManager
    from .risk_manager import RiskManager
except ImportError:
    import sys
    import os
    sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    from config.config import TradingConfig
    from database.db_manager import EnhancedDatabaseManager
    from managers.risk_manager import RiskManager


class PositionManager:
    """Advanced position management with complete trailing stop implementation"""
    
    def __init__(self, config: TradingConfig, exchange, db: EnhancedDatabaseManager, notifier=None):
        self.config = config
        self.exchange = exchange
        self.db = db
        self.notifier = notifier
        self.logger = logging.getLogger(__name__)
        
        # Initialize RiskManager instance
        self.risk_manager = RiskManager(config, db)
        
        # Track positions in memory for faster access
        self.active_positions = {}
        self._position_lock = asyncio.Lock()
    
    async def initialize(self):
        """Initialize position manager (async compatibility)"""
        # Already initialized in __init__, this is for compatibility
        return True
    
    async def open_position(self, symbol: str, signal: Dict, allocated_capital: float) -> Optional[Dict]:
        """Open a new position with comprehensive checks"""
        async with self._position_lock:
            try:
                # Double-check risk limits
                current_positions = self.db.get_open_positions(symbol)
                if len(current_positions) >= self.config.MAX_POSITIONS[symbol]:
                    self.logger.warning(f"{symbol} 포지션 한도 도달")
                    return None
                
                # Calculate position size with slippage consideration
                size_ratio = self._calculate_position_size_ratio(symbol, signal)
                
                # 🔥 CRITICAL: Enhanced defensive programming for None values
                if size_ratio is None:
                    self.logger.error(f"❌ {symbol} size_ratio가 None입니다")
                    return None
                    
                if allocated_capital is None:
                    self.logger.error(f"❌ {symbol} allocated_capital이 None입니다")
                    return None
                
                # Additional type and value checks
                try:
                    size_ratio = float(size_ratio)
                    allocated_capital = float(allocated_capital)
                    
                    if size_ratio <= 0:
                        self.logger.error(f"❌ {symbol} 잘못된 size_ratio: {size_ratio}")
                        return None
                        
                    if allocated_capital <= 0:
                        self.logger.error(f"❌ {symbol} 잘못된 allocated_capital: {allocated_capital}")
                        return None
                        
                except (ValueError, TypeError) as e:
                    self.logger.error(f"❌ {symbol} 포지션 파라미터 변환 오류: size_ratio={size_ratio}, allocated_capital={allocated_capital}, error={e}")
                    return None
                
                position_value = allocated_capital * size_ratio
                self.logger.info(f"💰 {symbol} 포지션 값 계산: ${allocated_capital:.2f} × {size_ratio:.3f} = ${position_value:.2f}")
                
                # Account for fees
                taker_fee = float(self.config.TAKER_FEE or 0.0006)  # Default 0.06%
                position_value *= (1 - taker_fee)
                
                # Get contract size
                contracts = await self.exchange.calculate_position_size(symbol, position_value)
                
                if contracts <= 0:
                    self.logger.warning(f"{symbol} 잘못된 포지션 크기")
                    return None
                
                # Place order
                side = 'buy' if signal['direction'] == 'long' else 'sell'
                order = await self.exchange.place_order(symbol, side, contracts)
                
                if not order or not order.get('id'):
                    self.logger.error(f"{symbol} 주문 실행 실패")
                    return None
                
                # Get fill details
                fill_price = order.get('price') or order.get('average', 0)
                actual_contracts = order.get('filled', contracts)
                
                # Calculate fees
                fees = position_value * self.config.TAKER_FEE
                slippage = order.get('slippage', 0)
                
                # Get Kelly fraction used
                kelly_fraction = self.db.get_kelly_fraction(symbol)
                
                # 🔥 ATR 기반 동적 손절/익절 계산
                dynamic_stops = await self._calculate_dynamic_stops(symbol, fill_price, side)
                stop_loss = dynamic_stops['stop_loss']
                take_profit = dynamic_stops['take_profit']
                
                # Save to database
                trade_data = {
                    'symbol': symbol,
                    'side': side,
                    'price': fill_price,
                    'quantity': actual_contracts,
                    'leverage': self.config.LEVERAGE[symbol],
                    'order_id': order.get('id'),
                    'status': 'open',
                    'reason': f"시그널: {signal['score']:.2f}, 신뢰도: {signal['confidence']:.1f}%",
                    'multi_tf_score': signal.get('alignment_score', 0),
                    'regime': signal.get('regime', 'unknown'),
                    'entry_signal_strength': signal['score'],
                    'fees_paid': fees,
                    'slippage': slippage,
                    # 🔥 ATR 정보 추가
                    'atr_value': dynamic_stops.get('atr_value', 0.0),
                    'stop_distance_pct': dynamic_stops.get('stop_distance_pct', 0.0),
                    'profit_distance_pct': dynamic_stops.get('profit_distance_pct', 0.0),
                    'kelly_fraction': kelly_fraction
                }
                
                trade_id = self.db.save_trade(trade_data)
                
                # Save position
                position_data = {
                    'symbol': symbol,
                    'trade_id': trade_id,
                    'entry_price': fill_price,
                    'quantity': actual_contracts,
                    'side': side,
                    'stop_loss': stop_loss,
                    'take_profit': json.dumps(take_profit)
                }
                
                position_id = self.db.save_position(position_data)
                
                # Place stop loss order
                sl_side = 'sell' if side == 'buy' else 'buy'
                sl_order = await self.exchange.place_stop_loss_order(
                    symbol, sl_side, actual_contracts, stop_loss
                )
                
                if sl_order and sl_order.get('id'):
                    self.db.update_position(position_id, {'stop_order_id': sl_order['id']})
                
                # Track in memory
                self.active_positions[position_id] = {
                    'symbol': symbol,
                    'position_id': position_id,
                    'trade_id': trade_id,
                    'entry_price': fill_price,
                    'side': side,
                    'quantity': actual_contracts,
                    'stop_loss': stop_loss,
                    'take_profit': take_profit,
                    'max_profit': 0,
                    'trailing_active': False
                }
                
                self.logger.info(
                    f"✅ 포지션 개시: {symbol} {side} {actual_contracts} @ {fill_price} "
                    f"(손절: {stop_loss:.2f}, 익절: {take_profit[0]['price'] if take_profit else 'None'})"
                )
                
                # Log to system
                self.db.log_system_event(
                    'INFO', 'PositionManager', 
                    f"포지션 개시: {symbol} {side}",
                    {'trade_id': trade_id, 'position_id': position_id, 'signal': signal}
                )
                
                return {
                    'trade_id': trade_id,
                    'position_id': position_id,
                    'order': order,
                    'position_data': self.active_positions[position_id]
                }
                
            except Exception as e:
                self.logger.error(f"포지션 개시 오류: {e}")
                self.db.log_system_event('ERROR', 'PositionManager', 
                                       f"{symbol} 포지션 개시 실패", 
                                       {'error': str(e)})
                return None
    
    async def manage_positions(self):
        """Manage all open positions with enhanced logic"""
        positions = self.db.get_open_positions()
        
        if not positions:
            return
        
        # Update active positions cache
        await self._sync_active_positions(positions)
        
        # Process each position
        tasks = []
        for position in positions:
            task = asyncio.create_task(self._manage_single_position(position))
            tasks.append(task)
        
        # Execute position management in parallel
        await asyncio.gather(*tasks, return_exceptions=True)
    
    async def _sync_active_positions(self, db_positions: List[Dict]):
        """Sync in-memory positions with database"""
        db_position_ids = {p['id'] for p in db_positions}
        memory_position_ids = set(self.active_positions.keys())
        
        # Remove closed positions from memory
        for pos_id in memory_position_ids - db_position_ids:
            del self.active_positions[pos_id]
        
        # Add new positions to memory
        for pos in db_positions:
            if pos['id'] not in self.active_positions:
                self.active_positions[pos['id']] = {
                    'symbol': pos['symbol'],
                    'position_id': pos['id'],
                    'trade_id': pos['trade_id'],
                    'entry_price': pos['entry_price'],
                    'side': pos['side'],
                    'quantity': pos['quantity'],
                    'stop_loss': pos['stop_loss'],
                    'take_profit': json.loads(pos.get('take_profit', '[]')),
                    'max_profit': pos.get('max_profit', 0),
                    'trailing_active': pos.get('trailing_stop_active', False)
                }
    
    async def _manage_single_position(self, position: Dict):
        """Manage a single position with complete logic"""
        try:
            symbol = position['symbol']
            position_id = position['id']
            
            # Get current price
            current_price = self.exchange.get_current_price(symbol)
            if not current_price:
                ticker = await self.exchange.exchange.fetch_ticker(
                    self.exchange._format_symbol(symbol)
                )
                current_price = ticker['last']
            
            # Update position in database
            self.db.update_position(position_id, {'current_price': current_price})
            
            # Calculate P&L
            pnl_data = self._calculate_pnl(position, current_price)
            
            # Update max profit
            if pnl_data['pnl_percent'] > position.get('max_profit', 0):
                self.db.update_position(position_id, {'max_profit': pnl_data['pnl_percent']})
                if position_id in self.active_positions:
                    self.active_positions[position_id]['max_profit'] = pnl_data['pnl_percent']
            
            # Check for trailing stop
            await self._manage_trailing_stop(position, current_price, pnl_data)
            
            # Check for partial take profits
            await self._check_take_profit(position, current_price, pnl_data)
            
            # Check stop loss
            if self._should_stop_loss(position, current_price):
                await self._close_position(position, '손절', current_price)
                return
            
            # Check for position timeout (optional)
            if self._should_timeout_position(position):
                await self._close_position(position, '시간초과', current_price)
                return
            
            # Check for adverse movement
            if self._should_cut_loss_early(position, pnl_data):
                await self._close_position(position, '조기손절', current_price)
                return
                
        except Exception as e:
            self.logger.error(f"포지션 {position_id} 관리 오류: {e}")
            self.db.log_system_event('ERROR', 'PositionManager',
                                   f"{symbol} 포지션 관리 오류",
                                   {'position_id': position_id, 'error': str(e)})
    
    def _calculate_pnl(self, position: Dict, current_price: float) -> Dict:
        """Calculate position P&L with fees"""
        entry_price = position.get('entry_price')
        quantity = position.get('quantity')
        side = position.get('side')
        
        # Validate required fields
        if entry_price is None or quantity is None or side is None:
            self.logger.warning(f"포지션 데이터 불완전: entry_price={entry_price}, quantity={quantity}, side={side}")
            return {
                'pnl_value': 0.0,
                'pnl_percent': 0.0,
                'unrealized_pnl': 0.0
            }
        
        if side == 'long':
            price_change = (current_price - entry_price) / entry_price
        else:
            price_change = (entry_price - current_price) / entry_price
        
        # Account for fees (entry + potential exit)
        total_fees = self.config.TAKER_FEE * 2
        pnl_percent = price_change - total_fees
        pnl_value = pnl_percent * quantity * entry_price
        
        return {
            'pnl_value': pnl_value,
            'pnl_percent': pnl_percent,
            'price_change': price_change,
            'current_price': current_price
        }
    
    async def _manage_trailing_stop(self, position: Dict, current_price: float, pnl_data: Dict):
        """Manage trailing stop with enhanced logic"""
        symbol = position['symbol']
        position_id = position['id']
        trailing_config = self.config.TRAILING_STOP[symbol]
        
        # Check if we should activate trailing stop
        if (pnl_data['pnl_percent'] >= trailing_config['activate'] and 
            not position.get('trailing_stop_active', False)):
            
            await self._activate_trailing_stop(position, current_price, trailing_config)
            
        elif position.get('trailing_stop_active', False):
            # Update trailing stop if price moved favorably
            await self._update_trailing_stop(position, current_price, trailing_config)
            
            # Check if trailing stop would be hit
            if self._check_trailing_stop_hit(position, current_price):
                await self._close_position(position, '추적손절', current_price)
    
    async def _activate_trailing_stop(self, position: Dict, current_price: float, config: Dict):
        """Activate trailing stop"""
        side = position['side']
        distance = config['distance']
        
        if side == 'long':
            trailing_stop_price = current_price * (1 - distance)
        else:
            trailing_stop_price = current_price * (1 + distance)
        
        # Ensure trailing stop is better than original stop loss
        original_sl = position['stop_loss']
        if side == 'long' and trailing_stop_price <= original_sl:
            return
        if side == 'short' and trailing_stop_price >= original_sl:
            return
        
        # Update database
        self.db.update_position(position['id'], {
            'trailing_stop_active': True,
            'trailing_stop_price': trailing_stop_price,
            'stop_loss': trailing_stop_price
        })
        
        # Update stop order on exchange
        if position.get('stop_order_id'):
            await self.exchange.modify_stop_loss(
                position['symbol'],
                position['stop_order_id'],
                trailing_stop_price
            )
        
        # Update memory
        if position['id'] in self.active_positions:
            self.active_positions[position['id']]['trailing_active'] = True
            self.active_positions[position['id']]['stop_loss'] = trailing_stop_price
        
        self.logger.info(
            f"📈 추적손절 활성화: {position['symbol']} @ {trailing_stop_price:.2f}"
        )
    
    async def _update_trailing_stop(self, position: Dict, current_price: float, config: Dict):
        """Update trailing stop if price moved favorably"""
        side = position['side']
        distance = config['distance']
        current_trailing = position.get('trailing_stop_price', position['stop_loss'])
        
        if side == 'long':
            new_trailing = current_price * (1 - distance)
            if new_trailing > current_trailing:
                await self._set_new_trailing_stop(position, new_trailing)
        else:
            new_trailing = current_price * (1 + distance)
            if new_trailing < current_trailing:
                await self._set_new_trailing_stop(position, new_trailing)
    
    async def _set_new_trailing_stop(self, position: Dict, new_stop_price: float):
        """Set new trailing stop price"""
        self.db.update_position(position['id'], {
            'trailing_stop_price': new_stop_price,
            'stop_loss': new_stop_price
        })
        
        if position.get('stop_order_id'):
            await self.exchange.modify_stop_loss(
                position['symbol'],
                position['stop_order_id'],
                new_stop_price
            )
        
        if position['id'] in self.active_positions:
            self.active_positions[position['id']]['stop_loss'] = new_stop_price
    
    def _check_trailing_stop_hit(self, position: Dict, current_price: float) -> bool:
        """Check if trailing stop is hit"""
        stop_loss = position.get('stop_loss', 0)
        side = position['side']
        
        if side == 'long':
            return current_price <= stop_loss
        else:
            return current_price >= stop_loss
    
    async def _check_take_profit(self, position: Dict, current_price: float, pnl_data: Dict):
        """Check and execute partial take profits"""
        take_profit_levels = json.loads(position.get('take_profit', '[]'))
        
        if not take_profit_levels:
            return
        
        for tp in take_profit_levels:
            if tp.get('executed', False):
                continue
            
            tp_hit = False
            if position['side'] == 'long':
                tp_hit = current_price >= tp['price']
            else:
                tp_hit = current_price <= tp['price']
            
            if tp_hit:
                # Execute partial close
                partial_quantity = position['quantity'] * tp['size']
                await self._close_partial_position(position, partial_quantity, '익절', current_price)
                
                # Mark as executed
                tp['executed'] = True
                self.db.update_position(position['id'], {
                    'take_profit': json.dumps(take_profit_levels)
                })
    
    async def _close_partial_position(self, position: Dict, quantity: float, reason: str, current_price: float):
        """Close partial position"""
        try:
            side = 'sell' if position['side'] == 'long' else 'buy'
            order = await self.exchange.place_order(position['symbol'], side, quantity)
            
            if order:
                self.logger.info(
                    f"💰 부분 포지션 마감: {position['symbol']} - "
                    f"{quantity} 계약 @ {current_price} - 사유: {reason}"
                )
                
                # Update remaining quantity
                new_quantity = position['quantity'] - quantity
                self.db.update_position(position['id'], {'quantity': new_quantity})
                
        except Exception as e:
            self.logger.error(f"부분 포지션 마감 실패: {e}")
    
    def _should_stop_loss(self, position: Dict, current_price: float) -> bool:
        """Check if stop loss should be triggered"""
        side = position['side']
        stop_loss = position['stop_loss']
        
        if side == 'long':
            return current_price <= stop_loss
        else:
            return current_price >= stop_loss
    
    def _should_timeout_position(self, position: Dict) -> bool:
        """Check if position should be closed due to timeout"""
        # Optional: Close positions open for too long
        # For now, return False
        return False
    
    def _should_cut_loss_early(self, position: Dict, pnl_data: Dict) -> bool:
        """Check if we should cut losses early based on adverse movement"""
        # If position quickly moves against us, cut early
        # This helps prevent larger losses
        
        # Get time since entry
        # If within first hour and already down significantly, cut
        # For now, simplified implementation
        if pnl_data['pnl_percent'] < -self.config.STOP_LOSS[position['symbol']] * 0.7:
            return True
        
        return False
    
    async def _close_position(self, position: Dict, reason: str, close_price: float):
        """Close a position completely"""
        try:
            # Close on exchange
            order = await self.exchange.close_position(position['symbol'], reason)
            
            if not order:
                self.logger.error(f"거래소에서 포지션 마감 실패: {position['symbol']}")
                return
            
            # Get actual close price from order
            actual_close_price = order.get('price', close_price)
            
            # Calculate final P&L
            pnl_data = self._calculate_pnl(position, actual_close_price)
            
            # Update database
            self.db.update_position(position['id'], {
                'status': 'closed',
                'current_price': actual_close_price
            })
            
            # Calculate hold duration
            with self.db._get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute(
                    "SELECT timestamp FROM trades WHERE id = ?", 
                    (position['trade_id'],)
                )
                trade = cursor.fetchone()
            
            if trade:
                hold_duration = (datetime.now() - datetime.fromisoformat(trade['timestamp'])).seconds // 60
            else:
                hold_duration = 0
            
            # Update trade
            self.db.update_trade(position['trade_id'], {
                'status': 'closed',
                'close_price': actual_close_price,
                'close_time': datetime.now(),
                'pnl': pnl_data['pnl_value'],
                'pnl_percent': pnl_data['pnl_percent'] * 100,
                'reason': reason,
                'hold_duration': hold_duration,
                'max_profit': position.get('max_profit', 0),
                'trailing_stop_activated': position.get('trailing_stop_active', False)
            })
            
            # Update Kelly tracking
            risk_manager = RiskManager(self.config, self.db)
            risk_manager.update_kelly_after_trade(position['symbol'], pnl_data['pnl_percent'])
            
            # Remove from active positions
            if position['id'] in self.active_positions:
                del self.active_positions[position['id']]
            
            # Log
            emoji = '💰' if pnl_data['pnl_percent'] > 0 else '🛑'
            self.logger.info(
                f"{emoji} 포지션 종료: {position['symbol']} - {reason} - "
                f"손익: {pnl_data['pnl_percent']:.2%} (${pnl_data['pnl_value']:.2f})"
            )
            
            self.db.log_system_event(
                'INFO', 'PositionManager',
                f"포지션 종료: {position['symbol']} - {reason}",
                {
                    'position_id': position['id'],
                    'pnl_percent': pnl_data['pnl_percent'],
                    'reason': reason
                }
            )
            
            # Send Telegram notification for position closure
            if self.notifier:
                try:
                    # Determine action type based on reason and P&L
                    if pnl_data['pnl_percent'] > 0:
                        action = 'close_profit'
                    elif reason in ['손절', '조기손절']:
                        action = 'close_loss'
                    elif reason == '추적손절':
                        action = 'trailing_stop'
                    else:
                        action = 'close_neutral'
                    
                    # Get position entry time
                    entry_time = position.get('timestamp', datetime.now())
                    if isinstance(entry_time, str):
                        entry_time = datetime.fromisoformat(entry_time)
                    
                    # Calculate hold duration
                    hold_duration = datetime.now() - entry_time
                    hold_hours = hold_duration.total_seconds() / 3600
                    
                    await self.notifier.send_trade_notification(
                        position['symbol'],
                        action,
                        {
                            'price': actual_close_price,
                            'quantity': position.get('quantity', 0),
                            'pnl': pnl_data['pnl_percent'] * 100,  # Convert to percentage
                            'pnl_value': pnl_data['pnl_value'],
                            'entry_price': position.get('entry_price', 0),
                            'reason': reason,
                            'hold_duration_hours': round(hold_hours, 1),
                            'position_type': position.get('direction', 'unknown'),
                            'leverage': position.get('leverage', 1)
                        }
                    )
                    self.logger.info(f"✅ 포지션 청산 알림 전송 완료: {position['symbol']} - {reason}")
                except Exception as e:
                    self.logger.error(f"❌ 포지션 청산 알림 전송 실패: {e}")
            
        except Exception as e:
            self.logger.error(f"포지션 마감 오류: {e}")
            self.db.log_system_event(
                'ERROR', 'PositionManager',
                f"포지션 마감 실패: {position['symbol']}",
                {'position_id': position['id'], 'error': str(e)}
            )
    
    def _calculate_position_size_ratio(self, symbol: str, signal: Dict) -> float:
        """Calculate position size ratio based on signal strength and market conditions"""
        try:
            # 🔥 CRITICAL: Enhanced defensive checks
            if not symbol:
                self.logger.error("❌ symbol이 비어있습니다")
                return None
                
            if not signal or not isinstance(signal, dict):
                self.logger.error(f"❌ {symbol} signal이 유효하지 않습니다: {signal}")
                return None
                
            if symbol not in self.config.POSITION_SIZE_RANGE:
                self.logger.warning(f"⚠️ Position size range not found for {symbol}, using default")
                return 0.2  # Default 20%
            
            base_range = self.config.POSITION_SIZE_RANGE[symbol]
            
            # Start with standard size
            size = float(base_range.get('standard', 0.2))
            
            # Adjust based on signal strength (defensive)
            signal_score = signal.get('score', 0)
            if signal_score is None:
                signal_score = 0
            
            signal_strength = abs(float(signal_score))
            if signal_strength > 0.7:
                size = float(base_range.get('max', 0.3))
            elif signal_strength < 0.4:
                size = float(base_range.get('min', 0.1))
            
            # Adjust based on confidence (defensive)
            confidence = signal.get('confidence', 50)
            if confidence is None:
                confidence = 50
            
            confidence = float(confidence)
            if confidence > 80:
                size *= 1.2
            elif confidence < 60:
                size *= 0.8
            
            # Adjust based on market regime
            regime = signal.get('regime', 'unknown')
            if regime == 'volatile':
                size *= 0.7  # Reduce size in volatile markets
            elif regime in ['trending_up', 'trending_down']:
                size *= 1.1  # Increase size in trending markets
            
            # Ensure within limits
            min_size = float(base_range.get('min', 0.1))
            max_size = float(base_range.get('max', 0.3))
            final_size = np.clip(size, min_size, max_size)
            
            return float(final_size)
            
        except Exception as e:
            self.logger.error(f"Position size ratio calculation error: {e}")
            return 0.2  # Safe default
    
    async def _calculate_dynamic_stops(self, symbol: str, entry_price: float, side: str) -> Dict[str, any]:
        """🔥 ATR 기반 동적 손절/익절 계산"""
        try:
            # 최근 캔들 데이터 조회 (50개)
            recent_candles = await self._get_recent_candles(symbol, limit=50)
            
            if not recent_candles or len(recent_candles) < 20:
                self.logger.warning(f"⚠️ {symbol} 캔들 데이터 부족, 폴백 모드 사용")
                return self._get_fallback_stops(symbol, entry_price, side)
            
            # RiskManager의 ATR 기반 계산 사용
            stops = self.risk_manager.calculate_position_stops(
                symbol, entry_price, side, recent_candles
            )
            
            # 익절 레벨 리스트 형태로 변환 (기존 호환성 유지)
            take_profit_levels = [{
                'price': stops['take_profit'],
                'size': 1.0,  # 100% 청산
                'executed': False
            }]
            
            return {
                'stop_loss': stops['stop_loss'],
                'take_profit': take_profit_levels,
                'atr_value': stops.get('atr_value', 0.0),
                'stop_distance_pct': stops['stop_distance_pct'],
                'profit_distance_pct': stops['profit_distance_pct']
            }
            
        except Exception as e:
            self.logger.error(f"동적 손절/익절 계산 오류: {e}")
            return self._get_fallback_stops(symbol, entry_price, side)
    
    def _calculate_stop_loss(self, symbol: str, entry_price: float, side: str) -> float:
        """레거시 호환성을 위한 폴백 손절 계산"""
        try:
            if hasattr(self.config, 'FALLBACK_STOP_LOSS'):
                sl_pct = self.config.FALLBACK_STOP_LOSS[symbol]
            else:
                # 기존 설정이 있다면 사용
                sl_pct = getattr(self.config, 'STOP_LOSS', {}).get(symbol, 0.01)
        except:
            sl_pct = 0.01  # 기본 1%
        
        if side == 'buy':
            return entry_price * (1 - sl_pct)
        else:
            return entry_price * (1 + sl_pct)
    
    def _calculate_take_profit(self, symbol: str, entry_price: float, side: str) -> List[Dict]:
        """레거시 호환성을 위한 폴백 익절 계산"""
        try:
            if hasattr(self.config, 'FALLBACK_TAKE_PROFIT'):
                tp_pct = self.config.FALLBACK_TAKE_PROFIT[symbol]
            else:
                # 기존 설정이 있다면 사용
                tp_levels = getattr(self.config, 'TAKE_PROFIT', {}).get(symbol, [(0.02, 1.0)])
                tp_pct = tp_levels[0][0] if tp_levels else 0.02
        except:
            tp_pct = 0.02  # 기본 2%
        
        if side == 'buy':
            tp_price = entry_price * (1 + tp_pct)
        else:
            tp_price = entry_price * (1 - tp_pct)
        
        return [{
            'price': tp_price,
            'size': 1.0,
            'executed': False
        }]
    
    async def _get_recent_candles(self, symbol: str, limit: int = 50) -> List[Dict]:
        """최근 캔들 데이터 조회"""
        try:
            # Exchange manager의 캔들 데이터 조회 메서드 사용
            df = await self.exchange.fetch_ohlcv_with_cache(symbol, '1h', limit)
            
            if df is None or df.empty:
                return []
            
            # DataFrame을 Dict 리스트로 변환
            candles = []
            for _, row in df.iterrows():
                candles.append({
                    'open': float(row['open']),
                    'high': float(row['high']),
                    'low': float(row['low']),
                    'close': float(row['close']),
                    'volume': float(row['volume'])
                })
            
            return candles
            
        except Exception as e:
            self.logger.error(f"캔들 데이터 조회 오류: {e}")
            return []
    
    def _get_fallback_stops(self, symbol: str, entry_price: float, side: str) -> Dict[str, any]:
        """ATR 실패 시 폴백 손절/익절"""
        try:
            stop_loss = self._calculate_stop_loss(symbol, entry_price, side)
            take_profit = self._calculate_take_profit(symbol, entry_price, side)
            
            return {
                'stop_loss': stop_loss,
                'take_profit': take_profit,
                'atr_value': 0.0,
                'stop_distance_pct': 1.0,
                'profit_distance_pct': 2.0
            }
            
        except Exception as e:
            self.logger.error(f"폴백 손절/익절 계산 오류: {e}")
            # 최후 폴백
            if side == 'buy':
                stop_loss = entry_price * 0.99
                tp_price = entry_price * 1.02
            else:
                stop_loss = entry_price * 1.01
                tp_price = entry_price * 0.98
            
            return {
                'stop_loss': stop_loss,
                'take_profit': [{'price': tp_price, 'size': 1.0, 'executed': False}],
                'atr_value': 0.0,
                'stop_distance_pct': 1.0,
                'profit_distance_pct': 2.0
            }
    
    async def monitor_and_adjust_stops(self):
        """🔥 실시간 ATR 변화에 따른 손절/익절 조정"""
        try:
            open_positions = self.db.get_open_positions()
            
            if not open_positions:
                return
                
            self.logger.info(f"📊 {len(open_positions)}개 포지션 ATR 모니터링 시작")
            
            for position in open_positions:
                try:
                    await self._monitor_single_position_atr(position)
                    # 각 포지션 간 짧은 딜레이 (API 제한 회피)
                    await asyncio.sleep(0.5)
                    
                except Exception as e:
                    self.logger.error(f"포지션 {position['id']} ATR 모니터링 오류: {e}")
                    continue
                    
        except Exception as e:
            self.logger.error(f"ATR 모니터링 시스템 오류: {e}")
    
    async def _monitor_single_position_atr(self, position: Dict):
        """개별 포지션 ATR 모니터링"""
        try:
            symbol = position['symbol']
            position_id = position['id']
            entry_price = position['entry_price']
            side = position['side']
            original_atr = position.get('atr_value', 0)
            
            # 현재 ATR 재계산
            recent_candles = await self._get_recent_candles(symbol)
            if not recent_candles or len(recent_candles) < 20:
                return
                
            current_atr = self.risk_manager.atr_calculator.calculate_atr(recent_candles)
            
            if current_atr <= 0 or original_atr <= 0:
                return
                
            # ATR 변화율 확인
            atr_change_rate = (current_atr - original_atr) / original_atr
            
            # 20% 이상 변화 시 조정 고려
            if abs(atr_change_rate) > 0.2:
                self.logger.info(
                    f"📊 {symbol} ATR 큰 변화 감지: "
                    f"{original_atr:.6f} → {current_atr:.6f} "
                    f"({atr_change_rate:+.1%})"
                )
                
                # 새로운 손절/익절 계산
                new_stops = self.risk_manager.calculate_position_stops(
                    symbol, entry_price, side, recent_candles
                )
                
                # 손절은 불리하게 조정하지 않음 (안전장치)
                current_stop_loss = position.get('stop_loss', 0)
                
                if side.lower() in ['long', 'buy']:
                    # 롱 포지션: 새 손절이 기존보다 높을 때만 적용
                    if new_stops['stop_loss'] > current_stop_loss:
                        should_update = True
                        update_reason = "ATR 감소로 손절 타이트하게 조정"
                    else:
                        should_update = False
                        self.logger.debug(f"{symbol} 롱 포지션 손절 불리한 조정 방지")
                else:
                    # 숏 포지션: 새 손절이 기존보다 낮을 때만 적용
                    if new_stops['stop_loss'] < current_stop_loss:
                        should_update = True
                        update_reason = "ATR 감소로 손절 타이트하게 조정"
                    else:
                        should_update = False
                        self.logger.debug(f"{symbol} 숏 포지션 손절 불리한 조정 방지")
                
                if should_update:
                    # 포지션 업데이트
                    await self._update_position_stops(position_id, new_stops, update_reason)
                    
                    # 알림 발송
                    await self.notifier.send_notification(
                        f"📊 **{symbol} ATR 기반 손절 조정**\n\n"
                        f"**ATR 변화**: {atr_change_rate:+.1%}\n"
                        f"**기존 손절**: ${current_stop_loss:.6f}\n"
                        f"**새 손절**: ${new_stops['stop_loss']:.6f}\n"
                        f"**사유**: {update_reason}",
                        priority='normal'
                    )
                    
        except Exception as e:
            self.logger.error(f"개별 포지션 ATR 모니터링 오류: {e}")
    
    async def _update_position_stops(self, position_id: int, new_stops: Dict, reason: str):
        """포지션 손절/익절 업데이트"""
        try:
            # 데이터베이스 업데이트
            self.db.execute_query(
                """UPDATE positions 
                   SET stop_loss = ?, 
                       atr_value = ?,
                       stop_distance_pct = ?,
                       profit_distance_pct = ?,
                       updated_at = CURRENT_TIMESTAMP
                   WHERE id = ?""",
                (new_stops['stop_loss'], 
                 new_stops.get('atr_value', 0),
                 new_stops.get('stop_distance_pct', 0),
                 new_stops.get('profit_distance_pct', 0),
                 position_id)
            )
            
            # 메모리 캐시 업데이트
            if position_id in self.active_positions:
                self.active_positions[position_id]['stop_loss'] = new_stops['stop_loss']
            
            self.logger.info(f"✅ 포지션 {position_id} 손절 업데이트 완료 - {reason}")
            
        except Exception as e:
            self.logger.error(f"포지션 {position_id} 업데이트 실패: {e}")
    
    async def open_position_with_dynamic_stops(self, signal: Dict) -> Dict:
        """🔥 동적 손절/익절을 적용한 포지션 오픈"""
        try:
            symbol = signal['symbol']
            
            # 기존 open_position 메서드 활용하되 동적 계산 강제
            result = await self.open_position(symbol, signal, signal.get('allocated_capital', 0))
            
            if result and result.get('success'):
                self.logger.info(f"🚀 {symbol} ATR 기반 동적 포지션 오픈 성공")
                
                # ATR 모니터링 스케줄링 (30분마다)
                asyncio.create_task(self._schedule_atr_monitoring(symbol))
                
            return result
            
        except Exception as e:
            self.logger.error(f"동적 손절/익절 포지션 오픈 실패: {e}")
            return {'success': False, 'error': str(e)}
    
    async def _schedule_atr_monitoring(self, symbol: str):
        """특정 심볼 ATR 모니터링 스케줄링"""
        try:
            # 30분 대기 후 모니터링 실행
            await asyncio.sleep(1800)  # 30분
            await self.monitor_and_adjust_stops()
            
        except asyncio.CancelledError:
            pass
        except Exception as e:
            self.logger.error(f"{symbol} ATR 모니터링 스케줄 오류: {e}")
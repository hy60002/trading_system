"""
Real-time Capital Tracking System
Monitors dynamic allocation limit and provides real-time position tracking
"""

import asyncio
import logging
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Tuple
from dataclasses import dataclass, field

# Import handling for both direct and package imports
try:
    from ..config.config import TradingConfig
    from ..database.db_manager import EnhancedDatabaseManager
    from ..notifications.notification_manager import NotificationManager
except ImportError:
    import sys
    import os
    sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    from config.config import TradingConfig
    from database.db_manager import EnhancedDatabaseManager
    from notifications.notification_manager import NotificationManager


@dataclass
class CapitalAllocation:
    """Capital allocation tracking data"""
    symbol: str
    quantity: float
    entry_price: float
    current_price: float
    market_value: float
    allocation_percentage: float
    unrealized_pnl: float
    leverage: int
    side: str  # 'long' or 'short'
    timestamp: datetime = field(default_factory=datetime.now)


@dataclass
class CapitalSnapshot:
    """Complete capital snapshot"""
    total_balance: float
    used_capital: float
    available_capital: float
    allocation_percentage: float
    btc_allocation: float
    eth_allocation: float
    positions: List[CapitalAllocation]
    within_limit: bool
    timestamp: datetime = field(default_factory=datetime.now)


class CapitalTracker:
    """Real-time capital allocation tracking system"""
    
    def __init__(self, config: TradingConfig, db: EnhancedDatabaseManager, 
                 notification_manager: NotificationManager, exchange=None):
        self.config = config
        self.db = db
        self.notification_manager = notification_manager
        self.exchange = exchange  # Exchange manager for real-time balance
        self.logger = logging.getLogger(__name__)
        
        # 🏦 Dynamic Capital Management Settings (하드코딩 제거)
        self.fallback_balance = config.FALLBACK_BALANCE
        self.dynamic_balance_enabled = config.ENABLE_DYNAMIC_BALANCE
        self.cache_timeout = config.BALANCE_CACHE_TIMEOUT
        self.allocation_limit = config.CAPITAL_ALLOCATION_LIMIT  # 동적 한도 설정
        
        # 잔고 캐시 시스템
        self._balance_cache = None
        self._balance_cache_time = 0
        
        # Real-time tracking variables
        self.current_snapshot: Optional[CapitalSnapshot] = None
        self.last_update_time: Optional[datetime] = None
        self.tracking_enabled = True
        self.update_interval = 30  # Update every 30 seconds
        
        # Alert thresholds
        self.warning_threshold = 0.25  # 25% - Warning
        self.danger_threshold = 0.30   # 30% - Danger
        self.critical_threshold = 0.32 # 32% - Critical (near limit)
        
        # Alert state tracking
        self.last_alert_level = None
        self.alert_cooldown = 300  # 5 minutes between same-level alerts
        self.last_alert_time = {}
        
        # Performance tracking
        self.update_count = 0
        self.error_count = 0
        
        # Start tracking task
        self.tracking_task: Optional[asyncio.Task] = None
    
    async def initialize(self):
        """Initialize capital tracking system"""
        self.logger.info("🏦 실시간 자본 추적 시스템 초기화 중...")
        
        try:
            # Initial snapshot
            await self.update_snapshot()
            
            # Start background tracking
            self.tracking_task = asyncio.create_task(self._tracking_loop())
            
            self.logger.info("✅ 실시간 자본 추적 시스템 초기화 완료")
            
            # Send initialization notification
            if self.current_snapshot:
                await self.notification_manager.send_notification(
                    f"🏦 **자본 추적 시스템 시작**\n\n"
                    f"💰 총 잔고: ${self.current_snapshot.total_balance:,.2f}\n"
                    f"📊 현재 할당: {self.current_snapshot.allocation_percentage:.1%}\n"
                    f"🎯 한도: {self.allocation_limit:.0%}\n"
                    f"✅ 시스템 정상 작동 중",
                    priority='normal'
                )
            
        except Exception as e:
            self.logger.error(f"❌ 자본 추적 시스템 초기화 실패: {e}")
            raise
    
    async def _tracking_loop(self):
        """Main tracking loop"""
        while self.tracking_enabled:
            try:
                await self.update_snapshot()
                await self._check_alerts()
                await asyncio.sleep(self.update_interval)
                
            except Exception as e:
                self.error_count += 1
                self.logger.error(f"❌ 추적 루프 오류: {e}")
                
                # Exponential backoff on errors
                error_delay = min(60, 5 * (2 ** min(self.error_count, 4)))
                await asyncio.sleep(error_delay)
    
    async def update_snapshot(self) -> CapitalSnapshot:
        """Update current capital snapshot"""
        try:
            # Get current balance
            total_balance = await self._get_total_balance()
            
            # Get open positions
            positions = await self._get_position_allocations()
            
            # Calculate totals
            used_capital = sum(pos.market_value for pos in positions)
            allocation_percentage = used_capital / total_balance if total_balance > 0 else 0
            
            # Calculate symbol-specific allocations
            btc_allocation = sum(pos.market_value for pos in positions if 'BTC' in pos.symbol)
            eth_allocation = sum(pos.market_value for pos in positions if 'ETH' in pos.symbol)
            
            # Check if within limit
            within_limit = allocation_percentage <= self.allocation_limit
            
            # Create snapshot
            self.current_snapshot = CapitalSnapshot(
                total_balance=total_balance,
                used_capital=used_capital,
                available_capital=total_balance * self.allocation_limit - used_capital,
                allocation_percentage=allocation_percentage,
                btc_allocation=btc_allocation,
                eth_allocation=eth_allocation,
                positions=positions,
                within_limit=within_limit
            )
            
            self.last_update_time = datetime.now()
            self.update_count += 1
            
            # Log periodic updates
            if self.update_count % 10 == 0:  # Every 10 updates (5 minutes)
                self.logger.info(
                    f"📊 자본 현황 업데이트 #{self.update_count}: "
                    f"{allocation_percentage:.1%} 사용 "
                    f"({used_capital:,.0f}/{total_balance * self.allocation_limit:,.0f})"
                )
            
            return self.current_snapshot
            
        except Exception as e:
            self.logger.error(f"❌ 자본 스냅샷 업데이트 실패: {e}")
            raise
    
    async def _get_total_balance(self) -> float:
        """Get total account balance from exchange or database"""
        try:
            # Try to get from exchange if available
            if self.exchange is not None:
                self.logger.info(f"🔄 거래소에서 잔고 조회 시도 중...")
                balance = await self.exchange.get_balance()
                self.logger.info(f"✅ 거래소 잔고 조회 성공: {balance}")
            else:
                self.logger.warning(f"⚠️ Exchange 객체가 None입니다. 직접 API 호출 시도...")
                
                # Exchange 객체가 없는 경우 직접 API 호출 시도
                try:
                    import ccxt
                    import os
                    
                    api_key = os.getenv('BITGET_API_KEY')
                    secret_key = os.getenv('BITGET_SECRET_KEY')
                    passphrase = os.getenv('BITGET_PASSPHRASE')
                    
                    if all([api_key, secret_key, passphrase]):
                        self.logger.info("🔄 임시 거래소 객체로 직접 잔고 조회 중...")
                        temp_exchange = ccxt.bitget({
                            'apiKey': api_key,
                            'secret': secret_key,
                            'password': passphrase,
                            'enableRateLimit': True,
                            'options': {'defaultType': 'swap'}
                        })
                        
                        balance = await asyncio.get_event_loop().run_in_executor(
                            None, temp_exchange.fetch_balance
                        )
                        self.logger.info(f"✅ 직접 잔고 조회 성공: {balance}")
                    else:
                        self.logger.warning(f"⚠️ API 키가 없어 fallback 사용: ${self.fallback_balance}")
                        return self.fallback_balance
                        
                except Exception as direct_error:
                    self.logger.error(f"❌ 직접 잔고 조회도 실패: {direct_error}")
                    return self.fallback_balance
                # Extract USDT balance using same logic as trading engine
                total_capital = 0
                
                if 'USDT' in balance and isinstance(balance['USDT'], dict):
                    total_capital = balance['USDT'].get('free', 0) or balance['USDT'].get('available', 0)
                elif 'free' in balance and 'USDT' in balance['free']:
                    total_capital = balance['free'].get('USDT', 0)
                elif 'total' in balance and 'USDT' in balance['total']:
                    total_capital = balance['total'].get('USDT', 0)
                elif 'info' in balance:
                    info = balance['info']
                    if isinstance(info, list):
                        for item in info:
                            if isinstance(item, dict):
                                # 선물 계좌: marginCoin 확인
                                if item.get('marginCoin') == 'USDT':
                                    available = item.get('available', 0)
                                    account_equity = item.get('accountEquity', 0)
                                    total_capital = float(available or account_equity or 0)
                                    self.logger.info(f"🎯 선물 계좌 USDT 잔고 발견: ${total_capital:.2f}")
                                    break
                                # 현물 계좌: coin 확인 (기존 코드)
                                elif item.get('coin') == 'USDT':
                                    total_capital = float(item.get('available', 0) or item.get('equity', 0))
                                    self.logger.info(f"🎯 현물 계좌 USDT 잔고 발견: ${total_capital:.2f}")
                                    break
                    elif isinstance(info, dict) and 'USDT' in info:
                        total_capital = float(info['USDT'].get('available', 0))
                
                if total_capital > 0:
                    return float(total_capital)
            
            # Fallback to database
            balance_data = self.db.get_latest_balance()
            
            if balance_data:
                return float(balance_data.get('total_balance', self.fallback_balance))
            else:
                # Default fallback balance from config
                self.logger.warning(f"⚠️ 잔고 데이터 없음 - 설정 기본값 사용: ${self.fallback_balance:.2f}")
                return self.fallback_balance
                
        except Exception as e:
            self.logger.error(f"❌ 잔고 조회 실패, 설정 기본값 사용: {e}")
            return self.fallback_balance
    
    async def _get_position_allocations(self) -> List[CapitalAllocation]:
        """Get current position allocations"""
        try:
            positions = self.db.get_open_positions()
            allocations = []
            
            for pos in positions:
                # 🔥 CRITICAL: Safe value extraction with comprehensive checks
                symbol = pos.get('symbol', 'UNKNOWN')
                
                # Defensive checks for None values
                raw_quantity = pos.get('quantity')
                raw_entry_price = pos.get('entry_price')
                
                if raw_quantity is None or raw_entry_price is None:
                    self.logger.warning(f"⚠️ 포지션 데이터 불완전 무시: {symbol} quantity={raw_quantity}, entry_price={raw_entry_price}")
                    continue
                
                try:
                    quantity = float(raw_quantity)
                    entry_price = float(raw_entry_price)
                    leverage = int(pos.get('leverage', 1))
                    side = pos.get('side', 'long')
                    
                    # 올바른 선물 포지션 증거금 계산
                    nominal_value = abs(quantity * entry_price)
                    market_value = nominal_value / leverage  # 실제 증거금
                    
                except (ValueError, TypeError) as e:
                    self.logger.warning(f"⚠️ 포지션 값 변환 오류 무시: {symbol} - {e}")
                    continue
                
                # Calculate unrealized PnL (simplified)
                current_price = entry_price  # Would get from real-time data
                if side == 'long':
                    unrealized_pnl = (current_price - entry_price) / entry_price
                else:
                    unrealized_pnl = (entry_price - current_price) / entry_price
                
                allocation = CapitalAllocation(
                    symbol=symbol,
                    quantity=quantity,
                    entry_price=entry_price,
                    current_price=current_price,
                    market_value=market_value,
                    allocation_percentage=0,  # Will be calculated later
                    unrealized_pnl=unrealized_pnl,
                    leverage=leverage,
                    side=side
                )
                
                allocations.append(allocation)
            
            return allocations
            
        except Exception as e:
            self.logger.error(f"❌ 포지션 할당 조회 실패: {e}")
            return []
    
    async def _check_alerts(self):
        """Check and send allocation alerts"""
        if not self.current_snapshot:
            return
        
        current_allocation = self.current_snapshot.allocation_percentage
        current_time = datetime.now()
        
        # Determine alert level
        alert_level = None
        if current_allocation >= self.critical_threshold:
            alert_level = 'critical'
        elif current_allocation >= self.danger_threshold:
            alert_level = 'danger'
        elif current_allocation >= self.warning_threshold:
            alert_level = 'warning'
        
        # Check if we should send alert
        if alert_level and alert_level != self.last_alert_level:
            # New alert level - always send
            await self._send_allocation_alert(alert_level, current_allocation)
            self.last_alert_level = alert_level
            self.last_alert_time[alert_level] = current_time
            
        elif alert_level and alert_level == self.last_alert_level:
            # Same level - check cooldown
            last_sent = self.last_alert_time.get(alert_level, datetime.min)
            if (current_time - last_sent).seconds >= self.alert_cooldown:
                await self._send_allocation_alert(alert_level, current_allocation)
                self.last_alert_time[alert_level] = current_time
        
        elif not alert_level and self.last_alert_level:
            # Allocation returned to safe levels
            await self._send_safe_level_notification()
            self.last_alert_level = None
    
    async def _send_allocation_alert(self, level: str, allocation: float):
        """Send allocation alert"""
        emojis = {
            'warning': '⚠️',
            'danger': '🔶', 
            'critical': '🚨'
        }
        
        priorities = {
            'warning': 'normal',
            'danger': 'high',
            'critical': 'emergency'
        }
        
        emoji = emojis.get(level, '⚠️')
        priority = priorities.get(level, 'normal')
        
        message = f"""{emoji} **자금 할당 {level.upper()} 알림**

📊 **현재 할당**: {allocation:.1%}
🎯 **제한 한도**: {self.allocation_limit:.0%}
💰 **사용 중**: ${self.current_snapshot.used_capital:,.2f}
💳 **총 잔고**: ${self.current_snapshot.total_balance:,.2f}
🔢 **가용 한도**: ${self.current_snapshot.available_capital:,.2f}

**포지션 현황**:"""
        
        for pos in self.current_snapshot.positions:
            pos_emoji = '🟢' if pos.side == 'long' else '🔴'
            message += f"\n{pos_emoji} {pos.symbol}: ${pos.market_value:,.2f} ({pos.leverage}x)"
        
        if level == 'critical':
            message += f"\n\n🛑 **즉시 조치 필요**: {self.allocation_limit:.0%} 한도에 근접했습니다!"
        elif level == 'danger':
            message += f"\n\n⚠️ **주의**: 30% 한도를 초과했습니다."
        
        await self.notification_manager.send_notification(message, priority=priority)
    
    async def _send_safe_level_notification(self):
        """Send notification when allocation returns to safe levels"""
        message = f"""✅ **자금 할당 정상화**

📊 현재 할당: {self.current_snapshot.allocation_percentage:.1%}
🎯 제한 한도: {self.allocation_limit:.0%}
✅ 상태: 안전 수준 복귀

계속 모니터링 중입니다."""
        
        await self.notification_manager.send_notification(message, priority='normal')
    
    def can_open_position(self, symbol: str, estimated_cost: float) -> Tuple[bool, str, Dict]:
        """Check if new position can be opened within dynamic allocation limit"""
        if not self.current_snapshot:
            return False, "스냅샷 데이터 없음", {}
        
        # Calculate what allocation would be after new position
        new_used_capital = self.current_snapshot.used_capital + estimated_cost
        new_allocation = new_used_capital / self.current_snapshot.total_balance
        
        # Check various limits
        checks = {
            'within_allocation_limit': new_allocation <= self.allocation_limit,  # 동적 한도 사용
            'symbol_weight_ok': self._check_symbol_weight(symbol, estimated_cost),
            'sufficient_balance': estimated_cost <= self.current_snapshot.available_capital
        }
        
        can_open = all(checks.values())
        
        if not can_open:
            failed_checks = [k for k, v in checks.items() if not v]
            reason = f"제한 위반: {', '.join(failed_checks)}"
        else:
            reason = "승인"
        
        details = {
            'current_allocation': self.current_snapshot.allocation_percentage,
            'new_allocation': new_allocation,
            'estimated_cost': estimated_cost,
            'available_capital': self.current_snapshot.available_capital,
            'checks': checks
        }
        
        return can_open, reason, details
    
    def _check_symbol_weight(self, symbol: str, additional_cost: float) -> bool:
        """Check if symbol allocation would be within target weights"""
        if not self.current_snapshot:
            return False
        
        target_weight = self.config.PORTFOLIO_WEIGHTS.get(symbol, 0)
        if target_weight == 0:
            return False
        
        # Calculate current symbol allocation
        current_symbol_value = sum(
            pos.market_value for pos in self.current_snapshot.positions 
            if pos.symbol == symbol
        )
        
        # Calculate what it would be with new position
        new_symbol_value = current_symbol_value + additional_cost
        total_target_allocation = self.current_snapshot.total_balance * self.allocation_limit
        max_symbol_allocation = total_target_allocation * target_weight
        
        return new_symbol_value <= max_symbol_allocation * 1.1  # 10% tolerance
    
    def get_current_status(self) -> Dict:
        """Get current tracking system status"""
        if not self.current_snapshot:
            return {'error': '스냅샷 데이터 없음'}
        
        return {
            'timestamp': self.current_snapshot.timestamp.isoformat(),
            'total_balance': self.current_snapshot.total_balance,
            'used_capital': self.current_snapshot.used_capital,
            'allocation_percentage': self.current_snapshot.allocation_percentage,
            'within_limit': self.current_snapshot.within_limit,
            'available_capital': self.current_snapshot.available_capital,
            'position_count': len(self.current_snapshot.positions),
            'btc_allocation': self.current_snapshot.btc_allocation,
            'eth_allocation': self.current_snapshot.eth_allocation,
            'update_count': self.update_count,
            'error_count': self.error_count,
            'last_update': self.last_update_time.isoformat() if self.last_update_time else None,
            'tracking_enabled': self.tracking_enabled
        }
    
    def get_detailed_positions(self) -> List[Dict]:
        """Get detailed position information"""
        if not self.current_snapshot:
            return []
        
        return [
            {
                'symbol': pos.symbol,
                'quantity': pos.quantity,
                'entry_price': pos.entry_price,
                'market_value': pos.market_value,
                'side': pos.side,
                'leverage': pos.leverage,
                'unrealized_pnl': pos.unrealized_pnl,
                'allocation_percentage': pos.market_value / self.current_snapshot.total_balance if self.current_snapshot.total_balance > 0 else 0
            }
            for pos in self.current_snapshot.positions
        ]
    
    async def force_update(self) -> CapitalSnapshot:
        """Force immediate snapshot update"""
        self.logger.info("🔄 강제 자본 스냅샷 업데이트...")
        return await self.update_snapshot()
    
    async def set_update_interval(self, seconds: int):
        """Change update interval"""
        self.update_interval = max(10, min(300, seconds))  # Between 10 seconds and 5 minutes
        self.logger.info(f"⏱️ 업데이트 주기 변경: {self.update_interval}초")
    
    async def shutdown(self):
        """Shutdown capital tracking system"""
        self.logger.info("🔄 자본 추적 시스템 종료 중...")
        self.tracking_enabled = False
        
        if self.tracking_task:
            try:
                await asyncio.wait_for(self.tracking_task, timeout=5.0)
            except asyncio.TimeoutError:
                self.logger.warning("추적 태스크 종료 타임아웃")
                self.tracking_task.cancel()
        
        # Send shutdown notification
        await self.notification_manager.send_notification(
            "🏦 **자본 추적 시스템 종료**\n\n"
            f"📊 총 업데이트: {self.update_count}회\n"
            f"❌ 오류 발생: {self.error_count}회\n"
            f"⏹️ 시스템 정상 종료",
            priority='normal'
        )
        
        self.logger.info("✅ 자본 추적 시스템 종료 완료")


# Helper functions for integration
async def check_position_feasibility(tracker: CapitalTracker, symbol: str, 
                                   price: float, quantity: float) -> Tuple[bool, str, Dict]:
    """Check if a position can be opened"""
    estimated_cost = abs(price * quantity)
    return tracker.can_open_position(symbol, estimated_cost)


async def get_available_capital_for_symbol(tracker: CapitalTracker, symbol: str) -> float:
    """Get available capital for a specific symbol"""
    if not tracker.current_snapshot:
        return 0.0
    
    target_weight = tracker.config.PORTFOLIO_WEIGHTS.get(symbol, 0)
    if target_weight == 0:
        return 0.0
    
    total_target_allocation = tracker.current_snapshot.total_balance * tracker.allocation_limit
    max_symbol_allocation = total_target_allocation * target_weight
    
    current_symbol_value = sum(
        pos.market_value for pos in tracker.current_snapshot.positions 
        if pos.symbol == symbol
    )
    
    return max(0, max_symbol_allocation - current_symbol_value)
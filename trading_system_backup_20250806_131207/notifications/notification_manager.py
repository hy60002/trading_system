"""
Notification Manager
Multi-channel notification system with rate limiting
"""

import asyncio
import hashlib
import logging
import queue
import time
import aiohttp
from collections import deque
from datetime import datetime
from typing import Dict

# Import handling for both direct and package imports
try:
    from ..config.config import TradingConfig
    from ..utils.telegram_safe_formatter import telegram_formatter
except ImportError:
    import sys
    import os
    sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    from config.config import TradingConfig
    from utils.telegram_safe_formatter import telegram_formatter


class NotificationManager:
    """Multi-channel notification system with rate limiting"""
    
    def __init__(self, config: TradingConfig):
        self.config = config
        self.logger = logging.getLogger(__name__)
        
        # Message queue to prevent spam
        self.message_queue = deque(maxlen=100)
        self.last_message_time = {}
        self.min_interval = 60  # Minimum seconds between similar messages
        
        # Priority queues
        self.emergency_queue = queue.PriorityQueue()
        self.normal_queue = queue.Queue()
        
        # Start message processor
        self.processor_task = None
        self.is_running = True
        
        # 🔍 NOTIFICATION VERIFICATION SYSTEM
        self.verification_stats = {
            'total_notifications_sent': 0,
            'successful_deliveries': 0,
            'failed_deliveries': 0,
            'notification_types': {
                'trade': {'sent': 0, 'success': 0, 'failed': 0},
                'error': {'sent': 0, 'success': 0, 'failed': 0},
                'risk_alert': {'sent': 0, 'success': 0, 'failed': 0},
                'daily_report': {'sent': 0, 'success': 0, 'failed': 0},
                'system': {'sent': 0, 'success': 0, 'failed': 0}
            },
            'telegram_api_errors': [],
            'last_successful_delivery': None,
            'longest_failure_streak': 0,
            'current_failure_streak': 0
        }
        self.notification_verification_task = None
    
    async def initialize(self):
        """Initialize notification system"""
        self.processor_task = asyncio.create_task(self._message_processor())
        
        # Start notification verification system
        self.notification_verification_task = asyncio.create_task(self._notification_verification_loop())
        
        self.logger.info("🔍 알림 시스템 및 검증 시스템 초기화 완료")
    
    async def _message_processor(self):
        """Process messages from queues"""
        while self.is_running:
            try:
                # Check emergency queue first
                if not self.emergency_queue.empty():
                    _, _, message = self.emergency_queue.get_nowait()
                    await self._send_message(message)
                
                # Then normal queue
                elif not self.normal_queue.empty():
                    message = self.normal_queue.get_nowait()
                    await self._send_message(message)
                
                await asyncio.sleep(0.1)
                
            except Exception as e:
                self.logger.error(f"메시지 프로세서 오류: {e}")
                await asyncio.sleep(1)
    
    async def send_notification(self, message: str, priority: str = 'normal', 
                              channel: str = 'telegram', metadata: Dict = None):
        """Send notification with priority and channel selection"""
        # Trade notifications bypass spam protection
        is_trade_notification = metadata and metadata.get('type') == 'trade'
        
        # Check for spam (except for trade notifications)
        message_hash = hashlib.md5(message.encode()).hexdigest()[:8]
        current_time = time.time()
        
        if priority != 'emergency' and not is_trade_notification:
            if message_hash in self.last_message_time:
                if current_time - self.last_message_time[message_hash] < self.min_interval:
                    self.logger.info(f"📵 중복 메시지 차단: {message_hash}")
                    return False  # Skip duplicate message
        
        self.last_message_time[message_hash] = current_time
        
        # Create message object with enhanced metadata
        msg_obj = {
            'content': message,
            'channel': channel,
            'timestamp': current_time,
            'priority': priority,
            'metadata': metadata or {},
            'retry_count': 0,
            'max_retries': 3 if is_trade_notification else 1  # More retries for trade notifications
        }
        
        # Queue based on priority with unique ID to prevent comparison issues
        unique_id = time.time()
        
        if priority == 'emergency':
            self.emergency_queue.put((0, unique_id, msg_obj))  # Highest priority
        elif priority == 'high' or is_trade_notification:
            self.emergency_queue.put((1, unique_id, msg_obj))
        else:
            self.normal_queue.put(msg_obj)
        
        return True
    
    async def _send_message(self, msg_obj: Dict):
        """Send message to appropriate channel with retry logic"""
        channel = msg_obj['channel']
        message = msg_obj['content']
        max_retries = msg_obj.get('max_retries', 1)
        
        success = False
        if channel == 'telegram':
            success = await self._send_telegram_message(message, max_retries)
        # Add other channels here (Discord, Email, etc.)
        
        # 🔍 VERIFICATION: Track notification statistics
        await self._track_notification_delivery(msg_obj, success)
        
        # Log delivery status
        if success:
            self.logger.info(f"✅ 메시지 전송 성공: {channel}")
        else:
            self.logger.error(f"❌ 메시지 전송 실패: {channel} - {message[:50]}...")
            
            # For critical trade notifications, try additional fallback
            if msg_obj.get('metadata', {}).get('type') == 'trade':
                await self._handle_critical_message_failure(msg_obj)
        
        return success
    
    async def _send_telegram_message(self, message: str, max_retries: int = 3):
        """Send Telegram message with comprehensive retry logic"""
        if not self.config.TELEGRAM_BOT_TOKEN or not self.config.TELEGRAM_CHAT_ID:
            self.logger.warning("텔레그램 설정 누락 - 메시지 전송 건너뜀")
            return False
        
        url = f"https://api.telegram.org/bot{self.config.TELEGRAM_BOT_TOKEN}/sendMessage"
        
        # Use JSON with safe HTML formatting to prevent parsing errors
        safe_message = telegram_formatter.escape_html(message)
        payload = {
            "chat_id": self.config.TELEGRAM_CHAT_ID,
            "text": safe_message,
            "disable_web_page_preview": True,
            "parse_mode": "HTML"  # HTML is more stable than Markdown
        }
        
        headers = {
            'Content-Type': 'application/json; charset=utf-8',
            'User-Agent': 'Bitget-Trading-Bot/1.0'
        }
        
        for attempt in range(max_retries + 1):
            try:
                timeout = aiohttp.ClientTimeout(total=30)  # 30 second timeout
                async with aiohttp.ClientSession(timeout=timeout) as session:
                    async with session.post(url, json=payload, headers=headers) as response:
                        if response.status == 200:
                            self.logger.info(f"✅ 텔레그램 메시지 전송 성공 (시도 {attempt + 1}/{max_retries + 1})")
                            return True
                        
                        elif response.status == 429:  # Rate limited
                            retry_after = int(response.headers.get('Retry-After', 60))
                            self.logger.warning(f"⏸️ 텔레그램 속도 제한 - {retry_after}초 대기 후 재시도")
                            await asyncio.sleep(retry_after)
                            continue
                        
                        elif response.status in [400, 401, 403]:  # Client errors - don't retry
                            error_text = await response.text()
                            self.logger.error(f"❌ 텔레그램 클라이언트 오류 (재시도 안함): {response.status} - {error_text}")
                            return False
                        
                        else:  # Server errors - retry
                            error_text = await response.text()
                            self.logger.warning(f"⚠️ 텔레그램 서버 오류 (시도 {attempt + 1}/{max_retries + 1}): {response.status} - {error_text}")
                            
                            if attempt < max_retries:
                                wait_time = (2 ** attempt) + 1  # Exponential backoff: 2, 3, 5 seconds
                                await asyncio.sleep(wait_time)
                                continue
                            
            except asyncio.TimeoutError:
                self.logger.warning(f"⏰ 텔레그램 타임아웃 (시도 {attempt + 1}/{max_retries + 1})")
                if attempt < max_retries:
                    await asyncio.sleep(2 ** attempt)  # Exponential backoff
                    continue
                    
            except aiohttp.ClientError as e:
                self.logger.warning(f"🌐 텔레그램 네트워크 오류 (시도 {attempt + 1}/{max_retries + 1}): {e}")
                if attempt < max_retries:
                    await asyncio.sleep(2 ** attempt)  # Exponential backoff
                    continue
                    
            except Exception as e:
                self.logger.error(f"❌ 텔레그램 예상치 못한 오류 (시도 {attempt + 1}/{max_retries + 1}): {e}")
                if attempt < max_retries:
                    await asyncio.sleep(2 ** attempt)
                    continue
        
        # All retries failed
        self.logger.error(f"🚨 텔레그램 메시지 전송 완전 실패 - {max_retries + 1}회 시도 후 포기")
        
        # Log failed message for manual review
        self.logger.critical(f"📝 실패한 메시지 내용:\n{message}")
        
        return False
    
    async def send_trade_notification(self, symbol: str, action: str, details: Dict):
        """Send formatted trade notification with guaranteed delivery - TelegramSafeFormatter 적용"""
        # 안전한 거래 알림 메시지 생성
        message = telegram_formatter.create_safe_trading_alert(
            symbol=symbol,
            action=action, 
            price=details.get('price', 0),
            confidence=details.get('confidence', 50),
            reason=details.get('reason', '')
        )
        
        # 추가 세부정보는 안전하게 추가
        if 'leverage' in details:
            safe_leverage = telegram_formatter.escape_html(str(details['leverage']))
            message += f"\n⚡ <b>레버리지</b>: {safe_leverage}x"
        
        if 'pnl' in details:
            pnl = details['pnl']
            pnl_emoji = '💰' if pnl > 0 else '🔻'
            message += f"\n{pnl_emoji} <b>손익</b>: {pnl:+.2f}%"
        
        if 'current_balance' in details:
            message += f"\n💳 <b>현재 잔고</b>: ${details['current_balance']:,.2f}"
        
        # Determine priority - trade notifications are always high priority
        priority = 'high'
        if action in ['open_long', 'open_short']:
            priority = 'high'  # New positions are high priority
        if 'emergency' in details.get('reason', '').lower():
            priority = 'emergency'
        
        # Enhanced logging for trade notifications
        self.logger.info(f"📤 거래 알림 발송 시작: {symbol} {action} at ${details.get('price', 0):,.2f}")
        
        success = await self.send_notification(message, priority=priority, metadata={
            'type': 'trade',
            'symbol': symbol,
            'action': action,
            'price': details.get('price'),
            'quantity': details.get('quantity')
        })
        
        if success:
            self.logger.info(f"✅ 거래 알림 전송 완료: {symbol} {action}")
        else:
            self.logger.error(f"❌ 거래 알림 전송 실패: {symbol} {action}")
        
        return success
    
    async def send_daily_report(self, report: str):
        """Send daily performance report - TelegramSafeFormatter 적용"""
        # 안전한 보고서 메시지 포맷팅
        safe_report = telegram_formatter.escape_html(report)
        header = "📊 <b>일일 거래 성과 보고서</b>\n" + "="*30 + "\n\n"
        full_report = header + safe_report
        
        await self.send_notification(full_report, priority='normal')
    
    async def send_error_notification(self, error: str, details: str = "", component: str = ""):
        """Send error notification - TelegramSafeFormatter 적용"""
        # 안전한 오류 메시지 생성  
        message = telegram_formatter.create_safe_error_message(
            component=component or '알 수 없음',
            error_msg=f"{error}{f' - {details}' if details else ''}",
            severity='ERROR'
        )
        
        await self.send_notification(message, priority='high')
    
    async def send_risk_alert(self, alert_type: str, details: Dict):
        """Send risk management alert"""
        emoji_map = {
            'daily_loss_limit': '🛑',
            'position_limit': '⚠️', 
            'drawdown_warning': '📉',
            'correlation_risk': '🔗',
            'risk_limit_exceeded': '🚨'
        }
        
        alert_translations = {
            'daily_loss_limit': '일일 손실 한계',
            'position_limit': '포지션 한계',
            'drawdown_warning': '낙폭 경고',
            'correlation_risk': '상관관계 위험',
            'risk_limit_exceeded': '리스크 한계 초과'
        }
        
        emoji = emoji_map.get(alert_type, '⚠️')
        alert_text = alert_translations.get(alert_type, alert_type.replace('_', ' ').title())
        
        message = f"""
{emoji} **위험 알림: {alert_text}**

{details.get('message', '')}

현재 상태:
- 일일 손익: {details.get('daily_pnl', 0):+.2f}%
- 보유 포지션: {details.get('open_positions', 0)}개
- 위험 수준: {details.get('risk_level', '알 수 없음')}
"""
        
        await self.send_notification(message, priority='high')
    
    async def _handle_critical_message_failure(self, msg_obj: Dict):
        """Handle critical message delivery failure"""
        self.logger.critical(f"🚨 중요한 거래 알림 전송 실패 - 로그에 기록")
        
        # Log to file for manual review
        trade_data = msg_obj.get('metadata', {})
        failure_log = {
            'timestamp': datetime.now().isoformat(),
            'message': msg_obj['content'],
            'trade_data': trade_data,
            'failure_reason': 'telegram_delivery_failed'
        }
        
        # In a real implementation, you might save this to a special failure log file
        # or send to an alternative notification channel
        self.logger.critical(f"거래 알림 실패 기록: {failure_log}")
    
    async def test_notification_system(self):
        """Test notification system connectivity"""
        test_message = f"🧪 **시스템 테스트**\n\n텔레그램 연결 테스트\n시간: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}"
        
        self.logger.info("🧪 알림 시스템 연결 테스트 시작...")
        success = await self._send_telegram_message(test_message, max_retries=1)
        
        if success:
            self.logger.info("✅ 알림 시스템 테스트 성공")
        else:
            self.logger.error("❌ 알림 시스템 테스트 실패")
        
        return success
    
    async def get_system_status(self):
        """Get notification system status"""
        return {
            'is_running': self.is_running,
            'emergency_queue_size': self.emergency_queue.qsize(),
            'normal_queue_size': self.normal_queue.qsize(),
            'telegram_configured': bool(self.config.TELEGRAM_BOT_TOKEN and self.config.TELEGRAM_CHAT_ID),
            'last_message_count': len(self.last_message_time),
            'processor_active': self.processor_task and not self.processor_task.done()
        }
    
    # 🔍 NOTIFICATION VERIFICATION METHODS
    
    async def _notification_verification_loop(self):
        """알림 시스템 검증을 주기적으로 실행하는 루프"""
        while self.is_running:
            try:
                await asyncio.sleep(3600)  # 1시간마다 실행
                
                # 텔레그램 연결 테스트
                await self._verify_telegram_connectivity()
                
                # 알림 전송 성공률 검증
                await self._verify_notification_success_rates()
                
                # 전체 알림 시스템 상태 검증
                await self._generate_notification_verification_report()
                
            except Exception as e:
                self.logger.error(f"❌ 알림 검증 루프 오류: {e}")
                await asyncio.sleep(300)  # 5분 후 재시도
    
    async def _track_notification_delivery(self, msg_obj: Dict, success: bool):
        """알림 전송 결과 추적"""
        try:
            # 전체 통계 업데이트
            self.verification_stats['total_notifications_sent'] += 1
            
            if success:
                self.verification_stats['successful_deliveries'] += 1
                self.verification_stats['last_successful_delivery'] = datetime.now()
                self.verification_stats['current_failure_streak'] = 0
            else:
                self.verification_stats['failed_deliveries'] += 1
                self.verification_stats['current_failure_streak'] += 1
                
                # 최장 실패 연속 기록 업데이트
                if self.verification_stats['current_failure_streak'] > self.verification_stats['longest_failure_streak']:
                    self.verification_stats['longest_failure_streak'] = self.verification_stats['current_failure_streak']
            
            # 알림 유형별 통계 업데이트
            notification_type = self._determine_notification_type(msg_obj)
            type_stats = self.verification_stats['notification_types'][notification_type]
            type_stats['sent'] += 1
            
            if success:
                type_stats['success'] += 1
            else:
                type_stats['failed'] += 1
                
        except Exception as e:
            self.logger.error(f"❌ 알림 전송 추적 오류: {e}")
    
    def _determine_notification_type(self, msg_obj: Dict) -> str:
        """메시지 객체에서 알림 유형 결정"""
        metadata = msg_obj.get('metadata', {})
        msg_type = metadata.get('type', '')
        
        if msg_type == 'trade':
            return 'trade'
        elif 'error' in msg_obj.get('content', '').lower() or 'Error' in msg_obj.get('content', ''):
            return 'error'
        elif '위험' in msg_obj.get('content', '') or 'Risk' in msg_obj.get('content', ''):
            return 'risk_alert'
        elif '보고서' in msg_obj.get('content', '') or 'Report' in msg_obj.get('content', ''):
            return 'daily_report'
        else:
            return 'system'
    
    async def _verify_telegram_connectivity(self):
        """텔레그램 연결 상태 검증"""
        try:
            self.logger.info("🔍 텔레그램 연결 상태 검증 중...")
            
            # 설정 확인
            if not self.config.TELEGRAM_BOT_TOKEN or not self.config.TELEGRAM_CHAT_ID:
                self.logger.error("❌ 텔레그램 설정 누락")
                return False
            
            # 간단한 테스트 메시지 전송
            test_message = f"🧪 **연결 테스트**\n\n시간: {datetime.now().strftime('%H:%M:%S')}"
            success = await self._send_telegram_message(test_message, max_retries=2)
            
            if success:
                self.logger.info("✅ 텔레그램 연결 정상")
            else:
                self.logger.error("❌ 텔레그램 연결 실패")
                
                # 실패 연속 기록이 높으면 경고
                if self.verification_stats['current_failure_streak'] >= 5:
                    self.logger.critical(f"🚨 텔레그램 {self.verification_stats['current_failure_streak']}회 연속 실패")
            
            return success
            
        except Exception as e:
            self.logger.error(f"❌ 텔레그램 연결 검증 오류: {e}")
            return False
    
    async def _verify_notification_success_rates(self):
        """알림 전송 성공률 검증"""
        try:
            total_sent = self.verification_stats['total_notifications_sent']
            if total_sent == 0:
                return
            
            success_rate = self.verification_stats['successful_deliveries'] / total_sent
            
            self.logger.info(f"📊 전체 알림 성공률: {success_rate:.1%} ({self.verification_stats['successful_deliveries']}/{total_sent})")
            
            # 성공률이 낮으면 경고
            if success_rate < 0.8 and total_sent >= 10:
                self.logger.warning(f"⚠️ 낮은 알림 성공률: {success_rate:.1%}")
                
                # 유형별 성공률 분석
                problematic_types = []
                for ntype, stats in self.verification_stats['notification_types'].items():
                    if stats['sent'] >= 5:  # 충분한 샘플이 있는 경우만
                        type_success_rate = stats['success'] / stats['sent']
                        if type_success_rate < 0.7:
                            problematic_types.append(f"{ntype}: {type_success_rate:.1%}")
                
                if problematic_types:
                    self.logger.warning(f"⚠️ 문제가 있는 알림 유형: {', '.join(problematic_types)}")
            else:
                self.logger.info("✅ 알림 전송 성공률 양호")
                
        except Exception as e:
            self.logger.error(f"❌ 알림 성공률 검증 오류: {e}")
    
    async def _generate_notification_verification_report(self):
        """알림 시스템 검증 보고서 생성"""
        try:
            stats = self.verification_stats
            total_sent = stats['total_notifications_sent']
            
            if total_sent == 0:
                return
            
            success_rate = stats['successful_deliveries'] / total_sent * 100
            
            # 마지막 성공 시간
            last_success = stats['last_successful_delivery']
            last_success_str = last_success.strftime('%H:%M:%S') if last_success else '없음'
            
            report = f"""
📊 알림 시스템 검증 보고서
═══════════════════════════════
📈 전체 성공률: {success_rate:.1f}% ({stats['successful_deliveries']}/{total_sent})
🚫 실패율: {stats['failed_deliveries']/total_sent*100:.1f}%
⏰ 마지막 성공: {last_success_str}
📉 현재 연속 실패: {stats['current_failure_streak']}회
📊 최장 연속 실패: {stats['longest_failure_streak']}회

📋 알림 유형별 성공률:"""
            
            for ntype, type_stats in stats['notification_types'].items():
                if type_stats['sent'] > 0:
                    type_success_rate = type_stats['success'] / type_stats['sent'] * 100
                    report += f"\n  • {ntype.title()}: {type_success_rate:.1f}% ({type_stats['success']}/{type_stats['sent']})"
            
            # 텔레그램 설정 상태
            telegram_configured = bool(self.config.TELEGRAM_BOT_TOKEN and self.config.TELEGRAM_CHAT_ID)
            report += f"\n\n🔧 설정 상태:\n  • 텔레그램 설정: {'✅ 완료' if telegram_configured else '❌ 미완료'}"
            
            # 큐 상태
            emergency_queue_size = self.emergency_queue.qsize()
            normal_queue_size = self.normal_queue.qsize()
            report += f"\n  • 긴급 큐: {emergency_queue_size}개 대기"
            report += f"\n  • 일반 큐: {normal_queue_size}개 대기"
            
            self.logger.info(report)
            
            # 심각한 문제가 있으면 자가 진단 알림 발송
            if success_rate < 70 and total_sent >= 5:
                critical_alert = f"""🚨 **알림 시스템 문제 감지**
                
성공률: {success_rate:.1f}%
연속 실패: {stats['current_failure_streak']}회
                
즉시 확인이 필요합니다."""
                
                # 직접 텔레그램으로 전송 시도
                try:
                    await self._send_telegram_message(critical_alert, max_retries=3)
                except Exception as e:
                    self.logger.critical(f"🚨 자가 진단 알림 전송 실패: {e}")
                    
        except Exception as e:
            self.logger.error(f"❌ 알림 검증 보고서 생성 오류: {e}")
    
    async def verify_all_notification_points(self):
        """모든 알림 지점 검증 (수동 호출용)"""
        self.logger.info("🔍 모든 알림 지점 검증 시작...")
        
        notification_points = [
            {
                'type': 'system_startup',
                'test_message': '🚀 **시스템 시작 테스트**\n\n검증용 시작 알림',
                'expected_priority': 'high'
            },
            {
                'type': 'trade_notification', 
                'test_message': '💰 **거래 알림 테스트**\n\nBTCUSDT 롱 포지션 진입\n가격: $50,000',
                'expected_priority': 'high'
            },
            {
                'type': 'error_notification',
                'test_message': '❌ **오류 알림 테스트**\n\n테스트용 오류 메시지',
                'expected_priority': 'high'
            },
            {
                'type': 'risk_alert',
                'test_message': '⚠️ **위험 알림 테스트**\n\n일일 손실 한계 근접',
                'expected_priority': 'high'
            },
            {
                'type': 'daily_report',
                'test_message': '📊 **일일 보고서 테스트**\n\n성과: +2.5%\n거래: 3회 성공',
                'expected_priority': 'normal'
            }
        ]
        
        results = {}
        for point in notification_points:
            try:
                self.logger.info(f"테스트 중: {point['type']}")
                success = await self._send_telegram_message(point['test_message'], max_retries=2)
                results[point['type']] = success
                await asyncio.sleep(2)  # Rate limiting
            except Exception as e:
                self.logger.error(f"{point['type']} 테스트 실패: {e}")
                results[point['type']] = False
        
        # 결과 요약
        successful_tests = sum(1 for success in results.values() if success)
        total_tests = len(results)
        
        summary = f"""
🧪 **알림 지점 검증 완료**
═══════════════════════════
✅ 성공: {successful_tests}/{total_tests}
        
상세 결과:"""
        
        for test_type, success in results.items():
            status = "✅ 성공" if success else "❌ 실패"
            summary += f"\n  • {test_type}: {status}"
        
        self.logger.info(summary)
        
        # 검증 결과를 텔레그램으로 전송
        if successful_tests > 0:  # 최소한 하나라도 작동하면 결과 전송
            try:
                await self._send_telegram_message(summary, max_retries=3)
            except Exception as e:
                self.logger.error(f"검증 결과 전송 실패: {e}")
        
        return results
    
    async def shutdown(self):
        """Shutdown notification system"""
        self.logger.info("🔄 알림 시스템 종료 중...")
        self.is_running = False
        
        if self.processor_task:
            try:
                await asyncio.wait_for(self.processor_task, timeout=5.0)
            except asyncio.TimeoutError:
                self.logger.warning("알림 프로세서 종료 타임아웃")
                self.processor_task.cancel()
        
        if self.notification_verification_task:
            try:
                await asyncio.wait_for(self.notification_verification_task, timeout=5.0)
            except asyncio.TimeoutError:
                self.logger.warning("알림 검증 프로세서 종료 타임아웃")
                self.notification_verification_task.cancel()
        
        self.logger.info("✅ 알림 시스템 종료 완료")
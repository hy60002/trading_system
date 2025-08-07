"""
Bitget WebSocket Manager
Handles WebSocket connections and real-time data streaming
"""

import asyncio
import logging
import json
import time
from datetime import datetime
from typing import Dict, Optional, Any
import numpy as np
import websockets

try:
    from ...config.config import TradingConfig
    from ...utils.errors import ExchangeError
    from ...utils.websocket_resilient_manager import ws_manager
except ImportError:
    import sys
    import os
    sys.path.append(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
    from config.config import TradingConfig
    from utils.errors import ExchangeError
    from utils.websocket_resilient_manager import ws_manager


class WebSocketManager:
    """Manages WebSocket connections and real-time data streaming"""
    
    def __init__(self, config: TradingConfig):
        self.config = config
        self.logger = logging.getLogger(__name__)
        
        # WebSocket connection state
        self.ws_connected = False
        self.ws_task = None
        self.ws_health_task = None
        self.ws_reconnect_attempts = 0
        
        # Data storage
        self.price_data = {}
        self.orderbook_data = {}
        
        # Health monitoring
        self.last_ws_message_time = None
        self.ws_health_check_interval = self.config.WS_HEALTH_CHECK_INTERVAL
        self.ws_message_timeout = self.config.WS_MESSAGE_TIMEOUT
    
    async def start(self):
        """Start WebSocket manager with ResilientWebSocketManager"""
        self.logger.info("🚀 WebSocket Manager 시작 - Resilient 모드")
        
        # Bitget 선물 WebSocket 연결 설정
        success = await ws_manager.connect(
            name='bitget_futures',
            url='wss://ws.bitget.com/mix/v1/stream',
            params={'channels': ['ticker']},
            message_handler=self._handle_ws_message
        )
        
        if success:
            self.ws_connected = True
            self.logger.info("✅ Resilient WebSocket 연결 성공")
            
            # 기존 health monitor도 유지 (추가 모니터링용)
            self.ws_health_task = asyncio.create_task(self._websocket_health_monitor())
        else:
            self.logger.error("❌ Resilient WebSocket 연결 실패")
            
        return success
    
    async def stop(self):
        """Stop WebSocket manager with ResilientWebSocketManager"""
        self.logger.info("🛑 WebSocket Manager 종료 - Resilient 모드")
        
        # Resilient WebSocket Manager에서 연결 해제
        await ws_manager.disconnect('bitget_futures')
        
        self.ws_connected = False
        
        if self.ws_task and not self.ws_task.done():
            self.ws_task.cancel()
            
        if self.ws_health_task and not self.ws_health_task.done():
            self.ws_health_task.cancel()
    
    async def _handle_ws_message(self, data: Dict[str, Any]):
        """ResilientWebSocketManager용 메시지 핸들러"""
        try:
            # 메시지 수신 시간 업데이트
            self.last_ws_message_time = time.time()
            
            # 기존 메시지 처리 로직 호출
            await self._process_ws_message(data)
            
        except Exception as e:
            self.logger.error(f"WebSocket 메시지 처리 오류: {e}")
    
    async def _websocket_manager(self):
        """Enhanced WebSocket manager with better error handling and fallback mode"""
        max_consecutive_failures = 5
        consecutive_failures = 0
        fallback_mode = False
        
        while True:
            try:
                if not fallback_mode:
                    await self._connect_websocket()
                    consecutive_failures = 0
                    if fallback_mode:
                        self.logger.info("🔄 WebSocket 연결 복구 - 실시간 모드 재개")
                        fallback_mode = False
                else:
                    # Fallback mode: use REST API instead of WebSocket
                    await self._fallback_price_update()
                    await asyncio.sleep(5)
                    
            except Exception as e:
                self.ws_connected = False
                consecutive_failures += 1
                self.ws_reconnect_attempts += 1
                
                error_type = type(e).__name__
                self.logger.error(f"🚫 WebSocket 오류 ({error_type}) - 시도 {self.ws_reconnect_attempts}: {str(e)[:100]}")
                
                # Activate fallback mode after consecutive failures
                if consecutive_failures >= max_consecutive_failures and not fallback_mode:
                    self.logger.warning(f"[WARNING] WebSocket 연속 실패 {consecutive_failures}회 - 대체 모드 활성화")
                    fallback_mode = True
                    consecutive_failures = 0
                    await asyncio.sleep(10)
                    continue
                    
                # Calculate wait time based on error type
                if 'rate limit' in str(e).lower() or 'too many requests' in str(e).lower():
                    wait_time = 60  # 1 minute for rate limiting
                elif 'network' in str(e).lower() or 'timeout' in str(e).lower():
                    wait_time = self.config.NETWORK_RETRY_WAIT  # 네트워크 재시도 대기시간
                else:
                    # Exponential backoff with jitter
                    base_wait = min(120, 10 * (1.5 ** min(consecutive_failures, 5)))
                    jitter = base_wait * 0.2 * (0.5 - np.random.random())
                    wait_time = base_wait + jitter
                
                self.logger.info(f"[RETRY] {wait_time:.1f}초 후 WebSocket 재연결 시도...")
                await asyncio.sleep(wait_time)
    
    async def _connect_websocket(self):
        """Enhanced WebSocket connection with multiple URL fallbacks"""
        ws_urls = [
            "wss://ws.bitget.com/v2/ws/public",
            "wss://ws.bitgetapi.com/v2/ws/public", 
            "wss://ws.bitget.com/mix/v1/stream"
        ]
        
        for i, ws_url in enumerate(ws_urls):
            try:
                self.logger.info(f"🔌 WebSocket 연결 시도 ({i+1}/{len(ws_urls)}): {ws_url}")
                
                async with websockets.connect(
                    ws_url,
                    ping_interval=20,
                    ping_timeout=10,
                    close_timeout=10,
                    max_size=2**20  # 1MB message size limit
                ) as websocket:
                    self.ws_connected = True
                    self.ws_reconnect_attempts = 0
                    self.logger.info(f"[SUCCESS] WebSocket 연결 성공: {ws_url}")
                    
                    # Subscribe to channels
                    await self._subscribe_channels(websocket)
                    
                    # Message handling loop with health checks
                    await self._handle_websocket_messages(websocket)
                    
            except (websockets.exceptions.ConnectionClosed, 
                   websockets.exceptions.InvalidURI,
                   websockets.exceptions.InvalidHandshake) as e:
                self.logger.warning(f"[FAIL] WebSocket URL {i+1} 실패: {type(e).__name__} - {str(e)[:50]}")
                if i == len(ws_urls) - 1:  # Last URL failed
                    raise e
                continue
                
            except Exception as e:
                self.logger.error(f"❌ 예상치 못한 WebSocket 오류: {type(e).__name__}")
                if i == len(ws_urls) - 1:
                    raise e
                continue
        
        self.ws_connected = False
        raise ConnectionError("모든 WebSocket URL 연결 실패")
    
    async def _websocket_health_monitor(self):
        """WebSocket 연결 상태 모니터링"""
        while True:
            try:
                await asyncio.sleep(self.ws_health_check_interval)
                
                if self.ws_connected and self.last_ws_message_time:
                    # 마지막 메시지로부터 경과 시간 확인
                    time_since_last_message = (datetime.now() - self.last_ws_message_time).total_seconds()
                    
                    if time_since_last_message > self.ws_message_timeout:
                        self.logger.warning(f"⚠️ WebSocket 응답 없음 ({time_since_last_message:.0f}초) - 재연결 필요")
                        self.ws_connected = False
                        
                        # WebSocket 태스크 재시작
                        if self.ws_task and not self.ws_task.done():
                            self.ws_task.cancel()
                        self.ws_task = asyncio.create_task(self._websocket_manager())
                        
                elif not self.ws_connected:
                    self.logger.debug("🔍 WebSocket 연결 대기 중...")
                    
            except Exception as e:
                self.logger.error(f"❌ WebSocket 헬스체크 오류: {e}")
                await asyncio.sleep(10)
    
    async def _handle_websocket_messages(self, websocket):
        """Handle WebSocket messages with enhanced monitoring"""
        last_message_time = datetime.now()
        heartbeat_timeout = 90  # 1.5 minutes
        message_count = 0
        
        async for message in websocket:
            try:
                current_time = datetime.now()
                last_message_time = current_time
                self.last_ws_message_time = current_time
                message_count += 1
                
                await self._handle_ws_message(message)
                
                # Log connection health every 100 messages
                if message_count % 100 == 0:
                    self.logger.info(f"📊 WebSocket 건강 상태: {message_count}개 메시지 수신 완료")
                
                # Enhanced stale connection check
                if (current_time - last_message_time).total_seconds() > heartbeat_timeout:
                    self.logger.warning(f"⏰ WebSocket 응답 없음 ({heartbeat_timeout}초) - 재연결 실행")
                    break
                    
            except asyncio.CancelledError:
                self.logger.info("🚫 WebSocket 작업 취소됨")
                break
            except Exception as msg_error:
                self.logger.error(f"❌ 메시지 처리 오류: {msg_error}")
                continue
    
    async def _subscribe_channels(self, websocket):
        """Subscribe to WebSocket channels"""
        try:
            for symbol in self.config.SYMBOLS:
                # Subscribe to ticker updates
                subscribe_msg = {
                    "op": "subscribe",
                    "args": [{
                        "instType": "UMCBL",
                        "channel": "ticker",
                        "instId": symbol
                    }]
                }
                
                await websocket.send(json.dumps(subscribe_msg))
                self.logger.info(f"📡 {symbol} 실시간 데이터 구독 요청")
                await asyncio.sleep(0.1)  # Rate limiting
                
        except Exception as e:
            self.logger.error(f"❌ 채널 구독 오류: {e}")
            raise
    
    async def _handle_ws_message(self, message: str):
        """Handle individual WebSocket messages"""
        try:
            data = json.loads(message)
            
            # Handle different message types
            if 'data' in data and data.get('arg', {}).get('channel') == 'ticker':
                await self._process_ticker_data(data)
            elif 'event' in data:
                await self._process_event_message(data)
            
        except json.JSONDecodeError:
            self.logger.debug(f"JSON 파싱 실패: {message[:100]}")
        except Exception as e:
            self.logger.error(f"메시지 처리 오류: {e}")
    
    async def _process_ticker_data(self, data: Dict):
        """Process ticker data from WebSocket"""
        try:
            if 'data' not in data:
                return
                
            for ticker_data in data['data']:
                symbol = ticker_data.get('instId')
                if symbol:
                    # Clean symbol format
                    clean_symbol = symbol.replace('USDT', 'USDT')
                    
                    # Update price data
                    self.price_data[clean_symbol] = {
                        'price': float(ticker_data.get('last', 0)),
                        'volume': float(ticker_data.get('vol24h', 0)),
                        'change': float(ticker_data.get('change24h', 0)),
                        'timestamp': time.time()
                    }
                    
        except Exception as e:
            self.logger.error(f"티커 데이터 처리 오류: {e}")
    
    async def _process_event_message(self, data: Dict):
        """Process event messages from WebSocket"""
        try:
            event = data.get('event')
            
            if event == 'error':
                error_msg = data.get('msg', 'Unknown error')
                self.logger.error(f"WebSocket 오류: {error_msg}")
            elif event == 'subscribe':
                self.logger.info(f"✅ 구독 성공: {data.get('arg', {})}")
            
        except Exception as e:
            self.logger.error(f"이벤트 메시지 처리 오류: {e}")
    
    async def _fallback_price_update(self):
        """Fallback price update using REST API when WebSocket fails"""
        try:
            self.logger.debug("🔄 REST API 대체 모드로 가격 업데이트")
            # This would need to be implemented with the exchange REST API
            # For now, just mark that we're in fallback mode
            await asyncio.sleep(5)
            
        except Exception as e:
            self.logger.error(f"대체 모드 가격 업데이트 오류: {e}")
    
    def get_current_price(self, symbol: str) -> Optional[float]:
        """Get current price for symbol"""
        if symbol in self.price_data:
            return self.price_data[symbol].get('price')
        return None
    
    def is_connected(self) -> bool:
        """Check if WebSocket is connected - ResilientWebSocketManager 통합"""
        # ResilientWebSocketManager 상태도 확인
        resilient_status = ws_manager.get_connection_status('bitget_futures')
        resilient_healthy = resilient_status.get('is_healthy', False) if 'error' not in resilient_status else False
        
        return self.ws_connected and resilient_healthy
    
    def get_connection_status(self) -> Dict[str, Any]:
        """WebSocket 연결 상태 상세 정보"""
        resilient_status = ws_manager.get_connection_status('bitget_futures')
        
        return {
            'local_connected': self.ws_connected,
            'resilient_status': resilient_status,
            'last_message_time': self.last_ws_message_time,
            'reconnect_attempts': self.ws_reconnect_attempts,
            'price_data_count': len(self.price_data)
        }
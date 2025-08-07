"""
WebSocket Resilient Manager
안정적인 WebSocket 연결 관리자
"""

import asyncio
import logging
import json
import time
from typing import Dict, Any, Optional, Callable, List
from datetime import datetime, timedelta
import websockets
from websockets.exceptions import ConnectionClosed, InvalidStatusCode


class ResilientWebSocketManager:
    """복원력 있는 WebSocket 연결 관리자"""
    
    def __init__(self):
        self.logger = logging.getLogger(__name__)
        self.connections = {}  # 연결별 정보 저장
        self.reconnection_tasks = {}  # 재연결 작업 추적
        self.message_handlers = {}  # 메시지 핸들러
        
        # 설정
        self.max_reconnect_attempts = 10
        self.base_reconnect_delay = 2  # 초
        self.max_reconnect_delay = 60  # 초
        self.ping_interval = 30  # 초
        self.ping_timeout = 10  # 초
        self.response_timeout = 90  # 초
    
    async def connect(self, name: str, url: str, params: Dict[str, Any] = None,
                     message_handler: Callable = None) -> bool:
        """
        WebSocket 연결 생성
        
        Args:
            name: 연결 식별자
            url: WebSocket URL
            params: 연결 파라미터
            message_handler: 메시지 처리 함수
            
        Returns:
            연결 성공 여부
        """
        try:
            self.logger.info(f"WebSocket 연결 시작: {name}")
            
            # 연결 정보 초기화
            self.connections[name] = {
                'url': url,
                'params': params or {},
                'websocket': None,
                'last_ping': None,
                'last_pong': None,
                'last_message': None,
                'reconnect_count': 0,
                'is_connecting': False,
                'is_healthy': False,
                'status': 'disconnected'
            }
            
            if message_handler:
                self.message_handlers[name] = message_handler
            
            # 실제 연결 시도
            success = await self._establish_connection(name)
            
            if success:
                # 연결 모니터링 시작
                self._start_connection_monitor(name)
                self.logger.info(f"WebSocket 연결 성공: {name}")
                return True
            else:
                self.logger.error(f"WebSocket 연결 실패: {name}")
                return False
                
        except Exception as e:
            self.logger.error(f"WebSocket 연결 중 오류: {name}, {e}")
            return False
    
    async def _establish_connection(self, name: str) -> bool:
        """실제 WebSocket 연결 수행"""
        try:
            conn_info = self.connections[name]
            conn_info['is_connecting'] = True
            conn_info['status'] = 'connecting'
            
            # WebSocket 연결
            websocket = await websockets.connect(
                conn_info['url'],
                ping_interval=self.ping_interval,
                ping_timeout=self.ping_timeout,
                close_timeout=10
            )
            
            conn_info['websocket'] = websocket
            conn_info['is_connecting'] = False
            conn_info['is_healthy'] = True
            conn_info['status'] = 'connected'
            conn_info['last_ping'] = time.time()
            
            # 구독 메시지 전송 (필요한 경우)
            if conn_info['params']:
                await self._send_subscription(name, conn_info['params'])
            
            # 메시지 수신 태스크 시작
            asyncio.create_task(self._message_receiver(name))
            
            return True
            
        except Exception as e:
            self.logger.error(f"WebSocket 연결 수행 실패: {name}, {e}")
            conn_info = self.connections[name]
            conn_info['is_connecting'] = False
            conn_info['is_healthy'] = False
            conn_info['status'] = 'failed'
            return False
    
    async def _send_subscription(self, name: str, params: Dict[str, Any]):
        """구독 메시지 전송"""
        try:
            conn_info = self.connections[name]
            websocket = conn_info['websocket']
            
            if websocket and not getattr(websocket, 'closed', True):
                # Bitget 형식의 구독 메시지 생성
                subscription_msg = {
                    "op": "subscribe",
                    "args": params.get('channels', [])
                }
                
                await websocket.send(json.dumps(subscription_msg))
                self.logger.debug(f"구독 메시지 전송: {name}, {subscription_msg}")
                
        except Exception as e:
            self.logger.error(f"구독 메시지 전송 실패: {name}, {e}")
    
    async def _message_receiver(self, name: str):
        """메시지 수신 처리"""
        conn_info = self.connections[name]
        websocket = conn_info['websocket']
        
        try:
            async for message in websocket:
                conn_info['last_message'] = time.time()
                
                try:
                    # JSON 파싱
                    data = json.loads(message)
                    
                    # pong 응답 처리
                    if data.get('event') == 'pong':
                        conn_info['last_pong'] = time.time()
                        self.logger.debug(f"Pong 받음: {name}")
                        continue
                    
                    # 오류 응답 처리
                    if 'code' in data and data.get('code') != 0:
                        error_msg = data.get('msg', 'Unknown error')
                        self.logger.warning(f"WebSocket 오류 응답: {name}, {error_msg}")
                        continue
                    
                    # 메시지 핸들러 호출
                    if name in self.message_handlers:
                        asyncio.create_task(self.message_handlers[name](data))
                    
                except json.JSONDecodeError as e:
                    self.logger.warning(f"JSON 파싱 실패: {name}, {message[:100]}")
                except Exception as e:
                    self.logger.error(f"메시지 처리 중 오류: {name}, {e}")
                    
        except ConnectionClosed:
            self.logger.warning(f"WebSocket 연결 종료됨: {name}")
        except Exception as e:
            self.logger.error(f"메시지 수신 중 오류: {name}, {e}")
        finally:
            conn_info['is_healthy'] = False
            conn_info['status'] = 'disconnected'
            # 자동 재연결 시도
            if name not in self.reconnection_tasks:
                self.reconnection_tasks[name] = asyncio.create_task(
                    self._auto_reconnect(name)
                )
    
    def _start_connection_monitor(self, name: str):
        """연결 상태 모니터링 시작"""
        asyncio.create_task(self._connection_health_monitor(name))
    
    async def _connection_health_monitor(self, name: str):
        """연결 건강성 모니터링"""
        while name in self.connections:
            try:
                conn_info = self.connections[name]
                
                if not conn_info['is_healthy']:
                    await asyncio.sleep(10)
                    continue
                
                current_time = time.time()
                
                # 응답 시간 초과 체크
                if conn_info['last_message']:
                    time_since_last_message = current_time - conn_info['last_message']
                    if time_since_last_message > self.response_timeout:
                        self.logger.warning(f"WebSocket 응답 없음 ({time_since_last_message:.0f}초): {name}")
                        await self._trigger_reconnection(name)
                        continue
                
                # 주기적 핑 전송
                if conn_info['last_ping']:
                    time_since_ping = current_time - conn_info['last_ping']
                    if time_since_ping > self.ping_interval:
                        await self._send_ping(name)
                
                await asyncio.sleep(10)  # 10초마다 체크
                
            except Exception as e:
                self.logger.error(f"연결 모니터링 오류: {name}, {e}")
                await asyncio.sleep(10)
    
    async def _send_ping(self, name: str):
        """핑 메시지 전송"""
        try:
            conn_info = self.connections[name]
            websocket = conn_info['websocket']
            
            if websocket and not getattr(websocket, 'closed', True):
                ping_msg = {"op": "ping"}
                await websocket.send(json.dumps(ping_msg))
                conn_info['last_ping'] = time.time()
                self.logger.debug(f"Ping 전송: {name}")
                
        except Exception as e:
            self.logger.error(f"Ping 전송 실패: {name}, {e}")
            await self._trigger_reconnection(name)
    
    async def _trigger_reconnection(self, name: str):
        """재연결 트리거"""
        self.logger.info(f"재연결 트리거: {name}")
        
        conn_info = self.connections[name]
        conn_info['is_healthy'] = False
        conn_info['status'] = 'reconnecting'
        
        # 기존 연결 종료
        if conn_info['websocket']:
            try:
                await conn_info['websocket'].close()
            except Exception:
                pass
        
        # 재연결 태스크 시작
        if name not in self.reconnection_tasks:
            self.reconnection_tasks[name] = asyncio.create_task(
                self._auto_reconnect(name)
            )
    
    async def _auto_reconnect(self, name: str):
        """자동 재연결"""
        conn_info = self.connections[name]
        
        while conn_info['reconnect_count'] < self.max_reconnect_attempts:
            try:
                conn_info['reconnect_count'] += 1
                delay = min(
                    self.base_reconnect_delay * (2 ** (conn_info['reconnect_count'] - 1)),
                    self.max_reconnect_delay
                )
                
                self.logger.info(f"재연결 시도 {conn_info['reconnect_count']}/{self.max_reconnect_attempts}: {name} (지연: {delay}초)")
                
                await asyncio.sleep(delay)
                
                success = await self._establish_connection(name)
                
                if success:
                    self.logger.info(f"재연결 성공: {name}")
                    conn_info['reconnect_count'] = 0
                    if name in self.reconnection_tasks:
                        del self.reconnection_tasks[name]
                    return
                    
            except Exception as e:
                self.logger.error(f"재연결 시도 중 오류: {name}, {e}")
        
        # 최대 재시도 횟수 초과
        self.logger.error(f"재연결 최대 시도 횟수 초과: {name}")
        conn_info['status'] = 'failed'
        if name in self.reconnection_tasks:
            del self.reconnection_tasks[name]
    
    def get_connection_status(self, name: str = None) -> Dict[str, Any]:
        """연결 상태 정보 반환"""
        if name:
            if name in self.connections:
                conn = self.connections[name]
                return {
                    'name': name,
                    'status': conn['status'],
                    'is_healthy': conn['is_healthy'],
                    'reconnect_count': conn['reconnect_count'],
                    'last_message_age': time.time() - conn['last_message'] if conn['last_message'] else None
                }
            else:
                return {'error': f'Connection {name} not found'}
        else:
            # 전체 연결 상태
            status = {}
            for conn_name, conn_info in self.connections.items():
                status[conn_name] = {
                    'status': conn_info['status'],
                    'is_healthy': conn_info['is_healthy'],
                    'reconnect_count': conn_info['reconnect_count']
                }
            return status
    
    async def disconnect(self, name: str):
        """연결 종료"""
        if name in self.connections:
            conn_info = self.connections[name]
            
            # 재연결 태스크 중단
            if name in self.reconnection_tasks:
                self.reconnection_tasks[name].cancel()
                del self.reconnection_tasks[name]
            
            # WebSocket 연결 종료
            if conn_info['websocket']:
                await conn_info['websocket'].close()
            
            # 연결 정보 제거
            del self.connections[name]
            if name in self.message_handlers:
                del self.message_handlers[name]
            
            self.logger.info(f"WebSocket 연결 종료: {name}")


# 전역 인스턴스
ws_manager = ResilientWebSocketManager()
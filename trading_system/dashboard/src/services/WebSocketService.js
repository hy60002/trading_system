/**
 * @fileoverview WebSocket 서비스 - 실시간 데이터 통신
 * @description 향상된 WebSocket 관리 시스템
 */

import { eventBus } from '../core/EventBus.js';
import { globalStore } from '../core/Store.js';

/**
 * WebSocket 서비스 클래스
 * @class WebSocketService
 */
export class WebSocketService {
    constructor() {
        this.ws = null;
        this.reconnectAttempts = 0;
        this.maxReconnectAttempts = 10;
        this.reconnectDelay = 1000;
        this.maxReconnectDelay = 30000;
        this.heartbeatInterval = null;
        this.heartbeatTimeout = null;
        this.isConnected = false;
        this.isReconnecting = false;
        this.messageQueue = [];
        this.subscriptions = new Set();
        
        // 연결 상태 추적
        this.connectionState = 'disconnected'; // 'connecting', 'connected', 'disconnected', 'error'
        
        // 메시지 통계
        this.stats = {
            messagesReceived: 0,
            messagesSent: 0,
            reconnectCount: 0,
            lastConnectedAt: null,
            lastDisconnectedAt: null,
            averageLatency: 0,
            latencyHistory: []
        };

        // 메시지 배치 처리
        this.batchedMessages = [];
        this.batchProcessingScheduled = false;
        this.batchSize = 10;
        this.batchDelay = 16; // ~60fps
        
        this.initializeEventListeners();
    }

    /**
     * 이벤트 리스너 초기화
     * @private
     */
    initializeEventListeners() {
        // 브라우저 이벤트 처리
        if (typeof window !== 'undefined') {
            window.addEventListener('online', () => {
                if (this.connectionState === 'disconnected') {
                    this.connect();
                }
            });

            window.addEventListener('offline', () => {
                this.updateConnectionState('disconnected');
                eventBus.emit('websocket:offline');
            });

            // 페이지 언로드 시 정리
            window.addEventListener('beforeunload', () => {
                this.disconnect();
            });
        }
    }

    /**
     * WebSocket 연결
     * @param {string} [url] - WebSocket URL
     * @returns {Promise<void>}
     */
    async connect(url = null) {
        if (this.isConnected || this.isReconnecting) {
            return;
        }

        try {
            this.isReconnecting = true;
            this.updateConnectionState('connecting');
            
            const wsUrl = url || this.getWebSocketURL();
            console.log(`🔌 WebSocket 연결 시도: ${wsUrl}`);
            
            this.ws = new WebSocket(wsUrl);
            this.setupWebSocketHandlers();
            
            // 연결 타임아웃 설정
            const connectTimeout = setTimeout(() => {
                if (this.connectionState === 'connecting') {
                    this.ws.close();
                    throw new Error('Connection timeout');
                }
            }, 10000);

            // 연결 완료까지 대기
            await new Promise((resolve, reject) => {
                const onOpen = () => {
                    clearTimeout(connectTimeout);
                    this.ws.removeEventListener('open', onOpen);
                    this.ws.removeEventListener('error', onError);
                    resolve();
                };
                
                const onError = (error) => {
                    clearTimeout(connectTimeout);
                    this.ws.removeEventListener('open', onOpen);
                    this.ws.removeEventListener('error', onError);
                    reject(error);
                };
                
                this.ws.addEventListener('open', onOpen);
                this.ws.addEventListener('error', onError);
            });
            
        } catch (error) {
            console.error('WebSocket 연결 실패:', error);
            this.handleConnectionError(error);
            throw error;
        } finally {
            this.isReconnecting = false;
        }
    }

    /**
     * WebSocket URL 생성
     * @returns {string} WebSocket URL
     * @private
     */
    getWebSocketURL() {
        const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
        const host = window.location.host;
        return `${protocol}//${host}/ws/dashboard`;
    }

    /**
     * WebSocket 이벤트 핸들러 설정
     * @private
     */
    setupWebSocketHandlers() {
        this.ws.onopen = this.handleOpen.bind(this);
        this.ws.onmessage = this.handleMessage.bind(this);
        this.ws.onclose = this.handleClose.bind(this);
        this.ws.onerror = this.handleError.bind(this);
    }

    /**
     * WebSocket 연결 성공 처리
     * @param {Event} event - 연결 이벤트
     * @private
     */
    handleOpen(event) {
        console.log('✅ WebSocket 연결 성공');
        
        this.isConnected = true;
        this.reconnectAttempts = 0;
        this.reconnectDelay = 1000;
        this.stats.lastConnectedAt = Date.now();
        this.stats.reconnectCount++;
        
        this.updateConnectionState('connected');
        this.startHeartbeat();
        this.processPendingMessages();
        this.resubscribeChannels();
        
        // 이벤트 발생
        eventBus.emit('websocket:connected', {
            timestamp: Date.now(),
            reconnectCount: this.stats.reconnectCount
        });
        
        // 스토어 상태 업데이트
        globalStore.dispatch({
            type: 'SET_SYSTEM_STATUS',
            payload: { websocketConnected: true }
        });
    }

    /**
     * WebSocket 메시지 처리
     * @param {MessageEvent} event - 메시지 이벤트
     * @private
     */
    handleMessage(event) {
        this.stats.messagesReceived++;
        
        try {
            const data = JSON.parse(event.data);
            this.processMessage(data);
        } catch (error) {
            console.error('WebSocket 메시지 파싱 실패:', error, event.data);
            eventBus.emit('websocket:parse_error', { error, rawData: event.data });
        }
    }

    /**
     * 메시지 처리 (배치 방식)
     * @param {Object} data - 메시지 데이터
     * @private
     */
    processMessage(data) {
        // 배치에 메시지 추가
        this.batchedMessages.push({
            ...data,
            receivedAt: Date.now()
        });

        // 배치 처리 스케줄링
        if (!this.batchProcessingScheduled) {
            this.batchProcessingScheduled = true;
            
            // 급한 메시지는 즉시 처리
            if (this.isUrgentMessage(data)) {
                this.processBatchedMessages();
            } else {
                // 일반 메시지는 배치로 처리
                requestAnimationFrame(() => {
                    setTimeout(() => this.processBatchedMessages(), this.batchDelay);
                });
            }
        }
    }

    /**
     * 급한 메시지인지 확인
     * @param {Object} data - 메시지 데이터
     * @returns {boolean} 급한 메시지 여부
     * @private
     */
    isUrgentMessage(data) {
        const urgentTypes = [
            'emergency_alert',
            'position_liquidation',
            'system_error',
            'connection_error'
        ];
        return urgentTypes.includes(data.type);
    }

    /**
     * 배치된 메시지들 처리
     * @private
     */
    processBatchedMessages() {
        if (this.batchedMessages.length === 0) {
            this.batchProcessingScheduled = false;
            return;
        }

        const messages = this.batchedMessages.splice(0, this.batchSize);
        this.batchProcessingScheduled = false;

        // 메시지 타입별로 그룹화
        const messagesByType = new Map();
        messages.forEach(msg => {
            if (!messagesByType.has(msg.type)) {
                messagesByType.set(msg.type, []);
            }
            messagesByType.get(msg.type).push(msg);
        });

        // 타입별로 처리
        messagesByType.forEach((msgs, type) => {
            this.handleMessageType(type, msgs);
        });

        // 남은 메시지가 있으면 다시 스케줄링
        if (this.batchedMessages.length > 0) {
            this.batchProcessingScheduled = true;
            requestAnimationFrame(() => {
                setTimeout(() => this.processBatchedMessages(), this.batchDelay);
            });
        }
    }

    /**
     * 메시지 타입별 처리
     * @param {string} type - 메시지 타입
     * @param {Array} messages - 메시지 배열
     * @private
     */
    handleMessageType(type, messages) {
        const latestMessage = messages[messages.length - 1];
        
        switch (type) {
            case 'heartbeat':
                this.handleHeartbeat(latestMessage);
                break;
                
            case 'price_update':
                this.handlePriceUpdates(messages);
                break;
                
            case 'position_update':
                this.handlePositionUpdate(latestMessage);
                break;
                
            case 'balance_update':
                this.handleBalanceUpdate(latestMessage);
                break;
                
            case 'trade_executed':
                this.handleTradeExecuted(latestMessage);
                break;
                
            case 'notification':
                messages.forEach(msg => this.handleNotification(msg));
                break;
                
            case 'system_status':
                this.handleSystemStatus(latestMessage);
                break;
                
            default:
                console.log(`알 수 없는 메시지 타입: ${type}`, latestMessage);
        }

        // 이벤트 버스로 메시지 전달
        eventBus.emit(`websocket:${type}`, messages.length === 1 ? latestMessage : messages);
    }

    /**
     * 하트비트 처리
     * @param {Object} data - 하트비트 데이터
     * @private
     */
    handleHeartbeat(data) {
        if (data.timestamp) {
            const latency = Date.now() - data.timestamp;
            this.updateLatencyStats(latency);
        }
        
        // 하트비트 응답 전송
        this.send({
            type: 'heartbeat_response',
            timestamp: Date.now()
        });
    }

    /**
     * 가격 업데이트 처리 (배치)
     * @param {Array} messages - 가격 업데이트 메시지들
     * @private
     */
    handlePriceUpdates(messages) {
        const priceMap = new Map();
        
        // 최신 가격으로 업데이트
        messages.forEach(msg => {
            if (msg.payload) {
                Object.entries(msg.payload).forEach(([symbol, price]) => {
                    priceMap.set(symbol, price);
                });
            }
        });
        
        // 스토어 업데이트
        globalStore.dispatch({
            type: 'UPDATE_CHART_DATA',
            payload: {
                chartType: 'priceData',
                data: priceMap
            }
        });
    }

    /**
     * 포지션 업데이트 처리
     * @param {Object} data - 포지션 데이터
     * @private
     */
    handlePositionUpdate(data) {
        globalStore.dispatch({
            type: 'UPDATE_POSITIONS',
            payload: data.payload
        });
    }

    /**
     * 잔고 업데이트 처리
     * @param {Object} data - 잔고 데이터
     * @private
     */
    handleBalanceUpdate(data) {
        globalStore.dispatch({
            type: 'UPDATE_BALANCE',
            payload: data.payload
        });
    }

    /**
     * 거래 실행 처리
     * @param {Object} data - 거래 데이터
     * @private
     */
    handleTradeExecuted(data) {
        // 알림 추가
        globalStore.dispatch({
            type: 'ADD_NOTIFICATION',
            payload: {
                type: 'trade',
                message: `거래 실행: ${data.payload.symbol} ${data.payload.side}`,
                timestamp: Date.now(),
                data: data.payload
            }
        });
    }

    /**
     * 알림 처리
     * @param {Object} data - 알림 데이터
     * @private
     */
    handleNotification(data) {
        globalStore.dispatch({
            type: 'ADD_NOTIFICATION',
            payload: {
                ...data.payload,
                timestamp: Date.now()
            }
        });
    }

    /**
     * 시스템 상태 처리
     * @param {Object} data - 시스템 상태 데이터
     * @private
     */
    handleSystemStatus(data) {
        globalStore.dispatch({
            type: 'SET_SYSTEM_STATUS',
            payload: data.payload
        });
    }

    /**
     * WebSocket 연결 종료 처리
     * @param {CloseEvent} event - 종료 이벤트
     * @private
     */
    handleClose(event) {
        console.log(`WebSocket 연결 종료: ${event.code} - ${event.reason}`);
        
        this.isConnected = false;
        this.stats.lastDisconnectedAt = Date.now();
        this.stopHeartbeat();
        
        this.updateConnectionState('disconnected');
        
        // 스토어 상태 업데이트
        globalStore.dispatch({
            type: 'SET_SYSTEM_STATUS',
            payload: { websocketConnected: false }
        });
        
        eventBus.emit('websocket:disconnected', {
            code: event.code,
            reason: event.reason,
            timestamp: Date.now()
        });

        // 정상 종료가 아닌 경우 재연결 시도
        if (event.code !== 1000 && event.code !== 1001) {
            this.scheduleReconnect();
        }
    }

    /**
     * WebSocket 에러 처리
     * @param {Event} event - 에러 이벤트
     * @private
     */
    handleError(event) {
        console.error('WebSocket 에러:', event);
        this.updateConnectionState('error');
        
        eventBus.emit('websocket:error', {
            error: event,
            timestamp: Date.now()
        });
    }

    /**
     * 연결 에러 처리
     * @param {Error} error - 에러 객체
     * @private
     */
    handleConnectionError(error) {
        this.updateConnectionState('error');
        
        globalStore.dispatch({
            type: 'SET_SYSTEM_STATUS',
            payload: {
                websocketConnected: false,
                errors: [error.message]
            }
        });
    }

    /**
     * 재연결 스케줄링
     * @private
     */
    scheduleReconnect() {
        if (this.reconnectAttempts >= this.maxReconnectAttempts) {
            console.error('WebSocket 재연결 최대 시도 횟수 초과');
            eventBus.emit('websocket:reconnect_failed');
            return;
        }

        this.reconnectAttempts++;
        const delay = Math.min(
            this.reconnectDelay * Math.pow(2, this.reconnectAttempts - 1),
            this.maxReconnectDelay
        );

        console.log(`WebSocket 재연결 시도 ${this.reconnectAttempts}/${this.maxReconnectAttempts} (${delay}ms 후)`);
        
        setTimeout(() => {
            if (!this.isConnected) {
                this.connect().catch(error => {
                    console.error('재연결 실패:', error);
                });
            }
        }, delay);
    }

    /**
     * 하트비트 시작
     * @private
     */
    startHeartbeat() {
        this.stopHeartbeat();
        
        this.heartbeatInterval = setInterval(() => {
            if (this.isConnected) {
                this.send({
                    type: 'heartbeat',
                    timestamp: Date.now()
                });
            }
        }, 30000); // 30초마다
    }

    /**
     * 하트비트 중지
     * @private
     */
    stopHeartbeat() {
        if (this.heartbeatInterval) {
            clearInterval(this.heartbeatInterval);
            this.heartbeatInterval = null;
        }
        
        if (this.heartbeatTimeout) {
            clearTimeout(this.heartbeatTimeout);
            this.heartbeatTimeout = null;
        }
    }

    /**
     * 메시지 전송
     * @param {Object} data - 전송할 데이터
     * @returns {boolean} 전송 성공 여부
     */
    send(data) {
        if (!this.isConnected || !this.ws) {
            this.messageQueue.push(data);
            return false;
        }

        try {
            this.ws.send(JSON.stringify(data));
            this.stats.messagesSent++;
            return true;
        } catch (error) {
            console.error('WebSocket 메시지 전송 실패:', error);
            this.messageQueue.push(data);
            return false;
        }
    }

    /**
     * 채널 구독
     * @param {string} channel - 채널 이름
     * @param {Object} [params] - 구독 파라미터
     */
    subscribe(channel, params = {}) {
        const subscription = { channel, params };
        this.subscriptions.add(subscription);
        
        this.send({
            type: 'subscribe',
            channel,
            params
        });
    }

    /**
     * 채널 구독 해제
     * @param {string} channel - 채널 이름
     */
    unsubscribe(channel) {
        this.subscriptions.forEach(sub => {
            if (sub.channel === channel) {
                this.subscriptions.delete(sub);
            }
        });
        
        this.send({
            type: 'unsubscribe',
            channel
        });
    }

    /**
     * 모든 채널 재구독
     * @private
     */
    resubscribeChannels() {
        this.subscriptions.forEach(subscription => {
            this.send({
                type: 'subscribe',
                channel: subscription.channel,
                params: subscription.params
            });
        });
    }

    /**
     * 대기 중인 메시지 처리
     * @private
     */
    processPendingMessages() {
        while (this.messageQueue.length > 0) {
            const message = this.messageQueue.shift();
            this.send(message);
        }
    }

    /**
     * 연결 상태 업데이트
     * @param {string} state - 새로운 상태
     * @private
     */
    updateConnectionState(state) {
        const previousState = this.connectionState;
        this.connectionState = state;
        
        if (previousState !== state) {
            eventBus.emit('websocket:state_change', {
                previous: previousState,
                current: state,
                timestamp: Date.now()
            });
        }
    }

    /**
     * 지연 시간 통계 업데이트
     * @param {number} latency - 지연 시간 (ms)
     * @private
     */
    updateLatencyStats(latency) {
        this.stats.latencyHistory.push(latency);
        
        // 최근 50개 지연 시간만 유지
        if (this.stats.latencyHistory.length > 50) {
            this.stats.latencyHistory.shift();
        }
        
        // 평균 지연 시간 계산
        this.stats.averageLatency = 
            this.stats.latencyHistory.reduce((sum, lat) => sum + lat, 0) / 
            this.stats.latencyHistory.length;
    }

    /**
     * WebSocket 연결 종료
     */
    disconnect() {
        if (this.ws) {
            this.ws.close(1000, 'Client disconnect');
        }
        
        this.stopHeartbeat();
        this.isConnected = false;
        this.isReconnecting = false;
        this.reconnectAttempts = 0;
        this.messageQueue = [];
        this.subscriptions.clear();
        this.batchedMessages = [];
        
        this.updateConnectionState('disconnected');
    }

    /**
     * 연결 상태 확인
     * @returns {boolean} 연결 상태
     */
    isConnectionAlive() {
        return this.isConnected && this.ws && this.ws.readyState === WebSocket.OPEN;
    }

    /**
     * 통계 정보 가져오기
     * @returns {Object} 통계 정보
     */
    getStats() {
        return {
            ...this.stats,
            connectionState: this.connectionState,
            reconnectAttempts: this.reconnectAttempts,
            queuedMessages: this.messageQueue.length,
            subscriptions: this.subscriptions.size,
            batchedMessages: this.batchedMessages.length
        };
    }

    /**
     * 통계 리셋
     */
    resetStats() {
        this.stats = {
            messagesReceived: 0,
            messagesSent: 0,
            reconnectCount: 0,
            lastConnectedAt: null,
            lastDisconnectedAt: null,
            averageLatency: 0,
            latencyHistory: []
        };
    }
}

// 전역 WebSocket 서비스 인스턴스
export const webSocketService = new WebSocketService();

// 개발 모드에서 전역 접근 가능하게 설정
if (typeof window !== 'undefined' && process.env.NODE_ENV === 'development') {
    window.__TRADING_DASHBOARD_WEBSOCKET__ = webSocketService;
}
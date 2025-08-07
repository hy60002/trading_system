import { BaseComponent } from '../core/BaseComponent.js';

/**
 * 강화된 WebSocket 서비스
 * - 지수 백오프 재연결
 * - 연결 상태 모니터링
 * - 하트비트 메커니즘
 * - 메시지 순서 보장
 * - 자동 구독 복구
 */
export class EnhancedWebSocketService extends BaseComponent {
    constructor(options = {}) {
        super(null, options);
        
        // 연결 설정
        this.wsUrl = options.wsUrl || 'wss://stream.bitget.com/mix/v1/stream';
        this.protocols = options.protocols || [];
        this.ws = null;
        
        // 연결 상태
        this.connectionState = {
            status: 'disconnected', // disconnected, connecting, connected, reconnecting, error
            lastConnected: null,
            lastDisconnected: null,
            totalConnections: 0,
            totalDisconnections: 0
        };
        
        // 재연결 설정 (지수 백오프)
        this.reconnectConfig = {
            enabled: options.reconnect !== false,
            attempts: 0,
            maxAttempts: options.maxReconnectAttempts || 10,
            baseDelay: options.baseReconnectDelay || 1000, // 1초
            maxDelay: options.maxReconnectDelay || 30000,   // 30초
            backoffFactor: options.backoffFactor || 2,
            jitter: options.jitter !== false
        };
        
        // 하트비트 설정
        this.heartbeat = {
            enabled: options.heartbeat !== false,
            interval: options.heartbeatInterval || 30000,  // 30초
            timeout: options.heartbeatTimeout || 10000,    // 10초
            intervalId: null,
            timeoutId: null,
            lastPong: null,
            missedPongs: 0,
            maxMissedPongs: options.maxMissedPongs || 3
        };
        
        // 메시지 관리
        this.messageQueue = [];
        this.pendingMessages = new Map(); // 응답 대기 메시지
        this.messageId = 0;
        this.maxQueueSize = options.maxQueueSize || 1000;
        
        // 구독 관리
        this.subscriptions = new Map();
        this.autoResubscribe = options.autoResubscribe !== false;
        
        // 메시지 순서 보장
        this.sequenceNumber = 0;
        this.receivedSequences = new Set();
        this.outOfOrderBuffer = new Map();
        
        // 성능 모니터링
        this.metrics = {
            messagesReceived: 0,
            messagesSent: 0,
            bytesReceived: 0,
            bytesSent: 0,
            averageLatency: 0,
            latencyHistory: [],
            errorCount: 0,
            reconnectCount: 0,
            uptime: 0,
            lastUptimeCheck: Date.now()
        };
        
        // 이벤트 핸들러
        this.eventHandlers = {
            onOpen: null,
            onMessage: null,
            onClose: null,
            onError: null,
            onReconnect: null
        };
        
        // 연결 품질 관리
        this.connectionQuality = {
            score: 100, // 0-100
            latency: 0,
            stability: 100,
            throughput: 0
        };
        
        this.init();
    }
    
    /**
     * 초기화
     */
    init() {
        this.setupConnectionMonitoring();
        this.startMetricsCollection();
        this.emit('webSocketServiceInitialized');
    }
    
    /**
     * WebSocket 연결
     */
    async connect() {
        if (this.connectionState.status === 'connected' || 
            this.connectionState.status === 'connecting') {
            return;
        }
        
        try {
            this.connectionState.status = 'connecting';
            this.emit('connectionStateChanged', 'connecting');
            
            // WebSocket 인스턴스 생성
            this.ws = new WebSocket(this.wsUrl, this.protocols);
            this.setupWebSocketEventHandlers();
            
            // 연결 타임아웃 설정
            const connectTimeout = setTimeout(() => {
                if (this.connectionState.status === 'connecting') {
                    this.ws.close();
                    this.handleConnectionError(new Error('Connection timeout'));
                }
            }, 10000);
            
            // 연결 성공 시 타임아웃 클리어
            this.ws.addEventListener('open', () => {
                clearTimeout(connectTimeout);
            }, { once: true });
            
        } catch (error) {
            this.handleConnectionError(error);
        }
    }
    
    /**
     * WebSocket 이벤트 핸들러 설정
     */
    setupWebSocketEventHandlers() {
        this.ws.onopen = (event) => {
            this.handleConnectionOpen(event);
        };
        
        this.ws.onmessage = (event) => {
            this.handleMessage(event);
        };
        
        this.ws.onclose = (event) => {
            this.handleConnectionClose(event);
        };
        
        this.ws.onerror = (event) => {
            this.handleConnectionError(event);
        };
    }
    
    /**
     * 연결 성공 처리
     */
    handleConnectionOpen(event) {
        console.log('✅ WebSocket connected');
        
        // 상태 업데이트
        this.connectionState.status = 'connected';
        this.connectionState.lastConnected = Date.now();
        this.connectionState.totalConnections++;
        
        // 재연결 카운터 리셋
        this.reconnectConfig.attempts = 0;
        
        // 큐된 메시지 전송
        this.flushMessageQueue();
        
        // 하트비트 시작
        this.startHeartbeat();
        
        // 구독 복구
        if (this.autoResubscribe && this.metrics.reconnectCount > 0) {
            this.resubscribeAll();
        }
        
        // 이벤트 발생
        this.emit('connectionStateChanged', 'connected');
        this.emit('connected', event);
        
        if (this.eventHandlers.onOpen) {
            this.eventHandlers.onOpen(event);
        }
        
        // 연결 품질 초기화
        this.connectionQuality.score = 100;
        this.updateConnectionMetrics();
    }
    
    /**
     * 메시지 수신 처리
     */
    handleMessage(event) {
        try {
            const startTime = performance.now();
            const data = JSON.parse(event.data);
            
            // 메트릭 업데이트
            this.metrics.messagesReceived++;
            this.metrics.bytesReceived += event.data.length;
            
            // 하트비트 응답 처리
            if (this.isHeartbeatResponse(data)) {
                this.handleHeartbeatResponse(data);
                return;
            }
            
            // 시퀀스 번호 확인 (순서 보장)
            if (data.sequence && this.isValidSequence(data.sequence)) {
                this.processMessage(data);
            } else if (data.sequence) {
                this.bufferOutOfOrderMessage(data);
            } else {
                // 시퀀스 번호가 없는 메시지는 바로 처리
                this.processMessage(data);
            }
            
            // 지연시간 계산
            const processingTime = performance.now() - startTime;
            this.updateLatencyMetrics(processingTime);
            
            // 연결 품질 업데이트
            this.updateConnectionQuality();
            
        } catch (error) {
            this.metrics.errorCount++;
            this.emit('messageError', { error, rawData: event.data });
            console.error('Message processing error:', error);
        }
    }
    
    /**
     * 메시지 처리
     */
    processMessage(data) {
        // 이벤트 발생
        this.emit('message', data);
        
        if (this.eventHandlers.onMessage) {
            this.eventHandlers.onMessage(data);
        }
        
        // 응답 대기 메시지 확인
        if (data.id && this.pendingMessages.has(data.id)) {
            const pending = this.pendingMessages.get(data.id);
            clearTimeout(pending.timeout);
            this.pendingMessages.delete(data.id);
            
            if (pending.resolve) {
                pending.resolve(data);
            }
        }
    }
    
    /**
     * 연결 종료 처리
     */
    handleConnectionClose(event) {
        console.warn('🔌 WebSocket disconnected:', event.code, event.reason);
        
        // 상태 업데이트
        this.connectionState.status = 'disconnected';
        this.connectionState.lastDisconnected = Date.now();
        this.connectionState.totalDisconnections++;
        
        // 하트비트 중지
        this.stopHeartbeat();
        
        // 대기 중인 메시지들 타임아웃 처리
        this.timeoutPendingMessages();
        
        // 이벤트 발생
        this.emit('connectionStateChanged', 'disconnected');
        this.emit('disconnected', event);
        
        if (this.eventHandlers.onClose) {
            this.eventHandlers.onClose(event);
        }
        
        // 자동 재연결 시도
        if (this.reconnectConfig.enabled && !this.isIntentionalClose(event.code)) {
            this.scheduleReconnect();
        }
        
        // 연결 품질 저하
        this.connectionQuality.score = 0;
    }
    
    /**
     * 연결 에러 처리
     */
    handleConnectionError(event) {
        console.error('❌ WebSocket error:', event);
        
        this.metrics.errorCount++;
        this.connectionState.status = 'error';
        
        // 이벤트 발생
        this.emit('connectionStateChanged', 'error');
        this.emit('error', event);
        
        if (this.eventHandlers.onError) {
            this.eventHandlers.onError(event);
        }
    }
    
    /**
     * 재연결 스케줄링 (지수 백오프)
     */
    scheduleReconnect() {
        if (this.reconnectConfig.attempts >= this.reconnectConfig.maxAttempts) {
            console.error('❌ Maximum reconnect attempts reached');
            this.emit('maxReconnectAttemptsReached');
            return;
        }
        
        this.connectionState.status = 'reconnecting';
        this.emit('connectionStateChanged', 'reconnecting');
        
        // 지수 백오프 계산
        const delay = this.calculateReconnectDelay();
        
        console.log(`🔄 Reconnecting in ${delay}ms (attempt ${this.reconnectConfig.attempts + 1})`);
        
        setTimeout(() => {
            this.reconnectConfig.attempts++;
            this.metrics.reconnectCount++;
            
            this.emit('reconnectAttempt', {
                attempt: this.reconnectConfig.attempts,
                delay: delay
            });
            
            this.connect();
        }, delay);
    }
    
    /**
     * 재연결 지연 시간 계산 (지수 백오프 + 지터)
     */
    calculateReconnectDelay() {
        let delay = this.reconnectConfig.baseDelay * 
                   Math.pow(this.reconnectConfig.backoffFactor, this.reconnectConfig.attempts);
        
        // 최대 지연 시간 제한
        delay = Math.min(delay, this.reconnectConfig.maxDelay);
        
        // 지터 추가 (랜덤성)
        if (this.reconnectConfig.jitter) {
            const jitterAmount = delay * 0.1; // 10% 지터
            delay += (Math.random() - 0.5) * 2 * jitterAmount;
        }
        
        return Math.max(0, Math.floor(delay));
    }
    
    /**
     * 하트비트 시작
     */
    startHeartbeat() {
        if (!this.heartbeat.enabled) return;
        
        this.stopHeartbeat(); // 기존 하트비트 중지
        
        this.heartbeat.intervalId = setInterval(() => {
            this.sendHeartbeat();
        }, this.heartbeat.interval);
    }
    
    /**
     * 하트비트 전송
     */
    sendHeartbeat() {
        if (this.connectionState.status !== 'connected') return;
        
        const heartbeatMessage = {
            type: 'ping',
            timestamp: Date.now()
        };
        
        this.send(heartbeatMessage, false); // 큐에 저장하지 않음
        
        // 응답 타임아웃 설정
        this.heartbeat.timeoutId = setTimeout(() => {
            this.handleHeartbeatTimeout();
        }, this.heartbeat.timeout);
    }
    
    /**
     * 하트비트 응답 처리
     */
    handleHeartbeatResponse(data) {
        if (this.heartbeat.timeoutId) {
            clearTimeout(this.heartbeat.timeoutId);
            this.heartbeat.timeoutId = null;
        }
        
        this.heartbeat.lastPong = Date.now();
        this.heartbeat.missedPongs = 0;
        
        // 지연 시간 계산
        if (data.timestamp) {
            const latency = Date.now() - data.timestamp;
            this.connectionQuality.latency = latency;
        }
    }
    
    /**
     * 하트비트 타임아웃 처리
     */
    handleHeartbeatTimeout() {
        this.heartbeat.missedPongs++;
        
        console.warn(`⚠️ Heartbeat missed (${this.heartbeat.missedPongs}/${this.heartbeat.maxMissedPongs})`);
        
        if (this.heartbeat.missedPongs >= this.heartbeat.maxMissedPongs) {
            console.error('💔 Too many missed heartbeats, closing connection');
            this.ws.close(1000, 'Heartbeat timeout');
        }
    }
    
    /**
     * 하트비트 중지
     */
    stopHeartbeat() {
        if (this.heartbeat.intervalId) {
            clearInterval(this.heartbeat.intervalId);
            this.heartbeat.intervalId = null;
        }
        
        if (this.heartbeat.timeoutId) {
            clearTimeout(this.heartbeat.timeoutId);
            this.heartbeat.timeoutId = null;
        }
        
        this.heartbeat.missedPongs = 0;
    }
    
    /**
     * 메시지 전송
     */
    send(message, queueIfDisconnected = true) {
        if (this.connectionState.status === 'connected') {
            return this.sendImmediate(message);
        } else if (queueIfDisconnected) {
            return this.queueMessage(message);
        } else {
            throw new Error('WebSocket not connected');
        }
    }
    
    /**
     * 즉시 메시지 전송
     */
    sendImmediate(message) {
        try {
            // 메시지 ID 추가
            if (!message.id) {
                message.id = this.generateMessageId();
            }
            
            // 시퀀스 번호 추가 (순서 보장용)
            if (!message.sequence) {
                message.sequence = ++this.sequenceNumber;
            }
            
            const messageString = JSON.stringify(message);
            this.ws.send(messageString);
            
            // 메트릭 업데이트
            this.metrics.messagesSent++;
            this.metrics.bytesSent += messageString.length;
            
            this.emit('messageSent', message);
            
            return message.id;
            
        } catch (error) {
            this.metrics.errorCount++;
            this.emit('sendError', { error, message });
            throw error;
        }
    }
    
    /**
     * 메시지 큐에 추가
     */
    queueMessage(message) {
        if (this.messageQueue.length >= this.maxQueueSize) {
            // 가장 오래된 메시지 제거
            this.messageQueue.shift();
            console.warn('⚠️ Message queue overflow, removing oldest message');
        }
        
        const queuedMessage = {
            ...message,
            id: message.id || this.generateMessageId(),
            queuedAt: Date.now()
        };
        
        this.messageQueue.push(queuedMessage);
        this.emit('messageQueued', queuedMessage);
        
        return queuedMessage.id;
    }
    
    /**
     * 큐된 메시지 모두 전송
     */
    flushMessageQueue() {
        if (this.messageQueue.length === 0) return;
        
        console.log(`📤 Flushing ${this.messageQueue.length} queued messages`);
        
        const messages = [...this.messageQueue];
        this.messageQueue = [];
        
        messages.forEach(message => {
            try {
                this.sendImmediate(message);
            } catch (error) {
                console.error('Failed to send queued message:', error);
                // 실패한 메시지는 다시 큐에 추가하지 않음
            }
        });
    }
    
    /**
     * 응답 대기 메시지 전송
     */
    sendAndWaitForResponse(message, timeout = 30000) {
        const messageId = this.send(message);
        
        return new Promise((resolve, reject) => {
            const timeoutId = setTimeout(() => {
                this.pendingMessages.delete(messageId);
                reject(new Error('Response timeout'));
            }, timeout);
            
            this.pendingMessages.set(messageId, {
                resolve,
                reject,
                timeout: timeoutId,
                sentAt: Date.now()
            });
        });
    }
    
    /**
     * 구독 관리
     */
    subscribe(subscription) {
        const subId = subscription.id || this.generateSubscriptionId();
        this.subscriptions.set(subId, {
            ...subscription,
            id: subId,
            subscribedAt: Date.now()
        });
        
        const message = {
            op: 'subscribe',
            args: subscription.args || subscription
        };
        
        this.send(message);
        this.emit('subscribed', subId);
        
        return subId;
    }
    
    /**
     * 구독 해제
     */
    unsubscribe(subscriptionId) {
        const subscription = this.subscriptions.get(subscriptionId);
        if (!subscription) return;
        
        const message = {
            op: 'unsubscribe',
            args: subscription.args || subscription
        };
        
        this.send(message);
        this.subscriptions.delete(subscriptionId);
        this.emit('unsubscribed', subscriptionId);
    }
    
    /**
     * 모든 구독 복구
     */
    resubscribeAll() {
        console.log(`🔄 Resubscribing ${this.subscriptions.size} subscriptions`);
        
        for (const [id, subscription] of this.subscriptions) {
            const message = {
                op: 'subscribe',
                args: subscription.args || subscription
            };
            
            this.send(message);
        }
        
        this.emit('resubscribedAll');
    }
    
    /**
     * 연결 모니터링 설정
     */
    setupConnectionMonitoring() {
        setInterval(() => {
            this.updateConnectionMetrics();
            this.checkConnectionHealth();
        }, 5000); // 5초마다
    }
    
    /**
     * 연결 상태 확인
     */
    checkConnectionHealth() {
        if (this.connectionState.status === 'connected') {
            // 최근 메시지 수신 확인
            const timeSinceLastMessage = Date.now() - (this.heartbeat.lastPong || this.connectionState.lastConnected);
            
            if (timeSinceLastMessage > this.heartbeat.interval * 2) {
                console.warn('⚠️ No recent activity detected, connection may be stale');
                this.connectionQuality.score = Math.max(0, this.connectionQuality.score - 10);
            }
        }
    }
    
    /**
     * 연결 품질 업데이트
     */
    updateConnectionQuality() {
        if (this.connectionState.status === 'connected') {
            // 지연시간 기반 점수
            const latencyScore = Math.max(0, 100 - (this.connectionQuality.latency / 10));
            
            // 안정성 점수 (재연결 횟수 기반)
            const stabilityPenalty = this.metrics.reconnectCount * 5;
            const stabilityScore = Math.max(0, 100 - stabilityPenalty);
            
            // 전체 점수 계산
            this.connectionQuality.score = Math.round((latencyScore + stabilityScore) / 2);
            this.connectionQuality.stability = stabilityScore;
        }
        
        this.emit('connectionQualityUpdated', this.connectionQuality);
    }
    
    /**
     * 메트릭 수집 시작
     */
    startMetricsCollection() {
        setInterval(() => {
            this.updateUptimeMetrics();
            this.emit('metricsUpdated', this.getMetrics());
        }, 60000); // 1분마다
    }
    
    /**
     * 업타임 메트릭 업데이트
     */
    updateUptimeMetrics() {
        if (this.connectionState.status === 'connected') {
            const now = Date.now();
            this.metrics.uptime += now - this.metrics.lastUptimeCheck;
            this.metrics.lastUptimeCheck = now;
        }
    }
    
    /**
     * 지연시간 메트릭 업데이트
     */
    updateLatencyMetrics(latency) {
        this.metrics.latencyHistory.push(latency);
        
        // 최근 100개 기록만 유지
        if (this.metrics.latencyHistory.length > 100) {
            this.metrics.latencyHistory.shift();
        }
        
        // 평균 지연시간 계산
        const sum = this.metrics.latencyHistory.reduce((a, b) => a + b, 0);
        this.metrics.averageLatency = sum / this.metrics.latencyHistory.length;
    }
    
    /**
     * 유틸리티 함수들
     */
    generateMessageId() {
        return `msg_${++this.messageId}_${Date.now()}`;
    }
    
    generateSubscriptionId() {
        return `sub_${Date.now()}_${Math.random().toString(36).substr(2, 9)}`;
    }
    
    isHeartbeatResponse(data) {
        return data.type === 'pong' || data.pong !== undefined;
    }
    
    isIntentionalClose(code) {
        return code === 1000 || code === 1001;
    }
    
    isValidSequence(sequence) {
        return sequence === this.expectedSequence;
    }
    
    bufferOutOfOrderMessage(data) {
        this.outOfOrderBuffer.set(data.sequence, data);
        
        // 버퍼 크기 제한
        if (this.outOfOrderBuffer.size > 100) {
            const oldestSequence = Math.min(...this.outOfOrderBuffer.keys());
            this.outOfOrderBuffer.delete(oldestSequence);
        }
    }
    
    timeoutPendingMessages() {
        for (const [id, pending] of this.pendingMessages) {
            clearTimeout(pending.timeout);
            if (pending.reject) {
                pending.reject(new Error('Connection closed'));
            }
        }
        this.pendingMessages.clear();
    }
    
    /**
     * 외부 API
     */
    
    // 연결 상태 조회
    getConnectionState() {
        return {
            ...this.connectionState,
            isConnected: this.connectionState.status === 'connected',
            quality: this.connectionQuality
        };
    }
    
    // 메트릭 조회
    getMetrics() {
        return {
            ...this.metrics,
            connectionState: this.connectionState,
            quality: this.connectionQuality,
            subscriptions: this.subscriptions.size,
            queueSize: this.messageQueue.length
        };
    }
    
    // 이벤트 핸들러 설정
    on(event, handler) {
        if (this.eventHandlers.hasOwnProperty(`on${event.charAt(0).toUpperCase()}${event.slice(1)}`)) {
            this.eventHandlers[`on${event.charAt(0).toUpperCase()}${event.slice(1)}`] = handler;
        }
        super.on(event, handler);
    }
    
    // 강제 재연결
    forceReconnect() {
        if (this.ws) {
            this.ws.close(1000, 'Force reconnect');
        }
        
        setTimeout(() => {
            this.connect();
        }, 100);
    }
    
    // 연결 종료
    disconnect() {
        this.reconnectConfig.enabled = false;
        
        if (this.ws) {
            this.ws.close(1000, 'Manual disconnect');
        }
        
        this.stopHeartbeat();
    }
    
    // 메트릭 리셋
    resetMetrics() {
        this.metrics = {
            messagesReceived: 0,
            messagesSent: 0,
            bytesReceived: 0,
            bytesSent: 0,
            averageLatency: 0,
            latencyHistory: [],
            errorCount: 0,
            reconnectCount: 0,
            uptime: 0,
            lastUptimeCheck: Date.now()
        };
    }
    
    /**
     * 정리
     */
    destroy() {
        this.disconnect();
        this.subscriptions.clear();
        this.messageQueue = [];
        this.pendingMessages.clear();
        
        super.destroy();
    }
}

export default EnhancedWebSocketService;
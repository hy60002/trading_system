/**
 * @fileoverview 메시지 순서 보장 및 중복 처리 시스템
 * @description 실시간 데이터의 순서와 무결성을 보장하는 메시지 큐 관리자
 */

import { eventBus } from '../core/EventBus.js';

/**
 * 메시지 큐 관리자
 * @class MessageQueue
 */
export class MessageQueue {
    constructor() {
        this.queues = new Map(); // 카테고리별 큐
        this.sequenceNumbers = new Map(); // 카테고리별 시퀀스 번호
        this.messageHistory = new Map(); // 중복 방지를 위한 메시지 히스토리
        this.processingIntervals = new Map(); // 처리 인터벌
        this.statistics = new Map(); // 통계 정보
        
        // 설정
        this.config = {
            maxQueueSize: 1000,
            maxHistorySize: 5000,
            processingInterval: 50, // 50ms마다 처리
            timeoutMs: 30000, // 30초 타임아웃
            maxRetries: 3,
            duplicateWindowMs: 5000, // 5초 중복 검사 윈도우
            orderingWindowMs: 10000 // 10초 순서 보장 윈도우
        };
        
        // 메시지 우선순위
        this.priorities = {
            'critical': 1,
            'high': 2,
            'normal': 3,
            'low': 4
        };
        
        this.setupEventListeners();
        this.startPeriodicCleanup();
    }

    /**
     * 이벤트 리스너 설정
     * @private
     */
    setupEventListeners() {
        eventBus.on('websocket:message', (data) => {
            this.enqueue(data);
        });

        eventBus.on('app:pause', () => {
            this.pauseProcessing();
        });

        eventBus.on('app:resume', () => {
            this.resumeProcessing();
        });
    }

    /**
     * 메시지를 큐에 추가
     * @param {Object} message - 메시지 객체
     * @param {Object} options - 옵션
     */
    enqueue(message, options = {}) {
        try {
            const processedMessage = this.preprocessMessage(message, options);
            
            // 중복 검사
            if (this.isDuplicate(processedMessage)) {
                this.updateStats(processedMessage.category, 'duplicates');
                console.warn('🔄 중복 메시지 무시:', processedMessage.id);
                return false;
            }

            // 큐 크기 확인
            const queue = this.getOrCreateQueue(processedMessage.category);
            if (queue.messages.length >= this.config.maxQueueSize) {
                this.handleQueueOverflow(processedMessage.category);
            }

            // 메시지 추가
            this.insertMessageInOrder(queue, processedMessage);
            
            // 히스토리에 추가
            this.addToHistory(processedMessage);
            
            // 통계 업데이트
            this.updateStats(processedMessage.category, 'received');
            
            // 처리 시작 (아직 시작되지 않은 경우)
            this.startProcessing(processedMessage.category);
            
            eventBus.emit('messageQueue:enqueued', {
                category: processedMessage.category,
                messageId: processedMessage.id,
                queueSize: queue.messages.length
            });

            return true;

        } catch (error) {
            console.error('❌ 메시지 큐 추가 실패:', error);
            eventBus.emit('messageQueue:error', { error, message });
            return false;
        }
    }

    /**
     * 메시지 전처리
     * @param {Object} message - 원본 메시지
     * @param {Object} options - 옵션
     * @returns {Object} 처리된 메시지
     * @private
     */
    preprocessMessage(message, options) {
        const now = Date.now();
        
        return {
            id: message.id || this.generateMessageId(),
            category: options.category || message.type || 'default',
            data: message.data || message,
            timestamp: message.timestamp || now,
            receivedAt: now,
            sequenceNumber: message.sequenceNumber || null,
            priority: options.priority || message.priority || 'normal',
            retries: 0,
            processed: false,
            timeout: now + this.config.timeoutMs,
            checksum: this.calculateChecksum(message.data || message)
        };
    }

    /**
     * 큐 가져오기 또는 생성
     * @param {string} category - 카테고리
     * @returns {Object} 큐 객체
     * @private
     */
    getOrCreateQueue(category) {
        if (!this.queues.has(category)) {
            this.queues.set(category, {
                messages: [],
                processing: false,
                lastProcessed: 0,
                expectedSequence: 1
            });
            
            this.statistics.set(category, {
                received: 0,
                processed: 0,
                failed: 0,
                duplicates: 0,
                outOfOrder: 0,
                averageProcessingTime: 0
            });
        }
        
        return this.queues.get(category);
    }

    /**
     * 메시지를 순서대로 삽입
     * @param {Object} queue - 큐 객체
     * @param {Object} message - 메시지
     * @private
     */
    insertMessageInOrder(queue, message) {
        const messages = queue.messages;
        
        // 시퀀스 번호가 있는 경우 순서 보장
        if (message.sequenceNumber !== null) {
            let insertIndex = messages.length;
            
            // 올바른 위치 찾기
            for (let i = messages.length - 1; i >= 0; i--) {
                if (messages[i].sequenceNumber !== null && 
                    messages[i].sequenceNumber <= message.sequenceNumber) {
                    insertIndex = i + 1;
                    break;
                }
            }
            
            messages.splice(insertIndex, 0, message);
            
            // 순서가 맞지 않는 경우 통계 업데이트
            if (message.sequenceNumber < queue.expectedSequence) {
                this.updateStats(message.category, 'outOfOrder');
            }
        } else {
            // 시퀀스 번호가 없는 경우 우선순위와 타임스탬프 기준 정렬
            const priority = this.priorities[message.priority] || this.priorities.normal;
            let insertIndex = messages.length;
            
            for (let i = messages.length - 1; i >= 0; i--) {
                const msgPriority = this.priorities[messages[i].priority] || this.priorities.normal;
                
                if (msgPriority < priority || 
                    (msgPriority === priority && messages[i].timestamp <= message.timestamp)) {
                    insertIndex = i + 1;
                    break;
                }
            }
            
            messages.splice(insertIndex, 0, message);
        }
    }

    /**
     * 중복 메시지 확인
     * @param {Object} message - 메시지
     * @returns {boolean} 중복 여부
     * @private
     */
    isDuplicate(message) {
        const historyKey = `${message.category}:${message.id}`;
        const history = this.messageHistory.get(historyKey);
        
        if (!history) {
            return false;
        }
        
        // 시간 윈도우 내의 중복 확인
        const now = Date.now();
        return history.some(entry => 
            now - entry.timestamp < this.config.duplicateWindowMs &&
            entry.checksum === message.checksum
        );
    }

    /**
     * 히스토리에 메시지 추가
     * @param {Object} message - 메시지
     * @private
     */
    addToHistory(message) {
        const historyKey = `${message.category}:${message.id}`;
        
        if (!this.messageHistory.has(historyKey)) {
            this.messageHistory.set(historyKey, []);
        }
        
        const history = this.messageHistory.get(historyKey);
        history.push({
            timestamp: message.receivedAt,
            checksum: message.checksum
        });
        
        // 히스토리 크기 제한
        if (history.length > 10) {
            history.shift();
        }
    }

    /**
     * 메시지 처리 시작
     * @param {string} category - 카테고리
     * @private
     */
    startProcessing(category) {
        const queue = this.getOrCreateQueue(category);
        
        if (queue.processing || this.processingIntervals.has(category)) {
            return;
        }
        
        queue.processing = true;
        
        const interval = setInterval(() => {
            this.processQueue(category);
        }, this.config.processingInterval);
        
        this.processingIntervals.set(category, interval);
        
        console.log(`🚀 메시지 처리 시작: ${category}`);
    }

    /**
     * 큐 처리
     * @param {string} category - 카테고리
     * @private
     */
    async processQueue(category) {
        const queue = this.getOrCreateQueue(category);
        
        if (queue.messages.length === 0) {
            return;
        }

        const now = Date.now();
        let processedCount = 0;
        const maxBatchSize = 10; // 배치당 최대 처리 개수
        
        // 처리 가능한 메시지 찾기
        const messagesToProcess = [];
        
        for (let i = 0; i < queue.messages.length && messagesToProcess.length < maxBatchSize; i++) {
            const message = queue.messages[i];
            
            // 타임아웃된 메시지 처리
            if (now > message.timeout) {
                this.handleTimeoutMessage(message, i);
                continue;
            }
            
            // 순서 보장 확인
            if (this.canProcessMessage(message, queue)) {
                messagesToProcess.push({ message, index: i });
            } else {
                // 순서가 맞지 않으면 대기
                break;
            }
        }
        
        // 메시지 처리
        for (const { message, index } of messagesToProcess.reverse()) {
            try {
                const startTime = Date.now();
                await this.processMessage(message);
                const processingTime = Date.now() - startTime;
                
                // 큐에서 제거
                queue.messages.splice(index, 1);
                
                // 통계 업데이트
                this.updateStats(category, 'processed');
                this.updateProcessingTime(category, processingTime);
                
                // 시퀀스 번호 업데이트
                if (message.sequenceNumber !== null) {
                    queue.expectedSequence = Math.max(queue.expectedSequence, message.sequenceNumber + 1);
                }
                
                queue.lastProcessed = Date.now();
                processedCount++;
                
                eventBus.emit('messageQueue:processed', {
                    category,
                    messageId: message.id,
                    processingTime,
                    queueSize: queue.messages.length
                });
                
            } catch (error) {
                await this.handleProcessingError(message, error);
            }
        }
        
        // 큐가 비어있으면 처리 중단
        if (queue.messages.length === 0) {
            this.stopProcessing(category);
        }
    }

    /**
     * 메시지 처리 가능 여부 확인
     * @param {Object} message - 메시지
     * @param {Object} queue - 큐
     * @returns {boolean} 처리 가능 여부
     * @private
     */
    canProcessMessage(message, queue) {
        // 시퀀스 번호가 있는 경우
        if (message.sequenceNumber !== null) {
            // 예상 시퀀스와 일치하거나 순서 보장 윈도우를 벗어난 경우
            const now = Date.now();
            const isWithinWindow = now - message.receivedAt < this.config.orderingWindowMs;
            
            return message.sequenceNumber === queue.expectedSequence || !isWithinWindow;
        }
        
        // 시퀀스 번호가 없는 경우 항상 처리 가능
        return true;
    }

    /**
     * 메시지 처리
     * @param {Object} message - 메시지
     * @private
     */
    async processMessage(message) {
        try {
            // 카테고리별 처리 로직 호출
            await this.dispatchMessage(message);
            
            message.processed = true;
            message.processedAt = Date.now();
            
        } catch (error) {
            throw new Error(`메시지 처리 실패: ${error.message}`);
        }
    }

    /**
     * 메시지 디스패치
     * @param {Object} message - 메시지
     * @private
     */
    async dispatchMessage(message) {
        const eventName = `message:${message.category}`;
        
        // 이벤트 버스를 통한 디스패치
        eventBus.emit(eventName, {
            id: message.id,
            data: message.data,
            timestamp: message.timestamp,
            sequenceNumber: message.sequenceNumber
        });
        
        // 전역 메시지 이벤트도 발생
        eventBus.emit('message:processed', {
            category: message.category,
            id: message.id,
            data: message.data
        });
    }

    /**
     * 처리 오류 처리
     * @param {Object} message - 메시지
     * @param {Error} error - 오류
     * @private
     */
    async handleProcessingError(message, error) {
        message.retries++;
        message.lastError = error.message;
        
        console.error(`❌ 메시지 처리 오류 (${message.id}):`, error);
        
        if (message.retries >= this.config.maxRetries) {
            // 최대 재시도 횟수 초과
            this.handleFailedMessage(message);
        } else {
            // 재시도를 위해 메시지를 큐 뒤로 이동
            const queue = this.getOrCreateQueue(message.category);
            const index = queue.messages.indexOf(message);
            
            if (index !== -1) {
                queue.messages.splice(index, 1);
                queue.messages.push(message);
            }
        }
        
        this.updateStats(message.category, 'failed');
        
        eventBus.emit('messageQueue:error', {
            messageId: message.id,
            category: message.category,
            error: error.message,
            retries: message.retries
        });
    }

    /**
     * 실패한 메시지 처리
     * @param {Object} message - 메시지
     * @private
     */
    handleFailedMessage(message) {
        console.error(`❌ 메시지 처리 포기 (${message.id}): 최대 재시도 횟수 초과`);
        
        // 실패 메시지 저장 (디버깅용)
        const failedMessages = JSON.parse(localStorage.getItem('failed_messages') || '[]');
        failedMessages.push({
            ...message,
            failedAt: Date.now()
        });
        
        // 최근 100개만 보관
        localStorage.setItem('failed_messages', 
            JSON.stringify(failedMessages.slice(-100))
        );
        
        eventBus.emit('messageQueue:failed', {
            messageId: message.id,
            category: message.category,
            finalError: message.lastError
        });
    }

    /**
     * 타임아웃된 메시지 처리
     * @param {Object} message - 메시지
     * @param {number} index - 인덱스
     * @private
     */
    handleTimeoutMessage(message, index) {
        const queue = this.getOrCreateQueue(message.category);
        queue.messages.splice(index, 1);
        
        console.warn(`⏰ 메시지 타임아웃 (${message.id})`);
        
        eventBus.emit('messageQueue:timeout', {
            messageId: message.id,
            category: message.category,
            age: Date.now() - message.receivedAt
        });
    }

    /**
     * 큐 오버플로우 처리
     * @param {string} category - 카테고리
     * @private
     */
    handleQueueOverflow(category) {
        const queue = this.getOrCreateQueue(category);
        
        // 오래된 메시지부터 제거 (우선순위 낮은 것 우선)
        const messagesToRemove = Math.floor(this.config.maxQueueSize * 0.1); // 10% 제거
        
        queue.messages
            .sort((a, b) => {
                const priorityDiff = this.priorities[b.priority] - this.priorities[a.priority];
                return priorityDiff !== 0 ? priorityDiff : a.receivedAt - b.receivedAt;
            })
            .splice(0, messagesToRemove);
        
        console.warn(`⚠️ 큐 오버플로우 - ${messagesToRemove}개 메시지 제거: ${category}`);
        
        eventBus.emit('messageQueue:overflow', {
            category,
            removedCount: messagesToRemove,
            queueSize: queue.messages.length
        });
    }

    /**
     * 처리 중단
     * @param {string} category - 카테고리
     * @private
     */
    stopProcessing(category) {
        const interval = this.processingIntervals.get(category);
        if (interval) {
            clearInterval(interval);
            this.processingIntervals.delete(category);
        }
        
        const queue = this.getOrCreateQueue(category);
        queue.processing = false;
        
        console.log(`⏸️ 메시지 처리 중단: ${category}`);
    }

    /**
     * 모든 처리 일시중지
     */
    pauseProcessing() {
        for (const category of this.processingIntervals.keys()) {
            this.stopProcessing(category);
        }
        
        eventBus.emit('messageQueue:paused');
    }

    /**
     * 처리 재개
     */
    resumeProcessing() {
        for (const [category, queue] of this.queues.entries()) {
            if (queue.messages.length > 0 && !queue.processing) {
                this.startProcessing(category);
            }
        }
        
        eventBus.emit('messageQueue:resumed');
    }

    /**
     * 통계 업데이트
     * @param {string} category - 카테고리
     * @param {string} type - 통계 타입
     * @private
     */
    updateStats(category, type) {
        const stats = this.statistics.get(category);
        if (stats) {
            stats[type]++;
        }
    }

    /**
     * 평균 처리 시간 업데이트
     * @param {string} category - 카테고리
     * @param {number} processingTime - 처리 시간
     * @private
     */
    updateProcessingTime(category, processingTime) {
        const stats = this.statistics.get(category);
        if (stats) {
            // 이동 평균 계산
            const alpha = 0.1; // 평활화 계수
            stats.averageProcessingTime = stats.averageProcessingTime * (1 - alpha) + processingTime * alpha;
        }
    }

    /**
     * 체크섬 계산
     * @param {*} data - 데이터
     * @returns {string} 체크섬
     * @private
     */
    calculateChecksum(data) {
        const str = JSON.stringify(data);
        let hash = 0;
        
        for (let i = 0; i < str.length; i++) {
            const char = str.charCodeAt(i);
            hash = ((hash << 5) - hash) + char;
            hash = hash & hash;
        }
        
        return hash.toString(36);
    }

    /**
     * 메시지 ID 생성
     * @returns {string} 고유 ID
     * @private
     */
    generateMessageId() {
        return `msg_${Date.now()}_${Math.random().toString(36).substr(2, 9)}`;
    }

    /**
     * 주기적 정리 시작
     * @private
     */
    startPeriodicCleanup() {
        // 5분마다 히스토리 정리
        setInterval(() => {
            this.cleanupHistory();
        }, 300000);
        
        // 1분마다 만료된 메시지 정리
        setInterval(() => {
            this.cleanupExpiredMessages();
        }, 60000);
    }

    /**
     * 히스토리 정리
     * @private
     */
    cleanupHistory() {
        const now = Date.now();
        let cleanedEntries = 0;
        
        for (const [key, history] of this.messageHistory.entries()) {
            const validEntries = history.filter(entry => 
                now - entry.timestamp < this.config.duplicateWindowMs * 2
            );
            
            if (validEntries.length !== history.length) {
                this.messageHistory.set(key, validEntries);
                cleanedEntries += history.length - validEntries.length;
            }
            
            // 빈 히스토리 제거
            if (validEntries.length === 0) {
                this.messageHistory.delete(key);
            }
        }
        
        // 전체 히스토리 크기 제한
        if (this.messageHistory.size > this.config.maxHistorySize) {
            const keysToRemove = Array.from(this.messageHistory.keys())
                .slice(0, this.messageHistory.size - this.config.maxHistorySize);
            
            keysToRemove.forEach(key => this.messageHistory.delete(key));
            cleanedEntries += keysToRemove.length;
        }
        
        if (cleanedEntries > 0) {
            console.log(`🧹 메시지 히스토리 정리: ${cleanedEntries}개 항목 제거`);
        }
    }

    /**
     * 만료된 메시지 정리
     * @private
     */
    cleanupExpiredMessages() {
        const now = Date.now();
        let removedCount = 0;
        
        for (const [category, queue] of this.queues.entries()) {
            const validMessages = queue.messages.filter(message => now <= message.timeout);
            const removed = queue.messages.length - validMessages.length;
            
            if (removed > 0) {
                queue.messages = validMessages;
                removedCount += removed;
                
                eventBus.emit('messageQueue:expired_cleanup', {
                    category,
                    removedCount: removed
                });
            }
        }
        
        if (removedCount > 0) {
            console.log(`🗑️ 만료된 메시지 정리: ${removedCount}개 제거`);
        }
    }

    /**
     * 큐 상태 조회
     * @param {string} category - 카테고리 (선택사항)
     * @returns {Object} 큐 상태
     */
    getQueueStatus(category = null) {
        if (category) {
            const queue = this.queues.get(category);
            const stats = this.statistics.get(category);
            
            return queue && stats ? {
                category,
                queueSize: queue.messages.length,
                processing: queue.processing,
                lastProcessed: queue.lastProcessed,
                expectedSequence: queue.expectedSequence,
                statistics: { ...stats }
            } : null;
        }
        
        // 전체 상태
        const status = {
            totalQueues: this.queues.size,
            totalMessages: 0,
            totalHistoryEntries: this.messageHistory.size,
            categories: {}
        };
        
        for (const [cat, queue] of this.queues.entries()) {
            const stats = this.statistics.get(cat);
            status.totalMessages += queue.messages.length;
            status.categories[cat] = {
                queueSize: queue.messages.length,
                processing: queue.processing,
                statistics: stats ? { ...stats } : {}
            };
        }
        
        return status;
    }

    /**
     * 큐 초기화
     * @param {string} category - 카테고리 (선택사항)
     */
    clearQueue(category = null) {
        if (category) {
            this.stopProcessing(category);
            this.queues.delete(category);
            this.statistics.delete(category);
            
            // 해당 카테고리의 히스토리도 정리
            for (const key of this.messageHistory.keys()) {
                if (key.startsWith(`${category}:`)) {
                    this.messageHistory.delete(key);
                }
            }
            
            console.log(`🗑️ 큐 초기화: ${category}`);
        } else {
            // 모든 큐 초기화
            this.pauseProcessing();
            this.queues.clear();
            this.statistics.clear();
            this.messageHistory.clear();
            
            console.log('🗑️ 모든 큐 초기화');
        }
        
        eventBus.emit('messageQueue:cleared', { category });
    }

    /**
     * 설정 업데이트
     * @param {Object} newConfig - 새로운 설정
     */
    updateConfig(newConfig) {
        this.config = { ...this.config, ...newConfig };
        console.log('⚙️ 메시지 큐 설정 업데이트:', newConfig);
    }

    /**
     * 강제로 메시지 처리
     * @param {string} category - 카테고리
     * @param {string} messageId - 메시지 ID (선택사항)
     */
    forceProcess(category, messageId = null) {
        const queue = this.getOrCreateQueue(category);
        
        if (messageId) {
            // 특정 메시지만 강제 처리
            const messageIndex = queue.messages.findIndex(msg => msg.id === messageId);
            if (messageIndex !== -1) {
                const message = queue.messages[messageIndex];
                this.processMessage(message).then(() => {
                    queue.messages.splice(messageIndex, 1);
                });
            }
        } else {
            // 전체 큐 강제 처리
            this.processQueue(category);
        }
    }
}

// 전역 메시지 큐 인스턴스
export const messageQueue = new MessageQueue();

// 개발 모드에서 전역 접근 가능하게 설정
if (typeof window !== 'undefined' && process.env.NODE_ENV === 'development') {
    window.__MESSAGE_QUEUE__ = messageQueue;
}
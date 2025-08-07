/**
 * @fileoverview 이벤트 버스 시스템
 * @description 컴포넌트 간 느슨한 결합을 위한 이벤트 시스템
 */

/**
 * 이벤트 버스 클래스
 * @class EventBus
 */
export class EventBus {
    constructor() {
        this.events = new Map();
        this.onceEvents = new Map();
        this.maxListeners = 100;
        this.debugMode = process.env.NODE_ENV === 'development';
        
        // 이벤트 통계 (개발 모드)
        this.stats = this.debugMode ? {
            totalEmitted: 0,
            eventCounts: new Map(),
            errorCounts: new Map()
        } : null;
    }

    /**
     * 이벤트 리스너 등록
     * @param {string} eventName - 이벤트 이름
     * @param {Function} listener - 리스너 함수
     * @param {Object} options - 옵션
     * @returns {Function} 리스너 제거 함수
     */
    on(eventName, listener, options = {}) {
        this.validateEventName(eventName);
        this.validateListener(listener);

        if (!this.events.has(eventName)) {
            this.events.set(eventName, []);
        }

        const listeners = this.events.get(eventName);
        
        // 최대 리스너 수 확인
        if (listeners.length >= this.maxListeners) {
            console.warn(`EventBus: Maximum listeners (${this.maxListeners}) exceeded for event "${eventName}"`);
        }

        const wrappedListener = {
            original: listener,
            handler: listener,
            priority: options.priority || 0,
            namespace: options.namespace || null,
            once: false,
            id: Symbol()
        };

        // 우선순위에 따라 삽입
        const insertIndex = listeners.findIndex(l => l.priority < wrappedListener.priority);
        if (insertIndex === -1) {
            listeners.push(wrappedListener);
        } else {
            listeners.splice(insertIndex, 0, wrappedListener);
        }

        this.debugLog(`Listener added for "${eventName}"`, { listenersCount: listeners.length });

        // 리스너 제거 함수 반환
        return () => this.off(eventName, listener);
    }

    /**
     * 일회성 이벤트 리스너 등록
     * @param {string} eventName - 이벤트 이름
     * @param {Function} listener - 리스너 함수
     * @param {Object} options - 옵션
     * @returns {Function} 리스너 제거 함수
     */
    once(eventName, listener, options = {}) {
        return new Promise((resolve) => {
            const onceListener = (...args) => {
                listener(...args);
                resolve(...args);
            };

            if (!this.onceEvents.has(eventName)) {
                this.onceEvents.set(eventName, []);
            }

            const onceListeners = this.onceEvents.get(eventName);
            onceListeners.push({
                original: listener,
                handler: onceListener,
                priority: options.priority || 0,
                namespace: options.namespace || null,
                id: Symbol()
            });

            // 일반 리스너로도 등록 (한 번 실행 후 자동 제거)
            const removeListener = this.on(eventName, (...args) => {
                onceListener(...args);
                removeListener();
            }, options);

            return removeListener;
        });
    }

    /**
     * 이벤트 리스너 제거
     * @param {string} eventName - 이벤트 이름
     * @param {Function} listener - 제거할 리스너 함수
     */
    off(eventName, listener) {
        if (!eventName) {
            // 모든 이벤트 리스너 제거
            this.events.clear();
            this.onceEvents.clear();
            return;
        }

        if (this.events.has(eventName)) {
            const listeners = this.events.get(eventName);
            const index = listeners.findIndex(l => l.original === listener);
            
            if (index !== -1) {
                listeners.splice(index, 1);
                this.debugLog(`Listener removed from "${eventName}"`, { listenersCount: listeners.length });
                
                if (listeners.length === 0) {
                    this.events.delete(eventName);
                }
            }
        }

        // once 이벤트에서도 제거
        if (this.onceEvents.has(eventName)) {
            const onceListeners = this.onceEvents.get(eventName);
            const index = onceListeners.findIndex(l => l.original === listener);
            
            if (index !== -1) {
                onceListeners.splice(index, 1);
                
                if (onceListeners.length === 0) {
                    this.onceEvents.delete(eventName);
                }
            }
        }
    }

    /**
     * 네임스페이스별 리스너 제거
     * @param {string} namespace - 네임스페이스
     */
    offNamespace(namespace) {
        for (const [eventName, listeners] of this.events.entries()) {
            const filteredListeners = listeners.filter(l => l.namespace !== namespace);
            
            if (filteredListeners.length === 0) {
                this.events.delete(eventName);
            } else {
                this.events.set(eventName, filteredListeners);
            }
        }

        for (const [eventName, listeners] of this.onceEvents.entries()) {
            const filteredListeners = listeners.filter(l => l.namespace !== namespace);
            
            if (filteredListeners.length === 0) {
                this.onceEvents.delete(eventName);
            } else {
                this.onceEvents.set(eventName, filteredListeners);
            }
        }

        this.debugLog(`All listeners removed for namespace "${namespace}"`);
    }

    /**
     * 이벤트 발생
     * @param {string} eventName - 이벤트 이름
     * @param {...any} args - 이벤트 인자
     * @returns {Promise<Array>} 리스너 실행 결과 배열
     */
    async emit(eventName, ...args) {
        this.validateEventName(eventName);
        
        if (this.debugMode && this.stats) {
            this.stats.totalEmitted++;
            this.stats.eventCounts.set(eventName, (this.stats.eventCounts.get(eventName) || 0) + 1);
        }

        const results = [];
        const listeners = this.events.get(eventName) || [];

        this.debugLog(`Emitting "${eventName}"`, { 
            listenersCount: listeners.length,
            args: args.length 
        });

        // 우선순위 순으로 리스너 실행
        for (const listenerWrapper of listeners) {
            try {
                const result = await this.executeListener(listenerWrapper.handler, args);
                results.push(result);
            } catch (error) {
                this.handleListenerError(eventName, error, listenerWrapper);
            }
        }

        return results;
    }

    /**
     * 동기적 이벤트 발생
     * @param {string} eventName - 이벤트 이름
     * @param {...any} args - 이벤트 인자
     * @returns {Array} 리스너 실행 결과 배열
     */
    emitSync(eventName, ...args) {
        this.validateEventName(eventName);
        
        const results = [];
        const listeners = this.events.get(eventName) || [];

        for (const listenerWrapper of listeners) {
            try {
                const result = listenerWrapper.handler(...args);
                results.push(result);
            } catch (error) {
                this.handleListenerError(eventName, error, listenerWrapper);
            }
        }

        return results;
    }

    /**
     * 리스너 실행
     * @param {Function} listener - 리스너 함수
     * @param {Array} args - 인자 배열
     * @returns {Promise<any>} 실행 결과
     * @private
     */
    async executeListener(listener, args) {
        const result = listener(...args);
        return Promise.resolve(result);
    }

    /**
     * 리스너 에러 처리
     * @param {string} eventName - 이벤트 이름
     * @param {Error} error - 에러 객체
     * @param {Object} listenerWrapper - 리스너 래퍼
     * @private
     */
    handleListenerError(eventName, error, listenerWrapper) {
        console.error(`EventBus listener error for "${eventName}":`, error);
        
        if (this.debugMode && this.stats) {
            this.stats.errorCounts.set(eventName, (this.stats.errorCounts.get(eventName) || 0) + 1);
        }

        // 에러 이벤트 발생
        this.emit('error', {
            eventName,
            error,
            listener: listenerWrapper
        });
    }

    /**
     * 이벤트 이름 검증
     * @param {string} eventName - 이벤트 이름
     * @private
     */
    validateEventName(eventName) {
        if (typeof eventName !== 'string' || eventName.length === 0) {
            throw new Error('Event name must be a non-empty string');
        }
    }

    /**
     * 리스너 함수 검증
     * @param {Function} listener - 리스너 함수
     * @private
     */
    validateListener(listener) {
        if (typeof listener !== 'function') {
            throw new Error('Listener must be a function');
        }
    }

    /**
     * 디버그 로그
     * @param {string} message - 메시지
     * @param {Object} data - 추가 데이터
     * @private
     */
    debugLog(message, data = {}) {
        if (this.debugMode) {
            console.log(`🚌 EventBus: ${message}`, data);
        }
    }

    /**
     * 등록된 이벤트 목록 가져오기
     * @returns {Array<string>} 이벤트 이름 배열
     */
    getEventNames() {
        return Array.from(this.events.keys());
    }

    /**
     * 특정 이벤트의 리스너 수 가져오기
     * @param {string} eventName - 이벤트 이름
     * @returns {number} 리스너 수
     */
    getListenerCount(eventName) {
        const listeners = this.events.get(eventName);
        return listeners ? listeners.length : 0;
    }

    /**
     * 모든 리스너 제거
     */
    removeAllListeners() {
        this.events.clear();
        this.onceEvents.clear();
        this.debugLog('All listeners removed');
    }

    /**
     * 통계 정보 가져오기 (개발 모드)
     * @returns {Object|null} 통계 정보
     */
    getStats() {
        return this.stats;
    }

    /**
     * 최대 리스너 수 설정
     * @param {number} max - 최대 리스너 수
     */
    setMaxListeners(max) {
        this.maxListeners = Math.max(1, max);
    }
}

// 전역 이벤트 버스 인스턴스
export const eventBus = new EventBus();

// 개발 모드에서 전역 접근 가능하게 설정
if (typeof window !== 'undefined' && process.env.NODE_ENV === 'development') {
    window.__TRADING_DASHBOARD_EVENTBUS__ = eventBus;
}
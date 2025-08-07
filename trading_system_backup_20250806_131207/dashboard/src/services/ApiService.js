/**
 * @fileoverview API 서비스 - REST API 통신
 * @description 향상된 HTTP 요청 관리 시스템
 */

import { eventBus } from '../core/EventBus.js';
import { globalStore } from '../core/Store.js';

/**
 * API 서비스 클래스
 * @class ApiService
 */
export class ApiService {
    constructor(baseURL = '/api') {
        this.baseURL = baseURL;
        this.requestInterceptors = [];
        this.responseInterceptors = [];
        this.errorInterceptors = [];
        
        // 요청 캐시
        this.cache = new Map();
        this.cacheTimeout = 30000; // 30초
        
        // 요청 중복 제거
        this.pendingRequests = new Map();
        
        // 재시도 설정
        this.retryConfig = {
            maxRetries: 3,
            retryDelay: 1000,
            retryCondition: (error) => {
                return error.status >= 500 || error.status === 0;
            }
        };
        
        // 통계
        this.stats = {
            totalRequests: 0,
            successfulRequests: 0,
            failedRequests: 0,
            cacheHits: 0,
            averageResponseTime: 0,
            responseTimeHistory: []
        };

        // 요청 큐 (오프라인 모드용)
        this.requestQueue = [];
        this.isOnline = navigator.onLine;
        
        this.initializeNetworkListeners();
    }

    /**
     * 네트워크 상태 리스너 초기화
     * @private
     */
    initializeNetworkListeners() {
        if (typeof window !== 'undefined') {
            window.addEventListener('online', () => {
                this.isOnline = true;
                this.processQueuedRequests();
                eventBus.emit('api:online');
            });

            window.addEventListener('offline', () => {
                this.isOnline = false;
                eventBus.emit('api:offline');
            });
        }
    }

    /**
     * 대기 중인 요청 처리
     * @private
     */
    async processQueuedRequests() {
        const queue = [...this.requestQueue];
        this.requestQueue = [];
        
        for (const queuedRequest of queue) {
            try {
                const response = await this.executeRequest(queuedRequest);
                queuedRequest.resolve(response);
            } catch (error) {
                queuedRequest.reject(error);
            }
        }
    }

    /**
     * 요청 인터셉터 추가
     * @param {Function} interceptor - 인터셉터 함수
     */
    addRequestInterceptor(interceptor) {
        this.requestInterceptors.push(interceptor);
    }

    /**
     * 응답 인터셉터 추가
     * @param {Function} interceptor - 인터셉터 함수
     */
    addResponseInterceptor(interceptor) {
        this.responseInterceptors.push(interceptor);
    }

    /**
     * 에러 인터셉터 추가
     * @param {Function} interceptor - 인터셉터 함수
     */
    addErrorInterceptor(interceptor) {
        this.errorInterceptors.push(interceptor);
    }

    /**
     * HTTP 요청 실행
     * @param {Object} config - 요청 설정
     * @returns {Promise<any>} 응답 데이터
     */
    async request(config) {
        const startTime = performance.now();
        this.stats.totalRequests++;

        try {
            // 요청 전처리
            const processedConfig = await this.processRequestConfig(config);
            
            // 캐시 확인
            if (processedConfig.cache) {
                const cached = this.getFromCache(processedConfig);
                if (cached) {
                    this.stats.cacheHits++;
                    return cached;
                }
            }

            // 중복 요청 확인
            const requestKey = this.generateRequestKey(processedConfig);
            if (this.pendingRequests.has(requestKey)) {
                return this.pendingRequests.get(requestKey);
            }

            // 오프라인 모드 처리
            if (!this.isOnline && processedConfig.queueOnOffline !== false) {
                return new Promise((resolve, reject) => {
                    this.requestQueue.push({
                        ...processedConfig,
                        resolve,
                        reject
                    });
                });
            }

            // 요청 실행
            const requestPromise = this.executeRequest(processedConfig);
            this.pendingRequests.set(requestKey, requestPromise);

            const response = await requestPromise;
            
            // 응답 처리
            const processedResponse = await this.processResponse(response, processedConfig);
            
            // 캐시 저장
            if (processedConfig.cache) {
                this.setCache(processedConfig, processedResponse);
            }

            // 통계 업데이트
            const responseTime = performance.now() - startTime;
            this.updateStats(true, responseTime);
            
            // 완료된 요청 제거
            this.pendingRequests.delete(requestKey);
            
            return processedResponse;
            
        } catch (error) {
            // 에러 처리
            const processedError = await this.processError(error, config);
            
            // 재시도 로직
            if (this.shouldRetry(processedError, config)) {
                config.retryCount = (config.retryCount || 0) + 1;
                
                await this.delay(
                    this.retryConfig.retryDelay * Math.pow(2, config.retryCount - 1)
                );
                
                return this.request(config);
            }

            // 통계 업데이트
            const responseTime = performance.now() - startTime;
            this.updateStats(false, responseTime);
            
            // 완료된 요청 제거
            const requestKey = this.generateRequestKey(config);
            this.pendingRequests.delete(requestKey);
            
            throw processedError;
        }
    }

    /**
     * 요청 설정 전처리
     * @param {Object} config - 원본 설정
     * @returns {Promise<Object>} 처리된 설정
     * @private
     */
    async processRequestConfig(config) {
        let processedConfig = {
            url: config.url.startsWith('http') ? config.url : `${this.baseURL}${config.url}`,
            method: config.method || 'GET',
            headers: {
                'Content-Type': 'application/json',
                ...config.headers
            },
            ...config
        };

        // 인터셉터 적용
        for (const interceptor of this.requestInterceptors) {
            processedConfig = await interceptor(processedConfig);
        }

        return processedConfig;
    }

    /**
     * HTTP 요청 실행
     * @param {Object} config - 요청 설정
     * @returns {Promise<Response>} fetch 응답
     * @private
     */
    async executeRequest(config) {
        const fetchOptions = {
            method: config.method,
            headers: config.headers,
            signal: config.signal
        };

        // 요청 본문 설정
        if (config.data && ['POST', 'PUT', 'PATCH'].includes(config.method)) {
            if (config.headers['Content-Type'] === 'application/json') {
                fetchOptions.body = JSON.stringify(config.data);
            } else if (config.data instanceof FormData) {
                fetchOptions.body = config.data;
                delete fetchOptions.headers['Content-Type']; // FormData는 자동 설정
            } else {
                fetchOptions.body = config.data;
            }
        }

        // URL 파라미터 처리
        const url = config.params ? 
            `${config.url}?${new URLSearchParams(config.params)}` : 
            config.url;

        const response = await fetch(url, fetchOptions);
        
        if (!response.ok) {
            throw new ApiError(
                `HTTP ${response.status}: ${response.statusText}`,
                response.status,
                response,
                config
            );
        }

        return response;
    }

    /**
     * 응답 처리
     * @param {Response} response - fetch 응답
     * @param {Object} config - 요청 설정
     * @returns {Promise<any>} 처리된 응답 데이터
     * @private
     */
    async processResponse(response, config) {
        let data;
        
        // 응답 타입에 따른 데이터 추출
        const contentType = response.headers.get('Content-Type') || '';
        
        if (contentType.includes('application/json')) {
            data = await response.json();
        } else if (contentType.includes('text/')) {
            data = await response.text();
        } else if (contentType.includes('application/octet-stream')) {
            data = await response.blob();
        } else {
            data = await response.text();
        }

        let processedResponse = {
            data,
            status: response.status,
            statusText: response.statusText,
            headers: response.headers,
            config
        };

        // 응답 인터셉터 적용
        for (const interceptor of this.responseInterceptors) {
            processedResponse = await interceptor(processedResponse);
        }

        return processedResponse.data;
    }

    /**
     * 에러 처리
     * @param {Error} error - 에러 객체
     * @param {Object} config - 요청 설정
     * @returns {Promise<Error>} 처리된 에러
     * @private
     */
    async processError(error, config) {
        let processedError = error;

        // 에러 인터셉터 적용
        for (const interceptor of this.errorInterceptors) {
            processedError = await interceptor(processedError, config);
        }

        // 이벤트 발생
        eventBus.emit('api:error', {
            error: processedError,
            config,
            timestamp: Date.now()
        });

        return processedError;
    }

    /**
     * 재시도 여부 확인
     * @param {Error} error - 에러 객체
     * @param {Object} config - 요청 설정
     * @returns {boolean} 재시도 여부
     * @private
     */
    shouldRetry(error, config) {
        const retryCount = config.retryCount || 0;
        
        return retryCount < this.retryConfig.maxRetries &&
               this.retryConfig.retryCondition(error);
    }

    /**
     * 지연 함수
     * @param {number} ms - 지연 시간 (밀리초)
     * @returns {Promise<void>}
     * @private
     */
    delay(ms) {
        return new Promise(resolve => setTimeout(resolve, ms));
    }

    /**
     * 요청 키 생성 (중복 요청 방지용)
     * @param {Object} config - 요청 설정
     * @returns {string} 요청 키
     * @private
     */
    generateRequestKey(config) {
        return `${config.method}:${config.url}:${JSON.stringify(config.params || {})}`;
    }

    /**
     * 캐시에서 데이터 가져오기
     * @param {Object} config - 요청 설정
     * @returns {any|null} 캐시된 데이터
     * @private
     */
    getFromCache(config) {
        const key = this.generateRequestKey(config);
        const cached = this.cache.get(key);
        
        if (cached && Date.now() - cached.timestamp < this.cacheTimeout) {
            return cached.data;
        }
        
        if (cached) {
            this.cache.delete(key);
        }
        
        return null;
    }

    /**
     * 캐시에 데이터 저장
     * @param {Object} config - 요청 설정
     * @param {any} data - 저장할 데이터
     * @private
     */
    setCache(config, data) {
        const key = this.generateRequestKey(config);
        this.cache.set(key, {
            data,
            timestamp: Date.now()
        });

        // 캐시 크기 제한
        if (this.cache.size > 100) {
            const firstKey = this.cache.keys().next().value;
            this.cache.delete(firstKey);
        }
    }

    /**
     * 통계 업데이트
     * @param {boolean} success - 성공 여부
     * @param {number} responseTime - 응답 시간
     * @private
     */
    updateStats(success, responseTime) {
        if (success) {
            this.stats.successfulRequests++;
        } else {
            this.stats.failedRequests++;
        }

        // 응답 시간 통계
        this.stats.responseTimeHistory.push(responseTime);
        if (this.stats.responseTimeHistory.length > 50) {
            this.stats.responseTimeHistory.shift();
        }

        this.stats.averageResponseTime = 
            this.stats.responseTimeHistory.reduce((sum, time) => sum + time, 0) / 
            this.stats.responseTimeHistory.length;
    }

    // 편의 메서드들
    
    /**
     * GET 요청
     * @param {string} url - 요청 URL
     * @param {Object} [config] - 추가 설정
     * @returns {Promise<any>} 응답 데이터
     */
    get(url, config = {}) {
        return this.request({ ...config, url, method: 'GET' });
    }

    /**
     * POST 요청
     * @param {string} url - 요청 URL
     * @param {any} data - 요청 데이터
     * @param {Object} [config] - 추가 설정
     * @returns {Promise<any>} 응답 데이터
     */
    post(url, data, config = {}) {
        return this.request({ ...config, url, method: 'POST', data });
    }

    /**
     * PUT 요청
     * @param {string} url - 요청 URL
     * @param {any} data - 요청 데이터
     * @param {Object} [config] - 추가 설정
     * @returns {Promise<any>} 응답 데이터
     */
    put(url, data, config = {}) {
        return this.request({ ...config, url, method: 'PUT', data });
    }

    /**
     * DELETE 요청
     * @param {string} url - 요청 URL
     * @param {Object} [config] - 추가 설정
     * @returns {Promise<any>} 응답 데이터
     */
    delete(url, config = {}) {
        return this.request({ ...config, url, method: 'DELETE' });
    }

    /**
     * PATCH 요청
     * @param {string} url - 요청 URL
     * @param {any} data - 요청 데이터
     * @param {Object} [config] - 추가 설정
     * @returns {Promise<any>} 응답 데이터
     */
    patch(url, data, config = {}) {
        return this.request({ ...config, url, method: 'PATCH', data });
    }

    // 특화된 API 메서드들

    /**
     * 대시보드 데이터 가져오기
     * @returns {Promise<Object>} 대시보드 데이터
     */
    async getDashboardData() {
        return this.get('/dashboard', { cache: true });
    }

    /**
     * 포지션 목록 가져오기
     * @returns {Promise<Array>} 포지션 목록
     */
    async getPositions() {
        return this.get('/positions', { cache: true });
    }

    /**
     * 거래 히스토리 가져오기
     * @param {Object} [params] - 쿼리 파라미터
     * @returns {Promise<Array>} 거래 히스토리
     */
    async getTradeHistory(params = {}) {
        return this.get('/trades', { params, cache: true });
    }

    /**
     * 잔고 정보 가져오기
     * @returns {Promise<Object>} 잔고 정보
     */
    async getBalance() {
        return this.get('/balance', { cache: true });
    }

    /**
     * 시스템 상태 가져오기
     * @returns {Promise<Object>} 시스템 상태
     */
    async getSystemStatus() {
        return this.get('/status', { cache: true });
    }

    /**
     * 알림 목록 가져오기
     * @returns {Promise<Object>} 알림 데이터
     */
    async getNotifications() {
        return this.get('/notifications', { cache: false });
    }

    /**
     * 포지션 닫기
     * @param {string} symbol - 심볼
     * @param {string} [reason] - 닫기 사유
     * @returns {Promise<Object>} 응답 데이터
     */
    async closePosition(symbol, reason = 'manual') {
        return this.post('/positions/close', { symbol, reason });
    }

    /**
     * 주문 실행
     * @param {Object} orderData - 주문 데이터
     * @returns {Promise<Object>} 주문 결과
     */
    async placeOrder(orderData) {
        return this.post('/orders', orderData);
    }

    /**
     * 자본 추적 현황 가져오기
     * @returns {Promise<Object>} 자본 추적 데이터
     */
    async getCapitalTracking() {
        return this.get('/capital/status', { cache: true, cacheTimeout: 5000 }); // 5초 캐시
    }

    /**
     * 상세 포지션 할당 정보 가져오기
     * @returns {Promise<Array>} 상세 포지션 정보
     */
    async getDetailedPositions() {
        return this.get('/capital/positions', { cache: true, cacheTimeout: 5000 });
    }

    /**
     * 자본 추적 강제 업데이트
     * @returns {Promise<Object>} 업데이트된 자본 정보
     */
    async forceCapitalUpdate() {
        return this.post('/capital/update');
    }

    /**
     * 심볼별 사용 가능 자본 조회
     * @param {string} symbol - 심볼 (BTCUSDT, ETHUSDT)
     * @returns {Promise<Object>} 사용 가능 자본 정보
     */
    async getAvailableCapitalForSymbol(symbol) {
        return this.get(`/capital/available/${symbol}`, { cache: true, cacheTimeout: 10000 });
    }

    /**
     * 알림 시스템 테스트
     * @returns {Promise<Object>} 테스트 결과
     */
    async testNotificationSystem() {
        return this.post('/notifications/test');
    }

    /**
     * 통계 정보 가져오기
     * @returns {Object} API 통계
     */
    getStats() {
        return {
            ...this.stats,
            cacheSize: this.cache.size,
            pendingRequests: this.pendingRequests.size,
            queuedRequests: this.requestQueue.length,
            isOnline: this.isOnline
        };
    }

    /**
     * 캐시 클리어
     */
    clearCache() {
        this.cache.clear();
        eventBus.emit('api:cache_cleared');
    }

    /**
     * 통계 리셋
     */
    resetStats() {
        this.stats = {
            totalRequests: 0,
            successfulRequests: 0,
            failedRequests: 0,
            cacheHits: 0,
            averageResponseTime: 0,
            responseTimeHistory: []
        };
    }
}

/**
 * API 에러 클래스
 * @class ApiError
 * @extends Error
 */
export class ApiError extends Error {
    constructor(message, status, response, config) {
        super(message);
        this.name = 'ApiError';
        this.status = status;
        this.response = response;
        this.config = config;
    }
}

// 전역 API 서비스 인스턴스
export const apiService = new ApiService();

// 기본 인터셉터 설정
apiService.addRequestInterceptor(async (config) => {
    // 인증 토큰 추가 (필요시)
    const token = localStorage.getItem('auth_token');
    if (token) {
        config.headers['Authorization'] = `Bearer ${token}`;
    }
    
    return config;
});

apiService.addResponseInterceptor(async (response) => {
    // 글로벌 응답 처리 로직
    return response;
});

apiService.addErrorInterceptor(async (error, config) => {
    // 인증 에러 처리
    if (error.status === 401) {
        eventBus.emit('auth:unauthorized');
        // 로그인 페이지로 리다이렉트 등
    }
    
    // 서버 에러 처리
    if (error.status >= 500) {
        globalStore.dispatch({
            type: 'ADD_NOTIFICATION',
            payload: {
                type: 'error',
                message: '서버 오류가 발생했습니다.',
                timestamp: Date.now()
            }
        });
    }
    
    return error;
});

// 개발 모드에서 전역 접근 가능하게 설정
if (typeof window !== 'undefined' && process.env.NODE_ENV === 'development') {
    window.__TRADING_DASHBOARD_API__ = apiService;
}
import { BaseComponent } from '../core/BaseComponent.js';

/**
 * 전역 에러 바운더리 시스템
 * - JavaScript 에러 포착 및 처리
 * - 컴포넌트 레벨 에러 복구
 * - 에러 로깅 및 리포팅
 * - 사용자 친화적 에러 메시지
 */
export class ErrorBoundary extends BaseComponent {
    constructor(options = {}) {
        super(null, options);
        
        // 에러 설정
        this.errorTypes = {
            COMPONENT_ERROR: 'component_error',
            NETWORK_ERROR: 'network_error', 
            WEBSOCKET_ERROR: 'websocket_error',
            CHART_ERROR: 'chart_error',
            DATA_ERROR: 'data_error',
            PERMISSION_ERROR: 'permission_error',
            VALIDATION_ERROR: 'validation_error',
            RUNTIME_ERROR: 'runtime_error'
        };
        
        // 에러 레벨
        this.errorLevels = {
            LOW: 'low',           // 경고성 에러
            MEDIUM: 'medium',     // 기능 제한 에러
            HIGH: 'high',         // 중요 기능 실패
            CRITICAL: 'critical'  // 시스템 전체 문제
        };
        
        // 에러 저장소
        this.errors = [];
        this.errorCounters = new Map();
        this.maxErrorHistory = options.maxErrorHistory || 100;
        this.errorThreshold = options.errorThreshold || 10; // 1분당 최대 에러 수
        
        // 복구 전략
        this.recoveryStrategies = new Map();
        this.retryAttempts = new Map();
        this.maxRetries = options.maxRetries || 3;
        
        // 알림 설정
        this.notificationEnabled = options.notifications !== false;
        this.debugMode = options.debug || false;
        
        // 에러 패턴 분석
        this.errorPatterns = new Map();
        this.patternThreshold = options.patternThreshold || 3;
        
        // 자동 복구 기능
        this.autoRecoveryEnabled = options.autoRecovery !== false;
        this.recoveryTimeout = options.recoveryTimeout || 5000;
        
        this.init();
    }
    
    /**
     * 초기화
     */
    init() {
        this.setupGlobalErrorHandlers();
        this.setupRecoveryStrategies();
        this.setupErrorReporting();
        this.startErrorMonitoring();
        this.emit('errorBoundaryInitialized');
    }
    
    /**
     * 전역 에러 핸들러 설정
     */
    setupGlobalErrorHandlers() {
        // JavaScript 런타임 에러
        window.addEventListener('error', (event) => {
            this.handleError({
                type: this.errorTypes.RUNTIME_ERROR,
                level: this.errorLevels.HIGH,
                message: event.message,
                filename: event.filename,
                lineno: event.lineno,
                colno: event.colno,
                error: event.error,
                timestamp: Date.now()
            });
        });
        
        // Promise rejection 에러
        window.addEventListener('unhandledrejection', (event) => {
            this.handleError({
                type: this.errorTypes.RUNTIME_ERROR,
                level: this.errorLevels.MEDIUM,
                message: 'Unhandled Promise Rejection',
                error: event.reason,
                timestamp: Date.now()
            });
            
            // 에러 전파 방지 (선택적)
            if (this.shouldPreventDefault(event.reason)) {
                event.preventDefault();
            }
        });
        
        // 네트워크 에러
        window.addEventListener('offline', () => {
            this.handleError({
                type: this.errorTypes.NETWORK_ERROR,
                level: this.errorLevels.HIGH,
                message: '인터넷 연결이 끊어졌습니다',
                timestamp: Date.now()
            });
        });
        
        window.addEventListener('online', () => {
            this.handleNetworkRecovery();
        });
        
        // 리소스 로딩 에러
        document.addEventListener('error', (event) => {
            if (event.target !== window) {
                this.handleError({
                    type: this.errorTypes.NETWORK_ERROR,
                    level: this.errorLevels.MEDIUM,
                    message: `리소스 로딩 실패: ${event.target.src || event.target.href}`,
                    element: event.target,
                    timestamp: Date.now()
                });
            }
        }, true);
    }
    
    /**
     * 에러 처리 메인 함수
     */
    handleError(errorInfo) {
        try {
            // 에러 정규화
            const normalizedError = this.normalizeError(errorInfo);
            
            // 중복 에러 체크
            if (this.isDuplicateError(normalizedError)) {
                this.updateErrorCount(normalizedError);
                return;
            }
            
            // 에러 저장
            this.storeError(normalizedError);
            
            // 에러 패턴 분석
            this.analyzeErrorPattern(normalizedError);
            
            // 에러 로깅
            this.logError(normalizedError);
            
            // 사용자 알림
            if (this.shouldNotifyUser(normalizedError)) {
                this.notifyUser(normalizedError);
            }
            
            // 자동 복구 시도
            if (this.autoRecoveryEnabled) {
                this.attemptRecovery(normalizedError);
            }
            
            // 에러 이벤트 발생
            this.emit('errorOccurred', normalizedError);
            
        } catch (handlingError) {
            console.error('Error handling failed:', handlingError);
            this.handleCriticalError(handlingError);
        }
    }
    
    /**
     * 에러 정규화
     */
    normalizeError(errorInfo) {
        const normalized = {
            id: this.generateErrorId(),
            type: errorInfo.type || this.errorTypes.RUNTIME_ERROR,
            level: errorInfo.level || this.errorLevels.MEDIUM,
            message: this.sanitizeMessage(errorInfo.message || 'Unknown error'),
            timestamp: errorInfo.timestamp || Date.now(),
            stack: errorInfo.error?.stack || new Error().stack,
            component: errorInfo.component || null,
            userAgent: navigator.userAgent,
            url: window.location.href,
            userId: this.getCurrentUserId(),
            sessionId: this.getSessionId()
        };
        
        // 추가 메타데이터
        if (errorInfo.error) {
            normalized.errorName = errorInfo.error.name;
            normalized.errorMessage = errorInfo.error.message;
        }
        
        if (errorInfo.filename) {
            normalized.filename = errorInfo.filename;
            normalized.lineno = errorInfo.lineno;
            normalized.colno = errorInfo.colno;
        }
        
        return normalized;
    }
    
    /**
     * 중복 에러 체크
     */
    isDuplicateError(error) {
        const key = this.getErrorKey(error);
        const lastError = this.errorCounters.get(key);
        
        if (lastError && Date.now() - lastError.timestamp < 1000) {
            return true;
        }
        
        return false;
    }
    
    /**
     * 에러 키 생성
     */
    getErrorKey(error) {
        return `${error.type}-${error.message}-${error.component || 'global'}`;
    }
    
    /**
     * 에러 개수 업데이트
     */
    updateErrorCount(error) {
        const key = this.getErrorKey(error);
        const existing = this.errorCounters.get(key) || { count: 0, timestamp: Date.now() };
        
        existing.count++;
        existing.timestamp = Date.now();
        
        this.errorCounters.set(key, existing);
        
        // 에러 임계치 체크
        if (existing.count > this.errorThreshold) {
            this.handleErrorThresholdExceeded(error, existing.count);
        }
    }
    
    /**
     * 에러 저장
     */
    storeError(error) {
        this.errors.unshift(error);
        
        // 최대 개수 제한
        if (this.errors.length > this.maxErrorHistory) {
            this.errors = this.errors.slice(0, this.maxErrorHistory);
        }
        
        // 로컬 스토리지에 저장 (선택적)
        if (this.shouldPersistError(error)) {
            this.persistError(error);
        }
    }
    
    /**
     * 사용자 친화적 메시지 생성
     */
    getUserFriendlyMessage(error) {
        const messageMap = {
            [this.errorTypes.NETWORK_ERROR]: '네트워크 연결에 문제가 있습니다. 인터넷 연결을 확인해주세요.',
            [this.errorTypes.WEBSOCKET_ERROR]: '실시간 데이터 연결이 끊어졌습니다. 자동으로 재연결을 시도합니다.',
            [this.errorTypes.CHART_ERROR]: '차트를 불러오는 중 문제가 발생했습니다. 페이지를 새로고침 해주세요.',
            [this.errorTypes.DATA_ERROR]: '데이터 처리 중 오류가 발생했습니다. 잠시 후 다시 시도해주세요.',
            [this.errorTypes.PERMISSION_ERROR]: '접근 권한이 없습니다. 로그인 상태를 확인해주세요.',
            [this.errorTypes.VALIDATION_ERROR]: '입력한 정보에 오류가 있습니다. 다시 확인해주세요.'
        };
        
        return messageMap[error.type] || '일시적인 오류가 발생했습니다. 잠시 후 다시 시도해주세요.';
    }
    
    /**
     * 복구 전략 설정
     */
    setupRecoveryStrategies() {
        // WebSocket 재연결
        this.recoveryStrategies.set(this.errorTypes.WEBSOCKET_ERROR, {
            name: 'WebSocket 재연결',
            handler: () => this.recoverWebSocket(),
            maxAttempts: 5,
            delay: 2000
        });
        
        // 차트 재초기화
        this.recoveryStrategies.set(this.errorTypes.CHART_ERROR, {
            name: '차트 재초기화',
            handler: () => this.recoverChart(),
            maxAttempts: 3,
            delay: 1000
        });
        
        // 데이터 새로고침
        this.recoveryStrategies.set(this.errorTypes.DATA_ERROR, {
            name: '데이터 새로고침',
            handler: () => this.recoverData(),
            maxAttempts: 2,
            delay: 3000
        });
        
        // 컴포넌트 재렌더링
        this.recoveryStrategies.set(this.errorTypes.COMPONENT_ERROR, {
            name: '컴포넌트 재렌더링',
            handler: (error) => this.recoverComponent(error),
            maxAttempts: 2,
            delay: 500
        });
    }
    
    /**
     * 자동 복구 시도
     */
    async attemptRecovery(error) {
        const strategy = this.recoveryStrategies.get(error.type);
        if (!strategy) return;
        
        const attemptKey = `${error.type}-${Date.now()}`;
        const currentAttempts = this.retryAttempts.get(error.type) || 0;
        
        if (currentAttempts >= strategy.maxAttempts) {
            this.handleRecoveryFailure(error, strategy);
            return;
        }
        
        try {
            this.emit('recoveryStarted', { error, strategy, attempt: currentAttempts + 1 });
            
            // 복구 시도
            await new Promise(resolve => setTimeout(resolve, strategy.delay));
            const result = await strategy.handler(error);
            
            if (result !== false) {
                // 복구 성공
                this.handleRecoverySuccess(error, strategy);
                this.retryAttempts.delete(error.type);
            } else {
                throw new Error('Recovery handler returned false');
            }
            
        } catch (recoveryError) {
            this.retryAttempts.set(error.type, currentAttempts + 1);
            this.handleRecoveryError(error, strategy, recoveryError);
            
            // 재시도
            if (currentAttempts + 1 < strategy.maxAttempts) {
                setTimeout(() => this.attemptRecovery(error), strategy.delay * 2);
            }
        }
    }
    
    // 헬퍼 메소드들 (간소화)
    generateErrorId() { return `err_${Date.now()}_${Math.random().toString(36).substr(2, 9)}`; }
    sanitizeMessage(message) { return String(message).substring(0, 500); }
    getCurrentUserId() { return localStorage.getItem('userId') || 'anonymous'; }
    getSessionId() { 
        if (!window.sessionId) {
            window.sessionId = `session_${Date.now()}_${Math.random().toString(36).substr(2, 9)}`;
        }
        return window.sessionId;
    }
    
    shouldPreventDefault(reason) {
        return reason instanceof TypeError || reason instanceof ReferenceError;
    }
    
    handleNetworkRecovery() {
        this.handleError({
            type: this.errorTypes.NETWORK_ERROR,
            level: this.errorLevels.LOW,
            message: '인터넷 연결이 복구되었습니다',
            timestamp: Date.now()
        });
        this.emit('networkRecovered');
    }
    
    // 구현 생략된 메소드들 (필요시 확장)
    analyzeErrorPattern(error) { /* 구현 생략 */ }
    logError(error) { console.error(`[${error.level.toUpperCase()}] ${error.type}: ${error.message}`, error); }
    shouldNotifyUser(error) { return this.notificationEnabled && error.level !== this.errorLevels.LOW; }
    notifyUser(error) { this.emit('showNotification', { message: this.getUserFriendlyMessage(error), type: 'error' }); }
    
    recoverWebSocket() { this.emit('recoverWebSocket'); return true; }
    recoverChart() { this.emit('recoverChart'); return true; }
    recoverData() { this.emit('recoverData'); return true; }
    recoverComponent(error) { this.emit('recoverComponent', error.component); return true; }
    
    setupErrorReporting() { /* 구현 생략 */ }
    startErrorMonitoring() { /* 구현 생략 */ }
    
    shouldPersistError(error) { return error.level === this.errorLevels.CRITICAL || error.level === this.errorLevels.HIGH; }
    persistError(error) {
        try {
            const errors = JSON.parse(localStorage.getItem('persistedErrors') || '[]');
            errors.unshift(error);
            localStorage.setItem('persistedErrors', JSON.stringify(errors.slice(0, 50)));
        } catch (e) { console.warn('Failed to persist error:', e); }
    }
    
    handleErrorThresholdExceeded(error, count) { /* 구현 생략 */ }
    handleRecoverySuccess(error, strategy) { this.emit('recoverySuccess', { error, strategy }); }
    handleRecoveryFailure(error, strategy) { this.emit('recoveryFailure', { error, strategy }); }
    handleRecoveryError(error, strategy, recoveryError) { this.emit('recoveryError', { error, strategy, recoveryError }); }
    handleCriticalError(error) {
        console.error('Critical error in ErrorBoundary:', error);
        if (window.confirm('심각한 오류가 발생했습니다. 페이지를 새로고침하시겠습니까?')) {
            window.location.reload();
        }
    }
    
    // 외부 API
    reportError(error, context = {}) {
        this.handleError({ ...error, ...context, timestamp: Date.now() });
    }
    
    getErrorStats() {
        return {
            total: this.errors.length,
            recent: this.errors.filter(e => Date.now() - e.timestamp < 3600000)
        };
    }
    
    clearErrors() {
        this.errors = [];
        this.emit('errorsCleared');
    }
    
    destroy() {
        this.clearErrors();
        this.errorCounters.clear();
        this.errorPatterns.clear();
        this.retryAttempts.clear();
        this.recoveryStrategies.clear();
        super.destroy();
    }
}

export default ErrorBoundary;
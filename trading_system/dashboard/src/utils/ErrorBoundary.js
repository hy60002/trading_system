/**
 * @fileoverview 에러 바운더리 유틸리티
 * @description React Error Boundary 패턴을 참고한 에러 처리 시스템
 */

import { eventBus } from '../core/EventBus.js';

/**
 * 에러 바운더리 클래스
 * @class ErrorBoundary
 */
export class ErrorBoundary {
    constructor() {
        this.errorHandlers = new Map();
        this.errorHistory = [];
        this.maxHistorySize = 50;
        this.isRecovering = false;
        this.recoveryAttempts = new Map();
        this.maxRecoveryAttempts = 3;
        
        // 에러 타입별 처리 전략
        this.errorStrategies = new Map([
            ['TypeError', 'retry'],
            ['NetworkError', 'fallback'],
            ['SyntaxError', 'reload'],
            ['ChunkLoadError', 'reload'],
            ['SecurityError', 'report'],
            ['ReferenceError', 'restart']
        ]);
        
        // 복구 전략
        this.recoveryStrategies = new Map([
            ['retry', this.retryStrategy.bind(this)],
            ['fallback', this.fallbackStrategy.bind(this)],
            ['reload', this.reloadStrategy.bind(this)],
            ['restart', this.restartStrategy.bind(this)],
            ['report', this.reportStrategy.bind(this)]
        ]);
        
        this.setupGlobalHandlers();
    }

    /**
     * 전역 에러 핸들러 설정
     * @private
     */
    setupGlobalHandlers() {
        // JavaScript 에러
        window.addEventListener('error', (event) => {
            this.handleError(event.error, {
                type: 'javascript',
                filename: event.filename,
                lineno: event.lineno,
                colno: event.colno,
                message: event.message
            });
        });

        // Promise rejection 에러
        window.addEventListener('unhandledrejection', (event) => {
            this.handleError(event.reason, {
                type: 'promise',
                promise: event.promise
            });
        });

        // 리소스 로딩 에러
        window.addEventListener('error', (event) => {
            if (event.target !== window) {
                this.handleResourceError(event);
            }
        }, true);
    }

    /**
     * 에러 처리
     * @param {Error} error - 에러 객체
     * @param {Object} errorInfo - 에러 정보
     */
    handleError(error, errorInfo = {}) {
        const errorData = this.processError(error, errorInfo);
        
        // 에러 히스토리에 추가
        this.addToHistory(errorData);
        
        // 에러 분류 및 처리
        const strategy = this.determineStrategy(errorData);
        
        // 복구 시도
        this.attemptRecovery(errorData, strategy);
        
        // 이벤트 발생
        eventBus.emit('error:boundary', errorData);
        
        // 콜백 실행
        if (this.onError) {
            this.onError(error, errorInfo);
        }
    }

    /**
     * 리소스 에러 처리
     * @param {Event} event - 에러 이벤트
     * @private
     */
    handleResourceError(event) {
        const target = event.target;
        const errorData = {
            type: 'resource',
            resourceType: target.tagName.toLowerCase(),
            src: target.src || target.href,
            message: `Failed to load ${target.tagName.toLowerCase()}`,
            timestamp: Date.now()
        };
        
        this.addToHistory(errorData);
        eventBus.emit('error:resource', errorData);
        
        // 리소스별 복구 전략
        this.handleResourceRecovery(target, errorData);
    }

    /**
     * 에러 데이터 처리
     * @param {Error} error - 에러 객체
     * @param {Object} errorInfo - 에러 정보
     * @returns {Object} 처리된 에러 데이터
     * @private
     */
    processError(error, errorInfo) {
        return {
            name: error.name || 'UnknownError',
            message: error.message || 'An unknown error occurred',
            stack: error.stack,
            timestamp: Date.now(),
            userAgent: navigator.userAgent,
            url: window.location.href,
            ...errorInfo,
            
            // 에러 심각도 계산
            severity: this.calculateSeverity(error, errorInfo),
            
            // 에러 카테고리
            category: this.categorizeError(error, errorInfo),
            
            // 복구 가능 여부
            recoverable: this.isRecoverable(error, errorInfo)
        };
    }

    /**
     * 에러 심각도 계산
     * @param {Error} error - 에러 객체
     * @param {Object} errorInfo - 에러 정보
     * @returns {string} 심각도 (low, medium, high, critical)
     * @private
     */
    calculateSeverity(error, errorInfo) {
        // Critical: 시스템 전체에 영향
        if (error.name === 'SecurityError' || 
            error.message.includes('chunk') ||
            errorInfo.type === 'system') {
            return 'critical';
        }
        
        // High: 주요 기능에 영향
        if (error.name === 'TypeError' && error.stack.includes('main') ||
            error.name === 'ReferenceError' ||
            errorInfo.type === 'component' && errorInfo.critical) {
            return 'high';
        }
        
        // Medium: 부분적 기능 영향
        if (error.name === 'NetworkError' ||
            errorInfo.type === 'api' ||
            errorInfo.type === 'websocket') {
            return 'medium';
        }
        
        // Low: 최소한의 영향
        return 'low';
    }

    /**
     * 에러 카테고리 분류
     * @param {Error} error - 에러 객체
     * @param {Object} errorInfo - 에러 정보
     * @returns {string} 카테고리
     * @private
     */
    categorizeError(error, errorInfo) {
        if (errorInfo.type) {
            return errorInfo.type;
        }
        
        if (error.name.includes('Network') || 
            error.message.includes('fetch') ||
            error.message.includes('XMLHttpRequest')) {
            return 'network';
        }
        
        if (error.name === 'TypeError' || error.name === 'ReferenceError') {
            return 'code';
        }
        
        if (error.name === 'SyntaxError') {
            return 'syntax';
        }
        
        if (error.message.includes('chunk') || error.message.includes('Loading')) {
            return 'loading';
        }
        
        return 'unknown';
    }

    /**
     * 복구 가능 여부 판단
     * @param {Error} error - 에러 객체
     * @param {Object} errorInfo - 에러 정보
     * @returns {boolean} 복구 가능 여부
     * @private
     */
    isRecoverable(error, errorInfo) {
        const nonRecoverableErrors = [
            'SecurityError',
            'SyntaxError'
        ];
        
        if (nonRecoverableErrors.includes(error.name)) {
            return false;
        }
        
        if (errorInfo.severity === 'critical') {
            return false;
        }
        
        return true;
    }

    /**
     * 처리 전략 결정
     * @param {Object} errorData - 에러 데이터
     * @returns {string} 처리 전략
     * @private
     */
    determineStrategy(errorData) {
        // 사용자 정의 전략 확인
        const customStrategy = this.errorStrategies.get(errorData.name);
        if (customStrategy) {
            return customStrategy;
        }
        
        // 카테고리별 기본 전략
        switch (errorData.category) {
            case 'network':
                return 'retry';
            case 'loading':
                return 'reload';
            case 'code':
                return 'restart';
            case 'component':
                return 'fallback';
            default:
                return 'report';
        }
    }

    /**
     * 복구 시도
     * @param {Object} errorData - 에러 데이터
     * @param {string} strategy - 복구 전략
     * @private
     */
    async attemptRecovery(errorData, strategy) {
        if (!errorData.recoverable || this.isRecovering) {
            return;
        }
        
        const errorKey = `${errorData.name}:${errorData.message}`;
        const attempts = this.recoveryAttempts.get(errorKey) || 0;
        
        if (attempts >= this.maxRecoveryAttempts) {
            console.error(`❌ 최대 복구 시도 횟수 초과: ${errorKey}`);
            return;
        }
        
        this.isRecovering = true;
        this.recoveryAttempts.set(errorKey, attempts + 1);
        
        try {
            const recoveryFunction = this.recoveryStrategies.get(strategy);
            if (recoveryFunction) {
                await recoveryFunction(errorData);
                console.log(`✅ 에러 복구 성공: ${strategy}`);
                
                eventBus.emit('error:recovered', {
                    strategy,
                    errorData,
                    attempts: attempts + 1
                });
            }
        } catch (recoveryError) {
            console.error(`❌ 에러 복구 실패 (${strategy}):`, recoveryError);
            
            eventBus.emit('error:recovery_failed', {
                strategy,
                errorData,
                recoveryError,
                attempts: attempts + 1
            });
        } finally {
            this.isRecovering = false;
        }
    }

    /**
     * 재시도 전략
     * @param {Object} errorData - 에러 데이터
     * @private
     */
    async retryStrategy(errorData) {
        console.log('🔄 재시도 전략 실행:', errorData.message);
        
        // 잠시 대기 후 재시도
        await this.delay(1000);
        
        // 실패한 작업을 다시 시도하는 이벤트 발생
        eventBus.emit('error:retry', errorData);
    }

    /**
     * 대체 전략
     * @param {Object} errorData - 에러 데이터
     * @private
     */
    async fallbackStrategy(errorData) {
        console.log('🔀 대체 전략 실행:', errorData.message);
        
        // 대체 UI 또는 기능 활성화
        eventBus.emit('error:fallback', errorData);
        
        // 오프라인 모드 활성화 (네트워크 에러인 경우)
        if (errorData.category === 'network') {
            eventBus.emit('app:offline_mode', true);
        }
    }

    /**
     * 새로고침 전략
     * @param {Object} errorData - 에러 데이터
     * @private
     */
    async reloadStrategy(errorData) {
        console.log('🔄 새로고침 전략 실행:', errorData.message);
        
        // 사용자에게 확인 후 새로고침
        const confirmReload = await this.showReloadDialog(errorData);
        
        if (confirmReload) {
            // 저장되지 않은 데이터 백업
            eventBus.emit('app:backup_data');
            
            // 잠시 대기 후 새로고침
            setTimeout(() => {
                window.location.reload();
            }, 1000);
        }
    }

    /**
     * 재시작 전략
     * @param {Object} errorData - 에러 데이터
     * @private
     */
    async restartStrategy(errorData) {
        console.log('🔄 재시작 전략 실행:', errorData.message);
        
        // 애플리케이션 재시작 이벤트
        eventBus.emit('app:restart', errorData);
    }

    /**
     * 보고 전략
     * @param {Object} errorData - 에러 데이터
     * @private
     */
    async reportStrategy(errorData) {
        console.log('📤 보고 전략 실행:', errorData.message);
        
        // 에러 리포팅 서비스로 전송
        await this.sendErrorReport(errorData);
        
        // 사용자에게 에러 알림
        eventBus.emit('toast:show', {
            message: '예상치 못한 오류가 발생했습니다.',
            type: 'error',
            duration: 5000,
            action: {
                text: '신고하기',
                handler: () => this.showErrorReportDialog(errorData)
            }
        });
    }

    /**
     * 리소스 복구 처리
     * @param {HTMLElement} element - 실패한 엘리먼트
     * @param {Object} errorData - 에러 데이터
     * @private
     */
    handleResourceRecovery(element, errorData) {
        switch (element.tagName.toLowerCase()) {
            case 'script':
                this.retryScriptLoad(element);
                break;
            case 'link':
                this.retryStylesheetLoad(element);
                break;
            case 'img':
                this.retryImageLoad(element);
                break;
        }
    }

    /**
     * 스크립트 재로드
     * @param {HTMLScriptElement} script - 스크립트 엘리먼트
     * @private
     */
    retryScriptLoad(script) {
        const newScript = document.createElement('script');
        newScript.src = script.src;
        newScript.onload = () => {
            console.log('✅ 스크립트 재로드 성공:', script.src);
        };
        newScript.onerror = () => {
            console.error('❌ 스크립트 재로드 실패:', script.src);
        };
        
        script.parentNode.replaceChild(newScript, script);
    }

    /**
     * 스타일시트 재로드
     * @param {HTMLLinkElement} link - 링크 엘리먼트
     * @private
     */
    retryStylesheetLoad(link) {
        const newLink = document.createElement('link');
        newLink.rel = link.rel;
        newLink.href = link.href + '?retry=' + Date.now();
        newLink.onload = () => {
            console.log('✅ 스타일시트 재로드 성공:', link.href);
            link.remove();
        };
        
        document.head.appendChild(newLink);
    }

    /**
     * 이미지 재로드
     * @param {HTMLImageElement} img - 이미지 엘리먼트
     * @private
     */
    retryImageLoad(img) {
        const originalSrc = img.src;
        img.src = '';
        
        setTimeout(() => {
            img.src = originalSrc + '?retry=' + Date.now();
        }, 1000);
    }

    /**
     * 에러 히스토리에 추가
     * @param {Object} errorData - 에러 데이터
     * @private
     */
    addToHistory(errorData) {
        this.errorHistory.push(errorData);
        
        // 히스토리 크기 제한
        if (this.errorHistory.length > this.maxHistorySize) {
            this.errorHistory.shift();
        }
    }

    /**
     * 새로고침 다이얼로그 표시
     * @param {Object} errorData - 에러 데이터
     * @returns {Promise<boolean>} 확인 여부
     * @private
     */
    async showReloadDialog(errorData) {
        return new Promise((resolve) => {
            const modal = document.createElement('div');
            modal.className = 'error-modal';
            modal.innerHTML = `
                <div class="error-modal-content">
                    <h3>⚠️ 오류 발생</h3>
                    <p>애플리케이션에서 오류가 발생했습니다. 페이지를 새로고침하시겠습니까?</p>
                    <div class="error-details">
                        <strong>에러:</strong> ${errorData.message}
                    </div>
                    <div class="error-actions">
                        <button class="btn btn-secondary" id="cancel-reload">취소</button>
                        <button class="btn btn-primary" id="confirm-reload">새로고침</button>
                    </div>
                </div>
            `;
            
            document.body.appendChild(modal);
            
            modal.querySelector('#confirm-reload').onclick = () => {
                modal.remove();
                resolve(true);
            };
            
            modal.querySelector('#cancel-reload').onclick = () => {
                modal.remove();
                resolve(false);
            };
            
            // 10초 후 자동 확인
            setTimeout(() => {
                if (document.body.contains(modal)) {
                    modal.remove();
                    resolve(true);
                }
            }, 10000);
        });
    }

    /**
     * 에러 리포트 다이얼로그 표시
     * @param {Object} errorData - 에러 데이터
     * @private
     */
    showErrorReportDialog(errorData) {
        const modal = document.createElement('div');
        modal.className = 'error-report-modal';
        modal.innerHTML = `
            <div class="error-report-content">
                <h3>🐛 오류 신고</h3>
                <p>오류에 대한 추가 정보를 제공해주세요.</p>
                <textarea placeholder="오류 발생 전 수행한 작업을 설명해주세요..."></textarea>
                <div class="error-report-actions">
                    <button class="btn btn-secondary" id="cancel-report">취소</button>
                    <button class="btn btn-primary" id="send-report">신고하기</button>
                </div>
            </div>
        `;
        
        document.body.appendChild(modal);
        
        modal.querySelector('#send-report').onclick = () => {
            const description = modal.querySelector('textarea').value;
            this.sendErrorReport({ ...errorData, userDescription: description });
            modal.remove();
        };
        
        modal.querySelector('#cancel-report').onclick = () => {
            modal.remove();
        };
    }

    /**
     * 에러 리포트 전송
     * @param {Object} errorData - 에러 데이터
     * @private
     */
    async sendErrorReport(errorData) {
        try {
            // 실제 구현에서는 에러 리포팅 서비스로 전송
            console.log('📤 에러 리포트 전송:', errorData);
            
            // 여기서는 localStorage에 저장
            const reports = JSON.parse(localStorage.getItem('error_reports') || '[]');
            reports.push(errorData);
            localStorage.setItem('error_reports', JSON.stringify(reports.slice(-10)));
            
            eventBus.emit('toast:show', {
                message: '오류 신고가 전송되었습니다.',
                type: 'success',
                duration: 3000
            });
            
        } catch (error) {
            console.error('에러 리포트 전송 실패:', error);
        }
    }

    /**
     * 지연 함수
     * @param {number} ms - 밀리초
     * @returns {Promise<void>}
     * @private
     */
    delay(ms) {
        return new Promise(resolve => setTimeout(resolve, ms));
    }

    /**
     * 에러 핸들러 등록
     * @param {string} type - 에러 타입
     * @param {Function} handler - 핸들러 함수
     */
    registerErrorHandler(type, handler) {
        if (!this.errorHandlers.has(type)) {
            this.errorHandlers.set(type, []);
        }
        this.errorHandlers.get(type).push(handler);
    }

    /**
     * 에러 핸들러 제거
     * @param {string} type - 에러 타입
     * @param {Function} handler - 핸들러 함수
     */
    removeErrorHandler(type, handler) {
        const handlers = this.errorHandlers.get(type);
        if (handlers) {
            const index = handlers.indexOf(handler);
            if (index !== -1) {
                handlers.splice(index, 1);
            }
        }
    }

    /**
     * 에러 통계 가져오기
     * @returns {Object} 에러 통계
     */
    getErrorStats() {
        const stats = {
            total: this.errorHistory.length,
            byCategory: {},
            bySeverity: {},
            recentErrors: this.errorHistory.slice(-10),
            recoveryRate: 0
        };
        
        this.errorHistory.forEach(error => {
            // 카테고리별 통계
            stats.byCategory[error.category] = (stats.byCategory[error.category] || 0) + 1;
            
            // 심각도별 통계
            stats.bySeverity[error.severity] = (stats.bySeverity[error.severity] || 0) + 1;
        });
        
        // 복구율 계산
        const recoveredErrors = this.errorHistory.filter(error => error.recovered);
        stats.recoveryRate = this.errorHistory.length > 0 ? 
            (recoveredErrors.length / this.errorHistory.length * 100).toFixed(1) : 0;
        
        return stats;
    }

    /**
     * 에러 히스토리 클리어
     */
    clearErrorHistory() {
        this.errorHistory = [];
        this.recoveryAttempts.clear();
    }

    /**
     * 복구 전략 설정
     * @param {string} errorType - 에러 타입
     * @param {string} strategy - 전략
     */
    setRecoveryStrategy(errorType, strategy) {
        this.errorStrategies.set(errorType, strategy);
    }

    /**
     * 에러 바운더리 비활성화
     */
    disable() {
        // 이벤트 리스너 제거는 불가능하므로 플래그로 제어
        this.disabled = true;
    }

    /**
     * 에러 바운더리 활성화
     */
    enable() {
        this.disabled = false;
    }
}

// 전역 에러 바운더리 인스턴스
export const errorBoundary = new ErrorBoundary();

// 개발 모드에서 전역 접근 가능하게 설정
if (typeof window !== 'undefined' && process.env.NODE_ENV === 'development') {
    window.__ERROR_BOUNDARY__ = errorBoundary;
}
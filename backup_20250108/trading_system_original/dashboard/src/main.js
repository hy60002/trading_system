/**
 * @fileoverview 메인 엔트리 포인트
 * @description 대시보드 애플리케이션 초기화 및 실행
 */

// 코어 시스템 임포트
import { globalStore, loggingMiddleware, asyncMiddleware } from './core/Store.js';
import { eventBus } from './core/EventBus.js';
import { vdom } from './core/VirtualDOM.js';

// 서비스 임포트
import { webSocketService } from './services/WebSocketService.js';
import { apiService } from './services/ApiService.js';  
import { chartService } from './services/ChartService.js';

// 컴포넌트 임포트
import { Header } from './components/Header.js';
import { CapitalTracker } from './components/CapitalTracker.js';

// 유틸리티 임포트
import { PerformanceMonitor } from './utils/performance.js';
import { ErrorBoundary } from './utils/ErrorBoundary.js';
import { ServiceWorkerManager } from './utils/ServiceWorkerManager.js';

/**
 * 메인 대시보드 애플리케이션 클래스
 * @class DashboardApp
 */
class DashboardApp {
    constructor() {
        this.components = new Map();
        this.services = new Map();
        this.isInitialized = false;
        this.isDestroyed = false;
        this.startTime = Date.now();
        
        // 성능 모니터
        this.performanceMonitor = new PerformanceMonitor();
        
        // 에러 바운더리
        this.errorBoundary = new ErrorBoundary();
        
        // 서비스 워커 매니저
        this.serviceWorkerManager = new ServiceWorkerManager();
        
        // 애플리케이션 설정
        this.config = {
            enableVirtualDOM: true,
            enableServiceWorker: true,
            enablePerformanceMonitoring: true,
            autoConnect: true,
            debug: window.location.hostname === 'localhost' || window.location.hostname === '127.0.0.1'
        };

        this.initializeApp();
    }

    /**
     * 애플리케이션 초기화
     * @private
     */
    async initializeApp() {
        try {
            console.log('🚀 Bitget Trading Dashboard v3.0 초기화 시작...');
            
            // 에러 바운더리 설정
            this.setupErrorBoundary();
            
            // 코어 시스템 초기화
            await this.initializeCore();
            
            // 서비스 초기화
            await this.initializeServices();
            
            // 컴포넌트 초기화
            await this.initializeComponents();
            
            // 이벤트 리스너 설정
            this.setupEventListeners();
            
            // 성능 모니터링 시작
            if (this.config.enablePerformanceMonitoring) {
                this.performanceMonitor.start();
            }
            
            // 서비스 워커 등록
            if (this.config.enableServiceWorker) {
                await this.serviceWorkerManager.register();
            }
            
            // 자동 연결
            if (this.config.autoConnect) {
                await this.connect();
            }
            
            this.isInitialized = true;
            this.onInitialized();
            
            console.log(`✅ 대시보드 초기화 완료 (${Date.now() - this.startTime}ms)`);
            
        } catch (error) {
            console.error('❌ 대시보드 초기화 실패:', error);
            
            // 즉시 강제 표시 (초기화 실패 시)
            this.forceShowDashboard('initialization_error');
            
            // 에러 리포팅
            this.reportError(error, { type: 'initialization' });
            
            // 3초 후 재시도 옵션 제공
            setTimeout(() => {
                if (!this.isInitialized) {
                    this.showRetryOption(error);
                }
            }, 3000);
        }
    }

    /**
     * 에러 바운더리 설정
     * @private
     */
    setupErrorBoundary() {
        this.errorBoundary.onError = (error, errorInfo) => {
            console.error('🚨 애플리케이션 에러:', error, errorInfo);
            
            // 에러 정보를 스토어에 저장
            globalStore.dispatch({
                type: 'SET_SYSTEM_STATUS',
                payload: {
                    status: 'error',
                    errors: [error.message]
                }
            });
            
            // 에러 리포팅 (실제 구현에서는 외부 서비스로 전송)
            this.reportError(error, errorInfo);
        };

        // 전역 에러 핸들러
        window.addEventListener('error', (event) => {
            this.errorBoundary.handleError(event.error, {
                type: 'global',
                filename: event.filename,
                lineno: event.lineno,
                colno: event.colno
            });
        });

        window.addEventListener('unhandledrejection', (event) => {
            this.errorBoundary.handleError(event.reason, {
                type: 'promise',
                promise: event.promise
            });
        });
    }

    /**
     * 코어 시스템 초기화
     * @private
     */
    async initializeCore() {
        console.log('🔧 코어 시스템 초기화...');
        
        // 스토어 미들웨어 설정
        if (this.config.debug) {
            globalStore.use(loggingMiddleware);
        }
        globalStore.use(asyncMiddleware);
        
        // 초기 상태 설정
        globalStore.dispatch({
            type: 'SET_SYSTEM_STATUS',
            payload: {
                status: 'loading',
                websocketConnected: false,
                lastUpdate: null
            }
        });
        
        // 테마 초기화
        const savedTheme = localStorage.getItem('dashboard-theme') || 'dark';
        document.documentElement.setAttribute('data-theme', savedTheme);
        globalStore.dispatch({
            type: 'UPDATE_UI_STATE',
            payload: { theme: savedTheme }
        });
        
        console.log('✅ 코어 시스템 초기화 완료');
    }

    /**
     * 서비스 초기화
     * @private
     */
    async initializeServices() {
        console.log('🔌 서비스 초기화...');
        
        // API 서비스 설정
        this.services.set('api', apiService);
        
        // WebSocket 서비스 설정
        this.services.set('websocket', webSocketService);
        
        // 차트 서비스 설정
        this.services.set('charts', chartService);
        
        // 서비스 간 이벤트 연결
        this.connectServices();
        
        console.log('✅ 서비스 초기화 완료');
    }

    /**
     * 서비스 간 연결 설정
     * @private
     */
    connectServices() {
        // API 에러 시 WebSocket 재연결 시도
        eventBus.on('api:error', (data) => {
            if (data.error.status === 0) { // 네트워크 오류
                webSocketService.connect().catch(console.error);
            }
        });

        // WebSocket 연결 시 초기 데이터 로드
        eventBus.on('websocket:connected', async () => {
            try {
                await this.loadInitialData();
            } catch (error) {
                console.error('초기 데이터 로드 실패:', error);
            }
        });

        // WebSocket 데이터를 차트로 전달
        eventBus.on('websocket:price_update', (data) => {
            // 실시간 가격 차트 업데이트
            Object.entries(data).forEach(([symbol, price]) => {
                eventBus.emit(`chart:update:${symbol}`, price);
            });
        });
    }

    /**
     * 컴포넌트 초기화
     * @private
     */
    async initializeComponents() {
        console.log('🧩 컴포넌트 초기화...');
        
        try {
            // 헤더 컴포넌트
            const headerContainer = document.querySelector('.header');
            if (headerContainer) {
                const header = new Header(headerContainer);
                this.components.set('header', header);
                console.log('✅ Header 컴포넌트 초기화 완료');
            }
            
            // 자본 추적 컴포넌트
            const capitalTrackerContainer = document.querySelector('#capital-tracker-container');
            if (capitalTrackerContainer) {
                const capitalTracker = new CapitalTracker(capitalTrackerContainer);
                this.components.set('capitalTracker', capitalTracker);
                console.log('✅ CapitalTracker 컴포넌트 초기화 완료');
            }
            
            // 추가 컴포넌트들을 여기에 초기화...
            // const summaryCards = new SummaryCards('.summary-grid');
            // this.components.set('summaryCards', summaryCards);
            
            console.log('✅ 모든 컴포넌트 초기화 완료');
            
        } catch (error) {
            console.error('컴포넌트 초기화 실패:', error);
            throw error;
        }
    }

    /**
     * 이벤트 리스너 설정
     * @private
     */
    setupEventListeners() {
        // 브라우저 이벤트
        window.addEventListener('beforeunload', this.handleBeforeUnload.bind(this));
        window.addEventListener('visibilitychange', this.handleVisibilityChange.bind(this));
        
        // 애플리케이션 이벤트
        eventBus.on('dashboard:refresh_all', this.handleRefreshAll.bind(this));
        eventBus.on('dashboard:theme_change', this.handleThemeChange.bind(this));
        eventBus.on('dashboard:export_data', this.handleExportData.bind(this));
        
        // 컴포넌트 이벤트
        eventBus.on('component:error', this.handleComponentError.bind(this));
        
        // 성능 관련 이벤트
        eventBus.on('performance:warning', this.handlePerformanceWarning.bind(this));
        
        // 키보드 단축키
        document.addEventListener('keydown', this.handleKeyboardShortcuts.bind(this));
    }

    /**
     * 연결 시작
     * @returns {Promise<void>}
     */
    async connect() {
        console.log('🔗 서비스 연결 시작...');
        
        try {
            // WebSocket 연결
            await webSocketService.connect();
            
            // 채널 구독
            this.subscribeToChannels();
            
            // 초기 데이터 로드
            await this.loadInitialData();
            
            // 시스템 상태 업데이트
            globalStore.dispatch({
                type: 'SET_SYSTEM_STATUS',
                payload: {
                    status: 'running',
                    lastUpdate: Date.now()
                }
            });
            
            console.log('✅ 모든 서비스 연결 완료');
            
        } catch (error) {
            console.error('서비스 연결 실패:', error);
            this.handleConnectionError(error);
        }
    }

    /**
     * 채널 구독
     * @private
     */
    subscribeToChannels() {
        // 가격 업데이트 구독
        webSocketService.subscribe('prices', {
            symbols: ['BTCUSDT', 'ETHUSDT', 'XRPUSDT']
        });
        
        // 포지션 업데이트 구독
        webSocketService.subscribe('positions');
        
        // 거래 실행 구독
        webSocketService.subscribe('trades');
        
        // 시스템 상태 구독
        webSocketService.subscribe('system_status');
    }

    /**
     * 초기 데이터 로드
     * @private
     */
    async loadInitialData() {
        console.log('📊 초기 데이터 로드...');
        
        try {
            // 병렬로 데이터 로드
            const [
                dashboardData,
                positions,
                trades,
                balance,
                notifications
            ] = await Promise.all([
                apiService.getDashboardData(),
                apiService.getPositions(),
                apiService.getTradeHistory({ limit: 100 }),
                apiService.getBalance(),
                apiService.getNotifications()
            ]);

            // 스토어에 데이터 저장
            globalStore.dispatch({
                type: 'UPDATE_POSITIONS',
                payload: positions
            });

            globalStore.dispatch({
                type: 'UPDATE_BALANCE',
                payload: balance
            });

            if (notifications && notifications.notifications) {
                notifications.notifications.forEach(notification => {
                    globalStore.dispatch({
                        type: 'ADD_NOTIFICATION',
                        payload: notification
                    });
                });
            }

            console.log('✅ 초기 데이터 로드 완료');
            
        } catch (error) {
            console.error('초기 데이터 로드 실패:', error);
            // 에러가 발생해도 애플리케이션은 계속 실행
        }
    }

    // 이벤트 핸들러들

    /**
     * 페이지 언로드 전 처리
     * @param {BeforeUnloadEvent} event - 이벤트
     * @private
     */
    handleBeforeUnload(event) {
        if (this.hasUnsavedChanges()) {
            const message = '저장되지 않은 변경사항이 있습니다. 정말 나가시겠습니까?';
            event.returnValue = message;
            return message;
        }
        
        // 정리 작업
        this.cleanup();
    }

    /**
     * 가시성 변경 처리
     * @param {Event} event - 이벤트
     * @private
     */
    handleVisibilityChange(event) {
        if (document.hidden) {
            // 페이지가 숨겨짐 - 리소스 절약
            this.pauseUpdates();
        } else {
            // 페이지가 다시 보임 - 업데이트 재개
            this.resumeUpdates();
        }
    }

    /**
     * 전체 새로고침 처리
     * @private
     */
    async handleRefreshAll() {
        console.log('🔄 전체 데이터 새로고침...');
        
        try {
            await this.loadInitialData();
            
            // 모든 컴포넌트에 새로고침 이벤트 전달
            this.components.forEach(component => {
                if (typeof component.refresh === 'function') {
                    component.refresh();
                }
            });
            
            eventBus.emit('toast:show', {
                message: '데이터 새로고침 완료',
                type: 'success',
                duration: 2000
            });
            
        } catch (error) {
            console.error('전체 새로고침 실패:', error);
            eventBus.emit('toast:show', {
                message: '새로고침 실패',
                type: 'error',
                duration: 3000
            });
        }
    }

    /**
     * 테마 변경 처리
     * @param {Object} data - 테마 데이터
     * @private
     */
    handleThemeChange(data) {
        const { theme } = data;
        document.documentElement.setAttribute('data-theme', theme);
        localStorage.setItem('dashboard-theme', theme);
        
        // 차트 테마 업데이트
        chartService.updateTheme(theme);
    }

    /**
     * 데이터 내보내기 처리
     * @param {Object} data - 내보내기 데이터
     * @private
     */
    async handleExportData(data) {
        try {
            const { type, format, dateRange } = data;
            
            // 데이터 수집
            let exportData;
            switch (type) {
                case 'trades':
                    exportData = await apiService.getTradeHistory(dateRange);
                    break;
                case 'positions':
                    exportData = await apiService.getPositions();
                    break;
                default:
                    exportData = await apiService.getDashboardData();
            }
            
            // 파일 생성 및 다운로드
            this.downloadData(exportData, `${type}_${Date.now()}.${format}`);
            
        } catch (error) {
            console.error('데이터 내보내기 실패:', error);
            eventBus.emit('toast:show', {
                message: '데이터 내보내기 실패',
                type: 'error'
            });
        }
    }

    /**
     * 컴포넌트 에러 처리
     * @param {Object} data - 에러 데이터
     * @private
     */
    handleComponentError(data) {
        const { componentName, error, context } = data;
        console.error(`컴포넌트 에러 (${componentName}):`, error);
        
        // 에러 복구 시도
        this.attemptErrorRecovery(data);
    }

    /**
     * 성능 경고 처리
     * @param {Object} data - 성능 데이터
     * @private
     */
    handlePerformanceWarning(data) {
        console.warn('성능 경고:', data);
        
        if (data.type === 'memory') {
            this.optimizeMemoryUsage();
        } else if (data.type === 'render') {
            this.optimizeRenderPerformance();
        }
    }

    /**
     * 키보드 단축키 처리
     * @param {KeyboardEvent} event - 키보드 이벤트
     * @private
     */
    handleKeyboardShortcuts(event) {
        // Ctrl/Cmd + K: 명령어 팔레트
        if ((event.ctrlKey || event.metaKey) && event.key === 'k') {
            event.preventDefault();
            eventBus.emit('command_palette:toggle');
        }
        
        // F5: 새로고침 (기본 동작 방지하고 커스텀 새로고침)
        if (event.key === 'F5') {
            event.preventDefault();
            this.handleRefreshAll();
        }
        
        // Escape: 모달/오버레이 닫기
        if (event.key === 'Escape') {
            eventBus.emit('overlay:close');
        }
    }

    // 유틸리티 메서드들

    /**
     * 저장되지 않은 변경사항 확인
     * @returns {boolean} 변경사항 여부
     * @private
     */
    hasUnsavedChanges() {
        // 실제 구현에서는 폼 데이터 등을 확인
        return false;
    }

    /**
     * 업데이트 일시 정지
     * @private
     */
    pauseUpdates() {
        webSocketService.disconnect();
        this.performanceMonitor.pause();
    }

    /**
     * 업데이트 재개
     * @private
     */
    resumeUpdates() {
        webSocketService.connect().catch(console.error);
        this.performanceMonitor.resume();
        this.handleRefreshAll();
    }

    /**
     * 에러 복구 시도
     * @param {Object} errorData - 에러 데이터
     * @private
     */
    attemptErrorRecovery(errorData) {
        const { componentId, componentName } = errorData;
        
        // 컴포넌트 재시작 시도
        const component = this.components.get(componentName.toLowerCase());
        if (component && typeof component.restart === 'function') {
            try {
                component.restart();
                console.log(`✅ ${componentName} 컴포넌트 복구 성공`);
            } catch (error) {
                console.error(`❌ ${componentName} 컴포넌트 복구 실패:`, error);
            }
        }
    }

    /**
     * 메모리 사용량 최적화
     * @private
     */
    optimizeMemoryUsage() {
        // 차트 캐시 정리
        chartService.clearCache();
        
        // API 캐시 정리
        apiService.clearCache();
        
        // 가비지 컬렉션 힌트
        if (window.gc) {
            window.gc();
        }
        
        console.log('🧹 메모리 최적화 완료');
    }

    /**
     * 강제로 대시보드 표시 (긴급상황용)
     * @param {string} reason - 강제 표시 이유
     * @private
     */
    forceShowDashboard(reason = 'unknown') {
        console.log(`🚨 강제 대시보드 표시 - 이유: ${reason}`);
        
        try {
            // 로딩 화면 숨기기
            const loadingScreen = document.querySelector('.loading-screen');
            if (loadingScreen) {
                loadingScreen.style.display = 'none';
            }
            
            // 컨테이너 보이기
            const container = document.querySelector('.container');
            if (container) {
                container.style.display = 'block';
            }
            
            // body에 로드 완료 클래스 추가
            document.body.classList.add('app-loaded');
            
            // 에러 상태 표시
            this.showEmergencyMode(reason);
            
        } catch (error) {
            console.error('❌ 강제 표시 중 오류:', error);
            // 최후의 수단: 간단한 HTML 표시
            this.showMinimalDashboard();
        }
    }
    
    /**
     * 긴급 모드 표시
     * @param {string} reason - 긴급 모드 원인
     * @private
     */
    showEmergencyMode(reason) {
        const container = document.querySelector('.container');
        if (!container) return;
        
        // 에러 배너 추가
        const errorBanner = document.createElement('div');
        errorBanner.style.cssText = `
            background: linear-gradient(135deg, #ff6b6b, #ee5a24);
            color: white;
            padding: 1rem;
            margin: 1rem 0;
            border-radius: 8px;
            text-align: center;
            box-shadow: 0 4px 12px rgba(255, 107, 107, 0.3);
        `;
        
        const reasonTexts = {
            'initialization_error': '초기화 오류 발생',
            'module_timeout': '모듈 로드 시간 초과',
            'module_error': '모듈 로드 실패',
            'no_module_support': 'ES6 모듈 미지원',
            'timeout': '로딩 시간 초과',
            'critical_timeout': '심각한 로딩 지연'
        };
        
        errorBanner.innerHTML = `
            <h3>⚠️ 긴급 모드</h3>
            <p><strong>원인:</strong> ${reasonTexts[reason] || reason}</p>
            <p>기본 기능만 사용 가능합니다. 새로고침을 시도해보세요.</p>
            <div style="margin-top: 1rem;">
                <button onclick="window.location.reload()" style="background: white; color: #ee5a24; border: none; padding: 0.5rem 1rem; border-radius: 4px; cursor: pointer; margin-right: 0.5rem; font-weight: bold;">
                    🔄 새로고침
                </button>
                <button onclick="window.open('/simple_dashboard.html', '_blank')" style="background: rgba(255,255,255,0.2); color: white; border: 1px solid white; padding: 0.5rem 1rem; border-radius: 4px; cursor: pointer;">
                    📱 간단 대시보드
                </button>
            </div>
        `;
        
        container.insertBefore(errorBanner, container.firstChild);
    }
    
    /**
     * 최소한의 대시보드 표시 (최후의 수단)
     * @private
     */
    showMinimalDashboard() {
        document.body.innerHTML = `
            <div style="padding: 2rem; text-align: center; font-family: 'Inter', sans-serif;">
                <h1 style="color: #333;">🚨 시스템 오류</h1>
                <p>대시보드를 로드할 수 없습니다.</p>
                <button onclick="location.reload()" style="background: #007bff; color: white; border: none; padding: 1rem 2rem; border-radius: 4px; cursor: pointer; font-size: 1rem; margin: 1rem;">
                    새로고침
                </button>
                <a href="/simple_dashboard.html" style="background: #6c757d; color: white; text-decoration: none; padding: 1rem 2rem; border-radius: 4px; display: inline-block; margin: 1rem;">
                    간단 대시보드
                </a>
            </div>
        `;
    }
    
    /**
     * 재시도 옵션 표시
     * @param {Error} error - 발생한 오류
     * @private
     */
    showRetryOption(error) {
        const container = document.querySelector('.container');
        if (!container) return;
        
        const retryBanner = document.createElement('div');
        retryBanner.style.cssText = `
            background: #ffc107;
            color: #212529;
            padding: 1rem;
            margin: 1rem 0;
            border-radius: 8px;
            text-align: center;
            border-left: 4px solid #ff9800;
        `;
        
        retryBanner.innerHTML = `
            <p><strong>💡 시스템을 다시 시도할 수 있습니다</strong></p>
            <button onclick="window.dashboardApp?.restart()" style="background: #28a745; color: white; border: none; padding: 0.5rem 1rem; border-radius: 4px; cursor: pointer; margin-right: 0.5rem;">
                🔄 재시도
            </button>
            <button onclick="this.parentElement.remove()" style="background: #6c757d; color: white; border: none; padding: 0.5rem 1rem; border-radius: 4px; cursor: pointer;">
                ✕ 닫기
            </button>
        `;
        
        container.insertBefore(retryBanner, container.firstChild);
    }


    /**
     * 렌더링 성능 최적화
     * @private
     */
    optimizeRenderPerformance() {
        // 컴포넌트 업데이트 빈도 조절
        this.components.forEach(component => {
            if (typeof component.throttleUpdates === 'function') {
                component.throttleUpdates(true);
            }
        });
        
        console.log('⚡ 렌더링 성능 최적화 완료');
    }

    /**
     * 데이터 다운로드
     * @param {Object} data - 데이터
     * @param {string} filename - 파일명
     * @private
     */
    downloadData(data, filename) {
        const jsonData = JSON.stringify(data, null, 2);
        const blob = new Blob([jsonData], { type: 'application/json' });
        const url = URL.createObjectURL(blob);
        
        const a = document.createElement('a');
        a.href = url;
        a.download = filename;
        document.body.appendChild(a);
        a.click();
        document.body.removeChild(a);
        URL.revokeObjectURL(url);
    }

    /**
     * 에러 리포팅
     * @param {Error} error - 에러
     * @param {Object} errorInfo - 에러 정보
     * @private
     */
    reportError(error, errorInfo) {
        // 실제 구현에서는 Sentry, LogRocket 등으로 전송
        const errorReport = {
            message: error.message,
            stack: error.stack,
            errorInfo,
            userAgent: navigator.userAgent,
            timestamp: Date.now(),
            url: window.location.href,
            userId: 'anonymous' // 실제로는 사용자 ID
        };
        
        console.log('📤 에러 리포트:', errorReport);
    }

    /**
     * 초기화 에러 처리
     * @param {Error} error - 에러
     * @private
     */
    handleInitializationError(error) {
        // 에러 화면 표시
        document.body.innerHTML = `
            <div class="initialization-error">
                <div class="error-container">
                    <h1>⚠️ 초기화 실패</h1>
                    <p>대시보드를 초기화하는 중 오류가 발생했습니다.</p>
                    <details>
                        <summary>에러 세부사항</summary>
                        <pre>${error.stack}</pre>
                    </details>
                    <button onclick="location.reload()">새로고침</button>
                </div>
            </div>
        `;

        // 에러 리포팅
        this.reportError(error, { type: 'initialization' });
    }

    /**
     * 연결 에러 처리
     * @param {Error} error - 에러
     * @private
     */
    handleConnectionError(error) {
        globalStore.dispatch({
            type: 'SET_SYSTEM_STATUS',
            payload: {
                status: 'error',
                errors: [error.message]
            }
        });

        eventBus.emit('toast:show', {
            message: '서버 연결에 실패했습니다',
            type: 'error',
            duration: 5000
        });
    }

    /**
     * 정리 작업
     * @private
     */
    cleanup() {
        if (this.isDestroyed) return;
        
        console.log('🧹 애플리케이션 정리 작업...');
        
        // 컴포넌트 정리
        this.components.forEach(component => {
            if (typeof component.destroy === 'function') {
                component.destroy();
            }
        });
        this.components.clear();
        
        // 서비스 정리
        webSocketService.disconnect();
        chartService.destroyAllCharts();
        
        // 성능 모니터 중지
        this.performanceMonitor.stop();
        
        // 이벤트 리스너 정리
        eventBus.removeAllListeners();
        
        this.isDestroyed = true;
        console.log('✅ 정리 작업 완료');
    }

    /**
     * 애플리케이션 재시작
     */
    async restart() {
        console.log('🔄 애플리케이션 재시작...');
        
        this.cleanup();
        
        // 잠시 대기
        await new Promise(resolve => setTimeout(resolve, 1000));
        
        // 재초기화
        this.isInitialized = false;
        this.isDestroyed = false;
        await this.initializeApp();
    }

    /**
     * 초기화 완료 후 처리
     * @private
     */
    onInitialized() {
        // 로딩 화면 제거
        const loadingScreen = document.querySelector('.loading-screen');
        if (loadingScreen) {
            loadingScreen.classList.add('fade-out');
            setTimeout(() => {
                loadingScreen.remove();
            }, 500);
        }
        
        // 애플리케이션 표시
        document.body.classList.add('app-loaded');
        
        // 초기화 완료 이벤트
        eventBus.emit('app:initialized', {
            timestamp: Date.now(),
            loadTime: Date.now() - this.startTime
        });

        // 환영 메시지
        eventBus.emit('toast:show', {
            message: '대시보드가 준비되었습니다',
            type: 'success',
            duration: 3000
        });
    }

    /**
     * 애플리케이션 상태 가져오기
     * @returns {Object} 상태 정보
     */
    getStatus() {
        return {
            isInitialized: this.isInitialized,
            isDestroyed: this.isDestroyed,
            startTime: this.startTime,
            components: Array.from(this.components.keys()),
            services: Array.from(this.services.keys()),
            performance: this.performanceMonitor.getMetrics(),
            config: this.config
        };
    }
}

// DOM 로드 완료 후 애플리케이션 시작
document.addEventListener('DOMContentLoaded', () => {
    console.log('📱 DOM 로드 완료 - 대시보드 시작');
    
    // 전역 애플리케이션 인스턴스 생성
    window.dashboardApp = new DashboardApp();
    
    // 개발 모드에서 디버깅 정보 제공 (localhost 또는 127.0.0.1에서만)
    const isDevelopment = window.location.hostname === 'localhost' || window.location.hostname === '127.0.0.1';
    if (isDevelopment) {
        window.__DASHBOARD_DEBUG__ = {
            app: window.dashboardApp,
            store: globalStore,
            eventBus,
            services: {
                websocket: webSocketService,
                api: apiService,
                charts: chartService
            }
        };
        
        console.log('🔧 개발 모드: window.__DASHBOARD_DEBUG__에서 디버깅 정보 확인 가능');
    }
});

// 모듈 내보내기
export { DashboardApp };
/**
 * @fileoverview 헤더 컴포넌트
 * @description 대시보드 상단 헤더 관리
 */

import { BaseComponent } from './BaseComponent.js';
import { eventBus } from '../core/EventBus.js';

/**
 * 헤더 컴포넌트 클래스
 * @class Header
 * @extends BaseComponent
 */
export class Header extends BaseComponent {
    /**
     * @param {HTMLElement|string} container - 컨테이너
     * @param {Object} props - 속성
     */
    constructor(container, props = {}) {
        super(container, props, {
            subscribeToStore: true,
            enableVirtualDOM: true
        });
    }

    /**
     * 초기 상태 반환
     * @returns {Object} 초기 상태
     * @protected
     */
    getInitialState() {
        return {
            systemStatus: 'loading',
            websocketStatus: 'disconnected',
            lastUpdate: null,
            theme: localStorage.getItem('dashboard-theme') || 'dark',
            isRefreshing: false,
            notifications: {
                count: 0,
                hasUnread: false
            }
        };
    }

    /**
     * 스토어 선택자 반환
     * @returns {Array<string>} 선택자 배열
     * @protected
     */
    getStoreSelectors() {
        return [
            ['system', 'status'],
            ['system', 'websocketConnected'],
            ['system', 'lastUpdate'],
            ['ui', 'theme'],
            ['ui', 'notifications']
        ];
    }

    /**
     * 스토어 업데이트 처리
     * @param {*} selectedState - 선택된 상태
     * @param {Object} fullState - 전체 상태
     * @param {Object} action - 액션
     * @param {Array} selector - 선택자
     * @protected
     */
    onStoreUpdate(selectedState, fullState, action, selector) {
        const selectorKey = selector.join('.');
        
        switch (selectorKey) {
            case 'system.status':
                this.setState({ systemStatus: selectedState });
                break;
            case 'system.websocketConnected':
                this.setState({ 
                    websocketStatus: selectedState ? 'connected' : 'disconnected' 
                });
                break;
            case 'system.lastUpdate':
                this.setState({ lastUpdate: selectedState });
                break;
            case 'ui.theme':
                this.setState({ theme: selectedState });
                break;
            case 'ui.notifications':
                this.updateNotificationState(selectedState);
                break;
        }
    }

    /**
     * 알림 상태 업데이트
     * @param {Array} notifications - 알림 목록
     * @private
     */
    updateNotificationState(notifications) {
        const count = notifications.length;
        const hasUnread = notifications.some(n => !n.read);
        
        this.setState({
            notifications: { count, hasUnread }
        });
    }

    /**
     * 커스텀 이벤트 리스너 설정
     * @protected
     */
    setupCustomEventListeners() {
        // WebSocket 상태 변경 이벤트
        eventBus.on('websocket:connected', this.handleWebSocketConnected);
        eventBus.on('websocket:disconnected', this.handleWebSocketDisconnected);
        eventBus.on('websocket:error', this.handleWebSocketError);
        
        // API 상태 이벤트
        eventBus.on('api:error', this.handleApiError);
        eventBus.on('api:offline', this.handleOffline);
        eventBus.on('api:online', this.handleOnline);
        
        // 알림 이벤트
        eventBus.on('notification:new', this.handleNewNotification);
    }

    /**
     * 이벤트 핸들러 바인딩
     * @protected
     */
    bindEventHandlers() {
        // 테마 토글 버튼
        const themeToggle = this.$('.theme-toggle[data-action="theme"]');
        if (themeToggle) {
            themeToggle.addEventListener('click', this.handleThemeToggle);
        }

        // 새로고침 버튼
        const refreshButton = this.$('.theme-toggle[data-action="refresh"]');
        if (refreshButton) {
            refreshButton.addEventListener('click', this.handleRefresh);
        }

        // 알림 버튼
        const notificationButton = this.$('.notification-button');
        if (notificationButton) {
            notificationButton.addEventListener('click', this.handleNotificationClick);
        }

        // 시스템 상태 클릭
        const systemStatus = this.$('.system-status');
        if (systemStatus) {
            systemStatus.addEventListener('click', this.handleSystemStatusClick);
        }
    }

    /**
     * 템플릿 반환
     * @returns {string} HTML 템플릿
     * @protected
     */
    template() {
        const { systemStatus, websocketStatus, lastUpdate, theme, isRefreshing, notifications } = this.state;
        
        return `
            <div class="header-content">
                <div class="header-title">
                    <i class="fas fa-rocket"></i>
                    <span class="title-text">Bitget Trading System v3.0</span>
                    <div class="build-info">
                        <span class="version">Build ${this.getBuildVersion()}</span>
                        <span class="environment ${this.getEnvironment()}">${this.getEnvironment().toUpperCase()}</span>
                    </div>
                </div>
                
                <div class="header-controls">
                    <!-- 시스템 상태 -->
                    <div class="status-indicator system-status" data-status="${systemStatus}">
                        <div class="status-dot ${this.getStatusDotClass(systemStatus)}"></div>
                        <span class="status-text">${this.getStatusText(systemStatus)}</span>
                        <div class="status-tooltip">
                            시스템 상태: ${systemStatus}
                            <br>클릭하여 상세 정보 보기
                        </div>
                    </div>
                    
                    <!-- WebSocket 상태 -->
                    <div class="status-indicator websocket-status" data-status="${websocketStatus}">
                        <i class="fas fa-wifi ${this.getWebSocketIconClass(websocketStatus)}"></i>
                        <span class="status-text">${this.getWebSocketStatusText(websocketStatus)}</span>
                        <div class="connection-quality ${this.getConnectionQuality()}"></div>
                        <div class="status-tooltip">
                            실시간 연결: ${websocketStatus}
                            <br>품질: ${this.getConnectionQuality()}
                        </div>
                    </div>
                    
                    <!-- 마지막 업데이트 -->
                    <div class="status-indicator last-update">
                        <i class="fas fa-clock"></i>
                        <span class="status-text">${this.formatLastUpdate(lastUpdate)}</span>
                        <div class="update-indicator ${this.getUpdateIndicatorClass()}"></div>
                        <div class="status-tooltip">
                            마지막 업데이트: ${this.formatLastUpdateFull(lastUpdate)}
                        </div>
                    </div>
                    
                    <!-- 알림 버튼 -->
                    <button class="header-button notification-button ${notifications.hasUnread ? 'has-unread' : ''}" 
                            data-action="notifications" 
                            aria-label="알림 (${notifications.count}개)">
                        <i class="fas fa-bell"></i>
                        ${notifications.count > 0 ? `<span class="notification-badge">${notifications.count > 99 ? '99+' : notifications.count}</span>` : ''}
                        <div class="notification-preview">
                            ${this.renderNotificationPreview()}
                        </div>
                    </button>
                    
                    <!-- 테마 토글 -->
                    <button class="header-button theme-toggle" 
                            data-action="theme" 
                            aria-label="테마 변경">
                        <i class="fas ${this.getThemeIcon(theme)}"></i>
                        <span class="button-text">${this.getThemeText(theme)}</span>
                        <div class="theme-options">
                            <div class="theme-option" data-theme="dark">
                                <i class="fas fa-moon"></i> 다크
                            </div>
                            <div class="theme-option" data-theme="light">
                                <i class="fas fa-sun"></i> 라이트
                            </div>
                            <div class="theme-option" data-theme="auto">
                                <i class="fas fa-adjust"></i> 자동
                            </div>
                        </div>
                    </button>
                    
                    <!-- 새로고침 버튼 -->
                    <button class="header-button refresh-button ${isRefreshing ? 'refreshing' : ''}" 
                            data-action="refresh" 
                            aria-label="새로고침"
                            ${isRefreshing ? 'disabled' : ''}>
                        <i class="fas fa-sync-alt ${isRefreshing ? 'fa-spin' : ''}"></i>
                        <span class="button-text">새로고침</span>
                        <div class="refresh-tooltip">
                            ${isRefreshing ? '데이터 새로고침 중...' : '모든 데이터 새로고침'}
                        </div>
                    </button>
                    
                    <!-- 추가 메뉴 -->
                    <div class="header-menu">
                        <button class="header-button menu-toggle" aria-label="메뉴">
                            <i class="fas fa-ellipsis-v"></i>
                        </button>
                        <div class="menu-dropdown">
                            <div class="menu-item" data-action="settings">
                                <i class="fas fa-cog"></i> 설정
                            </div>
                            <div class="menu-item" data-action="help">
                                <i class="fas fa-question-circle"></i> 도움말
                            </div>
                            <div class="menu-item" data-action="about">
                                <i class="fas fa-info-circle"></i> 정보
                            </div>
                            <div class="menu-divider"></div>
                            <div class="menu-item" data-action="debug" ${this.getEnvironment() === 'development' ? '' : 'style="display: none;"'}>
                                <i class="fas fa-bug"></i> 디버그
                            </div>
                        </div>
                    </div>
                </div>
            </div>
            
            <!-- 진행률 바 -->
            <div class="progress-bar ${this.shouldShowProgress() ? 'visible' : ''}">
                <div class="progress-fill" style="width: ${this.getProgressPercentage()}%"></div>
            </div>
        `;
    }

    // 이벤트 핸들러들

    /**
     * 테마 토글 핸들러
     * @param {Event} event - 클릭 이벤트
     * @private
     */
    handleThemeToggle(event) {
        event.preventDefault();
        
        const currentTheme = this.state.theme;
        const themes = ['dark', 'light', 'auto'];
        const currentIndex = themes.indexOf(currentTheme);
        const nextTheme = themes[(currentIndex + 1) % themes.length];
        
        this.changeTheme(nextTheme);
    }

    /**
     * 새로고침 핸들러
     * @param {Event} event - 클릭 이벤트
     * @private
     */
    async handleRefresh(event) {
        event.preventDefault();
        
        if (this.state.isRefreshing) return;
        
        this.setState({ isRefreshing: true });
        
        try {
            await this.performRefresh();
            this.showRefreshSuccess();
        } catch (error) {
            console.error('새로고침 실패:', error);
            this.showRefreshError(error);
        } finally {
            // 최소 1초는 로딩 상태 유지 (UX)
            setTimeout(() => {
                this.setState({ isRefreshing: false });
            }, 1000);
        }
    }

    /**
     * 알림 클릭 핸들러
     * @param {Event} event - 클릭 이벤트
     * @private
     */
    handleNotificationClick(event) {
        event.preventDefault();
        this.emit('notifications:toggle');
    }

    /**
     * 시스템 상태 클릭 핸들러
     * @param {Event} event - 클릭 이벤트
     * @private
     */
    handleSystemStatusClick(event) {
        event.preventDefault();
        this.emit('system_status:show');
    }

    /**
     * WebSocket 연결 핸들러
     * @param {Object} data - 이벤트 데이터
     * @private
     */
    handleWebSocketConnected(data) {
        this.setState({ websocketStatus: 'connected' });
        this.showConnectionNotification('WebSocket 연결됨', 'success');
    }

    /**
     * WebSocket 연결 해제 핸들러
     * @param {Object} data - 이벤트 데이터
     * @private
     */
    handleWebSocketDisconnected(data) {
        this.setState({ websocketStatus: 'disconnected' });
        this.showConnectionNotification('WebSocket 연결 해제됨', 'warning');
    }

    /**
     * WebSocket 에러 핸들러
     * @param {Object} data - 이벤트 데이터
     * @private
     */
    handleWebSocketError(data) {
        this.setState({ websocketStatus: 'error' });
        this.showConnectionNotification('WebSocket 오류 발생', 'error');
    }

    /**
     * API 에러 핸들러
     * @param {Object} data - 이벤트 데이터
     * @private
     */
    handleApiError(data) {
        if (data.error.status >= 500) {
            this.showConnectionNotification('서버 오류 발생', 'error');
        }
    }

    /**
     * 오프라인 핸들러
     * @private
     */
    handleOffline() {
        this.showConnectionNotification('오프라인 모드', 'warning');
    }

    /**
     * 온라인 핸들러
     * @private
     */
    handleOnline() {
        this.showConnectionNotification('온라인 복구됨', 'success');
    }

    /**
     * 새 알림 핸들러
     * @param {Object} data - 알림 데이터
     * @private
     */
    handleNewNotification(data) {
        // 알림 애니메이션 효과
        const notificationButton = this.$('.notification-button');
        if (notificationButton) {
            notificationButton.classList.add('new-notification');
            setTimeout(() => {
                notificationButton.classList.remove('new-notification');
            }, 2000);
        }
    }

    // 유틸리티 메서드들

    /**
     * 테마 변경
     * @param {string} theme - 새로운 테마
     * @private
     */
    changeTheme(theme) {
        document.documentElement.setAttribute('data-theme', theme);
        localStorage.setItem('dashboard-theme', theme);
        
        this.setState({ theme });
        this.dispatch({
            type: 'UPDATE_UI_STATE',
            payload: { theme }
        });
        
        this.emit('theme:changed', { theme });
    }

    /**
     * 새로고침 수행
     * @returns {Promise<void>}
     * @private
     */
    async performRefresh() {
        // 모든 데이터 새로고침 이벤트 발생
        eventBus.emit('dashboard:refresh_all');
        
        // 잠시 대기 (실제 새로고침 시뮬레이션)
        await new Promise(resolve => setTimeout(resolve, 2000));
    }

    /**
     * 새로고침 성공 알림
     * @private
     */
    showRefreshSuccess() {
        this.showConnectionNotification('데이터 새로고침 완료', 'success');
    }

    /**
     * 새로고침 실패 알림
     * @param {Error} error - 에러
     * @private
     */
    showRefreshError(error) {
        this.showConnectionNotification('새로고침 실패', 'error');
    }

    /**
     * 연결 알림 표시
     * @param {string} message - 메시지
     * @param {string} type - 타입
     * @private
     */
    showConnectionNotification(message, type) {
        eventBus.emit('toast:show', {
            message,
            type,
            duration: 3000
        });
    }

    /**
     * 빌드 버전 가져오기
     * @returns {string} 빌드 버전
     * @private
     */
    getBuildVersion() {
        return process.env.BUILD_VERSION || '3.0.0';
    }

    /**
     * 환경 가져오기
     * @returns {string} 환경
     * @private
     */
    getEnvironment() {
        return process.env.NODE_ENV || 'production';
    }

    /**
     * 상태 점 클래스 가져오기
     * @param {string} status - 상태
     * @returns {string} CSS 클래스
     * @private
     */
    getStatusDotClass(status) {
        const classes = {
            running: 'success',
            loading: 'warning',
            error: 'error',
            stopped: 'neutral'
        };
        return classes[status] || 'neutral';
    }

    /**
     * 상태 텍스트 가져오기
     * @param {string} status - 상태
     * @returns {string} 상태 텍스트
     * @private
     */
    getStatusText(status) {
        const texts = {
            running: '실행 중',
            loading: '로딩 중',
            error: '오류',
            stopped: '중지됨'
        };
        return texts[status] || '알 수 없음';
    }

    /**
     * WebSocket 아이콘 클래스 가져오기
     * @param {string} status - 상태
     * @returns {string} CSS 클래스
     * @private
     */
    getWebSocketIconClass(status) {
        const classes = {
            connected: 'text-success',
            disconnected: 'text-warning',
            error: 'text-error'
        };
        return classes[status] || 'text-muted';
    }

    /**
     * WebSocket 상태 텍스트 가져오기
     * @param {string} status - 상태
     * @returns {string} 상태 텍스트
     * @private
     */
    getWebSocketStatusText(status) {
        const texts = {
            connected: '연결됨',
            disconnected: '연결 해제',
            error: '오류'
        };
        return texts[status] || '알 수 없음';
    }

    /**
     * 연결 품질 가져오기
     * @returns {string} 연결 품질
     * @private
     */
    getConnectionQuality() {
        // 실제로는 지연 시간 등을 기반으로 계산
        const { websocketStatus } = this.state;
        if (websocketStatus === 'connected') return 'excellent';
        if (websocketStatus === 'disconnected') return 'poor';
        return 'unknown';
    }

    /**
     * 마지막 업데이트 포맷
     * @param {number|null} timestamp - 타임스탬프
     * @returns {string} 포맷된 시간
     * @private
     */
    formatLastUpdate(timestamp) {
        if (!timestamp) return '-';
        
        const now = Date.now();
        const diff = now - timestamp;
        
        if (diff < 60000) return '방금 전';
        if (diff < 3600000) return `${Math.floor(diff / 60000)}분 전`;
        if (diff < 86400000) return `${Math.floor(diff / 3600000)}시간 전`;
        return `${Math.floor(diff / 86400000)}일 전`;
    }

    /**
     * 마지막 업데이트 전체 포맷
     * @param {number|null} timestamp - 타임스탬프
     * @returns {string} 포맷된 시간
     * @private
     */
    formatLastUpdateFull(timestamp) {
        if (!timestamp) return '업데이트 없음';
        return new Date(timestamp).toLocaleString();
    }

    /**
     * 업데이트 인디케이터 클래스 가져오기
     * @returns {string} CSS 클래스
     * @private
     */
    getUpdateIndicatorClass() {
        const { lastUpdate } = this.state;
        if (!lastUpdate) return 'stale';
        
        const diff = Date.now() - lastUpdate;
        if (diff < 30000) return 'fresh';
        if (diff < 120000) return 'recent';
        return 'stale';
    }

    /**
     * 테마 아이콘 가져오기
     * @param {string} theme - 테마
     * @returns {string} 아이콘 클래스
     * @private
     */
    getThemeIcon(theme) {
        const icons = {
            dark: 'fa-moon',
            light: 'fa-sun',
            auto: 'fa-adjust'
        };
        return icons[theme] || 'fa-adjust';
    }

    /**
     * 테마 텍스트 가져오기
     * @param {string} theme - 테마
     * @returns {string} 테마 텍스트
     * @private
     */
    getThemeText(theme) {
        const texts = {
            dark: '다크',
            light: '라이트',
            auto: '자동'
        };
        return texts[theme] || '자동';
    }

    /**
     * 알림 미리보기 렌더링
     * @returns {string} HTML
     * @private
     */
    renderNotificationPreview() {
        const notifications = this.getStoreData(['ui', 'notifications']) || [];
        const recent = notifications.slice(0, 3);
        
        if (recent.length === 0) {
            return '<div class="no-notifications">새 알림이 없습니다</div>';
        }
        
        return recent.map(notification => `
            <div class="notification-preview-item ${notification.type}">
                <div class="notification-content">${notification.message}</div>
                <div class="notification-time">${this.formatLastUpdate(notification.timestamp)}</div>
            </div>
        `).join('');
    }

    /**
     * 진행률 표시 여부
     * @returns {boolean} 표시 여부
     * @private
     */
    shouldShowProgress() {
        return this.state.isRefreshing || this.state.systemStatus === 'loading';
    }

    /**
     * 진행률 퍼센티지 가져오기
     * @returns {number} 퍼센티지
     * @private
     */
    getProgressPercentage() {
        if (this.state.isRefreshing) {
            // 새로고침 진행률 시뮬레이션
            return Math.min(90, (Date.now() - this.refreshStartTime) / 20);
        }
        return 0;
    }

    /**
     * 마운트 후 처리
     * @protected
     */
    onMounted() {
        // 주기적 업데이트 시작
        this.startPeriodicUpdate();
        
        // 키보드 단축키 등록
        this.registerKeyboardShortcuts();
    }

    /**
     * 언마운트 전 처리
     * @protected
     */
    onBeforeUnmount() {
        // 주기적 업데이트 중지
        this.stopPeriodicUpdate();
        
        // 키보드 단축키 해제
        this.unregisterKeyboardShortcuts();
    }

    /**
     * 주기적 업데이트 시작
     * @private
     */
    startPeriodicUpdate() {
        this.updateInterval = setInterval(() => {
            // 마지막 업데이트 시간 갱신
            this.forceUpdate();
        }, 30000); // 30초마다
    }

    /**
     * 주기적 업데이트 중지
     * @private
     */
    stopPeriodicUpdate() {
        if (this.updateInterval) {
            clearInterval(this.updateInterval);
            this.updateInterval = null;
        }
    }

    /**
     * 키보드 단축키 등록
     * @private
     */
    registerKeyboardShortcuts() {
        this.addEventListener('keydown', this.handleKeyboardShortcut, { target: document });
    }

    /**
     * 키보드 단축키 해제
     * @private
     */
    unregisterKeyboardShortcuts() {
        this.removeEventListener('keydown', this.handleKeyboardShortcut);
    }

    /**
     * 키보드 단축키 핸들러
     * @param {KeyboardEvent} event - 키보드 이벤트
     * @private
     */
    handleKeyboardShortcut(event) {
        // Ctrl/Cmd + R: 새로고침
        if ((event.ctrlKey || event.metaKey) && event.key === 'r') {
            event.preventDefault();
            this.handleRefresh(event);
        }
        
        // Ctrl/Cmd + T: 테마 토글
        if ((event.ctrlKey || event.metaKey) && event.key === 't') {
            event.preventDefault();
            this.handleThemeToggle(event);
        }
        
        // Ctrl/Cmd + N: 알림 토글
        if ((event.ctrlKey || event.metaKey) && event.key === 'n') {
            event.preventDefault();
            this.handleNotificationClick(event);
        }
    }
}
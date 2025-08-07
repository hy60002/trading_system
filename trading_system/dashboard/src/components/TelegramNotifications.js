/**
 * @fileoverview 텔레그램 알림 컴포넌트
 * @description 실시간 텔레그램 알림을 관리하는 컴포넌트
 */

import { BaseComponent } from '../core/BaseComponent.js';
import { WebSocketService } from '../services/WebSocketService.js';
import { ToastManager } from './ToastManager.js';

/**
 * 텔레그램 알림 위젯 컴포넌트
 * @extends BaseComponent
 */
export class TelegramNotifications extends BaseComponent {
    /**
     * @param {HTMLElement|string} container - 컨테이너 엘리먼트
     * @param {Object} props - 컴포넌트 속성
     */
    constructor(container, props = {}) {
        super(container, props, {
            subscribeToStore: true,
            enableVirtualDOM: false
        });
        
        this.maxNotifications = props.maxNotifications || 10;
        this.currentFilter = 'all';
        this.reconnectInterval = null;
        this.pollingInterval = null;
        this.wsConnection = null;
    }

    /**
     * 초기 상태 반환
     * @returns {Object} 초기 상태
     */
    getInitialState() {
        return {
            notifications: [],
            isConnected: false,
            connectionStatus: 'connecting',
            connectionText: '연결 중...',
            isLoading: true,
            error: null
        };
    }

    /**
     * 스토어 선택자 반환
     * @returns {Array<string>} 선택자 배열
     */
    getStoreSelectors() {
        return ['notifications.telegram', 'websocket.status'];
    }

    /**
     * 커스텀 이벤트 리스너 설정
     */
    setupCustomEventListeners() {
        this.addEventListener('visibilitychange', this.handleVisibilityChange, {
            target: document
        });
    }

    /**
     * 마운트 후 호출
     */
    onMounted() {
        this.connectToNotificationStream();
        this.fetchNotifications();
    }

    /**
     * 언마운트 전 호출
     */
    onBeforeUnmount() {
        this.disconnectWebSocket();
        this.clearIntervals();
    }

    /**
     * 템플릿 반환
     * @returns {string} HTML 템플릿
     */
    template() {
        return `
            <div class="telegram-widget">
                <div class="widget-header">
                    <div class="widget-title">
                        <i class="fab fa-telegram-plane"></i>
                        텔레그램 알림
                        <span class="notification-count badge">${this.getNotificationCount()}</span>
                    </div>
                    <div class="widget-controls">
                        <button class="control-btn refresh-btn" title="새로고침">
                            <i class="fas fa-sync-alt"></i>
                        </button>
                        <button class="control-btn settings-btn" title="알림 설정">
                            <i class="fas fa-cog"></i>
                        </button>
                        <div class="connection-status">
                            <div class="status-dot ${this.state.connectionStatus}"></div>
                            <span>${this.state.connectionText}</span>
                        </div>
                    </div>
                </div>
                
                ${this.renderFilters()}
                ${this.renderNotificationList()}
                
                <div class="widget-footer">
                    <button class="view-all-btn">
                        <i class="fas fa-external-link-alt"></i>
                        모든 알림 보기
                    </button>
                </div>
            </div>
        `;
    }

    /**
     * 필터 렌더링
     * @returns {string} 필터 HTML
     */
    renderFilters() {
        const filters = [
            { type: 'all', text: '전체' },
            { type: 'trade', text: '거래' },
            { type: 'daily_report', text: '일일보고서' },
            { type: 'error', text: '오류' },
            { type: 'risk_alert', text: '위험알림' }
        ];

        return `
            <div class="notification-filters">
                ${filters.map(filter => `
                    <button class="filter-chip ${filter.type === this.currentFilter ? 'active' : ''}" 
                            data-type="${filter.type}">
                        ${filter.text}
                    </button>
                `).join('')}
            </div>
        `;
    }

    /**
     * 알림 목록 렌더링
     * @returns {string} 알림 목록 HTML
     */
    renderNotificationList() {
        if (this.state.isLoading) {
            return `
                <div class="notification-list">
                    <div class="loading-state">
                        <div class="loading-spinner"></div>
                        <p>텔레그램 알림을 불러오는 중...</p>
                    </div>
                </div>
            `;
        }

        if (this.state.error) {
            return `
                <div class="notification-list">
                    <div class="error-state">
                        <i class="fas fa-exclamation-triangle"></i>
                        <p>${this.state.error}</p>
                        <button class="retry-btn">다시 시도</button>
                    </div>
                </div>
            `;
        }

        const filteredNotifications = this.getFilteredNotifications();
        
        if (filteredNotifications.length === 0) {
            return `
                <div class="notification-list">
                    <div class="empty-state">
                        <i class="fab fa-telegram-plane"></i>
                        <p>표시할 알림이 없습니다</p>
                    </div>
                </div>
            `;
        }

        return `
            <div class="notification-list">
                ${filteredNotifications.map(notification => 
                    this.renderNotificationItem(notification)
                ).join('')}
            </div>
        `;
    }

    /**
     * 알림 아이템 렌더링
     * @param {Object} notification - 알림 객체
     * @returns {string} 알림 아이템 HTML
     */
    renderNotificationItem(notification) {
        const timeAgo = this.getTimeAgo(notification.timestamp);
        const typeIcon = this.getTypeIcon(notification.type);
        const priorityClass = this.getPriorityClass(notification.priority);
        
        return `
            <div class="notification-item ${notification.isNew ? 'new' : ''} ${priorityClass}" 
                 data-id="${notification.id}" data-type="${notification.type}">
                <div class="notification-icon">
                    <i class="${typeIcon}"></i>
                </div>
                <div class="notification-content">
                    <div class="notification-header">
                        <span class="notification-type">${this.getTypeText(notification.type)}</span>
                        <span class="notification-time">${timeAgo}</span>
                    </div>
                    <div class="notification-message">
                        ${this.formatMessage(notification.message)}
                    </div>
                    ${notification.details ? `
                        <div class="notification-details">
                            ${this.formatDetails(notification.details)}
                        </div>
                    ` : ''}
                </div>
                <div class="notification-actions">
                    <button class="action-btn view-btn" data-id="${notification.id}" title="상세보기">
                        <i class="fas fa-eye"></i>
                    </button>
                    <button class="action-btn delete-btn" data-id="${notification.id}" title="삭제">
                        <i class="fas fa-times"></i>
                    </button>
                </div>
            </div>
        `;
    }

    /**
     * 이벤트 핸들러 바인딩
     */
    bindEventHandlers() {
        // 새로고침 버튼
        this.$('.refresh-btn')?.addEventListener('click', this.handleRefresh);
        
        // 설정 버튼
        this.$('.settings-btn')?.addEventListener('click', this.handleOpenSettings);
        
        // 모든 알림 보기 버튼
        this.$('.view-all-btn')?.addEventListener('click', this.handleViewAll);
        
        // 다시 시도 버튼
        this.$('.retry-btn')?.addEventListener('click', this.handleRetry);
        
        // 필터 버튼들
        this.$$('.filter-chip').forEach(btn => {
            btn.addEventListener('click', this.handleFilterChange);
        });
        
        // 알림 액션 버튼들
        this.$$('.view-btn').forEach(btn => {
            btn.addEventListener('click', this.handleViewDetails);
        });
        
        this.$$('.delete-btn').forEach(btn => {
            btn.addEventListener('click', this.handleDeleteNotification);
        });
    }

    /**
     * WebSocket 연결
     */
    async connectToNotificationStream() {
        try {
            const wsService = WebSocketService.getInstance();
            this.wsConnection = await wsService.connect('/ws/telegram-notifications');
            
            this.wsConnection.on('message', this.handleWebSocketMessage);
            this.wsConnection.on('open', this.handleWebSocketOpen);
            this.wsConnection.on('close', this.handleWebSocketClose);
            this.wsConnection.on('error', this.handleWebSocketError);
            
        } catch (error) {
            console.error('텔레그램 WebSocket 연결 실패:', error);
            this.startPolling();
        }
    }

    /**
     * WebSocket 메시지 처리
     * @param {Object} data - 메시지 데이터
     */
    handleWebSocketMessage = (data) => {
        if (data.type === 'telegram_notification') {
            this.addNotification(data.notification);
        }
    };

    /**
     * WebSocket 연결 성공 처리
     */
    handleWebSocketOpen = () => {
        this.setState({
            isConnected: true,
            connectionStatus: 'online',
            connectionText: '실시간 연결됨'
        });
        this.clearReconnectInterval();
    };

    /**
     * WebSocket 연결 종료 처리
     */
    handleWebSocketClose = () => {
        this.setState({
            isConnected: false,
            connectionStatus: 'offline',
            connectionText: '연결 끊김'
        });
        this.startReconnect();
    };

    /**
     * WebSocket 오류 처리
     * @param {Error} error - 오류 객체
     */
    handleWebSocketError = (error) => {
        console.error('텔레그램 WebSocket 오류:', error);
        this.setState({
            connectionStatus: 'error',
            connectionText: '연결 오류'
        });
    };

    /**
     * 알림 목록 조회
     */
    async fetchNotifications() {
        try {
            this.setState({ isLoading: true, error: null });
            
            const response = await fetch('/api/telegram/notifications');
            if (!response.ok) throw new Error('알림 조회 실패');
            
            const data = await response.json();
            const notifications = data.notifications?.map(n => ({
                ...n,
                timestamp: new Date(n.timestamp)
            })) || [];
            
            this.setState({
                notifications,
                isLoading: false
            });

        } catch (error) {
            console.error('텔레그램 알림 조회 오류:', error);
            this.setState({
                error: '알림을 불러올 수 없습니다',
                isLoading: false
            });
        }
    }

    /**
     * 새 알림 추가
     * @param {Object} notification - 알림 객체
     */
    addNotification(notification) {
        const notifications = [...this.state.notifications];
        
        // 중복 방지
        if (notifications.find(n => n.id === notification.id)) {
            return;
        }

        // 새 알림을 맨 앞에 추가
        notifications.unshift({
            ...notification,
            timestamp: new Date(notification.timestamp),
            isNew: true
        });

        // 최대 개수 제한
        if (notifications.length > this.maxNotifications) {
            notifications.splice(this.maxNotifications);
        }

        this.setState({ notifications });
        this.showNewNotificationToast(notification);
        
        // 새 알림 하이라이트 제거
        setTimeout(() => {
            const updatedNotifications = [...this.state.notifications];
            const newNotification = updatedNotifications.find(n => n.id === notification.id);
            if (newNotification) {
                newNotification.isNew = false;
                this.setState({ notifications: updatedNotifications });
            }
        }, 2000);
    }

    /**
     * 필터링된 알림 목록 반환
     * @returns {Array} 필터링된 알림 배열
     */
    getFilteredNotifications() {
        if (this.currentFilter === 'all') {
            return this.state.notifications;
        }
        return this.state.notifications.filter(n => n.type === this.currentFilter);
    }

    /**
     * 알림 개수 반환
     * @returns {number} 알림 개수
     */
    getNotificationCount() {
        return this.state.notifications.length;
    }

    // 이벤트 핸들러들

    /**
     * 새로고침 버튼 클릭 처리
     */
    handleRefresh = async () => {
        const refreshBtn = this.$('.refresh-btn i');
        refreshBtn?.classList.add('fa-spin');
        
        await this.fetchNotifications();
        
        setTimeout(() => {
            refreshBtn?.classList.remove('fa-spin');
        }, 1000);
    };

    /**
     * 필터 변경 처리
     * @param {Event} event - 클릭 이벤트
     */
    handleFilterChange = (event) => {
        const type = event.target.dataset.type;
        this.currentFilter = type;
        
        // 활성 필터 업데이트
        this.$$('.filter-chip').forEach(btn => {
            btn.classList.remove('active');
        });
        event.target.classList.add('active');
        
        this.forceUpdate();
    };

    /**
     * 상세보기 버튼 클릭 처리
     * @param {Event} event - 클릭 이벤트
     */
    handleViewDetails = (event) => {
        const notificationId = event.currentTarget.dataset.id;
        const notification = this.state.notifications.find(n => n.id === notificationId);
        
        if (notification) {
            this.emit('view-details', notification);
        }
    };

    /**
     * 삭제 버튼 클릭 처리
     * @param {Event} event - 클릭 이벤트
     */
    handleDeleteNotification = (event) => {
        const notificationId = event.currentTarget.dataset.id;
        const notifications = this.state.notifications.filter(n => n.id !== notificationId);
        this.setState({ notifications });
        this.emit('notification-deleted', notificationId);
    };

    /**
     * 설정 버튼 클릭 처리
     */
    handleOpenSettings = () => {
        this.emit('open-settings');
    };

    /**
     * 모든 알림 보기 버튼 클릭 처리
     */
    handleViewAll = () => {
        this.emit('view-all-notifications');
    };

    /**
     * 다시 시도 버튼 클릭 처리
     */
    handleRetry = () => {
        this.fetchNotifications();
    };

    /**
     * 가시성 변경 처리
     */
    handleVisibilityChange = () => {
        if (!document.hidden && this.state.isConnected) {
            this.fetchNotifications();
        }
    };

    // 유틸리티 메서드들

    /**
     * 알림 타입별 아이콘 반환
     * @param {string} type - 알림 타입
     * @returns {string} 아이콘 클래스
     */
    getTypeIcon(type) {
        const icons = {
            trade: 'fas fa-exchange-alt',
            daily_report: 'fas fa-chart-bar',
            error: 'fas fa-exclamation-triangle',
            risk_alert: 'fas fa-warning',
            system: 'fas fa-cog'
        };
        return icons[type] || 'fas fa-bell';
    }

    /**
     * 알림 타입별 텍스트 반환
     * @param {string} type - 알림 타입
     * @returns {string} 타입 텍스트
     */
    getTypeText(type) {
        const texts = {
            trade: '거래',
            daily_report: '일일보고서',
            error: '오류',
            risk_alert: '위험알림',
            system: '시스템'
        };
        return texts[type] || '알림';
    }

    /**
     * 우선순위별 CSS 클래스 반환
     * @param {string} priority - 우선순위
     * @returns {string} CSS 클래스
     */
    getPriorityClass(priority) {
        return `priority-${priority}`;
    }

    /**
     * 메시지 포맷팅
     * @param {string} message - 원본 메시지
     * @returns {string} 포맷된 메시지
     */
    formatMessage(message) {
        return message
            .replace(/\*\*(.*?)\*\*/g, '<strong>$1</strong>')
            .replace(/\*(.*?)\*/g, '<em>$1</em>')
            .replace(/\\n/g, '<br>');
    }

    /**
     * 상세 정보 포맷팅
     * @param {Object|string} details - 상세 정보
     * @returns {string} 포맷된 상세 정보
     */
    formatDetails(details) {
        if (typeof details === 'object') {
            return Object.entries(details)
                .map(([key, value]) => `<span class="detail-item">${key}: ${value}</span>`)
                .join(' ');
        }
        return details;
    }

    /**
     * 시간차 텍스트 반환
     * @param {Date} timestamp - 타임스탬프
     * @returns {string} 시간차 텍스트
     */
    getTimeAgo(timestamp) {
        const now = new Date();
        const diff = now - timestamp;
        const minutes = Math.floor(diff / 60000);
        const hours = Math.floor(minutes / 60);
        const days = Math.floor(hours / 24);

        if (minutes < 1) return '방금 전';
        if (minutes < 60) return `${minutes}분 전`;
        if (hours < 24) return `${hours}시간 전`;
        return `${days}일 전`;
    }

    /**
     * 새 알림 토스트 표시
     * @param {Object} notification - 알림 객체
     */
    showNewNotificationToast(notification) {
        const toastManager = ToastManager.getInstance();
        toastManager.show(
            `새 ${this.getTypeText(notification.type)} 알림`,
            'info',
            {
                duration: 3000,
                onClick: () => this.emit('view-details', notification)
            }
        );
    }

    /**
     * 폴링 시작
     */
    startPolling() {
        if (this.pollingInterval) return;
        
        this.pollingInterval = setInterval(() => {
            this.fetchNotifications();
        }, 10000);
        
        this.setState({
            connectionStatus: 'polling',
            connectionText: '폴링 모드'
        });
    }

    /**
     * 재연결 시작
     */
    startReconnect() {
        if (this.reconnectInterval) return;
        
        this.reconnectInterval = setInterval(() => {
            console.log('텔레그램 WebSocket 재연결 시도...');
            this.connectToNotificationStream();
        }, 5000);
    }

    /**
     * 재연결 인터벌 정리
     */
    clearReconnectInterval() {
        if (this.reconnectInterval) {
            clearInterval(this.reconnectInterval);
            this.reconnectInterval = null;
        }
    }

    /**
     * 모든 인터벌 정리
     */
    clearIntervals() {
        this.clearReconnectInterval();
        
        if (this.pollingInterval) {
            clearInterval(this.pollingInterval);
            this.pollingInterval = null;
        }
    }

    /**
     * WebSocket 연결 해제
     */
    disconnectWebSocket() {
        if (this.wsConnection) {
            this.wsConnection.close();
            this.wsConnection = null;
        }
    }
}
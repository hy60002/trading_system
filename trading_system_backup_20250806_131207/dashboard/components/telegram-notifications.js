/**
 * 🔔 텔레그램 알림 통합 컴포넌트
 * 모든 텔레그램 보고서를 실시간으로 표시하는 컴포넌트
 */

class TelegramNotificationWidget {
    constructor(container) {
        this.container = container;
        this.notifications = [];
        this.maxNotifications = 10;
        this.isConnected = false;
        this.reconnectInterval = null;
        this.lastNotificationId = 0;
        
        this.initializeWidget();
        this.connectToNotificationStream();
    }

    initializeWidget() {
        this.container.innerHTML = `
            <div class="telegram-widget">
                <div class="widget-header">
                    <div class="widget-title">
                        <i class="fab fa-telegram-plane"></i>
                        텔레그램 알림
                        <span class="notification-count badge" id="telegram-count">0</span>
                    </div>
                    <div class="widget-controls">
                        <button class="control-btn" title="알림 설정" onclick="telegramWidget.openSettings()">
                            <i class="fas fa-cog"></i>
                        </button>
                        <button class="control-btn" title="새로고침" onclick="telegramWidget.refresh()">
                            <i class="fas fa-sync-alt"></i>
                        </button>
                        <div class="connection-status" id="telegram-status">
                            <div class="status-dot offline"></div>
                            <span>연결 중...</span>
                        </div>
                    </div>
                </div>
                
                <div class="notification-filters">
                    <button class="filter-chip active" data-type="all">전체</button>
                    <button class="filter-chip" data-type="trade">거래</button>
                    <button class="filter-chip" data-type="daily_report">일일보고서</button>
                    <button class="filter-chip" data-type="error">오류</button>
                    <button class="filter-chip" data-type="risk_alert">위험알림</button>
                </div>
                
                <div class="notification-list" id="telegram-notifications">
                    <div class="loading-state">
                        <div class="loading-spinner"></div>
                        <p>텔레그램 알림을 불러오는 중...</p>
                    </div>
                </div>
                
                <div class="widget-footer">
                    <button class="view-all-btn" onclick="telegramWidget.viewAllNotifications()">
                        <i class="fas fa-external-link-alt"></i>
                        모든 알림 보기
                    </button>
                </div>
            </div>
        `;

        this.bindEvents();
    }

    bindEvents() {
        // 필터 버튼 이벤트
        this.container.querySelectorAll('.filter-chip').forEach(btn => {
            btn.addEventListener('click', (e) => {
                this.filterNotifications(e.target.dataset.type);
                this.updateActiveFilter(e.target);
            });
        });

        // 자동 새로고침 (30초마다)
        setInterval(() => this.fetchNotifications(), 30000);
    }

    async connectToNotificationStream() {
        try {
            // WebSocket 연결로 실시간 알림 수신
            const ws = new WebSocket(`ws://${window.location.host}/ws/telegram-notifications`);
            
            ws.onopen = () => {
                this.isConnected = true;
                this.updateConnectionStatus('online', '실시간 연결됨');
                this.clearReconnectInterval();
            };

            ws.onmessage = (event) => {
                const notification = JSON.parse(event.data);
                this.addNotification(notification);
            };

            ws.onclose = () => {
                this.isConnected = false;
                this.updateConnectionStatus('offline', '연결 끊김');
                this.startReconnect();
            };

            ws.onerror = (error) => {
                console.error('텔레그램 WebSocket 오류:', error);
                this.updateConnectionStatus('error', '연결 오류');
            };

        } catch (error) {
            console.error('WebSocket 연결 실패:', error);
            // Fallback to polling
            this.startPolling();
        }
    }

    async fetchNotifications() {
        try {
            const response = await fetch('/api/telegram/notifications');
            if (!response.ok) throw new Error('알림 조회 실패');
            
            const data = await response.json();
            this.notifications = data.notifications || [];
            this.renderNotifications();
            this.updateNotificationCount();

        } catch (error) {
            console.error('텔레그램 알림 조회 오류:', error);
            this.showError('알림을 불러올 수 없습니다');
        }
    }

    addNotification(notification) {
        // 중복 방지
        if (this.notifications.find(n => n.id === notification.id)) {
            return;
        }

        // 새 알림을 맨 앞에 추가
        this.notifications.unshift({
            ...notification,
            timestamp: new Date(notification.timestamp),
            isNew: true
        });

        // 최대 개수 제한
        if (this.notifications.length > this.maxNotifications) {
            this.notifications = this.notifications.slice(0, this.maxNotifications);
        }

        this.renderNotifications();
        this.updateNotificationCount();
        this.showNewNotificationToast(notification);
    }

    renderNotifications() {
        const container = this.container.querySelector('#telegram-notifications');
        const activeFilter = this.container.querySelector('.filter-chip.active').dataset.type;
        
        let filteredNotifications = this.notifications;
        if (activeFilter !== 'all') {
            filteredNotifications = this.notifications.filter(n => n.type === activeFilter);
        }

        if (filteredNotifications.length === 0) {
            container.innerHTML = `
                <div class="empty-state">
                    <i class="fab fa-telegram-plane"></i>
                    <p>표시할 알림이 없습니다</p>
                </div>
            `;
            return;
        }

        const notificationsHTML = filteredNotifications.map(notification => 
            this.renderNotificationItem(notification)
        ).join('');

        container.innerHTML = notificationsHTML;

        // 새 알림 하이라이트 효과
        setTimeout(() => {
            container.querySelectorAll('.notification-item.new').forEach(item => {
                item.classList.remove('new');
            });
        }, 2000);
    }

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
                    <button class="action-btn" title="상세보기" onclick="telegramWidget.viewDetails('${notification.id}')">
                        <i class="fas fa-eye"></i>
                    </button>
                    <button class="action-btn" title="삭제" onclick="telegramWidget.deleteNotification('${notification.id}')">
                        <i class="fas fa-times"></i>
                    </button>
                </div>
            </div>
        `;
    }

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

    getPriorityClass(priority) {
        return `priority-${priority}`;
    }

    formatMessage(message) {
        // 마크다운 스타일 텍스트를 HTML로 변환
        return message
            .replace(/\*\*(.*?)\*\*/g, '<strong>$1</strong>')
            .replace(/\*(.*?)\*/g, '<em>$1</em>')
            .replace(/\\n/g, '<br>');
    }

    formatDetails(details) {
        if (typeof details === 'object') {
            return Object.entries(details)
                .map(([key, value]) => `<span class="detail-item">${key}: ${value}</span>`)
                .join(' ');
        }
        return details;
    }

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

    filterNotifications(type) {
        this.currentFilter = type;
        this.renderNotifications();
    }

    updateActiveFilter(clickedButton) {
        this.container.querySelectorAll('.filter-chip').forEach(btn => {
            btn.classList.remove('active');
        });
        clickedButton.classList.add('active');
    }

    updateNotificationCount() {
        const count = this.notifications.length;
        const badge = this.container.querySelector('#telegram-count');
        badge.textContent = count;
        badge.style.display = count > 0 ? 'inline' : 'none';
    }

    updateConnectionStatus(status, text) {
        const statusElement = this.container.querySelector('#telegram-status');
        const dot = statusElement.querySelector('.status-dot');
        const span = statusElement.querySelector('span');
        
        dot.className = `status-dot ${status}`;
        span.textContent = text;
    }

    showNewNotificationToast(notification) {
        // 새 알림 토스트 표시
        if (window.dashboard) {
            window.dashboard.showToast(
                `새 ${this.getTypeText(notification.type)} 알림`,
                'info',
                () => this.viewDetails(notification.id)
            );
        }
    }

    showError(message) {
        const container = this.container.querySelector('#telegram-notifications');
        container.innerHTML = `
            <div class="error-state">
                <i class="fas fa-exclamation-triangle"></i>
                <p>${message}</p>
                <button onclick="telegramWidget.refresh()" class="retry-btn">다시 시도</button>
            </div>
        `;
    }

    startPolling() {
        // WebSocket 실패 시 폴링으로 fallback
        setInterval(() => this.fetchNotifications(), 10000);
        this.updateConnectionStatus('polling', '폴링 모드');
    }

    startReconnect() {
        if (this.reconnectInterval) return;
        
        this.reconnectInterval = setInterval(() => {
            console.log('텔레그램 WebSocket 재연결 시도...');
            this.connectToNotificationStream();
        }, 5000);
    }

    clearReconnectInterval() {
        if (this.reconnectInterval) {
            clearInterval(this.reconnectInterval);
            this.reconnectInterval = null;
        }
    }

    async refresh() {
        await this.fetchNotifications();
        this.showRefreshFeedback();
    }

    showRefreshFeedback() {
        const refreshBtn = this.container.querySelector('.fa-sync-alt');
        refreshBtn.classList.add('fa-spin');
        setTimeout(() => refreshBtn.classList.remove('fa-spin'), 1000);
    }

    viewDetails(notificationId) {
        const notification = this.notifications.find(n => n.id === notificationId);
        if (!notification) return;

        // 상세 모달 표시
        window.dashboard?.showNotificationModal(notification);
    }

    deleteNotification(notificationId) {
        this.notifications = this.notifications.filter(n => n.id !== notificationId);
        this.renderNotifications();
        this.updateNotificationCount();
    }

    viewAllNotifications() {
        // 전체 알림 페이지로 이동 또는 모달 표시
        window.open('/dashboard/notifications', '_blank');
    }

    openSettings() {
        // 알림 설정 모달 표시
        window.dashboard?.showNotificationSettings();
    }
}

// 전역 인스턴스
window.telegramWidget = null;

// 초기화 함수
function initializeTelegramWidget(container) {
    window.telegramWidget = new TelegramNotificationWidget(container);
    return window.telegramWidget;
}

export { TelegramNotificationWidget, initializeTelegramWidget };
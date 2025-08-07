import { BaseComponent } from '../core/BaseComponent.js';

/**
 * 에러 알림 매니저
 * - 사용자 친화적 에러 메시지 표시
 * - 에러 복구 액션 제공
 * - 다양한 알림 타입 지원
 * - 알림 히스토리 관리
 */
export class ErrorNotificationManager extends BaseComponent {
    constructor(container, options = {}) {
        super(container, options);
        
        // 알림 설정
        this.maxNotifications = options.maxNotifications || 5;
        this.defaultDuration = options.defaultDuration || 5000;
        this.position = options.position || 'top-right';
        
        // 알림 저장소
        this.notifications = [];
        this.notificationQueue = [];
        this.isProcessingQueue = false;
        
        // 에러 메시지 템플릿
        this.messageTemplates = new Map();
        this.setupMessageTemplates();
        
        // 알림 타입별 설정
        this.notificationTypes = {
            error: {
                icon: '❌',
                className: 'error-notification',
                duration: 8000,
                priority: 4
            },
            warning: {
                icon: '⚠️',
                className: 'warning-notification',
                duration: 6000,
                priority: 3
            },
            info: {
                icon: 'ℹ️',
                className: 'info-notification',
                duration: 4000,
                priority: 2
            },
            success: {
                icon: '✅',
                className: 'success-notification',
                duration: 3000,
                priority: 1
            }
        };
        
        // 복구 액션 정의
        this.recoveryActions = new Map();
        this.setupRecoveryActions();
        
        this.init();
    }
    
    /**
     * 초기화
     */
    init() {
        this.createNotificationContainer();
        this.setupEventListeners();
        this.startQueueProcessor();
        this.emit('errorNotificationManagerInitialized');
    }
    
    /**
     * 알림 컨테이너 생성
     */
    createNotificationContainer() {
        // 기존 컨테이너 제거
        const existing = document.getElementById('error-notifications-container');
        if (existing) {
            existing.remove();
        }
        
        // 새 컨테이너 생성
        this.notificationContainer = document.createElement('div');
        this.notificationContainer.id = 'error-notifications-container';
        this.notificationContainer.className = `notification-container ${this.position}`;
        
        // 스타일 적용
        this.notificationContainer.style.cssText = `
            position: fixed;
            z-index: 10000;
            pointer-events: none;
            max-width: 400px;
            ${this.getPositionStyles()}
        `;
        
        document.body.appendChild(this.notificationContainer);
        
        // CSS 클래스 추가
        this.addNotificationStyles();
    }
    
    /**
     * 위치별 스타일 반환
     */
    getPositionStyles() {
        const positions = {
            'top-right': 'top: 20px; right: 20px;',
            'top-left': 'top: 20px; left: 20px;',
            'bottom-right': 'bottom: 20px; right: 20px;',
            'bottom-left': 'bottom: 20px; left: 20px;',
            'top-center': 'top: 20px; left: 50%; transform: translateX(-50%);',
            'bottom-center': 'bottom: 20px; left: 50%; transform: translateX(-50%);'
        };
        
        return positions[this.position] || positions['top-right'];
    }
    
    /**
     * 알림 스타일 추가
     */
    addNotificationStyles() {
        if (document.getElementById('error-notification-styles')) return;
        
        const style = document.createElement('style');
        style.id = 'error-notification-styles';
        style.textContent = `
            .notification-container {
                display: flex;
                flex-direction: column;
                gap: 10px;
            }
            
            .notification-item {
                pointer-events: auto;
                background: white;
                border-radius: 8px;
                padding: 16px;
                box-shadow: 0 4px 12px rgba(0, 0, 0, 0.15);
                border-left: 4px solid #ccc;
                min-width: 300px;
                animation: slideIn 0.3s ease-out;
                position: relative;
                overflow: hidden;
            }
            
            .notification-item.error-notification {
                border-left-color: #ef4444;
                background: #fef2f2;
            }
            
            .notification-item.warning-notification {
                border-left-color: #f59e0b;
                background: #fffbeb;
            }
            
            .notification-item.info-notification {
                border-left-color: #3b82f6;
                background: #eff6ff;
            }
            
            .notification-item.success-notification {
                border-left-color: #10b981;
                background: #f0fdf4;
            }
            
            .notification-header {
                display: flex;
                align-items: center;
                margin-bottom: 8px;
                font-weight: 600;
                font-size: 14px;
            }
            
            .notification-icon {
                margin-right: 8px;
                font-size: 16px;
            }
            
            .notification-title {
                flex: 1;
                color: #374151;
            }
            
            .notification-close {
                background: none;
                border: none;
                font-size: 18px;
                cursor: pointer;
                color: #6b7280;
                padding: 0;
                width: 20px;
                height: 20px;
                display: flex;
                align-items: center;
                justify-content: center;
            }
            
            .notification-close:hover {
                color: #374151;
            }
            
            .notification-message {
                color: #6b7280;
                font-size: 13px;
                line-height: 1.5;
                margin-bottom: 12px;
            }
            
            .notification-actions {
                display: flex;
                gap: 8px;
                margin-top: 8px;
            }
            
            .notification-action {
                background: #374151;
                color: white;
                border: none;
                border-radius: 4px;
                padding: 6px 12px;
                font-size: 12px;
                cursor: pointer;
                transition: background-color 0.2s;
            }
            
            .notification-action:hover {
                background: #1f2937;
            }
            
            .notification-action.secondary {
                background: #e5e7eb;
                color: #374151;
            }
            
            .notification-action.secondary:hover {
                background: #d1d5db;
            }
            
            .notification-progress {
                position: absolute;
                bottom: 0;
                left: 0;
                height: 2px;
                background: currentColor;
                opacity: 0.3;
                transition: width linear;
            }
            
            @keyframes slideIn {
                from {
                    transform: translateX(100%);
                    opacity: 0;
                }
                to {
                    transform: translateX(0);
                    opacity: 1;
                }
            }
            
            @keyframes slideOut {
                from {
                    transform: translateX(0);
                    opacity: 1;
                }
                to {
                    transform: translateX(100%);
                    opacity: 0;
                }
            }
            
            .notification-item.hiding {
                animation: slideOut 0.3s ease-in;
            }
            
            .notification-details {
                background: rgba(0, 0, 0, 0.05);
                border-radius: 4px;
                padding: 8px;
                margin-top: 8px;
                font-size: 11px;
                color: #6b7280;
                max-height: 100px;
                overflow-y: auto;
            }
            
            .notification-timestamp {
                font-size: 11px;
                color: #9ca3af;
                margin-top: 4px;
            }
        `;
        
        document.head.appendChild(style);
    }
    
    /**
     * 메시지 템플릿 설정
     */
    setupMessageTemplates() {
        // 네트워크 에러 템플릿
        this.messageTemplates.set('network_error', {
            title: '연결 오류',
            message: '인터넷 연결을 확인해주세요. 네트워크 상태가 불안정합니다.',
            type: 'error',
            actions: ['retry', 'ignore']
        });
        
        // WebSocket 에러 템플릿
        this.messageTemplates.set('websocket_error', {
            title: '실시간 연결 오류',
            message: '실시간 데이터 연결이 끊어졌습니다. 자동으로 재연결을 시도합니다.',
            type: 'warning',
            actions: ['retry', 'refresh']
        });
        
        // 차트 에러 템플릿
        this.messageTemplates.set('chart_error', {
            title: '차트 오류',
            message: '차트 데이터를 불러오는 중 문제가 발생했습니다.',
            type: 'error',
            actions: ['refresh', 'reset']
        });
        
        // 데이터 에러 템플릿
        this.messageTemplates.set('data_error', {
            title: '데이터 오류',
            message: '데이터 처리 중 오류가 발생했습니다. 잠시 후 다시 시도해주세요.',
            type: 'warning',
            actions: ['retry']
        });
        
        // 권한 에러 템플릿
        this.messageTemplates.set('permission_error', {
            title: '권한 오류',
            message: '접근 권한이 없습니다. 로그인 상태를 확인해주세요.',
            type: 'error',
            actions: ['login', 'refresh']
        });
        
        // 시스템 에러 템플릿
        this.messageTemplates.set('runtime_error', {
            title: '시스템 오류',
            message: '예상치 못한 오류가 발생했습니다.',
            type: 'error',
            actions: ['refresh', 'report']
        });
    }
    
    /**
     * 복구 액션 설정
     */
    setupRecoveryActions() {
        this.recoveryActions.set('retry', {
            label: '다시 시도',
            icon: '🔄',
            handler: (notification) => {
                this.emit('retryAction', notification);
                this.removeNotification(notification.id);
            }
        });
        
        this.recoveryActions.set('refresh', {
            label: '새로고침',
            icon: '↻',
            handler: () => {
                window.location.reload();
            }
        });
        
        this.recoveryActions.set('ignore', {
            label: '무시',
            icon: '✕',
            secondary: true,
            handler: (notification) => {
                this.removeNotification(notification.id);
            }
        });
        
        this.recoveryActions.set('reset', {
            label: '초기화',
            icon: '🔄',
            handler: (notification) => {
                this.emit('resetAction', notification);
                this.removeNotification(notification.id);
            }
        });
        
        this.recoveryActions.set('login', {
            label: '로그인',
            icon: '🔐',
            handler: () => {
                this.emit('loginAction');
            }
        });
        
        this.recoveryActions.set('report', {
            label: '신고하기',
            icon: '📧',
            secondary: true,
            handler: (notification) => {
                this.emit('reportError', notification);
                this.removeNotification(notification.id);
            }
        });
    }
    
    /**
     * 이벤트 리스너 설정
     */
    setupEventListeners() {
        // 에러 발생 이벤트 리스너
        document.addEventListener('errorOccurred', (event) => {
            this.handleErrorOccurred(event.detail);
        });
        
        // 복구 성공 알림
        document.addEventListener('recoverySuccess', (event) => {
            this.showRecoverySuccess(event.detail);
        });
        
        // 네트워크 상태 변경
        window.addEventListener('online', () => {
            this.showNetworkRecovered();
        });
        
        window.addEventListener('offline', () => {
            this.showNetworkError();
        });
    }
    
    /**
     * 알림 표시
     */
    showNotification(options) {
        const notification = this.createNotification(options);
        
        // 큐에 추가 또는 즉시 표시
        if (this.notifications.length >= this.maxNotifications) {
            this.notificationQueue.push(notification);
        } else {
            this.displayNotification(notification);
        }
        
        return notification.id;
    }
    
    /**
     * 알림 객체 생성
     */
    createNotification(options) {
        const template = this.messageTemplates.get(options.type) || {};
        const typeConfig = this.notificationTypes[options.level || 'info'] || this.notificationTypes.info;
        
        const notification = {
            id: this.generateNotificationId(),
            title: options.title || template.title || '알림',
            message: options.message || template.message || '',
            type: options.level || template.type || 'info',
            timestamp: Date.now(),
            duration: options.duration || typeConfig.duration || this.defaultDuration,
            actions: options.actions || template.actions || [],
            details: options.details || null,
            data: options.data || null,
            priority: typeConfig.priority || 2
        };
        
        return notification;
    }
    
    /**
     * 알림 실제 표시
     */
    displayNotification(notification) {
        const element = this.createNotificationElement(notification);
        
        // 컨테이너에 추가
        this.notificationContainer.appendChild(element);
        this.notifications.push({ ...notification, element });
        
        // 자동 제거 타이머 설정
        if (notification.duration > 0) {
            this.setAutoRemoveTimer(notification);
        }
        
        // 진행바 애니메이션
        if (notification.duration > 0) {
            this.animateProgress(element, notification.duration);
        }
        
        this.emit('notificationShown', notification);
    }
    
    /**
     * 알림 DOM 요소 생성
     */
    createNotificationElement(notification) {
        const typeConfig = this.notificationTypes[notification.type];
        const element = document.createElement('div');
        element.className = `notification-item ${typeConfig.className}`;
        element.dataset.notificationId = notification.id;
        
        // 헤더 생성
        const header = document.createElement('div');
        header.className = 'notification-header';
        
        const icon = document.createElement('span');
        icon.className = 'notification-icon';
        icon.textContent = typeConfig.icon;
        
        const title = document.createElement('span');
        title.className = 'notification-title';
        title.textContent = notification.title;
        
        const closeButton = document.createElement('button');
        closeButton.className = 'notification-close';
        closeButton.innerHTML = '×';
        closeButton.onclick = () => this.removeNotification(notification.id);
        
        header.appendChild(icon);
        header.appendChild(title);
        header.appendChild(closeButton);
        
        // 메시지
        const message = document.createElement('div');
        message.className = 'notification-message';
        message.textContent = notification.message;
        
        // 액션 버튼들
        const actionsContainer = document.createElement('div');
        actionsContainer.className = 'notification-actions';
        
        notification.actions.forEach(actionName => {
            const actionConfig = this.recoveryActions.get(actionName);
            if (actionConfig) {
                const button = document.createElement('button');
                button.className = `notification-action ${actionConfig.secondary ? 'secondary' : ''}`;
                button.textContent = `${actionConfig.icon} ${actionConfig.label}`;
                button.onclick = () => actionConfig.handler(notification);
                actionsContainer.appendChild(button);
            }
        });
        
        // 상세 정보 (선택적)
        let detailsElement = null;
        if (notification.details) {
            detailsElement = document.createElement('div');
            detailsElement.className = 'notification-details';
            detailsElement.textContent = JSON.stringify(notification.details, null, 2);
        }
        
        // 타임스탬프
        const timestamp = document.createElement('div');
        timestamp.className = 'notification-timestamp';
        timestamp.textContent = new Date(notification.timestamp).toLocaleTimeString();
        
        // 진행바
        const progress = document.createElement('div');
        progress.className = 'notification-progress';
        
        // 조립
        element.appendChild(header);
        element.appendChild(message);
        if (notification.actions.length > 0) {
            element.appendChild(actionsContainer);
        }
        if (detailsElement) {
            element.appendChild(detailsElement);
        }
        element.appendChild(timestamp);
        element.appendChild(progress);
        
        return element;
    }
    
    /**
     * 진행바 애니메이션
     */
    animateProgress(element, duration) {
        const progress = element.querySelector('.notification-progress');
        if (!progress) return;
        
        progress.style.width = '100%';
        progress.style.transition = `width ${duration}ms linear`;
        
        // 애니메이션 시작
        requestAnimationFrame(() => {
            progress.style.width = '0%';
        });
    }
    
    /**
     * 자동 제거 타이머 설정
     */
    setAutoRemoveTimer(notification) {
        setTimeout(() => {
            this.removeNotification(notification.id);
        }, notification.duration);
    }
    
    /**
     * 알림 제거
     */
    removeNotification(notificationId) {
        const index = this.notifications.findIndex(n => n.id === notificationId);
        if (index === -1) return;
        
        const notification = this.notifications[index];
        const element = notification.element;
        
        // 제거 애니메이션
        element.classList.add('hiding');
        
        setTimeout(() => {
            if (element.parentNode) {
                element.parentNode.removeChild(element);
            }
            this.notifications.splice(index, 1);
            
            // 큐에서 다음 알림 표시
            this.processQueue();
            
            this.emit('notificationRemoved', notification);
        }, 300);
    }
    
    /**
     * 큐 처리
     */
    startQueueProcessor() {
        setInterval(() => {
            this.processQueue();
        }, 500);
    }
    
    processQueue() {
        if (this.notificationQueue.length > 0 && this.notifications.length < this.maxNotifications) {
            // 우선순위 정렬
            this.notificationQueue.sort((a, b) => b.priority - a.priority);
            
            const notification = this.notificationQueue.shift();
            this.displayNotification(notification);
        }
    }
    
    /**
     * 특정 에러 처리
     */
    handleErrorOccurred(errorInfo) {
        const template = this.messageTemplates.get(errorInfo.type);
        if (template) {
            this.showNotification({
                ...template,
                details: errorInfo,
                data: errorInfo
            });
        } else {
            this.showNotification({
                title: '오류 발생',
                message: errorInfo.message || '알 수 없는 오류가 발생했습니다.',
                type: 'error',
                details: errorInfo,
                actions: ['retry', 'ignore']
            });
        }
    }
    
    /**
     * 복구 성공 알림
     */
    showRecoverySuccess(details) {
        this.showNotification({
            title: '복구 완료',
            message: `${details.strategy.name}이(가) 성공적으로 복구되었습니다.`,
            level: 'success',
            duration: 3000
        });
    }
    
    /**
     * 네트워크 관련 알림
     */
    showNetworkError() {
        this.showNotification({
            type: 'network_error',
            level: 'error',
            actions: ['retry', 'ignore']
        });
    }
    
    showNetworkRecovered() {
        this.showNotification({
            title: '연결 복구',
            message: '인터넷 연결이 복구되었습니다.',
            level: 'success',
            duration: 3000
        });
    }
    
    /**
     * 유틸리티 함수
     */
    generateNotificationId() {
        return `notification_${Date.now()}_${Math.random().toString(36).substr(2, 9)}`;
    }
    
    /**
     * 모든 알림 제거
     */
    clearAllNotifications() {
        [...this.notifications].forEach(notification => {
            this.removeNotification(notification.id);
        });
        
        this.notificationQueue = [];
        this.emit('allNotificationsCleared');
    }
    
    /**
     * 특정 타입 알림 제거
     */
    clearNotificationsByType(type) {
        const toRemove = this.notifications.filter(n => n.type === type);
        toRemove.forEach(notification => {
            this.removeNotification(notification.id);
        });
        
        this.notificationQueue = this.notificationQueue.filter(n => n.type !== type);
    }
    
    /**
     * 알림 개수 제한 설정
     */
    setMaxNotifications(max) {
        this.maxNotifications = max;
        
        // 현재 알림이 제한을 초과하면 오래된 것부터 제거
        while (this.notifications.length > max) {
            const oldest = this.notifications[0];
            this.removeNotification(oldest.id);
        }
    }
    
    /**
     * 알림 위치 변경
     */
    setPosition(position) {
        this.position = position;
        this.notificationContainer.className = `notification-container ${position}`;
        this.notificationContainer.style.cssText = `
            position: fixed;
            z-index: 10000;
            pointer-events: none;
            max-width: 400px;
            ${this.getPositionStyles()}
        `;
    }
    
    /**
     * 정리
     */
    destroy() {
        this.clearAllNotifications();
        
        if (this.notificationContainer && this.notificationContainer.parentNode) {
            this.notificationContainer.parentNode.removeChild(this.notificationContainer);
        }
        
        const styles = document.getElementById('error-notification-styles');
        if (styles) {
            styles.remove();
        }
        
        super.destroy();
    }
}

export default ErrorNotificationManager;
// 🔔 Alert Toast Component

class AlertToast {
    constructor(message, type = 'info', options = {}) {
        this.message = message;
        this.type = type;
        this.options = {
            duration: 5000,
            position: 'top-right',
            showIcon: true,
            showClose: true,
            sound: false,
            persistent: false,
            ...options
        };
        
        this.element = null;
        this.container = this.getContainer();
        this.timeoutId = null;
        
        this.create();
        this.show();
    }

    getContainer() {
        let container = document.getElementById('toast-container');
        if (!container) {
            container = document.createElement('div');
            container.id = 'toast-container';
            container.className = 'toast-container';
            document.body.appendChild(container);
        }
        return container;
    }

    create() {
        this.element = document.createElement('div');
        this.element.className = `toast toast-${this.type}`;
        this.element.setAttribute('role', 'alert');
        this.element.setAttribute('aria-live', 'polite');
        
        const icon = this.options.showIcon ? this.getIcon() : '';
        const closeButton = this.options.showClose ? 
            '<button class="toast-close" aria-label="닫기">&times;</button>' : '';
        
        this.element.innerHTML = `
            <div class="toast-content">
                ${icon}
                <div class="toast-message">${this.message}</div>
            </div>
            ${closeButton}
            <div class="toast-progress"></div>
        `;

        this.bindEvents();
    }

    getIcon() {
        const icons = {
            success: '<i class="fas fa-check-circle"></i>',
            error: '<i class="fas fa-exclamation-circle"></i>',
            warning: '<i class="fas fa-exclamation-triangle"></i>',
            info: '<i class="fas fa-info-circle"></i>',
            loading: '<i class="fas fa-spinner fa-spin"></i>'
        };
        
        return `<div class="toast-icon">${icons[this.type] || icons.info}</div>`;
    }

    bindEvents() {
        // 닫기 버튼 이벤트
        const closeBtn = this.element.querySelector('.toast-close');
        if (closeBtn) {
            closeBtn.addEventListener('click', () => this.hide());
        }

        // 호버 시 자동 닫기 일시정지
        this.element.addEventListener('mouseenter', () => {
            if (this.timeoutId) {
                clearTimeout(this.timeoutId);
                this.timeoutId = null;
            }
            this.element.classList.add('paused');
        });

        this.element.addEventListener('mouseleave', () => {
            if (!this.options.persistent) {
                this.scheduleHide();
            }
            this.element.classList.remove('paused');
        });

        // 클릭 이벤트 (액션이 있는 경우)
        if (this.options.onClick) {
            this.element.addEventListener('click', (e) => {
                if (!e.target.closest('.toast-close')) {
                    this.options.onClick();
                    this.hide();
                }
            });
            this.element.style.cursor = 'pointer';
        }
    }

    show() {
        this.container.appendChild(this.element);
        
        // 애니메이션을 위한 지연
        requestAnimationFrame(() => {
            this.element.classList.add('show');
            
            // 프로그레스 바 애니메이션
            if (!this.options.persistent) {
                this.startProgress();
                this.scheduleHide();
            }
        });

        // 사운드 재생
        if (this.options.sound) {
            this.playSound();
        }

        // 접근성을 위한 스크린 리더 알림
        this.announceToScreenReader();
    }

    hide() {
        if (this.timeoutId) {
            clearTimeout(this.timeoutId);
        }

        this.element.classList.add('hiding');
        this.element.classList.remove('show');
        
        setTimeout(() => {
            if (this.element && this.element.parentNode) {
                this.element.parentNode.removeChild(this.element);
            }
        }, 300); // 애니메이션 시간과 맞춤
    }

    scheduleHide() {
        if (this.options.persistent) return;
        
        this.timeoutId = setTimeout(() => {
            this.hide();
        }, this.options.duration);
    }

    startProgress() {
        const progressBar = this.element.querySelector('.toast-progress');
        if (progressBar) {
            progressBar.style.animationDuration = `${this.options.duration}ms`;
            progressBar.classList.add('running');
        }
    }

    playSound() {
        const soundMap = {
            success: '/sounds/success.mp3',
            error: '/sounds/error.mp3',
            warning: '/sounds/warning.mp3',
            info: '/sounds/info.mp3'
        };

        const soundUrl = soundMap[this.type];
        if (soundUrl) {
            const audio = new Audio(soundUrl);
            audio.volume = 0.3;
            audio.play().catch(() => {
                // 사운드 재생 실패는 무시
            });
        }
    }

    announceToScreenReader() {
        // 스크린 리더를 위한 임시 요소 생성
        const announcement = document.createElement('div');
        announcement.setAttribute('aria-live', 'polite');
        announcement.setAttribute('aria-atomic', 'true');
        announcement.className = 'sr-only';
        announcement.textContent = `${this.type} 알림: ${this.message}`;
        
        document.body.appendChild(announcement);
        
        // 일정 시간 후 제거
        setTimeout(() => {
            document.body.removeChild(announcement);
        }, 1000);
    }

    // 토스트 업데이트 (로딩 -> 성공/실패 등)
    update(message, type) {
        this.message = message;
        this.type = type;
        
        const messageElement = this.element.querySelector('.toast-message');
        const iconElement = this.element.querySelector('.toast-icon');
        
        if (messageElement) {
            messageElement.textContent = message;
        }
        
        if (iconElement && this.options.showIcon) {
            iconElement.innerHTML = this.getIcon().replace(/<div[^>]*>|<\/div>/g, '');
        }
        
        // 클래스 업데이트
        this.element.className = `toast toast-${type} show`;
        
        // 새로운 타입에 맞게 자동 닫기 재설정
        if (this.timeoutId) {
            clearTimeout(this.timeoutId);
        }
        
        if (!this.options.persistent) {
            this.scheduleHide();
        }
    }
}

// 토스트 매니저 클래스
class ToastManager {
    constructor() {
        this.toasts = [];
        this.maxToasts = 5;
        this.defaultOptions = {
            duration: 5000,
            position: 'top-right',
            showIcon: true,
            showClose: true,
            sound: this.getSoundSetting()
        };
    }

    show(message, type = 'info', options = {}) {
        const mergedOptions = { ...this.defaultOptions, ...options };
        const toast = new AlertToast(message, type, mergedOptions);
        
        this.toasts.push(toast);
        
        // 최대 토스트 수 제한
        if (this.toasts.length > this.maxToasts) {
            const oldestToast = this.toasts.shift();
            oldestToast.hide();
        }
        
        return toast;
    }

    success(message, options = {}) {
        return this.show(message, 'success', options);
    }

    error(message, options = {}) {
        return this.show(message, 'error', { ...options, duration: 8000 });
    }

    warning(message, options = {}) {
        return this.show(message, 'warning', { ...options, duration: 6000 });
    }

    info(message, options = {}) {
        return this.show(message, 'info', options);
    }

    loading(message, options = {}) {
        return this.show(message, 'loading', { ...options, persistent: true });
    }

    // 진행률이 있는 토스트 (다운로드, 업로드 등)
    progress(message, options = {}) {
        const toast = this.show(message, 'info', { 
            ...options, 
            persistent: true,
            showProgress: true 
        });
        
        toast.updateProgress = (percent) => {
            const progressBar = toast.element.querySelector('.toast-progress');
            if (progressBar) {
                progressBar.style.width = `${percent}%`;
                progressBar.style.animationDuration = 'none';
            }
        };
        
        return toast;
    }

    // 액션이 있는 토스트
    action(message, actionText, actionCallback, options = {}) {
        const actionButton = `
            <button class="toast-action" onclick="(${actionCallback})(); this.closest('.toast').querySelector('.toast-close').click();">
                ${actionText}
            </button>
        `;
        
        const customMessage = `
            <div class="toast-action-content">
                <span>${message}</span>
                ${actionButton}
            </div>
        `;
        
        return this.show(customMessage, 'info', { 
            ...options, 
            duration: 10000,
            showClose: true 
        });
    }

    // 모든 토스트 제거
    clear() {
        this.toasts.forEach(toast => toast.hide());
        this.toasts = [];
    }

    // 특정 타입의 토스트만 제거
    clearType(type) {
        this.toasts = this.toasts.filter(toast => {
            if (toast.type === type) {
                toast.hide();
                return false;
            }
            return true;
        });
    }

    getSoundSetting() {
        return localStorage.getItem('toast-sound') !== 'false';
    }

    setSoundEnabled(enabled) {
        localStorage.setItem('toast-sound', enabled.toString());
        this.defaultOptions.sound = enabled;
    }

    // 토스트 위치 설정
    setPosition(position) {
        this.defaultOptions.position = position;
        const container = document.getElementById('toast-container');
        if (container) {
            container.className = `toast-container toast-${position}`;
        }
    }
}

// 전역 토스트 매니저 인스턴스
const toastManager = new ToastManager();

// 편의 함수들
function showToast(message, type = 'info', options = {}) {
    return toastManager.show(message, type, options);
}

function showSuccessToast(message, options = {}) {
    return toastManager.success(message, options);
}

function showErrorToast(message, options = {}) {
    return toastManager.error(message, options);
}

function showWarningToast(message, options = {}) {
    return toastManager.warning(message, options);
}

function showInfoToast(message, options = {}) {
    return toastManager.info(message, options);
}

function showLoadingToast(message, options = {}) {
    return toastManager.loading(message, options);
}

function showProgressToast(message, options = {}) {
    return toastManager.progress(message, options);
}

function showActionToast(message, actionText, actionCallback, options = {}) {
    return toastManager.action(message, actionText, actionCallback, options);
}

// CSS 스타일 추가
const toastStyles = `
.toast-container {
    position: fixed;
    top: 20px;
    right: 20px;
    z-index: 10000;
    pointer-events: none;
}

.toast-container.toast-top-left {
    top: 20px;
    left: 20px;
    right: auto;
}

.toast-container.toast-bottom-right {
    top: auto;
    bottom: 20px;
    right: 20px;
}

.toast-container.toast-bottom-left {
    top: auto;
    bottom: 20px;
    left: 20px;
    right: auto;
}

.toast {
    display: flex;
    align-items: center;
    background: var(--bg-card);
    backdrop-filter: blur(10px);
    border-radius: 8px;
    padding: 12px 16px;
    margin-bottom: 8px;
    min-width: 300px;
    max-width: 500px;
    box-shadow: var(--shadow-lg);
    border-left: 4px solid;
    pointer-events: auto;
    transform: translateX(100%);
    opacity: 0;
    transition: all 0.3s ease;
    position: relative;
    overflow: hidden;
}

.toast.show {
    transform: translateX(0);
    opacity: 1;
}

.toast.hiding {
    transform: translateX(100%);
    opacity: 0;
}

.toast.paused .toast-progress {
    animation-play-state: paused;
}

.toast-success {
    border-left-color: var(--profit-green);
}

.toast-error {
    border-left-color: var(--loss-red);
}

.toast-warning {
    border-left-color: var(--warning-orange);
}

.toast-info {
    border-left-color: var(--active-blue);
}

.toast-loading {
    border-left-color: var(--neutral-gray);
}

.toast-content {
    display: flex;
    align-items: center;
    flex: 1;
    gap: 8px;
}

.toast-icon {
    font-size: 16px;
    flex-shrink: 0;
}

.toast-success .toast-icon {
    color: var(--profit-green);
}

.toast-error .toast-icon {
    color: var(--loss-red);
}

.toast-warning .toast-icon {
    color: var(--warning-orange);
}

.toast-info .toast-icon {
    color: var(--active-blue);
}

.toast-loading .toast-icon {
    color: var(--neutral-gray);
}

.toast-message {
    flex: 1;
    font-size: 14px;
    line-height: 1.4;
    color: var(--text-primary);
}

.toast-close {
    background: none;
    border: none;
    color: var(--text-secondary);
    font-size: 18px;
    cursor: pointer;
    padding: 0;
    margin-left: 8px;
    opacity: 0.7;
    transition: opacity 0.2s;
}

.toast-close:hover {
    opacity: 1;
}

.toast-progress {
    position: absolute;
    bottom: 0;
    left: 0;
    height: 3px;
    background: linear-gradient(90deg, transparent 0%, var(--active-blue) 100%);
    transform-origin: left;
    transform: scaleX(0);
}

.toast-progress.running {
    animation: toast-progress linear forwards;
}

.toast-action-content {
    display: flex;
    justify-content: space-between;
    align-items: center;
    width: 100%;
}

.toast-action {
    background: var(--active-blue);
    color: white;
    border: none;
    padding: 4px 8px;
    border-radius: 4px;
    font-size: 12px;
    cursor: pointer;
    margin-left: 8px;
    transition: background 0.2s;
}

.toast-action:hover {
    background: var(--active-blue);
    opacity: 0.9;
}

@keyframes toast-progress {
    to {
        transform: scaleX(1);
    }
}

/* 스크린 리더 전용 클래스 */
.sr-only {
    position: absolute;
    width: 1px;
    height: 1px;
    padding: 0;
    margin: -1px;
    overflow: hidden;
    clip: rect(0, 0, 0, 0);
    white-space: nowrap;
    border: 0;
}

/* 반응형 */
@media (max-width: 480px) {
    .toast-container {
        left: 10px;
        right: 10px;
        top: 10px;
    }
    
    .toast {
        min-width: auto;
        max-width: none;
        transform: translateY(-100%);
    }
    
    .toast.show {
        transform: translateY(0);
    }
    
    .toast.hiding {
        transform: translateY(-100%);
    }
}
`;

// 스타일 추가
const styleSheet = document.createElement('style');
styleSheet.textContent = toastStyles;
document.head.appendChild(styleSheet);
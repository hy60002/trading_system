/**
 * @fileoverview Toast Manager Component - ES6 Module
 * @description 토스트 알림 시스템
 * @version 2.0.0
 */

import { BaseComponent } from '../core/BaseComponent.js';
import { eventBus } from '../core/EventBus.js';

/**
 * Alert Toast Component
 * @extends BaseComponent
 */
export class AlertToast extends BaseComponent {
    /**
     * @param {HTMLElement} container - Container element (usually body)
     * @param {string} message - Toast message
     * @param {string} type - Toast type (success, error, warning, info, loading)
     * @param {Object} options - Toast options
     */
    constructor(container, message, type = 'info', options = {}) {
        super(container, options);
        
        this.message = message;
        this.type = type;
        this.timeoutId = null;
        this.isVisible = false;
        
        this.create();
    }

    /**
     * Get default options
     * @returns {Object}
     */
    getDefaultOptions() {
        return {
            ...super.getDefaultOptions(),
            duration: 5000,
            position: 'top-right',
            showIcon: true,
            showClose: true,
            sound: false,
            persistent: false,
            clickToClose: false
        };
    }

    /**
     * Create toast element
     */
    create() {
        this.element = this.createElement('div', {
            classes: ['toast', `toast-${this.type}`],
            attributes: {
                role: 'alert',
                'aria-live': 'polite',
                'aria-atomic': 'true'
            }
        });

        const icon = this.options.showIcon ? this.getIcon() : '';
        const closeButton = this.options.showClose ? 
            '<button class="toast-close" type="button" aria-label="닫기">&times;</button>' : '';

        this.element.innerHTML = `
            <div class="toast-content">
                ${icon}
                <div class="toast-message">${this.escapeHtml(this.message)}</div>
            </div>
            ${closeButton}
            <div class="toast-progress"></div>
        `;

        this.setupEventListeners();
    }

    /**
     * Setup event listeners
     */
    setupEventListeners() {
        // Close button event
        const closeBtn = this.find('.toast-close');
        if (closeBtn) {
            this.addEventListener(closeBtn, 'click', () => this.hide());
        }

        // Hover events for auto-close pause
        this.addEventListener(this.element, 'mouseenter', this.handleMouseEnter.bind(this));
        this.addEventListener(this.element, 'mouseleave', this.handleMouseLeave.bind(this));

        // Click to close
        if (this.options.clickToClose) {
            this.addEventListener(this.element, 'click', (e) => {
                if (!e.target.closest('.toast-close')) {
                    this.hide();
                }
            });
            this.element.style.cursor = 'pointer';
        }

        // Click action
        if (this.options.onClick) {
            this.addEventListener(this.element, 'click', (e) => {
                if (!e.target.closest('.toast-close')) {
                    this.options.onClick(this);
                }
            });
            this.element.style.cursor = 'pointer';
        }
    }

    /**
     * Get icon HTML based on type
     * @returns {string} Icon HTML
     */
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

    /**
     * Show toast
     */
    show() {
        if (this.isVisible) return this;

        // Get or create container
        const toastContainer = this.getToastContainer();
        toastContainer.appendChild(this.element);

        this.isVisible = true;

        // Animation
        requestAnimationFrame(() => {
            this.element.classList.add('show');
            
            // Progress bar animation
            if (!this.options.persistent) {
                this.startProgress();
                this.scheduleHide();
            }
        });

        // Play sound
        if (this.options.sound) {
            this.playSound();
        }

        // Screen reader announcement
        this.announceToScreenReader();

        // Emit event
        this.emit('shown', { toast: this });
        eventBus.emit('toast:shown', { toast: this, type: this.type, message: this.message });

        return this;
    }

    /**
     * Hide toast
     */
    hide() {
        if (!this.isVisible) return this;

        if (this.timeoutId) {
            clearTimeout(this.timeoutId);
            this.timeoutId = null;
        }

        this.element.classList.add('hiding');
        this.element.classList.remove('show');
        
        setTimeout(() => {
            if (this.element && this.element.parentNode) {
                this.element.parentNode.removeChild(this.element);
            }
            this.isVisible = false;
            
            // Emit event
            this.emit('hidden', { toast: this });
            eventBus.emit('toast:hidden', { toast: this });
        }, 300);

        return this;
    }

    /**
     * Update toast content and type
     * @param {string} message - New message
     * @param {string} type - New type
     */
    update(message, type) {
        this.message = message;
        this.type = type;
        
        const messageElement = this.find('.toast-message');
        const iconElement = this.find('.toast-icon');
        
        if (messageElement) {
            messageElement.textContent = message;
        }
        
        if (iconElement && this.options.showIcon) {
            iconElement.innerHTML = this.getIcon().replace(/<div[^>]*>|<\/div>/g, '');
        }
        
        // Update classes
        this.element.className = `toast toast-${type} show`;
        
        // Restart auto-close timer
        if (this.timeoutId) {
            clearTimeout(this.timeoutId);
        }
        
        if (!this.options.persistent) {
            this.scheduleHide();
        }

        this.emit('updated', { toast: this, message, type });
        
        return this;
    }

    /**
     * Update progress (for progress toasts)
     * @param {number} percent - Progress percentage (0-100)
     */
    updateProgress(percent) {
        const progressBar = this.find('.toast-progress');
        if (progressBar) {
            progressBar.style.width = `${Math.min(Math.max(percent, 0), 100)}%`;
            progressBar.style.animationDuration = 'none';
            progressBar.classList.remove('running');
        }
        
        this.emit('progressUpdated', { toast: this, percent });
        
        return this;
    }

    /**
     * Get or create toast container
     * @returns {HTMLElement} Toast container
     */
    getToastContainer() {
        let container = document.getElementById('toast-container');
        if (!container) {
            container = document.createElement('div');
            container.id = 'toast-container';
            container.className = `toast-container toast-${this.options.position}`;
            document.body.appendChild(container);
        }
        return container;
    }

    /**
     * Handle mouse enter
     */
    handleMouseEnter() {
        if (this.timeoutId) {
            clearTimeout(this.timeoutId);
            this.timeoutId = null;
        }
        this.element.classList.add('paused');
    }

    /**
     * Handle mouse leave
     */
    handleMouseLeave() {
        if (!this.options.persistent) {
            this.scheduleHide();
        }
        this.element.classList.remove('paused');
    }

    /**
     * Schedule auto-hide
     */
    scheduleHide() {
        if (this.options.persistent) return;
        
        this.timeoutId = setTimeout(() => {
            this.hide();
        }, this.options.duration);
    }

    /**
     * Start progress bar animation
     */
    startProgress() {
        const progressBar = this.find('.toast-progress');
        if (progressBar) {
            progressBar.style.animationDuration = `${this.options.duration}ms`;
            progressBar.classList.add('running');
        }
    }

    /**
     * Play notification sound
     */
    playSound() {
        const soundMap = {
            success: '/sounds/success.mp3',
            error: '/sounds/error.mp3',
            warning: '/sounds/warning.mp3',
            info: '/sounds/info.mp3'
        };

        const soundUrl = soundMap[this.type];
        if (soundUrl) {
            try {
                const audio = new Audio(soundUrl);
                audio.volume = 0.3;
                audio.play().catch(() => {
                    // Ignore sound playback failures
                });
            } catch (error) {
                // Ignore audio creation errors
            }
        }
    }

    /**
     * Announce to screen readers
     */
    announceToScreenReader() {
        const announcement = document.createElement('div');
        announcement.setAttribute('aria-live', 'polite');
        announcement.setAttribute('aria-atomic', 'true');
        announcement.className = 'sr-only';
        announcement.textContent = `${this.type} 알림: ${this.message}`;
        
        document.body.appendChild(announcement);
        
        setTimeout(() => {
            if (announcement.parentNode) {
                document.body.removeChild(announcement);
            }
        }, 1000);
    }

    /**
     * Cleanup when destroyed
     */
    destroy() {
        this.hide();
        super.destroy();
    }
}

/**
 * Toast Manager Class
 * Manages multiple toast notifications
 */
export class ToastManager {
    constructor(options = {}) {
        this.toasts = [];
        this.maxToasts = options.maxToasts || 5;
        this.defaultOptions = {
            duration: 5000,
            position: 'top-right',
            showIcon: true,
            showClose: true,
            sound: this.getSoundSetting(),
            ...options
        };

        this.initializeStyles();
        this.setupEventListeners();
    }

    /**
     * Setup event listeners
     */
    setupEventListeners() {
        // Global toast events
        eventBus.on('toast:show', (data) => {
            this.show(data.message, data.type || 'info', data.options || {});
        });

        eventBus.on('toast:clear', (data) => {
            if (data.type) {
                this.clearType(data.type);
            } else {
                this.clear();
            }
        });

        // Clean up hidden toasts
        eventBus.on('toast:hidden', (data) => {
            this.toasts = this.toasts.filter(toast => toast !== data.toast);
        });
    }

    /**
     * Show toast notification
     * @param {string} message - Toast message
     * @param {string} type - Toast type
     * @param {Object} options - Toast options
     * @returns {AlertToast} Toast instance
     */
    show(message, type = 'info', options = {}) {
        const mergedOptions = { ...this.defaultOptions, ...options };
        const toast = new AlertToast(document.body, message, type, mergedOptions);
        
        this.toasts.push(toast);
        
        // Enforce max toasts limit
        if (this.toasts.length > this.maxToasts) {
            const oldestToast = this.toasts.shift();
            oldestToast.hide();
        }
        
        toast.show();
        
        eventBus.emit('toast:manager:added', { 
            toast, 
            totalCount: this.toasts.length 
        });
        
        return toast;
    }

    /**
     * Show success toast
     * @param {string} message - Message
     * @param {Object} options - Options
     * @returns {AlertToast} Toast instance
     */
    success(message, options = {}) {
        return this.show(message, 'success', options);
    }

    /**
     * Show error toast
     * @param {string} message - Message
     * @param {Object} options - Options
     * @returns {AlertToast} Toast instance
     */
    error(message, options = {}) {
        return this.show(message, 'error', { 
            ...options, 
            duration: options.duration || 8000 
        });
    }

    /**
     * Show warning toast
     * @param {string} message - Message
     * @param {Object} options - Options
     * @returns {AlertToast} Toast instance
     */
    warning(message, options = {}) {
        return this.show(message, 'warning', { 
            ...options, 
            duration: options.duration || 6000 
        });
    }

    /**
     * Show info toast
     * @param {string} message - Message
     * @param {Object} options - Options
     * @returns {AlertToast} Toast instance
     */
    info(message, options = {}) {
        return this.show(message, 'info', options);
    }

    /**
     * Show loading toast
     * @param {string} message - Message
     * @param {Object} options - Options
     * @returns {AlertToast} Toast instance
     */
    loading(message, options = {}) {
        return this.show(message, 'loading', { 
            ...options, 
            persistent: true 
        });
    }

    /**
     * Show progress toast
     * @param {string} message - Message
     * @param {Object} options - Options
     * @returns {AlertToast} Toast instance
     */
    progress(message, options = {}) {
        const toast = this.show(message, 'info', { 
            ...options, 
            persistent: true,
            showProgress: true 
        });
        
        return toast;
    }

    /**
     * Show action toast with button
     * @param {string} message - Message
     * @param {string} actionText - Action button text
     * @param {Function} actionCallback - Action callback
     * @param {Object} options - Options
     * @returns {AlertToast} Toast instance
     */
    action(message, actionText, actionCallback, options = {}) {
        const actionButton = this.createElement('button', {
            classes: ['toast-action'],
            textContent: actionText
        });
        
        const customMessage = this.createElement('div', {
            classes: ['toast-action-content'],
            innerHTML: `
                <span>${this.escapeHtml(message)}</span>
            `
        });
        
        customMessage.appendChild(actionButton);
        
        const toast = this.show(customMessage.outerHTML, 'info', { 
            ...options, 
            duration: options.duration || 10000,
            showClose: true,
            onClick: (toastInstance) => {
                if (typeof actionCallback === 'function') {
                    actionCallback();
                }
                toastInstance.hide();
            }
        });
        
        return toast;
    }

    /**
     * Clear all toasts
     */
    clear() {
        this.toasts.forEach(toast => toast.hide());
        this.toasts = [];
        
        eventBus.emit('toast:manager:cleared');
    }

    /**
     * Clear toasts of specific type
     * @param {string} type - Toast type to clear
     */
    clearType(type) {
        this.toasts = this.toasts.filter(toast => {
            if (toast.type === type) {
                toast.hide();
                return false;
            }
            return true;
        });
        
        eventBus.emit('toast:manager:type_cleared', { type });
    }

    /**
     * Get sound setting from localStorage
     * @returns {boolean} Sound enabled
     */
    getSoundSetting() {
        return localStorage.getItem('toast-sound') !== 'false';
    }

    /**
     * Set sound enabled/disabled
     * @param {boolean} enabled - Sound enabled
     */
    setSoundEnabled(enabled) {
        localStorage.setItem('toast-sound', enabled.toString());
        this.defaultOptions.sound = enabled;
        
        eventBus.emit('toast:manager:sound_changed', { enabled });
    }

    /**
     * Set toast position
     * @param {string} position - Toast position
     */
    setPosition(position) {
        this.defaultOptions.position = position;
        const container = document.getElementById('toast-container');
        if (container) {
            container.className = `toast-container toast-${position}`;
        }
        
        eventBus.emit('toast:manager:position_changed', { position });
    }

    /**
     * Set maximum number of toasts
     * @param {number} max - Maximum toasts
     */
    setMaxToasts(max) {
        this.maxToasts = Math.max(1, max);
        
        // Remove excess toasts
        while (this.toasts.length > this.maxToasts) {
            const oldestToast = this.toasts.shift();
            oldestToast.hide();
        }
        
        eventBus.emit('toast:manager:max_changed', { max: this.maxToasts });
    }

    /**
     * Get active toasts count
     * @returns {number} Active toasts count
     */
    getActiveCount() {
        return this.toasts.length;
    }

    /**
     * Get toasts by type
     * @param {string} type - Toast type
     * @returns {Array} Toasts of specified type
     */
    getByType(type) {
        return this.toasts.filter(toast => toast.type === type);
    }

    /**
     * Create DOM element helper
     * @param {string} tag - Element tag
     * @param {Object} options - Element options
     * @returns {HTMLElement} Created element
     */
    createElement(tag, options = {}) {
        const element = document.createElement(tag);
        
        if (options.classes) {
            element.className = Array.isArray(options.classes) ? 
                options.classes.join(' ') : options.classes;
        }
        
        if (options.textContent) {
            element.textContent = options.textContent;
        }
        
        if (options.innerHTML) {
            element.innerHTML = options.innerHTML;
        }
        
        return element;
    }

    /**
     * Escape HTML to prevent XSS
     * @param {string} text - Text to escape
     * @returns {string} Escaped text
     */
    escapeHtml(text) {
        const div = document.createElement('div');
        div.textContent = text;
        return div.innerHTML;
    }

    /**
     * Initialize toast styles
     */
    initializeStyles() {
        if (document.getElementById('toast-styles')) return;

        const toastStyles = `
        .toast-container {
            position: fixed;
            top: 20px;
            right: 20px;
            z-index: 10000;
            pointer-events: none;
            display: flex;
            flex-direction: column;
            gap: 8px;
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

        const styleSheet = document.createElement('style');
        styleSheet.id = 'toast-styles';
        styleSheet.textContent = toastStyles;
        document.head.appendChild(styleSheet);
    }

    /**
     * Destroy toast manager
     */
    destroy() {
        this.clear();
        eventBus.off('toast:show');
        eventBus.off('toast:clear');
        eventBus.off('toast:hidden');
    }
}

// Global toast manager instance
export const toastManager = new ToastManager();

// Convenience functions for global use
export const showToast = (message, type = 'info', options = {}) => 
    toastManager.show(message, type, options);

export const showSuccessToast = (message, options = {}) => 
    toastManager.success(message, options);

export const showErrorToast = (message, options = {}) => 
    toastManager.error(message, options);

export const showWarningToast = (message, options = {}) => 
    toastManager.warning(message, options);

export const showInfoToast = (message, options = {}) => 
    toastManager.info(message, options);

export const showLoadingToast = (message, options = {}) => 
    toastManager.loading(message, options);

export const showProgressToast = (message, options = {}) => 
    toastManager.progress(message, options);

export const showActionToast = (message, actionText, actionCallback, options = {}) => 
    toastManager.action(message, actionText, actionCallback, options);

// Make available globally if needed
if (typeof window !== 'undefined') {
    window.AlertToast = AlertToast;
    window.ToastManager = ToastManager;
    window.toastManager = toastManager;
    
    // Global convenience functions
    window.showToast = showToast;
    window.showSuccessToast = showSuccessToast;
    window.showErrorToast = showErrorToast;
    window.showWarningToast = showWarningToast;
    window.showInfoToast = showInfoToast;
    window.showLoadingToast = showLoadingToast;
    window.showProgressToast = showProgressToast;
    window.showActionToast = showActionToast;
}
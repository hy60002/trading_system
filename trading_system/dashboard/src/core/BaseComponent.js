/**
 * @fileoverview Base Component Class for Trading Dashboard
 * @description Provides common functionality for all dashboard components
 * @version 1.0.0
 */

/**
 * Base class for all dashboard components
 * Provides common functionality like event handling, DOM manipulation, and lifecycle management
 */
export class BaseComponent {
    /**
     * @param {HTMLElement} element - The DOM element this component is attached to
     * @param {Object} options - Configuration options for the component
     */
    constructor(element, options = {}) {
        this.element = element;
        this.options = { ...this.getDefaultOptions(), ...options };
        this.eventListeners = new Map();
        this.isInitialized = false;
        this.isDestroyed = false;
        
        this.init();
    }

    /**
     * Get default options for the component
     * @returns {Object} Default options
     */
    getDefaultOptions() {
        return {
            autoUpdate: true,
            updateInterval: 1000,
            theme: 'dark'
        };
    }

    /**
     * Initialize the component
     * This method should be overridden by child classes
     */
    init() {
        this.bindEvents();
        this.render();
        this.isInitialized = true;
        
        if (this.options.autoUpdate) {
            this.startAutoUpdate();
        }
    }

    /**
     * Render the component
     * This method should be overridden by child classes
     */
    render() {
        // Override in child classes
    }

    /**
     * Update the component with new data
     * @param {Object} data - New data to update the component with
     */
    update(data) {
        if (this.isDestroyed) return;
        
        this.data = data;
        this.render();
    }

    /**
     * Bind event listeners
     * This method should be overridden by child classes
     */
    bindEvents() {
        // Override in child classes
    }

    /**
     * Add event listener with automatic cleanup
     * @param {HTMLElement} element - Element to add listener to
     * @param {string} event - Event name
     * @param {Function} handler - Event handler
     * @param {Object} options - Event options
     */
    addEventListener(element, event, handler, options = {}) {
        const boundHandler = handler.bind(this);
        element.addEventListener(event, boundHandler, options);
        
        // Store for cleanup
        const key = `${element.tagName}_${event}_${Date.now()}`;
        this.eventListeners.set(key, {
            element,
            event,
            handler: boundHandler,
            options
        });
    }

    /**
     * Remove all event listeners
     */
    removeEventListeners() {
        this.eventListeners.forEach(({ element, event, handler, options }) => {
            element.removeEventListener(event, handler, options);
        });
        this.eventListeners.clear();
    }

    /**
     * Start auto-update timer
     */
    startAutoUpdate() {
        if (this.updateTimer) {
            clearInterval(this.updateTimer);
        }
        
        this.updateTimer = setInterval(() => {
            if (!this.isDestroyed) {
                this.onAutoUpdate();
            }
        }, this.options.updateInterval);
    }

    /**
     * Stop auto-update timer
     */
    stopAutoUpdate() {
        if (this.updateTimer) {
            clearInterval(this.updateTimer);
            this.updateTimer = null;
        }
    }

    /**
     * Called during auto-update
     * This method should be overridden by child classes
     */
    onAutoUpdate() {
        // Override in child classes
    }

    /**
     * Show loading state
     */
    showLoading() {
        this.element.classList.add('loading');
    }

    /**
     * Hide loading state
     */
    hideLoading() {
        this.element.classList.remove('loading');
    }

    /**
     * Show error state
     * @param {string} message - Error message
     */
    showError(message) {
        this.element.classList.add('error');
        const errorElement = this.element.querySelector('.error-message');
        if (errorElement) {
            errorElement.textContent = message;
            errorElement.style.display = 'block';
        }
    }

    /**
     * Hide error state
     */
    hideError() {
        this.element.classList.remove('error');
        const errorElement = this.element.querySelector('.error-message');
        if (errorElement) {
            errorElement.style.display = 'none';
        }
    }

    /**
     * Create DOM element with classes and attributes
     * @param {string} tag - HTML tag name
     * @param {Object} options - Element options
     * @returns {HTMLElement} Created element
     */
    createElement(tag, options = {}) {
        const element = document.createElement(tag);
        
        if (options.classes) {
            element.classList.add(...options.classes);
        }
        
        if (options.attributes) {
            Object.entries(options.attributes).forEach(([key, value]) => {
                element.setAttribute(key, value);
            });
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
     * Find element within component scope
     * @param {string} selector - CSS selector
     * @returns {HTMLElement|null} Found element
     */
    find(selector) {
        return this.element.querySelector(selector);
    }

    /**
     * Find all elements within component scope
     * @param {string} selector - CSS selector
     * @returns {NodeList} Found elements
     */
    findAll(selector) {
        return this.element.querySelectorAll(selector);
    }

    /**
     * Emit custom event
     * @param {string} eventName - Event name
     * @param {Object} detail - Event detail data
     */
    emit(eventName, detail = {}) {
        const event = new CustomEvent(eventName, {
            detail,
            bubbles: true,
            cancelable: true
        });
        this.element.dispatchEvent(event);
    }

    /**
     * Format currency value
     * @param {number} amount - Amount to format
     * @param {string} currency - Currency code
     * @returns {string} Formatted currency
     */
    formatCurrency(amount, currency = 'USD') {
        return new Intl.NumberFormat('ko-KR', {
            style: 'currency',
            currency: currency,
            minimumFractionDigits: 2,
            maximumFractionDigits: 2
        }).format(amount);
    }

    /**
     * Format number value
     * @param {number} number - Number to format
     * @param {number} maxDecimals - Maximum decimal places
     * @returns {string} Formatted number
     */
    formatNumber(number, maxDecimals = 4) {
        return new Intl.NumberFormat('ko-KR', {
            minimumFractionDigits: 0,
            maximumFractionDigits: maxDecimals
        }).format(number);
    }

    /**
     * Format date value
     * @param {Date|string} date - Date to format
     * @returns {string} Formatted date
     */
    formatDate(date) {
        const d = new Date(date);
        return d.toLocaleString('ko-KR');
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
     * Debounce function calls
     * @param {Function} func - Function to debounce
     * @param {number} wait - Wait time in milliseconds
     * @returns {Function} Debounced function
     */
    debounce(func, wait) {
        let timeout;
        return (...args) => {
            clearTimeout(timeout);
            timeout = setTimeout(() => func.apply(this, args), wait);
        };
    }

    /**
     * Throttle function calls
     * @param {Function} func - Function to throttle
     * @param {number} limit - Time limit in milliseconds
     * @returns {Function} Throttled function
     */
    throttle(func, limit) {
        let inThrottle;
        return (...args) => {
            if (!inThrottle) {
                func.apply(this, args);
                inThrottle = true;
                setTimeout(() => inThrottle = false, limit);
            }
        };
    }

    /**
     * Destroy the component and cleanup resources
     */
    destroy() {
        if (this.isDestroyed) return;
        
        this.stopAutoUpdate();
        this.removeEventListeners();
        
        if (this.element && this.element.parentNode) {
            this.element.parentNode.removeChild(this.element);
        }
        
        this.isDestroyed = true;
        this.emit('destroyed');
    }

    /**
     * Get component state
     * @returns {Object} Component state
     */
    getState() {
        return {
            isInitialized: this.isInitialized,
            isDestroyed: this.isDestroyed,
            data: this.data,
            options: this.options
        };
    }
}

export default BaseComponent;
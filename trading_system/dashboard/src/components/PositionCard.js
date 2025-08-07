/**
 * @fileoverview Position Card Component - ES6 Module
 * @description 개별 포지션을 표시하는 카드 컴포넌트
 * @version 2.0.0
 */

import { BaseComponent } from '../core/BaseComponent.js';
import { eventBus } from '../core/EventBus.js';
import { globalStore } from '../core/Store.js';
import { dragDropManager } from '../core/DragDropManager.js';

/**
 * Position Card Component
 * @extends BaseComponent
 */
export class PositionCard extends BaseComponent {
    /**
     * @param {HTMLElement} container - Container element
     * @param {Object} position - Position data
     * @param {Object} options - Component options
     */
    constructor(container, position, options = {}) {
        super(container, options);
        
        this.position = position;
        this.isEditing = false;
        this.isDragging = false;
        this.dragHandle = null;
        
        this.create();
        this.setupEventListeners();
        this.setupDragDrop();
    }

    /**
     * Get default options
     * @returns {Object}
     */
    getDefaultOptions() {
        return {
            ...super.getDefaultOptions(),
            draggable: true,
            expandable: true,
            showMenu: true
        };
    }

    /**
     * Create card element
     */
    create() {
        this.element = this.createElement('div', {
            classes: ['position-card'],
            attributes: {
                'data-position-id': this.position.id,
                'data-symbol': this.position.symbol,
                draggable: this.options.draggable
            }
        });
        
        this.render();
        
        if (this.container) {
            this.container.appendChild(this.element);
        }
    }

    /**
     * Setup event listeners
     */
    setupEventListeners() {
        // Card click event (expand/collapse)
        this.addEventListener(this.element, 'click', (e) => {
            if (!e.target.closest('.action-btn') && 
                !e.target.closest('.menu-btn') && 
                !e.target.closest('input') &&
                this.options.expandable) {
                this.toggleExpanded();
            }
        });

        // Drag and drop events
        if (this.options.draggable) {
            this.addEventListener(this.element, 'dragstart', this.handleDragStart.bind(this));
            this.addEventListener(this.element, 'dragend', this.handleDragEnd.bind(this));
        }

        // Global events
        eventBus.on(`position:update:${this.position.id}`, this.handlePositionUpdate.bind(this));
        eventBus.on(`position:price:${this.position.symbol}`, this.handlePriceUpdate.bind(this));
    }

    /**
     * Render card content
     */
    render() {
        const pnlPercent = this.calculatePnlPercent();
        const pnlClass = this.position.pnl >= 0 ? 'positive' : 'negative';
        const sideClass = this.position.side.toLowerCase();
        
        this.element.innerHTML = `
            <div class="position-card-header">
                <div class="position-symbol">
                    <span class="symbol-name">${this.escapeHtml(this.position.symbol)}</span>
                    <span class="position-side ${sideClass}">${this.escapeHtml(this.position.side)}</span>
                </div>
                ${this.options.showMenu ? this.renderMenu() : ''}
            </div>
            
            <div class="position-metrics">
                <div class="metric-row">
                    <div class="metric">
                        <span class="metric-label">크기</span>
                        <span class="metric-value">${this.formatNumber(this.position.size)}</span>
                    </div>
                    <div class="metric">
                        <span class="metric-label">진입가</span>
                        <span class="metric-value">${this.formatCurrency(this.position.entry_price)}</span>
                    </div>
                </div>
                
                <div class="metric-row">
                    <div class="metric">
                        <span class="metric-label">현재가</span>
                        <span class="metric-value current-price">
                            ${this.formatCurrency(this.position.current_price)}
                        </span>
                    </div>
                    <div class="metric">
                        <span class="metric-label">손익률</span>
                        <span class="metric-value pnl-percent ${pnlClass}">
                            ${pnlPercent >= 0 ? '+' : ''}${pnlPercent.toFixed(2)}%
                        </span>
                    </div>
                </div>
                
                <div class="pnl-section">
                    <div class="pnl-amount ${pnlClass}">
                        ${this.formatCurrency(this.position.pnl)}
                    </div>
                    <div class="pnl-bar">
                        <div class="pnl-fill ${pnlClass}" style="width: ${Math.min(Math.abs(pnlPercent) * 2, 100)}%"></div>
                    </div>
                </div>
            </div>
            
            <div class="position-controls">
                ${this.renderEditSection()}
                ${this.renderActionButtons()}
            </div>
            
            <div class="position-footer">
                <div class="position-time">
                    <i class="fas fa-clock"></i>
                    ${this.formatRelativeTime(this.position.entry_time)}
                </div>
                <div class="position-status">
                    ${this.getPositionStatusBadge()}
                </div>
            </div>
        `;

        this.bindActionEvents();
    }

    /**
     * Render menu dropdown
     * @returns {string} Menu HTML
     */
    renderMenu() {
        return `
            <div class="position-menu">
                <button class="menu-btn" type="button">
                    <i class="fas fa-ellipsis-v"></i>
                </button>
                <div class="position-menu-dropdown" style="display: none;">
                    <button class="menu-item edit-btn" type="button">
                        <i class="fas fa-edit"></i> 수정
                    </button>
                    <button class="menu-item duplicate-btn" type="button">
                        <i class="fas fa-copy"></i> 복제
                    </button>
                    <button class="menu-item danger close-btn" type="button">
                        <i class="fas fa-times"></i> 종료
                    </button>
                </div>
            </div>
        `;
    }

    /**
     * Render edit section
     * @returns {string} Edit section HTML
     */
    renderEditSection() {
        return `
            <div class="stop-loss-section ${this.isEditing ? 'active' : ''}" data-section="edit">
                <div class="input-group">
                    <label>손절가</label>
                    <input type="number" class="stop-loss-input" 
                           value="${this.position.stop_loss || ''}" 
                           placeholder="손절가 입력" 
                           step="0.01">
                </div>
                <div class="input-group">
                    <label>익절가</label>
                    <input type="number" class="take-profit-input" 
                           value="${this.position.take_profit || ''}" 
                           placeholder="익절가 입력" 
                           step="0.01">
                </div>
                <div class="edit-actions">
                    <button class="btn btn-secondary cancel-edit-btn" type="button">취소</button>
                    <button class="btn btn-primary save-edit-btn" type="button">저장</button>
                </div>
            </div>
        `;
    }

    /**
     * Render action buttons
     * @returns {string} Action buttons HTML
     */
    renderActionButtons() {
        return `
            <div class="action-buttons ${this.isEditing ? 'hidden' : ''}" data-section="actions">
                <button class="action-btn primary toggle-edit-btn" type="button">
                    <i class="fas fa-edit"></i>
                    수정
                </button>
                <button class="action-btn warning partial-close-btn" type="button" data-percent="50">
                    <i class="fas fa-percentage"></i>
                    50%
                </button>
                <button class="action-btn danger confirm-close-btn" type="button">
                    <i class="fas fa-times"></i>
                    종료
                </button>
            </div>
        `;
    }

    /**
     * Bind action button events
     */
    bindActionEvents() {
        // Menu toggle
        const menuBtn = this.find('.menu-btn');
        const menuDropdown = this.find('.position-menu-dropdown');
        if (menuBtn && menuDropdown) {
            this.addEventListener(menuBtn, 'click', (e) => {
                e.stopPropagation();
                this.toggleMenu();
            });
        }

        // Menu items
        this.bindMenuActions();
        
        // Edit actions
        this.bindEditActions();

        // Action buttons
        this.bindMainActions();
    }

    /**
     * Bind menu actions
     */
    bindMenuActions() {
        const editBtn = this.find('.menu-item.edit-btn');
        const duplicateBtn = this.find('.menu-item.duplicate-btn');
        const closeBtn = this.find('.menu-item.close-btn');

        if (editBtn) {
            this.addEventListener(editBtn, 'click', () => {
                this.toggleEdit();
                this.toggleMenu();
            });
        }

        if (duplicateBtn) {
            this.addEventListener(duplicateBtn, 'click', () => {
                this.duplicatePosition();
                this.toggleMenu();
            });
        }

        if (closeBtn) {
            this.addEventListener(closeBtn, 'click', () => {
                this.confirmClosePosition();
                this.toggleMenu();
            });
        }
    }

    /**
     * Bind edit actions
     */
    bindEditActions() {
        const cancelBtn = this.find('.cancel-edit-btn');
        const saveBtn = this.find('.save-edit-btn');

        if (cancelBtn) {
            this.addEventListener(cancelBtn, 'click', () => this.cancelEdit());
        }

        if (saveBtn) {
            this.addEventListener(saveBtn, 'click', () => this.saveEdit());
        }
    }

    /**
     * Bind main actions
     */
    bindMainActions() {
        const toggleEditBtn = this.find('.toggle-edit-btn');
        const partialCloseBtn = this.find('.partial-close-btn');
        const confirmCloseBtn = this.find('.confirm-close-btn');

        if (toggleEditBtn) {
            this.addEventListener(toggleEditBtn, 'click', () => this.toggleEdit());
        }

        if (partialCloseBtn) {
            this.addEventListener(partialCloseBtn, 'click', () => {
                const percent = parseInt(partialCloseBtn.dataset.percent);
                this.partialClose(percent);
            });
        }

        if (confirmCloseBtn) {
            this.addEventListener(confirmCloseBtn, 'click', () => this.confirmClosePosition());
        }
    }

    /**
     * Update position data
     * @param {Object} newPosition - New position data
     */
    update(newPosition) {
        const oldPnl = this.position.pnl;
        this.position = { ...this.position, ...newPosition };
        
        // Update real-time elements
        this.updatePrice();
        this.updatePnl();
        
        // Flash effect on PnL change
        if (oldPnl !== this.position.pnl) {
            this.flashChange(this.position.pnl > oldPnl);
        }

        // Emit update event
        this.emit('updated', { position: this.position, oldPnl });
    }

    /**
     * Update price display
     */
    updatePrice() {
        const priceElement = this.find('.current-price');
        if (priceElement) {
            priceElement.textContent = this.formatCurrency(this.position.current_price);
        }
    }

    /**
     * Update PnL display
     */
    updatePnl() {
        const pnlElement = this.find('.pnl-amount');
        const pnlPercentElement = this.find('.pnl-percent');
        const pnlBar = this.find('.pnl-fill');
        
        if (pnlElement) {
            const pnlClass = this.position.pnl >= 0 ? 'positive' : 'negative';
            pnlElement.className = `pnl-amount ${pnlClass}`;
            pnlElement.textContent = this.formatCurrency(this.position.pnl);
            
            // Update PnL percentage
            if (pnlPercentElement) {
                const pnlPercent = this.calculatePnlPercent();
                pnlPercentElement.className = `metric-value pnl-percent ${pnlClass}`;
                pnlPercentElement.textContent = `${pnlPercent >= 0 ? '+' : ''}${pnlPercent.toFixed(2)}%`;
            }
            
            // Update PnL bar
            if (pnlBar) {
                const pnlPercent = this.calculatePnlPercent();
                pnlBar.className = `pnl-fill ${pnlClass}`;
                pnlBar.style.width = `${Math.min(Math.abs(pnlPercent) * 2, 100)}%`;
            }
        }
    }

    /**
     * Flash change effect
     * @param {boolean} isProfit - Whether change is profitable
     */
    flashChange(isProfit) {
        const flashClass = isProfit ? 'flash-profit' : 'flash-loss';
        this.element.classList.add(flashClass);
        setTimeout(() => {
            this.element.classList.remove(flashClass);
        }, 1000);
    }

    /**
     * Toggle menu visibility
     */
    toggleMenu() {
        const menuDropdown = this.find('.position-menu-dropdown');
        if (menuDropdown) {
            const isVisible = menuDropdown.style.display !== 'none';
            menuDropdown.style.display = isVisible ? 'none' : 'block';
            
            // Close other open menus
            if (!isVisible) {
                eventBus.emit('position:menu:opened', { positionId: this.position.id });
            }
        }
    }

    /**
     * Toggle expanded state
     */
    toggleExpanded() {
        this.element.classList.toggle('expanded');
        this.emit('expanded', { 
            positionId: this.position.id, 
            expanded: this.element.classList.contains('expanded') 
        });
    }

    /**
     * Toggle edit mode
     */
    toggleEdit() {
        this.isEditing = !this.isEditing;
        
        const editSection = this.find('[data-section="edit"]');
        const actionsSection = this.find('[data-section="actions"]');
        
        if (editSection) {
            editSection.classList.toggle('active', this.isEditing);
        }
        
        if (actionsSection) {
            actionsSection.classList.toggle('hidden', this.isEditing);
        }

        this.emit('editToggled', { positionId: this.position.id, editing: this.isEditing });
    }

    /**
     * Cancel edit mode
     */
    cancelEdit() {
        this.toggleEdit();
        
        // Reset input values
        const stopLossInput = this.find('.stop-loss-input');
        const takeProfitInput = this.find('.take-profit-input');
        
        if (stopLossInput) {
            stopLossInput.value = this.position.stop_loss || '';
        }
        
        if (takeProfitInput) {
            takeProfitInput.value = this.position.take_profit || '';
        }

        this.emit('editCancelled', { positionId: this.position.id });
    }

    /**
     * Save edit changes
     */
    async saveEdit() {
        const stopLossInput = this.find('.stop-loss-input');
        const takeProfitInput = this.find('.take-profit-input');
        
        const data = {
            stop_loss: stopLossInput?.value ? parseFloat(stopLossInput.value) : null,
            take_profit: takeProfitInput?.value ? parseFloat(takeProfitInput.value) : null
        };

        try {
            const response = await fetch(`/api/positions/${this.position.id}/update`, {
                method: 'PUT',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify(data)
            });

            if (!response.ok) {
                throw new Error(`HTTP ${response.status}: ${response.statusText}`);
            }

            const result = await response.json();
            
            // Update position data
            this.position = { ...this.position, ...data };
            
            this.toggleEdit();
            this.showToast('포지션이 성공적으로 수정되었습니다', 'success');
            
            this.emit('editSaved', { 
                positionId: this.position.id, 
                changes: data,
                result 
            });

        } catch (error) {
            console.error('포지션 수정 실패:', error);
            this.showToast('포지션 수정에 실패했습니다', 'error');
            
            this.emit('editError', { 
                positionId: this.position.id, 
                error: error.message 
            });
        }
    }

    /**
     * Duplicate position
     */
    duplicatePosition() {
        this.showToast('포지션 복제 기능은 곧 추가될 예정입니다', 'info');
        this.emit('duplicateRequested', { positionId: this.position.id });
    }

    /**
     * Partial close position
     * @param {number} percentage - Percentage to close
     */
    async partialClose(percentage) {
        try {
            const response = await fetch(`/api/positions/${this.position.id}/partial-close`, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ percentage })
            });

            if (!response.ok) {
                throw new Error(`HTTP ${response.status}: ${response.statusText}`);
            }

            const result = await response.json();
            this.showToast(`포지션의 ${percentage}%가 종료되었습니다`, 'success');
            
            this.emit('partialClosed', { 
                positionId: this.position.id, 
                percentage,
                result 
            });

        } catch (error) {
            console.error('부분 종료 실패:', error);
            this.showToast('부분 종료에 실패했습니다', 'error');
            
            this.emit('partialCloseError', { 
                positionId: this.position.id, 
                error: error.message 
            });
        }
    }

    /**
     * Confirm close position
     */
    confirmClosePosition() {
        eventBus.emit('modal:confirm', {
            title: '포지션 종료 확인',
            message: '정말로 이 포지션을 종료하시겠습니까?',
            onConfirm: () => this.closePosition()
        });
    }

    /**
     * Close position
     */
    async closePosition() {
        try {
            const response = await fetch(`/api/positions/${this.position.id}/close`, {
                method: 'POST'
            });

            if (!response.ok) {
                throw new Error(`HTTP ${response.status}: ${response.statusText}`);
            }

            const result = await response.json();
            this.showToast('포지션이 성공적으로 종료되었습니다', 'success');
            
            this.emit('closed', { 
                positionId: this.position.id, 
                result 
            });

        } catch (error) {
            console.error('포지션 종료 실패:', error);
            this.showToast('포지션 종료에 실패했습니다', 'error');
            
            this.emit('closeError', { 
                positionId: this.position.id, 
                error: error.message 
            });
        }
    }

    // Event handlers

    /**
     * Handle position update from store
     * @param {Object} data - Update data
     */
    handlePositionUpdate(data) {
        if (data.positionId === this.position.id) {
            this.update(data.position);
        }
    }

    /**
     * Handle price update
     * @param {Object} data - Price data
     */
    handlePriceUpdate(data) {
        if (data.symbol === this.position.symbol) {
            const updatedPosition = {
                ...this.position,
                current_price: data.price,
                pnl: (data.price - this.position.entry_price) * this.position.size
            };
            this.update(updatedPosition);
        }
    }

    /**
     * Handle drag start
     * @param {DragEvent} e - Drag event
     */
    handleDragStart(e) {
        this.isDragging = true;
        e.dataTransfer.setData('text/plain', this.position.id);
        this.element.classList.add('dragging');
        
        this.emit('dragStart', { positionId: this.position.id });
    }

    /**
     * Setup drag and drop functionality
     */
    setupDragDrop() {
        if (!this.options.draggable) return;
        
        // Register with drag drop manager
        dragDropManager.registerDragElement(this.element, {
            type: 'position-card',
            data: {
                positionId: this.position.id,
                symbol: this.position.symbol,
                side: this.position.side,
                size: this.position.size,
                pnl: this.position.pnl
            },
            accessibleName: `${this.position.symbol} ${this.position.side} 포지션`,
            onDragStart: this.onDragStartCustom.bind(this),
            onDragEnd: this.onDragEndCustom.bind(this)
        });
        
        // Add drag handle if specified
        if (this.options.dragHandle) {
            const handle = this.find(this.options.dragHandle);
            if (handle) {
                this.dragHandle = handle;
                handle.classList.add('drag-handle');
                handle.setAttribute('aria-label', '드래그 핸들');
            }
        }
    }
    
    /**
     * Custom drag start handler
     * @param {HTMLElement} element - Dragged element
     * @param {DragEvent} event - Drag event
     */
    onDragStartCustom(element, event) {
        this.isDragging = true;
        this.element.classList.add('dragging');
        
        // Add dragging class to parent container
        const container = this.element.closest('.positions-grid, .positions-list');
        if (container) {
            container.classList.add('drag-active');
        }
        
        // Store original position for cancel operation
        this.originalParent = this.element.parentNode;
        this.originalNextSibling = this.element.nextSibling;
        
        this.emit('dragStart', { 
            positionId: this.position.id, 
            position: this.position 
        });
    }
    
    /**
     * Custom drag end handler
     * @param {HTMLElement} element - Dragged element
     */
    onDragEndCustom(element) {
        this.isDragging = false;
        this.element.classList.remove('dragging');
        
        // Remove dragging class from parent container
        const container = this.element.closest('.positions-grid, .positions-list');
        if (container) {
            container.classList.remove('drag-active');
        }
        
        this.emit('dragEnd', { 
            positionId: this.position.id,
            newIndex: this.getIndexInParent()
        });
    }
    
    /**
     * Get index in parent container
     * @returns {number} Index
     */
    getIndexInParent() {
        if (!this.element.parentNode) return -1;
        return Array.from(this.element.parentNode.children).indexOf(this.element);
    }

    /**
     * Handle drag end (legacy - keeping for compatibility)
     */
    handleDragEnd() {
        this.isDragging = false;
        this.element.classList.remove('dragging');
        
        this.emit('dragEnd', { positionId: this.position.id });
    }

    // Utility methods

    /**
     * Calculate PnL percentage
     * @returns {number} PnL percentage
     */
    calculatePnlPercent() {
        if (this.position.entry_price === 0) return 0;
        return ((this.position.current_price - this.position.entry_price) / this.position.entry_price) * 100;
    }

    /**
     * Get position status badge
     * @returns {string} Status badge HTML
     */
    getPositionStatusBadge() {
        const pnlPercent = this.calculatePnlPercent();
        
        if (Math.abs(pnlPercent) < 1) {
            return '<span class="status-badge neutral">안정</span>';
        } else if (pnlPercent > 5) {
            return '<span class="status-badge success">수익</span>';
        } else if (pnlPercent < -5) {
            return '<span class="status-badge danger">손실</span>';
        } else {
            return '<span class="status-badge warning">변동</span>';
        }
    }

    /**
     * Format currency value
     * @param {number} amount - Amount to format
     * @returns {string} Formatted currency
     */
    formatCurrency(amount) {
        return new Intl.NumberFormat('ko-KR', {
            style: 'currency',
            currency: 'USD',
            minimumFractionDigits: 2,
            maximumFractionDigits: 2
        }).format(amount);
    }

    /**
     * Format number
     * @param {number} number - Number to format
     * @returns {string} Formatted number
     */
    formatNumber(number) {
        return new Intl.NumberFormat('ko-KR', {
            minimumFractionDigits: 0,
            maximumFractionDigits: 4
        }).format(number);
    }

    /**
     * Format relative time
     * @param {string|number} timestamp - Timestamp
     * @returns {string} Relative time string
     */
    formatRelativeTime(timestamp) {
        const now = new Date();
        const time = new Date(timestamp);
        const diffMs = now - time;
        const diffMins = Math.floor(diffMs / 60000);
        const diffHours = Math.floor(diffMs / 3600000);
        const diffDays = Math.floor(diffMs / 86400000);

        if (diffMins < 1) return '방금 전';
        if (diffMins < 60) return `${diffMins}분 전`;
        if (diffHours < 24) return `${diffHours}시간 전`;
        return `${diffDays}일 전`;
    }

    /**
     * Show toast notification
     * @param {string} message - Message to show
     * @param {string} type - Toast type
     */
    showToast(message, type = 'info') {
        eventBus.emit('toast:show', {
            message,
            type,
            duration: 3000
        });
    }

    /**
     * Cleanup when component is destroyed
     */
    destroy() {
        // Remove event listeners
        eventBus.off(`position:update:${this.position.id}`, this.handlePositionUpdate);
        eventBus.off(`position:price:${this.position.symbol}`, this.handlePriceUpdate);
        
        // Remove DOM element
        if (this.element && this.element.parentNode) {
            this.element.parentNode.removeChild(this.element);
        }
        
        super.destroy();
        
        this.emit('destroyed', { positionId: this.position.id });
    }
}

/**
 * Position Card Manager
 * Manages multiple position cards
 */
export class PositionCardManager {
    constructor(containerId, options = {}) {
        this.container = typeof containerId === 'string' 
            ? document.getElementById(containerId) 
            : containerId;
            
        this.cards = new Map();
        this.options = {
            sortBy: 'symbol',
            filterBy: 'all',
            enableDragDrop: true,
            ...options
        };
        
        if (this.options.enableDragDrop) {
            this.setupDragAndDrop();
            // Load saved card order
            setTimeout(() => this.loadCardOrder(), 100);
        }
        
        this.setupEventListeners();
    }

    /**
     * Setup event listeners
     */
    setupEventListeners() {
        // Close other menus when one opens
        eventBus.on('position:menu:opened', (data) => {
            this.cards.forEach((card, positionId) => {
                if (positionId !== data.positionId) {
                    const menuDropdown = card.find('.position-menu-dropdown');
                    if (menuDropdown) {
                        menuDropdown.style.display = 'none';
                    }
                }
            });
        });

        // Handle card events
        eventBus.on('position:card:*', this.handleCardEvent.bind(this));
    }

    /**
     * Handle card events
     * @param {Object} data - Event data
     */
    handleCardEvent(data) {
        // Relay card events with manager context
        eventBus.emit(`position:manager:${data.type}`, {
            ...data,
            manager: this
        });
    }

    /**
     * Add position
     * @param {Object} position - Position data
     * @returns {PositionCard} Created card
     */
    addPosition(position) {
        if (this.cards.has(position.id)) {
            return this.updatePosition(position.id, position);
        }

        const card = new PositionCard(this.container, position);
        this.cards.set(position.id, card);
        
        // Subscribe to card events
        card.on('*', (eventData) => {
            eventBus.emit(`position:card:${eventData.type}`, eventData.data);
        });
        
        this.resort();
        
        eventBus.emit('position:manager:added', { 
            positionId: position.id, 
            card 
        });
        
        return card;
    }

    /**
     * Update position
     * @param {string} positionId - Position ID
     * @param {Object} newData - New position data
     * @returns {PositionCard|null} Updated card
     */
    updatePosition(positionId, newData) {
        const card = this.cards.get(positionId);
        if (card) {
            card.update(newData);
            eventBus.emit('position:manager:updated', { 
                positionId, 
                newData, 
                card 
            });
            return card;
        }
        return null;
    }

    /**
     * Remove position
     * @param {string} positionId - Position ID
     * @returns {boolean} Success status
     */
    removePosition(positionId) {
        const card = this.cards.get(positionId);
        if (card) {
            card.destroy();
            this.cards.delete(positionId);
            
            eventBus.emit('position:manager:removed', { 
                positionId, 
                card 
            });
            return true;
        }
        return false;
    }

    /**
     * Update all positions
     * @param {Array} positions - Array of position data
     */
    updateAllPositions(positions) {
        const currentIds = new Set(this.cards.keys());
        const newIds = new Set(positions.map(p => p.id));

        // Remove positions that no longer exist
        currentIds.forEach(id => {
            if (!newIds.has(id)) {
                this.removePosition(id);
            }
        });

        // Add or update positions
        positions.forEach(position => {
            if (this.cards.has(position.id)) {
                this.updatePosition(position.id, position);
            } else {
                this.addPosition(position);
            }
        });

        this.resort();
        
        eventBus.emit('position:manager:batch_updated', { 
            positions, 
            totalCards: this.cards.size 
        });
    }

    /**
     * Set sort criteria
     * @param {string} sortBy - Sort field
     */
    setSortBy(sortBy) {
        this.options.sortBy = sortBy;
        this.resort();
        
        eventBus.emit('position:manager:sorted', { 
            sortBy, 
            cardCount: this.cards.size 
        });
    }

    /**
     * Set filter criteria
     * @param {string} filterBy - Filter value
     */
    setFilterBy(filterBy) {
        this.options.filterBy = filterBy;
        this.refilter();
        
        const visibleCount = Array.from(this.cards.values())
            .filter(card => card.element.style.display !== 'none').length;
            
        eventBus.emit('position:manager:filtered', { 
            filterBy, 
            visibleCount, 
            totalCount: this.cards.size 
        });
    }

    /**
     * Resort cards
     */
    resort() {
        const cards = Array.from(this.cards.values());
        
        cards.sort((a, b) => {
            switch (this.options.sortBy) {
                case 'pnl':
                    return b.position.pnl - a.position.pnl;
                case 'size':
                    return (b.position.size * b.position.current_price) - 
                           (a.position.size * a.position.current_price);
                case 'time':
                    return new Date(b.position.entry_time) - new Date(a.position.entry_time);
                default: // symbol
                    return a.position.symbol.localeCompare(b.position.symbol);
            }
        });

        // Reorder DOM elements
        cards.forEach(card => {
            if (this.container && card.element) {
                this.container.appendChild(card.element);
            }
        });
    }

    /**
     * Refilter cards
     */
    refilter() {
        this.cards.forEach(card => {
            const shouldShow = this.options.filterBy === 'all' || 
                             card.position.symbol.includes(this.options.filterBy);
            card.element.style.display = shouldShow ? 'block' : 'none';
        });
    }

    /**
     * Setup drag and drop functionality
     */
    setupDragAndDrop() {
        if (!this.container) return;

        // Register container as drop zone
        dragDropManager.registerDropZone(this.container, {
            accepts: ['position-card'],
            sortable: true,
            onDragEnter: this.onDragEnterContainer.bind(this),
            onDragOver: this.onDragOverContainer.bind(this),
            onDragLeave: this.onDragLeaveContainer.bind(this),
            onDrop: this.onDropContainer.bind(this)
        });
    }
    
    /**
     * Handle drag enter on container
     * @param {DragEvent} event - Drag event
     * @param {Object} dragData - Drag data
     */
    onDragEnterContainer(event, dragData) {
        this.container.classList.add('drop-zone-active');
    }
    
    /**
     * Handle drag over on container
     * @param {DragEvent} event - Drag event
     * @param {Object} dragData - Drag data
     */
    onDragOverContainer(event, dragData) {
        // Visual feedback is handled by DragDropManager
    }
    
    /**
     * Handle drag leave on container
     * @param {DragEvent} event - Drag event
     * @param {Object} dragData - Drag data
     */
    onDragLeaveContainer(event, dragData) {
        this.container.classList.remove('drop-zone-active');
    }
    
    /**
     * Handle drop on container
     * @param {DragEvent} event - Drop event
     * @param {Object} dragData - Drag data
     * @param {HTMLElement} dropZone - Drop zone
     */
    onDropContainer(event, dragData, dropZone) {
        this.container.classList.remove('drop-zone-active');
        
        const positionId = dragData.data.positionId;
        const newIndex = this.getCardIndex(positionId);
        
        eventBus.emit('position:manager:reordered', { 
            positionId, 
            newIndex,
            oldIndex: dragData.originalIndex || -1
        });
        
        // Save new order to storage
        this.saveCardOrder();
    }
    
    /**
     * Save card order to localStorage
     */
    saveCardOrder() {
        const order = Array.from(this.container.children)
            .filter(child => child.classList.contains('position-card'))
            .map(child => child.dataset.positionId);
            
        localStorage.setItem('position-card-order', JSON.stringify(order));
    }
    
    /**
     * Load card order from localStorage
     */
    loadCardOrder() {
        try {
            const savedOrder = localStorage.getItem('position-card-order');
            if (savedOrder) {
                const order = JSON.parse(savedOrder);
                this.reorderCards(order);
            }
        } catch (error) {
            console.warn('Failed to load card order:', error);
        }
    }
    
    /**
     * Reorder cards based on array
     * @param {Array} order - Array of position IDs
     */
    reorderCards(order) {
        const cardElements = new Map();
        
        // Collect all card elements
        this.cards.forEach((card, positionId) => {
            cardElements.set(positionId, card.element);
        });
        
        // Reorder based on saved order
        order.forEach(positionId => {
            const element = cardElements.get(positionId);
            if (element && this.container.contains(element)) {
                this.container.appendChild(element);
            }
        });
        
        // Append any cards not in the saved order
        cardElements.forEach((element, positionId) => {
            if (!order.includes(positionId) && this.container.contains(element)) {
                this.container.appendChild(element);
            }
        });
    }

    /**
     * Get card index
     * @param {string} positionId - Position ID
     * @returns {number} Card index
     */
    getCardIndex(positionId) {
        const card = this.cards.get(positionId);
        if (!card) return -1;

        const cards = [...this.container.children];
        return cards.indexOf(card.element);
    }

    /**
     * Get all cards
     * @returns {Map} Cards map
     */
    getAllCards() {
        return new Map(this.cards);
    }

    /**
     * Get card by position ID
     * @param {string} positionId - Position ID
     * @returns {PositionCard|undefined} Position card
     */
    getCard(positionId) {
        return this.cards.get(positionId);
    }

    /**
     * Clear all cards
     */
    clear() {
        this.cards.forEach(card => card.destroy());
        this.cards.clear();
        
        eventBus.emit('position:manager:cleared');
    }

    /**
     * Destroy manager
     */
    destroy() {
        this.clear();
        eventBus.off('position:menu:opened');
        eventBus.off('position:card:*');
    }
}

// Export for global access if needed
if (typeof window !== 'undefined') {
    window.PositionCard = PositionCard;
    window.PositionCardManager = PositionCardManager;
}
// 📋 Position Card Component

class PositionCard {
    constructor(position, container) {
        this.position = position;
        this.container = container;
        this.element = null;
        this.isEditing = false;
        
        this.create();
    }

    create() {
        this.element = document.createElement('div');
        this.element.className = 'position-card';
        this.element.dataset.positionId = this.position.id;
        this.element.dataset.symbol = this.position.symbol;
        
        this.render();
        this.bindEvents();
        
        if (this.container) {
            this.container.appendChild(this.element);
        }
    }

    render() {
        const pnlPercent = this.calculatePnlPercent();
        const pnlClass = this.position.pnl >= 0 ? 'positive' : 'negative';
        const sideClass = this.position.side.toLowerCase();
        
        this.element.innerHTML = `
            <div class="position-card-header">
                <div class="position-symbol">
                    <span class="symbol-name">${this.position.symbol}</span>
                    <span class="position-side ${sideClass}">${this.position.side}</span>
                </div>
                <div class="position-menu">
                    <button class="menu-btn" onclick="togglePositionMenu('${this.position.id}')">
                        <i class="fas fa-ellipsis-v"></i>
                    </button>
                    <div class="position-menu-dropdown" id="menu-${this.position.id}" style="display: none;">
                        <button class="menu-item" onclick="editPosition('${this.position.id}')">
                            <i class="fas fa-edit"></i> 수정
                        </button>
                        <button class="menu-item" onclick="duplicatePosition('${this.position.id}')">
                            <i class="fas fa-copy"></i> 복제
                        </button>
                        <button class="menu-item danger" onclick="closePosition('${this.position.id}')">
                            <i class="fas fa-times"></i> 종료
                        </button>
                    </div>
                </div>
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
                        <span class="metric-value" id="current-price-${this.position.id}">
                            ${this.formatCurrency(this.position.current_price)}
                        </span>
                    </div>
                    <div class="metric">
                        <span class="metric-label">손익률</span>
                        <span class="metric-value ${pnlClass}">
                            ${pnlPercent >= 0 ? '+' : ''}${pnlPercent.toFixed(2)}%
                        </span>
                    </div>
                </div>
                
                <div class="pnl-section">
                    <div class="pnl-amount ${pnlClass}" id="pnl-${this.position.id}">
                        ${this.formatCurrency(this.position.pnl)}
                    </div>
                    <div class="pnl-bar">
                        <div class="pnl-fill ${pnlClass}" style="width: ${Math.min(Math.abs(pnlPercent) * 2, 100)}%"></div>
                    </div>
                </div>
            </div>
            
            <div class="position-controls">
                <div class="stop-loss-section" ${this.isEditing ? '' : 'style="display: none;"'} id="edit-section-${this.position.id}">
                    <div class="input-group">
                        <label>손절가</label>
                        <input type="number" id="stop-loss-${this.position.id}" 
                               value="${this.position.stop_loss || ''}" 
                               placeholder="손절가 입력" 
                               step="0.01">
                    </div>
                    <div class="input-group">
                        <label>익절가</label>
                        <input type="number" id="take-profit-${this.position.id}" 
                               value="${this.position.take_profit || ''}" 
                               placeholder="익절가 입력" 
                               step="0.01">
                    </div>
                    <div class="edit-actions">
                        <button class="btn btn-secondary" onclick="cancelEdit('${this.position.id}')">취소</button>
                        <button class="btn btn-primary" onclick="savePositionEdit('${this.position.id}')">저장</button>
                    </div>
                </div>
                
                <div class="action-buttons" ${this.isEditing ? 'style="display: none;"' : ''} id="actions-${this.position.id}">
                    <button class="action-btn primary" onclick="toggleEdit('${this.position.id}')">
                        <i class="fas fa-edit"></i>
                        수정
                    </button>
                    <button class="action-btn warning" onclick="partialClose('${this.position.id}', 50)">
                        <i class="fas fa-percentage"></i>
                        50%
                    </button>
                    <button class="action-btn danger" onclick="confirmClosePosition('${this.position.id}')">
                        <i class="fas fa-times"></i>
                        종료
                    </button>
                </div>
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
    }

    update(newPosition) {
        const oldPnl = this.position.pnl;
        this.position = { ...this.position, ...newPosition };
        
        // 실시간 업데이트
        this.updatePrice();
        this.updatePnl();
        
        // 가격 변화 플래시 효과
        if (oldPnl !== this.position.pnl) {
            this.flashChange(this.position.pnl > oldPnl);
        }
    }

    updatePrice() {
        const priceElement = document.getElementById(`current-price-${this.position.id}`);
        if (priceElement) {
            priceElement.textContent = this.formatCurrency(this.position.current_price);
        }
    }

    updatePnl() {
        const pnlElement = document.getElementById(`pnl-${this.position.id}`);
        if (pnlElement) {
            const pnlClass = this.position.pnl >= 0 ? 'positive' : 'negative';
            pnlElement.className = `pnl-amount ${pnlClass}`;
            pnlElement.textContent = this.formatCurrency(this.position.pnl);
            
            // 손익률 업데이트
            const pnlPercent = this.calculatePnlPercent();
            const pnlBar = pnlElement.nextElementSibling?.querySelector('.pnl-fill');
            if (pnlBar) {
                pnlBar.className = `pnl-fill ${pnlClass}`;
                pnlBar.style.width = `${Math.min(Math.abs(pnlPercent) * 2, 100)}%`;
            }
        }
    }

    flashChange(isProfit) {
        const flashClass = isProfit ? 'flash-profit' : 'flash-loss';
        this.element.classList.add(flashClass);
        setTimeout(() => {
            this.element.classList.remove(flashClass);
        }, 1000);
    }

    bindEvents() {
        // 카드 클릭 이벤트 (확장/축소)
        this.element.addEventListener('click', (e) => {
            if (!e.target.closest('.action-btn') && !e.target.closest('.menu-btn')) {
                this.toggleExpanded();
            }
        });

        // 드래그 앤 드롭 (정렬용)
        this.element.draggable = true;
        this.element.addEventListener('dragstart', (e) => {
            e.dataTransfer.setData('text/plain', this.position.id);
            this.element.classList.add('dragging');
        });

        this.element.addEventListener('dragend', () => {
            this.element.classList.remove('dragging');
        });
    }

    toggleExpanded() {
        this.element.classList.toggle('expanded');
    }

    toggleEdit() {
        this.isEditing = !this.isEditing;
        const editSection = document.getElementById(`edit-section-${this.position.id}`);
        const actionsSection = document.getElementById(`actions-${this.position.id}`);
        
        if (editSection && actionsSection) {
            editSection.style.display = this.isEditing ? 'block' : 'none';
            actionsSection.style.display = this.isEditing ? 'none' : 'flex';
        }
    }

    calculatePnlPercent() {
        if (this.position.entry_price === 0) return 0;
        return ((this.position.current_price - this.position.entry_price) / this.position.entry_price) * 100;
    }

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

    formatCurrency(amount) {
        return new Intl.NumberFormat('ko-KR', {
            style: 'currency',
            currency: 'USD',
            minimumFractionDigits: 2,
            maximumFractionDigits: 2
        }).format(amount);
    }

    formatNumber(number) {
        return new Intl.NumberFormat('ko-KR', {
            minimumFractionDigits: 0,
            maximumFractionDigits: 4
        }).format(number);
    }

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

    destroy() {
        if (this.element && this.element.parentNode) {
            this.element.parentNode.removeChild(this.element);
        }
    }
}

// 포지션 카드 관리자
class PositionCardManager {
    constructor(containerId) {
        this.container = document.getElementById(containerId);
        this.cards = new Map();
        this.sortBy = 'symbol';
        this.filterBy = 'all';
        
        this.setupDragAndDrop();
    }

    addPosition(position) {
        const card = new PositionCard(position, this.container);
        this.cards.set(position.id, card);
        this.resort();
        return card;
    }

    updatePosition(positionId, newData) {
        const card = this.cards.get(positionId);
        if (card) {
            card.update(newData);
        }
    }

    removePosition(positionId) {
        const card = this.cards.get(positionId);
        if (card) {
            card.destroy();
            this.cards.delete(positionId);
        }
    }

    updateAllPositions(positions) {
        // 기존 카드들과 비교하여 업데이트/추가/제거
        const currentIds = new Set(this.cards.keys());
        const newIds = new Set(positions.map(p => p.id));

        // 제거된 포지션들
        currentIds.forEach(id => {
            if (!newIds.has(id)) {
                this.removePosition(id);
            }
        });

        // 새로운/업데이트된 포지션들
        positions.forEach(position => {
            if (this.cards.has(position.id)) {
                this.updatePosition(position.id, position);
            } else {
                this.addPosition(position);
            }
        });

        this.resort();
    }

    setSortBy(sortBy) {
        this.sortBy = sortBy;
        this.resort();
    }

    setFilterBy(filterBy) {
        this.filterBy = filterBy;
        this.refilter();
    }

    resort() {
        const cards = Array.from(this.cards.values());
        cards.sort((a, b) => {
            switch (this.sortBy) {
                case 'pnl':
                    return b.position.pnl - a.position.pnl;
                case 'size':
                    return (b.position.size * b.position.current_price) - 
                           (a.position.size * a.position.current_price);
                case 'time':
                    return new Date(b.position.entry_time) - new Date(a.position.entry_time);
                default:
                    return a.position.symbol.localeCompare(b.position.symbol);
            }
        });

        // DOM 순서 재정렬
        cards.forEach(card => {
            this.container.appendChild(card.element);
        });
    }

    refilter() {
        this.cards.forEach(card => {
            const shouldShow = this.filterBy === 'all' || 
                             card.position.symbol.includes(this.filterBy);
            card.element.style.display = shouldShow ? 'block' : 'none';
        });
    }

    setupDragAndDrop() {
        this.container.addEventListener('dragover', (e) => {
            e.preventDefault();
            const draggingCard = this.container.querySelector('.dragging');
            const siblings = [...this.container.querySelectorAll('.position-card:not(.dragging)')];
            
            const nextSibling = siblings.find(sibling => {
                return e.clientY <= sibling.getBoundingClientRect().top + sibling.offsetHeight / 2;
            });
            
            this.container.insertBefore(draggingCard, nextSibling);
        });
    }
}

// 전역 함수들 (HTML에서 호출)
function togglePositionMenu(positionId) {
    const menu = document.getElementById(`menu-${positionId}`);
    if (menu) {
        menu.style.display = menu.style.display === 'none' ? 'block' : 'none';
    }
}

function editPosition(positionId) {
    toggleEdit(positionId);
    togglePositionMenu(positionId);
}

function duplicatePosition(positionId) {
    // 포지션 복제 로직
    if (window.dashboard) {
        dashboard.showToast('포지션 복제 기능은 곧 추가될 예정입니다', 'info');
    }
    togglePositionMenu(positionId);
}

function toggleEdit(positionId) {
    const editSection = document.getElementById(`edit-section-${positionId}`);
    const actionsSection = document.getElementById(`actions-${positionId}`);
    
    if (editSection && actionsSection) {
        const isEditing = editSection.style.display !== 'none';
        editSection.style.display = isEditing ? 'none' : 'block';
        actionsSection.style.display = isEditing ? 'flex' : 'none';
    }
}

function cancelEdit(positionId) {
    toggleEdit(positionId);
}

async function savePositionEdit(positionId) {
    const stopLossInput = document.getElementById(`stop-loss-${positionId}`);
    const takeProfitInput = document.getElementById(`take-profit-${positionId}`);
    
    const data = {
        stop_loss: stopLossInput.value ? parseFloat(stopLossInput.value) : null,
        take_profit: takeProfitInput.value ? parseFloat(takeProfitInput.value) : null
    };

    try {
        const response = await fetch(`/api/positions/${positionId}/update`, {
            method: 'PUT',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(data)
        });

        if (response.ok) {
            if (window.dashboard) {
                dashboard.showToast('포지션이 성공적으로 수정되었습니다', 'success');
            }
            toggleEdit(positionId);
        } else {
            throw new Error('포지션 수정 실패');
        }
    } catch (error) {
        if (window.dashboard) {
            dashboard.showToast('포지션 수정에 실패했습니다', 'error');
        }
    }
}

function confirmClosePosition(positionId) {
    if (window.showConfirmModal) {
        showConfirmModal(
            '포지션 종료 확인',
            '정말로 이 포지션을 종료하시겠습니까?',
            () => closePosition(positionId)
        );
    } else {
        closePosition(positionId);
    }
}
/**
 * @fileoverview 자본 추적 컴포넌트
 * @description 33% 할당 한도 실시간 모니터링 컴포넌트
 */

import { BaseComponent } from './BaseComponent.js';
import { eventBus } from '../core/EventBus.js';
import { apiService } from '../services/ApiService.js';

/**
 * 자본 추적 컴포넌트
 * @class CapitalTracker
 * @extends BaseComponent
 */
export class CapitalTracker extends BaseComponent {
    constructor(container) {
        super(container);
        
        this.data = {
            totalBalance: 0,
            usedCapital: 0,
            allocationPercentage: 0,
            availableCapital: 0,
            btcAllocation: 0,
            ethAllocation: 0,
            withinLimit: true,
            positions: [],
            lastUpdate: null
        };
        
        // 업데이트 설정
        this.updateInterval = 10000; // 10초마다 업데이트
        this.updateTimer = null;
        
        // 알림 설정
        this.alertThresholds = {
            warning: 0.25,   // 25%
            danger: 0.30,    // 30%
            critical: 0.32   // 32%
        };
        
        this.lastAlertLevel = null;
        
        this.render();
        this.bindEvents();
        this.startAutoUpdate();
    }

    /**
     * 컴포넌트 렌더링
     */
    render() {
        const alertLevel = this.getAlertLevel();
        const alertClass = alertLevel ? `alert-${alertLevel}` : '';
        
        this.container.innerHTML = `
            <div class="capital-tracker ${alertClass}">
                <div class="capital-header">
                    <h3>
                        <span class="icon">🏦</span>
                        자본 추적 시스템
                        <span class="status-indicator ${this.data.withinLimit ? 'safe' : 'danger'}">
                            ${this.data.withinLimit ? '✅' : '⚠️'}
                        </span>
                    </h3>
                    <div class="last-update">
                        마지막 업데이트: ${this.formatTime(this.data.lastUpdate)}
                    </div>
                </div>

                <div class="allocation-overview">
                    <div class="allocation-chart">
                        <div class="progress-ring">
                            <svg class="progress-ring-svg" width="120" height="120">
                                <circle
                                    class="progress-ring-circle-bg"
                                    stroke="#e6e6e6"
                                    stroke-width="8"
                                    fill="transparent"
                                    r="52"
                                    cx="60"
                                    cy="60"
                                />
                                <circle
                                    class="progress-ring-circle"
                                    stroke="${this.getProgressColor()}"
                                    stroke-width="8"
                                    fill="transparent"
                                    r="52"
                                    cx="60"
                                    cy="60"
                                    stroke-dasharray="${this.getCircumference()}"
                                    stroke-dashoffset="${this.getStrokeOffset()}"
                                    stroke-linecap="round"
                                />
                            </svg>
                            <div class="progress-text">
                                <div class="percentage">${(this.data.allocationPercentage * 100).toFixed(1)}%</div>
                                <div class="limit">/ 33%</div>
                            </div>
                        </div>
                    </div>

                    <div class="allocation-details">
                        <div class="detail-item">
                            <span class="label">총 잔고</span>
                            <span class="value">${this.formatCurrency(this.data.totalBalance)}</span>
                        </div>
                        <div class="detail-item">
                            <span class="label">사용 중</span>
                            <span class="value">${this.formatCurrency(this.data.usedCapital)}</span>
                        </div>
                        <div class="detail-item">
                            <span class="label">사용 가능</span>
                            <span class="value ${this.data.availableCapital > 0 ? 'positive' : 'negative'}">
                                ${this.formatCurrency(this.data.availableCapital)}
                            </span>
                        </div>
                    </div>
                </div>

                <div class="symbol-allocations">
                    <h4>심볼별 할당</h4>
                    <div class="symbol-grid">
                        <div class="symbol-card btc">
                            <div class="symbol-header">
                                <span class="symbol-icon">₿</span>
                                <span class="symbol-name">BTC</span>
                                <span class="target-weight">목표: 70%</span>
                            </div>
                            <div class="symbol-value">${this.formatCurrency(this.data.btcAllocation)}</div>
                            <div class="symbol-percentage">
                                ${(this.data.btcAllocation / Math.max(this.data.usedCapital, 1) * 100).toFixed(1)}%
                            </div>
                        </div>
                        
                        <div class="symbol-card eth">
                            <div class="symbol-header">
                                <span class="symbol-icon">Ξ</span>
                                <span class="symbol-name">ETH</span>
                                <span class="target-weight">목표: 30%</span>
                            </div>
                            <div class="symbol-value">${this.formatCurrency(this.data.ethAllocation)}</div>
                            <div class="symbol-percentage">
                                ${(this.data.ethAllocation / Math.max(this.data.usedCapital, 1) * 100).toFixed(1)}%
                            </div>
                        </div>
                    </div>
                </div>

                <div class="positions-summary">
                    <h4>
                        활성 포지션 (${this.data.positions.length}개)
                        <button class="refresh-btn" id="refresh-capital">🔄</button>
                    </h4>
                    <div class="positions-list">
                        ${this.renderPositions()}
                    </div>
                </div>

                <div class="alert-levels">
                    <div class="alert-level ${this.data.allocationPercentage >= this.alertThresholds.warning ? 'active' : ''}">
                        <span class="alert-icon">⚠️</span>
                        <span class="alert-text">25% 경고</span>
                    </div>
                    <div class="alert-level ${this.data.allocationPercentage >= this.alertThresholds.danger ? 'active' : ''}">
                        <span class="alert-icon">🔶</span>
                        <span class="alert-text">30% 위험</span>
                    </div>
                    <div class="alert-level ${this.data.allocationPercentage >= this.alertThresholds.critical ? 'active' : ''}">
                        <span class="alert-icon">🚨</span>
                        <span class="alert-text">32% 임계</span>
                    </div>
                </div>
            </div>
        `;

        this.addStyles();
    }

    /**
     * 포지션 목록 렌더링
     */
    renderPositions() {
        if (this.data.positions.length === 0) {
            return '<div class="no-positions">활성 포지션 없음</div>';
        }

        return this.data.positions.map(position => `
            <div class="position-item">
                <div class="position-symbol">
                    <span class="symbol">${position.symbol}</span>
                    <span class="side ${position.side}">${position.side === 'long' ? '🟢 롱' : '🔴 숏'}</span>
                </div>
                <div class="position-details">
                    <div class="position-value">${this.formatCurrency(position.market_value)}</div>
                    <div class="position-percentage">${(position.allocation_percentage * 100).toFixed(1)}%</div>
                    <div class="position-leverage">${position.leverage}x</div>
                </div>
            </div>
        `).join('');
    }

    /**
     * 이벤트 바인딩
     */
    bindEvents() {
        // 새로고침 버튼
        this.container.addEventListener('click', (e) => {
            if (e.target.id === 'refresh-capital') {
                this.forceUpdate();
            }
        });

        // 실시간 업데이트 이벤트
        eventBus.on('websocket:balance_update', (data) => {
            this.updateData({ totalBalance: data.total });
        });

        eventBus.on('websocket:position_update', (data) => {
            this.updateFromWebSocket(data);
        });

        eventBus.on('capital:status_update', (data) => {
            this.updateData(data);
        });
    }

    /**
     * 자동 업데이트 시작
     */
    startAutoUpdate() {
        this.updateTimer = setInterval(() => {
            this.loadData();
        }, this.updateInterval);

        // 초기 데이터 로드
        this.loadData();
    }

    /**
     * 데이터 로드 및 업데이트
     */
    async loadData() {
        try {
            const [capitalData, detailedPositions] = await Promise.all([
                apiService.getCapitalTracking(),
                apiService.getDetailedPositions()
            ]);

            this.updateData({
                ...capitalData,
                positions: detailedPositions || [],
                lastUpdate: new Date()
            });

        } catch (error) {
            console.error('자본 추적 데이터 로드 실패:', error);
            this.handleError(error);
        }
    }

    /**
     * 강제 업데이트
     */
    async forceUpdate() {
        try {
            // 서버에서 강제 업데이트 실행
            await apiService.forceCapitalUpdate();
            
            // UI 새로고침 표시
            const refreshBtn = this.container.querySelector('#refresh-capital');
            if (refreshBtn) {
                refreshBtn.textContent = '⟳';
                refreshBtn.style.animation = 'spin 1s linear infinite';
            }

            // 데이터 다시 로드
            await this.loadData();

            // 새로고침 표시 복원
            setTimeout(() => {
                if (refreshBtn) {
                    refreshBtn.textContent = '🔄';
                    refreshBtn.style.animation = 'none';
                }
            }, 1000);

            eventBus.emit('toast:show', {
                message: '자본 추적 데이터 업데이트 완료',
                type: 'success',
                duration: 2000
            });

        } catch (error) {
            console.error('강제 업데이트 실패:', error);
            eventBus.emit('toast:show', {
                message: '업데이트 실패: ' + error.message,
                type: 'error',
                duration: 3000
            });
        }
    }

    /**
     * 데이터 업데이트
     */
    updateData(newData) {
        const oldAllocation = this.data.allocationPercentage;
        
        Object.assign(this.data, newData);

        // 알림 레벨 체크
        this.checkAlertLevel(oldAllocation);

        // 렌더링
        this.render();

        // 이벤트 발생
        eventBus.emit('capital:data_updated', this.data);
    }

    /**
     * WebSocket 데이터 업데이트
     */
    updateFromWebSocket(data) {
        // WebSocket 실시간 데이터로 부분 업데이트
        if (data.type === 'position_update') {
            // 포지션 데이터 업데이트
            this.loadData(); // 전체 새로고침
        }
    }

    /**
     * 알림 레벨 체크
     */
    checkAlertLevel(oldAllocation) {
        const currentLevel = this.getAlertLevel();
        const oldLevel = this.getAlertLevelForValue(oldAllocation);

        if (currentLevel !== oldLevel) {
            this.lastAlertLevel = currentLevel;
            
            if (currentLevel) {
                this.showAllocationAlert(currentLevel);
            } else if (oldLevel) {
                this.showSafeLevelNotification();
            }
        }
    }

    /**
     * 할당 경고 표시
     */
    showAllocationAlert(level) {
        const messages = {
            warning: '⚠️ 자금 할당 25% 경고',
            danger: '🔶 자금 할당 30% 위험 수준',
            critical: '🚨 자금 할당 32% 임계 수준!'
        };

        const types = {
            warning: 'warning',
            danger: 'error',
            critical: 'error'
        };

        eventBus.emit('toast:show', {
            message: messages[level] + ` (현재: ${(this.data.allocationPercentage * 100).toFixed(1)}%)`,
            type: types[level],
            duration: level === 'critical' ? 10000 : 5000
        });
    }

    /**
     * 안전 수준 복귀 알림
     */
    showSafeLevelNotification() {
        eventBus.emit('toast:show', {
            message: '✅ 자금 할당이 안전 수준으로 복귀했습니다',
            type: 'success',
            duration: 3000
        });
    }

    /**
     * 알림 레벨 계산
     */
    getAlertLevel() {
        return this.getAlertLevelForValue(this.data.allocationPercentage);
    }

    /**
     * 값에 대한 알림 레벨 계산
     */
    getAlertLevelForValue(value) {
        if (value >= this.alertThresholds.critical) return 'critical';
        if (value >= this.alertThresholds.danger) return 'danger';
        if (value >= this.alertThresholds.warning) return 'warning';
        return null;
    }

    /**
     * 진행률 색상 계산
     */
    getProgressColor() {
        const level = this.getAlertLevel();
        const colors = {
            critical: '#ff4444',
            danger: '#ff8800',
            warning: '#ffaa00',
            default: '#00aa44'
        };
        return colors[level] || colors.default;
    }

    /**
     * 원 둘레 계산
     */
    getCircumference() {
        return 2 * Math.PI * 52; // 반지름 52
    }

    /**
     * 스트로크 오프셋 계산
     */
    getStrokeOffset() {
        const circumference = this.getCircumference();
        const progress = Math.min(this.data.allocationPercentage / 0.33, 1); // 33% 기준
        return circumference - (progress * circumference);
    }

    /**
     * 통화 포맷팅
     */
    formatCurrency(amount) {
        if (amount === 0) return '$0.00';
        if (amount < 0) return `-$${Math.abs(amount).toLocaleString('en-US', { minimumFractionDigits: 2, maximumFractionDigits: 2 })}`;
        return `$${amount.toLocaleString('en-US', { minimumFractionDigits: 2, maximumFractionDigits: 2 })}`;
    }

    /**
     * 시간 포맷팅
     */
    formatTime(date) {
        if (!date) return '없음';
        return new Date(date).toLocaleTimeString('ko-KR');
    }

    /**
     * 에러 처리
     */
    handleError(error) {
        console.error('Capital Tracker Error:', error);
        
        // 에러 상태 표시
        if (this.container) {
            const errorDiv = this.container.querySelector('.capital-tracker') || this.container;
            errorDiv.classList.add('error-state');
        }

        eventBus.emit('component:error', {
            componentName: 'CapitalTracker',
            error,
            context: 'data_loading'
        });
    }

    /**
     * 스타일 추가
     */
    addStyles() {
        if (document.getElementById('capital-tracker-styles')) return;

        const styles = document.createElement('style');
        styles.id = 'capital-tracker-styles';
        styles.textContent = `
            .capital-tracker {
                background: var(--card-bg, #ffffff);
                border-radius: 12px;
                padding: 1.5rem;
                box-shadow: 0 2px 8px rgba(0,0,0,0.1);
                margin-bottom: 1rem;
                transition: all 0.3s ease;
            }
            
            .capital-tracker.alert-warning {
                border-left: 4px solid #ffaa00;
            }
            
            .capital-tracker.alert-danger {
                border-left: 4px solid #ff8800;
            }
            
            .capital-tracker.alert-critical {
                border-left: 4px solid #ff4444;
                animation: pulse-red 2s infinite;
            }
            
            @keyframes pulse-red {
                0%, 100% { box-shadow: 0 2px 8px rgba(0,0,0,0.1); }
                50% { box-shadow: 0 2px 16px rgba(255,68,68,0.3); }
            }
            
            .capital-header {
                display: flex;
                justify-content: space-between;
                align-items: center;
                margin-bottom: 1.5rem;
            }
            
            .capital-header h3 {
                margin: 0;
                display: flex;
                align-items: center;
                gap: 0.5rem;
            }
            
            .status-indicator.safe { color: #00aa44; }
            .status-indicator.danger { color: #ff4444; }
            
            .last-update {
                font-size: 0.8rem;
                color: var(--text-secondary, #666);
            }
            
            .allocation-overview {
                display: grid;
                grid-template-columns: auto 1fr;
                gap: 1.5rem;
                margin-bottom: 1.5rem;
            }
            
            .progress-ring {
                position: relative;
                display: flex;
                align-items: center;
                justify-content: center;
            }
            
            .progress-ring-svg {
                transform: rotate(-90deg);
            }
            
            .progress-text {
                position: absolute;
                text-align: center;
            }
            
            .progress-text .percentage {
                font-size: 1.2rem;
                font-weight: bold;
                color: var(--text-primary, #333);
            }
            
            .progress-text .limit {
                font-size: 0.8rem;
                color: var(--text-secondary, #666);
            }
            
            .allocation-details {
                display: flex;
                flex-direction: column;
                justify-content: center;
                gap: 0.75rem;
            }
            
            .detail-item {
                display: flex;
                justify-content: space-between;
                align-items: center;
            }
            
            .detail-item .label {
                color: var(--text-secondary, #666);
                font-size: 0.9rem;
            }
            
            .detail-item .value {
                font-weight: 600;
                color: var(--text-primary, #333);
            }
            
            .detail-item .value.positive { color: #00aa44; }
            .detail-item .value.negative { color: #ff4444; }
            
            .symbol-allocations h4,
            .positions-summary h4 {
                margin: 1.5rem 0 1rem 0;
                display: flex;
                align-items: center;
                justify-content: space-between;
            }
            
            .refresh-btn {
                background: none;
                border: none;
                font-size: 1rem;
                cursor: pointer;
                padding: 0.25rem;
                border-radius: 4px;
                transition: background-color 0.2s;
            }
            
            .refresh-btn:hover {
                background-color: var(--hover-bg, #f0f0f0);
            }
            
            @keyframes spin {
                from { transform: rotate(0deg); }
                to { transform: rotate(360deg); }
            }
            
            .symbol-grid {
                display: grid;
                grid-template-columns: 1fr 1fr;
                gap: 1rem;
            }
            
            .symbol-card {
                background: var(--secondary-bg, #f8f9fa);
                border-radius: 8px;
                padding: 1rem;
                text-align: center;
            }
            
            .symbol-card.btc {
                border-top: 3px solid #f7931a;
            }
            
            .symbol-card.eth {
                border-top: 3px solid #627eea;
            }
            
            .symbol-header {
                display: flex;
                align-items: center;
                justify-content: space-between;
                margin-bottom: 0.5rem;
            }
            
            .symbol-icon {
                font-size: 1.2rem;
                font-weight: bold;
            }
            
            .target-weight {
                font-size: 0.7rem;
                color: var(--text-secondary, #666);
            }
            
            .symbol-value {
                font-size: 1.1rem;
                font-weight: 600;
                margin-bottom: 0.25rem;
            }
            
            .symbol-percentage {
                font-size: 0.9rem;
                color: var(--text-secondary, #666);
            }
            
            .positions-list {
                max-height: 200px;
                overflow-y: auto;
            }
            
            .position-item {
                display: flex;
                justify-content: space-between;
                align-items: center;
                padding: 0.75rem;
                background: var(--secondary-bg, #f8f9fa);
                border-radius: 6px;
                margin-bottom: 0.5rem;
            }
            
            .position-symbol {
                display: flex;
                align-items: center;
                gap: 0.5rem;
            }
            
            .position-symbol .symbol {
                font-weight: 600;
            }
            
            .position-symbol .side {
                font-size: 0.8rem;
                padding: 0.2rem 0.4rem;
                border-radius: 4px;
                background: var(--badge-bg, #e9ecef);
            }
            
            .position-details {
                display: flex;
                align-items: center;
                gap: 1rem;
                font-size: 0.9rem;
            }
            
            .position-leverage {
                background: var(--accent-color, #007bff);
                color: white;
                padding: 0.2rem 0.4rem;
                border-radius: 4px;
                font-size: 0.8rem;
            }
            
            .alert-levels {
                display: flex;
                gap: 1rem;
                margin-top: 1.5rem;
                padding-top: 1rem;
                border-top: 1px solid var(--border-color, #dee2e6);
            }
            
            .alert-level {
                display: flex;
                align-items: center;
                gap: 0.25rem;
                font-size: 0.8rem;
                color: var(--text-secondary, #666);
                opacity: 0.5;
                transition: opacity 0.3s ease;
            }
            
            .alert-level.active {
                opacity: 1;
                font-weight: 600;
            }
            
            .no-positions {
                text-align: center;
                color: var(--text-secondary, #666);
                font-style: italic;
                padding: 1rem;
            }
            
            .capital-tracker.error-state {
                border-left: 4px solid #dc3545;
                background: rgba(220, 53, 69, 0.05);
            }
        `;
        document.head.appendChild(styles);
    }

    /**
     * 컴포넌트 정리
     */
    destroy() {
        if (this.updateTimer) {
            clearInterval(this.updateTimer);
        }
        
        eventBus.off('websocket:balance_update');
        eventBus.off('websocket:position_update');
        eventBus.off('capital:status_update');
        
        super.destroy();
    }

    /**
     * 컴포넌트 새로고침
     */
    refresh() {
        this.loadData();
    }
}

// 전역으로 내보내기
export { CapitalTracker };
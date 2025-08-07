// 🚀 Bitget Trading System v3.0 - Dashboard Core Logic

class TradingDashboard {
    constructor() {
        this.data = {};
        this.previousData = {};
        this.isLoading = false;
        this.currentFilter = 'all';
        this.currentSort = 'symbol';
        this.theme = localStorage.getItem('dashboard-theme') || 'dark';
        this.notificationCount = 0;
        this.lastNotificationTime = 0;
        
        this.initializeTheme();
        this.bindEvents();
        this.startNotificationUpdates();
    }

    initializeTheme() {
        document.documentElement.setAttribute('data-theme', this.theme);
        this.updateThemeUI();
    }

    bindEvents() {
        // 필터 버튼 이벤트
        document.querySelectorAll('.filter-btn[data-filter]').forEach(btn => {
            btn.addEventListener('click', (e) => this.handleFilter(e.target.dataset.filter));
        });

        // 정렬 선택 이벤트
        document.getElementById('sort-select').addEventListener('change', (e) => {
            this.handleSort(e.target.value);
        });

        // 새로고침 버튼
        document.querySelector('.theme-toggle[onclick="refreshData()"]').onclick = () => this.refreshData();
    }

    async fetchDashboardData() {
        if (this.isLoading) return;

        this.isLoading = true;
        document.body.classList.add('loading');

        try {
            const response = await fetch('/api/dashboard');
            if (!response.ok) throw new Error('API 요청 실패');
            
            this.previousData = { ...this.data };
            this.data = await response.json();
            
            this.updateDashboard();
            this.detectChanges();
            
        } catch (error) {
            console.error('대시보드 데이터 가져오기 실패:', error);
            this.showToast('데이터 로딩 실패', 'error');
        } finally {
            this.isLoading = false;
            document.body.classList.remove('loading');
            this.updateLastUpdateTime();
        }
    }

    updateDashboard() {
        this.updateSummaryCards();
        this.updatePositionsTable();
        this.updateTradesTable();
        this.updateWidgets();
        this.updateSystemStatus();
    }

    // 🔔 알림 관련 메서드
    startNotificationUpdates() {
        // 초기 알림 로드
        this.fetchNotifications();
        
        // 10초마다 알림 업데이트
        setInterval(() => {
            this.fetchNotifications();
        }, 10000);
    }

    async fetchNotifications() {
        try {
            const response = await fetch('/api/notifications');
            if (!response.ok) throw new Error('알림 가져오기 실패');
            
            const data = await response.json();
            this.updateNotifications(data);
            
        } catch (error) {
            console.error('알림 가져오기 실패:', error);
        }
    }

    updateNotifications(data) {
        const container = document.getElementById('notification-container');
        const countBadge = document.getElementById('notification-count');
        
        if (!container) return;

        const { notifications, system_logs } = data;
        const allItems = [...notifications, ...system_logs].sort((a, b) => 
            new Date(b.timestamp) - new Date(a.timestamp)
        );

        // 알림 개수 업데이트
        this.notificationCount = notifications.length;
        if (countBadge) {
            countBadge.textContent = this.notificationCount;
            countBadge.style.display = this.notificationCount > 0 ? 'inline' : 'none';
        }

        // 알림 컨테이너 업데이트
        if (allItems.length === 0) {
            container.innerHTML = '<div class="loading-spinner">알림이 없습니다</div>';
            return;
        }

        const html = allItems.slice(0, 15).map(item => {
            if (item.content) {
                // 텔레그램 알림
                return this.createNotificationItem(item);
            } else {
                // 시스템 로그
                return this.createSystemLogItem(item);
            }
        }).join('');

        container.innerHTML = html;

        // 새로운 알림 강조 효과
        this.highlightNewNotifications(allItems);
    }

    createNotificationItem(notification) {
        const type = this.getNotificationType(notification.content);
        const time = notification.formatted_time || new Date(notification.timestamp * 1000).toLocaleTimeString();
        
        return `
            <div class="notification-item ${type}" data-timestamp="${notification.timestamp}">
                <div class="notification-content">${this.escapeHtml(notification.content)}</div>
                <span class="notification-time">${time}</span>
            </div>
        `;
    }

    createSystemLogItem(log) {
        const time = log.formatted_time || log.timestamp.split('T')[1]?.split('.')[0] || '';
        
        return `
            <div class="system-log-item ${log.level}" data-timestamp="${log.timestamp}">
                <span class="log-component">[${log.component}]</span>
                ${this.escapeHtml(log.message)}
                <span class="notification-time">${time}</span>
            </div>
        `;
    }

    getNotificationType(content) {
        const text = content.toLowerCase();
        if (text.includes('🚨') || text.includes('긴급') || text.includes('위험')) return 'emergency';
        if (text.includes('⚠️') || text.includes('경고') || text.includes('주의')) return 'warning';
        if (text.includes('💰') || text.includes('수익') || text.includes('성공')) return 'success';
        return 'info';
    }

    highlightNewNotifications(items) {
        const currentTime = Date.now() / 1000;
        items.forEach((item, index) => {
            const timestamp = item.timestamp || 0;
            if (currentTime - timestamp < 30) { // 30초 이내
                setTimeout(() => {
                    const element = document.querySelector(`[data-timestamp="${timestamp}"]`);
                    if (element) {
                        element.style.animation = 'fadeInSlide 0.5s ease-out';
                        element.style.boxShadow = '0 0 10px rgba(100, 149, 237, 0.3)';
                    }
                }, index * 100); // 순차적 애니메이션
            }
        });
    }

    escapeHtml(text) {
        const div = document.createElement('div');
        div.textContent = text;
        return div.innerHTML;
    }

    updateSummaryCards() {
        const { balance, performance } = this.data;

        if (balance && balance.total && balance.total.USDT) {
            this.updateSummaryCard('total-balance', balance.total.USDT, 0);
            this.updateSummaryCard('unrealized-pnl', 
                parseFloat(balance.info?.[0]?.unrealizedPL || 0));
        }

        if (performance) {
            this.updateSummaryCard('daily-pnl', performance.total_pnl || 0);
            this.updateSummaryCard('realized-pnl', performance.realized_pnl || 0);
        }
    }

    updateSummaryCard(elementId, value, previousValue = 0) {
        const element = document.getElementById(elementId);
        const changeElement = document.getElementById(elementId.replace('-', '-') + '-change');
        
        if (element) {
            element.textContent = this.formatCurrency(value);
            
            // 카드 색상 업데이트
            const card = element.closest('.summary-card');
            card.classList.remove('profit', 'loss');
            if (value > 0) card.classList.add('profit');
            else if (value < 0) card.classList.add('loss');
        }

        if (changeElement && previousValue !== undefined) {
            const change = value - previousValue;
            const changePercent = previousValue !== 0 ? (change / Math.abs(previousValue) * 100) : 0;
            
            changeElement.classList.remove('positive', 'negative');
            if (change > 0) {
                changeElement.classList.add('positive');
                changeElement.innerHTML = `<i class="fas fa-arrow-up"></i><span>+${changePercent.toFixed(1)}%</span>`;
            } else if (change < 0) {
                changeElement.classList.add('negative');
                changeElement.innerHTML = `<i class="fas fa-arrow-down"></i><span>${changePercent.toFixed(1)}%</span>`;
            } else {
                changeElement.innerHTML = `<i class="fas fa-minus"></i><span>0%</span>`;
            }
        }
    }

    updatePositionsTable() {
        const tbody = document.getElementById('positions-tbody');
        const positions = this.data.positions || [];
        
        // 포지션 수 업데이트
        document.getElementById('positions-count').textContent = positions.length;

        if (positions.length === 0) {
            tbody.innerHTML = `
                <tr>
                    <td colspan="8" class="text-center" style="color: var(--text-muted); padding: 2rem;">
                        <i class="fas fa-chart-line" style="font-size: 2rem; opacity: 0.3; margin-bottom: 1rem; display: block;"></i>
                        활성 포지션이 없습니다
                    </td>
                </tr>`;
            return;
        }

        // 필터링 및 정렬
        let filteredPositions = this.filterPositions(positions);
        filteredPositions = this.sortPositions(filteredPositions);

        tbody.innerHTML = filteredPositions.map(position => this.createPositionRow(position)).join('');
    }

    createPositionRow(position) {
        const pnlPercent = ((position.current_price - position.entry_price) / position.entry_price * 100);
        const pnlClass = position.pnl >= 0 ? 'positive' : 'negative';
        const sideClass = position.side.toLowerCase();

        return `
            <tr data-symbol="${position.symbol}" data-id="${position.id}">
                <td>
                    <div class="position-symbol">${position.symbol}</div>
                </td>
                <td>
                    <span class="position-side ${sideClass}">${position.side}</span>
                </td>
                <td>${this.formatNumber(position.size)}</td>
                <td>${this.formatCurrency(position.entry_price)}</td>
                <td>${this.formatCurrency(position.current_price)}</td>
                <td>
                    <span class="position-pnl ${pnlClass}">
                        ${pnlPercent >= 0 ? '+' : ''}${pnlPercent.toFixed(2)}%
                    </span>
                </td>
                <td>
                    <span class="position-pnl ${pnlClass}">
                        ${this.formatCurrency(position.pnl)}
                    </span>
                </td>
                <td>
                    <div class="position-actions">
                        <button class="action-btn danger" onclick="closePosition('${position.id}')">
                            즉시 종료
                        </button>
                        <button class="action-btn warning" onclick="adjustStopLoss('${position.id}')">
                            손절 조정
                        </button>
                        <button class="action-btn" onclick="partialClose('${position.id}')">
                            50% 종료
                        </button>
                    </div>
                </td>
            </tr>`;
    }

    updateTradesTable() {
        const tbody = document.getElementById('trades-tbody');
        const trades = this.data.recent_trades || [];

        if (trades.length === 0) {
            tbody.innerHTML = `
                <tr>
                    <td colspan="8" class="text-center" style="color: var(--text-muted); padding: 2rem;">
                        <i class="fas fa-history" style="font-size: 2rem; opacity: 0.3; margin-bottom: 1rem; display: block;"></i>
                        최근 거래가 없습니다
                    </td>
                </tr>`;
            return;
        }

        tbody.innerHTML = trades.slice(0, 10).map(trade => this.createTradeRow(trade)).join('');
    }

    createTradeRow(trade) {
        const pnlClass = trade.pnl >= 0 ? 'positive' : 'negative';
        const pnlPercent = trade.pnl_percent || 0;

        return `
            <tr>
                <td>${new Date(trade.timestamp).toLocaleString()}</td>
                <td>${trade.symbol}</td>
                <td><span class="position-side ${trade.side.toLowerCase()}">${trade.side}</span></td>
                <td>${this.formatNumber(trade.size)}</td>
                <td>${this.formatCurrency(trade.entry_price)}</td>
                <td>${this.formatCurrency(trade.exit_price)}</td>
                <td><span class="position-pnl ${pnlClass}">${this.formatCurrency(trade.pnl)}</span></td>
                <td><span class="position-pnl ${pnlClass}">${pnlPercent >= 0 ? '+' : ''}${pnlPercent.toFixed(2)}%</span></td>
            </tr>`;
    }

    updateWidgets() {
        // 빠른 통계 업데이트
        if (this.data.performance) {
            const perf = this.data.performance;
            document.getElementById('win-rate').textContent = `${perf.win_rate || 0}%`;
            document.getElementById('avg-win').textContent = this.formatCurrency(perf.avg_win || 0);
            document.getElementById('avg-loss').textContent = this.formatCurrency(perf.avg_loss || 0);
            document.getElementById('total-trades').textContent = perf.total_trades || 0;
        }

        // 리스크 미터 업데이트 (임시 데이터)
        const riskLevel = this.calculateRiskLevel();
        document.getElementById('risk-percentage').textContent = `${riskLevel}%`;
        this.updateRiskMeter(riskLevel);

        // AI 신뢰도 업데이트 (임시 데이터)
        const confidence = 75; // 실제 ML 모델에서 가져와야 함
        document.getElementById('confidence-value').textContent = `${confidence}%`;
        document.getElementById('confidence-fill').style.width = `${confidence}%`;

        // 시장 상태 업데이트
        this.updateMarketStatus();
    }

    updateSystemStatus() {
        if (this.data.system_status) {
            const status = this.data.system_status;
            document.getElementById('system-status').textContent = status.running ? '실행 중' : '중지됨';
            document.getElementById('websocket-status').textContent = status.websocket_connected ? '연결됨' : '끊김';
        }
    }

    calculateRiskLevel() {
        // 실제 위험도 계산 로직 구현
        const positions = this.data.positions || [];
        if (positions.length === 0) return 0;

        const totalExposure = positions.reduce((sum, pos) => sum + Math.abs(pos.size * pos.current_price), 0);
        const balance = this.data.balance?.total?.USDT || 1;
        return Math.min((totalExposure / balance * 100), 100);
    }

    updateRiskMeter(level) {
        // SVG 원호 업데이트 로직
        const arc = document.getElementById('risk-arc-active');
        const angle = (level / 100) * 180;
        const radians = (angle - 90) * (Math.PI / 180);
        const x = 60 + 40 * Math.cos(radians);
        const y = 50 + 40 * Math.sin(radians);
        const largeArc = angle > 180 ? 1 : 0;
        
        arc.setAttribute('d', `M 20 50 A 40 40 0 ${largeArc} 1 ${x} ${y}`);
    }

    updateMarketStatus() {
        // 임시 시장 상태 데이터
        document.getElementById('market-volatility').textContent = '보통';
        document.getElementById('volatility-level').textContent = '중간';
        document.getElementById('market-trend').textContent = '횡보';
    }

    detectChanges() {
        // 중요한 변화 감지 및 플래시 효과
        if (this.previousData.positions && this.data.positions) {
            this.data.positions.forEach(position => {
                const prevPosition = this.previousData.positions.find(p => p.id === position.id);
                if (prevPosition && prevPosition.pnl !== position.pnl) {
                    const row = document.querySelector(`tr[data-id="${position.id}"]`);
                    if (row) {
                        const flashClass = position.pnl > prevPosition.pnl ? 'flash-profit' : 'flash-loss';
                        row.classList.add(flashClass);
                        setTimeout(() => row.classList.remove(flashClass), 800);
                    }
                }
            });
        }

        // 브라우저 알림
        this.checkForImportantEvents();
    }

    checkForImportantEvents() {
        // 중요한 이벤트 감지 (5% 이상 손익 변화, 새 포지션 등)
        const positions = this.data.positions || [];
        positions.forEach(position => {
            const pnlPercent = ((position.current_price - position.entry_price) / position.entry_price * 100);
            
            if (Math.abs(pnlPercent) >= 5) {
                const message = `${position.symbol} ${pnlPercent >= 0 ? '수익' : '손실'} ${Math.abs(pnlPercent).toFixed(1)}% 도달`;
                this.showNotification(message, pnlPercent >= 0 ? 'success' : 'warning');
            }
        });
    }

    // 필터링 및 정렬
    filterPositions(positions) {
        if (this.currentFilter === 'all') return positions;
        return positions.filter(pos => pos.symbol.includes(this.currentFilter));
    }

    sortPositions(positions) {
        return positions.sort((a, b) => {
            switch (this.currentSort) {
                case 'pnl':
                    return b.pnl - a.pnl;
                case 'size':
                    return b.size * b.current_price - a.size * a.current_price;
                case 'time':
                    return new Date(b.timestamp) - new Date(a.timestamp);
                default:
                    return a.symbol.localeCompare(b.symbol);
            }
        });
    }

    handleFilter(filter) {
        this.currentFilter = filter;
        document.querySelectorAll('.filter-btn[data-filter]').forEach(btn => {
            btn.classList.remove('active');
        });
        document.querySelector(`[data-filter="${filter}"]`).classList.add('active');
        
        this.updatePositionsTable();
    }

    handleSort(sort) {
        this.currentSort = sort;
        this.updatePositionsTable();
    }

    // 테마 관리
    toggleTheme() {
        const themes = ['dark', 'light', 'high-contrast'];
        const currentIndex = themes.indexOf(this.theme);
        this.theme = themes[(currentIndex + 1) % themes.length];
        
        document.documentElement.setAttribute('data-theme', this.theme);
        localStorage.setItem('dashboard-theme', this.theme);
        this.updateThemeUI();
    }

    updateThemeUI() {
        const themeIcon = document.getElementById('theme-icon');
        const themeText = document.getElementById('theme-text');
        
        const themeConfig = {
            dark: { icon: 'fa-moon', text: '다크' },
            light: { icon: 'fa-sun', text: '라이트' },
            'high-contrast': { icon: 'fa-adjust', text: '고대비' }
        };
        
        const config = themeConfig[this.theme];
        themeIcon.className = `fas ${config.icon}`;
        themeText.textContent = config.text;
    }

    // 알림 시스템
    showNotification(message, type = 'info') {
        if ('Notification' in window && Notification.permission === 'granted') {
            new Notification('GPTBITCOIN 알림', {
                body: message,
                icon: '/favicon.ico'
            });
        }
        
        this.showToast(message, type);
    }

    showToast(message, type = 'info') {
        const toast = document.createElement('div');
        toast.className = `toast toast-${type}`;
        toast.innerHTML = `
            <div class="toast-content">
                <i class="fas ${this.getToastIcon(type)}"></i>
                <span>${message}</span>
            </div>
            <button class="toast-close" onclick="this.parentElement.remove()">&times;</button>
        `;
        
        document.getElementById('toast-container').appendChild(toast);
        
        // 자동 제거
        setTimeout(() => {
            toast.remove();
        }, 5000);
    }

    getToastIcon(type) {
        const icons = {
            success: 'fa-check-circle',
            error: 'fa-exclamation-circle',
            warning: 'fa-exclamation-triangle',
            info: 'fa-info-circle'
        };
        return icons[type] || icons.info;
    }

    // 유틸리티 함수
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

    updateLastUpdateTime() {
        document.getElementById('last-update').textContent = new Date().toLocaleTimeString();
    }

    refreshData() {
        this.fetchDashboardData();
    }
}

// 전역 인스턴스
let dashboard;

function initializeDashboard() {
    dashboard = new TradingDashboard();
    dashboard.fetchDashboardData();
}

// 전역 함수들 (HTML에서 호출)
function toggleTheme() {
    dashboard.toggleTheme();
}

function refreshData() {
    dashboard.refreshData();
}

// 포지션 액션 함수들
async function closePosition(positionId) {
    showConfirmModal(
        '포지션 종료 확인',
        '정말로 이 포지션을 즉시 종료하시겠습니까?',
        async () => {
            try {
                const response = await fetch(`/api/positions/${positionId}/close`, {
                    method: 'POST'
                });
                
                if (response.ok) {
                    dashboard.showToast('포지션이 성공적으로 종료되었습니다', 'success');
                    dashboard.refreshData();
                } else {
                    throw new Error('포지션 종료 실패');
                }
            } catch (error) {
                dashboard.showToast('포지션 종료에 실패했습니다', 'error');
            }
        }
    );
}

async function adjustStopLoss(positionId) {
    const newStopLoss = prompt('새로운 손절가를 입력하세요:');
    if (!newStopLoss) return;

    try {
        const response = await fetch(`/api/positions/${positionId}/stop-loss`, {
            method: 'PUT',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ stop_loss: parseFloat(newStopLoss) })
        });

        if (response.ok) {
            dashboard.showToast('손절가가 성공적으로 수정되었습니다', 'success');
            dashboard.refreshData();
        } else {
            throw new Error('손절가 수정 실패');
        }
    } catch (error) {
        dashboard.showToast('손절가 수정에 실패했습니다', 'error');
    }
}

async function partialClose(positionId) {
    showConfirmModal(
        '부분 청산 확인',
        '포지션의 50%를 청산하시겠습니까?',
        async () => {
            try {
                const response = await fetch(`/api/positions/${positionId}/partial-close`, {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({ percentage: 50 })
                });

                if (response.ok) {
                    dashboard.showToast('부분 청산이 성공적으로 완료되었습니다', 'success');
                    dashboard.refreshData();
                } else {
                    throw new Error('부분 청산 실패');
                }
            } catch (error) {
                dashboard.showToast('부분 청산에 실패했습니다', 'error');
            }
        }
    );
}

function exportTrades() {
    dashboard.showToast('거래 내역을 내보내는 중...', 'info');
    // 실제 내보내기 로직 구현
}

// 모달 관리
function showConfirmModal(title, message, callback) {
    document.getElementById('confirm-title').textContent = title;
    document.getElementById('confirm-message').textContent = message;
    document.getElementById('confirm-modal').style.display = 'flex';
    
    document.getElementById('confirm-action').onclick = () => {
        closeModal();
        callback();
    };
}

function closeModal() {
    document.getElementById('confirm-modal').style.display = 'none';
}

// 키보드 단축키
function handleKeyboardShortcuts(e) {
    // Ctrl+K 또는 Cmd+K로 명령어 팔레트 열기
    if ((e.ctrlKey || e.metaKey) && e.key === 'k') {
        e.preventDefault();
        toggleCommandPalette();
    }
    
    // ESC로 모달 닫기
    if (e.key === 'Escape') {
        closeModal();
        document.getElementById('command-palette').style.display = 'none';
    }
}

function toggleCommandPalette() {
    const palette = document.getElementById('command-palette');
    palette.style.display = palette.style.display === 'none' ? 'flex' : 'none';
    
    if (palette.style.display === 'flex') {
        document.getElementById('command-input').focus();
    }
}
/**
 * @fileoverview Trading Dashboard Main Component
 * @description ES6 Module version of the main dashboard component
 * @version 2.0.0
 */

import { BaseComponent } from '../core/BaseComponent.js';
import { globalStore } from '../core/Store.js';
import { eventBus } from '../core/EventBus.js';
import { SearchFilterManager } from './SearchFilterManager.js';
import { KeyboardShortcutManager } from '../core/KeyboardShortcutManager.js';
import { ResponsiveGridManager } from '../core/ResponsiveGridManager.js';

// Chart system imports
import { ChartBase } from './ChartBase.js';
import { MarketHeatmapChart } from './MarketHeatmapChart.js';
import { OrderbookDepthChart } from './OrderbookDepthChart.js';
import { VolumeProfileChart } from './VolumeProfileChart.js';
import { AdvancedCandlestickChart } from './AdvancedCandlestickChart.js';
import { ChartInteractionManager } from './ChartInteractionManager.js';
import { RealTimeDataBinder } from './RealTimeDataBinder.js';
import { ChartSynchronizer } from './ChartSynchronizer.js';

/**
 * Main Trading Dashboard Component
 * @extends BaseComponent
 */
export class TradingDashboard extends BaseComponent {
    /**
     * @param {HTMLElement} element - Dashboard container element
     * @param {Object} options - Configuration options
     */
    constructor(element, options = {}) {
        super(element, options);
        
        this.store = globalStore;
        this.eventBus = eventBus;
        
        // Component state
        this.data = {};
        this.previousData = {};
        this.isLoading = false;
        this.currentFilter = 'all';
        this.currentSort = 'symbol';
        this.notificationCount = 0;
        this.lastNotificationTime = 0;
        
        // Search and filter components
        this.searchFilterManager = null;
        this.filteredData = [];
        
        // Keyboard shortcut manager
        this.keyboardManager = null;
        
        // Responsive grid manager
        this.gridManager = null;
        
        // Chart system components
        this.chartInstances = new Map();
        this.chartInteractionManager = null;
        this.realTimeDataBinder = null;
        this.chartSynchronizer = null;
        
        // Chart containers
        this.chartContainers = {
            heatmap: null,
            orderbook: null,
            volumeProfile: null,
            candlestick: null
        };
        
        // Initialize theme from store or localStorage
        this.theme = this.store.getState('ui.theme') || localStorage.getItem('dashboard-theme') || 'dark';
        
        this.bindStoreSubscriptions();
        this.initializeTheme();
        this.initializeSearchFilter();
        this.initializeKeyboardShortcuts();
        this.initializeResponsiveGrid();
        this.initializeChartSystem();
        this.startNotificationUpdates();
        
        // Auto-fetch data on initialization
        this.fetchDashboardData();
    }

    /**
     * Get default options
     * @returns {Object}
     */
    getDefaultOptions() {
        return {
            ...super.getDefaultOptions(),
            autoRefresh: true,
            refreshInterval: 5000,
            notifications: true,
            maxNotifications: 50
        };
    }

    /**
     * Bind store subscriptions
     */
    bindStoreSubscriptions() {
        // Subscribe to trading data changes
        this.store.subscribe((state) => {
            this.data = {
                balance: state.trading.balance,
                positions: state.trading.positions,
                recent_trades: state.trading.trades,
                performance: state.trading.performance,
                system_status: state.system
            };
            this.updateDashboard();
        }, 'trading');

        // Subscribe to UI state changes
        this.store.subscribe((state) => {
            this.currentFilter = state.ui.currentFilter;
            this.currentSort = state.ui.currentSort;
            this.theme = state.ui.theme;
        }, 'ui');

        // Subscribe to system status changes
        this.store.subscribe((state) => {
            this.updateSystemStatus(state.system);
        }, 'system');
    }

    /**
     * Bind events
     */
    bindEvents() {
        super.bindEvents();
        
        // Filter buttons
        this.findAll('.filter-btn[data-filter]').forEach(btn => {
            this.addEventListener(btn, 'click', (e) => {
                this.handleFilter(e.target.dataset.filter);
            });
        });

        // Sort select
        const sortSelect = this.find('#sort-select');
        if (sortSelect) {
            this.addEventListener(sortSelect, 'change', (e) => {
                this.handleSort(e.target.value);
            });
        }

        // Refresh button
        const refreshBtn = this.find('.theme-toggle[onclick="refreshData()"]');
        if (refreshBtn) {
            refreshBtn.onclick = null; // Remove inline handler
            this.addEventListener(refreshBtn, 'click', () => {
                this.refreshData();
            });
        }

        // Theme toggle
        this.addEventListener(document, 'keydown', this.handleKeyboardShortcuts.bind(this));

        // EventBus subscriptions
        this.eventBus.on('dashboard:refresh', () => this.refreshData());
        this.eventBus.on('dashboard:theme-toggle', () => this.toggleTheme());
        this.eventBus.on('position:closed', () => this.refreshData());
        this.eventBus.on('notification:new', (event) => this.handleNewNotification(event.data));
        
        // Search and filter events
        this.eventBus.on('search:request', (event) => this.handleSearchRequest(event.data));
        this.eventBus.on('search:selectResult', (event) => this.handleSearchSelection(event.data));
        this.eventBus.on('search:sort', (event) => this.handleSearchSort(event.data));
        
        // Keyboard shortcut events
        this.eventBus.on('shortcut:refreshData', () => this.refreshData());
        this.eventBus.on('shortcut:toggleTheme', () => this.toggleTheme());
        this.eventBus.on('shortcut:showHelp', () => this.keyboardManager?.showHelp());
        this.eventBus.on('shortcut:openCommandPalette', () => this.openCommandPalette());
        this.eventBus.on('shortcut:focusSearch', () => this.focusSearch());
        this.eventBus.on('shortcut:saveLayout', () => this.saveCurrentLayout());
        this.eventBus.on('shortcut:toggleFullscreen', () => this.toggleFullscreen());
        this.eventBus.on('shortcut:closeModal', () => this.closeAllModals());
        
        // Grid layout events
        this.eventBus.on('shortcut:switchToLayout1', () => this.gridManager?.switchLayout('dashboard'));
        this.eventBus.on('shortcut:switchToLayout2', () => this.gridManager?.switchLayout('trading'));
        this.eventBus.on('shortcut:switchToLayout3', () => this.gridManager?.switchLayout('compact'));
    }

    /**
     * Initialize search and filter system
     */
    initializeSearchFilter() {
        // Create search filter container if it doesn't exist
        let searchContainer = this.find('#search-filter-container');
        if (!searchContainer) {
            searchContainer = document.createElement('div');
            searchContainer.id = 'search-filter-container';
            
            // Insert before positions table
            const positionsSection = this.find('#positions-section') || this.find('.positions-container');
            if (positionsSection) {
                positionsSection.parentNode.insertBefore(searchContainer, positionsSection);
            } else {
                this.element.insertBefore(searchContainer, this.element.firstChild);
            }
        }
        
        // Initialize SearchFilterManager
        this.searchFilterManager = new SearchFilterManager();
        searchContainer.appendChild(this.searchFilterManager.element);
        
        this.emit('searchFilterInitialized');
    }
    
    /**
     * Initialize keyboard shortcut system
     */
    initializeKeyboardShortcuts() {
        this.keyboardManager = new KeyboardShortcutManager();
        
        // Register custom dashboard shortcuts
        this.registerDashboardShortcuts();
        
        this.emit('keyboardShortcutsInitialized');
    }
    
    /**
     * Register dashboard-specific shortcuts
     */
    registerDashboardShortcuts() {
        if (!this.keyboardManager) return;
        
        // Position management shortcuts
        this.keyboardManager.registerShortcut('ctrl+shift+c', 'closeAllPositions', 'positions', {
            description: '모든 포지션 강제 종료'
        });
        
        this.keyboardManager.registerShortcut('ctrl+shift+p', 'pauseTrading', 'global', {
            description: '자동 거래 일시정지'
        });
        
        // Dashboard specific shortcuts
        this.keyboardManager.registerShortcut('ctrl+shift+n', 'toggleNotifications', 'global', {
            description: '알림 패널 토글'
        });
        
        this.keyboardManager.registerShortcut('ctrl+shift+m', 'toggleMarginInfo', 'global', {
            description: '마진 정보 토글'
        });
        
        // Layout shortcuts
        this.keyboardManager.registerShortcut('ctrl+1', 'switchToLayout1', 'global', {
            description: '레이아웃 1로 전환'
        });
        
        this.keyboardManager.registerShortcut('ctrl+2', 'switchToLayout2', 'global', {
            description: '레이아웃 2로 전환'
        });
        
        this.keyboardManager.registerShortcut('ctrl+3', 'switchToLayout3', 'global', {
            description: '레이아웃 3으로 전환'
        });
        
        // Grid-specific shortcuts
        this.keyboardManager.registerShortcut('alt+1', 'switchToLayout1', 'global', {
            description: '대시보드 레이아웃'
        });
        
        this.keyboardManager.registerShortcut('alt+2', 'switchToLayout2', 'global', {
            description: '거래 레이아웃'
        });
        
        this.keyboardManager.registerShortcut('alt+3', 'switchToLayout3', 'global', {
            description: '컴팩트 레이아웃'
        });
        
        this.keyboardManager.registerShortcut('ctrl+alt+r', 'resetLayout', 'global', {
            description: '레이아웃 초기화'
        });
    }
    
    /**
     * Initialize responsive grid system
     */
    initializeResponsiveGrid() {
        // 메인 컨테이너를 그리드 컨테이너로 사용
        const mainContainer = this.element.querySelector('.dashboard-main') || this.element;
        
        // 그리드 아이템들을 마크업하여 식별
        this.setupGridItems(mainContainer);
        
        // ResponsiveGridManager 초기화
        this.gridManager = new ResponsiveGridManager(mainContainer, {
            defaultLayout: 'dashboard'
        });
        
        // 그리드 이벤트 리스너 설정
        this.setupGridEventListeners();
        
        this.emit('responsiveGridInitialized');
    }
    
    /**
     * Setup grid items markup
     */
    setupGridItems(container) {
        // 기존 대시보드 섹션들을 그리드 아이템으로 변환
        const sections = {
            'balance-section': { id: 'balance', span: 2, priority: 1 },
            'positions-section': { id: 'positions', span: 3, priority: 2 },
            'trades-section': { id: 'trades', span: 2, priority: 4 },
            'chart-section': { id: 'chart', span: 4, priority: 3 },
            'notifications-section': { id: 'notifications', span: 1, priority: 5 }
        };
        
        Object.entries(sections).forEach(([className, config]) => {
            const element = container.querySelector(`.${className}`) || 
                           container.querySelector(`#${className}`);
            
            if (element) {
                element.setAttribute('data-grid-item', config.id);
                element.setAttribute('data-grid-span', config.span);
                element.setAttribute('data-grid-priority', config.priority);
                element.setAttribute('data-grid-movable', 'true');
                element.setAttribute('data-grid-resizable', 'true');
                
                // 브레이크포인트별 가시성 설정
                if (config.id === 'notifications') {
                    element.setAttribute('data-grid-show', 'xs:false,sm:false,md:true,lg:true,xl:true,xxl:true');
                }
            }
        });
        
        // 검색 필터 섹션도 그리드 아이템으로 추가
        const searchSection = container.querySelector('#search-filter-container');
        if (searchSection) {
            searchSection.setAttribute('data-grid-item', 'search-filter');
            searchSection.setAttribute('data-grid-span', '4');
            searchSection.setAttribute('data-grid-priority', '0');
            searchSection.setAttribute('data-grid-movable', 'false');
        }
    }
    
    /**
     * Setup grid event listeners
     */
    setupGridEventListeners() {
        if (!this.gridManager) return;
        
        // 브레이크포인트 변경 이벤트
        this.gridManager.on('breakpointChanged', (data) => {
            this.handleBreakpointChange(data);
        });
        
        // 레이아웃 변경 이벤트
        this.gridManager.on('layoutUpdated', (data) => {
            this.handleLayoutUpdate(data);
        });
        
        // 아이템 리사이즈 이벤트
        this.gridManager.on('itemResized', (data) => {
            this.handleItemResize(data);
        });
        
        // 컨테이너 리사이즈 이벤트
        this.gridManager.on('containerResized', (data) => {
            this.handleContainerResize(data);
        });
    }
    
    /**
     * Handle breakpoint change
     */
    handleBreakpointChange(data) {
        const { current, previous, width } = data;
        
        // 브래이크포인트에 따른 UI 조정
        this.adjustUIForBreakpoint(current);
        
        // 알림 표시 (예: 모바일로 전환될 때)
        if (previous === 'xl' && current === 'sm') {
            this.showToast('모바일 모드로 전환되었습니다', 'info');
        }
        
        this.emit('dashboardBreakpointChanged', { current, previous, width });
    }
    
    /**
     * Adjust UI for breakpoint
     */
    adjustUIForBreakpoint(breakpoint) {
        // 모바일 모드에서는 검색 필터 패널 자동 숨김
        if (['xs', 'sm'].includes(breakpoint) && this.searchFilterManager) {
            const filterPanel = this.searchFilterManager.element.querySelector('.filter-panel');
            if (filterPanel) {
                filterPanel.style.display = 'none';
            }
        }
        
        // 커맨드 팔레트 크기 조정
        const palette = this.find('#command-palette');
        if (palette) {
            const content = palette.querySelector('.command-palette-content');
            if (content) {
                if (breakpoint === 'xs') {
                    content.style.maxWidth = '95vw';
                    content.style.maxHeight = '85vh';
                } else {
                    content.style.maxWidth = '600px';
                    content.style.maxHeight = '70vh';
                }
            }
        }
    }
    
    /**
     * Handle layout update
     */
    handleLayoutUpdate(data) {
        const { breakpoint, layout } = data;
        
        // 레이아웃 변경 알림
        this.showToast(`${layout} 레이아웃 적용 (${breakpoint})`, 'success');
        
        // 차트 리사이즈 트리거 (차트 라이브러리가 있는 경우)
        this.emit('chartResize');
        
        this.emit('dashboardLayoutUpdated', data);
    }
    
    /**
     * Handle item resize
     */
    handleItemResize(data) {
        const { id, width, height } = data;
        
        // 특정 아이템별 리사이즈 처리
        switch (id) {
            case 'chart':
                // 차트 업데이트
                this.emit('chartResize', { width, height });
                break;
            case 'positions':
                // 포지션 테이블 리사이즈
                this.emit('positionsTableResize', { width, height });
                break;
        }
    }
    
    /**
     * Handle container resize
     */
    handleContainerResize(data) {
        const { width, height, breakpoint } = data;
        
        // 컨테이너 리사이즈에 따른 전체 UI 조정
        this.adjustUIForContainerSize(width, height);
        
        this.emit('dashboardContainerResized', { width, height, breakpoint });
    }
    
    /**
     * Adjust UI for container size
     */
    adjustUIForContainerSize(width, height) {
        // 너무 작은 화면에서는 사이드바 숨김
        if (width < 600) {
            document.body.classList.add('compact-mode');
        } else {
            document.body.classList.remove('compact-mode');
        }
        
        // 높이가 부족한 경우 수직 스크롤 활성화
        if (height < 600) {
            document.body.classList.add('vertical-scroll');
        } else {
            document.body.classList.remove('vertical-scroll');
        }
    }

    /**
     * Initialize theme
     */
    initializeTheme() {
        document.documentElement.setAttribute('data-theme', this.theme);
        this.updateThemeUI();
        
        // Update store
        this.store.dispatch({
            type: 'UPDATE_UI_STATE',
            payload: { theme: this.theme }
        });
    }

    /**
     * Fetch dashboard data from API
     * @returns {Promise<void>}
     */
    async fetchDashboardData() {
        if (this.isLoading) return;

        this.isLoading = true;
        this.showLoading();
        
        // Update system status
        await this.store.dispatch({
            type: 'SET_SYSTEM_STATUS',
            payload: { status: 'loading' }
        });

        try {
            const response = await fetch('/api/dashboard');
            if (!response.ok) {
                throw new Error(`API 요청 실패: ${response.status}`);
            }
            
            this.previousData = { ...this.data };
            const newData = await response.json();
            
            // Update store with new data
            await this.store.dispatch({
                type: 'UPDATE_BALANCE',
                payload: newData.balance || {}
            });
            
            await this.store.dispatch({
                type: 'UPDATE_POSITIONS',
                payload: newData.positions || []
            });
            
            await this.store.dispatch({
                type: 'SET_SYSTEM_STATUS',
                payload: { 
                    status: 'ready',
                    lastUpdate: new Date(),
                    websocketConnected: newData.system_status?.websocket_connected || false
                }
            });
            
            this.detectChanges();
            this.emit('dataUpdated', newData);
            
        } catch (error) {
            console.error('대시보드 데이터 가져오기 실패:', error);
            
            await this.store.dispatch({
                type: 'SET_SYSTEM_STATUS',
                payload: { 
                    status: 'error',
                    errors: [error.message]
                }
            });
            
            this.showToast('데이터 로딩 실패: ' + error.message, 'error');
            this.emit('dataError', error);
        } finally {
            this.isLoading = false;
            this.hideLoading();
            this.updateLastUpdateTime();
        }
    }

    /**
     * Update dashboard components
     */
    updateDashboard() {
        this.updateSummaryCards();
        this.updatePositionsTable();
        this.updateTradesTable();
        this.updateWidgets();
        this.updateSystemStatus();
        
        // Update search filter with latest data
        this.updateSearchableData();
    }

    /**
     * Update searchable data for search filter manager
     */
    updateSearchableData() {
        if (!this.searchFilterManager) return;
        
        const searchableData = [];
        
        // Add positions to searchable data
        if (this.data.positions) {
            this.data.positions.forEach(position => {
                searchableData.push({
                    ...position,
                    type: 'position',
                    searchText: `${position.symbol} ${position.side} ${position.id} ${position.notes || ''}`.toLowerCase()
                });
            });
        }
        
        // Add recent trades to searchable data
        if (this.data.recent_trades) {
            this.data.recent_trades.forEach(trade => {
                searchableData.push({
                    ...trade,
                    type: 'trade',
                    searchText: `${trade.symbol} ${trade.side} ${trade.id} ${trade.notes || ''}`.toLowerCase()
                });
            });
        }
        
        this.searchableData = searchableData;
    }

    /**
     * Initialize chart system
     */
    initializeChartSystem() {
        this.createChartContainers();
        this.initializeChartComponents();
        this.setupChartEventListeners();
        this.emit('chartSystemInitialized');
    }

    /**
     * Create chart containers in DOM
     */
    createChartContainers() {
        const widgetsSection = this.element.querySelector('.widgets-section');
        if (!widgetsSection) return;

        // Market Heatmap Container
        const heatmapWidget = document.createElement('div');
        heatmapWidget.className = 'widget chart-widget';
        heatmapWidget.setAttribute('data-grid-item', 'heatmap');
        heatmapWidget.setAttribute('data-grid-span', '3');
        heatmapWidget.innerHTML = `
            <div class="widget-title">
                <i class="fas fa-th"></i>
                시장 상관관계 히트맵
                <div class="widget-controls">
                    <button class="widget-btn" onclick="this.closest('.widget').querySelector('.heatmap-container').style.display = this.closest('.widget').querySelector('.heatmap-container').style.display === 'none' ? 'block' : 'none'">
                        <i class="fas fa-eye"></i>
                    </button>
                </div>
            </div>
            <div class="heatmap-container chart-container" id="heatmap-container"></div>
        `;
        widgetsSection.appendChild(heatmapWidget);
        this.chartContainers.heatmap = heatmapWidget.querySelector('#heatmap-container');

        // Orderbook Depth Container
        const orderbookWidget = document.createElement('div');
        orderbookWidget.className = 'widget chart-widget';
        orderbookWidget.setAttribute('data-grid-item', 'orderbook');
        orderbookWidget.setAttribute('data-grid-span', '2');
        orderbookWidget.innerHTML = `
            <div class="widget-title">
                <i class="fas fa-layer-group"></i>
                오더북 깊이
                <div class="widget-controls">
                    <select class="widget-select" id="orderbook-symbol">
                        <option value="BTCUSDT">BTC/USDT</option>
                        <option value="ETHUSDT">ETH/USDT</option>
                    </select>
                </div>
            </div>
            <div class="orderbook-container chart-container" id="orderbook-container"></div>
        `;
        widgetsSection.appendChild(orderbookWidget);
        this.chartContainers.orderbook = orderbookWidget.querySelector('#orderbook-container');

        // Volume Profile Container
        const volumeWidget = document.createElement('div');
        volumeWidget.className = 'widget chart-widget';
        volumeWidget.setAttribute('data-grid-item', 'volume-profile');
        volumeWidget.setAttribute('data-grid-span', '2');
        volumeWidget.innerHTML = `
            <div class="widget-title">
                <i class="fas fa-chart-bar"></i>
                볼륨 프로파일
                <div class="widget-controls">
                    <button class="widget-btn" id="volume-settings">
                        <i class="fas fa-cog"></i>
                    </button>
                </div>
            </div>
            <div class="volume-profile-container chart-container" id="volume-profile-container"></div>
        `;
        widgetsSection.appendChild(volumeWidget);
        this.chartContainers.volumeProfile = volumeWidget.querySelector('#volume-profile-container');

        // Candlestick Chart Container
        const candlestickWidget = document.createElement('div');
        candlestickWidget.className = 'widget chart-widget large';
        candlestickWidget.setAttribute('data-grid-item', 'candlestick');
        candlestickWidget.setAttribute('data-grid-span', '4');
        candlestickWidget.innerHTML = `
            <div class="widget-title">
                <i class="fas fa-chart-line"></i>
                고급 캔들스틱 차트
                <div class="widget-controls">
                    <select class="widget-select" id="candlestick-timeframe">
                        <option value="1m">1분</option>
                        <option value="5m">5분</option>
                        <option value="1h" selected>1시간</option>
                        <option value="1d">1일</option>
                    </select>
                    <button class="widget-btn" id="chart-fullscreen">
                        <i class="fas fa-expand"></i>
                    </button>
                </div>
            </div>
            <div class="candlestick-container chart-container" id="candlestick-container"></div>
        `;
        widgetsSection.appendChild(candlestickWidget);
        this.chartContainers.candlestick = candlestickWidget.querySelector('#candlestick-container');
    }

    /**
     * Initialize chart components
     */
    initializeChartComponents() {
        try {
            // Initialize Market Heatmap
            if (this.chartContainers.heatmap) {
                const heatmap = new MarketHeatmapChart(this.chartContainers.heatmap, {
                    symbols: ['BTC', 'ETH', 'BNB', 'ADA', 'DOT', 'SOL', 'MATIC', 'AVAX'],
                    theme: this.theme
                });
                this.chartInstances.set('heatmap', heatmap);
            }

            // Initialize Orderbook Depth Chart
            if (this.chartContainers.orderbook) {
                const orderbook = new OrderbookDepthChart(this.chartContainers.orderbook, {
                    symbol: 'BTCUSDT',
                    maxLevels: 50,
                    theme: this.theme
                });
                this.chartInstances.set('orderbook', orderbook);
            }

            // Initialize Volume Profile Chart
            if (this.chartContainers.volumeProfile) {
                const volumeProfile = new VolumeProfileChart(this.chartContainers.volumeProfile, {
                    priceLevels: 100,
                    theme: this.theme
                });
                this.chartInstances.set('volumeProfile', volumeProfile);
            }

            // Initialize Advanced Candlestick Chart
            if (this.chartContainers.candlestick) {
                const candlestick = new AdvancedCandlestickChart(this.chartContainers.candlestick, {
                    symbol: 'BTCUSDT',
                    timeframe: '1h',
                    indicators: ['SMA20', 'EMA50', 'RSI', 'MACD'],
                    theme: this.theme
                });
                this.chartInstances.set('candlestick', candlestick);
            }

            // Initialize Chart Interaction Manager
            const chartArray = Array.from(this.chartInstances.values());
            this.chartInteractionManager = new ChartInteractionManager(chartArray, {
                enabled: true,
                syncEnabled: true,
                zoomEnabled: true,
                panEnabled: true,
                crosshairEnabled: true
            });

            // Initialize Real-time Data Binder
            this.realTimeDataBinder = new RealTimeDataBinder({
                wsUrl: 'wss://stream.bitget.com/mix/v1/stream',
                enabled: true,
                batchSize: 10,
                updateThrottle: 16
            });

            // Initialize Chart Synchronizer
            this.chartSynchronizer = new ChartSynchronizer({
                enabled: true,
                defaultSync: {
                    time: true,
                    zoom: true,
                    pan: false,
                    crosshair: true
                }
            });

            // Register charts with synchronizer
            this.chartInstances.forEach((chart, chartId) => {
                this.chartSynchronizer.registerChart(chartId, chart, 'main', {
                    isMaster: chartId === 'candlestick'
                });
            });

            // Bind real-time data to charts
            this.bindRealTimeData();

            this.emit('chartComponentsInitialized');

        } catch (error) {
            console.error('Chart components initialization failed:', error);
            this.emit('chartInitializationError', error);
        }
    }

    /**
     * Bind real-time data to charts
     */
    bindRealTimeData() {
        // Bind ticker data to heatmap
        this.realTimeDataBinder.bindChart('heatmap', this.chartInstances.get('heatmap'), 'ticker');
        
        // Bind depth data to orderbook
        this.realTimeDataBinder.bindChart('orderbook', this.chartInstances.get('orderbook'), 'depth');
        
        // Bind trade data to volume profile
        this.realTimeDataBinder.bindChart('volumeProfile', this.chartInstances.get('volumeProfile'), 'trades');
        
        // Bind kline data to candlestick
        this.realTimeDataBinder.bindChart('candlestick', this.chartInstances.get('candlestick'), 'kline_1h');
    }

    /**
     * Setup chart event listeners
     */
    setupChartEventListeners() {
        // Chart widget controls
        const symbolSelect = this.element.querySelector('#orderbook-symbol');
        if (symbolSelect) {
            symbolSelect.addEventListener('change', (e) => {
                const orderbook = this.chartInstances.get('orderbook');
                if (orderbook) {
                    orderbook.updateSettings({ symbol: e.target.value });
                }
            });
        }

        const timeframeSelect = this.element.querySelector('#candlestick-timeframe');
        if (timeframeSelect) {
            timeframeSelect.addEventListener('change', (e) => {
                const candlestick = this.chartInstances.get('candlestick');
                if (candlestick) {
                    candlestick.changeTimeframe(e.target.value);
                }
            });
        }

        const fullscreenBtn = this.element.querySelector('#chart-fullscreen');
        if (fullscreenBtn) {
            fullscreenBtn.addEventListener('click', () => {
                this.toggleChartFullscreen('candlestick');
            });
        }

        const volumeSettingsBtn = this.element.querySelector('#volume-settings');
        if (volumeSettingsBtn) {
            volumeSettingsBtn.addEventListener('click', () => {
                this.showVolumeProfileSettings();
            });
        }

        // Chart system events
        if (this.chartInteractionManager) {
            this.chartInteractionManager.on('chartClick', (data) => {
                this.emit('chartInteraction', { type: 'click', data });
            });

            this.chartInteractionManager.on('zoomChanged', (data) => {
                this.emit('chartInteraction', { type: 'zoom', data });
            });
        }

        if (this.realTimeDataBinder) {
            this.realTimeDataBinder.on('chartUpdated', (data) => {
                this.emit('chartDataUpdated', data);
            });

            this.realTimeDataBinder.on('connectionError', (error) => {
                this.showNotification('실시간 데이터 연결 오류', 'error');
            });
        }
    }

    /**
     * Toggle chart fullscreen mode
     */
    toggleChartFullscreen(chartId) {
        const chartWidget = this.element.querySelector(`[data-grid-item="${chartId}"]`);
        if (!chartWidget) return;

        chartWidget.classList.toggle('fullscreen');
        
        // Update chart size
        const chart = this.chartInstances.get(chartId);
        if (chart && chart.resize) {
            setTimeout(() => chart.resize(), 100);
        }
    }

    /**
     * Show volume profile settings modal
     */
    showVolumeProfileSettings() {
        const volumeProfile = this.chartInstances.get('volumeProfile');
        if (!volumeProfile) return;

        // Create settings modal (simplified)
        const modal = document.createElement('div');
        modal.className = 'modal';
        modal.innerHTML = `
            <div class="modal-content">
                <div class="modal-header">
                    <h3>볼륨 프로파일 설정</h3>
                    <button class="modal-close">&times;</button>
                </div>
                <div class="modal-body">
                    <div class="form-group">
                        <label>가격 레벨 수:</label>
                        <input type="range" id="price-levels" min="50" max="200" value="100">
                        <span id="levels-value">100</span>
                    </div>
                    <div class="form-group">
                        <label>
                            <input type="checkbox" id="show-poc" checked> POC 표시
                        </label>
                    </div>
                    <div class="form-group">
                        <label>
                            <input type="checkbox" id="show-value-area" checked> 밸류 에어리어 표시
                        </label>
                    </div>
                </div>
                <div class="modal-footer">
                    <button class="btn btn-primary" id="apply-settings">적용</button>
                    <button class="btn btn-secondary" id="cancel-settings">취소</button>
                </div>
            </div>
        `;

        document.body.appendChild(modal);
        modal.style.display = 'block';

        // Event listeners
        modal.querySelector('.modal-close').addEventListener('click', () => {
            modal.remove();
        });

        modal.querySelector('#cancel-settings').addEventListener('click', () => {
            modal.remove();
        });

        modal.querySelector('#apply-settings').addEventListener('click', () => {
            const settings = {
                priceLevels: parseInt(modal.querySelector('#price-levels').value),
                showPOC: modal.querySelector('#show-poc').checked,
                showValueArea: modal.querySelector('#show-value-area').checked
            };

            volumeProfile.updateProfileSettings(settings);
            modal.remove();
        });
    }

    /**
     * Start notification updates
     */
    startNotificationUpdates() {
        if (!this.options.notifications) return;
        
        // Initial notification load
        this.fetchNotifications();
        
        // Set up periodic updates
        this.notificationTimer = setInterval(() => {
            this.fetchNotifications();
        }, 10000); // Every 10 seconds
    }

    /**
     * Fetch notifications from API
     * @returns {Promise<void>}
     */
    async fetchNotifications() {
        try {
            const response = await fetch('/api/notifications');
            if (!response.ok) {
                throw new Error('알림 가져오기 실패');
            }
            
            const data = await response.json();
            this.updateNotifications(data);
            
        } catch (error) {
            console.error('알림 가져오기 실패:', error);
            this.emit('notificationError', error);
        }
    }

    /**
     * Update notifications display
     * @param {Object} data - Notification data
     */
    updateNotifications(data) {
        const container = this.find('#notification-container');
        const countBadge = this.find('#notification-count');
        
        if (!container) return;

        const { notifications = [], system_logs = [] } = data;
        const allItems = [...notifications, ...system_logs].sort((a, b) => 
            new Date(b.timestamp) - new Date(a.timestamp)
        );

        // Update notification count
        this.notificationCount = notifications.length;
        if (countBadge) {
            countBadge.textContent = this.notificationCount;
            countBadge.style.display = this.notificationCount > 0 ? 'inline' : 'none';
        }

        // Update store
        this.store.dispatch({
            type: 'UPDATE_UI_STATE',
            payload: { notifications: allItems.slice(0, this.options.maxNotifications) }
        });

        // Update container
        if (allItems.length === 0) {
            container.innerHTML = '<div class="loading-spinner">알림이 없습니다</div>';
            return;
        }

        const html = allItems.slice(0, 15).map(item => {
            return item.content ? 
                this.createNotificationItem(item) : 
                this.createSystemLogItem(item);
        }).join('');

        container.innerHTML = html;
        this.highlightNewNotifications(allItems);
        
        this.emit('notificationsUpdated', { count: this.notificationCount, items: allItems });
    }

    /**
     * Create notification item HTML
     * @param {Object} notification - Notification data
     * @returns {string} HTML string
     */
    createNotificationItem(notification) {
        const type = this.getNotificationType(notification.content);
        const time = notification.formatted_time || 
            new Date(notification.timestamp * 1000).toLocaleTimeString();
        
        return `
            <div class="notification-item ${type}" data-timestamp="${notification.timestamp}">
                <div class="notification-content">${this.escapeHtml(notification.content)}</div>
                <span class="notification-time">${time}</span>
            </div>
        `;
    }

    /**
     * Create system log item HTML
     * @param {Object} log - System log data
     * @returns {string} HTML string
     */
    createSystemLogItem(log) {
        const time = log.formatted_time || 
            log.timestamp.split('T')[1]?.split('.')[0] || '';
        
        return `
            <div class="system-log-item ${log.level}" data-timestamp="${log.timestamp}">
                <span class="log-component">[${log.component}]</span>
                ${this.escapeHtml(log.message)}
                <span class="notification-time">${time}</span>
            </div>
        `;
    }

    /**
     * Get notification type based on content
     * @param {string} content - Notification content
     * @returns {string} Notification type
     */
    getNotificationType(content) {
        const text = content.toLowerCase();
        if (text.includes('🚨') || text.includes('긴급') || text.includes('위험')) return 'emergency';
        if (text.includes('⚠️') || text.includes('경고') || text.includes('주의')) return 'warning';
        if (text.includes('💰') || text.includes('수익') || text.includes('성공')) return 'success';
        return 'info';
    }

    /**
     * Highlight new notifications with animation
     * @param {Array} items - Notification items
     */
    highlightNewNotifications(items) {
        const currentTime = Date.now() / 1000;
        items.forEach((item, index) => {
            const timestamp = item.timestamp || 0;
            if (currentTime - timestamp < 30) { // 30 seconds
                setTimeout(() => {
                    const element = this.find(`[data-timestamp="${timestamp}"]`);
                    if (element) {
                        element.style.animation = 'fadeInSlide 0.5s ease-out';
                        element.style.boxShadow = '0 0 10px rgba(100, 149, 237, 0.3)';
                    }
                }, index * 100); // Sequential animation
            }
        });
    }

    /**
     * Update summary cards
     */
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

    /**
     * Update individual summary card
     * @param {string} elementId - Card element ID
     * @param {number} value - Current value
     * @param {number} previousValue - Previous value for comparison
     */
    updateSummaryCard(elementId, value, previousValue = 0) {
        const element = this.find(`#${elementId}`);
        const changeElement = this.find(`#${elementId.replace('-', '-')}-change`);
        
        if (element) {
            element.textContent = this.formatCurrency(value);
            
            // Update card color
            const card = element.closest('.summary-card');
            if (card) {
                card.classList.remove('profit', 'loss');
                if (value > 0) card.classList.add('profit');
                else if (value < 0) card.classList.add('loss');
            }
        }

        if (changeElement && previousValue !== undefined) {
            const change = value - previousValue;
            const changePercent = previousValue !== 0 ? 
                (change / Math.abs(previousValue) * 100) : 0;
            
            changeElement.classList.remove('positive', 'negative');
            
            if (change > 0) {
                changeElement.classList.add('positive');
                changeElement.innerHTML = 
                    `<i class="fas fa-arrow-up"></i><span>+${changePercent.toFixed(1)}%</span>`;
            } else if (change < 0) {
                changeElement.classList.add('negative');
                changeElement.innerHTML = 
                    `<i class="fas fa-arrow-down"></i><span>${changePercent.toFixed(1)}%</span>`;
            } else {
                changeElement.innerHTML = 
                    `<i class="fas fa-minus"></i><span>0%</span>`;
            }
        }
    }

    /**
     * Update positions table
     */
    updatePositionsTable() {
        const tbody = this.find('#positions-tbody');
        const positions = this.data.positions || [];
        
        // Update position count
        const countElement = this.find('#positions-count');
        if (countElement) {
            countElement.textContent = positions.length;
        }

        if (!tbody) return;

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

        // Filter and sort positions
        let filteredPositions = this.filterPositions(positions);
        filteredPositions = this.sortPositions(filteredPositions);

        tbody.innerHTML = filteredPositions
            .map(position => this.createPositionRow(position))
            .join('');
        
        this.emit('positionsUpdated', { count: filteredPositions.length });
    }

    /**
     * Create position table row
     * @param {Object} position - Position data
     * @returns {string} HTML string
     */
    createPositionRow(position) {
        const pnlPercent = ((position.current_price - position.entry_price) / 
            position.entry_price * 100);
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
                        <button class="action-btn danger" data-action="close" data-position-id="${position.id}">
                            즉시 종료
                        </button>
                        <button class="action-btn warning" data-action="adjust-stop" data-position-id="${position.id}">
                            손절 조정
                        </button>
                        <button class="action-btn" data-action="partial-close" data-position-id="${position.id}">
                            50% 종료
                        </button>
                    </div>
                </td>
            </tr>`;
    }

    /**
     * Filter positions based on current filter
     * @param {Array} positions - Position array
     * @returns {Array} Filtered positions
     */
    filterPositions(positions) {
        if (this.currentFilter === 'all') return positions;
        return positions.filter(pos => pos.symbol.includes(this.currentFilter));
    }

    /**
     * Sort positions based on current sort criteria
     * @param {Array} positions - Position array
     * @returns {Array} Sorted positions
     */
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

    /**
     * Handle filter change
     * @param {string} filter - Filter value
     */
    handleFilter(filter) {
        this.currentFilter = filter;
        
        // Update UI
        this.findAll('.filter-btn[data-filter]').forEach(btn => {
            btn.classList.remove('active');
        });
        const activeBtn = this.find(`[data-filter="${filter}"]`);
        if (activeBtn) {
            activeBtn.classList.add('active');
        }
        
        // Update store
        this.store.dispatch({
            type: 'UPDATE_UI_STATE',
            payload: { currentFilter: filter }
        });
        
        this.updatePositionsTable();
        this.emit('filterChanged', filter);
    }

    /**
     * Handle sort change
     * @param {string} sort - Sort criteria
     */
    handleSort(sort) {
        this.currentSort = sort;
        
        // Update store
        this.store.dispatch({
            type: 'UPDATE_UI_STATE',
            payload: { currentSort: sort }
        });
        
        this.updatePositionsTable();
        this.emit('sortChanged', sort);
    }

    /**
     * Toggle theme
     */
    toggleTheme() {
        const themes = ['dark', 'light', 'high-contrast'];
        const currentIndex = themes.indexOf(this.theme);
        this.theme = themes[(currentIndex + 1) % themes.length];
        
        document.documentElement.setAttribute('data-theme', this.theme);
        localStorage.setItem('dashboard-theme', this.theme);
        
        // Update store
        this.store.dispatch({
            type: 'UPDATE_UI_STATE',
            payload: { theme: this.theme }
        });
        
        this.updateThemeUI();
        this.emit('themeChanged', this.theme);
    }

    /**
     * Update theme UI elements
     */
    updateThemeUI() {
        const themeIcon = this.find('#theme-icon');
        const themeText = this.find('#theme-text');
        
        if (!themeIcon || !themeText) return;
        
        const themeConfig = {
            dark: { icon: 'fa-moon', text: '다크' },
            light: { icon: 'fa-sun', text: '라이트' },
            'high-contrast': { icon: 'fa-adjust', text: '고대비' }
        };
        
        const config = themeConfig[this.theme];
        themeIcon.className = `fas ${config.icon}`;
        themeText.textContent = config.text;
    }

    /**
     * Open command palette
     */
    openCommandPalette() {
        // Create command palette if it doesn't exist
        let palette = this.find('#command-palette');
        if (!palette) {
            palette = this.createCommandPalette();
        }
        
        palette.style.display = 'flex';
        const input = palette.querySelector('input');
        if (input) {
            input.focus();
        }
    }
    
    /**
     * Create command palette
     */
    createCommandPalette() {
        const palette = document.createElement('div');
        palette.id = 'command-palette';
        palette.className = 'command-palette';
        palette.innerHTML = `
            <div class="command-palette-overlay">
                <div class="command-palette-content">
                    <div class="command-search">
                        <input type="text" placeholder="명령어 검색... (Ctrl+K)" class="command-input">
                    </div>
                    <div class="command-results">
                        <div class="command-item" data-action="refreshData">
                            <div class="command-info">
                                <div class="command-title">데이터 새로고침</div>
                                <div class="command-desc">최신 거래 데이터를 불러옵니다</div>
                            </div>
                            <div class="command-shortcut">Ctrl+R</div>
                        </div>
                        <div class="command-item" data-action="toggleTheme">
                            <div class="command-info">
                                <div class="command-title">테마 전환</div>
                                <div class="command-desc">다크/라이트 테마를 전환합니다</div>
                            </div>
                            <div class="command-shortcut">T</div>
                        </div>
                        <div class="command-item" data-action="showHelp">
                            <div class="command-info">
                                <div class="command-title">도움말</div>
                                <div class="command-desc">키보드 단축키 도움말을 표시합니다</div>
                            </div>
                            <div class="command-shortcut">?</div>
                        </div>
                        <div class="command-item" data-action="focusSearch">
                            <div class="command-info">
                                <div class="command-title">검색 포커스</div>
                                <div class="command-desc">검색 입력창에 포커스를 맞춥니다</div>
                            </div>
                            <div class="command-shortcut">Ctrl+F</div>
                        </div>
                        <div class="command-item" data-action="saveLayout">
                            <div class="command-info">
                                <div class="command-title">레이아웃 저장</div>
                                <div class="command-desc">현재 레이아웃을 저장합니다</div>
                            </div>
                            <div class="command-shortcut">Ctrl+S</div>
                        </div>
                        <div class="command-item" data-action="toggleFullscreen">
                            <div class="command-info">
                                <div class="command-title">전체화면</div>
                                <div class="command-desc">전체화면 모드를 전환합니다</div>
                            </div>
                            <div class="command-shortcut">F11</div>
                        </div>
                    </div>
                </div>
            </div>
        `;
        
        // Event listeners
        palette.addEventListener('click', (e) => {
            if (e.target === palette.querySelector('.command-palette-overlay')) {
                palette.style.display = 'none';
            }
        });
        
        palette.querySelectorAll('.command-item').forEach(item => {
            item.addEventListener('click', () => {
                const action = item.dataset.action;
                this.executeCommand(action);
                palette.style.display = 'none';
            });
        });
        
        const input = palette.querySelector('.command-input');
        input.addEventListener('keydown', (e) => {
            if (e.key === 'Escape') {
                palette.style.display = 'none';
            }
        });
        
        document.body.appendChild(palette);
        return palette;
    }
    
    /**
     * Execute command from palette
     */
    executeCommand(action) {
        switch (action) {
            case 'refreshData':
                this.refreshData();
                break;
            case 'toggleTheme':
                this.toggleTheme();
                break;
            case 'showHelp':
                this.keyboardManager?.showHelp();
                break;
            case 'focusSearch':
                this.focusSearch();
                break;
            case 'saveLayout':
                this.saveCurrentLayout();
                break;
            case 'toggleFullscreen':
                this.toggleFullscreen();
                break;
            default:
                console.warn('Unknown command:', action);
        }
    }
    
    /**
     * Focus search input
     */
    focusSearch() {
        const searchInput = this.find('.search-input');
        if (searchInput) {
            searchInput.focus();
            // Show search filter panel if hidden
            const filterPanel = this.find('.filter-panel');
            if (filterPanel && filterPanel.style.display === 'none') {
                filterPanel.style.display = 'block';
            }
        }
    }
    
    /**
     * Save current layout
     */
    saveCurrentLayout() {
        try {
            const layoutData = {
                timestamp: new Date().toISOString(),
                theme: this.theme,
                filters: this.searchFilterManager?.getActiveFilters() || {},
                // Add more layout data as needed
            };
            
            localStorage.setItem('savedDashboardLayout', JSON.stringify(layoutData));
            this.showToast('레이아웃이 저장되었습니다', 'success');
            
        } catch (error) {
            console.error('Failed to save layout:', error);
            this.showToast('레이아웃 저장 실패', 'error');
        }
    }
    
    /**
     * Toggle fullscreen mode
     */
    toggleFullscreen() {
        if (!document.fullscreenElement) {
            document.documentElement.requestFullscreen().catch(err => {
                console.error('Error attempting to enable fullscreen:', err);
            });
        } else {
            document.exitFullscreen();
        }
    }
    
    /**
     * Close all modals
     */
    closeAllModals() {
        // Close keyboard shortcut help modal
        if (this.keyboardManager) {
            this.keyboardManager.hideHelp();
            this.keyboardManager.hideSettings();
        }
        
        // Close command palette
        const palette = this.find('#command-palette');
        if (palette) {
            palette.style.display = 'none';
        }
        
        // Close any other modals
        const modals = this.findAll('.modal, .popup, .overlay');
        modals.forEach(modal => {
            if (modal.style.display !== 'none') {
                modal.style.display = 'none';
            }
        });
        
        // Remove modal-open class from body
        document.body.classList.remove('modal-open');
    }

    /**
     * Show toast notification
     * @param {string} message - Message to show
     * @param {string} type - Toast type (success, error, warning, info)
     */
    showToast(message, type = 'info') {
        const toast = this.createElement('div', {
            classes: ['toast', `toast-${type}`],
            innerHTML: `
                <div class="toast-content">
                    <i class="fas ${this.getToastIcon(type)}"></i>
                    <span>${this.escapeHtml(message)}</span>
                </div>
                <button class="toast-close">&times;</button>
            `
        });
        
        // Add close functionality
        const closeBtn = toast.querySelector('.toast-close');
        closeBtn.addEventListener('click', () => toast.remove());
        
        const container = this.find('#toast-container') || document.body;
        container.appendChild(toast);
        
        // Auto remove after 5 seconds
        setTimeout(() => {
            if (toast.parentNode) {
                toast.remove();
            }
        }, 5000);

        this.emit('toastShown', { message, type });
    }

    /**
     * Get toast icon class
     * @param {string} type - Toast type
     * @returns {string} Icon class
     */
    getToastIcon(type) {
        const icons = {
            success: 'fa-check-circle',
            error: 'fa-exclamation-circle',
            warning: 'fa-exclamation-triangle',
            info: 'fa-info-circle'
        };
        return icons[type] || icons.info;
    }

    /**
     * Update last update time
     */
    updateLastUpdateTime() {
        const element = this.find('#last-update');
        if (element) {
            element.textContent = new Date().toLocaleTimeString();
        }
    }

    /**
     * Refresh data
     */
    refreshData() {
        this.fetchDashboardData();
        this.emit('refreshTriggered');
    }

    /**
     * Detect important changes and provide visual feedback
     */
    detectChanges() {
        // Position change detection
        if (this.previousData.positions && this.data.positions) {
            this.data.positions.forEach(position => {
                const prevPosition = this.previousData.positions
                    .find(p => p.id === position.id);
                
                if (prevPosition && prevPosition.pnl !== position.pnl) {
                    const row = this.find(`tr[data-id="${position.id}"]`);
                    if (row) {
                        const flashClass = position.pnl > prevPosition.pnl ? 
                            'flash-profit' : 'flash-loss';
                        row.classList.add(flashClass);
                        setTimeout(() => row.classList.remove(flashClass), 800);
                    }
                }
            });
        }

        this.checkForImportantEvents();
    }

    /**
     * Check for important events and show notifications
     */
    checkForImportantEvents() {
        const positions = this.data.positions || [];
        
        positions.forEach(position => {
            const pnlPercent = ((position.current_price - position.entry_price) / 
                position.entry_price * 100);
            
            if (Math.abs(pnlPercent) >= 5) {
                const message = `${position.symbol} ${pnlPercent >= 0 ? '수익' : '손실'} ${Math.abs(pnlPercent).toFixed(1)}% 도달`;
                this.showNotification(message, pnlPercent >= 0 ? 'success' : 'warning');
            }
        });
    }

    /**
     * Show browser notification
     * @param {string} message - Message to show
     * @param {string} type - Notification type
     */
    showNotification(message, type = 'info') {
        // Browser notification
        if ('Notification' in window && Notification.permission === 'granted') {
            new Notification('GPTBITCOIN 알림', {
                body: message,
                icon: '/favicon.ico'
            });
        }
        
        // Toast notification
        this.showToast(message, type);
    }

    /**
     * Handle search request from search filter manager
     * @param {Object} searchData - Search query and filters
     */
    handleSearchRequest(searchData) {
        const { query, filters } = searchData;
        let results = this.searchableData || [];
        
        // Text search
        if (query && query.trim()) {
            const searchTerm = query.toLowerCase().trim();
            results = results.filter(item => 
                item.searchText && item.searchText.includes(searchTerm)
            );
        }
        
        // Apply filters
        results = this.applySearchFilters(results, filters);
        
        // Sort results by relevance or specified criteria
        results = this.sortSearchResults(results, query);
        
        // Update search filter manager with results
        if (this.searchFilterManager) {
            this.searchFilterManager.updateResults(results);
        }
        
        // Store filtered data for other components
        this.filteredData = results;
        
        this.emit('searchCompleted', { query, filters, results: results.length });
    }
    
    /**
     * Apply search filters to results
     * @param {Array} results - Search results
     * @param {Object} filters - Filter criteria
     * @returns {Array} Filtered results
     */
    applySearchFilters(results, filters) {
        if (!filters || Object.keys(filters).length === 0) return results;
        
        return results.filter(item => {
            // Symbol filter
            if (filters.symbol && Array.isArray(filters.symbol)) {
                if (!filters.symbol.includes(item.symbol)) return false;
            }
            
            // Side filter
            if (filters.side && filters.side !== item.side) return false;
            
            // P&L range filter
            if (filters.pnl) {
                const pnl = parseFloat(item.pnl || 0);
                if (filters.pnl.min !== null && pnl < filters.pnl.min) return false;
                if (filters.pnl.max !== null && pnl > filters.pnl.max) return false;
            }
            
            // Volume range filter
            if (filters.volume) {
                const volume = parseFloat(item.volume || item.size * item.current_price || 0);
                if (filters.volume.min !== null && volume < filters.volume.min) return false;
                if (filters.volume.max !== null && volume > filters.volume.max) return false;
            }
            
            // Status filter
            if (filters.status && Array.isArray(filters.status)) {
                const status = this.getItemStatus(item);
                if (!filters.status.includes(status)) return false;
            }
            
            // Time range filter
            if (filters.timeRange) {
                const itemDate = new Date(item.timestamp || item.created_at);
                if (filters.timeRange.start) {
                    const startDate = new Date(filters.timeRange.start);
                    if (itemDate < startDate) return false;
                }
                if (filters.timeRange.end) {
                    const endDate = new Date(filters.timeRange.end + 'T23:59:59');
                    if (itemDate > endDate) return false;
                }
            }
            
            return true;
        });
    }
    
    /**
     * Get status of an item for filtering
     * @param {Object} item - Data item
     * @returns {string} Status string
     */
    getItemStatus(item) {
        if (item.type === 'position') {
            if (item.size > 0) return '활성';
            return '완료';
        }
        if (item.type === 'trade') {
            return item.status || '완료';
        }
        return '기타';
    }
    
    /**
     * Sort search results
     * @param {Array} results - Search results
     * @param {string} query - Search query for relevance
     * @returns {Array} Sorted results
     */
    sortSearchResults(results, query) {
        if (!query) return results;
        
        const searchTerm = query.toLowerCase();
        
        return results.sort((a, b) => {
            // Exact symbol match first
            const aExactSymbol = a.symbol && a.symbol.toLowerCase() === searchTerm;
            const bExactSymbol = b.symbol && b.symbol.toLowerCase() === searchTerm;
            if (aExactSymbol && !bExactSymbol) return -1;
            if (!aExactSymbol && bExactSymbol) return 1;
            
            // Symbol starts with query
            const aStartsSymbol = a.symbol && a.symbol.toLowerCase().startsWith(searchTerm);
            const bStartsSymbol = b.symbol && b.symbol.toLowerCase().startsWith(searchTerm);
            if (aStartsSymbol && !bStartsSymbol) return -1;
            if (!aStartsSymbol && bStartsSymbol) return 1;
            
            // Sort by timestamp (newest first)
            const aTime = new Date(a.timestamp || a.created_at || 0);
            const bTime = new Date(b.timestamp || b.created_at || 0);
            return bTime - aTime;
        });
    }
    
    /**
     * Handle search result selection
     * @param {Object} selectedItem - Selected search result
     */
    handleSearchSelection(selectedItem) {
        if (selectedItem.type === 'position') {
            this.highlightPosition(selectedItem.id);
            this.scrollToPosition(selectedItem.id);
        } else if (selectedItem.type === 'trade') {
            this.highlightTrade(selectedItem.id);
            this.scrollToTrade(selectedItem.id);
        }
        
        this.emit('searchItemSelected', selectedItem);
    }
    
    /**
     * Handle search sort change
     * @param {string} sortBy - Sort criteria
     */
    handleSearchSort(sortBy) {
        let sortedResults = [...this.filteredData];
        
        switch (sortBy) {
            case 'time':
                sortedResults.sort((a, b) => {
                    const aTime = new Date(a.timestamp || a.created_at || 0);
                    const bTime = new Date(b.timestamp || b.created_at || 0);
                    return bTime - aTime;
                });
                break;
            case 'pnl':
                sortedResults.sort((a, b) => (b.pnl || 0) - (a.pnl || 0));
                break;
            case 'volume':
                sortedResults.sort((a, b) => {
                    const aVol = a.volume || (a.size * a.current_price) || 0;
                    const bVol = b.volume || (b.size * b.current_price) || 0;
                    return bVol - aVol;
                });
                break;
            case 'relevance':
            default:
                // Keep current relevance-based sorting
                break;
        }
        
        if (this.searchFilterManager) {
            this.searchFilterManager.updateResults(sortedResults);
        }
        
        this.filteredData = sortedResults;
        this.emit('searchSorted', sortBy);
    }
    
    /**
     * Highlight position in table
     * @param {string} positionId - Position ID
     */
    highlightPosition(positionId) {
        // Remove previous highlights
        this.findAll('.search-highlighted').forEach(el => {
            el.classList.remove('search-highlighted');
        });
        
        // Highlight target position
        const row = this.find(`tr[data-id="${positionId}"]`);
        if (row) {
            row.classList.add('search-highlighted');
            setTimeout(() => row.classList.remove('search-highlighted'), 3000);
        }
    }
    
    /**
     * Scroll to position in table
     * @param {string} positionId - Position ID
     */
    scrollToPosition(positionId) {
        const row = this.find(`tr[data-id="${positionId}"]`);
        if (row) {
            row.scrollIntoView({ 
                behavior: 'smooth', 
                block: 'center' 
            });
        }
    }
    
    /**
     * Highlight trade in table
     * @param {string} tradeId - Trade ID
     */
    highlightTrade(tradeId) {
        const row = this.find(`tr[data-trade-id="${tradeId}"]`);
        if (row) {
            row.classList.add('search-highlighted');
            setTimeout(() => row.classList.remove('search-highlighted'), 3000);
        }
    }
    
    /**
     * Scroll to trade in table
     * @param {string} tradeId - Trade ID
     */
    scrollToTrade(tradeId) {
        const row = this.find(`tr[data-trade-id="${tradeId}"]`);
        if (row) {
            row.scrollIntoView({ 
                behavior: 'smooth', 
                block: 'center' 
            });
        }
    }

    /**
     * Handle new notification from event bus
     * @param {Object} notification - Notification data
     */
    handleNewNotification(notification) {
        this.showToast(notification.message, notification.type);
    }

    /**
     * Cleanup when component is destroyed
     */
    destroy() {
        // Clear timers
        if (this.notificationTimer) {
            clearInterval(this.notificationTimer);
        }
        
        // Destroy search filter manager
        if (this.searchFilterManager) {
            this.searchFilterManager.destroy();
        }
        
        // Destroy keyboard shortcut manager
        if (this.keyboardManager) {
            this.keyboardManager.destroy();
        }
        
        // Destroy grid manager
        if (this.gridManager) {
            this.gridManager.destroy();
        }
        
        // Remove event bus listeners
        this.eventBus.removeAllListeners();
        
        super.destroy();
    }

    // Additional helper methods can be added here...
    // updateTradesTable, updateWidgets, updateSystemStatus, etc.
    // For brevity, I'll focus on the core structure and key methods
}

export default TradingDashboard;
import { BaseComponent } from './BaseComponent.js';

/**
 * 반응형 그리드 레이아웃 시스템
 * - CSS Grid 기반 반응형 레이아웃
 * - 브레이크포인트별 레이아웃 자동 조정
 * - 동적 컬럼/행 관리
 * - 위젯 자동 리플로우
 * - 터치 디바이스 최적화
 */
export class ResponsiveGridManager extends BaseComponent {
    constructor(container, options = {}) {
        super(container, options);
        
        // 그리드 설정
        this.gridContainer = container;
        this.gridItems = new Map(); // 그리드 아이템 관리
        this.currentBreakpoint = null;
        this.isInitialized = false;
        
        // 브레이크포인트 정의
        this.breakpoints = {
            xs: { min: 0, max: 575, columns: 1, gap: '0.5rem', margin: '0.5rem' },
            sm: { min: 576, max: 767, columns: 2, gap: '0.75rem', margin: '0.75rem' },
            md: { min: 768, max: 991, columns: 3, gap: '1rem', margin: '1rem' },
            lg: { min: 992, max: 1199, columns: 4, gap: '1.25rem', margin: '1.25rem' },
            xl: { min: 1200, max: 1399, columns: 6, gap: '1.5rem', margin: '1.5rem' },
            xxl: { min: 1400, max: Infinity, columns: 8, gap: '1.75rem', margin: '2rem' }
        };
        
        // 레이아웃 템플릿
        this.layoutTemplates = {
            dashboard: {
                xs: [
                    { id: 'balance', span: 1, order: 1 },
                    { id: 'positions', span: 1, order: 2 },
                    { id: 'trades', span: 1, order: 3 },
                    { id: 'chart', span: 1, order: 4 },
                    { id: 'notifications', span: 1, order: 5 }
                ],
                sm: [
                    { id: 'balance', span: 2, order: 1 },
                    { id: 'positions', span: 2, order: 2 },
                    { id: 'trades', span: 1, order: 3 },
                    { id: 'chart', span: 1, order: 4 },
                    { id: 'notifications', span: 2, order: 5 }
                ],
                md: [
                    { id: 'balance', span: 1, order: 1 },
                    { id: 'positions', span: 2, order: 2 },
                    { id: 'trades', span: 1, order: 4 },
                    { id: 'chart', span: 2, order: 3 },
                    { id: 'notifications', span: 1, order: 5 }
                ],
                lg: [
                    { id: 'balance', span: 1, order: 1 },
                    { id: 'positions', span: 2, order: 2 },
                    { id: 'chart', span: 2, order: 3 },
                    { id: 'trades', span: 1, order: 4 },
                    { id: 'notifications', span: 1, order: 5 }
                ],
                xl: [
                    { id: 'balance', span: 2, order: 1 },
                    { id: 'positions', span: 3, order: 2 },
                    { id: 'chart', span: 4, order: 3 },
                    { id: 'trades', span: 2, order: 4 },
                    { id: 'notifications', span: 1, order: 5 }
                ],
                xxl: [
                    { id: 'balance', span: 2, order: 1 },
                    { id: 'positions', span: 3, order: 2 },
                    { id: 'chart', span: 5, order: 3 },
                    { id: 'trades', span: 2, order: 4 },
                    { id: 'notifications', span: 1, order: 5 }
                ]
            },
            trading: {
                xs: [
                    { id: 'chart', span: 1, order: 1 },
                    { id: 'orderbook', span: 1, order: 2 },
                    { id: 'trades', span: 1, order: 3 },
                    { id: 'positions', span: 1, order: 4 }
                ],
                sm: [
                    { id: 'chart', span: 2, order: 1 },
                    { id: 'orderbook', span: 1, order: 2 },
                    { id: 'trades', span: 1, order: 3 },
                    { id: 'positions', span: 2, order: 4 }
                ],
                md: [
                    { id: 'chart', span: 2, order: 1 },
                    { id: 'orderbook', span: 1, order: 2 },
                    { id: 'trades', span: 1, order: 3 },
                    { id: 'positions', span: 2, order: 4 }
                ],
                lg: [
                    { id: 'chart', span: 3, order: 1 },
                    { id: 'orderbook', span: 1, order: 2 },
                    { id: 'trades', span: 1, order: 3 },
                    { id: 'positions', span: 2, order: 4 }
                ],
                xl: [
                    { id: 'chart', span: 4, order: 1 },
                    { id: 'orderbook', span: 1, order: 2 },
                    { id: 'trades', span: 1, order: 3 },
                    { id: 'positions', span: 2, order: 4 }
                ],
                xxl: [
                    { id: 'chart', span: 5, order: 1 },
                    { id: 'orderbook', span: 1, order: 2 },
                    { id: 'trades', span: 2, order: 3 },
                    { id: 'positions', span: 3, order: 4 }
                ]
            },
            compact: {
                xs: [{ id: 'summary', span: 1, order: 1 }],
                sm: [{ id: 'summary', span: 2, order: 1 }],
                md: [{ id: 'summary', span: 3, order: 1 }],
                lg: [{ id: 'summary', span: 4, order: 1 }],
                xl: [{ id: 'summary', span: 6, order: 1 }],
                xxl: [{ id: 'summary', span: 8, order: 1 }]
            }
        };
        
        // 현재 레이아웃
        this.currentLayout = 'dashboard';
        this.customLayouts = this.loadCustomLayouts();
        
        // 리사이즈 이벤트 디바운싱
        this.resizeTimeout = null;
        this.resizeObserver = null;
        
        // 터치 지원 감지
        this.isTouchDevice = 'ontouchstart' in window || navigator.maxTouchPoints > 0;
        
        this.init();
    }

    init() {
        this.setupGridContainer();
        this.detectBreakpoint();
        this.setupEventListeners();
        this.setupResizeObserver();
        this.initializeGrid();
        
        this.isInitialized = true;
        this.emit('gridInitialized');
    }

    /**
     * 그리드 컨테이너 설정
     */
    setupGridContainer() {
        this.gridContainer.classList.add('responsive-grid');
        
        // CSS Grid 기본 설정
        this.gridContainer.style.display = 'grid';
        this.gridContainer.style.width = '100%';
        this.gridContainer.style.minHeight = '100vh';
        this.gridContainer.style.gridAutoRows = 'min-content';
        
        // 터치 디바이스 최적화
        if (this.isTouchDevice) {
            this.gridContainer.classList.add('touch-optimized');
            this.gridContainer.style.touchAction = 'pan-y';
        }
    }

    /**
     * 현재 브레이크포인트 감지
     */
    detectBreakpoint() {
        const width = window.innerWidth;
        let newBreakpoint = null;
        
        for (const [key, bp] of Object.entries(this.breakpoints)) {
            if (width >= bp.min && width <= bp.max) {
                newBreakpoint = key;
                break;
            }
        }
        
        if (newBreakpoint !== this.currentBreakpoint) {
            const previousBreakpoint = this.currentBreakpoint;
            this.currentBreakpoint = newBreakpoint;
            
            this.emit('breakpointChanged', {
                current: newBreakpoint,
                previous: previousBreakpoint,
                width
            });
            
            this.updateGridLayout();
        }
    }

    /**
     * 이벤트 리스너 설정
     */
    setupEventListeners() {
        // 윈도우 리사이즈
        window.addEventListener('resize', this.handleResize.bind(this));
        
        // 방향 변경 (모바일)
        window.addEventListener('orientationchange', () => {
            setTimeout(() => {
                this.handleResize();
            }, 100);
        });
        
        // 키보드 단축키
        document.addEventListener('keydown', this.handleKeydown.bind(this));
        
        // 미디어 쿼리 변경 감지
        this.setupMediaQueryListeners();
    }

    /**
     * 미디어 쿼리 리스너 설정
     */
    setupMediaQueryListeners() {
        Object.entries(this.breakpoints).forEach(([name, bp]) => {
            if (bp.max !== Infinity) {
                const mediaQuery = window.matchMedia(`(max-width: ${bp.max}px)`);
                mediaQuery.addListener(() => this.detectBreakpoint());
            }
        });
        
        // 다크 모드 감지
        const darkModeQuery = window.matchMedia('(prefers-color-scheme: dark)');
        darkModeQuery.addListener((e) => {
            this.emit('colorSchemeChanged', e.matches ? 'dark' : 'light');
        });
        
        // 고대비 모드 감지
        const highContrastQuery = window.matchMedia('(prefers-contrast: high)');
        highContrastQuery.addListener((e) => {
            this.gridContainer.classList.toggle('high-contrast', e.matches);
        });
        
        // 애니메이션 감소 모드 감지
        const reducedMotionQuery = window.matchMedia('(prefers-reduced-motion: reduce)');
        reducedMotionQuery.addListener((e) => {
            this.gridContainer.classList.toggle('reduced-motion', e.matches);
        });
    }

    /**
     * ResizeObserver 설정
     */
    setupResizeObserver() {
        if ('ResizeObserver' in window) {
            this.resizeObserver = new ResizeObserver((entries) => {
                for (const entry of entries) {
                    if (entry.target === this.gridContainer) {
                        this.handleContainerResize(entry);
                    } else {
                        this.handleItemResize(entry);
                    }
                }
            });
            
            this.resizeObserver.observe(this.gridContainer);
        }
    }

    /**
     * 리사이즈 핸들러
     */
    handleResize() {
        clearTimeout(this.resizeTimeout);
        this.resizeTimeout = setTimeout(() => {
            this.detectBreakpoint();
            this.optimizeGridLayout();
        }, 150);
    }

    /**
     * 컨테이너 리사이즈 핸들러
     */
    handleContainerResize(entry) {
        const { inlineSize, blockSize } = entry.contentBoxSize[0] || entry.contentRect;
        
        this.emit('containerResized', {
            width: inlineSize,
            height: blockSize,
            breakpoint: this.currentBreakpoint
        });
    }

    /**
     * 아이템 리사이즈 핸들러
     */
    handleItemResize(entry) {
        const itemId = entry.target.dataset.gridItem;
        if (itemId && this.gridItems.has(itemId)) {
            const item = this.gridItems.get(itemId);
            const { inlineSize, blockSize } = entry.contentBoxSize[0] || entry.contentRect;
            
            item.actualSize = { width: inlineSize, height: blockSize };
            
            this.emit('itemResized', {
                id: itemId,
                width: inlineSize,
                height: blockSize
            });
        }
    }

    /**
     * 키보드 이벤트 핸들러
     */
    handleKeydown(e) {
        // Alt + 숫자키로 레이아웃 전환
        if (e.altKey && !e.ctrlKey && !e.shiftKey) {
            const layouts = Object.keys(this.layoutTemplates);
            const num = parseInt(e.key);
            if (num >= 1 && num <= layouts.length) {
                e.preventDefault();
                this.switchLayout(layouts[num - 1]);
            }
        }
        
        // Ctrl + Alt + R로 레이아웃 초기화
        if (e.ctrlKey && e.altKey && e.key === 'r') {
            e.preventDefault();
            this.resetLayout();
        }
    }

    /**
     * 그리드 초기화
     */
    initializeGrid() {
        this.collectGridItems();
        this.updateGridLayout();
    }

    /**
     * 그리드 아이템 수집
     */
    collectGridItems() {
        const items = this.gridContainer.querySelectorAll('[data-grid-item]');
        
        items.forEach((element, index) => {
            const id = element.dataset.gridItem || `item-${index}`;
            
            const item = {
                id,
                element,
                originalIndex: index,
                span: parseInt(element.dataset.gridSpan) || 1,
                minSpan: parseInt(element.dataset.gridMinSpan) || 1,
                maxSpan: parseInt(element.dataset.gridMaxSpan) || 999,
                priority: parseInt(element.dataset.gridPriority) || 0,
                breakpointVisibility: this.parseBreakpointVisibility(element.dataset.gridShow),
                isResizable: element.dataset.gridResizable === 'true',
                isMovable: element.dataset.gridMovable !== 'false',
                aspectRatio: element.dataset.gridAspectRatio || null
            };
            
            this.gridItems.set(id, item);
            
            // ResizeObserver 등록
            if (this.resizeObserver) {
                this.resizeObserver.observe(element);
            }
        });
    }

    /**
     * 브레이크포인트별 가시성 파싱
     */
    parseBreakpointVisibility(showAttr) {
        if (!showAttr) return {};
        
        const visibility = {};
        const rules = showAttr.split(',');
        
        rules.forEach(rule => {
            const [breakpoint, visible] = rule.trim().split(':');
            visibility[breakpoint] = visible !== 'false';
        });
        
        return visibility;
    }

    /**
     * 그리드 레이아웃 업데이트
     */
    updateGridLayout() {
        if (!this.currentBreakpoint) return;
        
        const bp = this.breakpoints[this.currentBreakpoint];
        const layout = this.getCurrentLayout();
        
        // 그리드 컨테이너 스타일 업데이트
        this.updateContainerStyles(bp);
        
        // 아이템 배치
        this.arrangeItems(layout);
        
        // 가시성 업데이트
        this.updateItemVisibility();
        
        this.emit('layoutUpdated', {
            breakpoint: this.currentBreakpoint,
            layout: this.currentLayout
        });
    }

    /**
     * 컨테이너 스타일 업데이트
     */
    updateContainerStyles(bp) {
        this.gridContainer.style.gridTemplateColumns = `repeat(${bp.columns}, 1fr)`;
        this.gridContainer.style.gap = bp.gap;
        this.gridContainer.style.padding = bp.margin;
        
        // 브레이크포인트 클래스 업데이트
        this.gridContainer.className = this.gridContainer.className
            .replace(/bp-\w+/g, '')
            .concat(` bp-${this.currentBreakpoint}`);
    }

    /**
     * 현재 레이아웃 가져오기
     */
    getCurrentLayout() {
        const customLayout = this.customLayouts[this.currentLayout];
        if (customLayout && customLayout[this.currentBreakpoint]) {
            return customLayout[this.currentBreakpoint];
        }
        
        const template = this.layoutTemplates[this.currentLayout];
        return template ? template[this.currentBreakpoint] : [];
    }

    /**
     * 아이템 배치
     */
    arrangeItems(layout) {
        if (!layout) return;
        
        // 레이아웃에 따라 아이템 정렬
        const sortedItems = layout.sort((a, b) => a.order - b.order);
        
        sortedItems.forEach((layoutItem, index) => {
            const item = this.gridItems.get(layoutItem.id);
            if (!item) return;
            
            const span = Math.min(
                Math.max(layoutItem.span, item.minSpan),
                item.maxSpan,
                this.breakpoints[this.currentBreakpoint].columns
            );
            
            // CSS Grid 속성 설정
            item.element.style.gridColumn = `span ${span}`;
            item.element.style.order = layoutItem.order || index;
            
            // 아스펙트 비율 적용
            if (item.aspectRatio) {
                item.element.style.aspectRatio = item.aspectRatio;
            }
            
            // 터치 디바이스 최적화
            if (this.isTouchDevice) {
                item.element.style.minHeight = '44px'; // 터치 타겟 최소 크기
            }
        });
    }

    /**
     * 아이템 가시성 업데이트
     */
    updateItemVisibility() {
        this.gridItems.forEach((item) => {
            const visibility = item.breakpointVisibility;
            const shouldShow = visibility[this.currentBreakpoint] !== false;
            
            if (shouldShow) {
                item.element.style.display = '';
                item.element.removeAttribute('aria-hidden');
            } else {
                item.element.style.display = 'none';
                item.element.setAttribute('aria-hidden', 'true');
            }
        });
    }

    /**
     * 그리드 레이아웃 최적화
     */
    optimizeGridLayout() {
        // 빈 공간 최소화
        this.compactLayout();
        
        // 성능 최적화
        this.optimizePerformance();
    }

    /**
     * 레이아웃 압축
     */
    compactLayout() {
        const bp = this.breakpoints[this.currentBreakpoint];
        const columns = bp.columns;
        
        // 현재 그리드 상태 분석
        const gridState = this.analyzeGridState();
        
        // 빈 공간을 채우기 위해 아이템 재배치
        this.fillEmptySpaces(gridState, columns);
    }

    /**
     * 그리드 상태 분석
     */
    analyzeGridState() {
        const state = {
            occupiedCells: new Set(),
            itemPositions: new Map(),
            emptySpaces: []
        };
        
        this.gridItems.forEach((item) => {
            if (item.element.style.display !== 'none') {
                const computedStyle = getComputedStyle(item.element);
                const gridColumn = computedStyle.gridColumnStart;
                const gridRow = computedStyle.gridRowStart;
                
                if (gridColumn !== 'auto' && gridRow !== 'auto') {
                    state.itemPositions.set(item.id, {
                        column: parseInt(gridColumn),
                        row: parseInt(gridRow),
                        span: item.span || 1
                    });
                }
            }
        });
        
        return state;
    }

    /**
     * 빈 공간 채우기
     */
    fillEmptySpaces(gridState, columns) {
        // 구현 로직 - 복잡한 알고리즘이므로 기본 버전만 구현
        // 실제로는 더 정교한 패킹 알고리즘이 필요
        
        this.emit('layoutCompacted');
    }

    /**
     * 성능 최적화
     */
    optimizePerformance() {
        // CSS containment 적용
        this.gridContainer.style.contain = 'layout style paint';
        
        // 가상화가 필요한 많은 아이템의 경우
        if (this.gridItems.size > 50) {
            this.enableVirtualization();
        }
        
        // GPU 가속 활성화
        this.gridItems.forEach((item) => {
            if (item.isMovable || item.isResizable) {
                item.element.style.willChange = 'transform';
            }
        });
    }

    /**
     * 가상화 활성화
     */
    enableVirtualization() {
        // 큰 그리드에 대한 가상화 로직
        // 뷰포트에 보이지 않는 아이템은 DOM에서 제거
        
        this.emit('virtualizationEnabled');
    }

    /**
     * 레이아웃 전환
     */
    switchLayout(layoutName) {
        if (this.layoutTemplates[layoutName] || this.customLayouts[layoutName]) {
            this.currentLayout = layoutName;
            this.updateGridLayout();
            
            this.emit('layoutSwitched', layoutName);
            return true;
        }
        return false;
    }

    /**
     * 레이아웃 초기화
     */
    resetLayout() {
        this.currentLayout = 'dashboard';
        this.updateGridLayout();
        
        this.emit('layoutReset');
    }

    /**
     * 커스텀 레이아웃 저장
     */
    saveCustomLayout(name, layout) {
        if (!this.customLayouts[name]) {
            this.customLayouts[name] = {};
        }
        
        this.customLayouts[name][this.currentBreakpoint] = layout;
        this.saveCustomLayouts();
        
        this.emit('customLayoutSaved', { name, layout });
    }

    /**
     * 아이템 추가
     */
    addItem(element, config = {}) {
        const id = config.id || element.dataset.gridItem || `item-${Date.now()}`;
        
        element.dataset.gridItem = id;
        if (config.span) element.dataset.gridSpan = config.span;
        if (config.priority) element.dataset.gridPriority = config.priority;
        
        const item = {
            id,
            element,
            span: config.span || 1,
            minSpan: config.minSpan || 1,
            maxSpan: config.maxSpan || 999,
            priority: config.priority || 0,
            breakpointVisibility: config.breakpointVisibility || {},
            isResizable: config.isResizable || false,
            isMovable: config.isMovable !== false
        };
        
        this.gridItems.set(id, item);
        this.gridContainer.appendChild(element);
        
        if (this.resizeObserver) {
            this.resizeObserver.observe(element);
        }
        
        this.updateGridLayout();
        this.emit('itemAdded', id);
        
        return id;
    }

    /**
     * 아이템 제거
     */
    removeItem(id) {
        const item = this.gridItems.get(id);
        if (!item) return false;
        
        if (this.resizeObserver) {
            this.resizeObserver.unobserve(item.element);
        }
        
        item.element.remove();
        this.gridItems.delete(id);
        
        this.updateGridLayout();
        this.emit('itemRemoved', id);
        
        return true;
    }

    /**
     * 커스텀 레이아웃 로드
     */
    loadCustomLayouts() {
        try {
            const saved = localStorage.getItem('responsiveGridLayouts');
            return saved ? JSON.parse(saved) : {};
        } catch (error) {
            console.warn('Failed to load custom layouts:', error);
            return {};
        }
    }

    /**
     * 커스텀 레이아웃 저장
     */
    saveCustomLayouts() {
        try {
            localStorage.setItem('responsiveGridLayouts', JSON.stringify(this.customLayouts));
        } catch (error) {
            console.error('Failed to save custom layouts:', error);
        }
    }

    /**
     * 현재 상태 내보내기
     */
    exportLayout() {
        return {
            currentLayout: this.currentLayout,
            currentBreakpoint: this.currentBreakpoint,
            customLayouts: this.customLayouts,
            items: Array.from(this.gridItems.values()).map(item => ({
                id: item.id,
                span: item.span,
                priority: item.priority,
                breakpointVisibility: item.breakpointVisibility
            }))
        };
    }

    /**
     * 레이아웃 가져오기
     */
    importLayout(layoutData) {
        if (layoutData.customLayouts) {
            this.customLayouts = { ...this.customLayouts, ...layoutData.customLayouts };
            this.saveCustomLayouts();
        }
        
        if (layoutData.currentLayout) {
            this.switchLayout(layoutData.currentLayout);
        }
        
        this.emit('layoutImported', layoutData);
    }

    /**
     * 디버그 정보
     */
    getDebugInfo() {
        return {
            currentBreakpoint: this.currentBreakpoint,
            currentLayout: this.currentLayout,
            itemCount: this.gridItems.size,
            containerSize: {
                width: this.gridContainer.offsetWidth,
                height: this.gridContainer.offsetHeight
            },
            isTouchDevice: this.isTouchDevice,
            items: Array.from(this.gridItems.entries()).map(([id, item]) => ({
                id,
                visible: item.element.style.display !== 'none',
                size: item.actualSize
            }))
        };
    }

    /**
     * 정리
     */
    destroy() {
        // 이벤트 리스너 제거
        window.removeEventListener('resize', this.handleResize);
        window.removeEventListener('orientationchange', this.handleResize);
        document.removeEventListener('keydown', this.handleKeydown);
        
        // ResizeObserver 해제
        if (this.resizeObserver) {
            this.resizeObserver.disconnect();
        }
        
        // 타이머 정리
        if (this.resizeTimeout) {
            clearTimeout(this.resizeTimeout);
        }
        
        // 그리드 아이템 정리
        this.gridItems.clear();
        
        super.destroy();
    }
}

export default ResponsiveGridManager;
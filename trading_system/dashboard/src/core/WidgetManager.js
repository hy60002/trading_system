/**
 * @fileoverview 위젯 관리 시스템
 * @description 대시보드 위젯의 배치, 크기 조절, 커스터마이징을 관리하는 시스템
 */

import { dragDropManager } from './DragDropManager.js';
import { eventBus } from './EventBus.js';
import { globalStore } from './Store.js';

/**
 * 위젯 관리자
 * @class WidgetManager
 */
export class WidgetManager {
    constructor() {
        this.widgets = new Map();
        this.containers = new Map();
        this.layouts = new Map();
        this.currentLayout = 'default';
        this.isEditMode = false;
        this.gridSize = { cols: 12, rows: 12 };
        this.cellSize = { width: 100, height: 100 };
        
        // 설정
        this.config = {
            minWidgetSize: { width: 2, height: 2 },
            maxWidgetSize: { width: 12, height: 12 },
            snapToGrid: true,
            showGridLines: false,
            enableResize: true,
            enableMove: true,
            saveInterval: 2000,
            animationDuration: 300
        };
        
        // 상태 추적
        this.state = {
            isResizing: false,
            isDragging: false,
            resizeHandle: null,
            activeWidget: null,
            ghostElement: null
        };
        
        // 위젯 타입 정의
        this.widgetTypes = new Map();
        this.registerDefaultWidgetTypes();
        
        // 레이아웃 변경 디바운서
        this.saveDebouncer = null;
        
        // 성능 메트릭
        this.metrics = {
            widgetCount: 0,
            layoutChanges: 0,
            resizeOperations: 0,
            moveOperations: 0
        };
        
        this.initialize();
    }

    /**
     * 초기화
     * @private
     */
    initialize() {
        this.setupEventListeners();
        this.loadLayouts();
        this.createGridOverlay();
        this.registerDragTypes();
        
        // 기본 레이아웃 설정
        this.setLayout(this.currentLayout);
    }

    /**
     * 이벤트 리스너 설정
     * @private
     */
    setupEventListeners() {
        // 윈도우 리사이즈
        window.addEventListener('resize', this.handleWindowResize.bind(this));
        
        // 키보드 이벤트
        document.addEventListener('keydown', this.handleKeyDown.bind(this));
        document.addEventListener('keyup', this.handleKeyUp.bind(this));
        
        // 위젯 이벤트
        eventBus.on('widget:*', this.handleWidgetEvent.bind(this));
        
        // 레이아웃 변경 이벤트
        eventBus.on('layout:change', this.handleLayoutChange.bind(this));
    }

    /**
     * 기본 위젯 타입 등록
     * @private
     */
    registerDefaultWidgetTypes() {
        this.registerWidgetType('chart', {
            name: '차트',
            icon: 'fas fa-chart-line',
            minSize: { width: 4, height: 3 },
            defaultSize: { width: 6, height: 4 },
            resizable: true,
            configurable: true,
            template: this.createChartWidgetTemplate.bind(this)
        });

        this.registerWidgetType('positions', {
            name: '포지션',
            icon: 'fas fa-list',
            minSize: { width: 3, height: 3 },
            defaultSize: { width: 4, height: 6 },
            resizable: true,
            configurable: true,
            template: this.createPositionsWidgetTemplate.bind(this)
        });

        this.registerWidgetType('balance', {
            name: '잔고',
            icon: 'fas fa-wallet',
            minSize: { width: 2, height: 2 },
            defaultSize: { width: 3, height: 2 },
            resizable: true,
            configurable: false,
            template: this.createBalanceWidgetTemplate.bind(this)
        });

        this.registerWidgetType('news', {
            name: '뉴스',
            icon: 'fas fa-newspaper',
            minSize: { width: 3, height: 3 },
            defaultSize: { width: 4, height: 5 },
            resizable: true,
            configurable: true,
            template: this.createNewsWidgetTemplate.bind(this)
        });

        this.registerWidgetType('watchlist', {
            name: '관심종목',
            icon: 'fas fa-eye',
            minSize: { width: 2, height: 3 },
            defaultSize: { width: 3, height: 4 },
            resizable: true,
            configurable: true,
            template: this.createWatchlistWidgetTemplate.bind(this)
        });
    }

    /**
     * 드래그 타입 등록
     * @private
     */
    registerDragTypes() {
        dragDropManager.registerDragType('widget', {
            canDrag: this.canDragWidget.bind(this),
            onDragStart: this.onWidgetDragStart.bind(this),
            onDrag: this.onWidgetDrag.bind(this),
            onDrop: this.onWidgetDrop.bind(this)
        });

        dragDropManager.registerDragType('widget-resize', {
            canDrag: this.canResizeWidget.bind(this),
            onDragStart: this.onResizeDragStart.bind(this),
            onDrag: this.onResizeDrag.bind(this),
            onDrop: this.onResizeDrop.bind(this)
        });
    }

    /**
     * 그리드 오버레이 생성
     * @private
     */
    createGridOverlay() {
        this.gridOverlay = document.createElement('div');
        this.gridOverlay.className = 'widget-grid-overlay';
        this.gridOverlay.style.cssText = `
            position: absolute;
            top: 0;
            left: 0;
            right: 0;
            bottom: 0;
            pointer-events: none;
            z-index: 1;
            opacity: 0;
            transition: opacity 0.3s ease;
        `;
        
        // 그리드 라인 생성
        this.updateGridLines();
    }

    /**
     * 그리드 라인 업데이트
     * @private
     */
    updateGridLines() {
        if (!this.gridOverlay) return;
        
        this.gridOverlay.innerHTML = '';
        
        const fragment = document.createDocumentFragment();
        
        // 수직선
        for (let i = 1; i < this.gridSize.cols; i++) {
            const line = document.createElement('div');
            line.className = 'grid-line vertical';
            line.style.cssText = `
                position: absolute;
                left: ${(i / this.gridSize.cols) * 100}%;
                top: 0;
                bottom: 0;
                width: 1px;
                background: rgba(255, 255, 255, 0.1);
            `;
            fragment.appendChild(line);
        }
        
        // 수평선
        for (let i = 1; i < this.gridSize.rows; i++) {
            const line = document.createElement('div');
            line.className = 'grid-line horizontal';
            line.style.cssText = `
                position: absolute;
                top: ${(i / this.gridSize.rows) * 100}%;
                left: 0;
                right: 0;
                height: 1px;
                background: rgba(255, 255, 255, 0.1);
            `;
            fragment.appendChild(line);
        }
        
        this.gridOverlay.appendChild(fragment);
    }

    /**
     * 위젯 컨테이너 등록
     * @param {HTMLElement|string} container - 컨테이너 요소 또는 ID
     * @param {Object} options - 옵션
     */
    registerContainer(container, options = {}) {
        const element = typeof container === 'string' 
            ? document.getElementById(container) 
            : container;
            
        if (!element) {
            throw new Error('Container element not found');
        }

        const containerData = {
            element,
            id: options.id || element.id || `container_${Date.now()}`,
            layout: options.layout || 'grid',
            widgets: new Set(),
            maxWidgets: options.maxWidgets || Infinity,
            allowedTypes: options.allowedTypes || ['*'],
            ...options
        };

        this.containers.set(element, containerData);
        
        // 컨테이너 스타일 설정
        this.setupContainer(element, containerData);
        
        // 드롭존으로 등록
        this.registerContainerAsDropZone(element, containerData);
        
        // 그리드 오버레이 추가
        if (this.gridOverlay && containerData.layout === 'grid') {
            element.appendChild(this.gridOverlay);
        }

        eventBus.emit('widget:container:registered', {
            containerId: containerData.id,
            container: element
        });
    }

    /**
     * 컨테이너 설정
     * @param {HTMLElement} element - 컨테이너 요소
     * @param {Object} containerData - 컨테이너 데이터
     * @private
     */
    setupContainer(element, containerData) {
        element.classList.add('widget-container');
        
        if (containerData.layout === 'grid') {
            element.style.cssText += `
                position: relative;
                display: grid;
                grid-template-columns: repeat(${this.gridSize.cols}, 1fr);
                grid-template-rows: repeat(${this.gridSize.rows}, minmax(${this.cellSize.height}px, 1fr));
                gap: 8px;
                padding: 16px;
            `;
        } else {
            element.style.cssText += `
                position: relative;
                display: flex;
                flex-direction: column;
                padding: 16px;
                gap: 16px;
            `;
        }
    }

    /**
     * 컨테이너를 드롭존으로 등록
     * @param {HTMLElement} element - 컨테이너 요소
     * @param {Object} containerData - 컨테이너 데이터
     * @private
     */
    registerContainerAsDropZone(element, containerData) {
        dragDropManager.registerDropZone(element, {
            accepts: ['widget'],
            sortable: true,
            onDragEnter: (event, dragData) => {
                element.classList.add('widget-drop-active');
            },
            onDragLeave: (event, dragData) => {
                element.classList.remove('widget-drop-active');
            },
            onDrop: (event, dragData, dropZone) => {
                this.handleWidgetDrop(event, dragData, dropZone, containerData);
            }
        });
    }

    /**
     * 위젯 타입 등록
     * @param {string} type - 위젯 타입
     * @param {Object} definition - 위젯 정의
     */
    registerWidgetType(type, definition) {
        this.widgetTypes.set(type, {
            name: definition.name,
            icon: definition.icon || 'fas fa-square',
            minSize: definition.minSize || this.config.minWidgetSize,
            maxSize: definition.maxSize || this.config.maxWidgetSize,
            defaultSize: definition.defaultSize || { width: 4, height: 3 },
            resizable: definition.resizable !== false,
            configurable: definition.configurable !== false,
            template: definition.template,
            onCreate: definition.onCreate,
            onDestroy: definition.onDestroy,
            onResize: definition.onResize,
            onMove: definition.onMove,
            onConfigure: definition.onConfigure
        });
    }

    /**
     * 위젯 생성
     * @param {string} type - 위젯 타입
     * @param {Object} options - 위젯 옵션
     * @param {HTMLElement} container - 대상 컨테이너
     * @returns {Object} 생성된 위젯
     */
    createWidget(type, options = {}, container = null) {
        const widgetType = this.widgetTypes.get(type);
        if (!widgetType) {
            throw new Error(`Unknown widget type: ${type}`);
        }

        const widgetId = options.id || `widget_${type}_${Date.now()}_${Math.random().toString(36).substr(2, 9)}`;
        
        // 위젯 요소 생성
        const element = document.createElement('div');
        element.className = 'dashboard-widget';
        element.setAttribute('data-widget-id', widgetId);
        element.setAttribute('data-widget-type', type);
        
        // 위젯 데이터 생성
        const widget = {
            id: widgetId,
            type,
            element,
            container: container,
            title: options.title || widgetType.name,
            position: options.position || { x: 0, y: 0 },
            size: options.size || widgetType.defaultSize,
            config: options.config || {},
            zIndex: options.zIndex || this.getNextZIndex(),
            locked: options.locked || false,
            minimized: options.minimized || false,
            visible: options.visible !== false,
            created: Date.now(),
            ...options
        };

        this.widgets.set(widgetId, widget);
        
        // 위젯 렌더링
        this.renderWidget(widget);
        
        // 드래그 가능하게 설정
        this.setupWidgetInteractions(widget);
        
        // 컨테이너에 추가
        if (container) {
            this.addWidgetToContainer(widget, container);
        }
        
        // 위젯 타입별 onCreate 콜백 실행
        if (widgetType.onCreate) {
            widgetType.onCreate(widget);
        }

        // 메트릭 업데이트
        this.metrics.widgetCount++;
        
        eventBus.emit('widget:created', {
            widgetId,
            widget,
            type
        });

        return widget;
    }

    /**
     * 위젯 렌더링
     * @param {Object} widget - 위젯
     * @private
     */
    renderWidget(widget) {
        const widgetType = this.widgetTypes.get(widget.type);
        
        // 기본 위젯 구조
        widget.element.innerHTML = `
            <div class="widget-header">
                <div class="widget-title">
                    <i class="${widgetType.icon}"></i>
                    <span class="title-text">${widget.title}</span>
                </div>
                <div class="widget-controls">
                    ${widgetType.configurable ? `
                        <button class="widget-btn config-btn" title="설정">
                            <i class="fas fa-cog"></i>
                        </button>
                    ` : ''}
                    <button class="widget-btn minimize-btn" title="최소화">
                        <i class="fas fa-minus"></i>
                    </button>
                    <button class="widget-btn close-btn" title="닫기">
                        <i class="fas fa-times"></i>
                    </button>
                </div>
            </div>
            <div class="widget-content">
                ${widgetType.template ? widgetType.template(widget) : '<div class="widget-placeholder">위젯 내용</div>'}
            </div>
            ${widgetType.resizable ? `
                <div class="widget-resize-handles">
                    <div class="resize-handle top-left"></div>
                    <div class="resize-handle top-right"></div>
                    <div class="resize-handle bottom-left"></div>
                    <div class="resize-handle bottom-right"></div>
                    <div class="resize-handle top"></div>
                    <div class="resize-handle bottom"></div>
                    <div class="resize-handle left"></div>
                    <div class="resize-handle right"></div>
                </div>
            ` : ''}
        `;

        // 위젯 스타일 적용
        this.applyWidgetStyles(widget);
        
        // 컨트롤 이벤트 바인딩
        this.bindWidgetControls(widget);
    }

    /**
     * 위젯 스타일 적용
     * @param {Object} widget - 위젯
     * @private
     */
    applyWidgetStyles(widget) {
        const container = this.containers.get(widget.container);
        
        if (container && container.layout === 'grid') {
            // 그리드 레이아웃
            widget.element.style.cssText = `
                grid-column: ${widget.position.x + 1} / span ${widget.size.width};
                grid-row: ${widget.position.y + 1} / span ${widget.size.height};
                position: relative;
                background: var(--widget-bg, #1a1a1a);
                border-radius: 8px;
                border: 1px solid var(--widget-border, #333);
                overflow: hidden;
                transition: all ${this.config.animationDuration}ms ease;
                z-index: ${widget.zIndex};
                ${widget.minimized ? 'height: 40px;' : ''}
                ${!widget.visible ? 'display: none;' : ''}
            `;
        } else {
            // 자유 레이아웃
            widget.element.style.cssText = `
                position: absolute;
                left: ${widget.position.x}px;
                top: ${widget.position.y}px;
                width: ${widget.size.width * this.cellSize.width}px;
                height: ${widget.size.height * this.cellSize.height}px;
                background: var(--widget-bg, #1a1a1a);
                border-radius: 8px;
                border: 1px solid var(--widget-border, #333);
                overflow: hidden;
                transition: all ${this.config.animationDuration}ms ease;
                z-index: ${widget.zIndex};
                ${widget.minimized ? 'height: 40px;' : ''}
                ${!widget.visible ? 'display: none;' : ''}
            `;
        }
    }

    /**
     * 위젯 인터랙션 설정
     * @param {Object} widget - 위젯
     * @private
     */
    setupWidgetInteractions(widget) {
        if (!widget.locked && this.config.enableMove) {
            // 헤더를 드래그 핸들로 설정
            const header = widget.element.querySelector('.widget-header');
            if (header) {
                dragDropManager.registerDragElement(widget.element, {
                    type: 'widget',
                    handle: header,
                    data: { widgetId: widget.id },
                    accessibleName: `${widget.title} 위젯`
                });
            }
        }

        if (!widget.locked && this.config.enableResize) {
            // 리사이즈 핸들 설정
            const resizeHandles = widget.element.querySelectorAll('.resize-handle');
            resizeHandles.forEach(handle => {
                dragDropManager.registerDragElement(handle, {
                    type: 'widget-resize',
                    data: { 
                        widgetId: widget.id,
                        direction: handle.className.split(' ')[1]
                    },
                    accessibleName: `${widget.title} 위젯 크기 조절`
                });
            });
        }
    }

    /**
     * 위젯 컨트롤 바인딩
     * @param {Object} widget - 위젯
     * @private
     */
    bindWidgetControls(widget) {
        const configBtn = widget.element.querySelector('.config-btn');
        const minimizeBtn = widget.element.querySelector('.minimize-btn');
        const closeBtn = widget.element.querySelector('.close-btn');

        if (configBtn) {
            configBtn.addEventListener('click', () => this.configureWidget(widget.id));
        }

        if (minimizeBtn) {
            minimizeBtn.addEventListener('click', () => this.toggleWidgetMinimize(widget.id));
        }

        if (closeBtn) {
            closeBtn.addEventListener('click', () => this.removeWidget(widget.id));
        }
    }

    /**
     * 위젯을 컨테이너에 추가
     * @param {Object} widget - 위젯
     * @param {HTMLElement} container - 컨테이너
     * @private
     */
    addWidgetToContainer(widget, container) {
        const containerData = this.containers.get(container);
        if (!containerData) {
            throw new Error('Container not registered');
        }

        // 위젯 수 제한 확인
        if (containerData.widgets.size >= containerData.maxWidgets) {
            throw new Error('Container widget limit reached');
        }

        // 위젯 타입 허용 확인
        const allowedTypes = containerData.allowedTypes;
        if (!allowedTypes.includes('*') && !allowedTypes.includes(widget.type)) {
            throw new Error(`Widget type ${widget.type} not allowed in this container`);
        }

        containerData.widgets.add(widget.id);
        widget.container = container;
        container.appendChild(widget.element);
        
        // 위치 충돌 해결
        this.resolvePositionCollision(widget, containerData);
    }

    /**
     * 위치 충돌 해결
     * @param {Object} widget - 위젯
     * @param {Object} containerData - 컨테이너 데이터
     * @private
     */
    resolvePositionCollision(widget, containerData) {
        if (containerData.layout !== 'grid') return;

        const occupiedPositions = this.getOccupiedPositions(containerData, widget.id);
        
        // 충돌 확인
        if (this.isPositionOccupied(widget.position, widget.size, occupiedPositions)) {
            // 빈 공간 찾기
            const newPosition = this.findAvailablePosition(widget.size, occupiedPositions);
            if (newPosition) {
                widget.position = newPosition;
                this.applyWidgetStyles(widget);
            }
        }
    }

    /**
     * 점유된 위치 가져오기
     * @param {Object} containerData - 컨테이너 데이터
     * @param {string} excludeWidgetId - 제외할 위젯 ID
     * @returns {Set} 점유된 위치 집합
     * @private
     */
    getOccupiedPositions(containerData, excludeWidgetId = null) {
        const occupied = new Set();
        
        containerData.widgets.forEach(widgetId => {
            if (widgetId === excludeWidgetId) return;
            
            const widget = this.widgets.get(widgetId);
            if (!widget || !widget.visible) return;
            
            for (let x = 0; x < widget.size.width; x++) {
                for (let y = 0; y < widget.size.height; y++) {
                    const pos = `${widget.position.x + x},${widget.position.y + y}`;
                    occupied.add(pos);
                }
            }
        });
        
        return occupied;
    }

    /**
     * 위치 점유 확인
     * @param {Object} position - 위치
     * @param {Object} size - 크기
     * @param {Set} occupiedPositions - 점유된 위치
     * @returns {boolean} 점유 여부
     * @private
     */
    isPositionOccupied(position, size, occupiedPositions) {
        for (let x = 0; x < size.width; x++) {
            for (let y = 0; y < size.height; y++) {
                const pos = `${position.x + x},${position.y + y}`;
                if (occupiedPositions.has(pos)) {
                    return true;
                }
            }
        }
        return false;
    }

    /**
     * 사용 가능한 위치 찾기
     * @param {Object} size - 위젯 크기
     * @param {Set} occupiedPositions - 점유된 위치
     * @returns {Object|null} 사용 가능한 위치
     * @private
     */
    findAvailablePosition(size, occupiedPositions) {
        for (let y = 0; y <= this.gridSize.rows - size.height; y++) {
            for (let x = 0; x <= this.gridSize.cols - size.width; x++) {
                const position = { x, y };
                if (!this.isPositionOccupied(position, size, occupiedPositions)) {
                    return position;
                }
            }
        }
        return null;
    }

    // 드래그 앤 드롭 핸들러들

    /**
     * 위젯 드래그 가능 여부 확인
     * @param {HTMLElement} element - 요소
     * @returns {boolean} 드래그 가능 여부
     * @private
     */
    canDragWidget(element) {
        const widgetId = element.dataset.widgetId;
        const widget = this.widgets.get(widgetId);
        return widget && !widget.locked && this.isEditMode;
    }

    /**
     * 위젯 드래그 시작
     * @param {HTMLElement} element - 요소
     * @param {Object} data - 드래그 데이터
     * @param {DragEvent} event - 이벤트
     * @private
     */
    onWidgetDragStart(element, data, event) {
        const widget = this.widgets.get(data.widgetId);
        if (!widget) return;

        this.state.isDragging = true;
        this.state.activeWidget = widget;

        // 시각적 피드백
        element.classList.add('widget-dragging');
        this.showGridOverlay(true);

        // 고스트 요소 생성
        this.createDragGhost(widget);

        eventBus.emit('widget:drag:start', { widget });
    }

    /**
     * 위젯 드래그 중
     * @param {HTMLElement} element - 요소
     * @param {Object} data - 드래그 데이터
     * @param {DragEvent} event - 이벤트
     * @private
     */
    onWidgetDrag(element, data, event) {
        if (!this.state.isDragging) return;

        // 그리드 스냅 계산
        if (this.config.snapToGrid) {
            const gridPosition = this.calculateGridPosition(event.clientX, event.clientY);
            this.updateDragGhost(gridPosition);
        }
    }

    /**
     * 위젯 드롭
     * @param {HTMLElement} element - 요소
     * @param {Object} data - 드래그 데이터
     * @param {HTMLElement} dropZone - 드롭존
     * @private
     */
    onWidgetDrop(element, data, dropZone) {
        const widget = this.widgets.get(data.widgetId);
        if (!widget) return;

        // 새 위치 계산
        const newPosition = this.calculateDropPosition(dropZone);
        
        if (newPosition) {
            this.moveWidget(widget.id, newPosition);
        }

        this.endWidgetDrag();
    }

    /**
     * 위젯 리사이즈 가능 여부 확인
     * @param {HTMLElement} element - 요소
     * @returns {boolean} 리사이즈 가능 여부
     * @private
     */
    canResizeWidget(element) {
        const widgetId = element.closest('.dashboard-widget')?.dataset.widgetId;
        const widget = this.widgets.get(widgetId);
        return widget && !widget.locked && this.isEditMode && this.widgetTypes.get(widget.type)?.resizable;
    }

    /**
     * 리사이즈 드래그 시작
     * @param {HTMLElement} element - 요소
     * @param {Object} data - 드래그 데이터
     * @param {DragEvent} event - 이벤트
     * @private
     */
    onResizeDragStart(element, data, event) {
        const widget = this.widgets.get(data.widgetId);
        if (!widget) return;

        this.state.isResizing = true;
        this.state.activeWidget = widget;
        this.state.resizeHandle = data.direction;

        // 시각적 피드백
        widget.element.classList.add('widget-resizing');
        this.showGridOverlay(true);

        eventBus.emit('widget:resize:start', { widget, direction: data.direction });
    }

    /**
     * 리사이즈 드래그 중
     * @param {HTMLElement} element - 요소
     * @param {Object} data - 드래그 데이터
     * @param {DragEvent} event - 이벤트
     * @private
     */
    onResizeDrag(element, data, event) {
        if (!this.state.isResizing) return;

        const widget = this.state.activeWidget;
        const newSize = this.calculateNewSize(widget, data.direction, event);
        
        if (newSize) {
            this.previewResize(widget, newSize);
        }
    }

    /**
     * 리사이즈 드롭
     * @param {HTMLElement} element - 요소
     * @param {Object} data - 드래그 데이터
     * @param {HTMLElement} dropZone - 드롭존
     * @private
     */
    onResizeDrop(element, data, dropZone) {
        const widget = this.widgets.get(data.widgetId);
        if (!widget) return;

        // 최종 크기 적용
        const finalSize = this.calculateFinalSize(widget, data.direction);
        if (finalSize) {
            this.resizeWidget(widget.id, finalSize);
        }

        this.endWidgetResize();
    }

    // 위젯 조작 메서드들

    /**
     * 위젯 이동
     * @param {string} widgetId - 위젯 ID
     * @param {Object} newPosition - 새 위치
     */
    moveWidget(widgetId, newPosition) {
        const widget = this.widgets.get(widgetId);
        if (!widget || widget.locked) return;

        const oldPosition = { ...widget.position };
        widget.position = newPosition;
        
        this.applyWidgetStyles(widget);
        this.metrics.moveOperations++;
        
        const widgetType = this.widgetTypes.get(widget.type);
        if (widgetType.onMove) {
            widgetType.onMove(widget, oldPosition, newPosition);
        }

        this.scheduleLayoutSave();
        
        eventBus.emit('widget:moved', {
            widgetId,
            widget,
            oldPosition,
            newPosition
        });
    }

    /**
     * 위젯 크기 조절
     * @param {string} widgetId - 위젯 ID
     * @param {Object} newSize - 새 크기
     */
    resizeWidget(widgetId, newSize) {
        const widget = this.widgets.get(widgetId);
        if (!widget || widget.locked) return;

        const widgetType = this.widgetTypes.get(widget.type);
        
        // 크기 제한 확인
        const minSize = widgetType.minSize;
        const maxSize = widgetType.maxSize;
        
        const constrainedSize = {
            width: Math.max(minSize.width, Math.min(maxSize.width, newSize.width)),
            height: Math.max(minSize.height, Math.min(maxSize.height, newSize.height))
        };

        const oldSize = { ...widget.size };
        widget.size = constrainedSize;
        
        this.applyWidgetStyles(widget);
        this.metrics.resizeOperations++;
        
        if (widgetType.onResize) {
            widgetType.onResize(widget, oldSize, constrainedSize);
        }

        this.scheduleLayoutSave();
        
        eventBus.emit('widget:resized', {
            widgetId,
            widget,
            oldSize,
            newSize: constrainedSize
        });
    }

    /**
     * 위젯 제거
     * @param {string} widgetId - 위젯 ID
     */
    removeWidget(widgetId) {
        const widget = this.widgets.get(widgetId);
        if (!widget) return;

        const widgetType = this.widgetTypes.get(widget.type);
        
        // onDestroy 콜백 실행
        if (widgetType.onDestroy) {
            widgetType.onDestroy(widget);
        }

        // 컨테이너에서 제거
        if (widget.container) {
            const containerData = this.containers.get(widget.container);
            if (containerData) {
                containerData.widgets.delete(widgetId);
            }
        }

        // DOM에서 제거
        if (widget.element && widget.element.parentNode) {
            widget.element.parentNode.removeChild(widget.element);
        }

        // 드래그 등록 해제
        dragDropManager.unregisterElement(widget.element);

        this.widgets.delete(widgetId);
        this.metrics.widgetCount--;
        
        this.scheduleLayoutSave();
        
        eventBus.emit('widget:removed', {
            widgetId,
            widget
        });
    }

    /**
     * 위젯 최소화 토글
     * @param {string} widgetId - 위젯 ID
     */
    toggleWidgetMinimize(widgetId) {
        const widget = this.widgets.get(widgetId);
        if (!widget) return;

        widget.minimized = !widget.minimized;
        
        const content = widget.element.querySelector('.widget-content');
        const minimizeBtn = widget.element.querySelector('.minimize-btn i');
        
        if (widget.minimized) {
            content.style.display = 'none';
            minimizeBtn.className = 'fas fa-plus';
            widget.element.classList.add('minimized');
        } else {
            content.style.display = '';
            minimizeBtn.className = 'fas fa-minus';
            widget.element.classList.remove('minimized');
        }
        
        this.applyWidgetStyles(widget);
        
        eventBus.emit('widget:minimized', {
            widgetId,
            widget,
            minimized: widget.minimized
        });
    }

    /**
     * 위젯 설정
     * @param {string} widgetId - 위젯 ID
     */
    configureWidget(widgetId) {
        const widget = this.widgets.get(widgetId);
        if (!widget) return;

        const widgetType = this.widgetTypes.get(widget.type);
        
        if (widgetType.onConfigure) {
            widgetType.onConfigure(widget);
        } else {
            // 기본 설정 모달 표시
            this.showWidgetConfigModal(widget);
        }
        
        eventBus.emit('widget:configure', {
            widgetId,
            widget
        });
    }

    // 템플릿 메서드들 (서브클래스에서 오버라이드 가능)

    /**
     * 차트 위젯 템플릿 생성
     * @param {Object} widget - 위젯
     * @returns {string} HTML 템플릿
     * @private
     */
    createChartWidgetTemplate(widget) {
        return `
            <div class="chart-container">
                <canvas class="chart-canvas" data-chart-type="${widget.config.chartType || 'line'}"></canvas>
            </div>
        `;
    }

    /**
     * 포지션 위젯 템플릿 생성
     * @param {Object} widget - 위젯
     * @returns {string} HTML 템플릿
     * @private
     */
    createPositionsWidgetTemplate(widget) {
        return `
            <div class="positions-container">
                <div class="positions-header">
                    <div class="positions-stats">
                        <span class="stat-item">
                            <i class="fas fa-chart-line"></i>
                            <span class="stat-value">0</span>
                            <span class="stat-label">포지션</span>
                        </span>
                    </div>
                </div>
                <div class="positions-list" id="positions-${widget.id}">
                    <!-- 포지션 카드들이 여기에 추가됨 -->
                </div>
            </div>
        `;
    }

    /**
     * 잔고 위젯 템플릿 생성
     * @param {Object} widget - 위젯
     * @returns {string} HTML 템플릿
     * @private
     */
    createBalanceWidgetTemplate(widget) {
        return `
            <div class="balance-container">
                <div class="balance-main">
                    <div class="balance-amount">$0.00</div>
                    <div class="balance-change">+$0.00 (+0.00%)</div>
                </div>
                <div class="balance-breakdown">
                    <div class="balance-item">
                        <span class="label">사용 가능:</span>
                        <span class="value">$0.00</span>
                    </div>
                    <div class="balance-item">
                        <span class="label">마진:</span>
                        <span class="value">$0.00</span>
                    </div>
                </div>
            </div>
        `;
    }

    /**
     * 뉴스 위젯 템플릿 생성
     * @param {Object} widget - 위젯
     * @returns {string} HTML 템플릿
     * @private
     */
    createNewsWidgetTemplate(widget) {
        return `
            <div class="news-container">
                <div class="news-filters">
                    <select class="news-source-filter">
                        <option value="all">모든 소스</option>
                        <option value="coindesk">CoinDesk</option>
                        <option value="cointelegraph">Cointelegraph</option>
                    </select>
                </div>
                <div class="news-list">
                    <!-- 뉴스 항목들이 여기에 추가됨 -->
                </div>
            </div>
        `;
    }

    /**
     * 관심종목 위젯 템플릿 생성
     * @param {Object} widget - 위젯
     * @returns {string} HTML 템플릿
     * @private
     */
    createWatchlistWidgetTemplate(widget) {
        return `
            <div class="watchlist-container">
                <div class="watchlist-header">
                    <input type="text" class="symbol-input" placeholder="심볼 추가...">
                    <button class="add-symbol-btn">
                        <i class="fas fa-plus"></i>
                    </button>
                </div>
                <div class="watchlist-items">
                    <!-- 관심종목 항목들이 여기에 추가됨 -->
                </div>
            </div>
        `;
    }

    // 유틸리티 메서드들

    /**
     * 다음 z-index 가져오기
     * @returns {number} 다음 z-index 값
     * @private
     */
    getNextZIndex() {
        let maxZ = 1000;
        this.widgets.forEach(widget => {
            if (widget.zIndex > maxZ) {
                maxZ = widget.zIndex;
            }
        });
        return maxZ + 1;
    }

    /**
     * 그리드 오버레이 표시/숨김
     * @param {boolean} show - 표시 여부
     * @private
     */
    showGridOverlay(show) {
        if (this.gridOverlay) {
            this.gridOverlay.style.opacity = show ? '1' : '0';
        }
    }

    /**
     * 레이아웃 저장 스케줄링
     * @private
     */
    scheduleLayoutSave() {
        if (this.saveDebouncer) {
            clearTimeout(this.saveDebouncer);
        }
        
        this.saveDebouncer = setTimeout(() => {
            this.saveCurrentLayout();
            this.metrics.layoutChanges++;
        }, this.config.saveInterval);
    }

    /**
     * 현재 레이아웃 저장
     * @private
     */
    saveCurrentLayout() {
        const layout = this.serializeLayout();
        localStorage.setItem(`widget-layout-${this.currentLayout}`, JSON.stringify(layout));
        
        eventBus.emit('widget:layout:saved', {
            layoutName: this.currentLayout,
            layout
        });
    }

    /**
     * 레이아웃 직렬화
     * @returns {Object} 직렬화된 레이아웃
     * @private
     */
    serializeLayout() {
        const layout = {
            name: this.currentLayout,
            timestamp: Date.now(),
            gridSize: this.gridSize,
            widgets: []
        };

        this.widgets.forEach(widget => {
            layout.widgets.push({
                id: widget.id,
                type: widget.type,
                title: widget.title,
                position: widget.position,
                size: widget.size,
                config: widget.config,
                zIndex: widget.zIndex,
                minimized: widget.minimized,
                visible: widget.visible,
                locked: widget.locked
            });
        });

        return layout;
    }

    /**
     * 레이아웃 로드
     * @private
     */
    loadLayouts() {
        try {
            const savedLayout = localStorage.getItem(`widget-layout-${this.currentLayout}`);
            if (savedLayout) {
                const layout = JSON.parse(savedLayout);
                this.deserializeLayout(layout);
            }
        } catch (error) {
            console.warn('레이아웃 로드 실패:', error);
        }
    }

    /**
     * 레이아웃 역직렬화
     * @param {Object} layout - 레이아웃 데이터
     * @private
     */
    deserializeLayout(layout) {
        // 기존 위젯 제거
        this.widgets.forEach((widget, widgetId) => {
            this.removeWidget(widgetId);
        });

        // 위젯 복원
        layout.widgets.forEach(widgetData => {
            try {
                this.createWidget(widgetData.type, widgetData);
            } catch (error) {
                console.warn(`위젯 복원 실패 (${widgetData.id}):`, error);
            }
        });
    }

    /**
     * 편집 모드 설정
     * @param {boolean} enabled - 편집 모드 여부
     */
    setEditMode(enabled) {
        this.isEditMode = enabled;
        
        document.body.classList.toggle('widget-edit-mode', enabled);
        this.showGridOverlay(enabled && this.config.showGridLines);
        
        // 위젯 편집 상태 업데이트
        this.widgets.forEach(widget => {
            widget.element.classList.toggle('editable', enabled && !widget.locked);
        });
        
        eventBus.emit('widget:edit-mode:changed', {
            enabled,
            widgetCount: this.widgets.size
        });
    }

    /**
     * 레이아웃 설정
     * @param {string} layoutName - 레이아웃 이름
     */
    setLayout(layoutName) {
        this.saveCurrentLayout(); // 현재 레이아웃 저장
        this.currentLayout = layoutName;
        this.loadLayouts(); // 새 레이아웃 로드
        
        eventBus.emit('widget:layout:changed', {
            layoutName,
            widgetCount: this.widgets.size
        });
    }

    /**
     * 메트릭 가져오기
     * @returns {Object} 성능 메트릭
     */
    getMetrics() {
        return {
            ...this.metrics,
            totalContainers: this.containers.size,
            totalWidgetTypes: this.widgetTypes.size,
            isEditMode: this.isEditMode,
            currentLayout: this.currentLayout
        };
    }

    /**
     * 정리
     */
    destroy() {
        // 모든 위젯 제거
        this.widgets.forEach((widget, widgetId) => {
            this.removeWidget(widgetId);
        });

        // 컨테이너 정리
        this.containers.forEach((containerData, container) => {
            dragDropManager.unregisterElement(container);
        });

        // 이벤트 리스너 제거
        window.removeEventListener('resize', this.handleWindowResize);
        document.removeEventListener('keydown', this.handleKeyDown);
        document.removeEventListener('keyup', this.handleKeyUp);

        // 그리드 오버레이 제거
        if (this.gridOverlay && this.gridOverlay.parentNode) {
            this.gridOverlay.parentNode.removeChild(this.gridOverlay);
        }

        // 디바운서 정리
        if (this.saveDebouncer) {
            clearTimeout(this.saveDebouncer);
        }

        // 맵 정리
        this.widgets.clear();
        this.containers.clear();
        this.layouts.clear();
        this.widgetTypes.clear();
    }

    // 빈 핸들러들 (필요시 구현)
    handleWindowResize() {
        this.updateGridLines();
    }
    
    handleKeyDown(event) {
        if (event.key === 'Escape' && this.isEditMode) {
            this.setEditMode(false);
        }
    }
    
    handleKeyUp(event) {}
    handleWidgetEvent(eventData) {}
    handleLayoutChange(eventData) {}
    handleWidgetDrop(event, dragData, dropZone, containerData) {}
    
    createDragGhost(widget) {}
    updateDragGhost(position) {}
    endWidgetDrag() {
        this.state.isDragging = false;
        this.state.activeWidget = null;
        this.showGridOverlay(false);
        
        // 드래그 중 클래스 제거
        this.widgets.forEach(widget => {
            widget.element.classList.remove('widget-dragging');
        });
    }
    
    calculateGridPosition(clientX, clientY) {
        return { x: 0, y: 0 };
    }
    
    calculateDropPosition(dropZone) {
        return { x: 0, y: 0 };
    }
    
    endWidgetResize() {
        this.state.isResizing = false;
        this.state.activeWidget = null;
        this.state.resizeHandle = null;
        this.showGridOverlay(false);
        
        // 리사이즈 중 클래스 제거
        this.widgets.forEach(widget => {
            widget.element.classList.remove('widget-resizing');
        });
    }
    
    calculateNewSize(widget, direction, event) {
        return null;
    }
    
    previewResize(widget, newSize) {}
    calculateFinalSize(widget, direction) {
        return null;
    }
    
    showWidgetConfigModal(widget) {}
}

// 전역 위젯 매니저 인스턴스
export const widgetManager = new WidgetManager();

// 편의 함수들
export const createWidget = (type, options, container) => 
    widgetManager.createWidget(type, options, container);

export const registerContainer = (container, options) => 
    widgetManager.registerContainer(container, options);

export const registerWidgetType = (type, definition) => 
    widgetManager.registerWidgetType(type, definition);

// 개발 모드에서 전역 접근 가능
if (typeof window !== 'undefined' && process.env.NODE_ENV === 'development') {
    window.__TRADING_DASHBOARD_WIDGETS__ = widgetManager;
}
import { BaseComponent } from '../core/BaseComponent.js';

/**
 * 차트 인터랙션 매니저
 * - 줌/팬 기능
 * - 툴팁 개선
 * - 크로스헤어 커서
 * - 차트 간 동기화
 * - 드로잉 도구
 */
export class ChartInteractionManager extends BaseComponent {
    constructor(chartInstances = [], options = {}) {
        super(null, options);
        
        // 차트 인스턴스들
        this.charts = new Map();
        this.masterChart = null; // 동기화 마스터 차트
        
        // 인터랙션 상태
        this.isEnabled = options.enabled !== false;
        this.syncEnabled = options.syncEnabled !== false;
        this.zoomEnabled = options.zoomEnabled !== false;
        this.panEnabled = options.panEnabled !== false;
        this.crosshairEnabled = options.crosshairEnabled !== false;
        
        // 줌/팬 설정
        this.zoomSensitivity = options.zoomSensitivity || 0.1;
        this.panSensitivity = options.panSensitivity || 1;
        this.maxZoom = options.maxZoom || 10;
        this.minZoom = options.minZoom || 0.1;
        
        // 인터랙션 상태
        this.currentZoom = 1;
        this.panOffset = { x: 0, y: 0 };
        this.isDragging = false;
        this.lastMousePos = { x: 0, y: 0 };
        this.crosshairPos = null;
        
        // 드로잉 도구
        this.drawingTools = new Map();
        this.activeDrawingTool = null;
        this.drawnObjects = [];
        
        // 툴팁 관리
        this.tooltipManager = null;
        this.activeTooltip = null;
        
        // 차트 추가
        chartInstances.forEach(chart => this.addChart(chart));
        
        this.init();
    }

    /**
     * 초기화
     */
    init() {
        this.setupDrawingTools();
        this.setupTooltipManager();
        this.setupEventListeners();
        this.emit('interactionManagerInitialized');
    }

    /**
     * 차트 추가
     */
    addChart(chart, chartId = null) {
        const id = chartId || `chart_${this.charts.size}`;
        
        this.charts.set(id, {
            instance: chart,
            canvas: chart.canvas || chart.chart?.canvas,
            enabled: true,
            zoomLevel: 1,
            panOffset: { x: 0, y: 0 }
        });
        
        // 첫 번째 차트를 마스터로 설정
        if (!this.masterChart) {
            this.masterChart = id;
        }
        
        this.setupChartEventListeners(id);
        this.emit('chartAdded', { id, chart });
        
        return id;
    }

    /**
     * 차트 제거
     */
    removeChart(chartId) {
        if (this.charts.has(chartId)) {
            this.removeChartEventListeners(chartId);
            this.charts.delete(chartId);
            
            // 마스터 차트가 제거된 경우 새로운 마스터 설정
            if (this.masterChart === chartId && this.charts.size > 0) {
                this.masterChart = this.charts.keys().next().value;
            }
            
            this.emit('chartRemoved', chartId);
        }
    }

    /**
     * 차트별 이벤트 리스너 설정
     */
    setupChartEventListeners(chartId) {
        const chartData = this.charts.get(chartId);
        if (!chartData || !chartData.canvas) return;
        
        const canvas = chartData.canvas;
        const eventHandlers = {
            wheel: (e) => this.handleWheel(e, chartId),
            mousedown: (e) => this.handleMouseDown(e, chartId),
            mousemove: (e) => this.handleMouseMove(e, chartId),
            mouseup: (e) => this.handleMouseUp(e, chartId),
            mouseleave: (e) => this.handleMouseLeave(e, chartId),
            click: (e) => this.handleClick(e, chartId),
            dblclick: (e) => this.handleDoubleClick(e, chartId)
        };
        
        // 이벤트 리스너 등록
        Object.entries(eventHandlers).forEach(([event, handler]) => {
            canvas.addEventListener(event, handler);
        });
        
        // 터치 이벤트 (모바일)
        if ('ontouchstart' in window) {
            canvas.addEventListener('touchstart', (e) => this.handleTouchStart(e, chartId));
            canvas.addEventListener('touchmove', (e) => this.handleTouchMove(e, chartId));
            canvas.addEventListener('touchend', (e) => this.handleTouchEnd(e, chartId));
        }
        
        // 핸들러 참조 저장 (나중에 제거하기 위해)
        chartData.eventHandlers = eventHandlers;
    }

    /**
     * 차트 이벤트 리스너 제거
     */
    removeChartEventListeners(chartId) {
        const chartData = this.charts.get(chartId);
        if (!chartData || !chartData.canvas || !chartData.eventHandlers) return;
        
        const canvas = chartData.canvas;
        Object.entries(chartData.eventHandlers).forEach(([event, handler]) => {
            canvas.removeEventListener(event, handler);
        });
        
        delete chartData.eventHandlers;
    }

    /**
     * 전역 이벤트 리스너 설정
     */
    setupEventListeners() {
        // 키보드 단축키
        document.addEventListener('keydown', (e) => this.handleKeyDown(e));
        document.addEventListener('keyup', (e) => this.handleKeyUp(e));
        
        // 윈도우 리사이즈
        window.addEventListener('resize', () => this.handleWindowResize());
    }

    /**
     * 휠 이벤트 핸들러 (줌)
     */
    handleWheel(e, chartId) {
        if (!this.zoomEnabled || !this.isEnabled) return;
        
        e.preventDefault();
        
        const delta = e.deltaY > 0 ? -this.zoomSensitivity : this.zoomSensitivity;
        const newZoom = Math.max(this.minZoom, Math.min(this.maxZoom, this.currentZoom * (1 + delta)));
        
        if (newZoom !== this.currentZoom) {
            this.setZoom(newZoom, chartId, { x: e.offsetX, y: e.offsetY });
        }
    }

    /**
     * 마우스 다운 핸들러
     */
    handleMouseDown(e, chartId) {
        if (!this.isEnabled) return;
        
        this.isDragging = true;
        this.lastMousePos = { x: e.offsetX, y: e.offsetY };
        
        // 드로잉 도구가 활성화된 경우
        if (this.activeDrawingTool) {
            this.startDrawing(e, chartId);
        }
        
        this.emit('mouseDown', { chartId, event: e });
    }

    /**
     * 마우스 이동 핸들러
     */
    handleMouseMove(e, chartId) {
        if (!this.isEnabled) return;
        
        const currentPos = { x: e.offsetX, y: e.offsetY };
        
        // 패닝 처리
        if (this.isDragging && this.panEnabled && !this.activeDrawingTool) {
            const deltaX = currentPos.x - this.lastMousePos.x;
            const deltaY = currentPos.y - this.lastMousePos.y;
            
            this.pan(deltaX * this.panSensitivity, deltaY * this.panSensitivity, chartId);
        }
        
        // 크로스헤어 업데이트
        if (this.crosshairEnabled) {
            this.updateCrosshair(currentPos, chartId);
        }
        
        // 드로잉 처리
        if (this.activeDrawingTool && this.isDragging) {
            this.updateDrawing(e, chartId);
        }
        
        // 툴팁 업데이트
        this.updateTooltip(e, chartId);
        
        this.lastMousePos = currentPos;
        this.emit('mouseMove', { chartId, event: e, position: currentPos });
    }

    /**
     * 마우스 업 핸들러
     */
    handleMouseUp(e, chartId) {
        if (!this.isEnabled) return;
        
        this.isDragging = false;
        
        // 드로잉 완료
        if (this.activeDrawingTool) {
            this.finishDrawing(e, chartId);
        }
        
        this.emit('mouseUp', { chartId, event: e });
    }

    /**
     * 마우스 떠남 핸들러
     */
    handleMouseLeave(e, chartId) {
        this.isDragging = false;
        this.crosshairPos = null;
        this.hideTooltip();
        this.emit('mouseLeave', { chartId, event: e });
    }

    /**
     * 클릭 핸들러
     */
    handleClick(e, chartId) {
        if (!this.isEnabled) return;
        
        this.emit('chartClick', { chartId, event: e, position: { x: e.offsetX, y: e.offsetY } });
    }

    /**
     * 더블클릭 핸들러
     */
    handleDoubleClick(e, chartId) {
        if (!this.isEnabled) return;
        
        // 줌 리셋
        this.resetZoom(chartId);
        this.emit('chartDoubleClick', { chartId, event: e });
    }

    /**
     * 터치 이벤트 핸들러들
     */
    handleTouchStart(e, chartId) {
        e.preventDefault();
        if (e.touches.length === 1) {
            // 단일 터치 - 패닝 시작
            const touch = e.touches[0];
            const rect = e.target.getBoundingClientRect();
            this.handleMouseDown({
                offsetX: touch.clientX - rect.left,
                offsetY: touch.clientY - rect.top
            }, chartId);
        } else if (e.touches.length === 2) {
            // 멀티 터치 - 줌 시작
            this.startPinchZoom(e, chartId);
        }
    }

    handleTouchMove(e, chartId) {
        e.preventDefault();
        if (e.touches.length === 1) {
            // 단일 터치 - 패닝
            const touch = e.touches[0];
            const rect = e.target.getBoundingClientRect();
            this.handleMouseMove({
                offsetX: touch.clientX - rect.left,
                offsetY: touch.clientY - rect.top
            }, chartId);
        } else if (e.touches.length === 2) {
            // 멀티 터치 - 줌
            this.updatePinchZoom(e, chartId);
        }
    }

    handleTouchEnd(e, chartId) {
        this.handleMouseUp(e, chartId);
        this.pinchZoomData = null;
    }

    /**
     * 핀치 줌 시작
     */
    startPinchZoom(e, chartId) {
        const touch1 = e.touches[0];
        const touch2 = e.touches[1];
        
        this.pinchZoomData = {
            initialDistance: Math.hypot(
                touch2.clientX - touch1.clientX,
                touch2.clientY - touch1.clientY
            ),
            initialZoom: this.currentZoom,
            centerX: (touch1.clientX + touch2.clientX) / 2,
            centerY: (touch1.clientY + touch2.clientY) / 2
        };
    }

    /**
     * 핀치 줌 업데이트
     */
    updatePinchZoom(e, chartId) {
        if (!this.pinchZoomData) return;
        
        const touch1 = e.touches[0];
        const touch2 = e.touches[1];
        const currentDistance = Math.hypot(
            touch2.clientX - touch1.clientX,
            touch2.clientY - touch1.clientY
        );
        
        const scale = currentDistance / this.pinchZoomData.initialDistance;
        const newZoom = Math.max(this.minZoom, Math.min(this.maxZoom, 
            this.pinchZoomData.initialZoom * scale));
        
        this.setZoom(newZoom, chartId, {
            x: this.pinchZoomData.centerX,
            y: this.pinchZoomData.centerY
        });
    }

    /**
     * 키보드 이벤트 핸들러
     */
    handleKeyDown(e) {
        if (!this.isEnabled) return;
        
        switch(e.key) {
            case 'Escape':
                this.cancelDrawing();
                break;
            case 'Delete':
                this.deleteSelectedObjects();
                break;
            case 'z':
                if (e.ctrlKey) {
                    this.undo();
                }
                break;
            case 'y':
                if (e.ctrlKey) {
                    this.redo();
                }
                break;
        }
        
        this.emit('keyDown', e);
    }

    handleKeyUp(e) {
        this.emit('keyUp', e);
    }

    /**
     * 윈도우 리사이즈 핸들러
     */
    handleWindowResize() {
        // 모든 차트에 리사이즈 이벤트 전파
        this.charts.forEach((chartData, chartId) => {
            if (chartData.instance.resize) {
                chartData.instance.resize();
            }
        });
        
        this.emit('windowResize');
    }

    /**
     * 줌 설정
     */
    setZoom(zoom, chartId = null, center = null) {
        const targetCharts = chartId ? [chartId] : Array.from(this.charts.keys());
        
        targetCharts.forEach(id => {
            const chartData = this.charts.get(id);
            if (!chartData || !chartData.enabled) return;
            
            chartData.zoomLevel = zoom;
            
            // 차트별 줌 적용 로직
            this.applyZoomToChart(id, zoom, center);
        });
        
        this.currentZoom = zoom;
        
        // 동기화된 차트들에 줌 전파
        if (this.syncEnabled && chartId) {
            this.syncZoom(chartId, zoom, center);
        }
        
        this.emit('zoomChanged', { zoom, chartId, center });
    }

    /**
     * 차트에 줌 적용
     */
    applyZoomToChart(chartId, zoom, center) {
        const chartData = this.charts.get(chartId);
        if (!chartData) return;
        
        // Chart.js의 경우
        if (chartData.instance.chart) {
            const chart = chartData.instance.chart;
            
            // 줌 플러그인 사용 가능한 경우
            if (chart.zoom) {
                chart.zoom(zoom);
            }
        }
        
        // 커스텀 차트의 경우
        if (chartData.instance.setZoom) {
            chartData.instance.setZoom(zoom, center);
        }
    }

    /**
     * 패닝
     */
    pan(deltaX, deltaY, chartId = null) {
        const targetCharts = chartId ? [chartId] : Array.from(this.charts.keys());
        
        targetCharts.forEach(id => {
            const chartData = this.charts.get(id);
            if (!chartData || !chartData.enabled) return;
            
            chartData.panOffset.x += deltaX;
            chartData.panOffset.y += deltaY;
            
            this.applyPanToChart(id, chartData.panOffset);
        });
        
        // 동기화된 차트들에 패닝 전파
        if (this.syncEnabled && chartId) {
            this.syncPan(chartId, deltaX, deltaY);
        }
        
        this.emit('panChanged', { deltaX, deltaY, chartId });
    }

    /**
     * 차트에 패닝 적용
     */
    applyPanToChart(chartId, panOffset) {
        const chartData = this.charts.get(chartId);
        if (!chartData) return;
        
        // 커스텀 차트의 경우
        if (chartData.instance.setPan) {
            chartData.instance.setPan(panOffset);
        }
    }

    /**
     * 줌 리셋
     */
    resetZoom(chartId = null) {
        this.setZoom(1, chartId);
        this.resetPan(chartId);
    }

    /**
     * 패닝 리셋
     */
    resetPan(chartId = null) {
        const targetCharts = chartId ? [chartId] : Array.from(this.charts.keys());
        
        targetCharts.forEach(id => {
            const chartData = this.charts.get(id);
            if (chartData) {
                chartData.panOffset = { x: 0, y: 0 };
                this.applyPanToChart(id, chartData.panOffset);
            }
        });
        
        this.emit('panReset', chartId);
    }

    /**
     * 크로스헤어 업데이트
     */
    updateCrosshair(position, chartId) {
        this.crosshairPos = position;
        
        // 모든 차트에 크로스헤어 위치 동기화
        if (this.syncEnabled) {
            this.syncCrosshair(chartId, position);
        }
        
        this.emit('crosshairUpdated', { position, chartId });
    }

    /**
     * 드로잉 도구 설정
     */
    setupDrawingTools() {
        this.drawingTools.set('line', {
            name: '직선',
            cursor: 'crosshair',
            start: null,
            current: null
        });
        
        this.drawingTools.set('rectangle', {
            name: '사각형',
            cursor: 'crosshair',
            start: null,
            current: null
        });
        
        this.drawingTools.set('circle', {
            name: '원',
            cursor: 'crosshair',
            start: null,
            current: null
        });
        
        this.drawingTools.set('arrow', {
            name: '화살표',
            cursor: 'crosshair',
            start: null,
            current: null
        });
        
        this.drawingTools.set('text', {
            name: '텍스트',
            cursor: 'text',
            position: null,
            text: ''
        });
    }

    /**
     * 드로잉 도구 활성화
     */
    setActiveDrawingTool(toolName) {
        if (this.drawingTools.has(toolName)) {
            this.activeDrawingTool = toolName;
            this.updateCursor();
            this.emit('drawingToolChanged', toolName);
        }
    }

    /**
     * 드로잉 시작
     */
    startDrawing(e, chartId) {
        const tool = this.drawingTools.get(this.activeDrawingTool);
        if (!tool) return;
        
        const position = { x: e.offsetX, y: e.offsetY };
        tool.start = position;
        tool.current = position;
        
        this.emit('drawingStarted', { tool: this.activeDrawingTool, position, chartId });
    }

    /**
     * 드로잉 업데이트
     */
    updateDrawing(e, chartId) {
        const tool = this.drawingTools.get(this.activeDrawingTool);
        if (!tool || !tool.start) return;
        
        tool.current = { x: e.offsetX, y: e.offsetY };
        this.renderDrawingPreview(tool, chartId);
        
        this.emit('drawingUpdated', { tool: this.activeDrawingTool, chartId });
    }

    /**
     * 드로잉 완료
     */
    finishDrawing(e, chartId) {
        const tool = this.drawingTools.get(this.activeDrawingTool);
        if (!tool || !tool.start) return;
        
        const drawingObject = {
            id: `drawing_${Date.now()}`,
            type: this.activeDrawingTool,
            start: tool.start,
            end: tool.current,
            chartId,
            timestamp: Date.now(),
            style: this.getDrawingStyle()
        };
        
        this.drawnObjects.push(drawingObject);
        this.renderDrawingObject(drawingObject);
        
        // 도구 리셋
        tool.start = null;
        tool.current = null;
        
        this.emit('drawingCompleted', { object: drawingObject, chartId });
    }

    /**
     * 드로잉 취소
     */
    cancelDrawing() {
        if (this.activeDrawingTool) {
            const tool = this.drawingTools.get(this.activeDrawingTool);
            if (tool) {
                tool.start = null;
                tool.current = null;
            }
        }
        
        this.emit('drawingCancelled');
    }

    /**
     * 드로잉 스타일 가져오기
     */
    getDrawingStyle() {
        return {
            strokeColor: '#3b82f6',
            strokeWidth: 2,
            fillColor: 'rgba(59, 130, 246, 0.1)',
            fontSize: 14,
            fontColor: '#374151'
        };
    }

    /**
     * 드로잉 미리보기 렌더링
     */
    renderDrawingPreview(tool, chartId) {
        // 구체적인 렌더링 로직은 차트 타입에 따라 구현
        this.emit('renderDrawingPreview', { tool, chartId });
    }

    /**
     * 드로잉 오브젝트 렌더링
     */
    renderDrawingObject(obj) {
        this.emit('renderDrawingObject', obj);
    }

    /**
     * 툴팁 매니저 설정
     */
    setupTooltipManager() {
        this.tooltipManager = {
            element: null,
            visible: false,
            timeout: null,
            delay: 500
        };
    }

    /**
     * 툴팁 업데이트
     */
    updateTooltip(e, chartId) {
        if (!this.tooltipManager) return;
        
        clearTimeout(this.tooltipManager.timeout);
        
        this.tooltipManager.timeout = setTimeout(() => {
            this.showTooltip(e, chartId);
        }, this.tooltipManager.delay);
    }

    /**
     * 툴팁 표시
     */
    showTooltip(e, chartId) {
        const tooltipData = this.getTooltipData(e, chartId);
        if (!tooltipData) return;
        
        const tooltip = this.getOrCreateTooltipElement();
        tooltip.innerHTML = this.formatTooltipContent(tooltipData);
        tooltip.style.left = e.pageX + 10 + 'px';
        tooltip.style.top = e.pageY - 10 + 'px';
        tooltip.style.display = 'block';
        
        this.tooltipManager.visible = true;
        this.activeTooltip = tooltipData;
        
        this.emit('tooltipShown', { data: tooltipData, chartId });
    }

    /**
     * 툴팁 숨기기
     */
    hideTooltip() {
        if (this.tooltipManager && this.tooltipManager.element) {
            this.tooltipManager.element.style.display = 'none';
            this.tooltipManager.visible = false;
            this.activeTooltip = null;
        }
        
        clearTimeout(this.tooltipManager.timeout);
        this.emit('tooltipHidden');
    }

    /**
     * 툴팁 엘리먼트 가져오기/생성
     */
    getOrCreateTooltipElement() {
        if (!this.tooltipManager.element) {
            const tooltip = document.createElement('div');
            tooltip.id = 'chart-interaction-tooltip';
            tooltip.className = 'chart-tooltip enhanced';
            tooltip.style.cssText = `
                position: absolute;
                background: rgba(0, 0, 0, 0.9);
                color: white;
                padding: 12px;
                border-radius: 8px;
                font-size: 12px;
                font-family: Inter, sans-serif;
                box-shadow: 0 4px 12px rgba(0, 0, 0, 0.3);
                pointer-events: none;
                z-index: 10000;
                display: none;
                max-width: 300px;
                line-height: 1.4;
            `;
            
            document.body.appendChild(tooltip);
            this.tooltipManager.element = tooltip;
        }
        
        return this.tooltipManager.element;
    }

    /**
     * 툴팁 데이터 가져오기
     */
    getTooltipData(e, chartId) {
        const chartData = this.charts.get(chartId);
        if (!chartData) return null;
        
        // 차트 타입별 툴팁 데이터 수집
        if (chartData.instance.getTooltipData) {
            return chartData.instance.getTooltipData(e.offsetX, e.offsetY);
        }
        
        return null;
    }

    /**
     * 툴팁 콘텐츠 포맷
     */
    formatTooltipContent(data) {
        if (!data) return '';
        
        let content = '';
        
        if (data.title) {
            content += `<div class="tooltip-title">${data.title}</div>`;
        }
        
        if (data.items && Array.isArray(data.items)) {
            content += '<div class="tooltip-items">';
            data.items.forEach(item => {
                content += `<div class="tooltip-item">
                    <span class="label">${item.label}:</span>
                    <span class="value">${item.value}</span>
                </div>`;
            });
            content += '</div>';
        }
        
        return content;
    }

    /**
     * 차트 간 동기화
     */
    syncZoom(sourceChartId, zoom, center) {
        if (!this.syncEnabled) return;
        
        this.charts.forEach((chartData, chartId) => {
            if (chartId !== sourceChartId && chartData.enabled) {
                this.applyZoomToChart(chartId, zoom, center);
                chartData.zoomLevel = zoom;
            }
        });
    }

    syncPan(sourceChartId, deltaX, deltaY) {
        if (!this.syncEnabled) return;
        
        this.charts.forEach((chartData, chartId) => {
            if (chartId !== sourceChartId && chartData.enabled) {
                chartData.panOffset.x += deltaX;
                chartData.panOffset.y += deltaY;
                this.applyPanToChart(chartId, chartData.panOffset);
            }
        });
    }

    syncCrosshair(sourceChartId, position) {
        if (!this.syncEnabled) return;
        
        this.charts.forEach((chartData, chartId) => {
            if (chartId !== sourceChartId && chartData.enabled) {
                if (chartData.instance.setCrosshair) {
                    chartData.instance.setCrosshair(position);
                }
            }
        });
    }

    /**
     * 커서 업데이트
     */
    updateCursor() {
        const cursor = this.activeDrawingTool ? 
            this.drawingTools.get(this.activeDrawingTool).cursor : 'default';
        
        this.charts.forEach((chartData) => {
            if (chartData.canvas) {
                chartData.canvas.style.cursor = cursor;
            }
        });
    }

    /**
     * 선택된 오브젝트 삭제
     */
    deleteSelectedObjects() {
        // 구현: 선택된 드로잉 오브젝트들 삭제
        this.emit('objectsDeleted');
    }

    /**
     * 실행 취소
     */
    undo() {
        // 구현: 마지막 액션 실행 취소
        this.emit('undo');
    }

    /**
     * 다시 실행
     */
    redo() {
        // 구현: 실행 취소된 액션 다시 실행
        this.emit('redo');
    }

    /**
     * 인터랙션 활성화/비활성화
     */
    setEnabled(enabled) {
        this.isEnabled = enabled;
        this.emit('enabledChanged', enabled);
    }

    /**
     * 동기화 활성화/비활성화
     */
    setSyncEnabled(enabled) {
        this.syncEnabled = enabled;
        this.emit('syncEnabledChanged', enabled);
    }

    /**
     * 설정 업데이트
     */
    updateSettings(settings) {
        if (settings.zoomSensitivity !== undefined) {
            this.zoomSensitivity = settings.zoomSensitivity;
        }
        
        if (settings.panSensitivity !== undefined) {
            this.panSensitivity = settings.panSensitivity;
        }
        
        if (settings.maxZoom !== undefined) {
            this.maxZoom = settings.maxZoom;
        }
        
        if (settings.minZoom !== undefined) {
            this.minZoom = settings.minZoom;
        }
        
        this.emit('settingsUpdated', settings);
    }

    /**
     * 상태 정보 가져오기
     */
    getState() {
        return {
            isEnabled: this.isEnabled,
            syncEnabled: this.syncEnabled,
            currentZoom: this.currentZoom,
            panOffset: this.panOffset,
            activeDrawingTool: this.activeDrawingTool,
            drawnObjects: this.drawnObjects.length,
            connectedCharts: this.charts.size,
            masterChart: this.masterChart
        };
    }

    /**
     * 정리
     */
    destroy() {
        // 이벤트 리스너 제거
        this.charts.forEach((chartData, chartId) => {
            this.removeChartEventListeners(chartId);
        });
        
        // 툴팁 제거
        if (this.tooltipManager && this.tooltipManager.element) {
            this.tooltipManager.element.remove();
        }
        
        // 데이터 정리
        this.charts.clear();
        this.drawingTools.clear();
        this.drawnObjects = [];
        
        super.destroy();
    }
}

export default ChartInteractionManager;
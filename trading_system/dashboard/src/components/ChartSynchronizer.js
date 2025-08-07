import { BaseComponent } from '../core/BaseComponent.js';

/**
 * 차트 간 동기화 시스템
 * - 시간축 동기화
 * - 줌/패닝 동기화
 * - 데이터 범위 동기화
 * - 크로스헤어 동기화
 * - 마스터-슬레이브 구조
 */
export class ChartSynchronizer extends BaseComponent {
    constructor(options = {}) {
        super(null, options);
        
        // 차트 그룹 관리
        this.chartGroups = new Map(); // 그룹별 차트들
        this.chartRegistry = new Map(); // 모든 차트 등록 정보
        this.masterCharts = new Map();  // 그룹별 마스터 차트
        
        // 동기화 설정
        this.syncModes = {
            TIME: 'time',           // 시간축 동기화
            ZOOM: 'zoom',          // 줌 동기화
            PAN: 'pan',            // 패닝 동기화
            CROSSHAIR: 'crosshair', // 크로스헤어 동기화
            SELECTION: 'selection', // 선택 영역 동기화
            DATA_RANGE: 'dataRange' // 데이터 범위 동기화
        };
        
        // 기본 동기화 설정
        this.defaultSyncSettings = options.defaultSync || {
            [this.syncModes.TIME]: true,
            [this.syncModes.ZOOM]: true,
            [this.syncModes.PAN]: true,
            [this.syncModes.CROSSHAIR]: false,
            [this.syncModes.SELECTION]: false,
            [this.syncModes.DATA_RANGE]: false
        };
        
        // 동기화 상태
        this.isSyncEnabled = options.enabled !== false;
        this.syncInProgress = false;
        this.batchUpdates = new Map();
        this.batchTimeout = null;
        this.batchDelay = options.batchDelay || 16; // ~60fps
        
        // 성능 최적화
        this.throttleDelay = options.throttleDelay || 50;
        this.maxChartUpdates = options.maxChartUpdates || 10;
        this.enableSmartSync = options.enableSmartSync !== false;
        
        // 이벤트 필터링
        this.eventFilters = new Map();
        this.setupDefaultEventFilters();
        
        // 통계
        this.stats = {
            syncOperations: 0,
            batchUpdates: 0,
            averageSyncTime: 0,
            skippedUpdates: 0
        };
        
        this.init();
    }

    /**
     * 초기화
     */
    init() {
        this.setupEventListeners();
        this.setupBatchProcessor();
        this.emit('synchronizerInitialized');
    }

    /**
     * 차트 등록
     */
    registerChart(chartId, chartInstance, groupId = 'default', options = {}) {
        const chartInfo = {
            id: chartId,
            instance: chartInstance,
            groupId,
            isMaster: options.isMaster || false,
            syncSettings: { ...this.defaultSyncSettings, ...options.sync },
            lastUpdate: null,
            updateCount: 0,
            bounds: null,
            timeRange: null,
            zoomLevel: 1,
            panOffset: { x: 0, y: 0 }
        };
        
        // 차트 등록
        this.chartRegistry.set(chartId, chartInfo);
        
        // 그룹에 추가
        if (!this.chartGroups.has(groupId)) {
            this.chartGroups.set(groupId, new Set());
        }
        this.chartGroups.get(groupId).add(chartId);
        
        // 마스터 차트 설정
        if (chartInfo.isMaster || !this.masterCharts.has(groupId)) {
            this.masterCharts.set(groupId, chartId);
        }
        
        // 차트별 이벤트 리스너 설정
        this.setupChartEventListeners(chartId, chartInstance);
        
        this.emit('chartRegistered', { chartId, groupId, chartInfo });
        return chartInfo;
    }

    /**
     * 차트 등록 해제
     */
    unregisterChart(chartId) {
        const chartInfo = this.chartRegistry.get(chartId);
        if (!chartInfo) return;
        
        const { groupId } = chartInfo;
        
        // 그룹에서 제거
        const group = this.chartGroups.get(groupId);
        if (group) {
            group.delete(chartId);
            
            // 그룹이 비어있으면 삭제
            if (group.size === 0) {
                this.chartGroups.delete(groupId);
                this.masterCharts.delete(groupId);
            } else if (this.masterCharts.get(groupId) === chartId) {
                // 마스터 차트가 제거된 경우 새로운 마스터 설정
                const newMaster = group.values().next().value;
                this.masterCharts.set(groupId, newMaster);
            }
        }
        
        // 차트별 이벤트 리스너 제거
        this.removeChartEventListeners(chartId);
        
        // 등록 정보 삭제
        this.chartRegistry.delete(chartId);
        
        this.emit('chartUnregistered', { chartId, groupId });
    }

    /**
     * 차트별 이벤트 리스너 설정
     */
    setupChartEventListeners(chartId, chartInstance) {
        const eventHandlers = {
            timeRangeChanged: (event) => this.handleTimeRangeChange(chartId, event),
            zoomChanged: (event) => this.handleZoomChange(chartId, event),
            panChanged: (event) => this.handlePanChange(chartId, event),
            crosshairMoved: (event) => this.handleCrosshairMove(chartId, event),
            selectionChanged: (event) => this.handleSelectionChange(chartId, event),
            dataRangeChanged: (event) => this.handleDataRangeChange(chartId, event)
        };
        
        // 이벤트 리스너 등록
        Object.entries(eventHandlers).forEach(([event, handler]) => {
            if (chartInstance.on) {
                chartInstance.on(event, handler);
            } else if (chartInstance.addEventListener) {
                chartInstance.addEventListener(event, handler);
            }
        });
        
        // 핸들러 참조 저장
        const chartInfo = this.chartRegistry.get(chartId);
        if (chartInfo) {
            chartInfo.eventHandlers = eventHandlers;
        }
    }

    /**
     * 차트 이벤트 리스너 제거
     */
    removeChartEventListeners(chartId) {
        const chartInfo = this.chartRegistry.get(chartId);
        if (!chartInfo || !chartInfo.eventHandlers) return;
        
        const { instance, eventHandlers } = chartInfo;
        
        Object.entries(eventHandlers).forEach(([event, handler]) => {
            if (instance.off) {
                instance.off(event, handler);
            } else if (instance.removeEventListener) {
                instance.removeEventListener(event, handler);
            }
        });
        
        delete chartInfo.eventHandlers;
    }

    /**
     * 시간 범위 변경 핸들러
     */
    handleTimeRangeChange(chartId, event) {
        if (!this.shouldSync(chartId, this.syncModes.TIME)) return;
        
        const chartInfo = this.chartRegistry.get(chartId);
        if (!chartInfo) return;
        
        chartInfo.timeRange = event.timeRange;
        chartInfo.lastUpdate = Date.now();
        
        this.syncTimeRange(chartId, event.timeRange);
    }

    /**
     * 줌 변경 핸들러
     */
    handleZoomChange(chartId, event) {
        if (!this.shouldSync(chartId, this.syncModes.ZOOM)) return;
        
        const chartInfo = this.chartRegistry.get(chartId);
        if (!chartInfo) return;
        
        chartInfo.zoomLevel = event.zoomLevel;
        chartInfo.lastUpdate = Date.now();
        
        this.syncZoom(chartId, event.zoomLevel, event.center);
    }

    /**
     * 패닝 변경 핸들러
     */
    handlePanChange(chartId, event) {
        if (!this.shouldSync(chartId, this.syncModes.PAN)) return;
        
        const chartInfo = this.chartRegistry.get(chartId);
        if (!chartInfo) return;
        
        chartInfo.panOffset = event.panOffset;
        chartInfo.lastUpdate = Date.now();
        
        this.syncPan(chartId, event.panOffset);
    }

    /**
     * 크로스헤어 이동 핸들러
     */
    handleCrosshairMove(chartId, event) {
        if (!this.shouldSync(chartId, this.syncModes.CROSSHAIR)) return;
        
        this.syncCrosshair(chartId, event.position, event.value);
    }

    /**
     * 선택 변경 핸들러
     */
    handleSelectionChange(chartId, event) {
        if (!this.shouldSync(chartId, this.syncModes.SELECTION)) return;
        
        this.syncSelection(chartId, event.selection);
    }

    /**
     * 데이터 범위 변경 핸들러
     */
    handleDataRangeChange(chartId, event) {
        if (!this.shouldSync(chartId, this.syncModes.DATA_RANGE)) return;
        
        this.syncDataRange(chartId, event.dataRange);
    }

    /**
     * 시간 범위 동기화
     */
    syncTimeRange(sourceChartId, timeRange) {
        const sourceChart = this.chartRegistry.get(sourceChartId);
        if (!sourceChart) return;
        
        const targetCharts = this.getTargetCharts(sourceChartId, this.syncModes.TIME);
        
        this.addToBatch('timeRange', {
            sourceChartId,
            timeRange,
            targetCharts: Array.from(targetCharts)
        });
    }

    /**
     * 줌 동기화
     */
    syncZoom(sourceChartId, zoomLevel, center) {
        const sourceChart = this.chartRegistry.get(sourceChartId);
        if (!sourceChart) return;
        
        const targetCharts = this.getTargetCharts(sourceChartId, this.syncModes.ZOOM);
        
        this.addToBatch('zoom', {
            sourceChartId,
            zoomLevel,
            center,
            targetCharts: Array.from(targetCharts)
        });
    }

    /**
     * 패닝 동기화
     */
    syncPan(sourceChartId, panOffset) {
        const sourceChart = this.chartRegistry.get(sourceChartId);
        if (!sourceChart) return;
        
        const targetCharts = this.getTargetCharts(sourceChartId, this.syncModes.PAN);
        
        this.addToBatch('pan', {
            sourceChartId,
            panOffset,
            targetCharts: Array.from(targetCharts)
        });
    }

    /**
     * 크로스헤어 동기화
     */
    syncCrosshair(sourceChartId, position, value) {
        const targetCharts = this.getTargetCharts(sourceChartId, this.syncModes.CROSSHAIR);
        
        // 크로스헤어는 배치 처리하지 않고 즉시 처리
        targetCharts.forEach(chartId => {
            const chartInfo = this.chartRegistry.get(chartId);
            if (chartInfo && chartInfo.instance.setCrosshair) {
                chartInfo.instance.setCrosshair(position, value);
            }
        });
        
        this.emit('crosshairSynced', { sourceChartId, position, value, targetCharts });
    }

    /**
     * 선택 영역 동기화
     */
    syncSelection(sourceChartId, selection) {
        const targetCharts = this.getTargetCharts(sourceChartId, this.syncModes.SELECTION);
        
        this.addToBatch('selection', {
            sourceChartId,
            selection,
            targetCharts: Array.from(targetCharts)
        });
    }

    /**
     * 데이터 범위 동기화
     */
    syncDataRange(sourceChartId, dataRange) {
        const targetCharts = this.getTargetCharts(sourceChartId, this.syncModes.DATA_RANGE);
        
        this.addToBatch('dataRange', {
            sourceChartId,
            dataRange,
            targetCharts: Array.from(targetCharts)
        });
    }

    /**
     * 타겟 차트들 가져오기
     */
    getTargetCharts(sourceChartId, syncMode) {
        const sourceChart = this.chartRegistry.get(sourceChartId);
        if (!sourceChart) return new Set();
        
        const { groupId } = sourceChart;
        const group = this.chartGroups.get(groupId);
        if (!group) return new Set();
        
        const targetCharts = new Set();
        
        for (const chartId of group) {
            if (chartId === sourceChartId) continue;
            
            const chartInfo = this.chartRegistry.get(chartId);
            if (chartInfo && chartInfo.syncSettings[syncMode]) {
                targetCharts.add(chartId);
            }
        }
        
        return targetCharts;
    }

    /**
     * 동기화 여부 확인
     */
    shouldSync(chartId, syncMode) {
        if (!this.isSyncEnabled || this.syncInProgress) return false;
        
        const chartInfo = this.chartRegistry.get(chartId);
        if (!chartInfo) return false;
        
        return chartInfo.syncSettings[syncMode];
    }

    /**
     * 배치 처리기 설정
     */
    setupBatchProcessor() {
        // 정기적인 배치 처리
        setInterval(() => {
            this.processBatchUpdates();
        }, this.batchDelay);
    }

    /**
     * 배치에 추가
     */
    addToBatch(operation, data) {
        if (!this.batchUpdates.has(operation)) {
            this.batchUpdates.set(operation, []);
        }
        
        const batch = this.batchUpdates.get(operation);
        batch.push({
            ...data,
            timestamp: Date.now()
        });
        
        // 중복 제거 및 최신 데이터 유지
        if (batch.length > 1) {
            this.deduplicateBatch(operation, batch);
        }
    }

    /**
     * 배치 중복 제거
     */
    deduplicateBatch(operation, batch) {
        // 같은 소스 차트의 최신 업데이트만 유지
        const deduped = new Map();
        
        batch.forEach(item => {
            const key = `${item.sourceChartId}_${operation}`;
            if (!deduped.has(key) || item.timestamp > deduped.get(key).timestamp) {
                deduped.set(key, item);
            }
        });
        
        batch.length = 0;
        batch.push(...deduped.values());
    }

    /**
     * 배치 업데이트 처리
     */
    processBatchUpdates() {
        if (this.batchUpdates.size === 0) return;
        
        this.syncInProgress = true;
        const startTime = performance.now();
        
        try {
            for (const [operation, batch] of this.batchUpdates) {
                this.processBatchOperation(operation, batch);
                batch.length = 0; // 배치 초기화
            }
            
            this.stats.batchUpdates++;
            
            const syncTime = performance.now() - startTime;
            this.updateSyncTimeStats(syncTime);
            
        } catch (error) {
            this.emit('syncError', error);
        } finally {
            this.syncInProgress = false;
        }
    }

    /**
     * 배치 오퍼레이션 처리
     */
    processBatchOperation(operation, batch) {
        batch.forEach(item => {
            const { targetCharts } = item;
            
            targetCharts.forEach(chartId => {
                this.applySyncOperation(operation, chartId, item);
            });
        });
        
        this.stats.syncOperations += batch.length;
    }

    /**
     * 동기화 오퍼레이션 적용
     */
    applySyncOperation(operation, chartId, data) {
        const chartInfo = this.chartRegistry.get(chartId);
        if (!chartInfo) return;
        
        const { instance } = chartInfo;
        
        try {
            switch (operation) {
                case 'timeRange':
                    if (instance.setTimeRange) {
                        instance.setTimeRange(data.timeRange);
                    }
                    break;
                    
                case 'zoom':
                    if (instance.setZoom) {
                        instance.setZoom(data.zoomLevel, data.center);
                    }
                    break;
                    
                case 'pan':
                    if (instance.setPan) {
                        instance.setPan(data.panOffset);
                    }
                    break;
                    
                case 'selection':
                    if (instance.setSelection) {
                        instance.setSelection(data.selection);
                    }
                    break;
                    
                case 'dataRange':
                    if (instance.setDataRange) {
                        instance.setDataRange(data.dataRange);
                    }
                    break;
            }
            
            chartInfo.updateCount++;
            
        } catch (error) {
            this.emit('syncOperationError', {
                operation,
                chartId,
                error
            });
        }
    }

    /**
     * 기본 이벤트 필터 설정
     */
    setupDefaultEventFilters() {
        // 시간 범위 필터
        this.eventFilters.set('timeRange', (current, previous) => {
            if (!previous) return true;
            
            const timeDiff = Math.abs(current.start - previous.start) + 
                           Math.abs(current.end - previous.end);
            return timeDiff > 1000; // 1초 이상 차이날 때만 동기화
        });
        
        // 줌 레벨 필터
        this.eventFilters.set('zoom', (current, previous) => {
            if (!previous) return true;
            
            const zoomDiff = Math.abs(current - previous);
            return zoomDiff > 0.01; // 1% 이상 차이날 때만 동기화
        });
        
        // 패닝 오프셋 필터
        this.eventFilters.set('pan', (current, previous) => {
            if (!previous) return true;
            
            const panDiff = Math.abs(current.x - previous.x) + 
                          Math.abs(current.y - previous.y);
            return panDiff > 5; // 5px 이상 차이날 때만 동기화
        });
    }

    /**
     * 전역 이벤트 리스너 설정
     */
    setupEventListeners() {
        // 윈도우 포커스 변경 시 동기화 상태 확인
        window.addEventListener('focus', () => {
            this.validateSyncState();
        });
        
        // 성능 모니터링
        setInterval(() => {
            this.emit('syncStats', this.getSyncStats());
        }, 5000);
    }

    /**
     * 동기화 상태 검증
     */
    validateSyncState() {
        // 모든 차트의 상태를 검증하고 불일치 발견 시 재동기화
        for (const [groupId, chartIds] of this.chartGroups) {
            const masterChartId = this.masterCharts.get(groupId);
            if (!masterChartId) continue;
            
            const masterChart = this.chartRegistry.get(masterChartId);
            if (!masterChart) continue;
            
            // 마스터 차트 상태를 기준으로 다른 차트들 동기화
            this.syncAllFromMaster(groupId, masterChartId);
        }
    }

    /**
     * 마스터 차트 기준으로 전체 동기화
     */
    syncAllFromMaster(groupId, masterChartId) {
        const masterChart = this.chartRegistry.get(masterChartId);
        if (!masterChart) return;
        
        const group = this.chartGroups.get(groupId);
        if (!group) return;
        
        for (const chartId of group) {
            if (chartId === masterChartId) continue;
            
            const chartInfo = this.chartRegistry.get(chartId);
            if (!chartInfo) continue;
            
            // 각 동기화 모드별로 마스터 차트 상태 적용
            Object.entries(this.syncModes).forEach(([key, mode]) => {
                if (chartInfo.syncSettings[mode]) {
                    this.syncFromMaster(mode, masterChart, chartInfo);
                }
            });
        }
    }

    /**
     * 마스터 차트로부터 동기화
     */
    syncFromMaster(mode, masterChart, targetChart) {
        const { instance: masterInstance } = masterChart;
        const { instance: targetInstance } = targetChart;
        
        try {
            switch (mode) {
                case this.syncModes.TIME:
                    if (masterChart.timeRange && targetInstance.setTimeRange) {
                        targetInstance.setTimeRange(masterChart.timeRange);
                    }
                    break;
                    
                case this.syncModes.ZOOM:
                    if (masterChart.zoomLevel && targetInstance.setZoom) {
                        targetInstance.setZoom(masterChart.zoomLevel);
                    }
                    break;
                    
                case this.syncModes.PAN:
                    if (masterChart.panOffset && targetInstance.setPan) {
                        targetInstance.setPan(masterChart.panOffset);
                    }
                    break;
            }
        } catch (error) {
            this.emit('masterSyncError', { mode, error });
        }
    }

    /**
     * 동기화 시간 통계 업데이트
     */
    updateSyncTimeStats(syncTime) {
        if (this.stats.averageSyncTime === 0) {
            this.stats.averageSyncTime = syncTime;
        } else {
            this.stats.averageSyncTime = (this.stats.averageSyncTime * 0.9) + (syncTime * 0.1);
        }
    }

    /**
     * 동기화 통계 가져오기
     */
    getSyncStats() {
        return {
            ...this.stats,
            chartGroups: this.chartGroups.size,
            registeredCharts: this.chartRegistry.size,
            pendingBatches: this.batchUpdates.size,
            isEnabled: this.isSyncEnabled,
            syncInProgress: this.syncInProgress
        };
    }

    /**
     * 차트 그룹의 동기화 설정 업데이트
     */
    updateGroupSyncSettings(groupId, syncSettings) {
        const group = this.chartGroups.get(groupId);
        if (!group) return;
        
        for (const chartId of group) {
            const chartInfo = this.chartRegistry.get(chartId);
            if (chartInfo) {
                chartInfo.syncSettings = { ...chartInfo.syncSettings, ...syncSettings };
            }
        }
        
        this.emit('groupSyncSettingsUpdated', { groupId, syncSettings });
    }

    /**
     * 마스터 차트 변경
     */
    changeMasterChart(groupId, newMasterChartId) {
        const group = this.chartGroups.get(groupId);
        if (!group || !group.has(newMasterChartId)) return false;
        
        this.masterCharts.set(groupId, newMasterChartId);
        
        // 새 마스터 차트로부터 전체 동기화
        this.syncAllFromMaster(groupId, newMasterChartId);
        
        this.emit('masterChartChanged', { groupId, newMasterChartId });
        return true;
    }

    /**
     * 동기화 활성화/비활성화
     */
    setEnabled(enabled) {
        this.isSyncEnabled = enabled;
        this.emit('syncEnabledChanged', enabled);
    }

    /**
     * 스마트 동기화 모드 토글
     */
    setSmartSyncEnabled(enabled) {
        this.enableSmartSync = enabled;
        this.emit('smartSyncEnabledChanged', enabled);
    }

    /**
     * 설정 업데이트
     */
    updateSettings(settings) {
        if (settings.batchDelay !== undefined) {
            this.batchDelay = settings.batchDelay;
        }
        
        if (settings.throttleDelay !== undefined) {
            this.throttleDelay = settings.throttleDelay;
        }
        
        if (settings.maxChartUpdates !== undefined) {
            this.maxChartUpdates = settings.maxChartUpdates;
        }
        
        this.emit('settingsUpdated', settings);
    }

    /**
     * 정리
     */
    destroy() {
        // 모든 차트 등록 해제
        for (const chartId of this.chartRegistry.keys()) {
            this.unregisterChart(chartId);
        }
        
        // 배치 처리 정리
        if (this.batchTimeout) {
            clearTimeout(this.batchTimeout);
        }
        
        // 데이터 정리
        this.chartGroups.clear();
        this.chartRegistry.clear();
        this.masterCharts.clear();
        this.batchUpdates.clear();
        this.eventFilters.clear();
        
        super.destroy();
    }
}

export default ChartSynchronizer;
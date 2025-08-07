/**
 * @fileoverview 차트 서비스 - 고급 데이터 시각화
 * @description Chart.js와 D3.js를 활용한 차트 관리 시스템
 */

import { eventBus } from '../core/EventBus.js';
import { globalStore } from '../core/Store.js';

/**
 * 차트 서비스 클래스
 * @class ChartService
 */
export class ChartService {
    constructor() {
        this.charts = new Map();
        this.chartInstances = new WeakMap();
        this.defaultOptions = this.getDefaultChartOptions();
        this.colorSchemes = this.getColorSchemes();
        this.animationQueue = [];
        this.isAnimating = false;
        
        // 성능 최적화
        this.updateDebounceTime = 16; // ~60fps
        this.maxDataPoints = 1000;
        this.decimationFactor = 2;
        
        // 차트 타입별 설정
        this.chartConfigs = new Map();
        this.initializeChartConfigs();
        
        // 반응형 설정
        this.breakpoints = {
            mobile: 768,
            tablet: 1024,
            desktop: 1440
        };
        
        this.currentBreakpoint = this.getCurrentBreakpoint();
        this.initializeResponsiveHandling();
        
        // 데이터 캐시
        this.dataCache = new Map();
        this.cacheTimeout = 60000; // 1분
        
        // 통계
        this.stats = {
            chartsCreated: 0,
            chartsDestroyed: 0,
            updatesPerformed: 0,
            averageUpdateTime: 0
        };
    }

    /**
     * 기본 차트 옵션 가져오기
     * @returns {Object} 기본 옵션
     * @private
     */
    getDefaultChartOptions() {
        return {
            responsive: true,
            maintainAspectRatio: false,
            interaction: {
                intersect: false,
                mode: 'index'
            },
            plugins: {
                legend: {
                    display: true,
                    position: 'top',
                    labels: {
                        usePointStyle: true,
                        padding: 20
                    }
                },
                tooltip: {
                    backgroundColor: 'rgba(0, 0, 0, 0.8)',
                    titleColor: '#ffffff',
                    bodyColor: '#ffffff',
                    cornerRadius: 8,
                    padding: 12
                }
            },
            scales: {
                x: {
                    display: true,
                    grid: {
                        display: true,
                        color: 'rgba(255, 255, 255, 0.1)'
                    },
                    ticks: {
                        color: '#888888'
                    }
                },
                y: {
                    display: true,
                    grid: {
                        display: true,
                        color: 'rgba(255, 255, 255, 0.1)'
                    },
                    ticks: {
                        color: '#888888'
                    }
                }
            },
            animation: {
                duration: 300,
                easing: 'easeInOutQuart'
            }
        };
    }

    /**
     * 색상 스키마 가져오기
     * @returns {Object} 색상 스키마
     * @private
     */
    getColorSchemes() {
        return {
            profit: {
                primary: '#10B981',
                secondary: '#059669',
                background: 'rgba(16, 185, 129, 0.1)',
                gradient: ['#10B981', '#059669']
            },
            loss: {
                primary: '#EF4444',
                secondary: '#DC2626',
                background: 'rgba(239, 68, 68, 0.1)',
                gradient: ['#EF4444', '#DC2626']
            },
            neutral: {
                primary: '#6366F1',
                secondary: '#4F46E5',
                background: 'rgba(99, 102, 241, 0.1)',
                gradient: ['#6366F1', '#4F46E5']
            },
            warning: {
                primary: '#F59E0B',
                secondary: '#D97706',
                background: 'rgba(245, 158, 11, 0.1)',
                gradient: ['#F59E0B', '#D97706']
            }
        };
    }

    /**
     * 차트 타입별 설정 초기화
     * @private
     */
    initializeChartConfigs() {
        // 라인 차트 설정
        this.chartConfigs.set('line', {
            type: 'line',
            options: {
                ...this.defaultOptions,
                elements: {
                    point: {
                        radius: 2,
                        hoverRadius: 4
                    },
                    line: {
                        tension: 0.4,
                        borderWidth: 2
                    }
                }
            }
        });

        // 캔들스틱 차트 설정
        this.chartConfigs.set('candlestick', {
            type: 'candlestick',
            options: {
                ...this.defaultOptions,
                scales: {
                    ...this.defaultOptions.scales,
                    y: {
                        ...this.defaultOptions.scales.y,
                        type: 'linear'
                    }
                }
            }
        });

        // 히트맵 설정
        this.chartConfigs.set('heatmap', {
            type: 'matrix',
            options: {
                ...this.defaultOptions,
                plugins: {
                    ...this.defaultOptions.plugins,
                    legend: {
                        display: false
                    }
                }
            }
        });

        // 도넛 차트 설정
        this.chartConfigs.set('doughnut', {
            type: 'doughnut',
            options: {
                ...this.defaultOptions,
                cutout: '70%',
                plugins: {
                    ...this.defaultOptions.plugins,
                    legend: {
                        position: 'right'
                    }
                }
            }
        });
    }

    /**
     * 반응형 처리 초기화
     * @private
     */
    initializeResponsiveHandling() {
        if (typeof window !== 'undefined') {
            const resizeObserver = new ResizeObserver((entries) => {
                const newBreakpoint = this.getCurrentBreakpoint();
                if (newBreakpoint !== this.currentBreakpoint) {
                    this.currentBreakpoint = newBreakpoint;
                    this.handleBreakpointChange();
                }
            });

            resizeObserver.observe(document.body);
        }
    }

    /**
     * 현재 브레이크포인트 가져오기
     * @returns {string} 브레이크포인트
     * @private
     */
    getCurrentBreakpoint() {
        const width = window.innerWidth;
        
        if (width < this.breakpoints.mobile) return 'mobile';
        if (width < this.breakpoints.tablet) return 'tablet';
        return 'desktop';
    }

    /**
     * 브레이크포인트 변경 처리
     * @private
     */
    handleBreakpointChange() {
        this.charts.forEach((chartData, chartId) => {
            this.updateChartResponsive(chartId);
        });
        
        eventBus.emit('chart:breakpoint_change', {
            breakpoint: this.currentBreakpoint
        });
    }

    /**
     * 차트 생성
     * @param {string} canvasId - 캔버스 ID
     * @param {string} type - 차트 타입
     * @param {Object} data - 차트 데이터
     * @param {Object} [options] - 차트 옵션
     * @returns {Promise<Object>} 차트 인스턴스
     */
    async createChart(canvasId, type, data, options = {}) {
        try {
            const canvas = document.getElementById(canvasId);
            if (!canvas) {
                throw new Error(`Canvas with id "${canvasId}" not found`);
            }

            // 기존 차트 제거
            if (this.charts.has(canvasId)) {
                await this.destroyChart(canvasId);
            }

            // 차트 설정 준비
            const config = this.prepareChartConfig(type, data, options);
            
            // Chart.js 차트 생성
            const Chart = await this.loadChartJS();
            const chartInstance = new Chart(canvas, config);

            // 차트 정보 저장
            const chartData = {
                instance: chartInstance,
                type,
                canvas,
                config,
                lastUpdate: Date.now()
            };

            this.charts.set(canvasId, chartData);
            this.chartInstances.set(chartInstance, chartData);

            // 통계 업데이트
            this.stats.chartsCreated++;

            // 이벤트 발생
            eventBus.emit('chart:created', {
                chartId: canvasId,
                type,
                timestamp: Date.now()
            });

            return chartInstance;

        } catch (error) {
            console.error(`차트 생성 실패 (${canvasId}):`, error);
            throw error;
        }
    }

    /**
     * Chart.js 라이브러리 로드
     * @returns {Promise<Object>} Chart.js 객체
     * @private
     */
    async loadChartJS() {
        // 이미 로드된 경우
        if (window.Chart) {
            return window.Chart;
        }

        // 동적 로드
        return new Promise((resolve, reject) => {
            const script = document.createElement('script');
            script.src = 'https://cdn.jsdelivr.net/npm/chart.js@4.2.1/dist/chart.umd.js';
            script.onload = () => resolve(window.Chart);
            script.onerror = reject;
            document.head.appendChild(script);
        });
    }

    /**
     * 차트 설정 준비
     * @param {string} type - 차트 타입
     * @param {Object} data - 차트 데이터
     * @param {Object} options - 추가 옵션
     * @returns {Object} 차트 설정
     * @private
     */
    prepareChartConfig(type, data, options) {
        const baseConfig = this.chartConfigs.get(type) || this.chartConfigs.get('line');
        
        return {
            type: baseConfig.type,
            data: this.processChartData(data, type),
            options: this.mergeOptions(baseConfig.options, options)
        };
    }

    /**
     * 차트 데이터 처리
     * @param {Object} data - 원본 데이터
     * @param {string} type - 차트 타입
     * @returns {Object} 처리된 데이터
     * @private
     */
    processChartData(data, type) {
        let processedData = { ...data };

        // 데이터셋에 색상 적용
        if (processedData.datasets) {
            processedData.datasets = processedData.datasets.map((dataset, index) => {
                return this.applyDatasetColors(dataset, type, index);
            });
        }

        // 데이터 포인트 제한
        if (type === 'line' && processedData.datasets) {
            processedData = this.limitDataPoints(processedData);
        }

        return processedData;
    }

    /**
     * 데이터셋에 색상 적용
     * @param {Object} dataset - 데이터셋
     * @param {string} type - 차트 타입
     * @param {number} index - 데이터셋 인덱스
     * @returns {Object} 색상이 적용된 데이터셋
     * @private
     */
    applyDatasetColors(dataset, type, index) {
        const colorScheme = this.getDatasetColorScheme(dataset, index);
        
        const coloredDataset = { ...dataset };

        switch (type) {
            case 'line':
                coloredDataset.borderColor = colorScheme.primary;
                coloredDataset.backgroundColor = colorScheme.background;
                coloredDataset.pointBackgroundColor = colorScheme.primary;
                break;
                
            case 'bar':
                coloredDataset.backgroundColor = colorScheme.primary;
                coloredDataset.borderColor = colorScheme.secondary;
                coloredDataset.borderWidth = 1;
                break;
                
            case 'doughnut':
                coloredDataset.backgroundColor = this.generateColorPalette(
                    dataset.data.length, 
                    colorScheme
                );
                break;
        }

        return coloredDataset;
    }

    /**
     * 데이터셋 색상 스키마 가져오기
     * @param {Object} dataset - 데이터셋
     * @param {number} index - 인덱스
     * @returns {Object} 색상 스키마
     * @private
     */
    getDatasetColorScheme(dataset, index) {
        // 명시적 색상 스키마
        if (dataset.colorScheme) {
            return this.colorSchemes[dataset.colorScheme] || this.colorSchemes.neutral;
        }

        // 라벨 기반 추론
        const label = (dataset.label || '').toLowerCase();
        if (label.includes('profit') || label.includes('수익')) {
            return this.colorSchemes.profit;
        }
        if (label.includes('loss') || label.includes('손실')) {
            return this.colorSchemes.loss;
        }
        if (label.includes('warning') || label.includes('경고')) {
            return this.colorSchemes.warning;
        }

        // 기본 색상 (인덱스 기반)
        const schemes = Object.values(this.colorSchemes);
        return schemes[index % schemes.length];
    }

    /**
     * 색상 팔레트 생성
     * @param {number} count - 색상 개수
     * @param {Object} baseScheme - 기본 색상 스키마
     * @returns {Array} 색상 배열
     * @private
     */
    generateColorPalette(count, baseScheme) {
        const colors = [];
        const baseHue = this.hexToHsl(baseScheme.primary)[0];
        
        for (let i = 0; i < count; i++) {
            const hue = (baseHue + (i * 360 / count)) % 360;
            colors.push(this.hslToHex(hue, 70, 60));
        }
        
        return colors;
    }

    /**
     * 차트 데이터 업데이트
     * @param {string} canvasId - 캔버스 ID
     * @param {Object} newData - 새로운 데이터
     * @param {boolean} [animate] - 애니메이션 여부
     */
    async updateChart(canvasId, newData, animate = true) {
        const startTime = performance.now();
        
        try {
            const chartData = this.charts.get(canvasId);
            if (!chartData) {
                console.warn(`Chart with id "${canvasId}" not found`);
                return;
            }

            const { instance, type } = chartData;
            
            // 데이터 처리
            const processedData = this.processChartData(newData, type);
            
            // 차트 업데이트
            if (animate) {
                await this.animateChartUpdate(instance, processedData);
            } else {
                instance.data = processedData;
                instance.update('none');
            }

            // 업데이트 시간 기록
            chartData.lastUpdate = Date.now();
            
            // 통계 업데이트
            const updateTime = performance.now() - startTime;
            this.updateStats(updateTime);

            // 이벤트 발생
            eventBus.emit('chart:updated', {
                chartId: canvasId,
                updateTime,
                timestamp: Date.now()
            });

        } catch (error) {
            console.error(`차트 업데이트 실패 (${canvasId}):`, error);
        }
    }

    /**
     * 애니메이션과 함께 차트 업데이트
     * @param {Object} chartInstance - 차트 인스턴스
     * @param {Object} newData - 새로운 데이터
     * @returns {Promise<void>}
     * @private
     */
    async animateChartUpdate(chartInstance, newData) {
        return new Promise((resolve) => {
            this.animationQueue.push({
                instance: chartInstance,
                data: newData,
                resolve
            });
            
            if (!this.isAnimating) {
                this.processAnimationQueue();
            }
        });
    }

    /**
     * 애니메이션 큐 처리
     * @private
     */
    async processAnimationQueue() {
        if (this.animationQueue.length === 0) {
            this.isAnimating = false;
            return;
        }

        this.isAnimating = true;
        
        while (this.animationQueue.length > 0) {
            const { instance, data, resolve } = this.animationQueue.shift();
            
            instance.data = data;
            instance.update();
            
            // 애니메이션 완료 대기
            await new Promise(r => setTimeout(r, 350));
            
            resolve();
        }

        this.isAnimating = false;
    }

    /**
     * 스파크라인 차트 생성
     * @param {string} canvasId - 캔버스 ID
     * @param {Array} data - 데이터 배열
     * @param {Object} [options] - 옵션
     * @returns {Promise<Object>} 차트 인스턴스
     */
    async createSparkline(canvasId, data, options = {}) {
        const sparklineData = {
            labels: data.map((_, index) => index),
            datasets: [{
                data: data,
                fill: true,
                borderWidth: 2,
                pointRadius: 0,
                pointHoverRadius: 0,
                colorScheme: options.colorScheme || 'profit'
            }]
        };

        const sparklineOptions = {
            plugins: {
                legend: { display: false },
                tooltip: { enabled: false }
            },
            scales: {
                x: { display: false },
                y: { display: false }
            },
            animation: { duration: 200 },
            ...options
        };

        return this.createChart(canvasId, 'line', sparklineData, sparklineOptions);
    }

    /**
     * 히트맵 생성
     * @param {string} canvasId - 캔버스 ID
     * @param {Array} data - 2D 데이터 배열
     * @param {Array} xLabels - X축 라벨
     * @param {Array} yLabels - Y축 라벨
     * @param {Object} [options] - 옵션
     * @returns {Promise<Object>} 차트 인스턴스
     */
    async createHeatmap(canvasId, data, xLabels, yLabels, options = {}) {
        // Chart.js용 히트맵 데이터 변환
        const heatmapData = [];
        
        data.forEach((row, y) => {
            row.forEach((value, x) => {
                heatmapData.push({
                    x: xLabels[x],
                    y: yLabels[y],
                    v: value
                });
            });
        });

        const chartData = {
            datasets: [{
                label: 'Correlation',
                data: heatmapData,
                backgroundColor: (ctx) => {
                    const value = ctx.parsed.v;
                    const alpha = Math.abs(value);
                    return value > 0 ? 
                        `rgba(16, 185, 129, ${alpha})` : 
                        `rgba(239, 68, 68, ${alpha})`;
                },
                borderColor: 'rgba(255, 255, 255, 0.1)',
                borderWidth: 1
            }]
        };

        return this.createChart(canvasId, 'heatmap', chartData, options);
    }

    /**
     * 실시간 가격 차트 생성
     * @param {string} canvasId - 캔버스 ID
     * @param {string} symbol - 심볼
     * @param {Object} [options] - 옵션
     * @returns {Promise<Object>} 차트 인스턴스
     */
    async createPriceChart(symbol, canvasId, options = {}) {
        const priceData = await this.getPriceData(symbol);
        
        const chartData = {
            labels: priceData.map(d => new Date(d.timestamp).toLocaleTimeString()),
            datasets: [{
                label: `${symbol} Price`,
                data: priceData.map(d => d.price),
                colorScheme: 'neutral',
                fill: false
            }]
        };

        const chart = await this.createChart(canvasId, 'line', chartData, options);
        
        // 실시간 업데이트 구독
        this.subscribeToRealTimeUpdates(symbol, canvasId);
        
        return chart;
    }

    /**
     * 실시간 업데이트 구독
     * @param {string} symbol - 심볼
     * @param {string} canvasId - 캔버스 ID
     * @private
     */
    subscribeToRealTimeUpdates(symbol, canvasId) {
        eventBus.on(`websocket:price_update`, (data) => {
            if (data[symbol]) {
                this.addPricePoint(canvasId, data[symbol]);
            }
        }, { namespace: `chart_${canvasId}` });
    }

    /**
     * 가격 포인트 추가
     * @param {string} canvasId - 캔버스 ID
     * @param {number} price - 새로운 가격
     * @private
     */
    addPricePoint(canvasId, price) {
        const chartData = this.charts.get(canvasId);
        if (!chartData) return;

        const { instance } = chartData;
        const now = new Date().toLocaleTimeString();
        
        // 데이터 추가
        instance.data.labels.push(now);
        instance.data.datasets[0].data.push(price);
        
        // 최대 데이터 포인트 제한
        if (instance.data.labels.length > this.maxDataPoints) {
            instance.data.labels.shift();
            instance.data.datasets[0].data.shift();
        }
        
        // 차트 업데이트 (디바운싱)
        this.debounceUpdate(canvasId);
    }

    /**
     * 업데이트 디바운싱
     * @param {string} canvasId - 캔버스 ID
     * @private
     */
    debounceUpdate(canvasId) {
        const chartData = this.charts.get(canvasId);
        if (!chartData) return;

        clearTimeout(chartData.updateTimeout);
        chartData.updateTimeout = setTimeout(() => {
            chartData.instance.update('none');
        }, this.updateDebounceTime);
    }

    /**
     * 차트 제거
     * @param {string} canvasId - 캔버스 ID
     */
    async destroyChart(canvasId) {
        const chartData = this.charts.get(canvasId);
        if (!chartData) return;

        const { instance } = chartData;
        
        // 이벤트 구독 해제
        eventBus.offNamespace(`chart_${canvasId}`);
        
        // 차트 인스턴스 제거
        instance.destroy();
        
        // 참조 제거
        this.charts.delete(canvasId);
        this.chartInstances.delete(instance);
        
        // 통계 업데이트
        this.stats.chartsDestroyed++;
        
        // 이벤트 발생
        eventBus.emit('chart:destroyed', {
            chartId: canvasId,
            timestamp: Date.now()
        });
    }

    /**
     * 모든 차트 제거
     */
    async destroyAllCharts() {
        const chartIds = Array.from(this.charts.keys());
        
        for (const chartId of chartIds) {
            await this.destroyChart(chartId);
        }
    }

    /**
     * 차트 반응형 업데이트
     * @param {string} canvasId - 캔버스 ID
     * @private
     */
    updateChartResponsive(canvasId) {
        const chartData = this.charts.get(canvasId);
        if (!chartData) return;

        const { instance } = chartData;
        
        // 브레이크포인트에 따른 옵션 조정
        const responsiveOptions = this.getResponsiveOptions();
        
        instance.options = this.mergeOptions(instance.options, responsiveOptions);
        instance.update();
    }

    /**
     * 반응형 옵션 가져오기
     * @returns {Object} 반응형 옵션
     * @private
     */
    getResponsiveOptions() {
        switch (this.currentBreakpoint) {
            case 'mobile':
                return {
                    plugins: {
                        legend: {
                            display: false
                        }
                    },
                    scales: {
                        x: { ticks: { maxTicksLimit: 5 } },
                        y: { ticks: { maxTicksLimit: 5 } }
                    }
                };
                
            case 'tablet':
                return {
                    plugins: {
                        legend: {
                            position: 'bottom'
                        }
                    },
                    scales: {
                        x: { ticks: { maxTicksLimit: 8 } },
                        y: { ticks: { maxTicksLimit: 8 } }
                    }
                };
                
            default:
                return {};
        }
    }

    // 유틸리티 메서드들

    /**
     * 옵션 병합
     * @param {Object} baseOptions - 기본 옵션
     * @param {Object} customOptions - 커스텀 옵션
     * @returns {Object} 병합된 옵션
     * @private
     */
    mergeOptions(baseOptions, customOptions) {
        return this.deepMerge(baseOptions, customOptions);
    }

    /**
     * 깊은 객체 병합
     * @param {Object} target - 대상 객체
     * @param {Object} source - 소스 객체
     * @returns {Object} 병합된 객체
     * @private
     */
    deepMerge(target, source) {
        const output = { ...target };
        
        if (this.isObject(target) && this.isObject(source)) {
            Object.keys(source).forEach(key => {
                if (this.isObject(source[key])) {
                    if (!(key in target)) {
                        Object.assign(output, { [key]: source[key] });
                    } else {
                        output[key] = this.deepMerge(target[key], source[key]);
                    }
                } else {
                    Object.assign(output, { [key]: source[key] });
                }
            });
        }
        
        return output;
    }

    /**
     * 객체 여부 확인
     * @param {*} item - 확인할 항목
     * @returns {boolean} 객체 여부
     * @private
     */
    isObject(item) {
        return item && typeof item === 'object' && !Array.isArray(item);
    }

    /**
     * 데이터 포인트 제한
     * @param {Object} data - 차트 데이터
     * @returns {Object} 제한된 데이터
     * @private
     */
    limitDataPoints(data) {
        if (!data.labels || data.labels.length <= this.maxDataPoints) {
            return data;
        }

        const factor = Math.ceil(data.labels.length / this.maxDataPoints);
        
        return {
            ...data,
            labels: data.labels.filter((_, index) => index % factor === 0),
            datasets: data.datasets.map(dataset => ({
                ...dataset,
                data: dataset.data.filter((_, index) => index % factor === 0)
            }))
        };
    }

    /**
     * HEX를 HSL로 변환
     * @param {string} hex - HEX 색상
     * @returns {Array} HSL 배열
     * @private
     */
    hexToHsl(hex) {
        const r = parseInt(hex.slice(1, 3), 16) / 255;
        const g = parseInt(hex.slice(3, 5), 16) / 255;
        const b = parseInt(hex.slice(5, 7), 16) / 255;

        const max = Math.max(r, g, b);
        const min = Math.min(r, g, b);
        let h, s, l = (max + min) / 2;

        if (max === min) {
            h = s = 0;
        } else {
            const d = max - min;
            s = l > 0.5 ? d / (2 - max - min) : d / (max + min);
            switch (max) {
                case r: h = (g - b) / d + (g < b ? 6 : 0); break;
                case g: h = (b - r) / d + 2; break;
                case b: h = (r - g) / d + 4; break;
            }
            h /= 6;
        }

        return [h * 360, s * 100, l * 100];
    }

    /**
     * HSL을 HEX로 변환
     * @param {number} h - 색조
     * @param {number} s - 채도
     * @param {number} l - 명도
     * @returns {string} HEX 색상
     * @private
     */
    hslToHex(h, s, l) {
        h /= 360;
        s /= 100;
        l /= 100;

        const hue2rgb = (p, q, t) => {
            if (t < 0) t += 1;
            if (t > 1) t -= 1;
            if (t < 1/6) return p + (q - p) * 6 * t;
            if (t < 1/2) return q;
            if (t < 2/3) return p + (q - p) * (2/3 - t) * 6;
            return p;
        };

        const q = l < 0.5 ? l * (1 + s) : l + s - l * s;
        const p = 2 * l - q;
        
        const r = Math.round(hue2rgb(p, q, h + 1/3) * 255);
        const g = Math.round(hue2rgb(p, q, h) * 255);
        const b = Math.round(hue2rgb(p, q, h - 1/3) * 255);

        return `#${((1 << 24) + (r << 16) + (g << 8) + b).toString(16).slice(1)}`;
    }

    /**
     * 가격 데이터 가져오기 (모의 데이터)
     * @param {string} symbol - 심볼
     * @returns {Promise<Array>} 가격 데이터
     * @private
     */
    async getPriceData(symbol) {
        // 실제 구현에서는 API에서 데이터를 가져옴
        const now = Date.now();
        const data = [];
        
        for (let i = 100; i >= 0; i--) {
            data.push({
                timestamp: now - (i * 60000), // 1분 간격
                price: 50000 + Math.random() * 1000 - 500
            });
        }
        
        return data;
    }

    /**
     * 통계 업데이트
     * @param {number} updateTime - 업데이트 시간
     * @private
     */
    updateStats(updateTime) {
        this.stats.updatesPerformed++;
        this.stats.averageUpdateTime = 
            (this.stats.averageUpdateTime * (this.stats.updatesPerformed - 1) + updateTime) / 
            this.stats.updatesPerformed;
    }

    /**
     * 통계 정보 가져오기
     * @returns {Object} 차트 통계
     */
    getStats() {
        return {
            ...this.stats,
            activeCharts: this.charts.size,
            currentBreakpoint: this.currentBreakpoint,
            cacheSize: this.dataCache.size
        };
    }

    /**
     * 캐시 클리어
     */
    clearCache() {
        this.dataCache.clear();
    }

    /**
     * 통계 리셋
     */
    resetStats() {
        this.stats = {
            chartsCreated: 0,
            chartsDestroyed: 0,
            updatesPerformed: 0,
            averageUpdateTime: 0
        };
    }
}

// 전역 차트 서비스 인스턴스
export const chartService = new ChartService();

// 개발 모드에서 전역 접근 가능하게 설정
if (typeof window !== 'undefined' && process.env.NODE_ENV === 'development') {
    window.__TRADING_DASHBOARD_CHARTS__ = chartService;
}
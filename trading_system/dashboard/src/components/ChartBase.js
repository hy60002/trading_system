import { BaseComponent } from '../core/BaseComponent.js';

/**
 * 차트 컴포넌트 베이스 클래스
 * - Chart.js 기반 공통 차트 기능
 * - 실시간 데이터 업데이트
 * - 반응형 차트 시스템
 * - 테마 지원
 * - 성능 최적화
 */
export class ChartBase extends BaseComponent {
    constructor(container, options = {}) {
        super(container, options);
        
        // Chart.js 인스턴스
        this.chart = null;
        this.canvas = null;
        this.ctx = null;
        
        // 차트 설정
        this.chartType = options.chartType || 'line';
        this.chartOptions = options.chartOptions || {};
        this.data = options.data || { labels: [], datasets: [] };
        
        // 실시간 업데이트 설정
        this.updateInterval = options.updateInterval || 1000;
        this.maxDataPoints = options.maxDataPoints || 100;
        this.autoUpdate = options.autoUpdate || false;
        this.updateTimer = null;
        
        // 성능 최적화 설정
        this.animationDuration = options.animationDuration || 300;
        this.enableAnimations = options.enableAnimations !== false;
        this.responsiveDelay = options.responsiveDelay || 150;
        
        // 테마 설정
        this.theme = options.theme || 'dark';
        this.colors = this.getThemeColors();
        
        // 상태 관리
        this.isInitialized = false;
        this.isUpdating = false;
        this.lastUpdate = null;
        
        this.init();
    }

    /**
     * 차트 초기화
     */
    init() {
        this.createCanvas();
        this.setupDefaultOptions();
        this.createChart();
        this.setupEventListeners();
        this.setupResizeHandler();
        
        if (this.autoUpdate) {
            this.startAutoUpdate();
        }
        
        this.isInitialized = true;
        this.emit('chartInitialized');
    }

    /**
     * 캔버스 생성
     */
    createCanvas() {
        this.canvas = document.createElement('canvas');
        this.canvas.style.maxWidth = '100%';
        this.canvas.style.height = 'auto';
        
        // 고DPI 디스플레이 지원
        const devicePixelRatio = window.devicePixelRatio || 1;
        this.canvas.style.width = '100%';
        this.canvas.style.height = '400px';
        
        this.element.appendChild(this.canvas);
        this.ctx = this.canvas.getContext('2d');
    }

    /**
     * 기본 차트 옵션 설정
     */
    setupDefaultOptions() {
        this.defaultOptions = {
            responsive: true,
            maintainAspectRatio: false,
            interaction: {
                intersect: false,
                mode: 'index'
            },
            animation: {
                duration: this.enableAnimations ? this.animationDuration : 0,
                easing: 'easeInOutQuart'
            },
            plugins: {
                legend: {
                    display: true,
                    position: 'top',
                    labels: {
                        color: this.colors.text,
                        font: {
                            family: 'Inter, sans-serif',
                            size: 12
                        },
                        usePointStyle: true,
                        padding: 20
                    }
                },
                tooltip: {
                    backgroundColor: this.colors.tooltipBg,
                    titleColor: this.colors.text,
                    bodyColor: this.colors.text,
                    borderColor: this.colors.border,
                    borderWidth: 1,
                    cornerRadius: 8,
                    displayColors: true,
                    titleFont: {
                        family: 'Inter, sans-serif',
                        size: 13,
                        weight: 'bold'
                    },
                    bodyFont: {
                        family: 'Inter, sans-serif',
                        size: 12
                    },
                    callbacks: {
                        title: (tooltipItems) => {
                            return this.formatTooltipTitle(tooltipItems);
                        },
                        label: (context) => {
                            return this.formatTooltipLabel(context);
                        }
                    }
                }
            },
            scales: {
                x: {
                    display: true,
                    grid: {
                        color: this.colors.gridLines,
                        drawBorder: false
                    },
                    ticks: {
                        color: this.colors.text,
                        font: {
                            family: 'Inter, sans-serif',
                            size: 11
                        }
                    }
                },
                y: {
                    display: true,
                    grid: {
                        color: this.colors.gridLines,
                        drawBorder: false
                    },
                    ticks: {
                        color: this.colors.text,
                        font: {
                            family: 'Inter, sans-serif',
                            size: 11
                        },
                        callback: (value) => this.formatYAxisLabel(value)
                    }
                }
            }
        };
    }

    /**
     * 차트 생성
     */
    createChart() {
        const config = {
            type: this.chartType,
            data: this.data,
            options: this.mergeOptions(this.defaultOptions, this.chartOptions)
        };

        this.chart = new Chart(this.ctx, config);
    }

    /**
     * 옵션 병합
     */
    mergeOptions(defaultOpts, customOpts) {
        return this.deepMerge(defaultOpts, customOpts);
    }

    /**
     * 깊은 객체 병합
     */
    deepMerge(target, source) {
        const result = { ...target };
        
        for (const key in source) {
            if (source[key] && typeof source[key] === 'object' && !Array.isArray(source[key])) {
                result[key] = this.deepMerge(result[key] || {}, source[key]);
            } else {
                result[key] = source[key];
            }
        }
        
        return result;
    }

    /**
     * 이벤트 리스너 설정
     */
    setupEventListeners() {
        // 차트 클릭 이벤트
        this.canvas.addEventListener('click', (e) => {
            const points = this.chart.getElementsAtEventForMode(e, 'nearest', { intersect: true }, false);
            if (points.length) {
                this.emit('chartClick', {
                    point: points[0],
                    data: this.chart.data.datasets[points[0].datasetIndex].data[points[0].index],
                    event: e
                });
            }
        });

        // 차트 호버 이벤트
        this.canvas.addEventListener('mousemove', (e) => {
            const points = this.chart.getElementsAtEventForMode(e, 'nearest', { intersect: false }, false);
            this.emit('chartHover', { points, event: e });
        });

        // 테마 변경 감지
        this.on('themeChanged', (theme) => {
            this.updateTheme(theme);
        });
    }

    /**
     * 리사이즈 핸들러 설정
     */
    setupResizeHandler() {
        let resizeTimeout;
        
        const handleResize = () => {
            clearTimeout(resizeTimeout);
            resizeTimeout = setTimeout(() => {
                if (this.chart) {
                    this.chart.resize();
                    this.emit('chartResized');
                }
            }, this.responsiveDelay);
        };

        window.addEventListener('resize', handleResize);
        
        // ResizeObserver 지원 시 사용
        if ('ResizeObserver' in window) {
            const resizeObserver = new ResizeObserver(handleResize);
            resizeObserver.observe(this.element);
        }
    }

    /**
     * 테마 색상 가져오기
     */
    getThemeColors() {
        const isDark = this.theme === 'dark';
        
        return {
            text: isDark ? '#ffffff' : '#333333',
            textMuted: isDark ? '#9ca3af' : '#6b7280',
            background: isDark ? '#1f2937' : '#ffffff',
            border: isDark ? '#374151' : '#e5e7eb',
            gridLines: isDark ? '#374151' : '#f3f4f6',
            tooltipBg: isDark ? '#374151' : '#ffffff',
            primary: '#3b82f6',
            success: '#10b981',
            warning: '#f59e0b',
            danger: '#ef4444',
            profit: '#10b981',
            loss: '#ef4444'
        };
    }

    /**
     * 테마 업데이트
     */
    updateTheme(theme) {
        this.theme = theme;
        this.colors = this.getThemeColors();
        
        if (this.chart) {
            // 차트 옵션 업데이트
            const options = this.chart.options;
            
            // 범례 색상
            options.plugins.legend.labels.color = this.colors.text;
            
            // 툴팁 색상
            options.plugins.tooltip.backgroundColor = this.colors.tooltipBg;
            options.plugins.tooltip.titleColor = this.colors.text;
            options.plugins.tooltip.bodyColor = this.colors.text;
            options.plugins.tooltip.borderColor = this.colors.border;
            
            // 축 색상
            if (options.scales.x) {
                options.scales.x.grid.color = this.colors.gridLines;
                options.scales.x.ticks.color = this.colors.text;
            }
            if (options.scales.y) {
                options.scales.y.grid.color = this.colors.gridLines;
                options.scales.y.ticks.color = this.colors.text;
            }
            
            this.chart.update('none');
            this.emit('themeUpdated', theme);
        }
    }

    /**
     * 데이터 업데이트
     */
    updateData(newData, animate = true) {
        if (!this.chart) return;
        
        this.isUpdating = true;
        
        // 데이터 포인트 제한
        if (this.maxDataPoints > 0) {
            newData = this.limitDataPoints(newData);
        }
        
        this.chart.data = newData;
        this.chart.update(animate ? 'active' : 'none');
        
        this.lastUpdate = Date.now();
        this.isUpdating = false;
        
        this.emit('dataUpdated', newData);
    }

    /**
     * 데이터 포인트 추가
     */
    addDataPoint(datasetIndex, data, label) {
        if (!this.chart || !this.chart.data.datasets[datasetIndex]) return;
        
        const dataset = this.chart.data.datasets[datasetIndex];
        
        // 라벨 추가
        if (label !== undefined) {
            this.chart.data.labels.push(label);
        }
        
        // 데이터 추가
        dataset.data.push(data);
        
        // 최대 포인트 수 제한
        if (this.maxDataPoints > 0) {
            while (this.chart.data.labels.length > this.maxDataPoints) {
                this.chart.data.labels.shift();
            }
            while (dataset.data.length > this.maxDataPoints) {
                dataset.data.shift();
            }
        }
        
        this.chart.update('active');
        this.emit('dataPointAdded', { datasetIndex, data, label });
    }

    /**
     * 데이터 포인트 제한
     */
    limitDataPoints(data) {
        if (!this.maxDataPoints || this.maxDataPoints <= 0) return data;
        
        const limitedData = { ...data };
        
        if (limitedData.labels && limitedData.labels.length > this.maxDataPoints) {
            limitedData.labels = limitedData.labels.slice(-this.maxDataPoints);
        }
        
        limitedData.datasets = limitedData.datasets.map(dataset => ({
            ...dataset,
            data: dataset.data.slice(-this.maxDataPoints)
        }));
        
        return limitedData;
    }

    /**
     * 자동 업데이트 시작
     */
    startAutoUpdate() {
        if (this.updateTimer) {
            clearInterval(this.updateTimer);
        }
        
        this.updateTimer = setInterval(() => {
            this.emit('autoUpdateTick');
        }, this.updateInterval);
        
        this.emit('autoUpdateStarted');
    }

    /**
     * 자동 업데이트 중지
     */
    stopAutoUpdate() {
        if (this.updateTimer) {
            clearInterval(this.updateTimer);
            this.updateTimer = null;
        }
        
        this.emit('autoUpdateStopped');
    }

    /**
     * 툴팁 제목 포맷
     */
    formatTooltipTitle(tooltipItems) {
        if (tooltipItems.length > 0) {
            return tooltipItems[0].label || '';
        }
        return '';
    }

    /**
     * 툴팁 라벨 포맷
     */
    formatTooltipLabel(context) {
        const label = context.dataset.label || '';
        const value = context.parsed.y;
        
        return `${label}: ${this.formatValue(value)}`;
    }

    /**
     * Y축 라벨 포맷
     */
    formatYAxisLabel(value) {
        return this.formatValue(value);
    }

    /**
     * 값 포맷 (상속받는 클래스에서 오버라이드)
     */
    formatValue(value) {
        if (typeof value === 'number') {
            return value.toLocaleString();
        }
        return value;
    }

    /**
     * 차트 다운로드
     */
    downloadChart(filename = 'chart.png') {
        if (!this.chart) return;
        
        const link = document.createElement('a');
        link.download = filename;
        link.href = this.chart.toBase64Image('image/png', 1);
        link.click();
        
        this.emit('chartDownloaded', filename);
    }

    /**
     * 차트 데이터 내보내기
     */
    exportData() {
        if (!this.chart) return null;
        
        return {
            type: this.chartType,
            data: this.chart.data,
            options: this.chart.options,
            timestamp: Date.now()
        };
    }

    /**
     * 차트 상태 가져오기
     */
    getStatus() {
        return {
            isInitialized: this.isInitialized,
            isUpdating: this.isUpdating,
            autoUpdate: !!this.updateTimer,
            lastUpdate: this.lastUpdate,
            dataPointCount: this.chart ? this.chart.data.labels.length : 0,
            theme: this.theme
        };
    }

    /**
     * 정리
     */
    destroy() {
        this.stopAutoUpdate();
        
        if (this.chart) {
            this.chart.destroy();
            this.chart = null;
        }
        
        if (this.canvas) {
            this.canvas.remove();
            this.canvas = null;
        }
        
        this.ctx = null;
        
        super.destroy();
    }
}

export default ChartBase;
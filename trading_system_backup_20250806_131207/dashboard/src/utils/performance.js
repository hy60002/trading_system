/**
 * @fileoverview 성능 모니터링 유틸리티
 * @description 애플리케이션 성능 측정 및 최적화
 */

import { eventBus } from '../core/EventBus.js';

/**
 * 성능 모니터 클래스
 * @class PerformanceMonitor
 */
export class PerformanceMonitor {
    constructor() {
        this.metrics = {
            memory: {
                used: 0,
                total: 0,
                peak: 0,
                history: []
            },
            timing: {
                domContentLoaded: 0,
                loadComplete: 0,
                firstPaint: 0,
                firstContentfulPaint: 0,
                largestContentfulPaint: 0
            },
            resources: {
                totalSize: 0,
                loadTime: 0,
                requests: 0,
                failed: 0
            },
            rendering: {
                fps: 0,
                frameDrops: 0,
                averageFrameTime: 0,
                longTasks: 0
            },
            interactions: {
                totalInputDelay: 0,
                inputCount: 0,
                averageInputDelay: 0
            }
        };

        this.observers = new Map();
        this.intervals = new Map();
        this.isMonitoring = false;
        this.thresholds = this.getPerformanceThresholds();
        
        // 성능 히스토리 (최근 100개 측정값)
        this.historySize = 100;
        this.startTime = Date.now();
    }

    /**
     * 성능 임계값 가져오기
     * @returns {Object} 임계값 설정
     * @private
     */
    getPerformanceThresholds() {
        return {
            memory: {
                warning: 50 * 1024 * 1024, // 50MB
                critical: 100 * 1024 * 1024 // 100MB
            },
            fps: {
                warning: 30,
                critical: 15
            },
            inputDelay: {
                warning: 100, // 100ms
                critical: 300  // 300ms
            },
            longTask: 50 // 50ms
        };
    }

    /**
     * 성능 모니터링 시작
     */
    start() {
        if (this.isMonitoring) return;
        
        console.log('📊 성능 모니터링 시작');
        this.isMonitoring = true;
        
        this.collectInitialMetrics();
        this.setupObservers();
        this.startPeriodicMonitoring();
        
        eventBus.emit('performance:monitoring_started');
    }

    /**
     * 성능 모니터링 중지
     */
    stop() {
        if (!this.isMonitoring) return;
        
        console.log('📊 성능 모니터링 중지');
        this.isMonitoring = false;
        
        this.disconnectObservers();
        this.clearIntervals();
        
        eventBus.emit('performance:monitoring_stopped');
    }

    /**
     * 모니터링 일시 정지
     */
    pause() {
        this.clearIntervals();
        this.disconnectObservers();
    }

    /**
     * 모니터링 재개
     */
    resume() {
        if (this.isMonitoring) {
            this.setupObservers();
            this.startPeriodicMonitoring();
        }
    }

    /**
     * 초기 메트릭 수집
     * @private
     */
    collectInitialMetrics() {
        this.collectNavigationTimings();
        this.collectPaintTimings();
        this.collectResourceTimings();
        this.collectMemoryInfo();
    }

    /**
     * 네비게이션 타이밍 수집
     * @private
     */
    collectNavigationTimings() {
        if (!performance.getEntriesByType) return;
        
        const navigationEntries = performance.getEntriesByType('navigation');
        if (navigationEntries.length > 0) {
            const nav = navigationEntries[0];
            
            this.metrics.timing.domContentLoaded = nav.domContentLoadedEventEnd - nav.navigationStart;
            this.metrics.timing.loadComplete = nav.loadEventEnd - nav.navigationStart;
        }
    }

    /**
     * 페인트 타이밍 수집
     * @private
     */
    collectPaintTimings() {
        if (!performance.getEntriesByType) return;
        
        const paintEntries = performance.getEntriesByType('paint');
        paintEntries.forEach(entry => {
            if (entry.name === 'first-paint') {
                this.metrics.timing.firstPaint = entry.startTime;
            } else if (entry.name === 'first-contentful-paint') {
                this.metrics.timing.firstContentfulPaint = entry.startTime;
            }
        });
    }

    /**
     * 리소스 타이밍 수집
     * @private
     */
    collectResourceTimings() {
        if (!performance.getEntriesByType) return;
        
        const resourceEntries = performance.getEntriesByType('resource');
        let totalSize = 0;
        let totalTime = 0;
        let failedCount = 0;
        
        resourceEntries.forEach(entry => {
            totalSize += entry.transferSize || 0;
            totalTime += entry.responseEnd - entry.requestStart;
            
            // HTTP 오류 상태 확인 (추정)
            if (entry.responseEnd - entry.responseStart === 0) {
                failedCount++;
            }
        });
        
        this.metrics.resources = {
            totalSize,
            loadTime: totalTime,
            requests: resourceEntries.length,
            failed: failedCount
        };
    }

    /**
     * 메모리 정보 수집
     * @private
     */
    collectMemoryInfo() {
        if (!performance.memory) return;
        
        const memory = performance.memory;
        this.metrics.memory.used = memory.usedJSHeapSize;
        this.metrics.memory.total = memory.totalJSHeapSize;
        this.metrics.memory.peak = Math.max(this.metrics.memory.peak, memory.usedJSHeapSize);
        
        // 메모리 히스토리 업데이트
        this.metrics.memory.history.push({
            timestamp: Date.now(),
            used: memory.usedJSHeapSize,
            total: memory.totalJSHeapSize
        });
        
        // 히스토리 크기 제한
        if (this.metrics.memory.history.length > this.historySize) {
            this.metrics.memory.history.shift();
        }
        
        // 메모리 경고 확인
        this.checkMemoryThresholds();
    }

    /**
     * 옵저버 설정
     * @private
     */
    setupObservers() {
        this.setupPerformanceObserver();
        this.setupIntersectionObserver();
        this.setupMutationObserver();
        this.setupLongTaskObserver();
    }

    /**
     * Performance Observer 설정
     * @private
     */
    setupPerformanceObserver() {
        if (!window.PerformanceObserver) return;
        
        try {
            // LCP 측정
            const lcpObserver = new PerformanceObserver((list) => {
                const entries = list.getEntries();
                const lastEntry = entries[entries.length - 1];
                this.metrics.timing.largestContentfulPaint = lastEntry.startTime;
            });
            lcpObserver.observe({ entryTypes: ['largest-contentful-paint'] });
            this.observers.set('lcp', lcpObserver);

            // 입력 지연 측정
            const inputObserver = new PerformanceObserver((list) => {
                list.getEntries().forEach(entry => {
                    if (entry.processingStart > entry.startTime) {
                        const inputDelay = entry.processingStart - entry.startTime;
                        this.recordInputDelay(inputDelay);
                    }
                });
            });
            inputObserver.observe({ entryTypes: ['first-input'] });
            this.observers.set('input', inputObserver);

        } catch (error) {
            console.warn('Performance Observer 설정 실패:', error);
        }
    }

    /**
     * Long Task Observer 설정
     * @private
     */
    setupLongTaskObserver() {
        if (!window.PerformanceObserver) return;
        
        try {
            const longTaskObserver = new PerformanceObserver((list) => {
                list.getEntries().forEach(entry => {
                    if (entry.duration > this.thresholds.longTask) {
                        this.metrics.rendering.longTasks++;
                        this.handleLongTask(entry);
                    }
                });
            });
            longTaskObserver.observe({ entryTypes: ['longtask'] });
            this.observers.set('longtask', longTaskObserver);

        } catch (error) {
            console.warn('Long Task Observer 설정 실패:', error);
        }
    }

    /**
     * Intersection Observer 설정 (가시성 최적화용)
     * @private
     */
    setupIntersectionObserver() {
        // 컴포넌트 가시성 추적을 위한 옵저버
        const visibilityObserver = new IntersectionObserver((entries) => {
            entries.forEach(entry => {
                const component = entry.target.dataset.component;
                if (component) {
                    eventBus.emit('performance:visibility_change', {
                        component,
                        visible: entry.isIntersecting,
                        ratio: entry.intersectionRatio
                    });
                }
            });
        }, {
            threshold: [0, 0.1, 0.5, 1.0]
        });
        
        this.observers.set('visibility', visibilityObserver);
        
        // 모든 컴포넌트 관찰 시작
        document.querySelectorAll('[data-component]').forEach(element => {
            visibilityObserver.observe(element);
        });
    }

    /**
     * Mutation Observer 설정 (DOM 변경 추적)
     * @private
     */
    setupMutationObserver() {
        const mutationObserver = new MutationObserver((mutations) => {
            let significantChanges = 0;
            
            mutations.forEach(mutation => {
                if (mutation.type === 'childList' && mutation.addedNodes.length > 0) {
                    significantChanges++;
                }
            });
            
            if (significantChanges > 10) {
                eventBus.emit('performance:dom_thrashing', {
                    changes: significantChanges,
                    timestamp: Date.now()
                });
            }
        });
        
        mutationObserver.observe(document.body, {
            childList: true,
            subtree: true,
            attributes: false
        });
        
        this.observers.set('mutation', mutationObserver);
    }

    /**
     * 주기적 모니터링 시작
     * @private
     */
    startPeriodicMonitoring() {
        // FPS 측정
        this.startFPSMonitoring();
        
        // 메모리 모니터링 (5초마다)
        const memoryInterval = setInterval(() => {
            this.collectMemoryInfo();
        }, 5000);
        this.intervals.set('memory', memoryInterval);
        
        // 전체 성능 보고서 (30초마다)
        const reportInterval = setInterval(() => {
            this.generatePerformanceReport();
        }, 30000);
        this.intervals.set('report', reportInterval);
    }

    /**
     * FPS 모니터링 시작
     * @private
     */
    startFPSMonitoring() {
        let frames = 0;
        let lastTime = performance.now();
        const frameHistory = [];
        
        const measureFPS = (currentTime) => {
            frames++;
            const delta = currentTime - lastTime;
            
            if (delta >= 1000) { // 1초마다 FPS 계산
                const fps = Math.round((frames * 1000) / delta);
                this.metrics.rendering.fps = fps;
                this.metrics.rendering.averageFrameTime = delta / frames;
                
                // FPS 히스토리 업데이트
                frameHistory.push({ timestamp: currentTime, fps });
                if (frameHistory.length > 60) { // 1분간의 데이터 유지
                    frameHistory.shift();
                }
                
                // FPS 임계값 확인
                this.checkFPSThresholds(fps);
                
                frames = 0;
                lastTime = currentTime;
            }
            
            if (this.isMonitoring) {
                requestAnimationFrame(measureFPS);
            }
        };
        
        requestAnimationFrame(measureFPS);
    }

    /**
     * 입력 지연 기록
     * @param {number} delay - 지연 시간
     * @private
     */
    recordInputDelay(delay) {
        this.metrics.interactions.totalInputDelay += delay;
        this.metrics.interactions.inputCount++;
        this.metrics.interactions.averageInputDelay = 
            this.metrics.interactions.totalInputDelay / this.metrics.interactions.inputCount;
        
        // 입력 지연 임계값 확인
        this.checkInputDelayThresholds(delay);
    }

    /**
     * Long Task 처리
     * @param {PerformanceEntry} entry - Long Task 엔트리
     * @private
     */
    handleLongTask(entry) {
        eventBus.emit('performance:long_task', {
            duration: entry.duration,
            startTime: entry.startTime,
            name: entry.name,
            attribution: entry.attribution
        });
        
        console.warn(`⚠️ Long Task 감지: ${entry.duration.toFixed(2)}ms`);
    }

    /**
     * 메모리 임계값 확인
     * @private
     */
    checkMemoryThresholds() {
        const { used } = this.metrics.memory;
        const { warning, critical } = this.thresholds.memory;
        
        if (used > critical) {
            eventBus.emit('performance:warning', {
                type: 'memory',
                level: 'critical',
                value: used,
                threshold: critical
            });
        } else if (used > warning) {
            eventBus.emit('performance:warning', {
                type: 'memory',
                level: 'warning',
                value: used,
                threshold: warning
            });
        }
    }

    /**
     * FPS 임계값 확인
     * @param {number} fps - 현재 FPS
     * @private
     */
    checkFPSThresholds(fps) {
        const { warning, critical } = this.thresholds.fps;
        
        if (fps < critical) {
            eventBus.emit('performance:warning', {
                type: 'render',
                level: 'critical',
                value: fps,
                threshold: critical
            });
        } else if (fps < warning) {
            eventBus.emit('performance:warning', {
                type: 'render',
                level: 'warning',
                value: fps,
                threshold: warning
            });
        }
    }

    /**
     * 입력 지연 임계값 확인
     * @param {number} delay - 입력 지연
     * @private
     */
    checkInputDelayThresholds(delay) {
        const { warning, critical } = this.thresholds.inputDelay;
        
        if (delay > critical) {
            eventBus.emit('performance:warning', {
                type: 'interaction',
                level: 'critical',
                value: delay,
                threshold: critical
            });
        } else if (delay > warning) {
            eventBus.emit('performance:warning', {
                type: 'interaction',
                level: 'warning',
                value: delay,
                threshold: warning
            });
        }
    }

    /**
     * 성능 보고서 생성
     * @private
     */
    generatePerformanceReport() {
        const report = {
            timestamp: Date.now(),
            uptime: Date.now() - this.startTime,
            metrics: this.getMetrics(),
            recommendations: this.generateRecommendations()
        };
        
        eventBus.emit('performance:report', report);
        
        if (process.env.NODE_ENV === 'development') {
            console.log('📊 성능 보고서:', report);
        }
    }

    /**
     * 최적화 권장사항 생성
     * @returns {Array} 권장사항 목록
     * @private
     */
    generateRecommendations() {
        const recommendations = [];
        const metrics = this.metrics;
        
        // 메모리 권장사항
        if (metrics.memory.used > this.thresholds.memory.warning) {
            recommendations.push({
                type: 'memory',
                priority: 'high',
                message: '메모리 사용량이 높습니다. 캐시 정리를 고려하세요.',
                action: 'clear_cache'
            });
        }
        
        // FPS 권장사항
        if (metrics.rendering.fps < this.thresholds.fps.warning) {
            recommendations.push({
                type: 'rendering',
                priority: 'medium',
                message: 'FPS가 낮습니다. 애니메이션을 줄이거나 최적화하세요.',
                action: 'optimize_rendering'
            });
        }
        
        // Long Task 권장사항
        if (metrics.rendering.longTasks > 5) {
            recommendations.push({
                type: 'performance',
                priority: 'high',
                message: 'Long Task가 자주 발생합니다. 작업을 분할하세요.',
                action: 'split_tasks'
            });
        }
        
        // 입력 지연 권장사항
        if (metrics.interactions.averageInputDelay > this.thresholds.inputDelay.warning) {
            recommendations.push({
                type: 'interaction',
                priority: 'medium',
                message: '입력 지연이 높습니다. 이벤트 핸들러를 최적화하세요.',
                action: 'optimize_handlers'
            });
        }
        
        return recommendations;
    }

    /**
     * 옵저버 연결 해제
     * @private
     */
    disconnectObservers() {
        this.observers.forEach(observer => {
            if (observer && typeof observer.disconnect === 'function') {
                observer.disconnect();
            }
        });
        this.observers.clear();
    }

    /**
     * 인터벌 정리
     * @private
     */
    clearIntervals() {
        this.intervals.forEach(intervalId => {
            clearInterval(intervalId);
        });
        this.intervals.clear();
    }

    /**
     * 성능 메트릭 가져오기
     * @returns {Object} 성능 메트릭
     */
    getMetrics() {
        return {
            ...this.metrics,
            uptime: Date.now() - this.startTime,
            timestamp: Date.now()
        };
    }

    /**
     * 성능 점수 계산
     * @returns {Object} 성능 점수
     */
    calculatePerformanceScore() {
        const metrics = this.metrics;
        let score = 100;
        const details = {};
        
        // FPS 점수 (30점 만점)
        const fpsScore = Math.min(30, (metrics.rendering.fps / 60) * 30);
        score = Math.min(score, score - (30 - fpsScore));
        details.fps = fpsScore;
        
        // 메모리 점수 (25점 만점)
        const memoryRatio = metrics.memory.used / metrics.memory.total;
        const memoryScore = Math.max(0, 25 - (memoryRatio * 25));
        score = Math.min(score, score - (25 - memoryScore));
        details.memory = memoryScore;
        
        // 로딩 성능 점수 (25점 만점)
        const loadScore = Math.max(0, 25 - (metrics.timing.loadComplete / 100));
        score = Math.min(score, score - (25 - loadScore));
        details.loading = loadScore;
        
        // 상호작용 점수 (20점 만점)
        const interactionScore = Math.max(0, 20 - (metrics.interactions.averageInputDelay / 10));
        score = Math.min(score, score - (20 - interactionScore));
        details.interaction = interactionScore;
        
        return {
            total: Math.round(score),
            details,
            grade: this.getPerformanceGrade(score)
        };
    }

    /**
     * 성능 등급 가져오기
     * @param {number} score - 성능 점수
     * @returns {string} 성능 등급
     * @private
     */
    getPerformanceGrade(score) {
        if (score >= 90) return 'A';
        if (score >= 80) return 'B';
        if (score >= 70) return 'C';
        if (score >= 60) return 'D';
        return 'F';
    }

    /**
     * 성능 측정 마크 추가
     * @param {string} name - 마크 이름
     */
    mark(name) {
        if (performance.mark) {
            performance.mark(name);
        }
    }

    /**
     * 성능 측정 완료
     * @param {string} name - 측정 이름
     * @param {string} startMark - 시작 마크
     * @param {string} endMark - 종료 마크
     */
    measure(name, startMark, endMark) {
        if (performance.measure) {
            performance.measure(name, startMark, endMark);
        }
    }

    /**
     * 커스텀 메트릭 기록
     * @param {string} name - 메트릭 이름
     * @param {number} value - 값
     * @param {string} [unit] - 단위
     */
    recordCustomMetric(name, value, unit = 'ms') {
        if (!this.metrics.custom) {
            this.metrics.custom = {};
        }
        
        this.metrics.custom[name] = {
            value,
            unit,
            timestamp: Date.now()
        };
        
        eventBus.emit('performance:custom_metric', {
            name,
            value,
            unit
        });
    }

    /**
     * 성능 데이터 내보내기
     * @returns {Object} 내보낼 데이터
     */
    exportData() {
        return {
            metrics: this.getMetrics(),
            score: this.calculatePerformanceScore(),
            recommendations: this.generateRecommendations(),
            startTime: this.startTime,
            exportTime: Date.now()
        };
    }
}

/**
 * 성능 측정 데코레이터
 * @param {string} name - 측정 이름
 * @returns {Function} 데코레이터 함수
 */
export function measurePerformance(name) {
    return function(target, propertyKey, descriptor) {
        const originalMethod = descriptor.value;
        
        descriptor.value = async function(...args) {
            const startTime = performance.now();
            
            try {
                const result = await originalMethod.apply(this, args);
                const endTime = performance.now();
                const duration = endTime - startTime;
                
                eventBus.emit('performance:method_measured', {
                    name: `${target.constructor.name}.${propertyKey}`,
                    duration,
                    success: true
                });
                
                return result;
            } catch (error) {
                const endTime = performance.now();
                const duration = endTime - startTime;
                
                eventBus.emit('performance:method_measured', {
                    name: `${target.constructor.name}.${propertyKey}`,
                    duration,
                    success: false,
                    error: error.message
                });
                
                throw error;
            }
        };
        
        return descriptor;
    };
}

/**
 * 함수 실행 시간 측정
 * @param {Function} fn - 측정할 함수
 * @param {string} name - 측정 이름
 * @returns {Function} 래핑된 함수
 */
export function timeFunction(fn, name) {
    return async function(...args) {
        const startTime = performance.now();
        
        try {
            const result = await fn.apply(this, args);
            const duration = performance.now() - startTime;
            
            console.log(`⏱️ ${name}: ${duration.toFixed(2)}ms`);
            
            return result;
        } catch (error) {
            const duration = performance.now() - startTime;
            console.log(`⏱️ ${name} (실패): ${duration.toFixed(2)}ms`);
            throw error;
        }
    };
}

// 전역 성능 모니터 인스턴스
export const performanceMonitor = new PerformanceMonitor();

// 개발 모드에서 전역 접근 가능하게 설정
if (typeof window !== 'undefined' && process.env.NODE_ENV === 'development') {
    window.__PERFORMANCE_MONITOR__ = performanceMonitor;
}
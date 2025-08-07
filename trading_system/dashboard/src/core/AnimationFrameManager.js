/**
 * @fileoverview requestAnimationFrame 기반 애니메이션 매니저
 * @description 고성능 차트 업데이트 및 애니메이션 시스템
 */

/**
 * 애니메이션 프레임 매니저
 * @class AnimationFrameManager
 */
export class AnimationFrameManager {
    constructor() {
        this.tasks = new Map();
        this.frameCallbacks = new Map();
        this.currentFrameId = null;
        this.isRunning = false;
        this.lastFrameTime = 0;
        this.frameCount = 0;
        this.fps = 0;
        this.targetFPS = 60;
        this.frameInterval = 1000 / this.targetFPS;
        
        // 우선순위 큐
        this.highPriorityTasks = [];
        this.normalPriorityTasks = [];
        this.lowPriorityTasks = [];
        
        // 성능 모니터링
        this.performanceMetrics = {
            averageFrameTime: 0,
            maxFrameTime: 0,
            droppedFrames: 0,
            totalFrames: 0,
            busyRatio: 0
        };
        
        // 적응형 품질 제어
        this.qualityLevel = 'high'; // 'high', 'medium', 'low'
        this.adaptiveThresholds = {
            high: 16.67, // 60fps
            medium: 33.33, // 30fps
            low: 50 // 20fps
        };
        
        // 디바운싱 및 스로틀링
        this.throttledTasks = new Map();
        this.debouncedTasks = new Map();
        
        this.initializePerformanceMonitoring();
    }

    /**
     * 성능 모니터링 초기화
     * @private
     */
    initializePerformanceMonitoring() {
        // FPS 계산을 위한 인터벌
        setInterval(() => {
            this.fps = this.frameCount;
            this.frameCount = 0;
            this.adjustQualityLevel();
        }, 1000);
    }

    /**
     * 품질 레벨 조정
     * @private
     */
    adjustQualityLevel() {
        const avgFrameTime = this.performanceMetrics.averageFrameTime;
        
        if (avgFrameTime > this.adaptiveThresholds.low) {
            this.qualityLevel = 'low';
        } else if (avgFrameTime > this.adaptiveThresholds.medium) {
            this.qualityLevel = 'medium';
        } else {
            this.qualityLevel = 'high';
        }
        
        this.emitQualityChange();
    }

    /**
     * 품질 변경 이벤트 발생
     * @private
     */
    emitQualityChange() {
        const event = new CustomEvent('animation-quality-change', {
            detail: {
                level: this.qualityLevel,
                fps: this.fps,
                averageFrameTime: this.performanceMetrics.averageFrameTime
            }
        });
        
        if (typeof window !== 'undefined') {
            window.dispatchEvent(event);
        }
    }

    /**
     * 애니메이션 작업 등록
     * @param {string} taskId - 작업 ID
     * @param {Function} callback - 콜백 함수
     * @param {Object} options - 옵션
     */
    registerTask(taskId, callback, options = {}) {
        const task = {
            id: taskId,
            callback,
            priority: options.priority || 'normal',
            interval: options.interval || 1, // 프레임 간격
            lastExecution: 0,
            executionCount: 0,
            maxExecutions: options.maxExecutions || Infinity,
            context: options.context || null,
            enabled: true,
            onComplete: options.onComplete || null,
            onError: options.onError || null
        };

        this.tasks.set(taskId, task);
        
        // 우선순위별 큐에 추가
        this.addToQueue(task);
        
        // 첫 번째 작업이면 애니메이션 시작
        if (this.tasks.size === 1 && !this.isRunning) {
            this.start();
        }
    }

    /**
     * 우선순위 큐에 작업 추가
     * @param {Object} task - 작업 객체
     * @private
     */
    addToQueue(task) {
        switch (task.priority) {
            case 'high':
                this.highPriorityTasks.push(task);
                break;
            case 'low':
                this.lowPriorityTasks.push(task);
                break;
            default:
                this.normalPriorityTasks.push(task);
        }
    }

    /**
     * 작업 제거
     * @param {string} taskId - 작업 ID
     */
    unregisterTask(taskId) {
        const task = this.tasks.get(taskId);
        if (!task) return;

        // 큐에서 제거
        this.removeFromQueue(task);
        
        // 맵에서 제거
        this.tasks.delete(taskId);
        
        // 작업이 없으면 애니메이션 중지
        if (this.tasks.size === 0 && this.isRunning) {
            this.stop();
        }
    }

    /**
     * 우선순위 큐에서 작업 제거
     * @param {Object} task - 작업 객체
     * @private
     */
    removeFromQueue(task) {
        const queues = [
            this.highPriorityTasks,
            this.normalPriorityTasks,
            this.lowPriorityTasks
        ];

        queues.forEach(queue => {
            const index = queue.findIndex(t => t.id === task.id);
            if (index !== -1) {
                queue.splice(index, 1);
            }
        });
    }

    /**
     * 작업 활성화/비활성화
     * @param {string} taskId - 작업 ID
     * @param {boolean} enabled - 활성화 여부
     */
    setTaskEnabled(taskId, enabled) {
        const task = this.tasks.get(taskId);
        if (task) {
            task.enabled = enabled;
        }
    }

    /**
     * 스로틀링된 작업 등록
     * @param {string} taskId - 작업 ID
     * @param {Function} callback - 콜백 함수
     * @param {number} interval - 스로틀링 간격 (ms)
     * @param {Object} options - 추가 옵션
     */
    registerThrottledTask(taskId, callback, interval, options = {}) {
        const throttledCallback = this.createThrottledCallback(callback, interval);
        
        this.registerTask(taskId, throttledCallback, {
            ...options,
            interval: Math.max(1, Math.floor(interval / this.frameInterval))
        });
        
        this.throttledTasks.set(taskId, {
            originalCallback: callback,
            throttledCallback,
            interval
        });
    }

    /**
     * 디바운싱된 작업 등록
     * @param {string} taskId - 작업 ID
     * @param {Function} callback - 콜백 함수
     * @param {number} delay - 디바운싱 지연 시간 (ms)
     * @param {Object} options - 추가 옵션
     */
    registerDebouncedTask(taskId, callback, delay, options = {}) {
        const debouncedCallback = this.createDebouncedCallback(callback, delay);
        
        this.registerTask(taskId, debouncedCallback, {
            ...options,
            interval: Math.max(1, Math.floor(delay / this.frameInterval))
        });
        
        this.debouncedTasks.set(taskId, {
            originalCallback: callback,
            debouncedCallback,
            delay
        });
    }

    /**
     * 스로틀링 콜백 생성
     * @param {Function} func - 원본 함수
     * @param {number} interval - 스로틀링 간격
     * @returns {Function} 스로틀링된 함수
     * @private
     */
    createThrottledCallback(func, interval) {
        let lastExecution = 0;
        
        return (...args) => {
            const now = performance.now();
            
            if (now - lastExecution >= interval) {
                lastExecution = now;
                return func.apply(this, args);
            }
        };
    }

    /**
     * 디바운싱 콜백 생성
     * @param {Function} func - 원본 함수
     * @param {number} delay - 디바운싱 지연 시간
     * @returns {Function} 디바운싱된 함수
     * @private
     */
    createDebouncedCallback(func, delay) {
        let timeoutId = null;
        
        return (...args) => {
            clearTimeout(timeoutId);
            timeoutId = setTimeout(() => {
                func.apply(this, args);
            }, delay);
        };
    }

    /**
     * 차트 업데이트 작업 등록
     * @param {string} chartId - 차트 ID
     * @param {Function} updateCallback - 업데이트 콜백
     * @param {Object} options - 옵션
     */
    registerChartUpdate(chartId, updateCallback, options = {}) {
        const taskId = `chart_${chartId}`;
        const optimizedCallback = this.createOptimizedChartCallback(
            updateCallback, 
            options
        );

        this.registerTask(taskId, optimizedCallback, {
            priority: options.priority || 'high',
            interval: this.getIntervalForQuality(),
            ...options
        });
    }

    /**
     * 최적화된 차트 콜백 생성
     * @param {Function} updateCallback - 업데이트 콜백
     * @param {Object} options - 옵션
     * @returns {Function} 최적화된 콜백
     * @private
     */
    createOptimizedChartCallback(updateCallback, options) {
        return (frameTime, deltaTime) => {
            // 품질 레벨에 따른 업데이트 스킵
            if (this.shouldSkipUpdate(options)) {
                return;
            }

            try {
                // 성능 측정 시작
                const startTime = performance.now();
                
                // 차트 업데이트 실행
                updateCallback(frameTime, deltaTime, this.qualityLevel);
                
                // 성능 측정 종료
                const executionTime = performance.now() - startTime;
                this.updateTaskPerformance(executionTime);
                
            } catch (error) {
                console.error('Chart update error:', error);
                
                if (options.onError) {
                    options.onError(error);
                }
            }
        };
    }

    /**
     * 업데이트 스킵 여부 결정
     * @param {Object} options - 작업 옵션
     * @returns {boolean} 스킵 여부
     * @private
     */
    shouldSkipUpdate(options) {
        // 낮은 품질에서는 일부 업데이트 스킵
        if (this.qualityLevel === 'low' && options.skipOnLowQuality) {
            return Math.random() > 0.5;
        }
        
        // 중간 품질에서는 가끔 스킵
        if (this.qualityLevel === 'medium' && options.skipOnMediumQuality) {
            return Math.random() > 0.8;
        }
        
        return false;
    }

    /**
     * 품질에 따른 인터벌 반환
     * @returns {number} 프레임 인터벌
     * @private
     */
    getIntervalForQuality() {
        switch (this.qualityLevel) {
            case 'low':
                return 3; // 20fps
            case 'medium':
                return 2; // 30fps
            default:
                return 1; // 60fps
        }
    }

    /**
     * 애니메이션 시작
     */
    start() {
        if (this.isRunning) return;
        
        this.isRunning = true;
        this.lastFrameTime = performance.now();
        this.animate();
    }

    /**
     * 애니메이션 중지
     */
    stop() {
        if (!this.isRunning) return;
        
        this.isRunning = false;
        
        if (this.currentFrameId) {
            cancelAnimationFrame(this.currentFrameId);
            this.currentFrameId = null;
        }
    }

    /**
     * 애니메이션 일시 정지/재개
     * @param {boolean} paused - 일시 정지 여부
     */
    setPaused(paused) {
        if (paused && this.isRunning) {
            this.stop();
        } else if (!paused && !this.isRunning && this.tasks.size > 0) {
            this.start();
        }
    }

    /**
     * 메인 애니메이션 루프
     * @private
     */
    animate() {
        if (!this.isRunning) return;

        const currentTime = performance.now();
        const deltaTime = currentTime - this.lastFrameTime;
        
        // 프레임 레이트 제한
        if (deltaTime >= this.frameInterval) {
            this.executeFrameTasks(currentTime, deltaTime);
            
            // 성능 메트릭 업데이트
            this.updatePerformanceMetrics(deltaTime);
            
            this.lastFrameTime = currentTime;
            this.frameCount++;
        }

        // 다음 프레임 스케줄링
        this.currentFrameId = requestAnimationFrame(() => this.animate());
    }

    /**
     * 프레임 작업 실행
     * @param {number} currentTime - 현재 시간
     * @param {number} deltaTime - 델타 시간
     * @private
     */
    executeFrameTasks(currentTime, deltaTime) {
        const frameStartTime = performance.now();
        const maxFrameTime = this.frameInterval * 0.8; // 프레임 시간의 80%까지만 사용
        
        // 우선순위 순서로 작업 실행
        const taskQueues = [
            this.highPriorityTasks,
            this.normalPriorityTasks,
            this.lowPriorityTasks
        ];

        for (const queue of taskQueues) {
            for (const task of queue) {
                // 프레임 시간 초과 체크
                if (performance.now() - frameStartTime > maxFrameTime) {
                    this.performanceMetrics.droppedFrames++;
                    break;
                }

                // 작업 실행 조건 체크
                if (!this.shouldExecuteTask(task, currentTime)) {
                    continue;
                }

                this.executeTask(task, currentTime, deltaTime);
            }
        }
    }

    /**
     * 작업 실행 조건 확인
     * @param {Object} task - 작업 객체
     * @param {number} currentTime - 현재 시간
     * @returns {boolean} 실행 여부
     * @private
     */
    shouldExecuteTask(task, currentTime) {
        if (!task.enabled) return false;
        if (task.executionCount >= task.maxExecutions) return false;
        
        const framesSinceLastExecution = 
            Math.floor((currentTime - task.lastExecution) / this.frameInterval);
        
        return framesSinceLastExecution >= task.interval;
    }

    /**
     * 작업 실행
     * @param {Object} task - 작업 객체
     * @param {number} currentTime - 현재 시간
     * @param {number} deltaTime - 델타 시간
     * @private
     */
    executeTask(task, currentTime, deltaTime) {
        try {
            task.callback(currentTime, deltaTime);
            task.lastExecution = currentTime;
            task.executionCount++;
            
            // 최대 실행 횟수 도달 시 완료 처리
            if (task.executionCount >= task.maxExecutions && task.onComplete) {
                task.onComplete();
                this.unregisterTask(task.id);
            }
            
        } catch (error) {
            console.error(`Animation task error (${task.id}):`, error);
            
            if (task.onError) {
                task.onError(error);
            } else {
                // 오류 발생 시 작업 제거
                this.unregisterTask(task.id);
            }
        }
    }

    /**
     * 성능 메트릭 업데이트
     * @param {number} frameTime - 프레임 시간
     * @private
     */
    updatePerformanceMetrics(frameTime) {
        this.performanceMetrics.totalFrames++;
        
        // 평균 프레임 시간
        this.performanceMetrics.averageFrameTime = 
            (this.performanceMetrics.averageFrameTime * 
             (this.performanceMetrics.totalFrames - 1) + frameTime) / 
            this.performanceMetrics.totalFrames;
        
        // 최대 프레임 시간
        this.performanceMetrics.maxFrameTime = 
            Math.max(this.performanceMetrics.maxFrameTime, frameTime);
        
        // 바쁨 비율 계산
        const busyTime = Math.min(frameTime, this.frameInterval);
        this.performanceMetrics.busyRatio = busyTime / this.frameInterval;
    }

    /**
     * 작업 성능 업데이트
     * @param {number} executionTime - 실행 시간
     * @private
     */
    updateTaskPerformance(executionTime) {
        // 작업 실행 시간이 프레임 예산을 초과하는 경우 경고
        if (executionTime > this.frameInterval * 0.5) {
            console.warn(`Long running animation task detected: ${executionTime.toFixed(2)}ms`);
        }
    }

    /**
     * 일회성 애니메이션 등록
     * @param {Function} callback - 콜백 함수
     * @param {Object} options - 옵션
     * @returns {string} 작업 ID
     */
    requestAnimationFrame(callback, options = {}) {
        const taskId = `once_${Date.now()}_${Math.random()}`;
        
        this.registerTask(taskId, callback, {
            ...options,
            maxExecutions: 1,
            priority: options.priority || 'high'
        });
        
        return taskId;
    }

    /**
     * 다음 프레임에서 실행
     * @param {Function} callback - 콜백 함수
     * @returns {Promise} Promise 객체
     */
    nextFrame(callback) {
        return new Promise((resolve) => {
            this.requestAnimationFrame((time, delta) => {
                if (callback) callback(time, delta);
                resolve({ time, delta });
            });
        });
    }

    /**
     * 여러 프레임에 걸친 애니메이션
     * @param {Function} callback - 콜백 함수 (progress, time, delta)
     * @param {number} duration - 지속 시간 (ms)
     * @param {Object} options - 옵션
     * @returns {Promise} Promise 객체
     */
    animate(callback, duration, options = {}) {
        const startTime = performance.now();
        const easing = options.easing || this.easeInOutCubic;
        
        return new Promise((resolve, reject) => {
            const taskId = `animation_${Date.now()}_${Math.random()}`;
            
            const animationCallback = (currentTime) => {
                const elapsed = currentTime - startTime;
                const progress = Math.min(elapsed / duration, 1);
                const easedProgress = easing(progress);
                
                try {
                    callback(easedProgress, currentTime, elapsed);
                    
                    if (progress >= 1) {
                        this.unregisterTask(taskId);
                        resolve(currentTime);
                    }
                } catch (error) {
                    this.unregisterTask(taskId);
                    reject(error);
                }
            };
            
            this.registerTask(taskId, animationCallback, {
                priority: options.priority || 'normal',
                onComplete: () => resolve(performance.now()),
                onError: reject
            });
        });
    }

    /**
     * Cubic ease-in-out 이징 함수
     * @param {number} t - 진행도 (0-1)
     * @returns {number} 이징된 값
     * @private
     */
    easeInOutCubic(t) {
        return t < 0.5 ? 4 * t * t * t : (t - 1) * (2 * t - 2) * (2 * t - 2) + 1;
    }

    /**
     * 성능 메트릭 가져오기
     * @returns {Object} 성능 메트릭
     */
    getPerformanceMetrics() {
        return {
            ...this.performanceMetrics,
            fps: this.fps,
            qualityLevel: this.qualityLevel,
            activeTasks: this.tasks.size,
            isRunning: this.isRunning,
            frameInterval: this.frameInterval
        };
    }

    /**
     * 작업 상태 가져오기
     * @returns {Object} 작업 상태
     */
    getTaskStatus() {
        return {
            total: this.tasks.size,
            highPriority: this.highPriorityTasks.length,
            normalPriority: this.normalPriorityTasks.length,
            lowPriority: this.lowPriorityTasks.length,
            throttled: this.throttledTasks.size,
            debounced: this.debouncedTasks.size
        };
    }

    /**
     * 메트릭 리셋
     */
    resetMetrics() {
        this.performanceMetrics = {
            averageFrameTime: 0,
            maxFrameTime: 0,
            droppedFrames: 0,
            totalFrames: 0,
            busyRatio: 0
        };
        this.frameCount = 0;
    }

    /**
     * 모든 작업 제거
     */
    clear() {
        this.tasks.clear();
        this.highPriorityTasks.length = 0;
        this.normalPriorityTasks.length = 0;
        this.lowPriorityTasks.length = 0;
        this.throttledTasks.clear();
        this.debouncedTasks.clear();
        
        if (this.isRunning) {
            this.stop();
        }
    }
}

// 전역 애니메이션 프레임 매니저 인스턴스
export const animationFrameManager = new AnimationFrameManager();

// 편의 함수들
export const requestAnimationTask = (callback, options) =>
    animationFrameManager.requestAnimationFrame(callback, options);

export const registerChartAnimation = (chartId, callback, options) =>
    animationFrameManager.registerChartUpdate(chartId, callback, options);

export const animateValue = (callback, duration, options) =>
    animationFrameManager.animate(callback, duration, options);

// 개발 모드에서 전역 접근 가능
if (typeof window !== 'undefined' && process.env.NODE_ENV === 'development') {
    window.__TRADING_DASHBOARD_ANIMATION__ = animationFrameManager;
}
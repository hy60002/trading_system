/**
 * @fileoverview 배치 업데이트 매니저
 * @description DOM 업데이트를 효율적으로 배치 처리하는 시스템
 */

/**
 * 배치 업데이트 매니저
 * @class BatchUpdateManager
 */
export class BatchUpdateManager {
    constructor() {
        this.updateQueue = [];
        this.isFlushPending = false;
        this.isProcessing = false;
        this.priorityQueue = new Map();
        this.deferredQueue = [];
        
        // 성능 최적화를 위한 설정
        this.maxBatchSize = 100;
        this.maxProcessingTime = 16; // 60fps를 위한 16ms 제한
        this.debounceTime = 5;
        
        // 메트릭
        this.metrics = {
            totalBatches: 0,
            totalUpdates: 0,
            avgBatchSize: 0,
            avgProcessingTime: 0,
            droppedUpdates: 0
        };
        
        // 성능 모니터링
        this.performanceObserver = null;
        this.initPerformanceMonitoring();
    }

    /**
     * 업데이트 추가 (우선순위 기반)
     * @param {Function} updateFn - 업데이트 함수
     * @param {string} priority - 우선순위 ('high', 'normal', 'low')
     * @param {Object} options - 추가 옵션
     */
    enqueueUpdate(updateFn, priority = 'normal', options = {}) {
        const update = {
            fn: updateFn,
            priority,
            timestamp: performance.now(),
            id: options.id || Math.random().toString(36).substr(2, 9),
            component: options.component || null,
            type: options.type || 'generic',
            retryCount: 0,
            maxRetries: options.maxRetries || 3
        };

        // 중복 업데이트 제거
        if (options.deduplicate && this.hasDuplicateUpdate(update)) {
            return false;
        }

        // 우선순위별 큐에 추가
        if (!this.priorityQueue.has(priority)) {
            this.priorityQueue.set(priority, []);
        }
        this.priorityQueue.get(priority).push(update);

        // 스케줄링
        this.scheduleFlush();
        return true;
    }

    /**
     * 지연 업데이트 추가
     * @param {Function} updateFn - 업데이트 함수
     * @param {number} delay - 지연 시간(ms)
     * @param {Object} options - 추가 옵션
     */
    enqueueDeferredUpdate(updateFn, delay, options = {}) {
        const deferredUpdate = {
            fn: updateFn,
            executeAt: performance.now() + delay,
            options
        };

        this.deferredQueue.push(deferredUpdate);
        this.deferredQueue.sort((a, b) => a.executeAt - b.executeAt);
        
        // 지연 업데이트 처리 스케줄링
        this.scheduleDeferredFlush();
    }

    /**
     * 중복 업데이트 검사
     * @param {Object} update - 업데이트 객체
     * @returns {boolean} 중복 여부
     * @private
     */
    hasDuplicateUpdate(update) {
        for (const [priority, queue] of this.priorityQueue) {
            const duplicate = queue.find(existing => 
                existing.id === update.id || 
                (existing.component === update.component && existing.type === update.type)
            );
            if (duplicate) {
                return true;
            }
        }
        return false;
    }

    /**
     * 플러시 스케줄링
     * @private
     */
    scheduleFlush() {
        if (this.isFlushPending) return;
        
        this.isFlushPending = true;
        
        // 디바운싱된 실행
        setTimeout(() => {
            requestAnimationFrame(() => this.flushUpdates());
        }, this.debounceTime);
    }

    /**
     * 지연된 플러시 스케줄링
     * @private
     */
    scheduleDeferredFlush() {
        const now = performance.now();
        const nextUpdate = this.deferredQueue[0];
        
        if (nextUpdate && nextUpdate.executeAt <= now) {
            requestAnimationFrame(() => this.processDeferredUpdates());
        } else if (nextUpdate) {
            const delay = Math.max(0, nextUpdate.executeAt - now);
            setTimeout(() => {
                requestAnimationFrame(() => this.processDeferredUpdates());
            }, delay);
        }
    }

    /**
     * 업데이트 플러시 실행
     * @private
     */
    flushUpdates() {
        if (this.isProcessing) {
            // 이미 처리 중이면 다음 프레임으로 연기
            requestAnimationFrame(() => this.flushUpdates());
            return;
        }

        this.isProcessing = true;
        this.isFlushPending = false;
        
        const startTime = performance.now();
        const processedUpdates = [];
        let processedCount = 0;

        try {
            // 우선순위 순서로 처리 (high > normal > low)
            const priorityOrder = ['high', 'normal', 'low'];
            
            for (const priority of priorityOrder) {
                const queue = this.priorityQueue.get(priority) || [];
                
                while (queue.length > 0 && processedCount < this.maxBatchSize) {
                    const currentTime = performance.now();
                    
                    // 처리 시간 제한 체크
                    if (currentTime - startTime > this.maxProcessingTime) {
                        console.warn('배치 처리 시간 초과, 남은 업데이트는 다음 프레임으로 연기');
                        break;
                    }

                    const update = queue.shift();
                    
                    try {
                        const result = update.fn();
                        processedUpdates.push({ update, result, success: true });
                        processedCount++;
                        
                    } catch (error) {
                        console.error('업데이트 처리 중 오류:', error, update);
                        
                        // 재시도 로직
                        if (update.retryCount < update.maxRetries) {
                            update.retryCount++;
                            queue.push(update); // 큐 뒤로 다시 추가
                        } else {
                            this.metrics.droppedUpdates++;
                            processedUpdates.push({ update, error, success: false });
                        }
                    }
                }
                
                // 시간 초과로 중단된 경우
                if (performance.now() - startTime > this.maxProcessingTime) {
                    break;
                }
            }

            // 메트릭 업데이트
            this.updateMetrics(processedCount, performance.now() - startTime);
            
        } finally {
            this.isProcessing = false;
            
            // 남은 업데이트가 있으면 다음 프레임에서 계속 처리
            if (this.getTotalQueueSize() > 0) {
                this.scheduleFlush();
            }
        }

        // 처리 완료 이벤트 발행
        this.emitBatchComplete(processedUpdates);
    }

    /**
     * 지연된 업데이트 처리
     * @private
     */
    processDeferredUpdates() {
        const now = performance.now();
        const readyUpdates = [];
        
        // 실행 준비된 업데이트 찾기
        while (this.deferredQueue.length > 0 && this.deferredQueue[0].executeAt <= now) {
            readyUpdates.push(this.deferredQueue.shift());
        }
        
        // 준비된 업데이트를 일반 큐에 추가
        readyUpdates.forEach(deferred => {
            this.enqueueUpdate(
                deferred.fn,
                deferred.options.priority || 'normal',
                deferred.options
            );
        });
        
        // 다음 지연 업데이트 스케줄링
        if (this.deferredQueue.length > 0) {
            this.scheduleDeferredFlush();
        }
    }

    /**
     * 전체 큐 크기 반환
     * @returns {number} 큐에 있는 총 업데이트 수
     * @private
     */
    getTotalQueueSize() {
        let total = 0;
        for (const [priority, queue] of this.priorityQueue) {
            total += queue.length;
        }
        return total;
    }

    /**
     * 특정 컴포넌트의 업데이트 취소
     * @param {Object} component - 컴포넌트 인스턴스
     */
    cancelUpdatesFor(component) {
        for (const [priority, queue] of this.priorityQueue) {
            const filtered = queue.filter(update => update.component !== component);
            this.priorityQueue.set(priority, filtered);
        }

        // 지연 큐에서도 제거
        this.deferredQueue = this.deferredQueue.filter(
            deferred => deferred.options.component !== component
        );
    }

    /**
     * 특정 타입의 업데이트 취소
     * @param {string} type - 업데이트 타입
     */
    cancelUpdatesByType(type) {
        for (const [priority, queue] of this.priorityQueue) {
            const filtered = queue.filter(update => update.type !== type);
            this.priorityQueue.set(priority, filtered);
        }
    }

    /**
     * 모든 업데이트 취소
     */
    cancelAllUpdates() {
        this.priorityQueue.clear();
        this.deferredQueue = [];
        this.isFlushPending = false;
    }

    /**
     * 즉시 플러시 (긴급 상황용)
     */
    flushImmediately() {
        if (this.isProcessing) return;
        
        this.isFlushPending = false;
        this.flushUpdates();
    }

    /**
     * 성능 모니터링 초기화
     * @private
     */
    initPerformanceMonitoring() {
        if (typeof PerformanceObserver !== 'undefined') {
            this.performanceObserver = new PerformanceObserver((list) => {
                const entries = list.getEntries();
                entries.forEach(entry => {
                    if (entry.name.startsWith('batch-update')) {
                        console.debug('배치 업데이트 성능:', entry.duration, 'ms');
                    }
                });
            });
            
            try {
                this.performanceObserver.observe({ 
                    entryTypes: ['measure', 'mark'] 
                });
            } catch (error) {
                console.warn('Performance Observer 초기화 실패:', error);
            }
        }
    }

    /**
     * 메트릭 업데이트
     * @param {number} batchSize - 배치 크기
     * @param {number} processingTime - 처리 시간
     * @private
     */
    updateMetrics(batchSize, processingTime) {
        this.metrics.totalBatches++;
        this.metrics.totalUpdates += batchSize;
        
        // 평균 계산
        this.metrics.avgBatchSize = this.metrics.totalUpdates / this.metrics.totalBatches;
        this.metrics.avgProcessingTime = (
            (this.metrics.avgProcessingTime * (this.metrics.totalBatches - 1)) + processingTime
        ) / this.metrics.totalBatches;
    }

    /**
     * 배치 완료 이벤트 발행
     * @param {Array} processedUpdates - 처리된 업데이트 배열
     * @private
     */
    emitBatchComplete(processedUpdates) {
        const event = new CustomEvent('batch-update-complete', {
            detail: {
                processedCount: processedUpdates.length,
                successCount: processedUpdates.filter(p => p.success).length,
                failureCount: processedUpdates.filter(p => !p.success).length,
                metrics: this.getMetrics()
            }
        });
        
        if (typeof window !== 'undefined') {
            window.dispatchEvent(event);
        }
    }

    /**
     * 메트릭 반환
     * @returns {Object} 성능 메트릭
     */
    getMetrics() {
        return {
            ...this.metrics,
            queueSize: this.getTotalQueueSize(),
            deferredQueueSize: this.deferredQueue.length,
            isProcessing: this.isProcessing,
            isFlushPending: this.isFlushPending
        };
    }

    /**
     * 메트릭 리셋
     */
    resetMetrics() {
        this.metrics = {
            totalBatches: 0,
            totalUpdates: 0,
            avgBatchSize: 0,
            avgProcessingTime: 0,
            droppedUpdates: 0
        };
    }

    /**
     * 큐 상태 반환 (디버깅용)
     * @returns {Object} 큐 상태
     */
    getQueueStatus() {
        const status = {
            priorityQueues: {},
            deferredQueue: this.deferredQueue.length,
            totalSize: this.getTotalQueueSize()
        };
        
        for (const [priority, queue] of this.priorityQueue) {
            status.priorityQueues[priority] = queue.length;
        }
        
        return status;
    }
}

// 전역 배치 매니저 인스턴스
export const batchUpdateManager = new BatchUpdateManager();

// 편의 함수들
export const batchUpdate = (updateFn, priority, options) => 
    batchUpdateManager.enqueueUpdate(updateFn, priority, options);

export const deferredUpdate = (updateFn, delay, options) => 
    batchUpdateManager.enqueueDeferredUpdate(updateFn, delay, options);

// 개발 모드에서 전역 접근 가능
if (typeof window !== 'undefined' && process.env.NODE_ENV === 'development') {
    window.__TRADING_DASHBOARD_BATCH_MANAGER__ = batchUpdateManager;
}
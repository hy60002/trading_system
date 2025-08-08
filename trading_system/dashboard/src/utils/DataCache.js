/**
 * @fileoverview 로컬 데이터 캐싱 및 동기화 큐 시스템
 * @description IndexedDB 기반의 오프라인 지원 데이터 관리
 */

import { eventBus } from '../core/EventBus.js';

/**
 * 데이터 캐시 관리자
 * @class DataCache
 */
export class DataCache {
    constructor() {
        this.dbName = 'TradingSystemCache';
        this.dbVersion = 1;
        this.db = null;
        this.syncQueue = [];
        this.isOnline = navigator.onLine;
        this.syncInProgress = false;
        this.maxRetries = 3;
        this.retryDelay = 1000;
        
        // 캐시 설정
        this.cacheConfig = {
            positions: { ttl: 30000, maxSize: 1000 },      // 30초
            trades: { ttl: 300000, maxSize: 5000 },         // 5분
            market: { ttl: 5000, maxSize: 100 },            // 5초
            analytics: { ttl: 600000, maxSize: 500 },       // 10분
            user: { ttl: 1800000, maxSize: 50 }             // 30분
        };
        
        // 동기화 상태
        this.syncStatus = {
            lastSync: null,
            pendingChanges: 0,
            conflictResolutions: 0,
            failedSyncs: 0
        };
        
        this.initDatabase();
        this.setupEventListeners();
    }

    /**
     * IndexedDB 초기화
     * @private
     */
    async initDatabase() {
        try {
            this.db = await this.openDatabase();
            console.log('✅ IndexedDB 초기화 완료');
            
            // 캐시 정리 스케줄링
            this.scheduleCleanup();
            
            eventBus.emit('cache:initialized');
        } catch (error) {
            console.error('❌ IndexedDB 초기화 실패:', error);
            this.fallbackToMemoryCache();
        }
    }

    /**
     * 데이터베이스 열기
     * @returns {Promise<IDBDatabase>}
     * @private
     */
    openDatabase() {
        return new Promise((resolve, reject) => {
            const request = indexedDB.open(this.dbName, this.dbVersion);
            
            request.onerror = () => reject(request.error);
            request.onsuccess = () => resolve(request.result);
            
            request.onupgradeneeded = (event) => {
                const db = event.target.result;
                
                // 캐시 스토어
                const cacheStore = db.createObjectStore('cache', { 
                    keyPath: 'key' 
                });
                cacheStore.createIndex('category', 'category', { unique: false });
                cacheStore.createIndex('timestamp', 'timestamp', { unique: false });
                
                // 동기화 큐 스토어
                const syncStore = db.createObjectStore('syncQueue', { 
                    keyPath: 'id', 
                    autoIncrement: true 
                });
                syncStore.createIndex('timestamp', 'timestamp', { unique: false });
                syncStore.createIndex('priority', 'priority', { unique: false });
                
                // 메타데이터 스토어
                db.createObjectStore('metadata', { keyPath: 'key' });
                
                console.log('📊 IndexedDB 스키마 생성 완료');
            };
        });
    }

    /**
     * 이벤트 리스너 설정
     * @private
     */
    setupEventListeners() {
        // 온라인/오프라인 상태 모니터링
        window.addEventListener('online', () => {
            this.isOnline = true;
            console.log('🌐 온라인 상태로 변경');
            eventBus.emit('cache:online');
            this.processSyncQueue();
        });

        window.addEventListener('offline', () => {
            this.isOnline = false;
            console.log('📴 오프라인 상태로 변경');
            eventBus.emit('cache:offline');
        });

        // 이벤트 버스 리스너
        eventBus.on('data:changed', (data) => {
            this.handleDataChange(data);
        });

        eventBus.on('sync:request', (category) => {
            this.requestSync(category);
        });
    }

    /**
     * 데이터 저장
     * @param {string} key - 데이터 키
     * @param {*} data - 저장할 데이터
     * @param {string} category - 데이터 카테고리
     * @param {Object} options - 옵션
     * @returns {Promise<void>}
     */
    async set(key, data, category = 'default', options = {}) {
        const cacheEntry = {
            key,
            data,
            category,
            timestamp: Date.now(),
            ttl: options.ttl || this.cacheConfig[category]?.ttl || 300000,
            version: options.version || 1,
            source: options.source || 'local',
            checksum: this.calculateChecksum(data)
        };

        try {
            if (this.db) {
                await this.storeInIndexedDB('cache', cacheEntry);
            } else {
                // 메모리 캐시 폴백
                this.memoryCache = this.memoryCache || new Map();
                this.memoryCache.set(key, cacheEntry);
            }

            // 온라인 상태에서 서버와 동기화 필요한 경우
            if (this.isOnline && options.sync !== false) {
                this.addToSyncQueue({
                    type: 'update',
                    key,
                    data,
                    category,
                    priority: options.priority || 'normal'
                });
            }

            eventBus.emit('cache:set', { key, category });
            
        } catch (error) {
            console.error('❌ 데이터 저장 실패:', error);
            throw error;
        }
    }

    /**
     * 데이터 조회
     * @param {string} key - 데이터 키
     * @param {Object} options - 옵션
     * @returns {Promise<*>} 조회된 데이터
     */
    async get(key, options = {}) {
        try {
            let cacheEntry;

            if (this.db) {
                cacheEntry = await this.getFromIndexedDB('cache', key);
            } else {
                // 메모리 캐시 폴백
                this.memoryCache = this.memoryCache || new Map();
                cacheEntry = this.memoryCache.get(key);
            }

            if (!cacheEntry) {
                return null;
            }

            // TTL 확인
            if (this.isCacheExpired(cacheEntry)) {
                await this.delete(key);
                
                // 만료된 경우 서버에서 새로운 데이터 요청
                if (this.isOnline && options.fetchOnExpired !== false) {
                    this.requestDataFromServer(key, cacheEntry.category);
                }
                
                return null;
            }

            // 데이터 무결성 검증
            if (options.validateChecksum !== false) {
                const currentChecksum = this.calculateChecksum(cacheEntry.data);
                if (currentChecksum !== cacheEntry.checksum) {
                    console.warn('⚠️ 캐시 데이터 무결성 실패:', key);
                    await this.delete(key);
                    return null;
                }
            }

            eventBus.emit('cache:hit', { key, category: cacheEntry.category });
            return cacheEntry.data;

        } catch (error) {
            console.error('❌ 데이터 조회 실패:', error);
            eventBus.emit('cache:miss', { key, error: error.message });
            return null;
        }
    }

    /**
     * 데이터 삭제
     * @param {string} key - 데이터 키
     * @returns {Promise<void>}
     */
    async delete(key) {
        try {
            if (this.db) {
                await this.deleteFromIndexedDB('cache', key);
            } else {
                this.memoryCache = this.memoryCache || new Map();
                this.memoryCache.delete(key);
            }

            eventBus.emit('cache:delete', { key });
            
        } catch (error) {
            console.error('❌ 데이터 삭제 실패:', error);
            throw error;
        }
    }

    /**
     * 카테고리별 데이터 조회
     * @param {string} category - 카테고리
     * @param {Object} options - 옵션
     * @returns {Promise<Array>} 데이터 배열
     */
    async getByCategory(category, options = {}) {
        try {
            if (this.db) {
                const transaction = this.db.transaction(['cache'], 'readonly');
                const store = transaction.objectStore('cache');
                const index = store.index('category');
                const request = index.getAll(category);

                const results = await new Promise((resolve, reject) => {
                    request.onsuccess = () => resolve(request.result);
                    request.onerror = () => reject(request.error);
                });

                return results
                    .filter(entry => !this.isCacheExpired(entry))
                    .sort((a, b) => b.timestamp - a.timestamp)
                    .slice(0, options.limit || 100)
                    .map(entry => entry.data);
            } else {
                // 메모리 캐시 폴백
                const results = [];
                for (const [key, entry] of this.memoryCache.entries()) {
                    if (entry.category === category && !this.isCacheExpired(entry)) {
                        results.push(entry.data);
                    }
                }
                return results;
            }
        } catch (error) {
            console.error('❌ 카테고리별 조회 실패:', error);
            return [];
        }
    }

    /**
     * 동기화 큐에 추가
     * @param {Object} syncItem - 동기화 아이템
     * @private
     */
    async addToSyncQueue(syncItem) {
        const queueItem = {
            ...syncItem,
            id: Date.now() + Math.random(),
            timestamp: Date.now(),
            retries: 0,
            status: 'pending'
        };

        try {
            if (this.db) {
                await this.storeInIndexedDB('syncQueue', queueItem);
            } else {
                this.syncQueue.push(queueItem);
            }

            this.syncStatus.pendingChanges++;
            eventBus.emit('sync:queue_updated', this.syncStatus);

            // 온라인 상태면 즉시 처리 시도
            if (this.isOnline && !this.syncInProgress) {
                this.processSyncQueue();
            }

        } catch (error) {
            console.error('❌ 동기화 큐 추가 실패:', error);
        }
    }

    /**
     * 동기화 큐 처리
     * @private
     */
    async processSyncQueue() {
        if (this.syncInProgress || !this.isOnline) {
            return;
        }

        this.syncInProgress = true;
        eventBus.emit('sync:started');

        try {
            let queueItems;

            if (this.db) {
                queueItems = await this.getAllFromIndexedDB('syncQueue');
            } else {
                queueItems = [...this.syncQueue];
            }

            // 우선순위별 정렬
            queueItems.sort((a, b) => {
                const priorityOrder = { high: 3, normal: 2, low: 1 };
                return priorityOrder[b.priority] - priorityOrder[a.priority] || 
                       a.timestamp - b.timestamp;
            });

            for (const item of queueItems) {
                if (item.status === 'pending') {
                    await this.processSyncItem(item);
                }
            }

            this.syncStatus.lastSync = Date.now();
            eventBus.emit('sync:completed', this.syncStatus);

        } catch (error) {
            console.error('❌ 동기화 처리 실패:', error);
            this.syncStatus.failedSyncs++;
            eventBus.emit('sync:failed', { error, status: this.syncStatus });
        } finally {
            this.syncInProgress = false;
        }
    }

    /**
     * 개별 동기화 아이템 처리
     * @param {Object} item - 동기화 아이템
     * @private
     */
    async processSyncItem(item) {
        try {
            // 서버로 데이터 전송
            const response = await this.sendToServer(item);
            
            if (response.success) {
                // 성공 시 큐에서 제거
                await this.removeSyncItem(item.id);
                
                // 서버 응답 데이터로 캐시 업데이트
                if (response.data) {
                    await this.handleServerResponse(item, response.data);
                }
                
                this.syncStatus.pendingChanges--;
            } else {
                // 실패 시 재시도 또는 포기
                await this.handleSyncFailure(item, response.error);
            }

        } catch (error) {
            console.error(`❌ 동기화 아이템 처리 실패 (${item.id}):`, error);
            await this.handleSyncFailure(item, error);
        }
    }

    /**
     * 동기화 실패 처리
     * @param {Object} item - 동기화 아이템
     * @param {Error} error - 에러
     * @private
     */
    async handleSyncFailure(item, error) {
        item.retries++;
        item.lastError = error.message;

        if (item.retries >= this.maxRetries) {
            // 최대 재시도 횟수 초과 시 실패 처리
            item.status = 'failed';
            console.error(`❌ 동기화 포기 (${item.id}): ${error.message}`);
            
            eventBus.emit('sync:item_failed', {
                item,
                error: error.message
            });
        } else {
            // 재시도 스케줄링
            const delay = this.retryDelay * Math.pow(2, item.retries - 1);
            setTimeout(() => {
                if (this.isOnline) {
                    this.processSyncItem(item);
                }
            }, delay);
        }

        // 큐 업데이트
        if (this.db) {
            await this.storeInIndexedDB('syncQueue', item);
        }
    }

    /**
     * 서버로 데이터 전송
     * @param {Object} item - 동기화 아이템
     * @returns {Promise<Object>} 응답
     * @private
     */
    async sendToServer(item) {
        // 실제 구현에서는 실제 API 엔드포인트로 전송
        try {
            const response = await fetch('/api/sync', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json'
                },
                body: JSON.stringify(item)
            });

            if (!response.ok) {
                throw new Error(`HTTP ${response.status}: ${response.statusText}`);
            }

            return await response.json();
        } catch (error) {
            // 개발/테스트 환경에서는 성공으로 처리
            if (process.env.NODE_ENV === 'development') {
                return { success: true, data: null };
            }
            throw error;
        }
    }

    /**
     * 서버 응답 처리
     * @param {Object} item - 동기화 아이템
     * @param {*} serverData - 서버 데이터
     * @private
     */
    async handleServerResponse(item, serverData) {
        if (serverData && typeof serverData === 'object') {
            // 서버 데이터와 로컬 데이터 병합
            const mergedData = this.mergeData(item.data, serverData);
            
            if (mergedData !== item.data) {
                // 변경사항이 있으면 캐시 업데이트
                await this.set(item.key, mergedData, item.category, {
                    sync: false, // 무한 동기화 방지
                    source: 'server'
                });
                
                this.syncStatus.conflictResolutions++;
                
                eventBus.emit('sync:conflict_resolved', {
                    key: item.key,
                    localData: item.data,
                    serverData,
                    mergedData
                });
            }
        }
    }

    /**
     * 데이터 병합
     * @param {*} localData - 로컬 데이터
     * @param {*} serverData - 서버 데이터
     * @returns {*} 병합된 데이터
     * @private
     */
    mergeData(localData, serverData) {
        // 간단한 병합 로직 (실제로는 더 복잡한 충돌 해결 필요)
        if (typeof localData !== 'object' || typeof serverData !== 'object') {
            // 서버 데이터 우선
            return serverData;
        }

        // 타임스탬프 기반 병합
        const merged = { ...localData };
        
        for (const [key, value] of Object.entries(serverData)) {
            if (!merged.hasOwnProperty(key)) {
                merged[key] = value;
            } else if (merged[key]?.timestamp < value?.timestamp) {
                merged[key] = value;
            }
        }

        return merged;
    }

    /**
     * 동기화 아이템 제거
     * @param {number} itemId - 아이템 ID
     * @private
     */
    async removeSyncItem(itemId) {
        try {
            if (this.db) {
                await this.deleteFromIndexedDB('syncQueue', itemId);
            } else {
                const index = this.syncQueue.findIndex(item => item.id === itemId);
                if (index !== -1) {
                    this.syncQueue.splice(index, 1);
                }
            }
        } catch (error) {
            console.error('❌ 동기화 아이템 제거 실패:', error);
        }
    }

    /**
     * 캐시 만료 확인
     * @param {Object} cacheEntry - 캐시 엔트리
     * @returns {boolean} 만료 여부
     * @private
     */
    isCacheExpired(cacheEntry) {
        return Date.now() > (cacheEntry.timestamp + cacheEntry.ttl);
    }

    /**
     * 체크섬 계산
     * @param {*} data - 데이터
     * @returns {string} 체크섬
     * @private
     */
    calculateChecksum(data) {
        const str = JSON.stringify(data);
        let hash = 0;
        
        for (let i = 0; i < str.length; i++) {
            const char = str.charCodeAt(i);
            hash = ((hash << 5) - hash) + char;
            hash = hash & hash; // 32bit integer
        }
        
        return hash.toString(36);
    }

    /**
     * IndexedDB에 저장
     * @param {string} storeName - 스토어 이름
     * @param {Object} data - 데이터
     * @returns {Promise<void>}
     * @private
     */
    storeInIndexedDB(storeName, data) {
        return new Promise((resolve, reject) => {
            const transaction = this.db.transaction([storeName], 'readwrite');
            const store = transaction.objectStore(storeName);
            const request = store.put(data);
            
            request.onsuccess = () => resolve();
            request.onerror = () => reject(request.error);
        });
    }

    /**
     * IndexedDB에서 조회
     * @param {string} storeName - 스토어 이름
     * @param {*} key - 키
     * @returns {Promise<*>} 데이터
     * @private
     */
    getFromIndexedDB(storeName, key) {
        return new Promise((resolve, reject) => {
            const transaction = this.db.transaction([storeName], 'readonly');
            const store = transaction.objectStore(storeName);
            const request = store.get(key);
            
            request.onsuccess = () => resolve(request.result);
            request.onerror = () => reject(request.error);
        });
    }

    /**
     * IndexedDB에서 모든 데이터 조회
     * @param {string} storeName - 스토어 이름
     * @returns {Promise<Array>} 데이터 배열
     * @private
     */
    getAllFromIndexedDB(storeName) {
        return new Promise((resolve, reject) => {
            const transaction = this.db.transaction([storeName], 'readonly');
            const store = transaction.objectStore(storeName);
            const request = store.getAll();
            
            request.onsuccess = () => resolve(request.result);
            request.onerror = () => reject(request.error);
        });
    }

    /**
     * IndexedDB에서 삭제
     * @param {string} storeName - 스토어 이름
     * @param {*} key - 키
     * @returns {Promise<void>}
     * @private
     */
    deleteFromIndexedDB(storeName, key) {
        return new Promise((resolve, reject) => {
            const transaction = this.db.transaction([storeName], 'readwrite');
            const store = transaction.objectStore(storeName);
            const request = store.delete(key);
            
            request.onsuccess = () => resolve();
            request.onerror = () => reject(request.error);
        });
    }

    /**
     * 메모리 캐시로 폴백
     * @private
     */
    fallbackToMemoryCache() {
        console.warn('⚠️ IndexedDB 사용 불가 - 메모리 캐시로 폴백');
        this.memoryCache = new Map();
        this.syncQueue = [];
        
        eventBus.emit('cache:fallback_mode');
    }

    /**
     * 캐시 정리 스케줄링
     * @private
     */
    scheduleCleanup() {
        // 10분마다 만료된 캐시 정리
        setInterval(() => {
            this.cleanupExpiredCache();
        }, 600000);
        
        // 1시간마다 캐시 크기 체크
        setInterval(() => {
            this.enforceCacheLimits();
        }, 3600000);
    }

    /**
     * 만료된 캐시 정리
     * @private
     */
    async cleanupExpiredCache() {
        try {
            if (this.db) {
                const transaction = this.db.transaction(['cache'], 'readwrite');
                const store = transaction.objectStore('cache');
                const request = store.openCursor();
                
                request.onsuccess = (event) => {
                    const cursor = event.target.result;
                    if (cursor) {
                        const entry = cursor.value;
                        if (this.isCacheExpired(entry)) {
                            cursor.delete();
                        }
                        cursor.continue();
                    }
                };
            } else if (this.memoryCache) {
                for (const [key, entry] of this.memoryCache.entries()) {
                    if (this.isCacheExpired(entry)) {
                        this.memoryCache.delete(key);
                    }
                }
            }
            
            console.log('🧹 만료된 캐시 정리 완료');
        } catch (error) {
            console.error('❌ 캐시 정리 실패:', error);
        }
    }

    /**
     * 캐시 크기 제한 적용
     * @private
     */
    async enforceCacheLimits() {
        for (const [category, config] of Object.entries(this.cacheConfig)) {
            try {
                const entries = await this.getByCategory(category);
                
                if (entries.length > config.maxSize) {
                    // 오래된 항목부터 삭제
                    const entriesToDelete = entries
                        .sort((a, b) => a.timestamp - b.timestamp)
                        .slice(0, entries.length - config.maxSize);
                    
                    for (const entry of entriesToDelete) {
                        await this.delete(entry.key);
                    }
                    
                    console.log(`🗑️ ${category} 카테고리 캐시 크기 조절: ${entriesToDelete.length}개 삭제`);
                }
            } catch (error) {
                console.error(`❌ ${category} 캐시 크기 제한 적용 실패:`, error);
            }
        }
    }

    /**
     * 서버에서 데이터 요청
     * @param {string} key - 데이터 키
     * @param {string} category - 카테고리
     * @private
     */
    requestDataFromServer(key, category) {
        this.addToSyncQueue({
            type: 'fetch',
            key,
            category,
            priority: 'normal'
        });
    }

    /**
     * 데이터 변경 처리
     * @param {Object} data - 변경된 데이터
     * @private
     */
    handleDataChange(data) {
        // 데이터 변경 시 동기화 큐에 추가
        this.addToSyncQueue({
            type: 'update',
            key: data.key,
            data: data.value,
            category: data.category,
            priority: data.priority || 'normal'
        });
    }

    /**
     * 동기화 요청
     * @param {string} category - 카테고리
     */
    requestSync(category) {
        if (this.isOnline) {
            this.processSyncQueue();
        } else {
            eventBus.emit('toast:show', {
                message: '오프라인 상태입니다. 온라인 연결 후 자동 동기화됩니다.',
                type: 'info',
                duration: 3000
            });
        }
    }

    /**
     * 캐시 통계 조회
     * @returns {Object} 캐시 통계
     */
    async getCacheStats() {
        const stats = {
            totalEntries: 0,
            byCategory: {},
            totalSize: 0,
            hitRate: 0,
            syncStatus: this.syncStatus,
            isOnline: this.isOnline
        };

        try {
            if (this.db) {
                const entries = await this.getAllFromIndexedDB('cache');
                stats.totalEntries = entries.length;
                
                for (const entry of entries) {
                    stats.byCategory[entry.category] = 
                        (stats.byCategory[entry.category] || 0) + 1;
                    stats.totalSize += JSON.stringify(entry.data).length;
                }
            } else if (this.memoryCache) {
                stats.totalEntries = this.memoryCache.size;
                
                for (const entry of this.memoryCache.values()) {
                    stats.byCategory[entry.category] = 
                        (stats.byCategory[entry.category] || 0) + 1;
                    stats.totalSize += JSON.stringify(entry.data).length;
                }
            }

            return stats;
        } catch (error) {
            console.error('❌ 캐시 통계 조회 실패:', error);
            return stats;
        }
    }

    /**
     * 캐시 초기화
     * @param {string} category - 특정 카테고리 (선택사항)
     */
    async clear(category = null) {
        try {
            if (this.db) {
                const transaction = this.db.transaction(['cache'], 'readwrite');
                const store = transaction.objectStore('cache');
                
                if (category) {
                    const index = store.index('category');
                    const request = index.openCursor(IDBKeyRange.only(category));
                    
                    request.onsuccess = (event) => {
                        const cursor = event.target.result;
                        if (cursor) {
                            cursor.delete();
                            cursor.continue();
                        }
                    };
                } else {
                    store.clear();
                }
            } else if (this.memoryCache) {
                if (category) {
                    for (const [key, entry] of this.memoryCache.entries()) {
                        if (entry.category === category) {
                            this.memoryCache.delete(key);
                        }
                    }
                } else {
                    this.memoryCache.clear();
                }
            }

            console.log(`🗑️ 캐시 초기화 완료${category ? ` (${category})` : ''}`);
            eventBus.emit('cache:cleared', { category });

        } catch (error) {
            console.error('❌ 캐시 초기화 실패:', error);
            throw error;
        }
    }

    /**
     * 강제 동기화
     */
    async forceSync() {
        if (!this.isOnline) {
            throw new Error('오프라인 상태에서는 동기화할 수 없습니다');
        }

        this.syncInProgress = false; // 강제로 리셋
        await this.processSyncQueue();
    }

    /**
     * 캐시 설정 업데이트
     * @param {Object} newConfig - 새로운 설정
     */
    updateConfig(newConfig) {
        this.cacheConfig = { ...this.cacheConfig, ...newConfig };
        console.log('⚙️ 캐시 설정 업데이트:', newConfig);
    }
}

// 전역 데이터 캐시 인스턴스
export const dataCache = new DataCache();

// 개발 모드에서 전역 접근 가능하게 설정
if (typeof window !== 'undefined' && process.env.NODE_ENV === 'development') {
    window.__DATA_CACHE__ = dataCache;
}
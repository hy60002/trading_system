/**
 * @fileoverview 서비스 워커 관리자
 * @description 오프라인 지원 및 캐싱 전략 관리
 */

import { eventBus } from '../core/EventBus.js';

/**
 * 서비스 워커 관리자 클래스
 * @class ServiceWorkerManager
 */
export class ServiceWorkerManager {
    constructor() {
        this.registration = null;
        this.isSupported = 'serviceWorker' in navigator;
        this.isRegistered = false;
        this.updateAvailable = false;
        this.isOnline = navigator.onLine;
        
        // 캐시 전략 설정
        this.cacheStrategies = {
            assets: 'cache-first',      // 정적 자산
            api: 'network-first',       // API 요청
            pages: 'stale-while-revalidate' // 페이지
        };
        
        // 캐시 이름
        this.cacheNames = {
            static: 'trading-dashboard-static-v1',
            dynamic: 'trading-dashboard-dynamic-v1',
            api: 'trading-dashboard-api-v1'
        };
        
        this.setupNetworkListeners();
    }

    /**
     * 네트워크 상태 리스너 설정
     * @private
     */
    setupNetworkListeners() {
        window.addEventListener('online', () => {
            this.isOnline = true;
            this.handleOnline();
        });

        window.addEventListener('offline', () => {
            this.isOnline = false;
            this.handleOffline();
        });
    }

    /**
     * 서비스 워커 등록
     * @returns {Promise<void>}
     */
    async register() {
        if (!this.isSupported) {
            console.warn('서비스 워커가 지원되지 않습니다.');
            return;
        }

        try {
            console.log('📱 서비스 워커 등록 중...');
            
            // 서비스 워커 생성
            await this.createServiceWorker();
            
            this.registration = await navigator.serviceWorker.register('/sw.js', {
                scope: '/'
            });

            console.log('✅ 서비스 워커 등록 성공:', this.registration.scope);
            this.isRegistered = true;

            // 이벤트 리스너 설정
            this.setupServiceWorkerListeners();
            
            // 업데이트 확인
            await this.checkForUpdates();
            
            eventBus.emit('sw:registered', {
                scope: this.registration.scope
            });

        } catch (error) {
            console.error('❌ 서비스 워커 등록 실패:', error);
            eventBus.emit('sw:registration_failed', { error });
        }
    }

    /**
     * 서비스 워커 생성
     * @private
     */
    async createServiceWorker() {
        const swContent = this.generateServiceWorkerCode();
        const blob = new Blob([swContent], { type: 'application/javascript' });
        const swUrl = URL.createObjectURL(blob);
        
        // 동적 서비스 워커 등록
        try {
            this.registration = await navigator.serviceWorker.register(swUrl, {
                scope: '/'
            });
        } finally {
            URL.revokeObjectURL(swUrl);
        }
    }

    /**
     * 서비스 워커 코드 생성
     * @returns {string} 서비스 워커 코드
     * @private
     */
    generateServiceWorkerCode() {
        return `
// Trading Dashboard Service Worker
const CACHE_NAME = '${this.cacheNames.static}';
const DYNAMIC_CACHE = '${this.cacheNames.dynamic}';
const API_CACHE = '${this.cacheNames.api}';

const STATIC_ASSETS = [
    '/',
    '/dashboard/index.html',
    '/dashboard/css/main.css',
    '/dashboard/css/themes.css',
    '/dashboard/src/main.js',
    'https://cdnjs.cloudflare.com/ajax/libs/font-awesome/6.4.0/css/all.min.css',
    'https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700&display=swap'
];

const API_ENDPOINTS = [
    '/api/dashboard',
    '/api/positions',
    '/api/balance',
    '/api/notifications'
];

// 설치 이벤트
self.addEventListener('install', (event) => {
    console.log('🔧 서비스 워커 설치 중...');
    
    event.waitUntil(
        caches.open(CACHE_NAME)
            .then(cache => {
                console.log('📦 정적 자산 캐싱...');
                return cache.addAll(STATIC_ASSETS);
            })
            .then(() => {
                console.log('✅ 서비스 워커 설치 완료');
                return self.skipWaiting();
            })
            .catch(error => {
                console.error('❌ 서비스 워커 설치 실패:', error);
            })
    );
});

// 활성화 이벤트
self.addEventListener('activate', (event) => {
    console.log('🚀 서비스 워커 활성화 중...');
    
    event.waitUntil(
        caches.keys()
            .then(cacheNames => {
                return Promise.all(
                    cacheNames.map(cacheName => {
                        if (cacheName !== CACHE_NAME && 
                            cacheName !== DYNAMIC_CACHE && 
                            cacheName !== API_CACHE) {
                            console.log('🗑️ 오래된 캐시 삭제:', cacheName);
                            return caches.delete(cacheName);
                        }
                    })
                );
            })
            .then(() => {
                console.log('✅ 서비스 워커 활성화 완료');
                return self.clients.claim();
            })
    );
});

// Fetch 이벤트
self.addEventListener('fetch', (event) => {
    const request = event.request;
    const url = new URL(request.url);
    
    // API 요청 처리
    if (url.pathname.startsWith('/api/')) {
        event.respondWith(handleApiRequest(request));
        return;
    }
    
    // WebSocket 요청은 무시
    if (url.pathname.startsWith('/ws/')) {
        return;
    }
    
    // 정적 자산 처리
    if (request.destination === 'document' || 
        request.destination === 'script' || 
        request.destination === 'style' ||
        request.destination === 'image') {
        event.respondWith(handleStaticRequest(request));
        return;
    }
    
    // 기타 요청은 네트워크 우선
    event.respondWith(
        fetch(request).catch(() => {
            return caches.match(request);
        })
    );
});

// API 요청 처리 (Network First 전략)
async function handleApiRequest(request) {
    const cacheName = API_CACHE;
    
    try {
        // 네트워크 요청 시도
        const networkResponse = await fetch(request);
        
        if (networkResponse.ok) {
            // 성공한 응답을 캐시에 저장
            const cache = await caches.open(cacheName);
            cache.put(request, networkResponse.clone());
        }
        
        return networkResponse;
        
    } catch (error) {
        console.log('📡 네트워크 요청 실패, 캐시에서 조회:', request.url);
        
        // 네트워크 실패 시 캐시에서 조회
        const cachedResponse = await caches.match(request);
        
        if (cachedResponse) {
            return cachedResponse;
        }
        
        // 캐시에도 없으면 오프라인 응답 반환
        return new Response(
            JSON.stringify({
                error: 'Offline',
                message: '오프라인 상태입니다.'
            }),
            {
                status: 503,
                headers: { 'Content-Type': 'application/json' }
            }
        );
    }
}

// 정적 자산 처리 (Cache First 전략)
async function handleStaticRequest(request) {
    // 캐시에서 먼저 조회
    const cachedResponse = await caches.match(request);
    
    if (cachedResponse) {
        return cachedResponse;
    }
    
    try {
        // 캐시에 없으면 네트워크에서 가져오기
        const networkResponse = await fetch(request);
        
        if (networkResponse.ok) {
            // 성공한 응답을 동적 캐시에 저장
            const cache = await caches.open(DYNAMIC_CACHE);
            cache.put(request, networkResponse.clone());
        }
        
        return networkResponse;
        
    } catch (error) {
        // 네트워크도 실패하면 기본 페이지 반환
        if (request.destination === 'document') {
            return caches.match('/dashboard/index.html');
        }
        
        throw error;
    }
}

// Background Sync 이벤트
self.addEventListener('sync', (event) => {
    if (event.tag === 'background-sync') {
        event.waitUntil(handleBackgroundSync());
    }
});

// Background Sync 처리
async function handleBackgroundSync() {
    console.log('🔄 백그라운드 동기화 실행');
    
    try {
        // 오프라인 중 저장된 데이터 동기화
        const offlineData = await getOfflineData();
        
        if (offlineData.length > 0) {
            for (const data of offlineData) {
                await syncData(data);
            }
            
            // 동기화 완료 후 오프라인 데이터 삭제
            await clearOfflineData();
        }
        
    } catch (error) {
        console.error('❌ 백그라운드 동기화 실패:', error);
    }
}

// 오프라인 데이터 가져오기
async function getOfflineData() {
    // IndexedDB에서 오프라인 데이터 조회
    // 실제 구현에서는 IndexedDB를 사용
    return [];
}

// 데이터 동기화
async function syncData(data) {
    const response = await fetch('/api/sync', {
        method: 'POST',
        headers: {
            'Content-Type': 'application/json'
        },
        body: JSON.stringify(data)
    });
    
    if (!response.ok) {
        throw new Error('동기화 실패');
    }
}

// 오프라인 데이터 삭제
async function clearOfflineData() {
    // IndexedDB에서 동기화된 데이터 삭제
}

// Push 이벤트 (푸시 알림)
self.addEventListener('push', (event) => {
    if (!event.data) return;
    
    const data = event.data.json();
    
    const options = {
        body: data.body,
        icon: '/dashboard/icons/icon-192x192.png',
        badge: '/dashboard/icons/badge-72x72.png',
        tag: data.tag || 'trading-notification',
        requireInteraction: data.requireInteraction || false,
        actions: data.actions || []
    };
    
    event.waitUntil(
        self.registration.showNotification(data.title, options)
    );
});

// Notification Click 이벤트
self.addEventListener('notificationclick', (event) => {
    event.notification.close();
    
    event.waitUntil(
        clients.openWindow('/dashboard/')
    );
});

// Message 이벤트 (클라이언트와의 통신)
self.addEventListener('message', (event) => {
    if (event.data && event.data.type === 'SKIP_WAITING') {
        self.skipWaiting();
    }
});
`;
    }

    /**
     * 서비스 워커 이벤트 리스너 설정
     * @private
     */
    setupServiceWorkerListeners() {
        // 업데이트 발견
        this.registration.addEventListener('updatefound', () => {
            console.log('🔄 서비스 워커 업데이트 발견');
            
            const newWorker = this.registration.installing;
            newWorker.addEventListener('statechange', () => {
                if (newWorker.state === 'installed' && navigator.serviceWorker.controller) {
                    this.updateAvailable = true;
                    this.showUpdateNotification();
                }
            });
        });

        // 메시지 수신
        navigator.serviceWorker.addEventListener('message', (event) => {
            this.handleServiceWorkerMessage(event.data);
        });

        // 컨트롤러 변경 (새 서비스 워커 활성화)
        navigator.serviceWorker.addEventListener('controllerchange', () => {
            console.log('🔄 서비스 워커 컨트롤러 변경');
            window.location.reload();
        });
    }

    /**
     * 업데이트 확인
     * @returns {Promise<void>}
     */
    async checkForUpdates() {
        if (!this.registration) return;

        try {
            await this.registration.update();
            console.log('✅ 서비스 워커 업데이트 확인 완료');
        } catch (error) {
            console.error('❌ 서비스 워커 업데이트 확인 실패:', error);
        }
    }

    /**
     * 업데이트 적용
     * @returns {Promise<void>}
     */
    async applyUpdate() {
        if (!this.registration || !this.registration.waiting) return;

        // 새로운 서비스 워커에게 활성화 신호 전송
        this.registration.waiting.postMessage({ type: 'SKIP_WAITING' });
    }

    /**
     * 업데이트 알림 표시
     * @private
     */
    showUpdateNotification() {
        eventBus.emit('toast:show', {
            message: '새로운 업데이트가 있습니다.',
            type: 'info',
            duration: 0, // 자동 사라지지 않음
            action: {
                text: '업데이트',
                handler: () => this.applyUpdate()
            }
        });

        eventBus.emit('sw:update_available');
    }

    /**
     * 서비스 워커 메시지 처리
     * @param {Object} data - 메시지 데이터
     * @private
     */
    handleServiceWorkerMessage(data) {
        switch (data.type) {
            case 'CACHE_UPDATED':
                eventBus.emit('sw:cache_updated', data);
                break;
            case 'OFFLINE_PAGE_READY':
                eventBus.emit('sw:offline_ready', data);
                break;
            case 'BACKGROUND_SYNC':
                eventBus.emit('sw:background_sync', data);
                break;
        }
    }

    /**
     * 온라인 상태 처리
     * @private
     */
    handleOnline() {
        console.log('🌐 온라인 상태로 변경');
        
        eventBus.emit('sw:online');
        
        // 백그라운드 동기화 트리거
        if (this.registration && this.registration.sync) {
            this.registration.sync.register('background-sync');
        }
        
        // 오프라인 알림 숨기기
        eventBus.emit('toast:hide', { tag: 'offline' });
    }

    /**
     * 오프라인 상태 처리
     * @private
     */
    handleOffline() {
        console.log('📱 오프라인 상태로 변경');
        
        eventBus.emit('sw:offline');
        
        // 오프라인 알림 표시
        eventBus.emit('toast:show', {
            message: '오프라인 모드입니다. 일부 기능이 제한될 수 있습니다.',
            type: 'warning',
            duration: 0,
            tag: 'offline'
        });
    }

    /**
     * 캐시 관리
     * @returns {Promise<void>}
     */
    async manageCache() {
        if (!this.isSupported) return;

        try {
            const cacheNames = await caches.keys();
            console.log('📦 현재 캐시 목록:', cacheNames);

            // 캐시 크기 확인
            for (const cacheName of cacheNames) {
                const cache = await caches.open(cacheName);
                const keys = await cache.keys();
                console.log(`📦 ${cacheName}: ${keys.length}개 항목`);
            }

        } catch (error) {
            console.error('❌ 캐시 관리 실패:', error);
        }
    }

    /**
     * 캐시 클리어
     * @param {string} [cacheName] - 특정 캐시 이름 (없으면 모든 캐시)
     * @returns {Promise<void>}
     */
    async clearCache(cacheName = null) {
        if (!this.isSupported) return;

        try {
            if (cacheName) {
                await caches.delete(cacheName);
                console.log(`🗑️ ${cacheName} 캐시 삭제 완료`);
            } else {
                const cacheNames = await caches.keys();
                await Promise.all(
                    cacheNames.map(name => caches.delete(name))
                );
                console.log('🗑️ 모든 캐시 삭제 완료');
            }

            eventBus.emit('sw:cache_cleared', { cacheName });

        } catch (error) {
            console.error('❌ 캐시 삭제 실패:', error);
        }
    }

    /**
     * 오프라인 데이터 저장
     * @param {string} key - 데이터 키
     * @param {any} data - 저장할 데이터
     * @returns {Promise<void>}
     */
    async saveOfflineData(key, data) {
        try {
            const offlineData = JSON.parse(localStorage.getItem('offline_data') || '{}');
            offlineData[key] = {
                data,
                timestamp: Date.now()
            };
            localStorage.setItem('offline_data', JSON.stringify(offlineData));
            
            console.log('💾 오프라인 데이터 저장:', key);

        } catch (error) {
            console.error('❌ 오프라인 데이터 저장 실패:', error);
        }
    }

    /**
     * 오프라인 데이터 가져오기
     * @param {string} key - 데이터 키
     * @returns {any} 저장된 데이터
     */
    getOfflineData(key) {
        try {
            const offlineData = JSON.parse(localStorage.getItem('offline_data') || '{}');
            return offlineData[key]?.data || null;

        } catch (error) {
            console.error('❌ 오프라인 데이터 조회 실패:', error);
            return null;
        }
    }

    /**
     * 푸시 알림 구독
     * @returns {Promise<PushSubscription>}
     */
    async subscribeToPush() {
        if (!this.registration) {
            throw new Error('서비스 워커가 등록되지 않았습니다.');
        }

        try {
            const subscription = await this.registration.pushManager.subscribe({
                userVisibleOnly: true,
                applicationServerKey: this.getVapidPublicKey()
            });

            console.log('🔔 푸시 알림 구독 완료');
            
            // 서버에 구독 정보 전송
            await this.sendSubscriptionToServer(subscription);
            
            return subscription;

        } catch (error) {
            console.error('❌ 푸시 알림 구독 실패:', error);
            throw error;
        }
    }

    /**
     * VAPID 공개 키 가져오기
     * @returns {Uint8Array} VAPID 공개 키
     * @private
     */
    getVapidPublicKey() {
        // 실제 구현에서는 환경 변수에서 가져옴
        const vapidPublicKey = 'YOUR_VAPID_PUBLIC_KEY';
        
        return new Uint8Array(
            atob(vapidPublicKey.replace(/-/g, '+').replace(/_/g, '/'))
                .split('')
                .map(char => char.charCodeAt(0))
        );
    }

    /**
     * 구독 정보를 서버에 전송
     * @param {PushSubscription} subscription - 구독 정보
     * @private
     */
    async sendSubscriptionToServer(subscription) {
        try {
            await fetch('/api/push/subscribe', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json'
                },
                body: JSON.stringify(subscription)
            });

        } catch (error) {
            console.error('❌ 구독 정보 전송 실패:', error);
        }
    }

    /**
     * 서비스 워커 등록 해제
     * @returns {Promise<void>}
     */
    async unregister() {
        if (!this.registration) return;

        try {
            await this.registration.unregister();
            console.log('✅ 서비스 워커 등록 해제 완료');
            
            this.registration = null;
            this.isRegistered = false;
            
            eventBus.emit('sw:unregistered');

        } catch (error) {
            console.error('❌ 서비스 워커 등록 해제 실패:', error);
        }
    }

    /**
     * 서비스 워커 상태 가져오기
     * @returns {Object} 상태 정보
     */
    getStatus() {
        return {
            isSupported: this.isSupported,
            isRegistered: this.isRegistered,
            updateAvailable: this.updateAvailable,
            isOnline: this.isOnline,
            registration: this.registration ? {
                scope: this.registration.scope,
                state: this.registration.active?.state || 'unknown'
            } : null
        };
    }

    /**
     * 서비스 워커 통계 가져오기
     * @returns {Promise<Object>} 통계 정보
     */
    async getStats() {
        if (!this.isSupported) return null;

        try {
            const cacheNames = await caches.keys();
            const stats = {
                cacheCount: cacheNames.length,
                caches: {}
            };

            for (const cacheName of cacheNames) {
                const cache = await caches.open(cacheName);
                const keys = await cache.keys();
                stats.caches[cacheName] = keys.length;
            }

            return stats;

        } catch (error) {
            console.error('❌ 서비스 워커 통계 조회 실패:', error);
            return null;
        }
    }
}

// 전역 서비스 워커 관리자 인스턴스
export const serviceWorkerManager = new ServiceWorkerManager();

// 개발 모드에서 전역 접근 가능하게 설정
if (typeof window !== 'undefined' && process.env.NODE_ENV === 'development') {
    window.__SERVICE_WORKER_MANAGER__ = serviceWorkerManager;
}
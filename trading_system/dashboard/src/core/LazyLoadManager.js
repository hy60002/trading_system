/**
 * @fileoverview Lazy Loading 및 리소스 최적화 매니저
 * @description 이미지, 아이콘, 컴포넌트의 지연 로딩 시스템
 */

/**
 * Lazy Loading 매니저
 * @class LazyLoadManager
 */
export class LazyLoadManager {
    constructor() {
        this.intersectionObserver = null;
        this.lazyElements = new Set();
        this.loadedElements = new WeakSet();
        this.loadingQueue = [];
        this.isProcessingQueue = false;
        
        // 설정
        this.config = {
            rootMargin: '50px 0px',
            threshold: 0.1,
            maxConcurrentLoads: 3,
            retryAttempts: 3,
            retryDelay: 1000,
            enableWebP: this.supportsWebP(),
            enableAvif: this.supportsAvif()
        };
        
        // 성능 메트릭
        this.metrics = {
            totalElements: 0,
            loadedElements: 0,
            failedLoads: 0,
            averageLoadTime: 0,
            totalLoadTime: 0,
            savedBytes: 0
        };
        
        // 캐시 시스템
        this.imageCache = new Map();
        this.preloadCache = new Set();
        
        // 아이콘 스프라이트 관리
        this.iconSprites = new Map();
        this.iconSpritePromises = new Map();
        
        this.initialize();
    }

    /**
     * 초기화
     * @private
     */
    initialize() {
        this.setupIntersectionObserver();
        this.setupImageCache();
        this.preloadCriticalResources();
        
        // 네트워크 상태 모니터링
        if ('connection' in navigator) {
            this.adaptToNetworkConditions();
        }
    }

    /**
     * Intersection Observer 설정
     * @private
     */
    setupIntersectionObserver() {
        if (!('IntersectionObserver' in window)) {
            console.warn('IntersectionObserver not supported, falling back to immediate loading');
            this.fallbackToImmediateLoading();
            return;
        }

        this.intersectionObserver = new IntersectionObserver(
            this.handleIntersection.bind(this),
            {
                rootMargin: this.config.rootMargin,
                threshold: this.config.threshold
            }
        );
    }

    /**
     * 교차점 처리
     * @param {IntersectionObserverEntry[]} entries - 교차 엔트리들
     * @private
     */
    handleIntersection(entries) {
        entries.forEach(entry => {
            if (entry.isIntersecting) {
                this.loadElement(entry.target);
                this.intersectionObserver.unobserve(entry.target);
            }
        });
    }

    /**
     * 이미지 캐시 설정
     * @private
     */
    setupImageCache() {
        // Service Worker가 있으면 캐시 제어 향상
        if ('serviceWorker' in navigator) {
            this.setupServiceWorkerCaching();
        }
        
        // 메모리 기반 캐시 크기 제한
        this.maxCacheSize = 50; // 50개 이미지까지 캐시
    }

    /**
     * Service Worker 캐싱 설정
     * @private
     */
    setupServiceWorkerCaching() {
        navigator.serviceWorker.ready.then(registration => {
            console.log('Service Worker ready for cache management');
            
            // 캐시 전략 설정 메시지 전송
            registration.active?.postMessage({
                type: 'CACHE_STRATEGY',
                strategy: 'staleWhileRevalidate',
                resources: ['images', 'icons', 'fonts']
            });
        });
    }

    /**
     * 중요한 리소스 미리 로드
     * @private
     */
    async preloadCriticalResources() {
        const criticalResources = [
            '/assets/icons/sprite-critical.svg',
            '/assets/images/logo.webp',
            '/assets/fonts/inter-var.woff2'
        ];

        for (const resource of criticalResources) {
            try {
                await this.preloadResource(resource);
                this.preloadCache.add(resource);
            } catch (error) {
                console.warn(`Failed to preload critical resource: ${resource}`, error);
            }
        }
    }

    /**
     * 리소스 미리 로드
     * @param {string} url - 리소스 URL
     * @param {string} type - 리소스 타입
     * @returns {Promise} 로드 Promise
     * @private
     */
    preloadResource(url, type = 'image') {
        return new Promise((resolve, reject) => {
            if (type === 'image') {
                const img = new Image();
                img.onload = () => resolve(img);
                img.onerror = reject;
                img.src = url;
            } else {
                // 다른 리소스 타입들 (CSS, JS, 폰트 등)
                const link = document.createElement('link');
                link.rel = 'preload';
                link.as = type;
                link.href = url;
                link.onload = resolve;
                link.onerror = reject;
                document.head.appendChild(link);
            }
        });
    }

    /**
     * 네트워크 상황에 따른 적응
     * @private
     */
    adaptToNetworkConditions() {
        const connection = navigator.connection;
        
        // 느린 연결에서는 로딩 전략 조정
        if (connection.effectiveType === 'slow-2g' || connection.effectiveType === '2g') {
            this.config.maxConcurrentLoads = 1;
            this.config.rootMargin = '10px 0px'; // 더 가까이 와야 로드
            this.config.enableWebP = false; // WebP 비활성화
        } else if (connection.effectiveType === '3g') {
            this.config.maxConcurrentLoads = 2;
            this.config.rootMargin = '30px 0px';
        }
        
        // 연결 상태 변경 모니터링
        connection.addEventListener('change', () => {
            this.adaptToNetworkConditions();
        });
    }

    /**
     * Lazy Loading 요소 등록
     * @param {HTMLElement} element - 대상 요소
     * @param {Object} options - 옵션
     */
    observe(element, options = {}) {
        if (this.loadedElements.has(element)) {
            return; // 이미 로드됨
        }

        // 요소 메타데이터 설정
        this.setElementMetadata(element, options);
        
        // 옵저버에 등록
        this.lazyElements.add(element);
        this.metrics.totalElements++;
        
        if (this.intersectionObserver) {
            this.intersectionObserver.observe(element);
        } else {
            // Fallback: 즉시 로드
            this.loadElement(element);
        }
    }

    /**
     * 요소 메타데이터 설정
     * @param {HTMLElement} element - 요소
     * @param {Object} options - 옵션
     * @private
     */
    setElementMetadata(element, options) {
        element._lazyLoadOptions = {
            placeholder: options.placeholder || 'data:image/svg+xml;base64,PHN2ZyB3aWR0aD0iMTAwIiBoZWlnaHQ9IjEwMCIgeG1sbnM9Imh0dHA6Ly93d3cudzMub3JnLzIwMDAvc3ZnIj48cmVjdCB3aWR0aD0iMTAwJSIgaGVpZ2h0PSIxMDAlIiBmaWxsPSIjZGRkIi8+PC9zdmc+',
            errorPlaceholder: options.errorPlaceholder || '/assets/images/error-placeholder.svg',
            retryCount: 0,
            loadStartTime: null,
            priority: options.priority || 'normal',
            onLoad: options.onLoad,
            onError: options.onError,
            transformations: options.transformations || {}
        };
        
        // 플레이스홀더 설정
        if (element.tagName === 'IMG' && !element.src) {
            element.src = element._lazyLoadOptions.placeholder;
        }
    }

    /**
     * 요소 로드
     * @param {HTMLElement} element - 로드할 요소
     * @private
     */
    async loadElement(element) {
        if (this.loadedElements.has(element)) {
            return;
        }

        const metadata = element._lazyLoadOptions;
        metadata.loadStartTime = performance.now();

        try {
            await this.loadElementByType(element);
            this.handleLoadSuccess(element);
        } catch (error) {
            this.handleLoadError(element, error);
        }
    }

    /**
     * 타입별 요소 로드
     * @param {HTMLElement} element - 요소
     * @returns {Promise} 로드 Promise
     * @private
     */
    async loadElementByType(element) {
        const tagName = element.tagName.toLowerCase();
        
        switch (tagName) {
            case 'img':
                return this.loadImage(element);
            case 'picture':
                return this.loadPicture(element);
            case 'iframe':
                return this.loadIframe(element);
            case 'video':
                return this.loadVideo(element);
            default:
                if (element.hasAttribute('data-lazy-component')) {
                    return this.loadComponent(element);
                }
                throw new Error(`Unsupported element type: ${tagName}`);
        }
    }

    /**
     * 이미지 로드
     * @param {HTMLImageElement} img - 이미지 요소
     * @returns {Promise} 로드 Promise
     * @private
     */
    async loadImage(img) {
        const dataSrc = img.getAttribute('data-src');
        if (!dataSrc) {
            throw new Error('No data-src attribute found');
        }

        // 최적화된 URL 생성
        const optimizedUrl = this.getOptimizedImageUrl(dataSrc, img);
        
        // 캐시 확인
        if (this.imageCache.has(optimizedUrl)) {
            const cachedImage = this.imageCache.get(optimizedUrl);
            img.src = cachedImage.src;
            return Promise.resolve();
        }

        // 새 이미지 로드
        return new Promise((resolve, reject) => {
            const newImg = new Image();
            
            newImg.onload = () => {
                // 캐시에 저장
                this.addToImageCache(optimizedUrl, newImg);
                
                // 크로스페이드 애니메이션
                this.applyCrossfadeEffect(img, newImg.src);
                
                resolve();
            };
            
            newImg.onerror = () => {
                reject(new Error(`Failed to load image: ${optimizedUrl}`));
            };
            
            newImg.src = optimizedUrl;
        });
    }

    /**
     * Picture 요소 로드
     * @param {HTMLElement} picture - Picture 요소
     * @returns {Promise} 로드 Promise
     * @private
     */
    async loadPicture(picture) {
        const img = picture.querySelector('img');
        if (!img) {
            throw new Error('No img element found in picture');
        }

        // source 요소들 처리
        const sources = picture.querySelectorAll('source[data-srcset]');
        sources.forEach(source => {
            const dataSrcset = source.getAttribute('data-srcset');
            if (dataSrcset) {
                source.srcset = dataSrcset;
                source.removeAttribute('data-srcset');
            }
        });

        // img 요소 로드
        return this.loadImage(img);
    }

    /**
     * 최적화된 이미지 URL 생성
     * @param {string} originalUrl - 원본 URL
     * @param {HTMLImageElement} img - 이미지 요소
     * @returns {string} 최적화된 URL
     * @private
     */
    getOptimizedImageUrl(originalUrl, img) {
        let url = originalUrl;
        
        // 반응형 크기 조정
        const rect = img.getBoundingClientRect();
        const dpr = window.devicePixelRatio || 1;
        const width = Math.ceil(rect.width * dpr);
        const height = Math.ceil(rect.height * dpr);
        
        // 이미지 서비스가 있다면 크기 파라미터 추가
        if (this.hasImageService(url)) {
            url = this.addImageServiceParams(url, { width, height });
        }
        
        // WebP/AVIF 지원 확인
        if (this.config.enableAvif && this.supportsAvif()) {
            url = this.convertToFormat(url, 'avif');
        } else if (this.config.enableWebP && this.supportsWebP()) {
            url = this.convertToFormat(url, 'webp');
        }
        
        return url;
    }

    /**
     * 이미지 서비스 파라미터 추가
     * @param {string} url - 원본 URL
     * @param {Object} params - 파라미터
     * @returns {string} 수정된 URL
     * @private
     */
    addImageServiceParams(url, params) {
        const urlObj = new URL(url, window.location.origin);
        
        Object.entries(params).forEach(([key, value]) => {
            urlObj.searchParams.set(key, value);
        });
        
        return urlObj.toString();
    }

    /**
     * 크로스페이드 효과 적용
     * @param {HTMLImageElement} img - 이미지 요소
     * @param {string} newSrc - 새 이미지 소스
     * @private
     */
    applyCrossfadeEffect(img, newSrc) {
        img.style.transition = 'opacity 0.3s ease-in-out';
        img.style.opacity = '0';
        
        setTimeout(() => {
            img.src = newSrc;
            img.style.opacity = '1';
            
            // 트랜지션 정리
            setTimeout(() => {
                img.style.transition = '';
            }, 300);
        }, 50);
    }

    /**
     * 이미지 캐시에 추가
     * @param {string} url - URL
     * @param {HTMLImageElement} img - 이미지
     * @private
     */
    addToImageCache(url, img) {
        // 캐시 크기 제한
        if (this.imageCache.size >= this.maxCacheSize) {
            const firstKey = this.imageCache.keys().next().value;
            this.imageCache.delete(firstKey);
        }
        
        this.imageCache.set(url, {
            src: img.src,
            width: img.naturalWidth,
            height: img.naturalHeight,
            size: this.estimateImageSize(img),
            timestamp: Date.now()
        });
    }

    /**
     * 아이콘 스프라이트 로드
     * @param {string} spriteId - 스프라이트 ID
     * @returns {Promise} 로드 Promise
     */
    async loadIconSprite(spriteId) {
        if (this.iconSprites.has(spriteId)) {
            return this.iconSprites.get(spriteId);
        }

        if (this.iconSpritePromises.has(spriteId)) {
            return this.iconSpritePromises.get(spriteId);
        }

        const promise = this.fetchIconSprite(spriteId);
        this.iconSpritePromises.set(spriteId, promise);

        try {
            const spriteData = await promise;
            this.iconSprites.set(spriteId, spriteData);
            this.iconSpritePromises.delete(spriteId);
            return spriteData;
        } catch (error) {
            this.iconSpritePromises.delete(spriteId);
            throw error;
        }
    }

    /**
     * 아이콘 스프라이트 페치
     * @param {string} spriteId - 스프라이트 ID
     * @returns {Promise} 페치 Promise
     * @private
     */
    async fetchIconSprite(spriteId) {
        const spriteUrl = `/assets/icons/${spriteId}.svg`;
        
        try {
            const response = await fetch(spriteUrl);
            if (!response.ok) {
                throw new Error(`Failed to fetch sprite: ${response.status}`);
            }
            
            const svgText = await response.text();
            
            // SVG를 DOM에 삽입
            const div = document.createElement('div');
            div.innerHTML = svgText;
            div.style.position = 'absolute';
            div.style.width = '0';
            div.style.height = '0';
            div.style.overflow = 'hidden';
            
            document.body.appendChild(div);
            
            return {
                element: div,
                symbols: this.extractSymbols(div)
            };
            
        } catch (error) {
            console.error(`Failed to load icon sprite ${spriteId}:`, error);
            throw error;
        }
    }

    /**
     * SVG 심볼 추출
     * @param {HTMLElement} container - 컨테이너 요소
     * @returns {Set} 심볼 ID 집합
     * @private
     */
    extractSymbols(container) {
        const symbols = new Set();
        const symbolElements = container.querySelectorAll('symbol[id]');
        
        symbolElements.forEach(symbol => {
            symbols.add(symbol.id);
        });
        
        return symbols;
    }

    /**
     * 아이콘 요소 생성
     * @param {string} spriteId - 스프라이트 ID
     * @param {string} iconId - 아이콘 ID
     * @param {Object} options - 옵션
     * @returns {Promise<SVGElement>} SVG 요소
     */
    async createIcon(spriteId, iconId, options = {}) {
        await this.loadIconSprite(spriteId);
        
        const svg = document.createElementNS('http://www.w3.org/2000/svg', 'svg');
        const use = document.createElementNS('http://www.w3.org/2000/svg', 'use');
        
        use.setAttributeNS('http://www.w3.org/1999/xlink', 'xlink:href', `#${iconId}`);
        svg.appendChild(use);
        
        // 옵션 적용
        if (options.className) {
            svg.className = options.className;
        }
        
        if (options.size) {
            svg.setAttribute('width', options.size);
            svg.setAttribute('height', options.size);
        }
        
        if (options.color) {
            svg.style.fill = options.color;
        }
        
        return svg;
    }

    /**
     * 로드 성공 처리
     * @param {HTMLElement} element - 요소
     * @private
     */
    handleLoadSuccess(element) {
        const metadata = element._lazyLoadOptions;
        const loadTime = performance.now() - metadata.loadStartTime;
        
        // 성공 상태 설정
        this.loadedElements.add(element);
        this.lazyElements.delete(element);
        element.classList.add('lazy-loaded');
        element.classList.remove('lazy-loading', 'lazy-error');
        
        // 메트릭 업데이트
        this.metrics.loadedElements++;
        this.metrics.totalLoadTime += loadTime;
        this.metrics.averageLoadTime = this.metrics.totalLoadTime / this.metrics.loadedElements;
        
        // 콜백 실행
        if (metadata.onLoad) {
            metadata.onLoad(element, loadTime);
        }
        
        // 이벤트 발생
        element.dispatchEvent(new CustomEvent('lazyloaded', {
            detail: { element, loadTime }
        }));
    }

    /**
     * 로드 실패 처리
     * @param {HTMLElement} element - 요소
     * @param {Error} error - 에러
     * @private
     */
    handleLoadError(element, error) {
        const metadata = element._lazyLoadOptions;
        metadata.retryCount++;
        
        console.error('Lazy load failed:', error, element);
        
        // 재시도 로직
        if (metadata.retryCount < this.config.retryAttempts) {
            setTimeout(() => {
                this.loadElement(element);
            }, this.config.retryDelay * metadata.retryCount);
            return;
        }
        
        // 최대 재시도 횟수 초과
        this.metrics.failedLoads++;
        element.classList.add('lazy-error');
        element.classList.remove('lazy-loading');
        
        // 에러 플레이스홀더 설정
        if (element.tagName === 'IMG' && metadata.errorPlaceholder) {
            element.src = metadata.errorPlaceholder;
        }
        
        // 콜백 실행
        if (metadata.onError) {
            metadata.onError(element, error);
        }
        
        // 이벤트 발생
        element.dispatchEvent(new CustomEvent('lazyerror', {
            detail: { element, error }
        }));
    }

    // 유틸리티 메서드들

    /**
     * WebP 지원 확인
     * @returns {boolean} 지원 여부
     * @private
     */
    supportsWebP() {
        if (!('createImageBitmap' in window)) return false;
        
        const canvas = document.createElement('canvas');
        canvas.width = 1;
        canvas.height = 1;
        
        return canvas.toDataURL('image/webp').indexOf('data:image/webp') === 0;
    }

    /**
     * AVIF 지원 확인
     * @returns {boolean} 지원 여부
     * @private
     */
    supportsAvif() {
        const avif = 'data:image/avif;base64,AAAAIGZ0eXBhdmlmAAAAAGF2aWZtaWYxbWlhZk1BMUIAAADybWV0YQAAAAAAAAAoaGRscgAAAAAAAAAAcGljdAAAAAAAAAAAAAAAAGxpYmF2aWYAAAAADnBpdG0AAAAAAAEAAAAeaWxvYwAAAABEAAABAAEAAAABAAABGgAAACAAAAAoaWluZgAAAAAAAQAAABppbmZlAgAAAAABAABhdjAxQ29sb3IAAAAAamlwcnAAAABLaXBjbwAAABRpc3BlAAAAAAAAAAEAAAABAAAAEHBpeGkAAAAAAwgICAAAAAxhdjFDgQ0MAAAAABNjb2xybmNseAACAAIAAYAAAAAXaXBtYQAAAAAAAAABAAEEAQKDBAAAACVtZGF0EgAKCBgABogQEAwgMg';
        
        const img = new Image();
        img.src = avif;
        
        return new Promise(resolve => {
            img.onload = () => resolve(true);
            img.onerror = () => resolve(false);
        });
    }

    /**
     * 이미지 서비스 확인
     * @param {string} url - URL
     * @returns {boolean} 서비스 지원 여부
     * @private
     */
    hasImageService(url) {
        const imageServices = [
            'cloudinary.com',
            'imgix.net',
            'images.unsplash.com'
        ];
        
        return imageServices.some(service => url.includes(service));
    }

    /**
     * 포맷 변환
     * @param {string} url - URL
     * @param {string} format - 새 포맷
     * @returns {string} 변환된 URL
     * @private
     */
    convertToFormat(url, format) {
        // 실제 구현에서는 이미지 서비스 API에 따라 달라짐
        if (url.includes('cloudinary.com')) {
            return url.replace(/\.(jpg|jpeg|png)/, `.${format}`);
        }
        
        // 기본적으로는 확장자만 변경
        return url.replace(/\.(jpg|jpeg|png)$/i, `.${format}`);
    }

    /**
     * 이미지 크기 추정
     * @param {HTMLImageElement} img - 이미지
     * @returns {number} 예상 크기 (bytes)
     * @private
     */
    estimateImageSize(img) {
        const pixels = img.naturalWidth * img.naturalHeight;
        const bytesPerPixel = 3; // RGB 평균
        return pixels * bytesPerPixel;
    }

    /**
     * 즉시 로딩 폴백
     * @private
     */
    fallbackToImmediateLoading() {
        // IntersectionObserver를 지원하지 않는 브라우저용 폴백
        this.observe = (element) => {
            setTimeout(() => this.loadElement(element), 100);
        };
    }

    /**
     * 모든 요소 로드 (디버깅용)
     */
    loadAll() {
        this.lazyElements.forEach(element => {
            this.loadElement(element);
        });
    }

    /**
     * 특정 요소 강제 로드
     * @param {HTMLElement} element - 요소
     */
    forceLoad(element) {
        if (this.intersectionObserver) {
            this.intersectionObserver.unobserve(element);
        }
        this.loadElement(element);
    }

    /**
     * 메트릭 반환
     * @returns {Object} 성능 메트릭
     */
    getMetrics() {
        return {
            ...this.metrics,
            cacheSize: this.imageCache.size,
            preloadCacheSize: this.preloadCache.size,
            iconSprites: this.iconSprites.size,
            loadSuccessRate: this.metrics.totalElements > 0 ? 
                (this.metrics.loadedElements / this.metrics.totalElements) * 100 : 0
        };
    }

    /**
     * 캐시 클리어
     */
    clearCache() {
        this.imageCache.clear();
        this.preloadCache.clear();
    }

    /**
     * 정리
     */
    destroy() {
        if (this.intersectionObserver) {
            this.intersectionObserver.disconnect();
        }
        
        this.lazyElements.clear();
        this.imageCache.clear();
        this.preloadCache.clear();
        this.iconSprites.clear();
        this.iconSpritePromises.clear();
    }
}

// 전역 Lazy Load 매니저 인스턴스
export const lazyLoadManager = new LazyLoadManager();

// 편의 함수들
export const lazyLoad = (element, options) => lazyLoadManager.observe(element, options);
export const loadIconSprite = (spriteId) => lazyLoadManager.loadIconSprite(spriteId);
export const createIcon = (spriteId, iconId, options) => lazyLoadManager.createIcon(spriteId, iconId, options);

// 개발 모드에서 전역 접근 가능
if (typeof window !== 'undefined' && process.env.NODE_ENV === 'development') {
    window.__TRADING_DASHBOARD_LAZY_LOAD__ = lazyLoadManager;
}
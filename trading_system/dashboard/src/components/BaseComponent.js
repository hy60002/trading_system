/**
 * @fileoverview 기본 컴포넌트 클래스
 * @description 모든 컴포넌트가 상속받는 기본 클래스
 */

import { eventBus } from '../core/EventBus.js';
import { globalStore } from '../core/Store.js';
import { vdom } from '../core/VirtualDOM.js';

/**
 * 기본 컴포넌트 클래스
 * @class BaseComponent
 */
export class BaseComponent {
    /**
     * @param {HTMLElement|string} container - 컨테이너 엘리먼트 또는 선택자
     * @param {Object} props - 컴포넌트 속성
     * @param {Object} options - 추가 옵션
     */
    constructor(container, props = {}, options = {}) {
        this.container = typeof container === 'string' ? 
            document.querySelector(container) : container;
        
        if (!this.container) {
            throw new Error(`Container not found: ${container}`);
        }

        this.props = { ...props };
        this.state = { ...this.getInitialState() };
        this.previousState = null;
        this.options = {
            autoRender: true,
            subscribeToStore: true,
            enableVirtualDOM: true,
            ...options
        };

        // 컴포넌트 메타데이터
        this.componentId = this.generateComponentId();
        this.componentName = this.constructor.name;
        this.isDestroyed = false;
        this.isMounted = false;
        this.renderCount = 0;

        // 바인딩된 메서드들
        this.boundMethods = new Set();
        
        // 이벤트 리스너들
        this.eventListeners = new Map();
        this.storeSubscriptions = new Set();
        
        // 가상 DOM 관련
        this.currentVNode = null;
        this.shadowRoot = null;
        
        // 라이프사이클 상태
        this.lifecycleState = 'created';
        
        // 성능 메트릭
        this.performanceMetrics = {
            renderTimes: [],
            averageRenderTime: 0,
            lastRenderTime: 0
        };

        this.initialize();
    }

    /**
     * 컴포넌트 초기화
     * @private
     */
    initialize() {
        this.bindMethods();
        this.setupEventListeners();
        
        if (this.options.subscribeToStore) {
            this.subscribeToStore();
        }
        
        if (this.options.autoRender) {
            this.mount();
        }
        
        this.lifecycleState = 'initialized';
        this.onInitialized();
    }

    /**
     * 컴포넌트 ID 생성
     * @returns {string} 고유 ID
     * @private
     */
    generateComponentId() {
        return `${this.constructor.name}_${Date.now()}_${Math.random().toString(36).substr(2, 9)}`;
    }

    /**
     * 초기 상태 반환
     * @returns {Object} 초기 상태
     * @protected
     */
    getInitialState() {
        return {};
    }

    /**
     * 메서드 바인딩
     * @private
     */
    bindMethods() {
        const proto = Object.getPrototypeOf(this);
        const methods = Object.getOwnPropertyNames(proto)
            .filter(name => {
                const descriptor = Object.getOwnPropertyDescriptor(proto, name);
                return descriptor && 
                       typeof descriptor.value === 'function' && 
                       name !== 'constructor' &&
                       !name.startsWith('_');
            });

        methods.forEach(methodName => {
            if (typeof this[methodName] === 'function') {
                this[methodName] = this[methodName].bind(this);
                this.boundMethods.add(methodName);
            }
        });
    }

    /**
     * 이벤트 리스너 설정
     * @private
     */
    setupEventListeners() {
        // 기본 이벤트 리스너들
        this.addEventListener('resize', this.handleResize);
        
        // 커스텀 이벤트 리스너 설정
        this.setupCustomEventListeners();
    }

    /**
     * 커스텀 이벤트 리스너 설정 (오버라이드용)
     * @protected
     */
    setupCustomEventListeners() {
        // 서브클래스에서 구현
    }

    /**
     * 스토어 구독
     * @private
     */
    subscribeToStore() {
        const storeSelectors = this.getStoreSelectors();
        
        storeSelectors.forEach(selector => {
            const unsubscribe = globalStore.subscribe(
                (state, fullState, action) => {
                    this.onStoreUpdate(state, fullState, action, selector);
                },
                selector
            );
            
            this.storeSubscriptions.add(unsubscribe);
        });
    }

    /**
     * 스토어 선택자 반환 (오버라이드용)
     * @returns {Array<string>} 선택자 배열
     * @protected
     */
    getStoreSelectors() {
        return [];
    }

    /**
     * 스토어 업데이트 처리
     * @param {*} selectedState - 선택된 상태
     * @param {Object} fullState - 전체 상태
     * @param {Object} action - 액션
     * @param {string} selector - 선택자
     * @protected
     */
    onStoreUpdate(selectedState, fullState, action, selector) {
        if (!this.isMounted || this.isDestroyed) return;
        
        const shouldUpdate = this.shouldUpdateOnStoreChange(
            selectedState, 
            fullState, 
            action, 
            selector
        );
        
        if (shouldUpdate) {
            this.forceUpdate();
        }
    }

    /**
     * 스토어 변경 시 업데이트 여부 결정
     * @param {*} selectedState - 선택된 상태
     * @param {Object} fullState - 전체 상태
     * @param {Object} action - 액션
     * @param {string} selector - 선택자
     * @returns {boolean} 업데이트 여부
     * @protected
     */
    shouldUpdateOnStoreChange(selectedState, fullState, action, selector) {
        return true; // 기본적으로 항상 업데이트
    }

    /**
     * 컴포넌트 마운트
     */
    mount() {
        if (this.isMounted || this.isDestroyed) return;
        
        this.lifecycleState = 'mounting';
        this.onBeforeMount();
        
        try {
            this.render();
            this.isMounted = true;
            this.lifecycleState = 'mounted';
            this.onMounted();
            
            // 마운트 이벤트 발생
            eventBus.emit('component:mounted', {
                componentId: this.componentId,
                componentName: this.componentName
            });
            
        } catch (error) {
            console.error(`Component mount failed (${this.componentName}):`, error);
            this.onMountError(error);
        }
    }

    /**
     * 컴포넌트 언마운트
     */
    unmount() {
        if (!this.isMounted || this.isDestroyed) return;
        
        this.lifecycleState = 'unmounting';
        this.onBeforeUnmount();
        
        try {
            this.cleanup();
            this.isMounted = false;
            this.lifecycleState = 'unmounted';
            this.onUnmounted();
            
            // 언마운트 이벤트 발생
            eventBus.emit('component:unmounted', {
                componentId: this.componentId,
                componentName: this.componentName
            });
            
        } catch (error) {
            console.error(`Component unmount failed (${this.componentName}):`, error);
            this.onUnmountError(error);
        }
    }

    /**
     * 컴포넌트 렌더링
     */
    render() {
        if (this.isDestroyed) return;
        
        const startTime = performance.now();
        this.renderCount++;
        
        try {
            if (this.options.enableVirtualDOM) {
                this.renderWithVirtualDOM();
            } else {
                this.renderDirectly();
            }
            
            // 성능 메트릭 업데이트
            const renderTime = performance.now() - startTime;
            this.updatePerformanceMetrics(renderTime);
            
            this.onAfterRender();
            
        } catch (error) {
            console.error(`Component render failed (${this.componentName}):`, error);
            this.onRenderError(error);
        }
    }

    /**
     * 가상 DOM을 사용한 렌더링
     * @private
     */
    renderWithVirtualDOM() {
        const newVNode = this.createVNode();
        
        if (this.currentVNode) {
            // 차이점 계산 및 패치 적용
            const patches = vdom.diff(this.currentVNode, newVNode);
            vdom.patch(this.container, patches);
        } else {
            // 첫 렌더링
            const element = vdom.render(newVNode);
            this.container.innerHTML = '';
            this.container.appendChild(element);
        }
        
        this.currentVNode = newVNode;
    }

    /**
     * 직접 렌더링
     * @private
     */
    renderDirectly() {
        const html = this.template();
        this.container.innerHTML = html;
        this.bindEventHandlers();
    }

    /**
     * 가상 노드 생성 (오버라이드용)
     * @returns {VNode} 가상 노드
     * @protected
     */
    createVNode() {
        // 기본 구현: HTML 문자열을 가상 노드로 변환
        const html = this.template();
        return this.htmlToVNode(html);
    }

    /**
     * HTML 문자열을 가상 노드로 변환
     * @param {string} html - HTML 문자열
     * @returns {VNode} 가상 노드
     * @private
     */
    htmlToVNode(html) {
        // 간단한 HTML 파서 (실제로는 더 복잡한 구현 필요)
        const tempDiv = document.createElement('div');
        tempDiv.innerHTML = html;
        
        return this.domToVNode(tempDiv.firstElementChild || tempDiv);
    }

    /**
     * DOM 엘리먼트를 가상 노드로 변환
     * @param {HTMLElement} element - DOM 엘리먼트
     * @returns {VNode} 가상 노드
     * @private
     */
    domToVNode(element) {
        if (element.nodeType === Node.TEXT_NODE) {
            return vdom.createTextNode(element.textContent);
        }
        
        const props = {};
        const attributes = element.attributes;
        
        for (let i = 0; i < attributes.length; i++) {
            const attr = attributes[i];
            props[attr.name] = attr.value;
        }
        
        const children = Array.from(element.childNodes)
            .map(child => this.domToVNode(child));
        
        return vdom.createElement(element.tagName.toLowerCase(), props, ...children);
    }

    /**
     * 템플릿 반환 (오버라이드용)
     * @returns {string} HTML 템플릿
     * @protected
     */
    template() {
        return '<div>Base Component</div>';
    }

    /**
     * 이벤트 핸들러 바인딩
     * @protected
     */
    bindEventHandlers() {
        // 서브클래스에서 구현
    }

    /**
     * 상태 업데이트
     * @param {Object|Function} newState - 새로운 상태 또는 상태 업데이트 함수
     * @param {boolean} [forceRender=true] - 강제 렌더링 여부
     */
    setState(newState, forceRender = true) {
        if (this.isDestroyed) return;
        
        this.previousState = { ...this.state };
        
        if (typeof newState === 'function') {
            this.state = { ...this.state, ...newState(this.state) };
        } else {
            this.state = { ...this.state, ...newState };
        }
        
        this.onStateChange(this.previousState, this.state);
        
        if (forceRender && this.shouldUpdate(this.previousState, this.state)) {
            this.render();
        }
    }

    /**
     * 업데이트 여부 결정
     * @param {Object} prevState - 이전 상태
     * @param {Object} nextState - 다음 상태
     * @returns {boolean} 업데이트 여부
     * @protected
     */
    shouldUpdate(prevState, nextState) {
        return JSON.stringify(prevState) !== JSON.stringify(nextState);
    }

    /**
     * 강제 업데이트
     */
    forceUpdate() {
        if (this.isMounted && !this.isDestroyed) {
            this.render();
        }
    }

    /**
     * 이벤트 리스너 추가
     * @param {string} event - 이벤트 이름
     * @param {Function} handler - 핸들러 함수
     * @param {Object} [options] - 이벤트 옵션
     */
    addEventListener(event, handler, options = {}) {
        const target = options.target || window;
        const boundHandler = handler.bind(this);
        
        target.addEventListener(event, boundHandler, options);
        
        if (!this.eventListeners.has(event)) {
            this.eventListeners.set(event, []);
        }
        
        this.eventListeners.get(event).push({
            target,
            handler: boundHandler,
            originalHandler: handler,
            options
        });
    }

    /**
     * 이벤트 리스너 제거
     * @param {string} event - 이벤트 이름
     * @param {Function} handler - 핸들러 함수
     */
    removeEventListener(event, handler) {
        const listeners = this.eventListeners.get(event);
        if (!listeners) return;
        
        const index = listeners.findIndex(l => l.originalHandler === handler);
        if (index !== -1) {
            const listener = listeners[index];
            listener.target.removeEventListener(event, listener.handler, listener.options);
            listeners.splice(index, 1);
        }
    }

    /**
     * 컴포넌트 이벤트 발생
     * @param {string} eventName - 이벤트 이름
     * @param {*} data - 이벤트 데이터
     */
    emit(eventName, data) {
        eventBus.emit(`component:${this.componentId}:${eventName}`, {
            componentId: this.componentId,
            componentName: this.componentName,
            data
        });
    }

    /**
     * 컴포넌트 이벤트 구독
     * @param {string} eventName - 이벤트 이름
     * @param {Function} handler - 핸들러 함수
     * @returns {Function} 구독 해제 함수
     */
    on(eventName, handler) {
        return eventBus.on(
            `component:${this.componentId}:${eventName}`, 
            handler,
            { namespace: this.componentId }
        );
    }

    /**
     * 리사이즈 핸들러
     * @private
     */
    handleResize() {
        if (this.isMounted && !this.isDestroyed) {
            this.onResize();
        }
    }

    /**
     * 성능 메트릭 업데이트
     * @param {number} renderTime - 렌더링 시간
     * @private
     */
    updatePerformanceMetrics(renderTime) {
        this.performanceMetrics.renderTimes.push(renderTime);
        this.performanceMetrics.lastRenderTime = renderTime;
        
        // 최근 20개 렌더링 시간만 유지
        if (this.performanceMetrics.renderTimes.length > 20) {
            this.performanceMetrics.renderTimes.shift();
        }
        
        // 평균 렌더링 시간 계산
        this.performanceMetrics.averageRenderTime = 
            this.performanceMetrics.renderTimes.reduce((sum, time) => sum + time, 0) / 
            this.performanceMetrics.renderTimes.length;
    }

    /**
     * 정리 작업
     * @private
     */
    cleanup() {
        // 이벤트 리스너 제거
        this.eventListeners.forEach((listeners, event) => {
            listeners.forEach(({ target, handler, options }) => {
                target.removeEventListener(event, handler, options);
            });
        });
        this.eventListeners.clear();
        
        // 스토어 구독 해제
        this.storeSubscriptions.forEach(unsubscribe => unsubscribe());
        this.storeSubscriptions.clear();
        
        // 이벤트 버스 네임스페이스 정리
        eventBus.offNamespace(this.componentId);
        
        // 컨테이너 정리
        if (this.container) {
            this.container.innerHTML = '';
        }
    }

    /**
     * 컴포넌트 제거
     */
    destroy() {
        if (this.isDestroyed) return;
        
        this.lifecycleState = 'destroying';
        this.onBeforeDestroy();
        
        try {
            this.unmount();
            this.cleanup();
            
            this.isDestroyed = true;
            this.lifecycleState = 'destroyed';
            this.onDestroyed();
            
            // 제거 이벤트 발생
            eventBus.emit('component:destroyed', {
                componentId: this.componentId,
                componentName: this.componentName
            });
            
        } catch (error) {
            console.error(`Component destroy failed (${this.componentName}):`, error);
            this.onDestroyError(error);
        }
    }

    // 라이프사이클 메서드들 (오버라이드용)

    /**
     * 초기화 완료 후 호출
     * @protected
     */
    onInitialized() {}

    /**
     * 마운트 전 호출
     * @protected
     */
    onBeforeMount() {}

    /**
     * 마운트 후 호출
     * @protected
     */
    onMounted() {}

    /**
     * 언마운트 전 호출
     * @protected
     */
    onBeforeUnmount() {}

    /**
     * 언마운트 후 호출
     * @protected
     */
    onUnmounted() {}

    /**
     * 제거 전 호출
     * @protected
     */
    onBeforeDestroy() {}

    /**
     * 제거 후 호출
     * @protected
     */
    onDestroyed() {}

    /**
     * 렌더링 후 호출
     * @protected
     */
    onAfterRender() {}

    /**
     * 상태 변경 시 호출
     * @param {Object} prevState - 이전 상태
     * @param {Object} nextState - 다음 상태
     * @protected
     */
    onStateChange(prevState, nextState) {}

    /**
     * 리사이즈 시 호출
     * @protected
     */
    onResize() {}

    // 에러 핸들링 메서드들

    /**
     * 마운트 에러 처리
     * @param {Error} error - 에러 객체
     * @protected
     */
    onMountError(error) {
        this.handleError(error, 'mount');
    }

    /**
     * 언마운트 에러 처리
     * @param {Error} error - 에러 객체
     * @protected
     */
    onUnmountError(error) {
        this.handleError(error, 'unmount');
    }

    /**
     * 렌더링 에러 처리
     * @param {Error} error - 에러 객체
     * @protected
     */
    onRenderError(error) {
        this.handleError(error, 'render');
    }

    /**
     * 제거 에러 처리
     * @param {Error} error - 에러 객체
     * @protected
     */
    onDestroyError(error) {
        this.handleError(error, 'destroy');
    }

    /**
     * 일반 에러 처리
     * @param {Error} error - 에러 객체
     * @param {string} context - 에러 컨텍스트
     * @protected
     */
    handleError(error, context) {
        eventBus.emit('component:error', {
            componentId: this.componentId,
            componentName: this.componentName,
            error,
            context,
            timestamp: Date.now()
        });
    }

    // 유틸리티 메서드들

    /**
     * 엘리먼트 찾기
     * @param {string} selector - CSS 선택자
     * @returns {HTMLElement|null} 엘리먼트
     * @protected
     */
    $(selector) {
        return this.container.querySelector(selector);
    }

    /**
     * 모든 엘리먼트 찾기
     * @param {string} selector - CSS 선택자
     * @returns {NodeList} 엘리먼트 목록
     * @protected
     */
    $$(selector) {
        return this.container.querySelectorAll(selector);
    }

    /**
     * 스토어에서 데이터 가져오기
     * @param {string} [selector] - 선택자
     * @returns {*} 상태 데이터
     * @protected
     */
    getStoreData(selector) {
        return globalStore.getState(selector);
    }

    /**
     * 스토어 액션 디스패치
     * @param {Object} action - 액션 객체
     * @returns {Promise<Object>} 새로운 상태
     * @protected
     */
    dispatch(action) {
        return globalStore.dispatch(action);
    }

    /**
     * 성능 정보 가져오기
     * @returns {Object} 성능 메트릭
     */
    getPerformanceMetrics() {
        return {
            ...this.performanceMetrics,
            renderCount: this.renderCount,
            componentId: this.componentId,
            componentName: this.componentName,
            lifecycleState: this.lifecycleState,
            isMounted: this.isMounted,
            isDestroyed: this.isDestroyed
        };
    }

    /**
     * 컴포넌트 정보 문자열 반환
     * @returns {string} 컴포넌트 정보
     */
    toString() {
        return `${this.componentName}#${this.componentId}`;
    }
}
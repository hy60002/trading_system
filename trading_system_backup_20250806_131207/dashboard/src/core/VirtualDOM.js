/**
 * @fileoverview 가상 DOM 구현
 * @description 성능 최적화를 위한 간단한 가상 DOM 시스템
 */

/**
 * 가상 노드 클래스
 * @class VNode
 */
export class VNode {
    /**
     * @param {string} tag - HTML 태그
     * @param {Object} props - 속성
     * @param {Array|string} children - 자식 노드들
     */
    constructor(tag, props = {}, children = []) {
        this.tag = tag;
        this.props = props || {};
        this.children = Array.isArray(children) ? children : [children];
        this.key = props.key || null;
        this.ref = props.ref || null;
    }
}

/**
 * 가상 DOM 매니저
 * @class VirtualDOM
 */
export class VirtualDOM {
    constructor() {
        this.componentInstances = new WeakMap();
        this.eventListeners = new WeakMap();
        this.batchedUpdates = [];
        this.isUpdating = false;
        this.updateScheduled = false;
        
        // 성능 메트릭
        this.metrics = {
            renderCount: 0,
            diffCount: 0,
            patchCount: 0,
            avgRenderTime: 0
        };
    }

    /**
     * 가상 노드 생성
     * @param {string} tag - HTML 태그
     * @param {Object} props - 속성
     * @param {...(VNode|string|number)} children - 자식 노드들
     * @returns {VNode} 가상 노드
     */
    createElement(tag, props = {}, ...children) {
        // 함수형 컴포넌트 처리
        if (typeof tag === 'function') {
            return this.createComponentNode(tag, props, children);
        }

        // 자식 노드 정규화
        const normalizedChildren = children
            .flat()
            .filter(child => child != null && child !== false)
            .map(child => {
                if (typeof child === 'string' || typeof child === 'number') {
                    return this.createTextNode(String(child));
                }
                return child;
            });

        return new VNode(tag, props, normalizedChildren);
    }

    /**
     * 텍스트 노드 생성
     * @param {string} text - 텍스트 내용
     * @returns {VNode} 텍스트 노드
     */
    createTextNode(text) {
        return new VNode('#text', { nodeValue: text }, []);
    }

    /**
     * 컴포넌트 노드 생성
     * @param {Function} component - 컴포넌트 함수
     * @param {Object} props - 속성
     * @param {Array} children - 자식 노드들
     * @returns {VNode} 컴포넌트 노드
     */
    createComponentNode(component, props, children) {
        const componentProps = { ...props, children };
        const vnode = component(componentProps);
        
        // 컴포넌트 메타데이터 저장
        if (vnode) {
            vnode._component = component;
            vnode._componentProps = componentProps;
        }
        
        return vnode;
    }

    /**
     * 가상 DOM을 실제 DOM으로 렌더링
     * @param {VNode} vnode - 가상 노드
     * @returns {HTMLElement} 실제 DOM 엘리먼트
     */
    render(vnode) {
        const startTime = performance.now();
        
        const element = this.createDOMElement(vnode);
        
        // 성능 메트릭 업데이트
        const renderTime = performance.now() - startTime;
        this.updateMetrics('render', renderTime);
        
        return element;
    }

    /**
     * DOM 엘리먼트 생성
     * @param {VNode} vnode - 가상 노드
     * @returns {HTMLElement|Text} DOM 엘리먼트
     * @private
     */
    createDOMElement(vnode) {
        if (!vnode) return null;

        // 텍스트 노드
        if (vnode.tag === '#text') {
            return document.createTextNode(vnode.props.nodeValue || '');
        }

        // HTML 엘리먼트
        const element = document.createElement(vnode.tag);
        
        // 속성 설정
        this.setElementProps(element, vnode.props);
        
        // 자식 노드 추가
        vnode.children.forEach(child => {
            if (child) {
                const childElement = this.createDOMElement(child);
                if (childElement) {
                    element.appendChild(childElement);
                }
            }
        });

        // ref 설정
        if (vnode.ref) {
            vnode.ref.current = element;
        }

        return element;
    }

    /**
     * 엘리먼트 속성 설정
     * @param {HTMLElement} element - DOM 엘리먼트
     * @param {Object} props - 속성 객체
     * @private
     */
    setElementProps(element, props) {
        Object.entries(props).forEach(([key, value]) => {
            if (key === 'key' || key === 'ref') return;
            
            // 이벤트 리스너
            if (key.startsWith('on') && typeof value === 'function') {
                const eventType = key.slice(2).toLowerCase();
                element.addEventListener(eventType, value);
                
                // 이벤트 리스너 추적
                if (!this.eventListeners.has(element)) {
                    this.eventListeners.set(element, new Map());
                }
                this.eventListeners.get(element).set(eventType, value);
                return;
            }
            
            // 스타일 속성
            if (key === 'style' && typeof value === 'object') {
                Object.assign(element.style, value);
                return;
            }
            
            // 클래스 속성
            if (key === 'className' || key === 'class') {
                element.className = value;
                return;
            }
            
            // 일반 속성
            if (value === true) {
                element.setAttribute(key, '');
            } else if (value === false || value == null) {
                element.removeAttribute(key);
            } else {
                element.setAttribute(key, String(value));
            }
        });
    }

    /**
     * 가상 DOM 차이점 계산
     * @param {VNode} oldVNode - 이전 가상 노드
     * @param {VNode} newVNode - 새로운 가상 노드
     * @returns {Array} 패치 배열
     */
    diff(oldVNode, newVNode) {
        const startTime = performance.now();
        const patches = [];
        
        this.diffNode(oldVNode, newVNode, patches, []);
        
        // 성능 메트릭 업데이트
        const diffTime = performance.now() - startTime;
        this.updateMetrics('diff', diffTime);
        
        return patches;
    }

    /**
     * 단일 노드 차이점 계산
     * @param {VNode} oldNode - 이전 노드
     * @param {VNode} newNode - 새로운 노드
     * @param {Array} patches - 패치 배열
     * @param {Array} path - 노드 경로
     * @private
     */
    diffNode(oldNode, newNode, patches, path) {
        // 새 노드가 없는 경우 (제거)
        if (!newNode) {
            patches.push({
                type: 'REMOVE',
                path: [...path]
            });
            return;
        }

        // 이전 노드가 없는 경우 (추가)
        if (!oldNode) {
            patches.push({
                type: 'CREATE',
                path: [...path],
                vnode: newNode
            });
            return;
        }

        // 태그가 다른 경우 (교체)
        if (oldNode.tag !== newNode.tag) {
            patches.push({
                type: 'REPLACE',
                path: [...path],
                vnode: newNode
            });
            return;
        }

        // 텍스트 노드 처리
        if (oldNode.tag === '#text') {
            if (oldNode.props.nodeValue !== newNode.props.nodeValue) {
                patches.push({
                    type: 'TEXT',
                    path: [...path],
                    text: newNode.props.nodeValue
                });
            }
            return;
        }

        // 속성 차이점 계산
        const propPatches = this.diffProps(oldNode.props, newNode.props);
        if (propPatches.length > 0) {
            patches.push({
                type: 'PROPS',
                path: [...path],
                patches: propPatches
            });
        }

        // 자식 노드 차이점 계산
        this.diffChildren(oldNode.children, newNode.children, patches, path);
    }

    /**
     * 속성 차이점 계산
     * @param {Object} oldProps - 이전 속성
     * @param {Object} newProps - 새로운 속성
     * @returns {Array} 속성 패치 배열
     * @private
     */
    diffProps(oldProps, newProps) {
        const patches = [];
        const allKeys = new Set([...Object.keys(oldProps), ...Object.keys(newProps)]);

        allKeys.forEach(key => {
            const oldValue = oldProps[key];
            const newValue = newProps[key];

            if (oldValue !== newValue) {
                patches.push({
                    key,
                    oldValue,
                    newValue
                });
            }
        });

        return patches;
    }

    /**
     * 자식 노드 차이점 계산
     * @param {Array} oldChildren - 이전 자식 노드들
     * @param {Array} newChildren - 새로운 자식 노드들
     * @param {Array} patches - 패치 배열
     * @param {Array} path - 현재 경로
     * @private
     */
    diffChildren(oldChildren, newChildren, patches, path) {
        // 키 기반 매칭을 위한 맵 생성
        const oldKeyedNodes = new Map();
        const newKeyedNodes = new Map();
        
        oldChildren.forEach((child, index) => {
            if (child && child.key) {
                oldKeyedNodes.set(child.key, { node: child, index });
            }
        });
        
        newChildren.forEach((child, index) => {
            if (child && child.key) {
                newKeyedNodes.set(child.key, { node: child, index });
            }
        });

        // 길이가 더 긴 배열까지 순회
        const maxLength = Math.max(oldChildren.length, newChildren.length);
        
        for (let i = 0; i < maxLength; i++) {
            const oldChild = oldChildren[i];
            const newChild = newChildren[i];
            
            this.diffNode(oldChild, newChild, patches, [...path, i]);
        }
    }

    /**
     * 패치 적용
     * @param {HTMLElement} element - 루트 엘리먼트
     * @param {Array} patches - 패치 배열
     */
    patch(element, patches) {
        const startTime = performance.now();
        
        patches.forEach(patch => {
            this.applyPatch(element, patch);
        });
        
        // 성능 메트릭 업데이트
        const patchTime = performance.now() - startTime;
        this.updateMetrics('patch', patchTime);
    }

    /**
     * 단일 패치 적용
     * @param {HTMLElement} rootElement - 루트 엘리먼트
     * @param {Object} patch - 패치 객체
     * @private
     */
    applyPatch(rootElement, patch) {
        const targetElement = this.getElementByPath(rootElement, patch.path);
        
        if (!targetElement && patch.type !== 'CREATE') return;

        switch (patch.type) {
            case 'CREATE':
                const newElement = this.createDOMElement(patch.vnode);
                const parentElement = this.getElementByPath(rootElement, patch.path.slice(0, -1));
                if (parentElement && newElement) {
                    parentElement.appendChild(newElement);
                }
                break;
                
            case 'REMOVE':
                if (targetElement && targetElement.parentNode) {
                    targetElement.parentNode.removeChild(targetElement);
                }
                break;
                
            case 'REPLACE':
                const replacementElement = this.createDOMElement(patch.vnode);
                if (targetElement && targetElement.parentNode && replacementElement) {
                    targetElement.parentNode.replaceChild(replacementElement, targetElement);
                }
                break;
                
            case 'TEXT':
                if (targetElement) {
                    targetElement.nodeValue = patch.text;
                }
                break;
                
            case 'PROPS':
                patch.patches.forEach(propPatch => {
                    this.applyPropPatch(targetElement, propPatch);
                });
                break;
        }
    }

    /**
     * 속성 패치 적용
     * @param {HTMLElement} element - 대상 엘리먼트
     * @param {Object} propPatch - 속성 패치
     * @private
     */
    applyPropPatch(element, propPatch) {
        const { key, newValue } = propPatch;
        
        // 이벤트 리스너 업데이트
        if (key.startsWith('on')) {
            const eventType = key.slice(2).toLowerCase();
            const listeners = this.eventListeners.get(element);
            
            if (listeners && listeners.has(eventType)) {
                element.removeEventListener(eventType, listeners.get(eventType));
            }
            
            if (newValue) {
                element.addEventListener(eventType, newValue);
                if (!this.eventListeners.has(element)) {
                    this.eventListeners.set(element, new Map());
                }
                this.eventListeners.get(element).set(eventType, newValue);
            }
            return;
        }

        // 일반 속성 업데이트
        if (newValue == null || newValue === false) {
            element.removeAttribute(key);
        } else {
            element.setAttribute(key, String(newValue));
        }
    }

    /**
     * 경로로 엘리먼트 찾기
     * @param {HTMLElement} rootElement - 루트 엘리먼트
     * @param {Array} path - 경로 배열
     * @returns {HTMLElement|null} 대상 엘리먼트
     * @private
     */
    getElementByPath(rootElement, path) {
        return path.reduce((element, index) => {
            return element && element.childNodes[index];
        }, rootElement);
    }

    /**
     * 배치 업데이트 스케줄링
     * @param {Function} updateFn - 업데이트 함수
     */
    batchUpdate(updateFn) {
        this.batchedUpdates.push(updateFn);
        
        if (!this.updateScheduled) {
            this.updateScheduled = true;
            requestAnimationFrame(() => this.flushBatchedUpdates());
        }
    }

    /**
     * 배치된 업데이트 실행
     * @private
     */
    flushBatchedUpdates() {
        if (this.isUpdating) return;
        
        this.isUpdating = true;
        
        while (this.batchedUpdates.length > 0) {
            const updateFn = this.batchedUpdates.shift();
            try {
                updateFn();
            } catch (error) {
                console.error('VirtualDOM batch update error:', error);
            }
        }
        
        this.isUpdating = false;
        this.updateScheduled = false;
    }

    /**
     * 성능 메트릭 업데이트
     * @param {string} operation - 작업 유형
     * @param {number} time - 소요 시간
     * @private
     */
    updateMetrics(operation, time) {
        const count = this.metrics[`${operation}Count`] || 0;
        this.metrics[`${operation}Count`] = count + 1;
        
        if (operation === 'render') {
            this.metrics.avgRenderTime = (this.metrics.avgRenderTime * count + time) / (count + 1);
        }
    }

    /**
     * 성능 메트릭 가져오기
     * @returns {Object} 성능 메트릭
     */
    getMetrics() {
        return { ...this.metrics };
    }

    /**
     * 메트릭 리셋
     */
    resetMetrics() {
        this.metrics = {
            renderCount: 0,
            diffCount: 0,
            patchCount: 0,
            avgRenderTime: 0
        };
    }
}

// 전역 가상 DOM 인스턴스
export const vdom = new VirtualDOM();

// JSX 스타일 헬퍼 함수
export const h = (tag, props, ...children) => vdom.createElement(tag, props, ...children);

// 개발 모드에서 전역 접근 가능하게 설정
if (typeof window !== 'undefined' && process.env.NODE_ENV === 'development') {
    window.__TRADING_DASHBOARD_VDOM__ = vdom;
}
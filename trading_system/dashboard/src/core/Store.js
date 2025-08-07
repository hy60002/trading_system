/**
 * @fileoverview 중앙 집중식 상태 관리 스토어
 * @description Redux 패턴을 참고한 간단한 상태 관리 시스템
 */

/**
 * 상태 관리 스토어 클래스
 * @class Store
 */
export class Store {
    /**
     * @param {Object} initialState - 초기 상태
     * @param {Function} reducer - 상태 변경 함수
     */
    constructor(initialState = {}, reducer = null) {
        this.state = { ...initialState };
        this.subscribers = new Set();
        this.reducer = reducer || this.defaultReducer;
        this.middlewares = [];
        this.devMode = process.env.NODE_ENV === 'development';
        
        // 상태 변경 히스토리 (개발 모드에서만)
        this.history = this.devMode ? [] : null;
        
        this.initializeDefaultState();
    }

    /**
     * 기본 상태 초기화
     * @private
     */
    initializeDefaultState() {
        const defaultState = {
            // 시스템 상태
            system: {
                status: 'loading',
                websocketConnected: false,
                lastUpdate: null,
                errors: []
            },
            
            // 거래 데이터
            trading: {
                balance: { total: 0, available: 0, used: 0 },
                positions: [],
                trades: [],
                performance: {
                    dailyPnl: 0,
                    totalPnl: 0,
                    winRate: 0,
                    totalTrades: 0
                }
            },
            
            // UI 상태
            ui: {
                theme: 'dark',
                currentFilter: 'all',
                currentSort: 'symbol',
                notifications: [],
                selectedPosition: null,
                layout: 'default'
            },
            
            // 차트 데이터
            charts: {
                sparklineData: [],
                priceData: new Map(),
                indicators: new Map()
            }
        };

        this.state = { ...defaultState, ...this.state };
    }

    /**
     * 기본 리듀서
     * @param {Object} state - 현재 상태
     * @param {Object} action - 액션 객체
     * @returns {Object} 새로운 상태
     */
    defaultReducer(state, action) {
        const { type, payload } = action;
        
        switch (type) {
            case 'SET_SYSTEM_STATUS':
                return {
                    ...state,
                    system: { ...state.system, ...payload }
                };
                
            case 'UPDATE_BALANCE':
                return {
                    ...state,
                    trading: {
                        ...state.trading,
                        balance: { ...state.trading.balance, ...payload }
                    }
                };
                
            case 'UPDATE_POSITIONS':
                return {
                    ...state,
                    trading: {
                        ...state.trading,
                        positions: payload
                    }
                };
                
            case 'ADD_NOTIFICATION':
                return {
                    ...state,
                    ui: {
                        ...state.ui,
                        notifications: [payload, ...state.ui.notifications].slice(0, 50)
                    }
                };
                
            case 'UPDATE_UI_STATE':
                return {
                    ...state,
                    ui: { ...state.ui, ...payload }
                };
                
            case 'UPDATE_CHART_DATA':
                const { chartType, data } = payload;
                return {
                    ...state,
                    charts: {
                        ...state.charts,
                        [chartType]: data
                    }
                };
                
            default:
                return state;
        }
    }

    /**
     * 액션 디스패치
     * @param {Object} action - 액션 객체
     * @returns {Promise<Object>} 새로운 상태
     */
    async dispatch(action) {
        // 미들웨어 실행
        let processedAction = action;
        for (const middleware of this.middlewares) {
            processedAction = await middleware(processedAction, this.state, this);
        }

        const previousState = this.state;
        this.state = this.reducer(this.state, processedAction);

        // 개발 모드에서 히스토리 저장
        if (this.devMode && this.history) {
            this.history.push({
                action: processedAction,
                previousState,
                newState: this.state,
                timestamp: Date.now()
            });
            
            // 히스토리 크기 제한
            if (this.history.length > 100) {
                this.history.shift();
            }
        }

        // 구독자들에게 상태 변경 알림
        this.notifySubscribers(processedAction);
        
        return this.state;
    }

    /**
     * 상태 구독
     * @param {Function} callback - 상태 변경 콜백
     * @param {string|Array<string>} selector - 구독할 상태 경로
     * @returns {Function} 구독 해제 함수
     */
    subscribe(callback, selector = null) {
        const subscription = {
            callback,
            selector: Array.isArray(selector) ? selector : (selector ? [selector] : null),
            id: Symbol()
        };
        
        this.subscribers.add(subscription);
        
        // 현재 상태로 즉시 호출
        if (selector) {
            const selectedState = this.getNestedValue(this.state, subscription.selector);
            callback(selectedState, this.state);
        } else {
            callback(this.state);
        }

        // 구독 해제 함수 반환
        return () => {
            this.subscribers.delete(subscription);
        };
    }

    /**
     * 구독자들에게 알림
     * @param {Object} action - 실행된 액션
     * @private
     */
    notifySubscribers(action) {
        this.subscribers.forEach(subscription => {
            try {
                if (subscription.selector) {
                    const selectedState = this.getNestedValue(this.state, subscription.selector);
                    subscription.callback(selectedState, this.state, action);
                } else {
                    subscription.callback(this.state, action);
                }
            } catch (error) {
                console.error('Store subscriber error:', error);
            }
        });
    }

    /**
     * 중첩된 객체 값 가져오기
     * @param {Object} obj - 객체
     * @param {Array<string>} path - 경로 배열
     * @returns {*} 값
     * @private
     */
    getNestedValue(obj, path) {
        return path.reduce((current, key) => current && current[key], obj);
    }

    /**
     * 현재 상태 가져오기
     * @param {string|Array<string>} selector - 선택자
     * @returns {*} 상태 값
     */
    getState(selector = null) {
        if (!selector) return this.state;
        
        const path = Array.isArray(selector) ? selector : selector.split('.');
        return this.getNestedValue(this.state, path);
    }

    /**
     * 미들웨어 추가
     * @param {Function} middleware - 미들웨어 함수
     */
    use(middleware) {
        this.middlewares.push(middleware);
    }

    /**
     * 상태 리셋
     */
    reset() {
        this.state = {};
        this.initializeDefaultState();
        this.notifySubscribers({ type: 'RESET', payload: null });
    }

    /**
     * 개발 도구용 디버그 정보
     * @returns {Object} 디버그 정보
     */
    getDebugInfo() {
        if (!this.devMode) return null;
        
        return {
            currentState: this.state,
            history: this.history,
            subscribersCount: this.subscribers.size,
            middlewaresCount: this.middlewares.length
        };
    }
}

/**
 * 로깅 미들웨어
 * @param {Object} action - 액션
 * @param {Object} state - 현재 상태
 * @param {Store} store - 스토어 인스턴스
 * @returns {Object} 액션
 */
export const loggingMiddleware = (action, state, store) => {
    if (process.env.NODE_ENV === 'development') {
        console.group(`🏪 Store Action: ${action.type}`);
        console.log('Payload:', action.payload);
        console.log('Previous State:', state);
        console.log('New State:', store.state);
        console.groupEnd();
    }
    return action;
};

/**
 * 비동기 액션 미들웨어
 * @param {Object} action - 액션
 * @param {Object} state - 현재 상태
 * @param {Store} store - 스토어 인스턴스
 * @returns {Promise<Object>} 액션
 */
export const asyncMiddleware = async (action, state, store) => {
    if (typeof action.payload === 'function') {
        const result = await action.payload(store.dispatch.bind(store), store.getState.bind(store));
        return { ...action, payload: result };
    }
    return action;
};

// 전역 스토어 인스턴스
export const globalStore = new Store();

// 개발 모드에서 전역 접근 가능하게 설정
if (typeof window !== 'undefined' && process.env.NODE_ENV === 'development') {
    window.__TRADING_DASHBOARD_STORE__ = globalStore;
}
import { BaseComponent } from './BaseComponent.js';

/**
 * 키보드 단축키 관리 시스템
 * - 전역 단축키 관리
 * - 커스터마이징 가능한 단축키
 * - 컨텍스트별 단축키 스코프
 * - 단축키 도움말 시스템
 * - 충돌 방지 및 우선순위 관리
 */
export class KeyboardShortcutManager extends BaseComponent {
    constructor() {
        super();
        
        // 단축키 저장소
        this.shortcuts = new Map();
        this.contextStack = ['global']; // 컨텍스트 스택
        this.isEnabled = true;
        this.helpVisible = false;
        
        // 단축키 설정 (localStorage에서 로드)
        this.loadShortcutSettings();
        
        // 기본 단축키 정의
        this.defineDefaultShortcuts();
        
        // DOM 요소들
        this.helpModal = null;
        this.settingsModal = null;
        
        this.init();
    }

    init() {
        this.createHelpModal();
        this.createSettingsModal();
        this.setupEventListeners();
        this.emit('shortcutManagerInitialized');
    }

    /**
     * 기본 단축키 정의
     */
    defineDefaultShortcuts() {
        const defaults = {
            // 전역 단축키
            global: {
                'ctrl+k': { action: 'openCommandPalette', description: '명령 팔레트 열기' },
                'ctrl+shift+k': { action: 'openSearch', description: '검색 열기' },
                'ctrl+r': { action: 'refreshData', description: '데이터 새로고침' },
                'ctrl+shift+r': { action: 'hardRefresh', description: '완전 새로고침' },
                't': { action: 'toggleTheme', description: '테마 전환' },
                'ctrl+shift+t': { action: 'openThemeSettings', description: '테마 설정' },
                '?': { action: 'showHelp', description: '단축키 도움말' },
                'h': { action: 'showHelp', description: '단축키 도움말' },
                'escape': { action: 'closeModal', description: '모달 닫기' },
                'ctrl+s': { action: 'saveLayout', description: '레이아웃 저장' },
                'ctrl+shift+s': { action: 'saveLayoutAs', description: '다른 이름으로 레이아웃 저장' },
                'ctrl+l': { action: 'loadLayout', description: '레이아웃 불러오기' },
                'ctrl+shift+l': { action: 'resetLayout', description: '레이아웃 초기화' },
                'ctrl+f': { action: 'focusSearch', description: '검색 포커스' },
                'ctrl+shift+f': { action: 'openAdvancedSearch', description: '고급 검색' },
                'ctrl+d': { action: 'toggleDragMode', description: '드래그 모드 전환' },
                'ctrl+shift+d': { action: 'resetWidgetPositions', description: '위젯 위치 초기화' },
                'f11': { action: 'toggleFullscreen', description: '전체 화면 전환' },
                'ctrl+shift+i': { action: 'toggleDevTools', description: '개발자 도구' }
            },
            
            // 포지션 관리 단축키
            positions: {
                'c': { action: 'closePosition', description: '포지션 닫기' },
                'ctrl+c': { action: 'copyPosition', description: '포지션 복사' },
                'a': { action: 'adjustStopLoss', description: '손절가 조정' },
                'p': { action: 'partialClose', description: '부분 청산 (50%)' },
                'shift+p': { action: 'partialCloseCustom', description: '부분 청산 (커스텀)' },
                'm': { action: 'addMargin', description: '마진 추가' },
                'shift+m': { action: 'reduceMargin', description: '마진 감소' },
                'n': { action: 'addNote', description: '메모 추가' },
                'shift+c': { action: 'closeAllPositions', description: '모든 포지션 닫기' }
            },
            
            // 차트 단축키
            chart: {
                '+': { action: 'zoomIn', description: '차트 확대' },
                '-': { action: 'zoomOut', description: '차트 축소' },
                '0': { action: 'resetZoom', description: '줌 초기화' },
                'arrowleft': { action: 'panLeft', description: '왼쪽 이동' },
                'arrowright': { action: 'panRight', description: '오른쪽 이동' },
                'arrowup': { action: 'panUp', description: '위로 이동' },
                'arrowdown': { action: 'panDown', description: '아래로 이동' },
                'space': { action: 'togglePause', description: '실시간 업데이트 일시정지' },
                '1': { action: 'setTimeframe1m', description: '1분봉' },
                '5': { action: 'setTimeframe5m', description: '5분봉' },
                '15': { action: 'setTimeframe15m', description: '15분봉' },
                '60': { action: 'setTimeframe1h', description: '1시간봉' },
                'd': { action: 'setTimeframe1d', description: '일봉' }
            },
            
            // 필터링/검색 단축키
            search: {
                'enter': { action: 'submitSearch', description: '검색 실행' },
                'ctrl+enter': { action: 'searchInNewTab', description: '새 탭에서 검색' },
                'arrowdown': { action: 'nextSuggestion', description: '다음 제안' },
                'arrowup': { action: 'prevSuggestion', description: '이전 제안' },
                'tab': { action: 'nextFilter', description: '다음 필터' },
                'shift+tab': { action: 'prevFilter', description: '이전 필터' },
                'escape': { action: 'clearSearch', description: '검색 지우기' },
                'ctrl+a': { action: 'selectAllResults', description: '모든 결과 선택' },
                'ctrl+shift+a': { action: 'clearAllFilters', description: '모든 필터 지우기' }
            },
            
            // 네비게이션 단축키
            navigation: {
                'g+h': { action: 'goHome', description: '홈으로 이동' },
                'g+p': { action: 'goToPositions', description: '포지션으로 이동' },
                'g+t': { action: 'goToTrades', description: '거래내역으로 이동' },
                'g+c': { action: 'goToCharts', description: '차트로 이동' },
                'g+s': { action: 'goToSettings', description: '설정으로 이동' },
                'g+n': { action: 'goToNotifications', description: '알림으로 이동' },
                'j': { action: 'nextItem', description: '다음 항목' },
                'k': { action: 'prevItem', description: '이전 항목' },
                'gg': { action: 'goToTop', description: '맨 위로' },
                'shift+g': { action: 'goToBottom', description: '맨 아래로' }
            }
        };
        
        // 기본 단축키 등록
        Object.entries(defaults).forEach(([context, shortcuts]) => {
            Object.entries(shortcuts).forEach(([key, config]) => {
                this.registerShortcut(key, config.action, context, {
                    description: config.description,
                    isDefault: true
                });
            });
        });
    }

    /**
     * 단축키 등록
     * @param {string} key - 키 조합 (예: 'ctrl+s', 'shift+f')
     * @param {string|function} action - 액션 이름 또는 콜백 함수
     * @param {string} context - 컨텍스트 ('global', 'positions', 'chart' 등)
     * @param {object} options - 추가 옵션
     */
    registerShortcut(key, action, context = 'global', options = {}) {
        const normalizedKey = this.normalizeKey(key);
        
        if (!this.shortcuts.has(context)) {
            this.shortcuts.set(context, new Map());
        }
        
        const contextShortcuts = this.shortcuts.get(context);
        
        // 충돌 검사
        if (contextShortcuts.has(normalizedKey) && !options.override) {
            console.warn(`Shortcut '${key}' already exists in context '${context}'`);
            return false;
        }
        
        contextShortcuts.set(normalizedKey, {
            key: normalizedKey,
            action,
            context,
            description: options.description || '',
            isDefault: options.isDefault || false,
            isCustom: options.isCustom || false,
            enabled: options.enabled !== false,
            preventDefault: options.preventDefault !== false,
            stopPropagation: options.stopPropagation !== false
        });
        
        this.saveShortcutSettings();
        this.emit('shortcutRegistered', { key: normalizedKey, action, context });
        return true;
    }

    /**
     * 단축키 제거
     * @param {string} key - 키 조합
     * @param {string} context - 컨텍스트
     */
    unregisterShortcut(key, context = 'global') {
        const normalizedKey = this.normalizeKey(key);
        const contextShortcuts = this.shortcuts.get(context);
        
        if (contextShortcuts && contextShortcuts.has(normalizedKey)) {
            contextShortcuts.delete(normalizedKey);
            this.saveShortcutSettings();
            this.emit('shortcutUnregistered', { key: normalizedKey, context });
            return true;
        }
        
        return false;
    }

    /**
     * 컨텍스트 푸시 (스택 방식)
     * @param {string} context - 컨텍스트 이름
     */
    pushContext(context) {
        if (!this.contextStack.includes(context)) {
            this.contextStack.push(context);
            this.emit('contextPushed', context);
        }
    }

    /**
     * 컨텍스트 팝
     * @param {string} context - 제거할 컨텍스트 (선택적)
     */
    popContext(context) {
        if (context) {
            const index = this.contextStack.indexOf(context);
            if (index > 0) { // global은 제거 불가
                this.contextStack.splice(index, 1);
                this.emit('contextPopped', context);
            }
        } else {
            if (this.contextStack.length > 1) {
                const popped = this.contextStack.pop();
                this.emit('contextPopped', popped);
            }
        }
    }

    /**
     * 키 조합 정규화
     * @param {string} key - 원본 키 조합
     * @returns {string} 정규화된 키 조합
     */
    normalizeKey(key) {
        const parts = key.toLowerCase().split('+');
        const modifiers = [];
        let mainKey = '';
        
        parts.forEach(part => {
            switch (part) {
                case 'ctrl':
                case 'control':
                    modifiers.push('ctrl');
                    break;
                case 'shift':
                    modifiers.push('shift');
                    break;
                case 'alt':
                    modifiers.push('alt');
                    break;
                case 'meta':
                case 'cmd':
                case 'command':
                    modifiers.push('meta');
                    break;
                default:
                    mainKey = part;
            }
        });
        
        // 일관된 순서로 정렬
        modifiers.sort();
        return modifiers.length > 0 ? modifiers.join('+') + '+' + mainKey : mainKey;
    }

    /**
     * 키 이벤트를 키 조합 문자열로 변환
     * @param {KeyboardEvent} event - 키보드 이벤트
     * @returns {string} 키 조합 문자열
     */
    eventToKeyString(event) {
        const modifiers = [];
        let key = event.key.toLowerCase();
        
        // 특수 키 매핑
        const specialKeys = {
            ' ': 'space',
            'arrowleft': 'arrowleft',
            'arrowright': 'arrowright',
            'arrowup': 'arrowup',
            'arrowdown': 'arrowdown',
            'escape': 'escape',
            'enter': 'enter',
            'tab': 'tab',
            'backspace': 'backspace',
            'delete': 'delete',
            'home': 'home',
            'end': 'end',
            'pageup': 'pageup',
            'pagedown': 'pagedown'
        };
        
        if (specialKeys[key]) {
            key = specialKeys[key];
        }
        
        if (event.ctrlKey) modifiers.push('ctrl');
        if (event.shiftKey) modifiers.push('shift');
        if (event.altKey) modifiers.push('alt');
        if (event.metaKey) modifiers.push('meta');
        
        modifiers.sort();
        return modifiers.length > 0 ? modifiers.join('+') + '+' + key : key;
    }

    /**
     * 이벤트 리스너 설정
     */
    setupEventListeners() {
        document.addEventListener('keydown', this.handleKeyDown.bind(this), true);
        document.addEventListener('keyup', this.handleKeyUp.bind(this), true);
        
        // 시퀀스 키를 위한 타이머
        this.sequenceTimer = null;
        this.currentSequence = '';
    }

    /**
     * 키다운 이벤트 처리
     * @param {KeyboardEvent} event - 키보드 이벤트
     */
    handleKeyDown(event) {
        if (!this.isEnabled) return;
        
        // 입력 필드에서는 일부 단축키만 허용
        if (this.isInputField(event.target)) {
            const allowedInInput = ['escape', 'ctrl+s', 'ctrl+a', 'ctrl+z', 'ctrl+y'];
            const keyString = this.eventToKeyString(event);
            if (!allowedInInput.includes(keyString)) {
                return;
            }
        }
        
        const keyString = this.eventToKeyString(event);
        
        // 시퀀스 키 처리 (예: 'g+h', 'gg')
        if (this.isSequenceKey(keyString)) {
            this.handleSequenceKey(keyString, event);
            return;
        }
        
        // 단축키 찾기 (역순으로 컨텍스트 검사 - 가장 최근 컨텍스트가 우선)
        for (let i = this.contextStack.length - 1; i >= 0; i--) {
            const context = this.contextStack[i];
            const contextShortcuts = this.shortcuts.get(context);
            
            if (contextShortcuts && contextShortcuts.has(keyString)) {
                const shortcut = contextShortcuts.get(keyString);
                
                if (shortcut.enabled) {
                    if (shortcut.preventDefault) {
                        event.preventDefault();
                    }
                    if (shortcut.stopPropagation) {
                        event.stopPropagation();
                    }
                    
                    this.executeShortcut(shortcut, event);
                    return;
                }
            }
        }
    }

    /**
     * 키업 이벤트 처리 (필요시)
     * @param {KeyboardEvent} event - 키보드 이벤트
     */
    handleKeyUp(event) {
        // 현재는 키업 이벤트 처리 없음
        // 필요시 길게 누르기 등의 기능 구현 가능
    }

    /**
     * 시퀀스 키 처리
     * @param {string} keyString - 키 문자열
     * @param {KeyboardEvent} event - 키보드 이벤트
     */
    handleSequenceKey(keyString, event) {
        clearTimeout(this.sequenceTimer);
        
        this.currentSequence += keyString;
        
        // 시퀀스 완성 체크
        const sequenceShortcut = this.findSequenceShortcut(this.currentSequence);
        if (sequenceShortcut) {
            event.preventDefault();
            event.stopPropagation();
            this.executeShortcut(sequenceShortcut, event);
            this.currentSequence = '';
            return;
        }
        
        // 시퀀스 타임아웃 (1초)
        this.sequenceTimer = setTimeout(() => {
            this.currentSequence = '';
        }, 1000);
    }

    /**
     * 시퀀스 단축키 찾기
     * @param {string} sequence - 시퀀스 문자열
     * @returns {object|null} 단축키 객체 또는 null
     */
    findSequenceShortcut(sequence) {
        for (let i = this.contextStack.length - 1; i >= 0; i--) {
            const context = this.contextStack[i];
            const contextShortcuts = this.shortcuts.get(context);
            
            if (contextShortcuts) {
                for (const [key, shortcut] of contextShortcuts) {
                    if (key.includes('+') && key.replace(/\+/g, '') === sequence) {
                        return shortcut;
                    }
                }
            }
        }
        return null;
    }

    /**
     * 시퀀스 키인지 확인
     * @param {string} keyString - 키 문자열
     * @returns {boolean} 시퀀스 키 여부
     */
    isSequenceKey(keyString) {
        const sequenceKeys = ['g', 'shift+g'];
        return sequenceKeys.includes(keyString) || keyString.length === 1;
    }

    /**
     * 입력 필드인지 확인
     * @param {Element} element - DOM 요소
     * @returns {boolean} 입력 필드 여부
     */
    isInputField(element) {
        const tagName = element.tagName.toLowerCase();
        const inputTypes = ['input', 'textarea', 'select'];
        const editableElement = element.contentEditable === 'true';
        
        return inputTypes.includes(tagName) || editableElement;
    }

    /**
     * 단축키 실행
     * @param {object} shortcut - 단축키 객체
     * @param {KeyboardEvent} event - 키보드 이벤트
     */
    executeShortcut(shortcut, event) {
        try {
            if (typeof shortcut.action === 'function') {
                shortcut.action(event);
            } else {
                // 이벤트 버스를 통해 액션 전송
                this.eventBus.emit('shortcut:' + shortcut.action, {
                    key: shortcut.key,
                    context: shortcut.context,
                    event
                });
            }
            
            this.emit('shortcutExecuted', {
                key: shortcut.key,
                action: shortcut.action,
                context: shortcut.context
            });
            
        } catch (error) {
            console.error('Shortcut execution failed:', error);
            this.emit('shortcutError', { shortcut, error });
        }
    }

    /**
     * 도움말 모달 생성
     */
    createHelpModal() {
        this.helpModal = document.createElement('div');
        this.helpModal.className = 'shortcut-help-modal';
        this.helpModal.style.display = 'none';
        this.helpModal.innerHTML = `
            <div class="modal-overlay">
                <div class="modal-content">
                    <div class="modal-header">
                        <h2><i class="fas fa-keyboard"></i> 키보드 단축키</h2>
                        <button class="modal-close" aria-label="닫기">
                            <i class="fas fa-times"></i>
                        </button>
                    </div>
                    <div class="modal-body">
                        <div class="shortcut-search">
                            <input type="text" placeholder="단축키 검색..." class="shortcut-search-input">
                        </div>
                        <div class="shortcut-categories"></div>
                    </div>
                    <div class="modal-footer">
                        <button class="btn btn-secondary" id="customize-shortcuts">커스터마이징</button>
                        <button class="btn btn-primary" id="close-help">확인</button>
                    </div>
                </div>
            </div>
        `;
        
        document.body.appendChild(this.helpModal);
        
        // 이벤트 리스너
        this.helpModal.querySelector('.modal-close').addEventListener('click', () => this.hideHelp());
        this.helpModal.querySelector('#close-help').addEventListener('click', () => this.hideHelp());
        this.helpModal.querySelector('#customize-shortcuts').addEventListener('click', () => this.showSettings());
        this.helpModal.querySelector('.modal-overlay').addEventListener('click', (e) => {
            if (e.target === e.currentTarget) this.hideHelp();
        });
        
        // 검색 기능
        const searchInput = this.helpModal.querySelector('.shortcut-search-input');
        searchInput.addEventListener('input', (e) => this.filterShortcuts(e.target.value));
    }

    /**
     * 설정 모달 생성
     */
    createSettingsModal() {
        this.settingsModal = document.createElement('div');
        this.settingsModal.className = 'shortcut-settings-modal';
        this.settingsModal.style.display = 'none';
        this.settingsModal.innerHTML = `
            <div class="modal-overlay">
                <div class="modal-content">
                    <div class="modal-header">
                        <h2><i class="fas fa-cog"></i> 단축키 설정</h2>
                        <button class="modal-close" aria-label="닫기">
                            <i class="fas fa-times"></i>
                        </button>
                    </div>
                    <div class="modal-body">
                        <div class="settings-tabs">
                            <button class="tab-btn active" data-tab="customize">커스터마이징</button>
                            <button class="tab-btn" data-tab="import-export">가져오기/내보내기</button>
                            <button class="tab-btn" data-tab="reset">초기화</button>
                        </div>
                        <div class="settings-content">
                            <div class="tab-panel active" data-panel="customize">
                                <div class="shortcut-editor"></div>
                            </div>
                            <div class="tab-panel" data-panel="import-export">
                                <div class="import-export-controls">
                                    <button class="btn btn-secondary" id="export-shortcuts">설정 내보내기</button>
                                    <button class="btn btn-secondary" id="import-shortcuts">설정 가져오기</button>
                                    <input type="file" id="import-file" accept=".json" style="display: none;">
                                </div>
                            </div>
                            <div class="tab-panel" data-panel="reset">
                                <div class="reset-controls">
                                    <p>단축키 설정을 초기화하시겠습니까?</p>
                                    <button class="btn btn-danger" id="reset-shortcuts">초기화</button>
                                </div>
                            </div>
                        </div>
                    </div>
                    <div class="modal-footer">
                        <button class="btn btn-secondary" id="cancel-settings">취소</button>
                        <button class="btn btn-primary" id="save-settings">저장</button>
                    </div>
                </div>
            </div>
        `;
        
        document.body.appendChild(this.settingsModal);
        this.setupSettingsEventListeners();
    }

    /**
     * 설정 모달 이벤트 리스너 설정
     */
    setupSettingsEventListeners() {
        // 모달 닫기
        this.settingsModal.querySelector('.modal-close').addEventListener('click', () => this.hideSettings());
        this.settingsModal.querySelector('#cancel-settings').addEventListener('click', () => this.hideSettings());
        this.settingsModal.querySelector('#save-settings').addEventListener('click', () => this.saveSettings());
        
        // 탭 전환
        this.settingsModal.querySelectorAll('.tab-btn').forEach(btn => {
            btn.addEventListener('click', (e) => this.switchTab(e.target.dataset.tab));
        });
        
        // 가져오기/내보내기
        this.settingsModal.querySelector('#export-shortcuts').addEventListener('click', () => this.exportSettings());
        this.settingsModal.querySelector('#import-shortcuts').addEventListener('click', () => {
            this.settingsModal.querySelector('#import-file').click();
        });
        this.settingsModal.querySelector('#import-file').addEventListener('change', (e) => this.importSettings(e));
        
        // 초기화
        this.settingsModal.querySelector('#reset-shortcuts').addEventListener('click', () => this.resetToDefaults());
    }

    /**
     * 도움말 표시
     */
    showHelp() {
        this.updateHelpContent();
        this.helpModal.style.display = 'flex';
        this.helpVisible = true;
        document.body.classList.add('modal-open');
        
        // 포커스 설정
        setTimeout(() => {
            this.helpModal.querySelector('.shortcut-search-input').focus();
        }, 100);
    }

    /**
     * 도움말 숨기기
     */
    hideHelp() {
        this.helpModal.style.display = 'none';
        this.helpVisible = false;
        document.body.classList.remove('modal-open');
    }

    /**
     * 설정 모달 표시
     */
    showSettings() {
        this.hideHelp();
        this.updateSettingsContent();
        this.settingsModal.style.display = 'flex';
        document.body.classList.add('modal-open');
    }

    /**
     * 설정 모달 숨기기
     */
    hideSettings() {
        this.settingsModal.style.display = 'none';
        document.body.classList.remove('modal-open');
    }

    /**
     * 도움말 내용 업데이트
     */
    updateHelpContent() {
        const container = this.helpModal.querySelector('.shortcut-categories');
        container.innerHTML = '';
        
        // 컨텍스트별로 그룹화
        const contextNames = {
            global: '전역',
            positions: '포지션 관리',
            chart: '차트',
            search: '검색/필터',
            navigation: '네비게이션'
        };
        
        this.shortcuts.forEach((contextShortcuts, context) => {
            if (contextShortcuts.size === 0) return;
            
            const section = document.createElement('div');
            section.className = 'shortcut-section';
            section.innerHTML = `
                <h3>${contextNames[context] || context}</h3>
                <div class="shortcut-list"></div>
            `;
            
            const list = section.querySelector('.shortcut-list');
            
            // 단축키들을 정렬하여 표시
            const sortedShortcuts = Array.from(contextShortcuts.values())
                .sort((a, b) => a.key.localeCompare(b.key));
            
            sortedShortcuts.forEach(shortcut => {
                if (shortcut.description) {
                    const item = document.createElement('div');
                    item.className = 'shortcut-item';
                    item.innerHTML = `
                        <span class="shortcut-key">${this.formatKeyForDisplay(shortcut.key)}</span>
                        <span class="shortcut-description">${shortcut.description}</span>
                    `;
                    list.appendChild(item);
                }
            });
            
            container.appendChild(section);
        });
    }

    /**
     * 키 조합을 표시용으로 포맷팅
     * @param {string} key - 키 조합 문자열
     * @returns {string} 포맷된 키 조합
     */
    formatKeyForDisplay(key) {
        const isMac = navigator.platform.toUpperCase().indexOf('MAC') >= 0;
        
        return key
            .split('+')
            .map(part => {
                switch (part) {
                    case 'ctrl': return isMac ? '⌘' : 'Ctrl';
                    case 'shift': return isMac ? '⇧' : 'Shift';
                    case 'alt': return isMac ? '⌥' : 'Alt';
                    case 'meta': return isMac ? '⌘' : 'Win';
                    case 'arrowleft': return '←';
                    case 'arrowright': return '→';
                    case 'arrowup': return '↑';
                    case 'arrowdown': return '↓';
                    case 'space': return 'Space';
                    case 'escape': return 'Esc';
                    case 'enter': return 'Enter';
                    case 'tab': return 'Tab';
                    default: return part.toUpperCase();
                }
            })
            .join(isMac ? '' : ' + ');
    }

    /**
     * 단축키 필터링 (검색)
     * @param {string} query - 검색어
     */
    filterShortcuts(query) {
        const sections = this.helpModal.querySelectorAll('.shortcut-section');
        
        sections.forEach(section => {
            const items = section.querySelectorAll('.shortcut-item');
            let visibleCount = 0;
            
            items.forEach(item => {
                const key = item.querySelector('.shortcut-key').textContent.toLowerCase();
                const desc = item.querySelector('.shortcut-description').textContent.toLowerCase();
                const match = key.includes(query.toLowerCase()) || desc.includes(query.toLowerCase());
                
                item.style.display = match || !query ? 'flex' : 'none';
                if (match || !query) visibleCount++;
            });
            
            section.style.display = visibleCount > 0 ? 'block' : 'none';
        });
    }

    /**
     * 설정 저장
     */
    saveShortcutSettings() {
        const settings = {};
        
        this.shortcuts.forEach((contextShortcuts, context) => {
            settings[context] = {};
            contextShortcuts.forEach((shortcut, key) => {
                if (shortcut.isCustom) {
                    settings[context][key] = {
                        action: shortcut.action,
                        description: shortcut.description,
                        enabled: shortcut.enabled
                    };
                }
            });
        });
        
        localStorage.setItem('keyboardShortcuts', JSON.stringify(settings));
    }

    /**
     * 설정 로드
     */
    loadShortcutSettings() {
        try {
            const saved = localStorage.getItem('keyboardShortcuts');
            if (saved) {
                const settings = JSON.parse(saved);
                
                Object.entries(settings).forEach(([context, shortcuts]) => {
                    Object.entries(shortcuts).forEach(([key, config]) => {
                        this.registerShortcut(key, config.action, context, {
                            description: config.description,
                            isCustom: true,
                            enabled: config.enabled,
                            override: true
                        });
                    });
                });
            }
        } catch (error) {
            console.error('Failed to load shortcut settings:', error);
        }
    }

    /**
     * 단축키 관리자 활성화/비활성화
     * @param {boolean} enabled - 활성화 여부
     */
    setEnabled(enabled) {
        this.isEnabled = enabled;
        this.emit('shortcutManagerToggled', enabled);
    }

    /**
     * 현재 컨텍스트 반환
     * @returns {string} 현재 활성 컨텍스트
     */
    getCurrentContext() {
        return this.contextStack[this.contextStack.length - 1];
    }

    /**
     * 모든 단축키 목록 반환
     * @param {string} context - 특정 컨텍스트 (선택적)
     * @returns {Array} 단축키 목록
     */
    getAllShortcuts(context) {
        if (context) {
            const contextShortcuts = this.shortcuts.get(context);
            return contextShortcuts ? Array.from(contextShortcuts.values()) : [];
        }
        
        const all = [];
        this.shortcuts.forEach((contextShortcuts) => {
            all.push(...Array.from(contextShortcuts.values()));
        });
        return all;
    }

    /**
     * 설정 내보내기
     */
    exportSettings() {
        const settings = {
            shortcuts: {},
            version: '1.0',
            timestamp: new Date().toISOString()
        };
        
        this.shortcuts.forEach((contextShortcuts, context) => {
            settings.shortcuts[context] = {};
            contextShortcuts.forEach((shortcut, key) => {
                settings.shortcuts[context][key] = {
                    action: shortcut.action,
                    description: shortcut.description,
                    enabled: shortcut.enabled,
                    isCustom: shortcut.isCustom,
                    isDefault: shortcut.isDefault
                };
            });
        });
        
        const blob = new Blob([JSON.stringify(settings, null, 2)], 
            { type: 'application/json' });
        const url = URL.createObjectURL(blob);
        const a = document.createElement('a');
        a.href = url;
        a.download = `keyboard-shortcuts-${new Date().toISOString().slice(0, 10)}.json`;
        a.click();
        URL.revokeObjectURL(url);
    }

    /**
     * 설정 가져오기
     */
    importSettings(event) {
        const file = event.target.files[0];
        if (!file) return;
        
        const reader = new FileReader();
        reader.onload = (e) => {
            try {
                const settings = JSON.parse(e.target.result);
                
                if (settings.shortcuts) {
                    // 기존 커스텀 단축키 제거
                    this.shortcuts.forEach((contextShortcuts) => {
                        const toDelete = [];
                        contextShortcuts.forEach((shortcut, key) => {
                            if (shortcut.isCustom) {
                                toDelete.push(key);
                            }
                        });
                        toDelete.forEach(key => contextShortcuts.delete(key));
                    });
                    
                    // 새 설정 적용
                    Object.entries(settings.shortcuts).forEach(([context, shortcuts]) => {
                        Object.entries(shortcuts).forEach(([key, config]) => {
                            this.registerShortcut(key, config.action, context, {
                                description: config.description,
                                isCustom: config.isCustom,
                                enabled: config.enabled,
                                override: true
                            });
                        });
                    });
                    
                    this.saveShortcutSettings();
                    alert('단축키 설정을 가져왔습니다.');
                }
            } catch (error) {
                console.error('Failed to import settings:', error);
                alert('설정 파일을 읽는데 실패했습니다.');
            }
        };
        reader.readAsText(file);
    }

    /**
     * 기본값으로 초기화
     */
    resetToDefaults() {
        if (confirm('모든 단축키 설정을 초기화하시겠습니까?')) {
            localStorage.removeItem('keyboardShortcuts');
            
            // 커스텀 단축키 제거
            this.shortcuts.forEach((contextShortcuts) => {
                const toDelete = [];
                contextShortcuts.forEach((shortcut, key) => {
                    if (shortcut.isCustom) {
                        toDelete.push(key);
                    }
                });
                toDelete.forEach(key => contextShortcuts.delete(key));
            });
            
            alert('단축키 설정이 초기화되었습니다.');
            this.hideSettings();
        }
    }

    /**
     * 정리
     */
    destroy() {
        // 이벤트 리스너 제거
        document.removeEventListener('keydown', this.handleKeyDown);
        document.removeEventListener('keyup', this.handleKeyUp);
        
        // 타이머 정리
        if (this.sequenceTimer) {
            clearTimeout(this.sequenceTimer);
        }
        
        // 모달 제거
        if (this.helpModal) {
            this.helpModal.remove();
        }
        if (this.settingsModal) {
            this.settingsModal.remove();
        }
        
        super.destroy();
    }
}

export default KeyboardShortcutManager;
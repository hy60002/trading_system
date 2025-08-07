/**
 * @fileoverview 레이아웃 커스터마이징 시스템
 * @description 사용자 맞춤형 레이아웃 설정 및 관리 시스템
 */

import { BaseComponent } from './BaseComponent.js';
import { eventBus } from './EventBus.js';
import { globalStore } from './Store.js';
import { widgetManager } from './WidgetManager.js';

/**
 * 레이아웃 커스터마이저
 * @class LayoutCustomizer
 */
export class LayoutCustomizer extends BaseComponent {
    constructor(options = {}) {
        super(null, options);
        
        this.isVisible = false;
        this.currentLayout = 'default';
        this.layouts = new Map();
        this.presets = new Map();
        this.customLayouts = new Map();
        
        // 설정
        this.config = {
            maxLayouts: 10,
            autoSave: true,
            showPreview: true,
            enableSharing: false,
            defaultLayouts: ['default', 'trading', 'analysis', 'minimal']
        };
        
        // 상태
        this.state = {
            isEditing: false,
            selectedLayout: null,
            previewMode: false,
            isDirty: false
        };
        
        // 템플릿
        this.templates = new Map();
        
        this.initialize();
    }

    /**
     * 초기화
     * @private
     */
    initialize() {
        this.loadPresets();
        this.loadCustomLayouts();
        this.createCustomizerUI();
        this.setupEventListeners();
        this.registerTemplates();
    }

    /**
     * 프리셋 레이아웃 로드
     * @private
     */
    loadPresets() {
        // 기본 레이아웃
        this.presets.set('default', {
            name: '기본 레이아웃',
            description: '균형 잡힌 기본 구성',
            icon: 'fas fa-th',
            widgets: [
                { type: 'balance', position: { x: 0, y: 0 }, size: { width: 3, height: 2 } },
                { type: 'chart', position: { x: 3, y: 0 }, size: { width: 6, height: 4 } },
                { type: 'positions', position: { x: 9, y: 0 }, size: { width: 3, height: 6 } },
                { type: 'watchlist', position: { x: 0, y: 2 }, size: { width: 3, height: 4 } },
                { type: 'news', position: { x: 3, y: 4 }, size: { width: 6, height: 3 } }
            ]
        });

        // 트레이딩 중심 레이아웃
        this.presets.set('trading', {
            name: '트레이딩 레이아웃',
            description: '거래에 최적화된 구성',
            icon: 'fas fa-chart-line',
            widgets: [
                { type: 'chart', position: { x: 0, y: 0 }, size: { width: 8, height: 5 } },
                { type: 'positions', position: { x: 8, y: 0 }, size: { width: 4, height: 5 } },
                { type: 'balance', position: { x: 0, y: 5 }, size: { width: 4, height: 2 } },
                { type: 'watchlist', position: { x: 4, y: 5 }, size: { width: 4, height: 2 } },
                { type: 'news', position: { x: 8, y: 5 }, size: { width: 4, height: 2 } }
            ]
        });

        // 분석 중심 레이아웃
        this.presets.set('analysis', {
            name: '분석 레이아웃',
            description: '데이터 분석에 최적화',
            icon: 'fas fa-analytics',
            widgets: [
                { type: 'chart', position: { x: 0, y: 0 }, size: { width: 6, height: 4 } },
                { type: 'chart', position: { x: 6, y: 0 }, size: { width: 6, height: 4 } },
                { type: 'positions', position: { x: 0, y: 4 }, size: { width: 4, height: 3 } },
                { type: 'news', position: { x: 4, y: 4 }, size: { width: 4, height: 3 } },
                { type: 'watchlist', position: { x: 8, y: 4 }, size: { width: 4, height: 3 } }
            ]
        });

        // 미니멀 레이아웃
        this.presets.set('minimal', {
            name: '미니멀 레이아웃',
            description: '단순하고 깔끔한 구성',
            icon: 'fas fa-minus',
            widgets: [
                { type: 'chart', position: { x: 0, y: 0 }, size: { width: 8, height: 6 } },
                { type: 'positions', position: { x: 8, y: 0 }, size: { width: 4, height: 6 } }
            ]
        });
    }

    /**
     * 커스텀 레이아웃 로드
     * @private
     */
    loadCustomLayouts() {
        try {
            const saved = localStorage.getItem('dashboard-custom-layouts');
            if (saved) {
                const layouts = JSON.parse(saved);
                Object.entries(layouts).forEach(([id, layout]) => {
                    this.customLayouts.set(id, layout);
                });
            }
        } catch (error) {
            console.warn('커스텀 레이아웃 로드 실패:', error);
        }
    }

    /**
     * 커스터마이저 UI 생성
     * @private
     */
    createCustomizerUI() {
        // 메인 커스터마이저 패널
        this.customizerPanel = document.createElement('div');
        this.customizerPanel.className = 'layout-customizer-panel';
        this.customizerPanel.innerHTML = this.renderCustomizerPanel();
        
        // 프리뷰 오버레이
        this.previewOverlay = document.createElement('div');
        this.previewOverlay.className = 'layout-preview-overlay';
        this.previewOverlay.innerHTML = this.renderPreviewOverlay();
        
        // 툴바
        this.customizeToolbar = document.createElement('div');
        this.customizeToolbar.className = 'layout-customize-toolbar';
        this.customizeToolbar.innerHTML = this.renderCustomizeToolbar();
        
        // DOM에 추가
        document.body.appendChild(this.customizerPanel);
        document.body.appendChild(this.previewOverlay);
        document.body.appendChild(this.customizeToolbar);
        
        // 초기 상태 설정
        this.hide();
    }

    /**
     * 커스터마이저 패널 렌더링
     * @returns {string} HTML 템플릿
     * @private
     */
    renderCustomizerPanel() {
        return `
            <div class="customizer-header">
                <h3>
                    <i class="fas fa-palette"></i>
                    레이아웃 커스터마이징
                </h3>
                <button class="close-btn" type="button">
                    <i class="fas fa-times"></i>
                </button>
            </div>
            
            <div class="customizer-content">
                <div class="layout-tabs">
                    <button class="tab-btn active" data-tab="presets">프리셋</button>
                    <button class="tab-btn" data-tab="custom">커스텀</button>
                    <button class="tab-btn" data-tab="create">생성</button>
                </div>
                
                <div class="tab-content">
                    <div class="tab-panel active" data-panel="presets">
                        ${this.renderPresetsPanel()}
                    </div>
                    
                    <div class="tab-panel" data-panel="custom">
                        ${this.renderCustomPanel()}
                    </div>
                    
                    <div class="tab-panel" data-panel="create">
                        ${this.renderCreatePanel()}
                    </div>
                </div>
            </div>
            
            <div class="customizer-footer">
                <button class="btn btn-secondary cancel-btn">취소</button>
                <button class="btn btn-primary apply-btn">적용</button>
            </div>
        `;
    }

    /**
     * 프리셋 패널 렌더링
     * @returns {string} HTML 템플릿
     * @private
     */
    renderPresetsPanel() {
        const presetCards = Array.from(this.presets.entries()).map(([id, preset]) => `
            <div class="layout-card ${id === this.currentLayout ? 'active' : ''}" 
                 data-layout-id="${id}" data-layout-type="preset">
                <div class="layout-preview">
                    ${this.renderLayoutPreview(preset)}
                </div>
                <div class="layout-info">
                    <h4>
                        <i class="${preset.icon}"></i>
                        ${preset.name}
                    </h4>
                    <p>${preset.description}</p>
                    <div class="layout-stats">
                        <span class="stat">
                            <i class="fas fa-th-large"></i>
                            ${preset.widgets.length} 위젯
                        </span>
                    </div>
                </div>
                <div class="layout-actions">
                    <button class="btn-icon preview-btn" title="미리보기">
                        <i class="fas fa-eye"></i>
                    </button>
                    <button class="btn-icon select-btn" title="선택">
                        <i class="fas fa-check"></i>
                    </button>
                </div>
            </div>
        `).join('');

        return `
            <div class="presets-container">
                <div class="section-header">
                    <h4>프리셋 레이아웃</h4>
                    <p>미리 정의된 레이아웃 중에서 선택하세요</p>
                </div>
                <div class="layout-grid">
                    ${presetCards}
                </div>
            </div>
        `;
    }

    /**
     * 커스텀 패널 렌더링
     * @returns {string} HTML 템플릿
     * @private
     */
    renderCustomPanel() {
        const customCards = Array.from(this.customLayouts.entries()).map(([id, layout]) => `
            <div class="layout-card ${id === this.currentLayout ? 'active' : ''}" 
                 data-layout-id="${id}" data-layout-type="custom">
                <div class="layout-preview">
                    ${this.renderLayoutPreview(layout)}
                </div>
                <div class="layout-info">
                    <h4>
                        <i class="fas fa-user"></i>
                        ${layout.name}
                    </h4>
                    <p>${layout.description || '사용자 정의 레이아웃'}</p>
                    <div class="layout-stats">
                        <span class="stat">
                            <i class="fas fa-th-large"></i>
                            ${layout.widgets.length} 위젯
                        </span>
                        <span class="stat">
                            <i class="fas fa-clock"></i>
                            ${this.formatDate(layout.created)}
                        </span>
                    </div>
                </div>
                <div class="layout-actions">
                    <button class="btn-icon preview-btn" title="미리보기">
                        <i class="fas fa-eye"></i>
                    </button>
                    <button class="btn-icon edit-btn" title="편집">
                        <i class="fas fa-edit"></i>
                    </button>
                    <button class="btn-icon duplicate-btn" title="복제">
                        <i class="fas fa-copy"></i>
                    </button>
                    <button class="btn-icon delete-btn" title="삭제">
                        <i class="fas fa-trash"></i>
                    </button>
                </div>
            </div>
        `).join('');

        return `
            <div class="custom-container">
                <div class="section-header">
                    <h4>커스텀 레이아웃</h4>
                    <p>저장된 사용자 정의 레이아웃</p>
                </div>
                <div class="layout-grid">
                    ${customCards || '<div class="empty-state">저장된 커스텀 레이아웃이 없습니다</div>'}
                </div>
            </div>
        `;
    }

    /**
     * 생성 패널 렌더링
     * @returns {string} HTML 템플릿
     * @private
     */
    renderCreatePanel() {
        return `
            <div class="create-container">
                <div class="section-header">
                    <h4>새 레이아웃 생성</h4>
                    <p>현재 레이아웃을 기반으로 새로운 레이아웃을 만들어보세요</p>
                </div>
                
                <form class="create-form">
                    <div class="form-group">
                        <label for="layout-name">레이아웃 이름</label>
                        <input type="text" id="layout-name" name="name" 
                               placeholder="새 레이아웃 이름을 입력하세요" required>
                    </div>
                    
                    <div class="form-group">
                        <label for="layout-description">설명 (선택사항)</label>
                        <textarea id="layout-description" name="description" 
                                  placeholder="레이아웃에 대한 설명을 입력하세요" rows="3"></textarea>
                    </div>
                    
                    <div class="form-group">
                        <label>기반 레이아웃</label>
                        <div class="base-layout-options">
                            <label class="radio-option">
                                <input type="radio" name="base" value="current" checked>
                                <span>현재 레이아웃</span>
                            </label>
                            <label class="radio-option">
                                <input type="radio" name="base" value="empty">
                                <span>빈 레이아웃</span>
                            </label>
                            <label class="radio-option">
                                <input type="radio" name="base" value="template">
                                <span>템플릿 선택</span>
                            </label>
                        </div>
                    </div>
                    
                    <div class="template-selector" style="display: none;">
                        <select name="template">
                            <option value="">템플릿을 선택하세요</option>
                            ${this.renderTemplateOptions()}
                        </select>
                    </div>
                    
                    <div class="form-actions">
                        <button type="button" class="btn btn-secondary reset-btn">초기화</button>
                        <button type="submit" class="btn btn-primary create-btn">생성</button>
                    </div>
                </form>
                
                <div class="creation-tips">
                    <h5>
                        <i class="fas fa-lightbulb"></i>
                        팁
                    </h5>
                    <ul>
                        <li>위젯을 드래그하여 원하는 위치로 이동할 수 있습니다</li>
                        <li>위젯 모서리를 드래그하여 크기를 조절할 수 있습니다</li>
                        <li>편집 모드에서 위젯을 추가하거나 제거할 수 있습니다</li>
                        <li>레이아웃은 자동으로 저장됩니다</li>
                    </ul>
                </div>
            </div>
        `;
    }

    /**
     * 템플릿 옵션 렌더링
     * @returns {string} 옵션 HTML
     * @private
     */
    renderTemplateOptions() {
        return Array.from(this.templates.entries()).map(([id, template]) => 
            `<option value="${id}">${template.name}</option>`
        ).join('');
    }

    /**
     * 레이아웃 프리뷰 렌더링
     * @param {Object} layout - 레이아웃 데이터
     * @returns {string} 프리뷰 HTML
     * @private
     */
    renderLayoutPreview(layout) {
        const gridCells = 144; // 12x12 그리드
        const cells = Array(gridCells).fill(0);
        
        // 위젯 위치 표시
        layout.widgets.forEach(widget => {
            for (let y = 0; y < widget.size.height; y++) {
                for (let x = 0; x < widget.size.width; x++) {
                    const cellIndex = (widget.position.y + y) * 12 + (widget.position.x + x);
                    if (cellIndex < gridCells) {
                        cells[cellIndex] = widget.type;
                    }
                }
            }
        });
        
        return `
            <div class="layout-preview-grid">
                ${cells.map((cellType, index) => `
                    <div class="preview-cell ${cellType ? 'filled' : ''}" 
                         data-type="${cellType}" 
                         data-index="${index}">
                    </div>
                `).join('')}
            </div>
        `;
    }

    /**
     * 프리뷰 오버레이 렌더링
     * @returns {string} HTML 템플릿
     * @private
     */
    renderPreviewOverlay() {
        return `
            <div class="preview-content">
                <div class="preview-header">
                    <h3>레이아웃 미리보기</h3>
                    <div class="preview-controls">
                        <button class="btn btn-secondary close-preview-btn">닫기</button>
                        <button class="btn btn-primary apply-preview-btn">적용</button>
                    </div>
                </div>
                <div class="preview-container">
                    <!-- 미리보기 위젯들이 여기에 렌더링됩니다 -->
                </div>
            </div>
        `;
    }

    /**
     * 커스터마이즈 툴바 렌더링
     * @returns {string} HTML 템플릿
     * @private
     */
    renderCustomizeToolbar() {
        return `
            <div class="toolbar-content">
                <div class="toolbar-section">
                    <button class="tool-btn edit-toggle-btn" title="편집 모드">
                        <i class="fas fa-edit"></i>
                        편집
                    </button>
                    <button class="tool-btn add-widget-btn" title="위젯 추가">
                        <i class="fas fa-plus"></i>
                        위젯 추가
                    </button>
                </div>
                
                <div class="toolbar-section">
                    <button class="tool-btn grid-toggle-btn" title="그리드 표시">
                        <i class="fas fa-th"></i>
                        그리드
                    </button>
                    <button class="tool-btn snap-toggle-btn active" title="그리드 스냅">
                        <i class="fas fa-magnet"></i>
                        스냅
                    </button>
                </div>
                
                <div class="toolbar-section">
                    <button class="tool-btn save-btn" title="저장">
                        <i class="fas fa-save"></i>
                        저장
                    </button>
                    <button class="tool-btn reset-btn" title="초기화">
                        <i class="fas fa-undo"></i>
                        초기화
                    </button>
                </div>
                
                <div class="toolbar-section">
                    <button class="tool-btn close-toolbar-btn" title="닫기">
                        <i class="fas fa-times"></i>
                    </button>
                </div>
            </div>
        `;
    }

    /**
     * 이벤트 리스너 설정
     * @private
     */
    setupEventListeners() {
        // 커스터마이저 패널 이벤트
        this.bindCustomizerEvents();
        
        // 툴바 이벤트
        this.bindToolbarEvents();
        
        // 전역 이벤트
        eventBus.on('layout:customize', this.show.bind(this));
        eventBus.on('layout:save', this.saveCurrentLayout.bind(this));
        eventBus.on('widget:*', this.handleWidgetEvent.bind(this));
        
        // 키보드 단축키
        document.addEventListener('keydown', this.handleKeyDown.bind(this));
    }

    /**
     * 커스터마이저 이벤트 바인딩
     * @private
     */
    bindCustomizerEvents() {
        if (!this.customizerPanel) return;

        // 탭 전환
        this.customizerPanel.querySelectorAll('.tab-btn').forEach(btn => {
            btn.addEventListener('click', this.handleTabSwitch.bind(this));
        });

        // 닫기 버튼
        const closeBtn = this.customizerPanel.querySelector('.close-btn');
        if (closeBtn) {
            closeBtn.addEventListener('click', this.hide.bind(this));
        }

        // 레이아웃 카드 클릭
        this.customizerPanel.addEventListener('click', this.handleLayoutCardClick.bind(this));

        // 생성 폼
        const createForm = this.customizerPanel.querySelector('.create-form');
        if (createForm) {
            createForm.addEventListener('submit', this.handleCreateLayout.bind(this));
        }

        // 기반 레이아웃 선택
        const baseOptions = this.customizerPanel.querySelectorAll('input[name="base"]');
        baseOptions.forEach(option => {
            option.addEventListener('change', this.handleBaseLayoutChange.bind(this));
        });

        // 적용/취소 버튼
        const applyBtn = this.customizerPanel.querySelector('.apply-btn');
        const cancelBtn = this.customizerPanel.querySelector('.cancel-btn');
        
        if (applyBtn) {
            applyBtn.addEventListener('click', this.applySelectedLayout.bind(this));
        }
        
        if (cancelBtn) {
            cancelBtn.addEventListener('click', this.hide.bind(this));
        }
    }

    /**
     * 툴바 이벤트 바인딩
     * @private
     */
    bindToolbarEvents() {
        if (!this.customizeToolbar) return;

        this.customizeToolbar.addEventListener('click', (event) => {
            const btn = event.target.closest('.tool-btn');
            if (!btn) return;

            const action = btn.className.split(' ').find(cls => cls.includes('-btn'));
            this.handleToolbarAction(action, btn);
        });
    }

    /**
     * 템플릿 등록
     * @private
     */
    registerTemplates() {
        this.templates.set('dashboard', {
            name: '대시보드 기본',
            widgets: [
                { type: 'balance', position: { x: 0, y: 0 }, size: { width: 3, height: 2 } },
                { type: 'chart', position: { x: 3, y: 0 }, size: { width: 6, height: 4 } },
                { type: 'positions', position: { x: 9, y: 0 }, size: { width: 3, height: 6 } }
            ]
        });

        this.templates.set('trader', {
            name: '트레이더 전용',
            widgets: [
                { type: 'chart', position: { x: 0, y: 0 }, size: { width: 8, height: 6 } },
                { type: 'positions', position: { x: 8, y: 0 }, size: { width: 4, height: 6 } }
            ]
        });
    }

    // 공개 메서드들

    /**
     * 커스터마이저 표시
     */
    show() {
        this.isVisible = true;
        this.customizerPanel.classList.add('visible');
        document.body.classList.add('customizer-open');
        
        // 현재 레이아웃 표시
        this.refreshLayoutCards();
        
        eventBus.emit('layout:customizer:opened');
    }

    /**
     * 커스터마이저 숨김
     */
    hide() {
        this.isVisible = false;
        this.customizerPanel.classList.remove('visible');
        document.body.classList.remove('customizer-open');
        
        // 편집 모드 해제
        if (this.state.isEditing) {
            this.toggleEditMode(false);
        }
        
        eventBus.emit('layout:customizer:closed');
    }

    /**
     * 편집 모드 토글
     * @param {boolean} enabled - 편집 모드 활성화 여부
     */
    toggleEditMode(enabled) {
        this.state.isEditing = enabled;
        
        // 위젯 매니저에 편집 모드 설정
        widgetManager.setEditMode(enabled);
        
        // 툴바 표시/숨김
        this.customizeToolbar.classList.toggle('visible', enabled);
        
        // 편집 모드 클래스
        document.body.classList.toggle('layout-edit-mode', enabled);
        
        eventBus.emit('layout:edit-mode:changed', { enabled });
    }

    /**
     * 레이아웃 적용
     * @param {string} layoutId - 레이아웃 ID
     * @param {string} type - 레이아웃 타입 ('preset' | 'custom')
     */
    applyLayout(layoutId, type = 'preset') {
        let layout;
        
        if (type === 'preset') {
            layout = this.presets.get(layoutId);
        } else {
            layout = this.customLayouts.get(layoutId);
        }
        
        if (!layout) {
            console.warn(`Layout not found: ${layoutId}`);
            return;
        }

        // 현재 위젯 제거
        widgetManager.widgets.forEach((widget, widgetId) => {
            widgetManager.removeWidget(widgetId);
        });

        // 새 위젯 생성
        const containers = Array.from(widgetManager.containers.keys());
        const mainContainer = containers[0]; // 첫 번째 컨테이너 사용

        layout.widgets.forEach(widgetConfig => {
            try {
                widgetManager.createWidget(
                    widgetConfig.type, 
                    {
                        position: widgetConfig.position,
                        size: widgetConfig.size,
                        config: widgetConfig.config || {}
                    },
                    mainContainer
                );
            } catch (error) {
                console.warn(`Failed to create widget: ${widgetConfig.type}`, error);
            }
        });

        this.currentLayout = layoutId;
        
        // 레이아웃 저장
        if (this.config.autoSave) {
            this.saveLayoutState();
        }
        
        eventBus.emit('layout:applied', { layoutId, type, layout });
    }

    /**
     * 현재 레이아웃 저장
     */
    saveCurrentLayout() {
        if (!this.state.isDirty) return;

        const layoutData = this.serializeCurrentLayout();
        
        // localStorage에 저장
        localStorage.setItem(`layout-${this.currentLayout}`, JSON.stringify(layoutData));
        
        this.state.isDirty = false;
        
        eventBus.emit('layout:saved', { layoutId: this.currentLayout, layout: layoutData });
    }

    /**
     * 커스텀 레이아웃 생성
     * @param {string} name - 레이아웃 이름
     * @param {string} description - 설명
     * @param {Object} baseLayout - 기반 레이아웃
     * @returns {string} 생성된 레이아웃 ID
     */
    createCustomLayout(name, description = '', baseLayout = null) {
        const layoutId = `custom_${Date.now()}_${Math.random().toString(36).substr(2, 9)}`;
        
        let widgets;
        if (baseLayout) {
            widgets = baseLayout.widgets;
        } else {
            // 현재 레이아웃 기반
            widgets = this.serializeCurrentWidgets();
        }

        const layout = {
            id: layoutId,
            name,
            description,
            widgets,
            created: Date.now(),
            updated: Date.now(),
            version: 1
        };

        this.customLayouts.set(layoutId, layout);
        this.saveCustomLayouts();
        
        eventBus.emit('layout:custom:created', { layoutId, layout });
        
        return layoutId;
    }

    /**
     * 커스텀 레이아웃 삭제
     * @param {string} layoutId - 레이아웃 ID
     */
    deleteCustomLayout(layoutId) {
        if (this.customLayouts.has(layoutId)) {
            this.customLayouts.delete(layoutId);
            this.saveCustomLayouts();
            
            eventBus.emit('layout:custom:deleted', { layoutId });
        }
    }

    /**
     * 레이아웃 복제
     * @param {string} sourceId - 원본 레이아웃 ID
     * @param {string} type - 레이아웃 타입
     * @returns {string} 복제된 레이아웃 ID
     */
    duplicateLayout(sourceId, type = 'custom') {
        let sourceLayout;
        
        if (type === 'preset') {
            sourceLayout = this.presets.get(sourceId);
        } else {
            sourceLayout = this.customLayouts.get(sourceId);
        }
        
        if (!sourceLayout) return null;

        const newName = `${sourceLayout.name} 복사본`;
        return this.createCustomLayout(newName, sourceLayout.description, sourceLayout);
    }

    // 이벤트 핸들러들

    /**
     * 탭 전환 처리
     * @param {Event} event - 클릭 이벤트
     * @private
     */
    handleTabSwitch(event) {
        const tabBtn = event.currentTarget;
        const tabName = tabBtn.dataset.tab;

        // 탭 버튼 상태 업데이트
        this.customizerPanel.querySelectorAll('.tab-btn').forEach(btn => {
            btn.classList.remove('active');
        });
        tabBtn.classList.add('active');

        // 탭 패널 표시/숨김
        this.customizerPanel.querySelectorAll('.tab-panel').forEach(panel => {
            panel.classList.remove('active');
        });
        
        const targetPanel = this.customizerPanel.querySelector(`[data-panel="${tabName}"]`);
        if (targetPanel) {
            targetPanel.classList.add('active');
        }

        // 탭별 추가 로직
        if (tabName === 'custom') {
            this.refreshCustomLayouts();
        }
    }

    /**
     * 레이아웃 카드 클릭 처리
     * @param {Event} event - 클릭 이벤트
     * @private
     */
    handleLayoutCardClick(event) {
        const card = event.target.closest('.layout-card');
        const button = event.target.closest('button');
        
        if (!card) return;

        const layoutId = card.dataset.layoutId;
        const layoutType = card.dataset.layoutType;

        if (button) {
            const action = button.className.split(' ').find(cls => cls.includes('-btn'));
            this.handleLayoutAction(action, layoutId, layoutType);
        } else {
            // 카드 선택
            this.selectLayoutCard(card);
        }
    }

    /**
     * 레이아웃 액션 처리
     * @param {string} action - 액션 타입
     * @param {string} layoutId - 레이아웃 ID
     * @param {string} layoutType - 레이아웃 타입
     * @private
     */
    handleLayoutAction(action, layoutId, layoutType) {
        switch (action) {
            case 'preview-btn':
                this.previewLayout(layoutId, layoutType);
                break;
            case 'select-btn':
                this.applyLayout(layoutId, layoutType);
                break;
            case 'edit-btn':
                this.editLayout(layoutId, layoutType);
                break;
            case 'duplicate-btn':
                this.duplicateLayout(layoutId, layoutType);
                break;
            case 'delete-btn':
                this.confirmDeleteLayout(layoutId);
                break;
        }
    }

    /**
     * 툴바 액션 처리
     * @param {string} action - 액션 타입
     * @param {HTMLElement} button - 버튼 요소
     * @private
     */
    handleToolbarAction(action, button) {
        switch (action) {
            case 'edit-toggle-btn':
                this.toggleEditMode(!this.state.isEditing);
                break;
            case 'add-widget-btn':
                this.showAddWidgetDialog();
                break;
            case 'grid-toggle-btn':
                this.toggleGridDisplay();
                button.classList.toggle('active');
                break;
            case 'snap-toggle-btn':
                this.toggleGridSnap();
                button.classList.toggle('active');
                break;
            case 'save-btn':
                this.saveCurrentLayout();
                break;
            case 'reset-btn':
                this.confirmResetLayout();
                break;
            case 'close-toolbar-btn':
                this.toggleEditMode(false);
                break;
        }
    }

    // 유틸리티 메서드들

    /**
     * 레이아웃 카드 새로고침
     * @private
     */
    refreshLayoutCards() {
        // 프리셋 패널
        const presetsPanel = this.customizerPanel.querySelector('[data-panel="presets"]');
        if (presetsPanel) {
            presetsPanel.innerHTML = this.renderPresetsPanel();
        }

        // 커스텀 패널
        const customPanel = this.customizerPanel.querySelector('[data-panel="custom"]');
        if (customPanel) {
            customPanel.innerHTML = this.renderCustomPanel();
        }
    }

    /**
     * 커스텀 레이아웃 새로고침
     * @private
     */
    refreshCustomLayouts() {
        const customPanel = this.customizerPanel.querySelector('[data-panel="custom"]');
        if (customPanel) {
            customPanel.innerHTML = this.renderCustomPanel();
        }
    }

    /**
     * 현재 레이아웃 직렬화
     * @returns {Object} 직렬화된 레이아웃
     * @private
     */
    serializeCurrentLayout() {
        return {
            name: this.currentLayout,
            widgets: this.serializeCurrentWidgets(),
            updated: Date.now()
        };
    }

    /**
     * 현재 위젯들 직렬화
     * @returns {Array} 위젯 데이터 배열
     * @private
     */
    serializeCurrentWidgets() {
        const widgets = [];
        
        widgetManager.widgets.forEach(widget => {
            widgets.push({
                type: widget.type,
                position: widget.position,
                size: widget.size,
                config: widget.config
            });
        });
        
        return widgets;
    }

    /**
     * 커스텀 레이아웃 저장
     * @private
     */
    saveCustomLayouts() {
        const layouts = {};
        this.customLayouts.forEach((layout, id) => {
            layouts[id] = layout;
        });
        
        localStorage.setItem('dashboard-custom-layouts', JSON.stringify(layouts));
    }

    /**
     * 레이아웃 상태 저장
     * @private
     */
    saveLayoutState() {
        localStorage.setItem('dashboard-current-layout', this.currentLayout);
    }

    /**
     * 날짜 포맷팅
     * @param {number} timestamp - 타임스탬프
     * @returns {string} 포맷된 날짜
     * @private
     */
    formatDate(timestamp) {
        const date = new Date(timestamp);
        const now = new Date();
        const diff = now - date;
        const days = Math.floor(diff / (24 * 60 * 60 * 1000));
        
        if (days === 0) return '오늘';
        if (days === 1) return '어제';
        if (days < 30) return `${days}일 전`;
        
        return date.toLocaleDateString('ko-KR');
    }

    /**
     * 키보드 이벤트 처리
     * @param {KeyboardEvent} event - 키보드 이벤트
     * @private
     */
    handleKeyDown(event) {
        if (!this.isVisible) return;

        switch (event.key) {
            case 'Escape':
                this.hide();
                break;
            case 'Enter':
                if (event.ctrlKey || event.metaKey) {
                    this.applySelectedLayout();
                }
                break;
        }
    }

    // 빈 메서드들 (필요시 구현)
    selectLayoutCard(card) {}
    previewLayout(layoutId, layoutType) {}
    editLayout(layoutId, layoutType) {}
    confirmDeleteLayout(layoutId) {}
    handleCreateLayout(event) {}
    handleBaseLayoutChange(event) {}
    applySelectedLayout() {}
    showAddWidgetDialog() {}
    toggleGridDisplay() {}
    toggleGridSnap() {}
    confirmResetLayout() {}
    handleWidgetEvent(eventData) {}

    /**
     * 정리
     */
    destroy() {
        // DOM 요소 제거
        if (this.customizerPanel && this.customizerPanel.parentNode) {
            this.customizerPanel.parentNode.removeChild(this.customizerPanel);
        }
        
        if (this.previewOverlay && this.previewOverlay.parentNode) {
            this.previewOverlay.parentNode.removeChild(this.previewOverlay);
        }
        
        if (this.customizeToolbar && this.customizeToolbar.parentNode) {
            this.customizeToolbar.parentNode.removeChild(this.customizeToolbar);
        }

        // 이벤트 리스너 제거
        eventBus.off('layout:customize');
        eventBus.off('layout:save');
        eventBus.off('widget:*');
        document.removeEventListener('keydown', this.handleKeyDown);

        // 맵 정리
        this.layouts.clear();
        this.presets.clear();
        this.customLayouts.clear();
        this.templates.clear();
    }
}

// 전역 레이아웃 커스터마이저 인스턴스
export const layoutCustomizer = new LayoutCustomizer();

// 편의 함수들
export const showLayoutCustomizer = () => layoutCustomizer.show();
export const hideLayoutCustomizer = () => layoutCustomizer.hide();
export const applyLayout = (layoutId, type) => layoutCustomizer.applyLayout(layoutId, type);

// 개발 모드에서 전역 접근 가능
if (typeof window !== 'undefined' && process.env.NODE_ENV === 'development') {
    window.__TRADING_DASHBOARD_LAYOUT_CUSTOMIZER__ = layoutCustomizer;
}
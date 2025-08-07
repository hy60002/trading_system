import { BaseComponent } from '../core/BaseComponent.js';

/**
 * 실시간 검색/필터링 시스템
 * - 실시간 검색 결과
 * - 고급 필터링 옵션  
 * - 검색어 하이라이트
 * - 자동완성 기능
 * - 검색 히스토리
 */
export class SearchFilterManager extends BaseComponent {
    constructor() {
        super();
        this.searchInput = null;
        this.filterContainer = null;
        this.resultsContainer = null;
        this.suggestionsList = null;
        
        // 검색 상태
        this.searchQuery = '';
        this.activeFilters = new Map();
        this.searchHistory = JSON.parse(localStorage.getItem('searchHistory') || '[]');
        this.searchResults = [];
        
        // 디바운싱 설정
        this.searchDebounceTime = 300;
        this.searchTimeout = null;
        
        // 필터 정의
        this.filterDefinitions = {
            symbol: {
                label: '심볼',
                type: 'select',
                options: ['BTC', 'ETH', 'ADA', 'DOT', 'SOL', 'MATIC'],
                multiple: true
            },
            side: {
                label: '포지션',
                type: 'select',
                options: ['LONG', 'SHORT'],
                multiple: false
            },
            pnl: {
                label: 'P&L',
                type: 'range',
                min: -1000,
                max: 1000,
                step: 10
            },
            volume: {
                label: '거래량',
                type: 'range',
                min: 0,
                max: 10000,
                step: 100
            },
            status: {
                label: '상태',
                type: 'select',
                options: ['활성', '대기', '완료', '취소'],
                multiple: true
            },
            timeRange: {
                label: '시간범위',
                type: 'daterange'
            }
        };

        // 검색 가능한 데이터 필드
        this.searchableFields = ['symbol', 'side', 'id', 'notes'];
        
        this.init();
    }

    init() {
        this.createSearchInterface();
        this.setupEventListeners();
        this.loadSavedFilters();
    }

    createSearchInterface() {
        this.element = document.createElement('div');
        this.element.className = 'search-filter-manager';
        this.element.setAttribute('role', 'search');
        this.element.setAttribute('aria-label', '거래 검색 및 필터링');

        this.element.innerHTML = `
            <div class="search-container">
                <div class="search-input-wrapper">
                    <input 
                        type="text" 
                        class="search-input" 
                        placeholder="심볼, ID, 메모 검색..."
                        autocomplete="off"
                        aria-label="검색어 입력"
                    >
                    <button class="search-clear" aria-label="검색어 지우기" title="지우기">
                        <svg viewBox="0 0 24 24" width="16" height="16">
                            <path d="M19 6.41L17.59 5 12 10.59 6.41 5 5 6.41 10.59 12 5 17.59 6.41 19 12 13.41 17.59 19 19 17.59 13.41 12z"/>
                        </svg>
                    </button>
                    <div class="search-suggestions" role="listbox" aria-label="검색 제안"></div>
                </div>
                
                <button class="filter-toggle" aria-label="필터 옵션" title="필터">
                    <svg viewBox="0 0 24 24" width="20" height="20">
                        <path d="M10 18h4v-2h-4v2zM3 6v2h18V6H3zm3 7h12v-2H6v2z"/>
                    </svg>
                </button>
            </div>

            <div class="filter-panel" role="region" aria-label="필터 옵션">
                <div class="filter-header">
                    <h3>고급 필터</h3>
                    <div class="filter-actions">
                        <button class="filter-preset" data-preset="recent">최근 거래</button>
                        <button class="filter-preset" data-preset="profitable">수익 포지션</button>
                        <button class="filter-preset" data-preset="losses">손실 포지션</button>
                        <button class="filter-clear">모두 지우기</button>
                    </div>
                </div>
                <div class="filter-controls"></div>
            </div>

            <div class="active-filters" role="region" aria-label="활성 필터"></div>
            
            <div class="search-results" role="region" aria-label="검색 결과">
                <div class="results-header">
                    <span class="results-count">0개 결과</span>
                    <div class="results-sort">
                        <label for="sort-select">정렬:</label>
                        <select id="sort-select" class="sort-select">
                            <option value="relevance">관련도</option>
                            <option value="time">시간순</option>
                            <option value="pnl">수익순</option>
                            <option value="volume">거래량순</option>
                        </select>
                    </div>
                </div>
                <div class="results-content"></div>
            </div>
        `;

        // 요소 참조 저장
        this.searchInput = this.element.querySelector('.search-input');
        this.filterContainer = this.element.querySelector('.filter-controls');
        this.resultsContainer = this.element.querySelector('.results-content');
        this.suggestionsList = this.element.querySelector('.search-suggestions');
        this.activeFiltersContainer = this.element.querySelector('.active-filters');
        this.filterPanel = this.element.querySelector('.filter-panel');
        
        this.createFilterControls();
    }

    createFilterControls() {
        Object.entries(this.filterDefinitions).forEach(([key, definition]) => {
            const filterGroup = document.createElement('div');
            filterGroup.className = 'filter-group';
            filterGroup.innerHTML = this.createFilterHTML(key, definition);
            this.filterContainer.appendChild(filterGroup);
        });
    }

    createFilterHTML(key, definition) {
        switch (definition.type) {
            case 'select':
                return `
                    <label class="filter-label">${definition.label}</label>
                    <select 
                        class="filter-select" 
                        data-filter="${key}"
                        ${definition.multiple ? 'multiple' : ''}
                        aria-label="${definition.label} 필터"
                    >
                        ${definition.multiple ? '' : '<option value="">전체</option>'}
                        ${definition.options.map(option => 
                            `<option value="${option}">${option}</option>`
                        ).join('')}
                    </select>
                `;
            
            case 'range':
                return `
                    <label class="filter-label">${definition.label}</label>
                    <div class="range-filter" data-filter="${key}">
                        <input 
                            type="number" 
                            class="range-min" 
                            placeholder="최소값"
                            min="${definition.min}"
                            max="${definition.max}"
                            step="${definition.step}"
                            aria-label="${definition.label} 최소값"
                        >
                        <span class="range-separator">~</span>
                        <input 
                            type="number" 
                            class="range-max" 
                            placeholder="최대값"
                            min="${definition.min}"
                            max="${definition.max}"
                            step="${definition.step}"
                            aria-label="${definition.label} 최대값"
                        >
                    </div>
                `;
            
            case 'daterange':
                return `
                    <label class="filter-label">${definition.label}</label>
                    <div class="date-range-filter" data-filter="${key}">
                        <input 
                            type="date" 
                            class="date-start"
                            aria-label="시작 날짜"
                        >
                        <span class="date-separator">~</span>
                        <input 
                            type="date" 
                            class="date-end"
                            aria-label="종료 날짜"
                        >
                    </div>
                `;
            
            default:
                return '';
        }
    }

    setupEventListeners() {
        // 검색 입력 이벤트
        this.searchInput.addEventListener('input', this.handleSearchInput.bind(this));
        this.searchInput.addEventListener('focus', this.showSuggestions.bind(this));
        this.searchInput.addEventListener('blur', this.hideSuggestionsDelayed.bind(this));
        this.searchInput.addEventListener('keydown', this.handleKeyNavigation.bind(this));

        // 검색어 지우기
        this.element.querySelector('.search-clear').addEventListener('click', this.clearSearch.bind(this));

        // 필터 토글
        this.element.querySelector('.filter-toggle').addEventListener('click', this.toggleFilterPanel.bind(this));

        // 필터 변경 이벤트
        this.filterContainer.addEventListener('change', this.handleFilterChange.bind(this));
        this.filterContainer.addEventListener('input', this.debounce(this.handleFilterChange.bind(this), 500));

        // 필터 프리셋
        this.element.querySelectorAll('.filter-preset').forEach(btn => {
            btn.addEventListener('click', (e) => this.applyPreset(e.target.dataset.preset));
        });

        // 모든 필터 지우기
        this.element.querySelector('.filter-clear').addEventListener('click', this.clearAllFilters.bind(this));

        // 정렬 변경
        this.element.querySelector('.sort-select').addEventListener('change', this.handleSortChange.bind(this));

        // 외부 클릭시 제안 숨기기
        document.addEventListener('click', (e) => {
            if (!this.element.contains(e.target)) {
                this.hideSuggestions();
            }
        });
    }

    handleSearchInput(e) {
        const query = e.target.value.trim();
        this.searchQuery = query;
        
        // 검색어 지우기 버튼 표시/숨기기
        this.element.querySelector('.search-clear').style.display = query ? 'block' : 'none';

        // 디바운스된 검색 실행
        clearTimeout(this.searchTimeout);
        this.searchTimeout = setTimeout(() => {
            this.performSearch();
            this.updateSuggestions();
        }, this.searchDebounceTime);
    }

    performSearch() {
        // 이벤트 버스를 통해 검색 요청
        this.eventBus.emit('search:request', {
            query: this.searchQuery,
            filters: this.getActiveFilters()
        });

        // 검색 히스토리에 추가
        if (this.searchQuery && !this.searchHistory.includes(this.searchQuery)) {
            this.searchHistory.unshift(this.searchQuery);
            this.searchHistory = this.searchHistory.slice(0, 10); // 최대 10개 유지
            localStorage.setItem('searchHistory', JSON.stringify(this.searchHistory));
        }
    }

    updateResults(results) {
        this.searchResults = results;
        const count = results.length;
        
        // 결과 개수 업데이트
        this.element.querySelector('.results-count').textContent = `${count}개 결과`;
        
        // 결과 렌더링
        this.resultsContainer.innerHTML = '';
        
        if (count === 0) {
            this.resultsContainer.innerHTML = `
                <div class="no-results">
                    <p>검색 결과가 없습니다.</p>
                    <p>다른 검색어나 필터를 시도해보세요.</p>
                </div>
            `;
            return;
        }

        results.forEach(result => {
            const resultElement = this.createResultElement(result);
            this.resultsContainer.appendChild(resultElement);
        });
    }

    createResultElement(data) {
        const element = document.createElement('div');
        element.className = 'search-result-item';
        element.innerHTML = `
            <div class="result-header">
                <span class="result-symbol">${this.highlightText(data.symbol)}</span>
                <span class="result-side ${data.side.toLowerCase()}">${data.side}</span>
            </div>
            <div class="result-details">
                <span class="result-pnl ${data.pnl >= 0 ? 'positive' : 'negative'}">
                    ${data.pnl >= 0 ? '+' : ''}${data.pnl.toFixed(2)} USDT
                </span>
                <span class="result-volume">${data.volume.toLocaleString()}</span>
            </div>
            ${data.notes ? `<div class="result-notes">${this.highlightText(data.notes)}</div>` : ''}
        `;

        // 클릭 이벤트
        element.addEventListener('click', () => {
            this.eventBus.emit('search:selectResult', data);
        });

        return element;
    }

    highlightText(text) {
        if (!this.searchQuery || typeof text !== 'string') return text;
        
        const regex = new RegExp(`(${this.escapeRegExp(this.searchQuery)})`, 'gi');
        return text.replace(regex, '<mark class="search-highlight">$1</mark>');
    }

    escapeRegExp(string) {
        return string.replace(/[.*+?^${}()|[\]\\]/g, '\\$&');
    }

    updateSuggestions() {
        const suggestions = this.generateSuggestions();
        this.suggestionsList.innerHTML = '';
        
        suggestions.forEach((suggestion, index) => {
            const item = document.createElement('div');
            item.className = 'suggestion-item';
            item.setAttribute('role', 'option');
            item.setAttribute('aria-selected', 'false');
            item.textContent = suggestion;
            
            item.addEventListener('click', () => {
                this.searchInput.value = suggestion;
                this.searchQuery = suggestion;
                this.hideSuggestions();
                this.performSearch();
            });
            
            this.suggestionsList.appendChild(item);
        });
    }

    generateSuggestions() {
        const suggestions = new Set();
        
        // 검색 히스토리에서 매칭되는 항목들
        this.searchHistory.forEach(item => {
            if (item.toLowerCase().includes(this.searchQuery.toLowerCase())) {
                suggestions.add(item);
            }
        });
        
        // 자주 검색되는 키워드들
        const commonKeywords = ['BTC', 'ETH', 'LONG', 'SHORT', 'profit', 'loss'];
        commonKeywords.forEach(keyword => {
            if (keyword.toLowerCase().includes(this.searchQuery.toLowerCase())) {
                suggestions.add(keyword);
            }
        });
        
        return Array.from(suggestions).slice(0, 5);
    }

    showSuggestions() {
        if (this.searchQuery || this.searchHistory.length > 0) {
            this.suggestionsList.style.display = 'block';
            this.updateSuggestions();
        }
    }

    hideSuggestions() {
        this.suggestionsList.style.display = 'none';
    }

    hideSuggestionsDelayed() {
        setTimeout(() => this.hideSuggestions(), 150);
    }

    handleKeyNavigation(e) {
        const suggestions = this.suggestionsList.querySelectorAll('.suggestion-item');
        const current = this.suggestionsList.querySelector('[aria-selected="true"]');
        let currentIndex = current ? Array.from(suggestions).indexOf(current) : -1;

        switch (e.key) {
            case 'ArrowDown':
                e.preventDefault();
                currentIndex = Math.min(currentIndex + 1, suggestions.length - 1);
                break;
            case 'ArrowUp':
                e.preventDefault();
                currentIndex = Math.max(currentIndex - 1, -1);
                break;
            case 'Enter':
                if (current) {
                    e.preventDefault();
                    current.click();
                    return;
                }
                break;
            case 'Escape':
                this.hideSuggestions();
                return;
        }

        // 선택 상태 업데이트
        suggestions.forEach((item, index) => {
            item.setAttribute('aria-selected', index === currentIndex ? 'true' : 'false');
        });
    }

    handleFilterChange(e) {
        const filterElement = e.target;
        const filterKey = filterElement.closest('[data-filter]').dataset.filter;
        
        this.updateFilter(filterKey);
        this.performSearch();
        this.updateActiveFilters();
    }

    updateFilter(filterKey) {
        const filterGroup = this.element.querySelector(`[data-filter="${filterKey}"]`);
        const definition = this.filterDefinitions[filterKey];
        let value = null;

        switch (definition.type) {
            case 'select':
                const select = filterGroup.querySelector('select');
                if (definition.multiple) {
                    const selected = Array.from(select.selectedOptions).map(opt => opt.value);
                    value = selected.length > 0 ? selected : null;
                } else {
                    value = select.value || null;
                }
                break;
                
            case 'range':
                const min = filterGroup.querySelector('.range-min').value;
                const max = filterGroup.querySelector('.range-max').value;
                if (min || max) {
                    value = { min: min ? parseFloat(min) : null, max: max ? parseFloat(max) : null };
                }
                break;
                
            case 'daterange':
                const start = filterGroup.querySelector('.date-start').value;
                const end = filterGroup.querySelector('.date-end').value;
                if (start || end) {
                    value = { start, end };
                }
                break;
        }

        if (value !== null) {
            this.activeFilters.set(filterKey, value);
        } else {
            this.activeFilters.delete(filterKey);
        }
    }

    updateActiveFilters() {
        this.activeFiltersContainer.innerHTML = '';
        
        this.activeFilters.forEach((value, key) => {
            const tag = document.createElement('div');
            tag.className = 'filter-tag';
            
            const definition = this.filterDefinitions[key];
            const displayValue = this.getFilterDisplayValue(value, definition);
            
            tag.innerHTML = `
                <span class="filter-label">${definition.label}:</span>
                <span class="filter-value">${displayValue}</span>
                <button class="filter-remove" data-filter="${key}" aria-label="${definition.label} 필터 제거">
                    <svg viewBox="0 0 24 24" width="14" height="14">
                        <path d="M19 6.41L17.59 5 12 10.59 6.41 5 5 6.41 10.59 12 5 17.59 6.41 19 12 13.41 17.59 19 19 17.59 13.41 12z"/>
                    </svg>
                </button>
            `;
            
            tag.querySelector('.filter-remove').addEventListener('click', () => {
                this.removeFilter(key);
            });
            
            this.activeFiltersContainer.appendChild(tag);
        });
    }

    getFilterDisplayValue(value, definition) {
        switch (definition.type) {
            case 'select':
                return Array.isArray(value) ? value.join(', ') : value;
            case 'range':
                return `${value.min || '∞'} ~ ${value.max || '∞'}`;
            case 'daterange':
                return `${value.start || ''} ~ ${value.end || ''}`;
            default:
                return value;
        }
    }

    removeFilter(filterKey) {
        this.activeFilters.delete(filterKey);
        this.resetFilterControl(filterKey);
        this.performSearch();
        this.updateActiveFilters();
    }

    resetFilterControl(filterKey) {
        const filterGroup = this.element.querySelector(`[data-filter="${filterKey}"]`);
        const definition = this.filterDefinitions[filterKey];
        
        switch (definition.type) {
            case 'select':
                const select = filterGroup.querySelector('select');
                select.selectedIndex = 0;
                if (definition.multiple) {
                    Array.from(select.options).forEach(opt => opt.selected = false);
                }
                break;
            case 'range':
                filterGroup.querySelector('.range-min').value = '';
                filterGroup.querySelector('.range-max').value = '';
                break;
            case 'daterange':
                filterGroup.querySelector('.date-start').value = '';
                filterGroup.querySelector('.date-end').value = '';
                break;
        }
    }

    applyPreset(presetName) {
        this.clearAllFilters();
        
        const now = new Date();
        const today = now.toISOString().split('T')[0];
        
        switch (presetName) {
            case 'recent':
                const yesterday = new Date(now - 24 * 60 * 60 * 1000).toISOString().split('T')[0];
                this.activeFilters.set('timeRange', { start: yesterday, end: today });
                break;
                
            case 'profitable':
                this.activeFilters.set('pnl', { min: 0, max: null });
                break;
                
            case 'losses':
                this.activeFilters.set('pnl', { min: null, max: 0 });
                break;
        }
        
        this.updateFilterControlsFromState();
        this.performSearch();
        this.updateActiveFilters();
    }

    updateFilterControlsFromState() {
        this.activeFilters.forEach((value, key) => {
            const filterGroup = this.element.querySelector(`[data-filter="${key}"]`);
            const definition = this.filterDefinitions[key];
            
            switch (definition.type) {
                case 'range':
                    if (value.min !== null) {
                        filterGroup.querySelector('.range-min').value = value.min;
                    }
                    if (value.max !== null) {
                        filterGroup.querySelector('.range-max').value = value.max;
                    }
                    break;
                case 'daterange':
                    if (value.start) {
                        filterGroup.querySelector('.date-start').value = value.start;
                    }
                    if (value.end) {
                        filterGroup.querySelector('.date-end').value = value.end;
                    }
                    break;
            }
        });
    }

    clearAllFilters() {
        this.activeFilters.clear();
        
        // 모든 필터 컨트롤 초기화
        Object.keys(this.filterDefinitions).forEach(key => {
            this.resetFilterControl(key);
        });
        
        this.performSearch();
        this.updateActiveFilters();
    }

    clearSearch() {
        this.searchInput.value = '';
        this.searchQuery = '';
        this.element.querySelector('.search-clear').style.display = 'none';
        this.hideSuggestions();
        this.performSearch();
    }

    toggleFilterPanel() {
        const isVisible = this.filterPanel.style.display !== 'none';
        this.filterPanel.style.display = isVisible ? 'none' : 'block';
        
        // 아이콘 회전 효과
        const icon = this.element.querySelector('.filter-toggle svg');
        icon.style.transform = isVisible ? 'rotate(0deg)' : 'rotate(180deg)';
    }

    handleSortChange(e) {
        const sortBy = e.target.value;
        this.eventBus.emit('search:sort', sortBy);
    }

    getActiveFilters() {
        const filters = {};
        this.activeFilters.forEach((value, key) => {
            filters[key] = value;
        });
        return filters;
    }

    loadSavedFilters() {
        const savedFilters = localStorage.getItem('savedSearchFilters');
        if (savedFilters) {
            try {
                const filters = JSON.parse(savedFilters);
                Object.entries(filters).forEach(([key, value]) => {
                    this.activeFilters.set(key, value);
                });
                this.updateFilterControlsFromState();
                this.updateActiveFilters();
            } catch (e) {
                console.warn('Failed to load saved filters:', e);
            }
        }
    }

    saveFilters() {
        const filters = this.getActiveFilters();
        localStorage.setItem('savedSearchFilters', JSON.stringify(filters));
    }

    debounce(func, wait) {
        let timeout;
        return function executedFunction(...args) {
            const later = () => {
                clearTimeout(timeout);
                func(...args);
            };
            clearTimeout(timeout);
            timeout = setTimeout(later, wait);
        };
    }

    destroy() {
        this.saveFilters();
        super.destroy();
    }
}
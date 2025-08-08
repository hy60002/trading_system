/**
 * 🎨 ThemeManager.js - 완전한 테마 관리 시스템
 * 6개 내장 테마, 커스텀 테마 생성/수정/삭제, 시스템 테마 자동 감지
 * 749 lines - DASHBOARD_IMPROVEMENT_COMPLETE.md 요구사항
 */

class ThemeManager {
    constructor() {
        this.currentTheme = 'auto';
        this.customThemes = new Map();
        this.themeChangeCallbacks = new Set();
        this.systemThemeMediaQuery = window.matchMedia('(prefers-color-scheme: dark)');
        
        // 6개 내장 테마 정의
        this.builtInThemes = {
            light: {
                name: 'Light',
                type: 'light',
                colors: {
                    // 기본 색상
                    primary: '#2563eb',
                    primaryHover: '#1d4ed8',
                    secondary: '#64748b',
                    accent: '#3b82f6',
                    
                    // 배경 색상
                    background: '#ffffff',
                    backgroundSecondary: '#f8fafc',
                    backgroundTertiary: '#f1f5f9',
                    
                    // 표면 색상
                    surface: '#ffffff',
                    surfaceSecondary: '#f8fafc',
                    card: '#ffffff',
                    modal: '#ffffff',
                    
                    // 텍스트 색상
                    text: '#1e293b',
                    textSecondary: '#64748b',
                    textMuted: '#94a3b8',
                    textInverse: '#ffffff',
                    
                    // 테두리 색상
                    border: '#e2e8f0',
                    borderSecondary: '#cbd5e1',
                    divider: '#f1f5f9',
                    
                    // 상태 색상
                    success: '#10b981',
                    successBackground: '#ecfdf5',
                    warning: '#f59e0b',
                    warningBackground: '#fffbeb',
                    danger: '#ef4444',
                    dangerBackground: '#fef2f2',
                    info: '#3b82f6',
                    infoBackground: '#eff6ff',
                    
                    // 차트 색상
                    profit: '#10b981',
                    loss: '#ef4444',
                    neutral: '#64748b',
                    
                    // 그라디언트
                    gradient: 'linear-gradient(135deg, #667eea 0%, #764ba2 100%)',
                    gradientSecondary: 'linear-gradient(135deg, #f093fb 0%, #f5576c 100%)',
                    
                    // 그림자
                    shadow: '0 1px 3px 0 rgba(0, 0, 0, 0.1), 0 1px 2px 0 rgba(0, 0, 0, 0.06)',
                    shadowLg: '0 10px 15px -3px rgba(0, 0, 0, 0.1), 0 4px 6px -2px rgba(0, 0, 0, 0.05)'
                }
            },
            
            dark: {
                name: 'Dark',
                type: 'dark',
                colors: {
                    // 기본 색상
                    primary: '#3b82f6',
                    primaryHover: '#2563eb',
                    secondary: '#6b7280',
                    accent: '#60a5fa',
                    
                    // 배경 색상
                    background: '#0f172a',
                    backgroundSecondary: '#1e293b',
                    backgroundTertiary: '#334155',
                    
                    // 표면 색상
                    surface: '#1e293b',
                    surfaceSecondary: '#334155',
                    card: '#1e293b',
                    modal: '#1e293b',
                    
                    // 텍스트 색상
                    text: '#f8fafc',
                    textSecondary: '#cbd5e1',
                    textMuted: '#94a3b8',
                    textInverse: '#1e293b',
                    
                    // 테두리 색상
                    border: '#334155',
                    borderSecondary: '#475569',
                    divider: '#334155',
                    
                    // 상태 색상
                    success: '#10b981',
                    successBackground: '#064e3b',
                    warning: '#f59e0b',
                    warningBackground: '#451a03',
                    danger: '#ef4444',
                    dangerBackground: '#450a0a',
                    info: '#3b82f6',
                    infoBackground: '#1e3a8a',
                    
                    // 차트 색상
                    profit: '#10b981',
                    loss: '#ef4444',
                    neutral: '#94a3b8',
                    
                    // 그라디언트
                    gradient: 'linear-gradient(135deg, #667eea 0%, #764ba2 100%)',
                    gradientSecondary: 'linear-gradient(135deg, #f093fb 0%, #f5576c 100%)',
                    
                    // 그림자
                    shadow: '0 1px 3px 0 rgba(0, 0, 0, 0.3), 0 1px 2px 0 rgba(0, 0, 0, 0.2)',
                    shadowLg: '0 10px 15px -3px rgba(0, 0, 0, 0.3), 0 4px 6px -2px rgba(0, 0, 0, 0.2)'
                }
            },
            
            blue: {
                name: 'Ocean Blue',
                type: 'dark',
                colors: {
                    primary: '#0ea5e9',
                    primaryHover: '#0284c7',
                    secondary: '#64748b',
                    accent: '#38bdf8',
                    
                    background: '#0c1426',
                    backgroundSecondary: '#1e293b',
                    backgroundTertiary: '#334155',
                    
                    surface: '#1e293b',
                    surfaceSecondary: '#334155',
                    card: '#1e293b',
                    modal: '#1e293b',
                    
                    text: '#f0f9ff',
                    textSecondary: '#cbd5e1',
                    textMuted: '#94a3b8',
                    textInverse: '#0c1426',
                    
                    border: '#334155',
                    borderSecondary: '#475569',
                    divider: '#334155',
                    
                    success: '#10b981',
                    successBackground: '#064e3b',
                    warning: '#f59e0b',
                    warningBackground: '#451a03',
                    danger: '#ef4444',
                    dangerBackground: '#450a0a',
                    info: '#0ea5e9',
                    infoBackground: '#0c4a6e',
                    
                    profit: '#10b981',
                    loss: '#ef4444',
                    neutral: '#94a3b8',
                    
                    gradient: 'linear-gradient(135deg, #0ea5e9 0%, #3b82f6 100%)',
                    gradientSecondary: 'linear-gradient(135deg, #38bdf8 0%, #0ea5e9 100%)',
                    
                    shadow: '0 1px 3px 0 rgba(14, 165, 233, 0.1), 0 1px 2px 0 rgba(0, 0, 0, 0.2)',
                    shadowLg: '0 10px 15px -3px rgba(14, 165, 233, 0.2), 0 4px 6px -2px rgba(0, 0, 0, 0.2)'
                }
            },
            
            green: {
                name: 'Forest Green',
                type: 'dark',
                colors: {
                    primary: '#10b981',
                    primaryHover: '#059669',
                    secondary: '#6b7280',
                    accent: '#34d399',
                    
                    background: '#0a1f1a',
                    backgroundSecondary: '#1e2d23',
                    backgroundTertiary: '#2d3b2d',
                    
                    surface: '#1e2d23',
                    surfaceSecondary: '#2d3b2d',
                    card: '#1e2d23',
                    modal: '#1e2d23',
                    
                    text: '#f0fdf4',
                    textSecondary: '#cbd5e1',
                    textMuted: '#94a3b8',
                    textInverse: '#0a1f1a',
                    
                    border: '#2d3b2d',
                    borderSecondary: '#3b4b3b',
                    divider: '#2d3b2d',
                    
                    success: '#10b981',
                    successBackground: '#064e3b',
                    warning: '#f59e0b',
                    warningBackground: '#451a03',
                    danger: '#ef4444',
                    dangerBackground: '#450a0a',
                    info: '#3b82f6',
                    infoBackground: '#1e3a8a',
                    
                    profit: '#10b981',
                    loss: '#ef4444',
                    neutral: '#94a3b8',
                    
                    gradient: 'linear-gradient(135deg, #10b981 0%, #059669 100%)',
                    gradientSecondary: 'linear-gradient(135deg, #34d399 0%, #10b981 100%)',
                    
                    shadow: '0 1px 3px 0 rgba(16, 185, 129, 0.1), 0 1px 2px 0 rgba(0, 0, 0, 0.2)',
                    shadowLg: '0 10px 15px -3px rgba(16, 185, 129, 0.2), 0 4px 6px -2px rgba(0, 0, 0, 0.2)'
                }
            },
            
            purple: {
                name: 'Royal Purple',
                type: 'dark',
                colors: {
                    primary: '#8b5cf6',
                    primaryHover: '#7c3aed',
                    secondary: '#6b7280',
                    accent: '#a78bfa',
                    
                    background: '#1a0a26',
                    backgroundSecondary: '#2d1b3d',
                    backgroundTertiary: '#3b2655',
                    
                    surface: '#2d1b3d',
                    surfaceSecondary: '#3b2655',
                    card: '#2d1b3d',
                    modal: '#2d1b3d',
                    
                    text: '#faf5ff',
                    textSecondary: '#cbd5e1',
                    textMuted: '#94a3b8',
                    textInverse: '#1a0a26',
                    
                    border: '#3b2655',
                    borderSecondary: '#4c366d',
                    divider: '#3b2655',
                    
                    success: '#10b981',
                    successBackground: '#064e3b',
                    warning: '#f59e0b',
                    warningBackground: '#451a03',
                    danger: '#ef4444',
                    dangerBackground: '#450a0a',
                    info: '#8b5cf6',
                    infoBackground: '#581c87',
                    
                    profit: '#10b981',
                    loss: '#ef4444',
                    neutral: '#94a3b8',
                    
                    gradient: 'linear-gradient(135deg, #8b5cf6 0%, #7c3aed 100%)',
                    gradientSecondary: 'linear-gradient(135deg, #a78bfa 0%, #8b5cf6 100%)',
                    
                    shadow: '0 1px 3px 0 rgba(139, 92, 246, 0.1), 0 1px 2px 0 rgba(0, 0, 0, 0.2)',
                    shadowLg: '0 10px 15px -3px rgba(139, 92, 246, 0.2), 0 4px 6px -2px rgba(0, 0, 0, 0.2)'
                }
            },
            
            auto: {
                name: 'Auto (System)',
                type: 'auto',
                colors: null // 시스템 설정에 따라 동적으로 결정
            }
        };
        
        this.init();
    }
    
    /**
     * 테마 매니저 초기화
     */
    init() {
        // 저장된 테마 및 커스텀 테마 로드
        this.loadSavedTheme();
        this.loadCustomThemes();
        
        // 시스템 테마 변경 감지
        this.systemThemeMediaQuery.addEventListener('change', (e) => {
            if (this.currentTheme === 'auto') {
                this.applyTheme('auto');
            }
        });
        
        // 초기 테마 적용
        this.applyTheme(this.currentTheme);
        
        console.log('🎨 ThemeManager initialized with 6 built-in themes');
    }
    
    /**
     * 테마 변경
     * @param {string} themeId - 테마 ID
     */
    setTheme(themeId) {
        if (this.isValidTheme(themeId)) {
            this.currentTheme = themeId;
            this.applyTheme(themeId);
            this.saveTheme(themeId);
            this.notifyThemeChange(themeId);
        } else {
            console.error(`Unknown theme: ${themeId}`);
        }
    }
    
    /**
     * 현재 테마 반환
     */
    getCurrentTheme() {
        return this.currentTheme;
    }
    
    /**
     * 테마가 유효한지 확인
     */
    isValidTheme(themeId) {
        return this.builtInThemes.hasOwnProperty(themeId) || this.customThemes.has(themeId);
    }
    
    /**
     * 테마 적용
     */
    applyTheme(themeId) {
        let theme;
        
        if (themeId === 'auto') {
            // 시스템 설정에 따라 자동 선택
            const isDark = this.systemThemeMediaQuery.matches;
            theme = this.builtInThemes[isDark ? 'dark' : 'light'];
        } else if (this.builtInThemes[themeId]) {
            theme = this.builtInThemes[themeId];
        } else if (this.customThemes.has(themeId)) {
            theme = this.customThemes.get(themeId);
        } else {
            console.error(`Cannot apply unknown theme: ${themeId}`);
            return;
        }
        
        // CSS 변수로 색상 적용
        this.applyCSSVariables(theme.colors);
        
        // 테마 타입 클래스 적용
        document.body.className = document.body.className.replace(/theme-\w+/g, '');
        if (theme.type !== 'auto') {
            document.body.classList.add(`theme-${theme.type}`);
        }
        
        // 메타 테마 컬러 업데이트 (모바일 브라우저)
        this.updateMetaThemeColor(theme.colors);
        
        console.log(`🎨 Applied theme: ${theme.name}`);
    }
    
    /**
     * CSS 변수 적용
     */
    applyCSSVariables(colors) {
        if (!colors) return;
        
        const root = document.documentElement;
        Object.entries(colors).forEach(([key, value]) => {
            root.style.setProperty(`--color-${this.camelToKebab(key)}`, value);
        });
    }
    
    /**
     * 메타 테마 컬러 업데이트
     */
    updateMetaThemeColor(colors) {
        if (!colors) return;
        
        let metaThemeColor = document.querySelector('meta[name="theme-color"]');
        if (!metaThemeColor) {
            metaThemeColor = document.createElement('meta');
            metaThemeColor.name = 'theme-color';
            document.head.appendChild(metaThemeColor);
        }
        
        metaThemeColor.content = colors.primary || '#2563eb';
    }
    
    /**
     * 커스텀 테마 생성
     */
    createCustomTheme(id, name, baseTheme, customColors = {}) {
        const base = this.builtInThemes[baseTheme] || this.builtInThemes.light;
        
        const customTheme = {
            name: name,
            type: base.type,
            isCustom: true,
            baseTheme: baseTheme,
            colors: {
                ...base.colors,
                ...customColors
            }
        };
        
        this.customThemes.set(id, customTheme);
        this.saveCustomThemes();
        
        console.log(`🎨 Created custom theme: ${name}`);
        return customTheme;
    }
    
    /**
     * 커스텀 테마 수정
     */
    updateCustomTheme(id, updates) {
        if (!this.customThemes.has(id)) {
            console.error(`Custom theme not found: ${id}`);
            return false;
        }
        
        const theme = this.customThemes.get(id);
        
        if (updates.name) theme.name = updates.name;
        if (updates.colors) {
            theme.colors = { ...theme.colors, ...updates.colors };
        }
        
        this.customThemes.set(id, theme);
        this.saveCustomThemes();
        
        // 현재 테마가 수정된 테마인 경우 다시 적용
        if (this.currentTheme === id) {
            this.applyTheme(id);
        }
        
        console.log(`🎨 Updated custom theme: ${theme.name}`);
        return true;
    }
    
    /**
     * 커스텀 테마 삭제
     */
    deleteCustomTheme(id) {
        if (!this.customThemes.has(id)) {
            console.error(`Custom theme not found: ${id}`);
            return false;
        }
        
        // 현재 사용 중인 테마를 삭제하는 경우 기본 테마로 변경
        if (this.currentTheme === id) {
            this.setTheme('light');
        }
        
        const themeName = this.customThemes.get(id).name;
        this.customThemes.delete(id);
        this.saveCustomThemes();
        
        console.log(`🗑️ Deleted custom theme: ${themeName}`);
        return true;
    }
    
    /**
     * 모든 테마 목록 반환
     */
    getAllThemes() {
        const themes = [];
        
        // 내장 테마
        Object.entries(this.builtInThemes).forEach(([id, theme]) => {
            themes.push({
                id,
                name: theme.name,
                type: theme.type,
                isCustom: false
            });
        });
        
        // 커스텀 테마
        this.customThemes.forEach((theme, id) => {
            themes.push({
                id,
                name: theme.name,
                type: theme.type,
                isCustom: true,
                baseTheme: theme.baseTheme
            });
        });
        
        return themes;
    }
    
    /**
     * 테마 색상 반환
     */
    getThemeColors(themeId) {
        if (themeId === 'auto') {
            const isDark = this.systemThemeMediaQuery.matches;
            return this.builtInThemes[isDark ? 'dark' : 'light'].colors;
        }
        
        if (this.builtInThemes[themeId]) {
            return this.builtInThemes[themeId].colors;
        }
        
        if (this.customThemes.has(themeId)) {
            return this.customThemes.get(themeId).colors;
        }
        
        return null;
    }
    
    /**
     * 테마 변경 콜백 등록
     */
    onThemeChange(callback) {
        if (typeof callback === 'function') {
            this.themeChangeCallbacks.add(callback);
        }
    }
    
    /**
     * 테마 변경 콜백 제거
     */
    offThemeChange(callback) {
        this.themeChangeCallbacks.delete(callback);
    }
    
    /**
     * 테마 변경 알림
     */
    notifyThemeChange(themeId) {
        const theme = this.getThemeInfo(themeId);
        this.themeChangeCallbacks.forEach(callback => {
            try {
                callback(themeId, theme);
            } catch (error) {
                console.error('Theme change callback error:', error);
            }
        });
    }
    
    /**
     * 테마 정보 반환
     */
    getThemeInfo(themeId) {
        if (themeId === 'auto') {
            const isDark = this.systemThemeMediaQuery.matches;
            return {
                id: 'auto',
                name: 'Auto (System)',
                type: 'auto',
                activeTheme: isDark ? 'dark' : 'light',
                isCustom: false
            };
        }
        
        if (this.builtInThemes[themeId]) {
            return {
                id: themeId,
                name: this.builtInThemes[themeId].name,
                type: this.builtInThemes[themeId].type,
                isCustom: false
            };
        }
        
        if (this.customThemes.has(themeId)) {
            const theme = this.customThemes.get(themeId);
            return {
                id: themeId,
                name: theme.name,
                type: theme.type,
                isCustom: true,
                baseTheme: theme.baseTheme
            };
        }
        
        return null;
    }
    
    /**
     * 테마 미리보기 CSS 생성
     */
    generatePreviewCSS(colors) {
        let css = '';
        Object.entries(colors).forEach(([key, value]) => {
            css += `--preview-${this.camelToKebab(key)}: ${value};\n`;
        });
        return css;
    }
    
    /**
     * 테마 내보내기 (JSON)
     */
    exportTheme(themeId) {
        let theme;
        
        if (this.builtInThemes[themeId]) {
            theme = { ...this.builtInThemes[themeId] };
        } else if (this.customThemes.has(themeId)) {
            theme = { ...this.customThemes.get(themeId) };
        } else {
            throw new Error(`Theme not found: ${themeId}`);
        }
        
        return {
            id: themeId,
            exportDate: new Date().toISOString(),
            version: '1.0',
            theme: theme
        };
    }
    
    /**
     * 테마 가져오기 (JSON)
     */
    importTheme(themeData, customId = null) {
        try {
            const { theme } = themeData;
            const id = customId || `imported_${Date.now()}`;
            
            this.customThemes.set(id, {
                ...theme,
                isCustom: true,
                imported: true,
                importDate: new Date().toISOString()
            });
            
            this.saveCustomThemes();
            console.log(`📥 Imported theme: ${theme.name}`);
            return id;
            
        } catch (error) {
            console.error('Failed to import theme:', error);
            throw error;
        }
    }
    
    /**
     * 시스템 다크 모드 감지
     */
    isSystemDarkMode() {
        return this.systemThemeMediaQuery.matches;
    }
    
    /**
     * 저장된 테마 로드
     */
    loadSavedTheme() {
        const saved = localStorage.getItem('dashboard-theme');
        if (saved && this.isValidTheme(saved)) {
            this.currentTheme = saved;
        }
    }
    
    /**
     * 테마 저장
     */
    saveTheme(themeId) {
        localStorage.setItem('dashboard-theme', themeId);
    }
    
    /**
     * 커스텀 테마들 로드
     */
    loadCustomThemes() {
        const saved = localStorage.getItem('dashboard-custom-themes');
        if (saved) {
            try {
                const themes = JSON.parse(saved);
                Object.entries(themes).forEach(([id, theme]) => {
                    this.customThemes.set(id, theme);
                });
                console.log(`📦 Loaded ${this.customThemes.size} custom themes`);
            } catch (error) {
                console.error('Failed to load custom themes:', error);
            }
        }
    }
    
    /**
     * 커스텀 테마들 저장
     */
    saveCustomThemes() {
        const themes = {};
        this.customThemes.forEach((theme, id) => {
            themes[id] = theme;
        });
        localStorage.setItem('dashboard-custom-themes', JSON.stringify(themes));
    }
    
    /**
     * camelCase를 kebab-case로 변환
     */
    camelToKebab(str) {
        return str.replace(/([a-z0-9]|(?=[A-Z]))([A-Z])/g, '$1-$2').toLowerCase();
    }
    
    /**
     * 테마 변수 스타일 시트 생성
     */
    generateThemeStylesheet() {
        const currentColors = this.getThemeColors(this.currentTheme);
        if (!currentColors) return '';
        
        let css = ':root {\n';
        Object.entries(currentColors).forEach(([key, value]) => {
            css += `  --color-${this.camelToKebab(key)}: ${value};\n`;
        });
        css += '}\n';
        
        return css;
    }
    
    /**
     * 접근성을 위한 고대비 모드 토글
     */
    toggleHighContrast() {
        const isHighContrast = document.body.classList.contains('high-contrast');
        
        if (isHighContrast) {
            document.body.classList.remove('high-contrast');
            localStorage.removeItem('high-contrast-mode');
        } else {
            document.body.classList.add('high-contrast');
            localStorage.setItem('high-contrast-mode', 'true');
        }
        
        console.log(`🔍 High contrast mode: ${!isHighContrast ? 'ON' : 'OFF'}`);
        return !isHighContrast;
    }
    
    /**
     * 고대비 모드 상태 확인
     */
    isHighContrastEnabled() {
        return document.body.classList.contains('high-contrast');
    }
    
    /**
     * 테마 매니저 파괴 (cleanup)
     */
    destroy() {
        this.systemThemeMediaQuery.removeEventListener('change', this.handleSystemThemeChange);
        this.themeChangeCallbacks.clear();
        this.customThemes.clear();
    }
}

// 전역 인스턴스 생성
window.themeManager = new ThemeManager();

console.log('🎨 ThemeManager.js loaded - 6 built-in themes + custom theme support');

export default ThemeManager;
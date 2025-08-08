/**
 * 🌍 I18nManager.js - 완전한 국제화 관리 시스템
 * 9개 언어 지원, RTL 언어 지원, 동적 언어 변경, 날짜/숫자 현지화
 * 847 lines - DASHBOARD_IMPROVEMENT_COMPLETE.md 요구사항
 */

class I18nManager {
    constructor() {
        this.currentLanguage = 'ko';
        this.fallbackLanguage = 'en';
        this.translations = new Map();
        this.languageChangeCallbacks = new Set();
        this.rtlLanguages = new Set(['ar', 'he', 'fa', 'ur']);
        
        // 지원 언어 정의
        this.supportedLanguages = {
            ko: {
                name: '한국어',
                nativeName: '한국어',
                code: 'ko',
                region: 'KR',
                rtl: false,
                dateFormat: 'YYYY-MM-DD',
                timeFormat: 'HH:mm:ss',
                numberFormat: {
                    decimal: '.',
                    thousands: ',',
                    currency: '₩'
                }
            },
            en: {
                name: 'English',
                nativeName: 'English',
                code: 'en',
                region: 'US',
                rtl: false,
                dateFormat: 'MM/DD/YYYY',
                timeFormat: 'hh:mm:ss A',
                numberFormat: {
                    decimal: '.',
                    thousands: ',',
                    currency: '$'
                }
            },
            ja: {
                name: '日本語',
                nativeName: '日本語',
                code: 'ja',
                region: 'JP',
                rtl: false,
                dateFormat: 'YYYY/MM/DD',
                timeFormat: 'HH:mm:ss',
                numberFormat: {
                    decimal: '.',
                    thousands: ',',
                    currency: '¥'
                }
            },
            zh: {
                name: '中文',
                nativeName: '中文',
                code: 'zh',
                region: 'CN',
                rtl: false,
                dateFormat: 'YYYY-MM-DD',
                timeFormat: 'HH:mm:ss',
                numberFormat: {
                    decimal: '.',
                    thousands: ',',
                    currency: '¥'
                }
            },
            de: {
                name: 'Deutsch',
                nativeName: 'Deutsch',
                code: 'de',
                region: 'DE',
                rtl: false,
                dateFormat: 'DD.MM.YYYY',
                timeFormat: 'HH:mm:ss',
                numberFormat: {
                    decimal: ',',
                    thousands: '.',
                    currency: '€'
                }
            },
            fr: {
                name: 'Français',
                nativeName: 'Français',
                code: 'fr',
                region: 'FR',
                rtl: false,
                dateFormat: 'DD/MM/YYYY',
                timeFormat: 'HH:mm:ss',
                numberFormat: {
                    decimal: ',',
                    thousands: ' ',
                    currency: '€'
                }
            },
            es: {
                name: 'Español',
                nativeName: 'Español',
                code: 'es',
                region: 'ES',
                rtl: false,
                dateFormat: 'DD/MM/YYYY',
                timeFormat: 'HH:mm:ss',
                numberFormat: {
                    decimal: ',',
                    thousands: '.',
                    currency: '€'
                }
            },
            ar: {
                name: 'العربية',
                nativeName: 'العربية',
                code: 'ar',
                region: 'SA',
                rtl: true,
                dateFormat: 'DD/MM/YYYY',
                timeFormat: 'HH:mm:ss',
                numberFormat: {
                    decimal: '.',
                    thousands: ',',
                    currency: 'ر.س'
                }
            },
            ru: {
                name: 'Русский',
                nativeName: 'Русский',
                code: 'ru',
                region: 'RU',
                rtl: false,
                dateFormat: 'DD.MM.YYYY',
                timeFormat: 'HH:mm:ss',
                numberFormat: {
                    decimal: ',',
                    thousands: ' ',
                    currency: '₽'
                }
            }
        };
        
        // 기본 번역 데이터
        this.defaultTranslations = {
            ko: {
                // 네비게이션
                'nav.dashboard': '대시보드',
                'nav.trading': '거래',
                'nav.portfolio': '포트폴리오',
                'nav.history': '거래 내역',
                'nav.settings': '설정',
                'nav.logout': '로그아웃',
                
                // 대시보드
                'dashboard.title': 'Trading Dashboard',
                'dashboard.overview': '개요',
                'dashboard.totalBalance': '총 잔고',
                'dashboard.totalPnL': '총 손익',
                'dashboard.dayChange': '일일 변화',
                'dashboard.positions': '포지션',
                'dashboard.orders': '주문',
                'dashboard.performance': '성과',
                
                // 거래
                'trading.buy': '매수',
                'trading.sell': '매도',
                'trading.long': 'Long',
                'trading.short': 'Short',
                'trading.amount': '수량',
                'trading.price': '가격',
                'trading.total': '총액',
                'trading.leverage': '레버리지',
                'trading.stopLoss': '손절가',
                'trading.takeProfit': '익절가',
                'trading.orderType': '주문 유형',
                'trading.market': '시장가',
                'trading.limit': '지정가',
                'trading.placeOrder': '주문하기',
                
                // 포트폴리오
                'portfolio.totalValue': '총 가치',
                'portfolio.availableBalance': '사용 가능 잔고',
                'portfolio.marginUsed': '사용 마진',
                'portfolio.freeMargin': '여유 마진',
                'portfolio.marginRatio': '마진 비율',
                'portfolio.unrealizedPnL': '미실현 손익',
                'portfolio.realizedPnL': '실현 손익',
                
                // 공통
                'common.loading': '로딩 중...',
                'common.error': '오류',
                'common.success': '성공',
                'common.warning': '경고',
                'common.info': '정보',
                'common.confirm': '확인',
                'common.cancel': '취소',
                'common.save': '저장',
                'common.edit': '편집',
                'common.delete': '삭제',
                'common.close': '닫기',
                'common.refresh': '새로고침',
                'common.search': '검색',
                'common.filter': '필터',
                'common.sort': '정렬',
                'common.date': '날짜',
                'common.time': '시간',
                'common.status': '상태',
                'common.active': '활성',
                'common.inactive': '비활성',
                
                // 상태 메시지
                'status.connected': '연결됨',
                'status.disconnected': '연결 끊김',
                'status.connecting': '연결 중...',
                'status.reconnecting': '재연결 중...',
                'status.online': '온라인',
                'status.offline': '오프라인',
                
                // 설정
                'settings.general': '일반',
                'settings.appearance': '외관',
                'settings.language': '언어',
                'settings.theme': '테마',
                'settings.notifications': '알림',
                'settings.trading': '거래 설정',
                'settings.api': 'API 설정',
                'settings.security': '보안',
                'settings.about': '정보',
                
                // 오류 메시지
                'error.networkError': '네트워크 오류가 발생했습니다',
                'error.serverError': '서버 오류가 발생했습니다',
                'error.invalidInput': '입력값이 올바르지 않습니다',
                'error.unauthorized': '인증이 필요합니다',
                'error.forbidden': '접근이 금지되었습니다',
                'error.notFound': '요청한 데이터를 찾을 수 없습니다',
                'error.timeout': '요청 시간이 초과되었습니다'
            },
            
            en: {
                // Navigation
                'nav.dashboard': 'Dashboard',
                'nav.trading': 'Trading',
                'nav.portfolio': 'Portfolio',
                'nav.history': 'History',
                'nav.settings': 'Settings',
                'nav.logout': 'Logout',
                
                // Dashboard
                'dashboard.title': 'Trading Dashboard',
                'dashboard.overview': 'Overview',
                'dashboard.totalBalance': 'Total Balance',
                'dashboard.totalPnL': 'Total P&L',
                'dashboard.dayChange': 'Day Change',
                'dashboard.positions': 'Positions',
                'dashboard.orders': 'Orders',
                'dashboard.performance': 'Performance',
                
                // Trading
                'trading.buy': 'Buy',
                'trading.sell': 'Sell',
                'trading.long': 'Long',
                'trading.short': 'Short',
                'trading.amount': 'Amount',
                'trading.price': 'Price',
                'trading.total': 'Total',
                'trading.leverage': 'Leverage',
                'trading.stopLoss': 'Stop Loss',
                'trading.takeProfit': 'Take Profit',
                'trading.orderType': 'Order Type',
                'trading.market': 'Market',
                'trading.limit': 'Limit',
                'trading.placeOrder': 'Place Order',
                
                // Portfolio
                'portfolio.totalValue': 'Total Value',
                'portfolio.availableBalance': 'Available Balance',
                'portfolio.marginUsed': 'Margin Used',
                'portfolio.freeMargin': 'Free Margin',
                'portfolio.marginRatio': 'Margin Ratio',
                'portfolio.unrealizedPnL': 'Unrealized P&L',
                'portfolio.realizedPnL': 'Realized P&L',
                
                // Common
                'common.loading': 'Loading...',
                'common.error': 'Error',
                'common.success': 'Success',
                'common.warning': 'Warning',
                'common.info': 'Info',
                'common.confirm': 'Confirm',
                'common.cancel': 'Cancel',
                'common.save': 'Save',
                'common.edit': 'Edit',
                'common.delete': 'Delete',
                'common.close': 'Close',
                'common.refresh': 'Refresh',
                'common.search': 'Search',
                'common.filter': 'Filter',
                'common.sort': 'Sort',
                'common.date': 'Date',
                'common.time': 'Time',
                'common.status': 'Status',
                'common.active': 'Active',
                'common.inactive': 'Inactive',
                
                // Status messages
                'status.connected': 'Connected',
                'status.disconnected': 'Disconnected',
                'status.connecting': 'Connecting...',
                'status.reconnecting': 'Reconnecting...',
                'status.online': 'Online',
                'status.offline': 'Offline',
                
                // Settings
                'settings.general': 'General',
                'settings.appearance': 'Appearance',
                'settings.language': 'Language',
                'settings.theme': 'Theme',
                'settings.notifications': 'Notifications',
                'settings.trading': 'Trading Settings',
                'settings.api': 'API Settings',
                'settings.security': 'Security',
                'settings.about': 'About',
                
                // Error messages
                'error.networkError': 'Network error occurred',
                'error.serverError': 'Server error occurred',
                'error.invalidInput': 'Invalid input',
                'error.unauthorized': 'Authentication required',
                'error.forbidden': 'Access forbidden',
                'error.notFound': 'Requested data not found',
                'error.timeout': 'Request timeout'
            },
            
            ja: {
                'nav.dashboard': 'ダッシュボード',
                'nav.trading': '取引',
                'nav.portfolio': 'ポートフォリオ',
                'nav.history': '履歴',
                'nav.settings': '設定',
                'nav.logout': 'ログアウト',
                'dashboard.title': '取引ダッシュボード',
                'dashboard.totalBalance': '総残高',
                'dashboard.totalPnL': '総損益',
                'trading.buy': '買い',
                'trading.sell': '売り',
                'common.loading': '読み込み中...',
                'common.error': 'エラー',
                'common.success': '成功',
                'common.cancel': 'キャンセル'
            },
            
            zh: {
                'nav.dashboard': '仪表板',
                'nav.trading': '交易',
                'nav.portfolio': '投资组合',
                'nav.history': '历史',
                'nav.settings': '设置',
                'nav.logout': '登出',
                'dashboard.title': '交易仪表板',
                'dashboard.totalBalance': '总余额',
                'dashboard.totalPnL': '总损益',
                'trading.buy': '买入',
                'trading.sell': '卖出',
                'common.loading': '加载中...',
                'common.error': '错误',
                'common.success': '成功',
                'common.cancel': '取消'
            },
            
            de: {
                'nav.dashboard': 'Dashboard',
                'nav.trading': 'Handel',
                'nav.portfolio': 'Portfolio',
                'nav.history': 'Verlauf',
                'nav.settings': 'Einstellungen',
                'nav.logout': 'Abmelden',
                'dashboard.title': 'Trading Dashboard',
                'dashboard.totalBalance': 'Gesamtsaldo',
                'dashboard.totalPnL': 'Gesamt-P&L',
                'trading.buy': 'Kaufen',
                'trading.sell': 'Verkaufen',
                'common.loading': 'Laden...',
                'common.error': 'Fehler',
                'common.success': 'Erfolg',
                'common.cancel': 'Abbrechen'
            },
            
            fr: {
                'nav.dashboard': 'Tableau de bord',
                'nav.trading': 'Trading',
                'nav.portfolio': 'Portefeuille',
                'nav.history': 'Historique',
                'nav.settings': 'Paramètres',
                'nav.logout': 'Déconnexion',
                'dashboard.title': 'Tableau de bord de trading',
                'dashboard.totalBalance': 'Solde total',
                'dashboard.totalPnL': 'P&L total',
                'trading.buy': 'Acheter',
                'trading.sell': 'Vendre',
                'common.loading': 'Chargement...',
                'common.error': 'Erreur',
                'common.success': 'Succès',
                'common.cancel': 'Annuler'
            },
            
            es: {
                'nav.dashboard': 'Panel',
                'nav.trading': 'Trading',
                'nav.portfolio': 'Cartera',
                'nav.history': 'Historial',
                'nav.settings': 'Configuración',
                'nav.logout': 'Cerrar sesión',
                'dashboard.title': 'Panel de trading',
                'dashboard.totalBalance': 'Balance total',
                'dashboard.totalPnL': 'P&L total',
                'trading.buy': 'Comprar',
                'trading.sell': 'Vender',
                'common.loading': 'Cargando...',
                'common.error': 'Error',
                'common.success': 'Éxito',
                'common.cancel': 'Cancelar'
            },
            
            ar: {
                'nav.dashboard': 'لوحة التحكم',
                'nav.trading': 'التداول',
                'nav.portfolio': 'المحفظة',
                'nav.history': 'التاريخ',
                'nav.settings': 'الإعدادات',
                'nav.logout': 'تسجيل الخروج',
                'dashboard.title': 'لوحة تحكم التداول',
                'dashboard.totalBalance': 'الرصيد الإجمالي',
                'dashboard.totalPnL': 'إجمالي الربح والخسارة',
                'trading.buy': 'شراء',
                'trading.sell': 'بيع',
                'common.loading': 'جاري التحميل...',
                'common.error': 'خطأ',
                'common.success': 'نجح',
                'common.cancel': 'إلغاء'
            },
            
            ru: {
                'nav.dashboard': 'Панель управления',
                'nav.trading': 'Торговля',
                'nav.portfolio': 'Портфолио',
                'nav.history': 'История',
                'nav.settings': 'Настройки',
                'nav.logout': 'Выйти',
                'dashboard.title': 'Торговая панель',
                'dashboard.totalBalance': 'Общий баланс',
                'dashboard.totalPnL': 'Общий P&L',
                'trading.buy': 'Купить',
                'trading.sell': 'Продать',
                'common.loading': 'Загрузка...',
                'common.error': 'Ошибка',
                'common.success': 'Успех',
                'common.cancel': 'Отмена'
            }
        };
        
        this.init();
    }
    
    /**
     * I18n 매니저 초기화
     */
    init() {
        // 저장된 언어 로드
        this.loadSavedLanguage();
        
        // 기본 번역 데이터 로드
        Object.entries(this.defaultTranslations).forEach(([lang, translations]) => {
            this.translations.set(lang, new Map(Object.entries(translations)));
        });
        
        // 브라우저 언어 감지
        this.detectBrowserLanguage();
        
        // 초기 언어 적용
        this.applyLanguage(this.currentLanguage);
        
        console.log(`🌍 I18nManager initialized with ${Object.keys(this.supportedLanguages).length} languages`);
    }
    
    /**
     * 언어 변경
     */
    setLanguage(languageCode) {
        if (this.isLanguageSupported(languageCode)) {
            this.currentLanguage = languageCode;
            this.applyLanguage(languageCode);
            this.saveLanguage(languageCode);
            this.notifyLanguageChange(languageCode);
        } else {
            console.error(`Unsupported language: ${languageCode}`);
        }
    }
    
    /**
     * 현재 언어 반환
     */
    getCurrentLanguage() {
        return this.currentLanguage;
    }
    
    /**
     * 언어가 지원되는지 확인
     */
    isLanguageSupported(languageCode) {
        return this.supportedLanguages.hasOwnProperty(languageCode);
    }
    
    /**
     * 언어 적용
     */
    applyLanguage(languageCode) {
        const language = this.supportedLanguages[languageCode];
        if (!language) return;
        
        // HTML lang 속성 설정
        document.documentElement.lang = languageCode;
        
        // RTL 지원
        if (language.rtl) {
            document.documentElement.dir = 'rtl';
            document.body.classList.add('rtl');
        } else {
            document.documentElement.dir = 'ltr';
            document.body.classList.remove('rtl');
        }
        
        // 언어별 CSS 클래스 적용
        document.body.className = document.body.className.replace(/lang-\w+/g, '');
        document.body.classList.add(`lang-${languageCode}`);
        
        // 자동 번역 적용
        this.updatePageTranslations();
        
        console.log(`🌍 Applied language: ${language.name} (${languageCode})`);
    }
    
    /**
     * 텍스트 번역
     */
    t(key, params = {}) {
        // 현재 언어에서 찾기
        let translation = this.getTranslation(this.currentLanguage, key);
        
        // 없으면 fallback 언어에서 찾기
        if (!translation && this.currentLanguage !== this.fallbackLanguage) {
            translation = this.getTranslation(this.fallbackLanguage, key);
        }
        
        // 여전히 없으면 키를 그대로 반환
        if (!translation) {
            console.warn(`Missing translation for key: ${key}`);
            return key;
        }
        
        // 파라미터 치환
        return this.interpolate(translation, params);
    }
    
    /**
     * 번역 데이터 가져오기
     */
    getTranslation(languageCode, key) {
        const langTranslations = this.translations.get(languageCode);
        return langTranslations ? langTranslations.get(key) : null;
    }
    
    /**
     * 번역 텍스트에 파라미터 삽입
     */
    interpolate(text, params) {
        return text.replace(/\{\{(\w+)\}\}/g, (match, key) => {
            return params.hasOwnProperty(key) ? params[key] : match;
        });
    }
    
    /**
     * 페이지의 모든 번역 업데이트
     */
    updatePageTranslations() {
        // data-i18n 속성을 가진 요소들 찾기
        const elements = document.querySelectorAll('[data-i18n]');
        
        elements.forEach(element => {
            const key = element.getAttribute('data-i18n');
            const params = this.parseDataParams(element);
            const translation = this.t(key, params);
            
            // 텍스트 또는 HTML 설정
            if (element.hasAttribute('data-i18n-html')) {
                element.innerHTML = translation;
            } else {
                element.textContent = translation;
            }
        });
        
        // placeholder 번역
        const placeholderElements = document.querySelectorAll('[data-i18n-placeholder]');
        placeholderElements.forEach(element => {
            const key = element.getAttribute('data-i18n-placeholder');
            element.placeholder = this.t(key);
        });
        
        // title 번역
        const titleElements = document.querySelectorAll('[data-i18n-title]');
        titleElements.forEach(element => {
            const key = element.getAttribute('data-i18n-title');
            element.title = this.t(key);
        });
    }
    
    /**
     * 데이터 속성에서 파라미터 파싱
     */
    parseDataParams(element) {
        const paramsAttr = element.getAttribute('data-i18n-params');
        if (!paramsAttr) return {};
        
        try {
            return JSON.parse(paramsAttr);
        } catch (error) {
            console.warn('Invalid i18n params:', paramsAttr);
            return {};
        }
    }
    
    /**
     * 번역 데이터 추가/업데이트
     */
    addTranslations(languageCode, translations) {
        if (!this.translations.has(languageCode)) {
            this.translations.set(languageCode, new Map());
        }
        
        const langMap = this.translations.get(languageCode);
        Object.entries(translations).forEach(([key, value]) => {
            langMap.set(key, value);
        });
        
        // 현재 언어인 경우 페이지 업데이트
        if (languageCode === this.currentLanguage) {
            this.updatePageTranslations();
        }
    }
    
    /**
     * 숫자 현지화
     */
    formatNumber(number, options = {}) {
        const language = this.supportedLanguages[this.currentLanguage];
        const locale = `${this.currentLanguage}-${language.region}`;
        
        return new Intl.NumberFormat(locale, {
            minimumFractionDigits: options.decimals || 0,
            maximumFractionDigits: options.decimals || 2,
            useGrouping: options.useGrouping !== false,
            ...options
        }).format(number);
    }
    
    /**
     * 통화 현지화
     */
    formatCurrency(amount, currency = null) {
        const language = this.supportedLanguages[this.currentLanguage];
        const locale = `${this.currentLanguage}-${language.region}`;
        const currencyCode = currency || this.getCurrencyCode();
        
        return new Intl.NumberFormat(locale, {
            style: 'currency',
            currency: currencyCode,
            minimumFractionDigits: 2,
            maximumFractionDigits: 2
        }).format(amount);
    }
    
    /**
     * 날짜 현지화
     */
    formatDate(date, options = {}) {
        const language = this.supportedLanguages[this.currentLanguage];
        const locale = `${this.currentLanguage}-${language.region}`;
        
        const defaultOptions = {
            year: 'numeric',
            month: '2-digit',
            day: '2-digit'
        };
        
        return new Intl.DateTimeFormat(locale, {
            ...defaultOptions,
            ...options
        }).format(new Date(date));
    }
    
    /**
     * 시간 현지화
     */
    formatTime(date, options = {}) {
        const language = this.supportedLanguages[this.currentLanguage];
        const locale = `${this.currentLanguage}-${language.region}`;
        
        const defaultOptions = {
            hour: '2-digit',
            minute: '2-digit',
            second: '2-digit'
        };
        
        return new Intl.DateTimeFormat(locale, {
            ...defaultOptions,
            ...options
        }).format(new Date(date));
    }
    
    /**
     * 상대 시간 현지화 (예: "2분 전")
     */
    formatRelativeTime(date) {
        const language = this.supportedLanguages[this.currentLanguage];
        const locale = `${this.currentLanguage}-${language.region}`;
        
        const rtf = new Intl.RelativeTimeFormat(locale, { numeric: 'auto' });
        const diff = Date.now() - new Date(date).getTime();
        const seconds = Math.floor(diff / 1000);
        const minutes = Math.floor(seconds / 60);
        const hours = Math.floor(minutes / 60);
        const days = Math.floor(hours / 24);
        
        if (days > 0) return rtf.format(-days, 'day');
        if (hours > 0) return rtf.format(-hours, 'hour');
        if (minutes > 0) return rtf.format(-minutes, 'minute');
        return rtf.format(-seconds, 'second');
    }
    
    /**
     * 현재 언어의 통화 코드 반환
     */
    getCurrencyCode() {
        const language = this.supportedLanguages[this.currentLanguage];
        const currencyMap = {
            'ko': 'KRW',
            'en': 'USD',
            'ja': 'JPY',
            'zh': 'CNY',
            'de': 'EUR',
            'fr': 'EUR',
            'es': 'EUR',
            'ar': 'SAR',
            'ru': 'RUB'
        };
        
        return currencyMap[this.currentLanguage] || 'USD';
    }
    
    /**
     * RTL 언어 확인
     */
    isRTL(languageCode = null) {
        const lang = languageCode || this.currentLanguage;
        return this.supportedLanguages[lang]?.rtl || false;
    }
    
    /**
     * 지원 언어 목록 반환
     */
    getSupportedLanguages() {
        return Object.entries(this.supportedLanguages).map(([code, info]) => ({
            code,
            name: info.name,
            nativeName: info.nativeName,
            rtl: info.rtl
        }));
    }
    
    /**
     * 브라우저 언어 감지
     */
    detectBrowserLanguage() {
        const browserLang = navigator.language || navigator.userLanguage;
        const langCode = browserLang.split('-')[0];
        
        if (this.isLanguageSupported(langCode) && !localStorage.getItem('dashboard-language')) {
            this.currentLanguage = langCode;
        }
    }
    
    /**
     * 언어 변경 콜백 등록
     */
    onLanguageChange(callback) {
        if (typeof callback === 'function') {
            this.languageChangeCallbacks.add(callback);
        }
    }
    
    /**
     * 언어 변경 콜백 제거
     */
    offLanguageChange(callback) {
        this.languageChangeCallbacks.delete(callback);
    }
    
    /**
     * 언어 변경 알림
     */
    notifyLanguageChange(languageCode) {
        const languageInfo = this.supportedLanguages[languageCode];
        this.languageChangeCallbacks.forEach(callback => {
            try {
                callback(languageCode, languageInfo);
            } catch (error) {
                console.error('Language change callback error:', error);
            }
        });
    }
    
    /**
     * 번역 데이터 내보내기
     */
    exportTranslations(languageCode) {
        const translations = this.translations.get(languageCode);
        if (!translations) return null;
        
        const exportData = {};
        translations.forEach((value, key) => {
            exportData[key] = value;
        });
        
        return {
            language: languageCode,
            languageInfo: this.supportedLanguages[languageCode],
            translations: exportData,
            exportDate: new Date().toISOString()
        };
    }
    
    /**
     * 번역 데이터 가져오기
     */
    importTranslations(translationData) {
        try {
            const { language, translations } = translationData;
            this.addTranslations(language, translations);
            console.log(`📥 Imported translations for ${language}`);
            return true;
        } catch (error) {
            console.error('Failed to import translations:', error);
            return false;
        }
    }
    
    /**
     * 저장된 언어 로드
     */
    loadSavedLanguage() {
        const saved = localStorage.getItem('dashboard-language');
        if (saved && this.isLanguageSupported(saved)) {
            this.currentLanguage = saved;
        }
    }
    
    /**
     * 언어 저장
     */
    saveLanguage(languageCode) {
        localStorage.setItem('dashboard-language', languageCode);
    }
    
    /**
     * 다국어 지원 HTML 요소 생성 헬퍼
     */
    createElement(tagName, translationKey, params = {}) {
        const element = document.createElement(tagName);
        element.setAttribute('data-i18n', translationKey);
        
        if (Object.keys(params).length > 0) {
            element.setAttribute('data-i18n-params', JSON.stringify(params));
        }
        
        element.textContent = this.t(translationKey, params);
        return element;
    }
    
    /**
     * 언어 선택기 UI 생성
     */
    createLanguageSelector(container) {
        const select = document.createElement('select');
        select.className = 'language-selector';
        
        this.getSupportedLanguages().forEach(lang => {
            const option = document.createElement('option');
            option.value = lang.code;
            option.textContent = `${lang.nativeName} (${lang.name})`;
            if (lang.code === this.currentLanguage) {
                option.selected = true;
            }
            select.appendChild(option);
        });
        
        select.addEventListener('change', (e) => {
            this.setLanguage(e.target.value);
        });
        
        if (container) {
            container.appendChild(select);
        }
        
        return select;
    }
    
    /**
     * I18n 매니저 파괴 (cleanup)
     */
    destroy() {
        this.languageChangeCallbacks.clear();
        this.translations.clear();
    }
}

// 전역 인스턴스 생성
window.i18nManager = new I18nManager();

console.log('🌍 I18nManager.js loaded - 9 languages + RTL support');

export default I18nManager;
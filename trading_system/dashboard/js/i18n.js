/**
 * @fileoverview 국제화 관련 전역 함수들
 * @description HTML에서 사용할 수 있는 언어 관련 함수들
 */

// 언어 메뉴 토글
function toggleLanguageMenu() {
    const menu = document.getElementById('language-menu');
    if (menu) {
        const isVisible = menu.style.display === 'block';
        menu.style.display = isVisible ? 'none' : 'block';
        
        // 외부 클릭 시 메뉴 닫기
        if (!isVisible) {
            setTimeout(() => {
                document.addEventListener('click', closeLanguageMenuOnOutsideClick, { once: true });
            }, 0);
        }
    }
}

// 외부 클릭 시 언어 메뉴 닫기
function closeLanguageMenuOnOutsideClick(event) {
    const menu = document.getElementById('language-menu');
    const toggle = document.querySelector('.language-toggle');
    
    if (menu && toggle && !toggle.contains(event.target) && !menu.contains(event.target)) {
        menu.style.display = 'none';
    }
}

// 언어 변경
function changeLanguage(languageCode) {
    console.log('🌐 언어 변경 요청:', languageCode);
    
    // 대시보드 앱이 로드되어 있는지 확인
    if (window.dashboardApp && window.dashboardApp.i18nManager) {
        window.dashboardApp.i18nManager.setLanguage(languageCode).then(success => {
            if (success) {
                updateLanguageUI(languageCode);
                
                // 메뉴 닫기
                const menu = document.getElementById('language-menu');
                if (menu) {
                    menu.style.display = 'none';
                }
                
                console.log('✅ 언어 변경 완료:', languageCode);
            } else {
                console.error('❌ 언어 변경 실패:', languageCode);
            }
        });
    } else {
        // 대시보드 앱이 로드되기 전이면 localStorage에 저장
        localStorage.setItem('trading_dashboard_language', languageCode);
        
        // 간단한 UI 업데이트
        updateLanguageUI(languageCode);
        
        // 메뉴 닫기
        const menu = document.getElementById('language-menu');
        if (menu) {
            menu.style.display = 'none';
        }
        
        // 페이지 새로고침으로 언어 적용
        setTimeout(() => {
            window.location.reload();
        }, 100);
    }
}

// 언어 UI 업데이트
function updateLanguageUI(languageCode) {
    const languageNames = {
        ko: '한국어',
        en: 'English',
        ja: '日本語',
        zh: '中文',
        de: 'Deutsch',
        fr: 'Français',
        es: 'Español',
        ar: 'العربية',
        ru: 'Русский'
    };
    
    const currentLanguageSpan = document.getElementById('current-language');
    if (currentLanguageSpan && languageNames[languageCode]) {
        currentLanguageSpan.textContent = languageNames[languageCode];
    }
    
    // HTML lang 속성 업데이트
    document.documentElement.lang = languageCode;
    
    // RTL 언어 처리
    if (languageCode === 'ar') {
        document.documentElement.dir = 'rtl';
    } else {
        document.documentElement.dir = 'ltr';
    }
}

// DOM 로드 완료 후 초기화
document.addEventListener('DOMContentLoaded', () => {
    // 저장된 언어 설정 확인
    const savedLanguage = localStorage.getItem('trading_dashboard_language');
    if (savedLanguage) {
        updateLanguageUI(savedLanguage);
    }
});

// 전역 함수로 내보내기
window.toggleLanguageMenu = toggleLanguageMenu;
window.changeLanguage = changeLanguage;
window.updateLanguageUI = updateLanguageUI;
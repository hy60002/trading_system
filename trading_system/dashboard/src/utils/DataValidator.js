/**
 * @fileoverview 데이터 검증 및 sanitization 유틸리티
 * @description 입력 데이터의 유효성 검사와 보안 처리
 */

/**
 * 데이터 검증기
 * @class DataValidator
 */
export class DataValidator {
    constructor() {
        // 검증 스키마 정의
        this.schemas = new Map();
        this.setupDefaultSchemas();
        
        // 보안 패턴 정의
        this.securityPatterns = {
            xss: /<script\b[^<]*(?:(?!<\/script>)<[^<]*)*<\/script>/gi,
            sqlInjection: /('|(\\'))|(-{2})|(;)|(\|)|(%)|(\*)/gi,
            htmlTags: /<[^>]*>/g,
            specialChars: /[<>\"'&]/g,
            email: /^[^\s@]+@[^\s@]+\.[^\s@]+$/,
            url: /^https?:\/\/[\w\-]+(\.[\w\-]+)+([\w\-\._~:/?#[\]@!\$&'\(\)\*\+,;=.]+)?$/
        };
        
        // 허용된 HTML 태그 (화이트리스트)
        this.allowedHtmlTags = ['b', 'i', 'u', 'strong', 'em', 'br', 'p'];
        
        // 데이터 타입별 제한
        this.limits = {
            string: { maxLength: 10000 },
            number: { min: -Number.MAX_SAFE_INTEGER, max: Number.MAX_SAFE_INTEGER },
            array: { maxItems: 1000 },
            object: { maxKeys: 100 }
        };
    }

    /**
     * 기본 검증 스키마 설정
     * @private
     */
    setupDefaultSchemas() {
        // 거래 데이터 스키마
        this.schemas.set('trade', {
            symbol: { type: 'string', required: true, pattern: /^[A-Z]{3,10}$/ },
            side: { type: 'string', required: true, enum: ['buy', 'sell'] },
            size: { type: 'number', required: true, min: 0 },
            price: { type: 'number', required: true, min: 0 },
            timestamp: { type: 'number', required: true }
        });

        // 포지션 데이터 스키마
        this.schemas.set('position', {
            symbol: { type: 'string', required: true, pattern: /^[A-Z]{3,10}$/ },
            side: { type: 'string', required: true, enum: ['long', 'short'] },
            size: { type: 'number', required: true },
            entryPrice: { type: 'number', required: true, min: 0 },
            markPrice: { type: 'number', required: true, min: 0 },
            pnl: { type: 'number', required: true },
            percentage: { type: 'number', required: true }
        });

        // 사용자 설정 스키마
        this.schemas.set('userSettings', {
            theme: { type: 'string', enum: ['light', 'dark'] },
            language: { type: 'string', pattern: /^[a-z]{2}$/ },
            notifications: { type: 'boolean' },
            riskLimit: { type: 'number', min: 0, max: 100 }
        });

        // 시장 데이터 스키마
        this.schemas.set('marketData', {
            symbol: { type: 'string', required: true, pattern: /^[A-Z]{3,10}$/ },
            price: { type: 'number', required: true, min: 0 },
            volume: { type: 'number', required: true, min: 0 },
            change: { type: 'number', required: true },
            timestamp: { type: 'number', required: true }
        });

        // WebSocket 메시지 스키마
        this.schemas.set('websocketMessage', {
            type: { type: 'string', required: true },
            data: { type: 'object', required: true },
            timestamp: { type: 'number', required: true },
            id: { type: 'string', pattern: /^[a-zA-Z0-9-_]+$/ }
        });
    }

    /**
     * 데이터 검증
     * @param {*} data - 검증할 데이터
     * @param {string|Object} schemaNameOrSchema - 스키마 이름 또는 스키마 객체
     * @returns {Object} 검증 결과
     */
    validate(data, schemaNameOrSchema) {
        const result = {
            valid: true,
            errors: [],
            warnings: [],
            sanitizedData: null
        };

        try {
            // 스키마 가져오기
            const schema = typeof schemaNameOrSchema === 'string' ? 
                this.schemas.get(schemaNameOrSchema) : schemaNameOrSchema;

            if (!schema) {
                result.valid = false;
                result.errors.push(`스키마를 찾을 수 없습니다: ${schemaNameOrSchema}`);
                return result;
            }

            // 데이터 sanitization
            result.sanitizedData = this.sanitize(data);

            // 스키마 검증
            this.validateAgainstSchema(result.sanitizedData, schema, result);

            // 보안 검증
            this.validateSecurity(result.sanitizedData, result);

        } catch (error) {
            result.valid = false;
            result.errors.push(`검증 중 오류 발생: ${error.message}`);
        }

        return result;
    }

    /**
     * 스키마 기반 검증
     * @param {*} data - 데이터
     * @param {Object} schema - 스키마
     * @param {Object} result - 검증 결과
     * @private
     */
    validateAgainstSchema(data, schema, result, path = '') {
        if (typeof data !== 'object' || data === null) {
            result.valid = false;
            result.errors.push(`${path} 객체가 아닙니다`);
            return;
        }

        // 필수 필드 확인
        for (const [key, rules] of Object.entries(schema)) {
            const currentPath = path ? `${path}.${key}` : key;
            const value = data[key];

            if (rules.required && (value === undefined || value === null)) {
                result.valid = false;
                result.errors.push(`${currentPath}는 필수 필드입니다`);
                continue;
            }

            if (value !== undefined && value !== null) {
                this.validateField(value, rules, currentPath, result);
            }
        }

        // 추가 필드 확인 (스키마에 없는 필드)
        for (const key of Object.keys(data)) {
            if (!schema[key]) {
                const currentPath = path ? `${path}.${key}` : key;
                result.warnings.push(`${currentPath}는 스키마에 정의되지 않은 필드입니다`);
            }
        }
    }

    /**
     * 개별 필드 검증
     * @param {*} value - 필드 값
     * @param {Object} rules - 검증 규칙
     * @param {string} path - 필드 경로
     * @param {Object} result - 검증 결과
     * @private
     */
    validateField(value, rules, path, result) {
        // 타입 검증
        if (rules.type && !this.validateType(value, rules.type)) {
            result.valid = false;
            result.errors.push(`${path}의 타입이 올바르지 않습니다. 예상: ${rules.type}, 실제: ${typeof value}`);
            return;
        }

        // 열거형 검증
        if (rules.enum && !rules.enum.includes(value)) {
            result.valid = false;
            result.errors.push(`${path}의 값이 허용된 값이 아닙니다. 허용값: [${rules.enum.join(', ')}]`);
        }

        // 패턴 검증
        if (rules.pattern && typeof value === 'string' && !rules.pattern.test(value)) {
            result.valid = false;
            result.errors.push(`${path}의 형식이 올바르지 않습니다`);
        }

        // 범위 검증
        if (typeof value === 'number') {
            if (rules.min !== undefined && value < rules.min) {
                result.valid = false;
                result.errors.push(`${path}의 값이 최솟값(${rules.min})보다 작습니다`);
            }
            if (rules.max !== undefined && value > rules.max) {
                result.valid = false;
                result.errors.push(`${path}의 값이 최댓값(${rules.max})보다 큽니다`);
            }
        }

        // 길이 검증
        if (typeof value === 'string') {
            if (rules.minLength && value.length < rules.minLength) {
                result.valid = false;
                result.errors.push(`${path}의 길이가 최소 길이(${rules.minLength})보다 짧습니다`);
            }
            if (rules.maxLength && value.length > rules.maxLength) {
                result.valid = false;
                result.errors.push(`${path}의 길이가 최대 길이(${rules.maxLength})를 초과합니다`);
            }
        }

        // 배열 검증
        if (Array.isArray(value)) {
            if (rules.minItems && value.length < rules.minItems) {
                result.valid = false;
                result.errors.push(`${path}의 항목 수가 최소 개수(${rules.minItems})보다 적습니다`);
            }
            if (rules.maxItems && value.length > rules.maxItems) {
                result.valid = false;
                result.errors.push(`${path}의 항목 수가 최대 개수(${rules.maxItems})를 초과합니다`);
            }

            // 배열 항목 검증
            if (rules.items) {
                value.forEach((item, index) => {
                    this.validateField(item, rules.items, `${path}[${index}]`, result);
                });
            }
        }

        // 객체 검증
        if (rules.properties && typeof value === 'object' && value !== null) {
            this.validateAgainstSchema(value, rules.properties, result, path);
        }
    }

    /**
     * 타입 검증
     * @param {*} value - 값
     * @param {string} expectedType - 예상 타입
     * @returns {boolean} 검증 결과
     * @private
     */
    validateType(value, expectedType) {
        switch (expectedType) {
            case 'string':
                return typeof value === 'string';
            case 'number':
                return typeof value === 'number' && !isNaN(value) && isFinite(value);
            case 'boolean':
                return typeof value === 'boolean';
            case 'array':
                return Array.isArray(value);
            case 'object':
                return typeof value === 'object' && value !== null && !Array.isArray(value);
            case 'null':
                return value === null;
            case 'undefined':
                return value === undefined;
            default:
                return true;
        }
    }

    /**
     * 보안 검증
     * @param {*} data - 데이터
     * @param {Object} result - 검증 결과
     * @private
     */
    validateSecurity(data, result) {
        this.checkForXSS(data, result);
        this.checkForSQLInjection(data, result);
        this.validateDataSize(data, result);
    }

    /**
     * XSS 공격 검사
     * @param {*} data - 데이터
     * @param {Object} result - 검증 결과
     * @private
     */
    checkForXSS(data, result) {
        const checkValue = (value, path = '') => {
            if (typeof value === 'string') {
                if (this.securityPatterns.xss.test(value)) {
                    result.valid = false;
                    result.errors.push(`${path} XSS 위험 요소가 감지되었습니다`);
                }
            } else if (Array.isArray(value)) {
                value.forEach((item, index) => checkValue(item, `${path}[${index}]`));
            } else if (typeof value === 'object' && value !== null) {
                Object.entries(value).forEach(([key, val]) => 
                    checkValue(val, path ? `${path}.${key}` : key)
                );
            }
        };

        checkValue(data);
    }

    /**
     * SQL Injection 검사
     * @param {*} data - 데이터
     * @param {Object} result - 검증 결과
     * @private
     */
    checkForSQLInjection(data, result) {
        const checkValue = (value, path = '') => {
            if (typeof value === 'string') {
                if (this.securityPatterns.sqlInjection.test(value)) {
                    result.warnings.push(`${path} SQL Injection 위험 패턴이 감지되었습니다`);
                }
            } else if (Array.isArray(value)) {
                value.forEach((item, index) => checkValue(item, `${path}[${index}]`));
            } else if (typeof value === 'object' && value !== null) {
                Object.entries(value).forEach(([key, val]) => 
                    checkValue(val, path ? `${path}.${key}` : key)
                );
            }
        };

        checkValue(data);
    }

    /**
     * 데이터 크기 검증
     * @param {*} data - 데이터
     * @param {Object} result - 검증 결과
     * @private
     */
    validateDataSize(data, result) {
        try {
            const jsonString = JSON.stringify(data);
            const sizeInBytes = new Blob([jsonString]).size;
            const maxSizeInMB = 10; // 10MB 제한
            const maxSizeInBytes = maxSizeInMB * 1024 * 1024;

            if (sizeInBytes > maxSizeInBytes) {
                result.valid = false;
                result.errors.push(`데이터 크기가 제한을 초과했습니다. 최대: ${maxSizeInMB}MB, 현재: ${(sizeInBytes / 1024 / 1024).toFixed(2)}MB`);
            }

            // 중첩 깊이 검사
            const maxDepth = 10;
            const depth = this.getObjectDepth(data);
            if (depth > maxDepth) {
                result.valid = false;
                result.errors.push(`객체 중첩 깊이가 제한을 초과했습니다. 최대: ${maxDepth}, 현재: ${depth}`);
            }

        } catch (error) {
            result.warnings.push('데이터 크기 검증 중 오류 발생');
        }
    }

    /**
     * 객체 중첩 깊이 계산
     * @param {*} obj - 객체
     * @param {number} depth - 현재 깊이
     * @returns {number} 최대 깊이
     * @private
     */
    getObjectDepth(obj, depth = 0) {
        if (typeof obj !== 'object' || obj === null) {
            return depth;
        }

        let maxDepth = depth;
        
        if (Array.isArray(obj)) {
            for (const item of obj) {
                maxDepth = Math.max(maxDepth, this.getObjectDepth(item, depth + 1));
            }
        } else {
            for (const value of Object.values(obj)) {
                maxDepth = Math.max(maxDepth, this.getObjectDepth(value, depth + 1));
            }
        }

        return maxDepth;
    }

    /**
     * 데이터 sanitization
     * @param {*} data - 데이터
     * @returns {*} 정화된 데이터
     */
    sanitize(data) {
        if (typeof data === 'string') {
            return this.sanitizeString(data);
        } else if (Array.isArray(data)) {
            return data.map(item => this.sanitize(item));
        } else if (typeof data === 'object' && data !== null) {
            const sanitized = {};
            for (const [key, value] of Object.entries(data)) {
                const sanitizedKey = this.sanitizeString(key);
                sanitized[sanitizedKey] = this.sanitize(value);
            }
            return sanitized;
        }
        
        return data;
    }

    /**
     * 문자열 sanitization
     * @param {string} str - 문자열
     * @returns {string} 정화된 문자열
     * @private
     */
    sanitizeString(str) {
        if (typeof str !== 'string') {
            return str;
        }

        // HTML 태그 제거 (허용된 태그 제외)
        let sanitized = str.replace(this.securityPatterns.htmlTags, (match) => {
            const tagName = match.match(/<\/?(\w+)/)?.[1]?.toLowerCase();
            return this.allowedHtmlTags.includes(tagName) ? match : '';
        });

        // 특수 문자 이스케이프
        sanitized = sanitized
            .replace(/</g, '&lt;')
            .replace(/>/g, '&gt;')
            .replace(/"/g, '&quot;')
            .replace(/'/g, '&#x27;')
            .replace(/&/g, '&amp;');

        // 길이 제한
        if (sanitized.length > this.limits.string.maxLength) {
            sanitized = sanitized.substring(0, this.limits.string.maxLength);
        }

        return sanitized.trim();
    }

    /**
     * 이메일 검증
     * @param {string} email - 이메일
     * @returns {boolean} 유효성
     */
    validateEmail(email) {
        return typeof email === 'string' && this.securityPatterns.email.test(email);
    }

    /**
     * URL 검증
     * @param {string} url - URL
     * @returns {boolean} 유효성
     */
    validateURL(url) {
        return typeof url === 'string' && this.securityPatterns.url.test(url);
    }

    /**
     * 숫자 범위 검증
     * @param {number} value - 값
     * @param {number} min - 최솟값
     * @param {number} max - 최댓값
     * @returns {boolean} 유효성
     */
    validateNumberRange(value, min = -Infinity, max = Infinity) {
        return typeof value === 'number' && 
               !isNaN(value) && 
               isFinite(value) && 
               value >= min && 
               value <= max;
    }

    /**
     * 거래 심볼 검증
     * @param {string} symbol - 심볼
     * @returns {boolean} 유효성
     */
    validateTradingSymbol(symbol) {
        return typeof symbol === 'string' && 
               /^[A-Z]{3,10}$/.test(symbol);
    }

    /**
     * 타임스탬프 검증
     * @param {number} timestamp - 타임스탬프
     * @param {number} maxAgeMs - 최대 나이 (밀리초)
     * @returns {boolean} 유효성
     */
    validateTimestamp(timestamp, maxAgeMs = 300000) { // 기본 5분
        if (!this.validateNumberRange(timestamp, 0)) {
            return false;
        }

        const now = Date.now();
        const age = now - timestamp;
        
        return age >= 0 && age <= maxAgeMs;
    }

    /**
     * 스키마 등록
     * @param {string} name - 스키마 이름
     * @param {Object} schema - 스키마
     */
    registerSchema(name, schema) {
        this.schemas.set(name, schema);
    }

    /**
     * 스키마 제거
     * @param {string} name - 스키마 이름
     */
    removeSchema(name) {
        this.schemas.delete(name);
    }

    /**
     * 검증 제한 설정
     * @param {Object} newLimits - 새로운 제한
     */
    setLimits(newLimits) {
        this.limits = { ...this.limits, ...newLimits };
    }

    /**
     * 허용된 HTML 태그 설정
     * @param {Array<string>} tags - 허용할 태그 목록
     */
    setAllowedHtmlTags(tags) {
        this.allowedHtmlTags = [...tags];
    }

    /**
     * 빠른 검증 (기본 타입만)
     * @param {*} value - 값
     * @param {string} type - 예상 타입
     * @returns {boolean} 유효성
     */
    quickValidate(value, type) {
        return this.validateType(value, type);
    }

    /**
     * 배치 검증
     * @param {Array} dataArray - 데이터 배열
     * @param {string|Object} schema - 스키마
     * @returns {Object} 배치 검증 결과
     */
    validateBatch(dataArray, schema) {
        if (!Array.isArray(dataArray)) {
            return {
                valid: false,
                error: '배치 데이터는 배열이어야 합니다',
                results: []
            };
        }

        const results = dataArray.map((data, index) => ({
            index,
            ...this.validate(data, schema)
        }));

        const allValid = results.every(result => result.valid);
        const totalErrors = results.reduce((sum, result) => sum + result.errors.length, 0);
        const totalWarnings = results.reduce((sum, result) => sum + result.warnings.length, 0);

        return {
            valid: allValid,
            totalItems: dataArray.length,
            validItems: results.filter(r => r.valid).length,
            totalErrors,
            totalWarnings,
            results
        };
    }

    /**
     * 검증 통계
     * @returns {Object} 통계 정보
     */
    getValidationStats() {
        return {
            totalSchemas: this.schemas.size,
            schemaNames: Array.from(this.schemas.keys()),
            limits: this.limits,
            allowedHtmlTags: this.allowedHtmlTags
        };
    }
}

// 전역 데이터 검증기 인스턴스
export const dataValidator = new DataValidator();

// 개발 모드에서 전역 접근 가능하게 설정
if (typeof window !== 'undefined' && process.env.NODE_ENV === 'development') {
    window.__DATA_VALIDATOR__ = dataValidator;
}
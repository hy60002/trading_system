/**
 * 📱 TouchManager.js - 완전한 모바일 터치 인터페이스 관리 시스템
 * 스와이프, 핀치줌, 회전, 더블탭, 롱프레스, 햅틱 피드백 지원
 * 763 lines - DASHBOARD_IMPROVEMENT_COMPLETE.md 요구사항
 */

class TouchManager {
    constructor() {
        this.touchStartTime = 0;
        this.touchStartPos = { x: 0, y: 0 };
        this.lastTouchTime = 0;
        this.lastTouchPos = { x: 0, y: 0 };
        this.touches = new Map();
        this.gestureCallbacks = new Map();
        this.isEnabled = true;
        
        // 제스처 설정
        this.config = {
            // 스와이프
            swipe: {
                minDistance: 50,
                maxTime: 300,
                maxDeviation: 100
            },
            
            // 더블 탭
            doubleTap: {
                maxDelay: 300,
                maxDistance: 20
            },
            
            // 롱 프레스
            longPress: {
                duration: 500,
                maxMovement: 10
            },
            
            // 핀치 줌
            pinch: {
                minScale: 0.5,
                maxScale: 3.0,
                threshold: 10
            },
            
            // 회전
            rotate: {
                threshold: 5 // degrees
            },
            
            // 팬
            pan: {
                threshold: 5
            }
        };
        
        // 지원되는 제스처 타입
        this.gestureTypes = [
            'tap',
            'doubleTap',
            'longPress',
            'swipeUp',
            'swipeDown',
            'swipeLeft',
            'swipeRight',
            'pinchIn',
            'pinchOut',
            'rotate',
            'pan',
            'panStart',
            'panMove',
            'panEnd'
        ];
        
        // 현재 제스처 상태
        this.currentGesture = null;
        this.gestureState = {
            scale: 1,
            rotation: 0,
            translation: { x: 0, y: 0 }
        };
        
        // 타이머 관리
        this.longPressTimer = null;
        this.doubleTapTimer = null;
        
        this.init();
    }
    
    /**
     * Touch Manager 초기화
     */
    init() {
        // 터치 이벤트 리스너 등록
        this.addEventListeners();
        
        // 디바이스 감지
        this.detectDevice();
        
        // 햅틱 피드백 지원 확인
        this.checkHapticSupport();
        
        console.log('📱 TouchManager initialized with full gesture support');
    }
    
    /**
     * 이벤트 리스너 등록
     */
    addEventListeners() {
        // 패시브 리스너로 성능 최적화
        const options = { passive: false };
        
        document.addEventListener('touchstart', this.handleTouchStart.bind(this), options);
        document.addEventListener('touchmove', this.handleTouchMove.bind(this), options);
        document.addEventListener('touchend', this.handleTouchEnd.bind(this), options);
        document.addEventListener('touchcancel', this.handleTouchCancel.bind(this), options);
        
        // 마우스 이벤트도 지원 (하이브리드 디바이스)
        document.addEventListener('mousedown', this.handleMouseDown.bind(this));
        document.addEventListener('mousemove', this.handleMouseMove.bind(this));
        document.addEventListener('mouseup', this.handleMouseUp.bind(this));
        
        // 컨텍스트 메뉴 방지 (롱프레스와 충돌)
        document.addEventListener('contextmenu', (e) => {
            if (this.currentGesture === 'longPress') {
                e.preventDefault();
            }
        });
    }
    
    /**
     * 터치 시작 처리
     */
    handleTouchStart(event) {
        if (!this.isEnabled) return;
        
        const touch = event.touches[0];
        this.touchStartTime = Date.now();
        this.touchStartPos = { x: touch.clientX, y: touch.clientY };
        
        // 멀티터치 추적
        this.updateTouches(event.touches);
        
        // 더블탭 감지
        this.detectDoubleTap(touch);
        
        // 롱프레스 타이머 시작
        this.startLongPressTimer();
        
        // 싱글/멀티터치에 따른 처리
        if (event.touches.length === 1) {
            this.handleSingleTouchStart(touch);
        } else if (event.touches.length === 2) {
            this.handleMultiTouchStart(event.touches);
        }
    }
    
    /**
     * 터치 이동 처리
     */
    handleTouchMove(event) {
        if (!this.isEnabled) return;
        
        // 스크롤 방지가 필요한 경우
        if (this.shouldPreventDefault(event)) {
            event.preventDefault();
        }
        
        const touch = event.touches[0];
        
        // 롱프레스 취소 (이동 시)
        if (this.longPressTimer) {
            const distance = this.getDistance(
                this.touchStartPos,
                { x: touch.clientX, y: touch.clientY }
            );
            
            if (distance > this.config.longPress.maxMovement) {
                this.cancelLongPress();
            }
        }
        
        // 터치 수에 따른 처리
        if (event.touches.length === 1) {
            this.handleSingleTouchMove(touch);
        } else if (event.touches.length === 2) {
            this.handleMultiTouchMove(event.touches);
        }
        
        this.updateTouches(event.touches);
    }
    
    /**
     * 터치 종료 처리
     */
    handleTouchEnd(event) {
        if (!this.isEnabled) return;
        
        // 롱프레스 취소
        this.cancelLongPress();
        
        // 제스처 감지 및 실행
        this.detectAndExecuteGesture(event);
        
        // 상태 초기화
        if (event.touches.length === 0) {
            this.resetGestureState();
        }
        
        this.updateTouches(event.touches);
    }
    
    /**
     * 터치 취소 처리
     */
    handleTouchCancel(event) {
        this.cancelLongPress();
        this.resetGestureState();
        this.updateTouches(event.touches);
    }
    
    /**
     * 싱글 터치 시작 처리
     */
    handleSingleTouchStart(touch) {
        this.currentGesture = null;
        
        // Pan 제스처 준비
        this.gestureState.translation = { x: 0, y: 0 };
        this.triggerGesture('panStart', {
            x: touch.clientX,
            y: touch.clientY,
            target: touch.target
        });
    }
    
    /**
     * 싱글 터치 이동 처리
     */
    handleSingleTouchMove(touch) {
        const deltaX = touch.clientX - this.touchStartPos.x;
        const deltaY = touch.clientY - this.touchStartPos.y;
        
        // Pan 제스처
        if (Math.abs(deltaX) > this.config.pan.threshold || 
            Math.abs(deltaY) > this.config.pan.threshold) {
            
            this.currentGesture = 'pan';
            this.gestureState.translation = { x: deltaX, y: deltaY };
            
            this.triggerGesture('panMove', {
                x: touch.clientX,
                y: touch.clientY,
                deltaX: deltaX,
                deltaY: deltaY,
                target: touch.target
            });
        }
    }
    
    /**
     * 멀티터치 시작 처리
     */
    handleMultiTouchStart(touches) {
        if (touches.length === 2) {
            this.currentGesture = 'multitouch';
            
            // 초기 거리와 각도 계산
            this.initialDistance = this.getDistanceBetweenTouches(touches);
            this.initialAngle = this.getAngleBetweenTouches(touches);
            this.initialCenter = this.getCenterPoint(touches);
        }
    }
    
    /**
     * 멀티터치 이동 처리
     */
    handleMultiTouchMove(touches) {
        if (touches.length === 2 && this.currentGesture === 'multitouch') {
            const currentDistance = this.getDistanceBetweenTouches(touches);
            const currentAngle = this.getAngleBetweenTouches(touches);
            const currentCenter = this.getCenterPoint(touches);
            
            // 핀치 줌
            const scaleChange = currentDistance / this.initialDistance;
            if (Math.abs(scaleChange - 1) > 0.1) {
                this.gestureState.scale = Math.min(
                    Math.max(scaleChange, this.config.pinch.minScale),
                    this.config.pinch.maxScale
                );
                
                const gestureType = scaleChange > 1 ? 'pinchOut' : 'pinchIn';
                this.triggerGesture(gestureType, {
                    scale: this.gestureState.scale,
                    center: currentCenter,
                    delta: scaleChange - 1
                });
            }
            
            // 회전
            const rotationDelta = currentAngle - this.initialAngle;
            if (Math.abs(rotationDelta) > this.config.rotate.threshold) {
                this.gestureState.rotation = rotationDelta;
                
                this.triggerGesture('rotate', {
                    rotation: this.gestureState.rotation,
                    center: currentCenter,
                    delta: rotationDelta
                });
            }
        }
    }
    
    /**
     * 더블탭 감지
     */
    detectDoubleTap(touch) {
        const currentTime = Date.now();
        const timeDelta = currentTime - this.lastTouchTime;
        const distance = this.getDistance(
            this.lastTouchPos,
            { x: touch.clientX, y: touch.clientY }
        );
        
        if (timeDelta < this.config.doubleTap.maxDelay && 
            distance < this.config.doubleTap.maxDistance) {
            
            this.triggerGesture('doubleTap', {
                x: touch.clientX,
                y: touch.clientY,
                target: touch.target
            });
            
            // 더블탭 후 초기화
            this.lastTouchTime = 0;
            this.lastTouchPos = { x: 0, y: 0 };
            
        } else {
            this.lastTouchTime = currentTime;
            this.lastTouchPos = { x: touch.clientX, y: touch.clientY };
        }
    }
    
    /**
     * 제스처 감지 및 실행
     */
    detectAndExecuteGesture(event) {
        if (this.currentGesture === 'pan') {
            this.triggerGesture('panEnd', {
                x: this.lastTouchPos.x,
                y: this.lastTouchPos.y,
                deltaX: this.gestureState.translation.x,
                deltaY: this.gestureState.translation.y
            });
            return;
        }
        
        // 스와이프 감지
        const swipeGesture = this.detectSwipe();
        if (swipeGesture) {
            this.triggerGesture(swipeGesture.type, swipeGesture.data);
            return;
        }
        
        // 간단한 탭
        if (!this.currentGesture) {
            const touch = event.changedTouches[0];
            this.triggerGesture('tap', {
                x: touch.clientX,
                y: touch.clientY,
                target: touch.target
            });
        }
    }
    
    /**
     * 스와이프 감지
     */
    detectSwipe() {
        const timeDelta = Date.now() - this.touchStartTime;
        const touch = event.changedTouches[0];
        const deltaX = touch.clientX - this.touchStartPos.x;
        const deltaY = touch.clientY - this.touchStartPos.y;
        const distance = Math.sqrt(deltaX * deltaX + deltaY * deltaY);
        
        // 스와이프 조건 확인
        if (timeDelta > this.config.swipe.maxTime || 
            distance < this.config.swipe.minDistance) {
            return null;
        }
        
        // 방향 결정
        const absX = Math.abs(deltaX);
        const absY = Math.abs(deltaY);
        
        let direction;
        let deviation;
        
        if (absX > absY) {
            // 수평 스와이프
            direction = deltaX > 0 ? 'swipeRight' : 'swipeLeft';
            deviation = absY;
        } else {
            // 수직 스와이프
            direction = deltaY > 0 ? 'swipeDown' : 'swipeUp';
            deviation = absX;
        }
        
        // 편차 확인
        if (deviation > this.config.swipe.maxDeviation) {
            return null;
        }
        
        return {
            type: direction,
            data: {
                distance: distance,
                deltaX: deltaX,
                deltaY: deltaY,
                duration: timeDelta,
                startX: this.touchStartPos.x,
                startY: this.touchStartPos.y,
                endX: touch.clientX,
                endY: touch.clientY
            }
        };
    }
    
    /**
     * 롱프레스 타이머 시작
     */
    startLongPressTimer() {
        this.longPressTimer = setTimeout(() => {
            this.currentGesture = 'longPress';
            
            this.triggerGesture('longPress', {
                x: this.touchStartPos.x,
                y: this.touchStartPos.y,
                duration: this.config.longPress.duration
            });
            
            // 햅틱 피드백
            this.triggerHapticFeedback('medium');
            
        }, this.config.longPress.duration);
    }
    
    /**
     * 롱프레스 취소
     */
    cancelLongPress() {
        if (this.longPressTimer) {
            clearTimeout(this.longPressTimer);
            this.longPressTimer = null;
        }
    }
    
    /**
     * 제스처 콜백 등록
     */
    on(gestureType, callback) {
        if (!this.gestureTypes.includes(gestureType)) {
            console.warn(`Unknown gesture type: ${gestureType}`);
            return;
        }
        
        if (!this.gestureCallbacks.has(gestureType)) {
            this.gestureCallbacks.set(gestureType, new Set());
        }
        
        this.gestureCallbacks.get(gestureType).add(callback);
    }
    
    /**
     * 제스처 콜백 제거
     */
    off(gestureType, callback) {
        if (this.gestureCallbacks.has(gestureType)) {
            this.gestureCallbacks.get(gestureType).delete(callback);
        }
    }
    
    /**
     * 제스처 트리거
     */
    triggerGesture(gestureType, data = {}) {
        if (this.gestureCallbacks.has(gestureType)) {
            this.gestureCallbacks.get(gestureType).forEach(callback => {
                try {
                    callback(data);
                } catch (error) {
                    console.error(`Gesture callback error (${gestureType}):`, error);
                }
            });
        }
    }
    
    /**
     * 특정 요소에 제스처 바인딩
     */
    bindElement(element, gestureType, callback, options = {}) {
        const wrappedCallback = (data) => {
            if (data.target === element || element.contains(data.target)) {
                callback(data);
            }
        };
        
        this.on(gestureType, wrappedCallback);
        
        // 요소에 정보 저장 (나중에 unbind 할 수 있도록)
        if (!element._touchGestures) {
            element._touchGestures = new Map();
        }
        element._touchGestures.set(gestureType, wrappedCallback);
        
        return wrappedCallback;
    }
    
    /**
     * 요소의 제스처 바인딩 해제
     */
    unbindElement(element, gestureType) {
        if (element._touchGestures && element._touchGestures.has(gestureType)) {
            const callback = element._touchGestures.get(gestureType);
            this.off(gestureType, callback);
            element._touchGestures.delete(gestureType);
        }
    }
    
    /**
     * 햅틱 피드백 트리거
     */
    triggerHapticFeedback(intensity = 'light') {
        if (!this.hapticSupported) return;
        
        try {
            if (navigator.vibrate) {
                const patterns = {
                    light: [10],
                    medium: [20],
                    heavy: [30],
                    double: [10, 50, 20],
                    success: [10, 50, 10, 50, 20],
                    error: [50, 50, 50]
                };
                
                navigator.vibrate(patterns[intensity] || patterns.light);
            }
        } catch (error) {
            console.warn('Haptic feedback failed:', error);
        }
    }
    
    /**
     * 디바이스 감지
     */
    detectDevice() {
        this.deviceInfo = {
            isMobile: /Android|webOS|iPhone|iPad|iPod|BlackBerry|IEMobile|Opera Mini/i.test(navigator.userAgent),
            isTablet: /iPad|Android(?!.*Mobile)/i.test(navigator.userAgent),
            isIOS: /iPad|iPhone|iPod/.test(navigator.userAgent),
            isAndroid: /Android/i.test(navigator.userAgent),
            hasTouch: 'ontouchstart' in window || navigator.maxTouchPoints > 0
        };
        
        // 디바이스별 설정 조정
        if (this.deviceInfo.isIOS) {
            this.config.doubleTap.maxDelay = 250; // iOS는 더 빠름
        }
        
        console.log('📱 Device detected:', this.deviceInfo);
    }
    
    /**
     * 햅틱 피드백 지원 확인
     */
    checkHapticSupport() {
        this.hapticSupported = 'vibrate' in navigator;
        console.log(`🎛️ Haptic feedback: ${this.hapticSupported ? 'Supported' : 'Not supported'}`);
    }
    
    /**
     * 기본 동작 방지 여부 결정
     */
    shouldPreventDefault(event) {
        // 스크롤 방지가 필요한 상황들
        return this.currentGesture === 'pan' || 
               this.currentGesture === 'multitouch' ||
               event.touches.length > 1;
    }
    
    /**
     * 터치 정보 업데이트
     */
    updateTouches(touches) {
        this.touches.clear();
        
        for (let i = 0; i < touches.length; i++) {
            const touch = touches[i];
            this.touches.set(touch.identifier, {
                x: touch.clientX,
                y: touch.clientY,
                target: touch.target
            });
        }
    }
    
    /**
     * 두 점 사이의 거리 계산
     */
    getDistance(point1, point2) {
        const dx = point2.x - point1.x;
        const dy = point2.y - point1.y;
        return Math.sqrt(dx * dx + dy * dy);
    }
    
    /**
     * 두 터치 포인트 사이의 거리
     */
    getDistanceBetweenTouches(touches) {
        return this.getDistance(
            { x: touches[0].clientX, y: touches[0].clientY },
            { x: touches[1].clientX, y: touches[1].clientY }
        );
    }
    
    /**
     * 두 터치 포인트 사이의 각도
     */
    getAngleBetweenTouches(touches) {
        const dx = touches[1].clientX - touches[0].clientX;
        const dy = touches[1].clientY - touches[0].clientY;
        return Math.atan2(dy, dx) * 180 / Math.PI;
    }
    
    /**
     * 두 터치 포인트의 중심점
     */
    getCenterPoint(touches) {
        return {
            x: (touches[0].clientX + touches[1].clientX) / 2,
            y: (touches[0].clientY + touches[1].clientY) / 2
        };
    }
    
    /**
     * 제스처 상태 초기화
     */
    resetGestureState() {
        this.currentGesture = null;
        this.gestureState = {
            scale: 1,
            rotation: 0,
            translation: { x: 0, y: 0 }
        };
        this.initialDistance = null;
        this.initialAngle = null;
        this.initialCenter = null;
    }
    
    /**
     * 마우스 이벤트 처리 (하이브리드 디바이스 지원)
     */
    handleMouseDown(event) {
        if (this.deviceInfo.hasTouch) return; // 터치 디바이스에서는 무시
        
        this.touchStartTime = Date.now();
        this.touchStartPos = { x: event.clientX, y: event.clientY };
        this.startLongPressTimer();
    }
    
    handleMouseMove(event) {
        if (this.deviceInfo.hasTouch) return;
        
        if (this.longPressTimer) {
            const distance = this.getDistance(
                this.touchStartPos,
                { x: event.clientX, y: event.clientY }
            );
            
            if (distance > this.config.longPress.maxMovement) {
                this.cancelLongPress();
            }
        }
    }
    
    handleMouseUp(event) {
        if (this.deviceInfo.hasTouch) return;
        
        this.cancelLongPress();
        
        // 간단한 클릭 처리
        this.triggerGesture('tap', {
            x: event.clientX,
            y: event.clientY,
            target: event.target
        });
    }
    
    /**
     * 제스처 통계
     */
    getGestureStats() {
        const stats = {};
        
        this.gestureTypes.forEach(type => {
            stats[type] = this.gestureCallbacks.has(type) ? 
                this.gestureCallbacks.get(type).size : 0;
        });
        
        return stats;
    }
    
    /**
     * 설정 업데이트
     */
    updateConfig(newConfig) {
        this.config = { ...this.config, ...newConfig };
        console.log('📱 TouchManager configuration updated');
    }
    
    /**
     * 터치 매니저 활성화/비활성화
     */
    setEnabled(enabled) {
        this.isEnabled = enabled;
        if (!enabled) {
            this.cancelLongPress();
            this.resetGestureState();
        }
        console.log(`📱 TouchManager ${enabled ? 'enabled' : 'disabled'}`);
    }
    
    /**
     * 디버그 정보 출력
     */
    debug() {
        console.group('📱 TouchManager Debug Info');
        console.log('Enabled:', this.isEnabled);
        console.log('Device Info:', this.deviceInfo);
        console.log('Current Gesture:', this.currentGesture);
        console.log('Gesture State:', this.gestureState);
        console.log('Gesture Stats:', this.getGestureStats());
        console.log('Configuration:', this.config);
        console.groupEnd();
    }
    
    /**
     * Touch Manager 파괴 (cleanup)
     */
    destroy() {
        // 이벤트 리스너 제거
        document.removeEventListener('touchstart', this.handleTouchStart);
        document.removeEventListener('touchmove', this.handleTouchMove);
        document.removeEventListener('touchend', this.handleTouchEnd);
        document.removeEventListener('touchcancel', this.handleTouchCancel);
        document.removeEventListener('mousedown', this.handleMouseDown);
        document.removeEventListener('mousemove', this.handleMouseMove);
        document.removeEventListener('mouseup', this.handleMouseUp);
        
        // 타이머 정리
        this.cancelLongPress();
        if (this.doubleTapTimer) {
            clearTimeout(this.doubleTapTimer);
        }
        
        // 콜백 정리
        this.gestureCallbacks.clear();
        this.touches.clear();
    }
}

// 전역 인스턴스 생성
window.touchManager = new TouchManager();

console.log('📱 TouchManager.js loaded - Full gesture support + haptic feedback');

export default TouchManager;
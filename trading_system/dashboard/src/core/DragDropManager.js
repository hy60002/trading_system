/**
 * @fileoverview 드래그 앤 드롭 매니저
 * @description HTML5 Drag & Drop API를 활용한 고급 드래그 앤 드롭 시스템
 */

/**
 * 드래그 앤 드롭 매니저
 * @class DragDropManager
 */
export class DragDropManager {
    constructor() {
        this.dragElements = new Map();
        this.dropZones = new Map();
        this.currentDragData = null;
        this.dragPreview = null;
        this.dropIndicator = null;
        this.isTouch = 'ontouchstart' in window;
        
        // 설정
        this.config = {
            dragDelay: this.isTouch ? 150 : 0,
            scrollSpeed: 5,
            scrollThreshold: 50,
            animationDuration: 300,
            enableAccessibility: true,
            enableVirtualization: false
        };
        
        // 상태 추적
        this.state = {
            isDragging: false,
            dragStarted: false,
            dragElement: null,
            ghostElement: null,
            insertPosition: null,
            scrollInterval: null,
            touchStartTime: 0
        };
        
        // 드래그 타입별 핸들러
        this.dragTypes = new Map();
        
        // 접근성
        this.announcer = null;
        this.keyboardMode = false;
        
        // 성능 메트릭
        this.metrics = {
            totalDrags: 0,
            successfulDrops: 0,
            canceledDrags: 0,
            averageDragDuration: 0
        };
        
        this.initialize();
    }

    /**
     * 초기화
     * @private
     */
    initialize() {
        this.createDropIndicator();
        this.createDragPreview();
        this.setupGlobalEventListeners();
        
        if (this.config.enableAccessibility) {
            this.setupAccessibility();
        }
        
        // 기본 드래그 타입 등록
        this.registerDragType('position-card', {
            canDrag: this.canDragPositionCard.bind(this),
            onDragStart: this.onPositionCardDragStart.bind(this),
            onDrag: this.onPositionCardDrag.bind(this),
            onDrop: this.onPositionCardDrop.bind(this)
        });
    }

    /**
     * 드롭 인디케이터 생성
     * @private
     */
    createDropIndicator() {
        this.dropIndicator = document.createElement('div');
        this.dropIndicator.className = 'drag-drop-indicator';
        this.dropIndicator.innerHTML = `
            <div class="indicator-line"></div>
            <div class="indicator-ghost"></div>
        `;
        this.dropIndicator.style.cssText = `
            position: absolute;
            pointer-events: none;
            z-index: 10000;
            opacity: 0;
            transition: opacity 0.2s ease;
        `;
        document.body.appendChild(this.dropIndicator);
    }

    /**
     * 드래그 프리뷰 생성
     * @private
     */
    createDragPreview() {
        this.dragPreview = document.createElement('div');
        this.dragPreview.className = 'drag-preview';
        this.dragPreview.style.cssText = `
            position: fixed;
            pointer-events: none;
            z-index: 10001;
            opacity: 0;
            transform: scale(0.95);
            transition: opacity 0.2s ease, transform 0.2s ease;
            border-radius: 8px;
            box-shadow: 0 10px 25px rgba(0, 0, 0, 0.3);
        `;
        document.body.appendChild(this.dragPreview);
    }

    /**
     * 전역 이벤트 리스너 설정
     * @private
     */
    setupGlobalEventListeners() {
        // 마우스 이벤트
        document.addEventListener('dragover', this.handleGlobalDragOver.bind(this));
        document.addEventListener('drop', this.handleGlobalDrop.bind(this));
        document.addEventListener('dragend', this.handleGlobalDragEnd.bind(this));
        
        // 터치 이벤트 (모바일 지원)
        if (this.isTouch) {
            document.addEventListener('touchmove', this.handleTouchMove.bind(this), { passive: false });
            document.addEventListener('touchend', this.handleTouchEnd.bind(this));
        }
        
        // 키보드 이벤트 (접근성)
        document.addEventListener('keydown', this.handleKeyDown.bind(this));
        document.addEventListener('keyup', this.handleKeyUp.bind(this));
        
        // 윈도우 이벤트
        window.addEventListener('resize', this.handleWindowResize.bind(this));
        window.addEventListener('scroll', this.handleWindowScroll.bind(this), { passive: true });
    }

    /**
     * 접근성 설정
     * @private
     */
    setupAccessibility() {
        // 스크린 리더 공지용 요소 생성
        this.announcer = document.createElement('div');
        this.announcer.className = 'drag-drop-announcer';
        this.announcer.setAttribute('aria-live', 'polite');
        this.announcer.setAttribute('aria-atomic', 'true');
        this.announcer.style.cssText = `
            position: absolute;
            left: -10000px;
            width: 1px;
            height: 1px;
            overflow: hidden;
        `;
        document.body.appendChild(this.announcer);
    }

    /**
     * 드래그 가능한 요소 등록
     * @param {HTMLElement} element - 드래그 요소
     * @param {Object} options - 드래그 옵션
     */
    registerDragElement(element, options = {}) {
        const dragData = {
            element,
            type: options.type || 'default',
            data: options.data || {},
            handle: options.handle || element,
            ghost: options.ghost || null,
            disabled: options.disabled || false,
            constraints: options.constraints || {},
            onDragStart: options.onDragStart,
            onDrag: options.onDrag,
            onDragEnd: options.onDragEnd,
            accessibleName: options.accessibleName || element.textContent || 'Draggable item'
        };

        this.dragElements.set(element, dragData);
        
        // 드래그 속성 설정
        element.draggable = true;
        element.setAttribute('role', 'button');
        element.setAttribute('aria-grabbed', 'false');
        element.setAttribute('aria-label', `${dragData.accessibleName} - 드래그하여 이동 가능`);
        element.setAttribute('tabindex', '0');
        
        // 이벤트 리스너 추가
        this.attachDragListeners(element);
    }

    /**
     * 드롭 존 등록
     * @param {HTMLElement} element - 드롭 존 요소
     * @param {Object} options - 드롭 옵션
     */
    registerDropZone(element, options = {}) {
        const dropData = {
            element,
            accepts: options.accepts || ['*'],
            onDragEnter: options.onDragEnter,
            onDragOver: options.onDragOver,
            onDragLeave: options.onDragLeave,
            onDrop: options.onDrop,
            disabled: options.disabled || false,
            sortable: options.sortable || false,
            insertionMode: options.insertionMode || 'append' // 'append', 'prepend', 'before', 'after'
        };

        this.dropZones.set(element, dropData);
        
        // 드롭존 속성 설정
        element.setAttribute('role', 'region');
        element.setAttribute('aria-label', '드롭 가능 영역');
        
        // 이벤트 리스너 추가
        this.attachDropListeners(element);
    }

    /**
     * 드래그 타입 등록
     * @param {string} type - 드래그 타입
     * @param {Object} handlers - 핸들러 객체
     */
    registerDragType(type, handlers) {
        this.dragTypes.set(type, handlers);
    }

    /**
     * 드래그 리스너 연결
     * @param {HTMLElement} element - 요소
     * @private
     */
    attachDragListeners(element) {
        element.addEventListener('dragstart', this.handleDragStart.bind(this));
        element.addEventListener('drag', this.handleDrag.bind(this));
        element.addEventListener('dragend', this.handleDragEnd.bind(this));
        
        // 터치 이벤트
        if (this.isTouch) {
            element.addEventListener('touchstart', this.handleTouchStart.bind(this), { passive: false });
        }
        
        // 키보드 이벤트
        element.addEventListener('keydown', this.handleElementKeyDown.bind(this));
        element.addEventListener('focus', this.handleElementFocus.bind(this));
        element.addEventListener('blur', this.handleElementBlur.bind(this));
    }

    /**
     * 드롭 리스너 연결
     * @param {HTMLElement} element - 요소
     * @private
     */
    attachDropListeners(element) {
        element.addEventListener('dragenter', this.handleDragEnter.bind(this));
        element.addEventListener('dragover', this.handleDragOver.bind(this));
        element.addEventListener('dragleave', this.handleDragLeave.bind(this));
        element.addEventListener('drop', this.handleDrop.bind(this));
    }

    /**
     * 드래그 시작 처리
     * @param {DragEvent} event - 드래그 이벤트
     * @private
     */
    handleDragStart(event) {
        const element = event.currentTarget;
        const dragData = this.dragElements.get(element);
        
        if (!dragData || dragData.disabled) {
            event.preventDefault();
            return;
        }

        this.state.isDragging = true;
        this.state.dragElement = element;
        this.state.dragStarted = performance.now();
        
        // 드래그 데이터 설정
        this.currentDragData = {
            ...dragData,
            startX: event.clientX,
            startY: event.clientY,
            originalIndex: this.getElementIndex(element)
        };

        // DataTransfer 설정
        event.dataTransfer.effectAllowed = 'move';
        event.dataTransfer.setData('text/plain', ''); // Firefox 호환성
        
        // 커스텀 드래그 이미지
        if (dragData.ghost) {
            event.dataTransfer.setDragImage(dragData.ghost, 0, 0);
        } else {
            this.createCustomDragImage(element, event);
        }

        // 접근성 업데이트
        element.setAttribute('aria-grabbed', 'true');
        
        // 시각적 피드백
        element.classList.add('dragging');
        document.body.classList.add('drag-active');
        
        // 드래그 타입별 처리
        const typeHandler = this.dragTypes.get(dragData.type);
        if (typeHandler && typeHandler.onDragStart) {
            typeHandler.onDragStart(element, dragData.data, event);
        }

        // 커스텀 핸들러 실행
        if (dragData.onDragStart) {
            dragData.onDragStart(element, event);
        }

        // 메트릭 업데이트
        this.metrics.totalDrags++;
        
        // 접근성 공지
        this.announce(`${dragData.accessibleName} 드래그 시작됨`);
    }

    /**
     * 드래그 중 처리
     * @param {DragEvent} event - 드래그 이벤트
     * @private
     */
    handleDrag(event) {
        if (!this.state.isDragging) return;
        
        const dragData = this.currentDragData;
        if (!dragData) return;

        // 드래그 타입별 처리
        const typeHandler = this.dragTypes.get(dragData.type);
        if (typeHandler && typeHandler.onDrag) {
            typeHandler.onDrag(dragData.element, dragData.data, event);
        }

        // 커스텀 핸들러 실행
        if (dragData.onDrag) {
            dragData.onDrag(dragData.element, event);
        }

        // 자동 스크롤
        this.handleAutoScroll(event);
    }

    /**
     * 전역 드래그 오버 처리
     * @param {DragEvent} event - 드래그 이벤트
     * @private
     */
    handleGlobalDragOver(event) {
        if (!this.state.isDragging) return;
        
        event.preventDefault();
        
        const dropZone = this.findDropZone(event.target);
        if (dropZone) {
            const dropData = this.dropZones.get(dropZone);
            
            if (this.canAcceptDrop(dropData, this.currentDragData)) {
                event.dataTransfer.dropEffect = 'move';
                
                if (dropData.sortable) {
                    this.updateDropIndicator(event, dropZone);
                }
            } else {
                event.dataTransfer.dropEffect = 'none';
            }
        }
    }

    /**
     * 드래그 엔터 처리
     * @param {DragEvent} event - 드래그 이벤트
     * @private
     */
    handleDragEnter(event) {
        if (!this.state.isDragging) return;
        
        const dropZone = event.currentTarget;
        const dropData = this.dropZones.get(dropZone);
        
        if (!dropData || dropData.disabled) return;
        
        if (this.canAcceptDrop(dropData, this.currentDragData)) {
            dropZone.classList.add('drag-over');
            
            if (dropData.onDragEnter) {
                dropData.onDragEnter(event, this.currentDragData);
            }
        }
    }

    /**
     * 드래그 오버 처리
     * @param {DragEvent} event - 드래그 이벤트
     * @private
     */
    handleDragOver(event) {
        if (!this.state.isDragging) return;
        
        event.preventDefault();
        
        const dropZone = event.currentTarget;
        const dropData = this.dropZones.get(dropZone);
        
        if (!dropData || dropData.disabled) return;
        
        if (this.canAcceptDrop(dropData, this.currentDragData)) {
            event.dataTransfer.dropEffect = 'move';
            
            if (dropData.onDragOver) {
                dropData.onDragOver(event, this.currentDragData);
            }
            
            if (dropData.sortable) {
                this.updateSortableIndicator(event, dropZone);
            }
        }
    }

    /**
     * 드래그 리브 처리
     * @param {DragEvent} event - 드래그 이벤트
     * @private
     */
    handleDragLeave(event) {
        if (!this.state.isDragging) return;
        
        const dropZone = event.currentTarget;
        const dropData = this.dropZones.get(dropZone);
        
        // 실제로 드롭존을 벗어났는지 확인
        if (!dropZone.contains(event.relatedTarget)) {
            dropZone.classList.remove('drag-over');
            
            if (dropData && dropData.onDragLeave) {
                dropData.onDragLeave(event, this.currentDragData);
            }
        }
    }

    /**
     * 드롭 처리
     * @param {DragEvent} event - 드롭 이벤트
     * @private
     */
    handleDrop(event) {
        if (!this.state.isDragging) return;
        
        event.preventDefault();
        
        const dropZone = event.currentTarget;
        const dropData = this.dropZones.get(dropZone);
        
        if (!dropData || dropData.disabled) return;
        
        if (this.canAcceptDrop(dropData, this.currentDragData)) {
            const dropResult = this.performDrop(dropZone, dropData, event);
            
            if (dropResult) {
                this.metrics.successfulDrops++;
                this.announce(`${this.currentDragData.accessibleName} 성공적으로 이동됨`);
            }
        }
        
        this.endDrag();
    }

    /**
     * 전역 드롭 처리
     * @param {DragEvent} event - 드롭 이벤트
     * @private
     */
    handleGlobalDrop(event) {
        if (!this.state.isDragging) return;
        
        // 유효한 드롭존이 아닌 곳에 드롭된 경우
        event.preventDefault();
        this.endDrag();
    }

    /**
     * 드래그 종료 처리
     * @param {DragEvent} event - 드래그 이벤트
     * @private
     */
    handleDragEnd(event) {
        this.endDrag();
    }

    /**
     * 전역 드래그 종료 처리
     * @param {DragEvent} event - 드래그 이벤트
     * @private
     */
    handleGlobalDragEnd(event) {
        this.endDrag();
    }

    /**
     * 드래그 종료
     * @private
     */
    endDrag() {
        if (!this.state.isDragging) return;
        
        const dragElement = this.state.dragElement;
        const dragData = this.currentDragData;
        
        // 상태 초기화
        this.state.isDragging = false;
        this.state.dragElement = null;
        this.currentDragData = null;
        
        // 시각적 피드백 제거
        if (dragElement) {
            dragElement.classList.remove('dragging');
            dragElement.setAttribute('aria-grabbed', 'false');
        }
        
        document.body.classList.remove('drag-active');
        
        // 모든 드롭존에서 클래스 제거
        this.dropZones.forEach((_, dropZone) => {
            dropZone.classList.remove('drag-over');
        });
        
        // 인디케이터 숨기기
        this.hideDropIndicator();
        
        // 자동 스크롤 중지
        if (this.state.scrollInterval) {
            clearInterval(this.state.scrollInterval);
            this.state.scrollInterval = null;
        }
        
        // 드래그 타입별 처리
        if (dragData) {
            const typeHandler = this.dragTypes.get(dragData.type);
            if (typeHandler && typeHandler.onDragEnd) {
                typeHandler.onDragEnd(dragElement, dragData.data);
            }
            
            if (dragData.onDragEnd) {
                dragData.onDragEnd(dragElement);
            }
        }
        
        // 메트릭 업데이트
        if (this.state.dragStarted) {
            const duration = performance.now() - this.state.dragStarted;
            this.updateDragDurationMetric(duration);
        }
    }

    // 포지션 카드 전용 핸들러들

    /**
     * 포지션 카드 드래그 가능 여부 확인
     * @param {HTMLElement} element - 요소
     * @returns {boolean} 드래그 가능 여부
     * @private
     */
    canDragPositionCard(element) {
        return element.classList.contains('position-card') && !element.classList.contains('disabled');
    }

    /**
     * 포지션 카드 드래그 시작 처리
     * @param {HTMLElement} element - 요소
     * @param {Object} data - 데이터
     * @param {DragEvent} event - 이벤트
     * @private
     */
    onPositionCardDragStart(element, data, event) {
        const container = element.closest('.positions-grid');
        if (container) {
            container.classList.add('dragging-active');
        }
        
        // 포지션 데이터 추출
        const positionData = this.extractPositionData(element);
        this.currentDragData.positionData = positionData;
    }

    /**
     * 포지션 카드 드래그 중 처리
     * @param {HTMLElement} element - 요소
     * @param {Object} data - 데이터
     * @param {DragEvent} event - 이벤트
     * @private
     */
    onPositionCardDrag(element, data, event) {
        // 실시간 정렬 미리보기는 여기서 처리 가능
    }

    /**
     * 포지션 카드 드롭 처리
     * @param {HTMLElement} element - 요소
     * @param {Object} data - 데이터
     * @param {DragEvent} event - 이벤트
     * @private
     */
    onPositionCardDrop(element, data, event) {
        const container = element.closest('.positions-grid');
        if (container) {
            container.classList.remove('dragging-active');
        }
    }

    // 유틸리티 메서드들

    /**
     * 드롭 가능 여부 확인
     * @param {Object} dropData - 드롭존 데이터
     * @param {Object} dragData - 드래그 데이터
     * @returns {boolean} 드롭 가능 여부
     * @private
     */
    canAcceptDrop(dropData, dragData) {
        if (!dropData || !dragData) return false;
        
        const accepts = dropData.accepts;
        const dragType = dragData.type;
        
        return accepts.includes('*') || accepts.includes(dragType);
    }

    /**
     * 실제 드롭 수행
     * @param {HTMLElement} dropZone - 드롭존
     * @param {Object} dropData - 드롭 데이터
     * @param {DragEvent} event - 이벤트
     * @returns {boolean} 성공 여부
     * @private
     */
    performDrop(dropZone, dropData, event) {
        try {
            if (dropData.sortable) {
                this.performSortableDrop(dropZone, dropData, event);
            }
            
            // 드래그 타입별 드롭 처리
            const typeHandler = this.dragTypes.get(this.currentDragData.type);
            if (typeHandler && typeHandler.onDrop) {
                typeHandler.onDrop(this.currentDragData.element, this.currentDragData.data, dropZone);
            }
            
            // 커스텀 드롭 핸들러
            if (dropData.onDrop) {
                dropData.onDrop(event, this.currentDragData, dropZone);
            }
            
            return true;
        } catch (error) {
            console.error('Drop operation failed:', error);
            return false;
        }
    }

    /**
     * 정렬 가능한 드롭 수행
     * @param {HTMLElement} dropZone - 드롭존
     * @param {Object} dropData - 드롭 데이터
     * @param {DragEvent} event - 이벤트
     * @private
     */
    performSortableDrop(dropZone, dropData, event) {
        const dragElement = this.currentDragData.element;
        const insertPosition = this.state.insertPosition;
        
        if (!insertPosition) return;
        
        // 애니메이션과 함께 요소 이동
        this.animateElementMove(dragElement, insertPosition, () => {
            // 실제 DOM 조작
            if (insertPosition.before) {
                insertPosition.before.parentNode.insertBefore(dragElement, insertPosition.before);
            } else {
                dropZone.appendChild(dragElement);
            }
            
            // 레이아웃 업데이트
            this.updateLayout(dropZone);
        });
    }

    /**
     * 요소 이동 애니메이션
     * @param {HTMLElement} element - 요소
     * @param {Object} position - 위치
     * @param {Function} callback - 콜백
     * @private
     */
    animateElementMove(element, position, callback) {
        const rect = element.getBoundingClientRect();
        const targetRect = position.before ? 
            position.before.getBoundingClientRect() : 
            position.parent.getBoundingClientRect();
        
        // FLIP 애니메이션 기법 사용
        const deltaX = targetRect.left - rect.left;
        const deltaY = targetRect.top - rect.top;
        
        element.style.transform = `translate(${deltaX}px, ${deltaY}px)`;
        element.style.transition = 'none';
        
        requestAnimationFrame(() => {
            callback();
            
            requestAnimationFrame(() => {
                element.style.transform = '';
                element.style.transition = `transform ${this.config.animationDuration}ms ease`;
                
                setTimeout(() => {
                    element.style.transition = '';
                }, this.config.animationDuration);
            });
        });
    }

    /**
     * 커스텀 드래그 이미지 생성
     * @param {HTMLElement} element - 요소
     * @param {DragEvent} event - 이벤트
     * @private
     */
    createCustomDragImage(element, event) {
        const clone = element.cloneNode(true);
        clone.style.cssText = `
            position: absolute;
            top: -9999px;
            left: -9999px;
            opacity: 0.8;
            transform: scale(0.95);
            pointer-events: none;
            z-index: -1;
        `;
        
        document.body.appendChild(clone);
        event.dataTransfer.setDragImage(clone, event.offsetX, event.offsetY);
        
        setTimeout(() => {
            document.body.removeChild(clone);
        }, 0);
    }

    /**
     * 드롭 인디케이터 업데이트
     * @param {DragEvent} event - 이벤트
     * @param {HTMLElement} dropZone - 드롭존
     * @private
     */
    updateDropIndicator(event, dropZone) {
        const position = this.calculateInsertPosition(event, dropZone);
        
        if (position) {
            this.state.insertPosition = position;
            this.showDropIndicator(position);
        } else {
            this.hideDropIndicator();
        }
    }

    /**
     * 정렬 가능한 인디케이터 업데이트
     * @param {DragEvent} event - 이벤트
     * @param {HTMLElement} dropZone - 드롭존
     * @private
     */
    updateSortableIndicator(event, dropZone) {
        this.updateDropIndicator(event, dropZone);
    }

    /**
     * 삽입 위치 계산
     * @param {DragEvent} event - 이벤트
     * @param {HTMLElement} container - 컨테이너
     * @returns {Object|null} 삽입 위치
     * @private
     */
    calculateInsertPosition(event, container) {
        const children = Array.from(container.children).filter(child => 
            child !== this.currentDragData.element && 
            !child.classList.contains('drag-drop-indicator')
        );
        
        const mouseX = event.clientX;
        const mouseY = event.clientY;
        
        let closestChild = null;
        let closestDistance = Infinity;
        let insertBefore = null;
        
        for (const child of children) {
            const rect = child.getBoundingClientRect();
            const childCenterX = rect.left + rect.width / 2;
            const childCenterY = rect.top + rect.height / 2;
            
            const distance = Math.sqrt(
                Math.pow(mouseX - childCenterX, 2) + 
                Math.pow(mouseY - childCenterY, 2)
            );
            
            if (distance < closestDistance) {
                closestDistance = distance;
                closestChild = child;
                
                // 마우스가 요소의 왼쪽/위쪽에 있으면 앞에 삽입
                if (mouseX < childCenterX || mouseY < childCenterY) {
                    insertBefore = child;
                } else {
                    insertBefore = child.nextElementSibling;
                }
            }
        }
        
        return {
            parent: container,
            before: insertBefore,
            reference: closestChild
        };
    }

    /**
     * 드롭 인디케이터 표시
     * @param {Object} position - 위치
     * @private
     */
    showDropIndicator(position) {
        if (!position) return;
        
        let rect;
        if (position.before) {
            rect = position.before.getBoundingClientRect();
        } else {
            rect = position.parent.getBoundingClientRect();
            rect = {
                ...rect,
                top: rect.bottom - 4,
                height: 4
            };
        }
        
        this.dropIndicator.style.left = rect.left + 'px';
        this.dropIndicator.style.top = rect.top + 'px';
        this.dropIndicator.style.width = rect.width + 'px';
        this.dropIndicator.style.height = '4px';
        this.dropIndicator.style.opacity = '1';
    }

    /**
     * 드롭 인디케이터 숨기기
     * @private
     */
    hideDropIndicator() {
        this.dropIndicator.style.opacity = '0';
        this.state.insertPosition = null;
    }

    /**
     * 자동 스크롤 처리
     * @param {DragEvent} event - 이벤트
     * @private
     */
    handleAutoScroll(event) {
        const scrollContainer = this.findScrollContainer(event.target);
        if (!scrollContainer) return;
        
        const rect = scrollContainer.getBoundingClientRect();
        const threshold = this.config.scrollThreshold;
        const speed = this.config.scrollSpeed;
        
        let scrollX = 0;
        let scrollY = 0;
        
        if (event.clientY < rect.top + threshold) {
            scrollY = -speed;
        } else if (event.clientY > rect.bottom - threshold) {
            scrollY = speed;
        }
        
        if (event.clientX < rect.left + threshold) {
            scrollX = -speed;
        } else if (event.clientX > rect.right - threshold) {
            scrollX = speed;
        }
        
        if (scrollX !== 0 || scrollY !== 0) {
            if (!this.state.scrollInterval) {
                this.state.scrollInterval = setInterval(() => {
                    scrollContainer.scrollBy(scrollX, scrollY);
                }, 16);
            }
        } else if (this.state.scrollInterval) {
            clearInterval(this.state.scrollInterval);
            this.state.scrollInterval = null;
        }
    }

    // 터치 이벤트 핸들러들 (모바일 지원)

    /**
     * 터치 시작 처리
     * @param {TouchEvent} event - 터치 이벤트
     * @private
     */
    handleTouchStart(event) {
        this.state.touchStartTime = performance.now();
        
        if (this.config.dragDelay > 0) {
            setTimeout(() => {
                if (performance.now() - this.state.touchStartTime >= this.config.dragDelay) {
                    this.startTouchDrag(event);
                }
            }, this.config.dragDelay);
        }
    }

    /**
     * 터치 드래그 시작
     * @param {TouchEvent} event - 터치 이벤트
     * @private
     */
    startTouchDrag(event) {
        // 터치를 드래그로 변환하는 로직
        event.preventDefault();
        
        const touch = event.touches[0];
        const element = event.currentTarget;
        
        // 가상의 드래그 이벤트 생성
        const dragEvent = new DragEvent('dragstart', {
            clientX: touch.clientX,
            clientY: touch.clientY,
            dataTransfer: new DataTransfer()
        });
        
        this.handleDragStart.call(element, dragEvent);
    }

    // 키보드 접근성 핸들러들

    /**
     * 키보드 다운 처리
     * @param {KeyboardEvent} event - 키보드 이벤트
     * @private
     */
    handleKeyDown(event) {
        if (!this.keyboardMode) return;
        
        switch (event.code) {
            case 'Escape':
                this.cancelKeyboardDrag();
                break;
            case 'Enter':
            case 'Space':
                this.confirmKeyboardDrag();
                break;
            case 'ArrowUp':
            case 'ArrowDown':
            case 'ArrowLeft':
            case 'ArrowRight':
                this.moveKeyboardSelection(event.code);
                event.preventDefault();
                break;
        }
    }

    // 유틸리티 메서드들

    /**
     * 드롭존 찾기
     * @param {HTMLElement} element - 요소
     * @returns {HTMLElement|null} 드롭존
     * @private
     */
    findDropZone(element) {
        let current = element;
        while (current && current !== document.body) {
            if (this.dropZones.has(current)) {
                return current;
            }
            current = current.parentElement;
        }
        return null;
    }

    /**
     * 스크롤 컨테이너 찾기
     * @param {HTMLElement} element - 요소
     * @returns {HTMLElement|null} 스크롤 컨테이너
     * @private
     */
    findScrollContainer(element) {
        let current = element;
        while (current && current !== document.body) {
            const overflow = getComputedStyle(current).overflow;
            if (overflow === 'auto' || overflow === 'scroll') {
                return current;
            }
            current = current.parentElement;
        }
        return window;
    }

    /**
     * 요소 인덱스 가져오기
     * @param {HTMLElement} element - 요소
     * @returns {number} 인덱스
     * @private
     */
    getElementIndex(element) {
        return Array.from(element.parentElement.children).indexOf(element);
    }

    /**
     * 포지션 데이터 추출
     * @param {HTMLElement} element - 포지션 카드 요소
     * @returns {Object} 포지션 데이터
     * @private
     */
    extractPositionData(element) {
        return {
            symbol: element.dataset.symbol,
            side: element.dataset.side,
            size: element.dataset.size,
            pnl: element.dataset.pnl
        };
    }

    /**
     * 레이아웃 업데이트
     * @param {HTMLElement} container - 컨테이너
     * @private
     */
    updateLayout(container) {
        // CSS Grid나 Flexbox 레이아웃 재계산 트리거
        container.style.display = 'none';
        container.offsetHeight; // 리플로우 강제
        container.style.display = '';
    }

    /**
     * 접근성 공지
     * @param {string} message - 메시지
     * @private
     */
    announce(message) {
        if (this.announcer) {
            this.announcer.textContent = message;
        }
    }

    /**
     * 드래그 지속 시간 메트릭 업데이트
     * @param {number} duration - 지속 시간
     * @private
     */
    updateDragDurationMetric(duration) {
        const count = this.metrics.totalDrags;
        this.metrics.averageDragDuration = 
            (this.metrics.averageDragDuration * (count - 1) + duration) / count;
    }

    /**
     * 요소 등록 해제
     * @param {HTMLElement} element - 요소
     */
    unregisterElement(element) {
        this.dragElements.delete(element);
        this.dropZones.delete(element);
        
        element.draggable = false;
        element.removeAttribute('role');
        element.removeAttribute('aria-grabbed');
        element.removeAttribute('aria-label');
        element.removeAttribute('tabindex');
    }

    /**
     * 메트릭 가져오기
     * @returns {Object} 메트릭
     */
    getMetrics() {
        return {
            ...this.metrics,
            successRate: this.metrics.totalDrags > 0 ? 
                (this.metrics.successfulDrops / this.metrics.totalDrags) * 100 : 0
        };
    }

    /**
     * 정리
     */
    destroy() {
        // 모든 이벤트 리스너 제거
        this.dragElements.clear();
        this.dropZones.clear();
        this.dragTypes.clear();
        
        // DOM 요소 제거
        if (this.dropIndicator) {
            document.body.removeChild(this.dropIndicator);
        }
        if (this.dragPreview) {
            document.body.removeChild(this.dragPreview);
        }
        if (this.announcer) {
            document.body.removeChild(this.announcer);
        }
        
        // 인터벌 정리
        if (this.state.scrollInterval) {
            clearInterval(this.state.scrollInterval);
        }
    }

    // 빈 핸들러들 (서브클래스에서 구현)
    handleTouchMove(event) {}
    handleTouchEnd(event) {}
    handleElementKeyDown(event) {}
    handleElementFocus(event) {}
    handleElementBlur(event) {}
    handleKeyUp(event) {}
    handleWindowResize(event) {}
    handleWindowScroll(event) {}
    cancelKeyboardDrag() {}
    confirmKeyboardDrag() {}
    moveKeyboardSelection(direction) {}
}

// 전역 드래그 앤 드롭 매니저 인스턴스
export const dragDropManager = new DragDropManager();

// 편의 함수들
export const registerDragElement = (element, options) => 
    dragDropManager.registerDragElement(element, options);

export const registerDropZone = (element, options) => 
    dragDropManager.registerDropZone(element, options);

export const registerDragType = (type, handlers) => 
    dragDropManager.registerDragType(type, handlers);

// 개발 모드에서 전역 접근 가능
if (typeof window !== 'undefined' && process.env.NODE_ENV === 'development') {
    window.__TRADING_DASHBOARD_DRAG_DROP__ = dragDropManager;
}
// 🔌 WebSocket Manager for Real-time Updates

class WebSocketManager {
    constructor() {
        this.ws = null;
        this.reconnectAttempts = 0;
        this.maxReconnectAttempts = 5;
        this.reconnectDelay = 1000;
        this.heartbeatInterval = null;
        this.isConnected = false;
        this.messageQueue = [];
        this.listeners = new Map();
        
        this.initializeWebSocket();
    }

    initializeWebSocket() {
        try {
            // WebSocket URL 구성 (현재 호스트 기반)
            const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
            const wsUrl = `${protocol}//${window.location.host}/ws/dashboard`;
            
            this.ws = new WebSocket(wsUrl);
            this.setupEventHandlers();
            
        } catch (error) {
            console.error('WebSocket 초기화 실패:', error);
            this.scheduleReconnect();
        }
    }

    setupEventHandlers() {
        this.ws.onopen = () => {
            console.log('WebSocket 연결됨');
            this.isConnected = true;
            this.reconnectAttempts = 0;
            this.updateConnectionStatus('connected');
            this.startHeartbeat();
            this.processPendingMessages();
        };

        this.ws.onmessage = (event) => {
            try {
                const data = JSON.parse(event.data);
                this.handleMessage(data);
            } catch (error) {
                console.error('WebSocket 메시지 파싱 실패:', error);
            }
        };

        this.ws.onclose = (event) => {
            console.log('WebSocket 연결 종료:', event.code, event.reason);
            this.isConnected = false;
            this.updateConnectionStatus('disconnected');
            this.stopHeartbeat();
            
            if (event.code !== 1000) { // 정상 종료가 아닌 경우
                this.scheduleReconnect();
            }
        };

        this.ws.onerror = (error) => {
            console.error('WebSocket 오류:', error);
            this.updateConnectionStatus('error');
        };
    }

    handleMessage(data) {
        // 메시지 타입별 처리
        switch (data.type) {
            case 'price_update':
                this.handlePriceUpdate(data.payload);
                break;
            case 'position_update':
                this.handlePositionUpdate(data.payload);
                break;
            case 'trade_executed':
                this.handleTradeExecuted(data.payload);
                break;
            case 'balance_update':
                this.handleBalanceUpdate(data.payload);
                break;
            case 'system_status':
                this.handleSystemStatus(data.payload);
                break;
            case 'notification':
                this.handleNotification(data.payload);
                break;
            case 'heartbeat':
                this.handleHeartbeat(data.payload);
                break;
            default:
                console.log('알 수 없는 메시지 타입:', data.type);
        }

        // 등록된 리스너들에게 메시지 전달
        if (this.listeners.has(data.type)) {
            this.listeners.get(data.type).forEach(callback => callback(data.payload));
        }
    }

    handlePriceUpdate(data) {
        // 실시간 가격 업데이트
        if (window.dashboard) {
            const positions = dashboard.data.positions || [];
            let hasChanges = false;

            positions.forEach(position => {
                if (data[position.symbol]) {
                    const newPrice = data[position.symbol];
                    const oldPrice = position.current_price;
                    
                    position.current_price = newPrice;
                    position.pnl = (newPrice - position.entry_price) * position.size;
                    
                    // 가격 변화 플래시 효과
                    if (newPrice !== oldPrice) {
                        this.flashPriceChange(position.symbol, newPrice > oldPrice);
                        hasChanges = true;
                    }
                }
            });

            if (hasChanges) {
                dashboard.updatePositionsTable();
                dashboard.updateSummaryCards();
            }
        }
    }

    handlePositionUpdate(data) {
        // 포지션 업데이트 (새 포지션, 종료된 포지션 등)
        if (window.dashboard) {
            dashboard.data.positions = data.positions;
            dashboard.updatePositionsTable();
            dashboard.updateSummaryCards();
            
            // 새 포지션 알림
            if (data.action === 'opened') {
                dashboard.showNotification(
                    `새 포지션 진입: ${data.symbol} ${data.side} ${data.size}`,
                    'info'
                );
                this.playSound('position_open');
            } else if (data.action === 'closed') {
                const pnlClass = data.pnl >= 0 ? 'success' : 'warning';
                dashboard.showNotification(
                    `포지션 종료: ${data.symbol} 손익 ${data.pnl >= 0 ? '+' : ''}${data.pnl.toFixed(2)}$`,
                    pnlClass
                );
                this.playSound('position_close');
            }
        }
    }

    handleTradeExecuted(data) {
        // 거래 실행 알림
        if (window.dashboard) {
            dashboard.showNotification(
                `거래 실행: ${data.symbol} ${data.side} ${data.size}@${data.price}`,
                'info'
            );
            
            // 최근 거래 목록 업데이트
            if (!dashboard.data.recent_trades) {
                dashboard.data.recent_trades = [];
            }
            dashboard.data.recent_trades.unshift(data);
            dashboard.updateTradesTable();
        }
    }

    handleBalanceUpdate(data) {
        // 잔액 업데이트
        if (window.dashboard) {
            dashboard.data.balance = data;
            dashboard.updateSummaryCards();
        }
    }

    handleSystemStatus(data) {
        // 시스템 상태 업데이트
        if (window.dashboard) {
            dashboard.data.system_status = data;
            dashboard.updateSystemStatus();
        }
    }

    handleNotification(data) {
        // 서버에서 보낸 알림
        if (window.dashboard) {
            dashboard.showNotification(data.message, data.type || 'info');
            
            if (data.sound) {
                this.playSound(data.sound);
            }
        }
    }

    handleHeartbeat(data) {
        // 하트비트 응답
        console.log('Heartbeat received:', data.timestamp);
    }

    flashPriceChange(symbol, isUp) {
        // 가격 변화 시 플래시 효과
        const row = document.querySelector(`tr[data-symbol="${symbol}"]`);
        if (row) {
            const flashClass = isUp ? 'flash-profit' : 'flash-loss';
            row.classList.add(flashClass);
            setTimeout(() => row.classList.remove(flashClass), 800);
        }
    }

    playSound(soundType) {
        // 사운드 재생 (사용자 설정에 따라)
        if (!this.getSoundSetting()) return;

        const soundMap = {
            'position_open': '/sounds/position_open.mp3',
            'position_close': '/sounds/position_close.mp3',
            'profit_alert': '/sounds/profit_alert.mp3',
            'loss_alert': '/sounds/loss_alert.mp3',
            'notification': '/sounds/notification.mp3'
        };

        const soundUrl = soundMap[soundType];
        if (soundUrl) {
            const audio = new Audio(soundUrl);
            audio.volume = 0.3; // 볼륨 조절
            audio.play().catch(console.error);
        }
    }

    getSoundSetting() {
        // 로컬 스토리지에서 사운드 설정 가져오기
        return localStorage.getItem('dashboard-sound') !== 'false';
    }

    updateConnectionStatus(status) {
        const statusElement = document.getElementById('websocket-status');
        const statusMap = {
            'connected': { text: '연결됨', class: 'positive' },
            'disconnected': { text: '끊김', class: 'negative' },
            'connecting': { text: '연결중', class: 'neutral' },
            'error': { text: '오류', class: 'negative' }
        };

        if (statusElement && statusMap[status]) {
            statusElement.textContent = statusMap[status].text;
            statusElement.className = statusMap[status].class;
        }
    }

    startHeartbeat() {
        this.heartbeatInterval = setInterval(() => {
            if (this.isConnected) {
                this.send({
                    type: 'heartbeat',
                    timestamp: Date.now()
                });
            }
        }, 30000); // 30초마다 하트비트
    }

    stopHeartbeat() {
        if (this.heartbeatInterval) {
            clearInterval(this.heartbeatInterval);
            this.heartbeatInterval = null;
        }
    }

    send(data) {
        if (this.isConnected && this.ws.readyState === WebSocket.OPEN) {
            this.ws.send(JSON.stringify(data));
        } else {
            // 연결되지 않은 경우 메시지 큐에 저장
            this.messageQueue.push(data);
        }
    }

    processPendingMessages() {
        // 대기 중인 메시지들 전송
        while (this.messageQueue.length > 0) {
            const message = this.messageQueue.shift();
            this.send(message);
        }
    }

    scheduleReconnect() {
        if (this.reconnectAttempts < this.maxReconnectAttempts) {
            this.reconnectAttempts++;
            const delay = this.reconnectDelay * Math.pow(2, this.reconnectAttempts - 1);
            
            console.log(`WebSocket 재연결 시도 ${this.reconnectAttempts}/${this.maxReconnectAttempts} (${delay}ms 후)`);
            this.updateConnectionStatus('connecting');
            
            setTimeout(() => {
                this.initializeWebSocket();
            }, delay);
        } else {
            console.error('WebSocket 재연결 시도 횟수 초과');
            this.updateConnectionStatus('error');
        }
    }

    addEventListener(type, callback) {
        // 메시지 타입별 리스너 등록
        if (!this.listeners.has(type)) {
            this.listeners.set(type, []);
        }
        this.listeners.get(type).push(callback);
    }

    removeEventListener(type, callback) {
        // 리스너 제거
        if (this.listeners.has(type)) {
            const listeners = this.listeners.get(type);
            const index = listeners.indexOf(callback);
            if (index > -1) {
                listeners.splice(index, 1);
            }
        }
    }

    disconnect() {
        // 수동 연결 해제
        if (this.ws) {
            this.ws.close(1000, 'Manual disconnect');
        }
        this.stopHeartbeat();
    }

    // 백그라운드 탭에서의 성능 최적화
    handleVisibilityChange() {
        if (document.hidden) {
            // 백그라운드일 때 업데이트 빈도 감소
            this.stopHeartbeat();
        } else {
            // 포그라운드로 돌아왔을 때 재개
            if (this.isConnected) {
                this.startHeartbeat();
                // 즉시 데이터 동기화
                this.send({ type: 'sync_request' });
            }
        }
    }
}

// 전역 WebSocket 매니저 인스턴스
let wsManager;

function initializeWebSocket() {
    wsManager = new WebSocketManager();
    
    // 페이지 가시성 변화 감지
    document.addEventListener('visibilitychange', () => {
        wsManager.handleVisibilityChange();
    });
    
    // 페이지 언로드 시 연결 해제
    window.addEventListener('beforeunload', () => {
        wsManager.disconnect();
    });
}

// 메시지 배치 처리를 위한 큐 시스템
class MessageBatcher {
    constructor(batchSize = 10, batchDelay = 100) {
        this.batchSize = batchSize;
        this.batchDelay = batchDelay;
        this.messageQueue = [];
        this.batchTimeout = null;
    }

    addMessage(message) {
        this.messageQueue.push(message);
        
        if (this.messageQueue.length >= this.batchSize) {
            this.processBatch();
        } else if (!this.batchTimeout) {
            this.batchTimeout = setTimeout(() => {
                this.processBatch();
            }, this.batchDelay);
        }
    }

    processBatch() {
        if (this.messageQueue.length === 0) return;
        
        const batch = [...this.messageQueue];
        this.messageQueue = [];
        
        if (this.batchTimeout) {
            clearTimeout(this.batchTimeout);
            this.batchTimeout = null;
        }
        
        // 배치 처리 로직
        this.handleBatch(batch);
    }

    handleBatch(messages) {
        // 메시지 타입별로 그룹화하여 효율적 처리
        const groupedMessages = messages.reduce((groups, message) => {
            const type = message.type;
            if (!groups[type]) groups[type] = [];
            groups[type].push(message);
            return groups;
        }, {});

        // 타입별 배치 처리
        Object.entries(groupedMessages).forEach(([type, typeMessages]) => {
            this.processByType(type, typeMessages);
        });
    }

    processByType(type, messages) {
        switch (type) {
            case 'price_update':
                // 가격 업데이트는 최신 것만 처리
                const latestPrices = messages[messages.length - 1];
                wsManager.handlePriceUpdate(latestPrices.payload);
                break;
            case 'position_update':
                // 포지션 업데이트는 모두 처리
                messages.forEach(msg => wsManager.handlePositionUpdate(msg.payload));
                break;
            default:
                // 기타 메시지는 순차 처리
                messages.forEach(msg => wsManager.handleMessage(msg));
        }
    }
}
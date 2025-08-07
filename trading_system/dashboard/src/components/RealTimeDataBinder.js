import { BaseComponent } from '../core/BaseComponent.js';

/**
 * 실시간 데이터 바인딩 시스템
 * - WebSocket 기반 실시간 데이터 스트리밍
 * - 차트별 데이터 구독/해제
 * - 데이터 변환 및 캐싱
 * - 자동 재연결 및 에러 핸들링
 */
export class RealTimeDataBinder extends BaseComponent {
    constructor(options = {}) {
        super(null, options);
        
        // WebSocket 설정
        this.wsUrl = options.wsUrl || 'wss://stream.bitget.com/mix/v1/stream';
        this.ws = null;
        this.isConnected = false;
        this.reconnectAttempts = 0;
        this.maxReconnectAttempts = options.maxReconnectAttempts || 10;
        this.reconnectDelay = options.reconnectDelay || 1000;
        
        // 구독 관리
        this.subscriptions = new Map(); // 구독 정보
        this.chartBindings = new Map();  // 차트별 바인딩
        this.dataStreams = new Map();    // 데이터 스트림
        
        // 데이터 캐시 및 처리
        this.dataCache = new Map();
        this.cacheTimeout = options.cacheTimeout || 5000;
        this.batchSize = options.batchSize || 10;
        this.batchDelay = options.batchDelay || 100;
        this.pendingUpdates = new Map();
        
        // 성능 최적화
        this.updateThrottle = options.updateThrottle || 16; // ~60fps
        this.maxDataPoints = options.maxDataPoints || 1000;
        this.compressionRatio = options.compressionRatio || 0.1;
        
        // 데이터 변환기
        this.dataTransformers = new Map();
        this.setupDefaultTransformers();
        
        // 통계 및 모니터링
        this.stats = {
            messagesReceived: 0,
            messagesProcessed: 0,
            dataUpdates: 0,
            errors: 0,
            reconnections: 0,
            averageLatency: 0
        };
        
        this.init();
    }

    /**
     * 초기화
     */
    init() {
        this.connect();
        this.setupBatchProcessor();
        this.setupPerformanceMonitoring();
        this.emit('dataBinderInitialized');
    }

    /**
     * WebSocket 연결
     */
    connect() {
        try {
            this.ws = new WebSocket(this.wsUrl);
            this.setupWebSocketEventListeners();
            this.emit('connecting');
        } catch (error) {
            this.handleConnectionError(error);
        }
    }

    /**
     * WebSocket 이벤트 리스너 설정
     */
    setupWebSocketEventListeners() {
        this.ws.onopen = (event) => {
            this.isConnected = true;
            this.reconnectAttempts = 0;
            this.resubscribeAll();
            this.emit('connected', event);
        };

        this.ws.onmessage = (event) => {
            this.handleMessage(event);
        };

        this.ws.onclose = (event) => {
            this.isConnected = false;
            this.handleDisconnection(event);
        };

        this.ws.onerror = (event) => {
            this.handleConnectionError(event);
        };
    }

    /**
     * 메시지 처리
     */
    handleMessage(event) {
        try {
            const startTime = performance.now();
            const data = JSON.parse(event.data);
            
            this.stats.messagesReceived++;
            
            // 핑/퐁 메시지 처리
            if (data.event === 'pong' || data.ping) {
                this.handlePingPong(data);
                return;
            }
            
            // 구독 확인 메시지
            if (data.event === 'subscribe') {
                this.handleSubscriptionConfirm(data);
                return;
            }
            
            // 데이터 메시지 처리
            if (data.data) {
                this.processDataMessage(data);
            }
            
            // 지연시간 계산
            const latency = performance.now() - startTime;
            this.updateLatencyStats(latency);
            
            this.stats.messagesProcessed++;
        } catch (error) {
            this.stats.errors++;
            this.emit('messageError', error);
        }
    }

    /**
     * 데이터 메시지 처리
     */
    processDataMessage(message) {
        const { action, arg, data } = message;
        
        if (!arg || !data) return;
        
        const streamKey = this.getStreamKey(arg);
        const subscription = this.subscriptions.get(streamKey);
        
        if (!subscription) return;
        
        // 데이터 변환
        const transformedData = this.transformData(data, subscription.type);
        
        // 캐시 업데이트
        this.updateCache(streamKey, transformedData);
        
        // 배치 업데이트에 추가
        this.addToBatch(streamKey, transformedData);
        
        this.emit('dataReceived', {
            stream: streamKey,
            data: transformedData,
            subscription
        });
    }

    /**
     * 차트 바인딩
     */
    bindChart(chartId, chart, dataTypes) {
        const binding = {
            chartId,
            chart,
            dataTypes: Array.isArray(dataTypes) ? dataTypes : [dataTypes],
            lastUpdate: null,
            updateCount: 0
        };
        
        this.chartBindings.set(chartId, binding);
        
        // 필요한 데이터 스트림 구독
        binding.dataTypes.forEach(dataType => {
            this.subscribeToDataType(dataType, chartId);
        });
        
        this.emit('chartBound', { chartId, dataTypes });
        return binding;
    }

    /**
     * 차트 바인딩 해제
     */
    unbindChart(chartId) {
        const binding = this.chartBindings.get(chartId);
        if (!binding) return;
        
        // 구독 해제
        binding.dataTypes.forEach(dataType => {
            this.unsubscribeFromDataType(dataType, chartId);
        });
        
        this.chartBindings.delete(chartId);
        this.emit('chartUnbound', chartId);
    }

    /**
     * 데이터 타입 구독
     */
    subscribeToDataType(dataType, chartId) {
        const streamKey = this.getStreamKeyForDataType(dataType);
        let subscription = this.subscriptions.get(streamKey);
        
        if (!subscription) {
            subscription = {
                streamKey,
                type: dataType,
                subscribers: new Set(),
                lastData: null,
                updateFrequency: this.getUpdateFrequency(dataType)
            };
            this.subscriptions.set(streamKey, subscription);
        }
        
        subscription.subscribers.add(chartId);
        
        // WebSocket 구독 메시지 전송
        if (this.isConnected) {
            this.sendSubscriptionMessage(streamKey, dataType);
        }
        
        this.emit('subscribed', { streamKey, dataType, chartId });
    }

    /**
     * 데이터 타입 구독 해제
     */
    unsubscribeFromDataType(dataType, chartId) {
        const streamKey = this.getStreamKeyForDataType(dataType);
        const subscription = this.subscriptions.get(streamKey);
        
        if (!subscription) return;
        
        subscription.subscribers.delete(chartId);
        
        // 더 이상 구독자가 없으면 구독 해제
        if (subscription.subscribers.size === 0) {
            this.sendUnsubscriptionMessage(streamKey, dataType);
            this.subscriptions.delete(streamKey);
            this.dataCache.delete(streamKey);
        }
        
        this.emit('unsubscribed', { streamKey, dataType, chartId });
    }

    /**
     * 구독 메시지 전송
     */
    sendSubscriptionMessage(streamKey, dataType) {
        const message = this.createSubscriptionMessage(streamKey, dataType);
        this.sendMessage(message);
    }

    /**
     * 구독 해제 메시지 전송
     */
    sendUnsubscriptionMessage(streamKey, dataType) {
        const message = this.createUnsubscriptionMessage(streamKey, dataType);
        this.sendMessage(message);
    }

    /**
     * 구독 메시지 생성
     */
    createSubscriptionMessage(streamKey, dataType) {
        // Bitget WebSocket API 형식에 맞춰 구현
        const [symbol, channel] = streamKey.split(':');
        
        return {
            op: 'subscribe',
            args: [{
                instType: 'UMCBL',
                channel,
                instId: symbol
            }]
        };
    }

    /**
     * 구독 해제 메시지 생성
     */
    createUnsubscriptionMessage(streamKey, dataType) {
        const [symbol, channel] = streamKey.split(':');
        
        return {
            op: 'unsubscribe',
            args: [{
                instType: 'UMCBL',
                channel,
                instId: symbol
            }]
        };
    }

    /**
     * 메시지 전송
     */
    sendMessage(message) {
        if (this.isConnected && this.ws.readyState === WebSocket.OPEN) {
            this.ws.send(JSON.stringify(message));
        } else {
            this.emit('sendError', { message, reason: 'Not connected' });
        }
    }

    /**
     * 스트림 키 생성
     */
    getStreamKey(arg) {
        if (arg.instId && arg.channel) {
            return `${arg.instId}:${arg.channel}`;
        }
        return null;
    }

    /**
     * 데이터 타입에서 스트림 키 생성
     */
    getStreamKeyForDataType(dataType) {
        // 데이터 타입 매핑
        const typeMapping = {
            'ticker': 'BTCUSDT:ticker',
            'depth': 'BTCUSDT:books',
            'trades': 'BTCUSDT:trade',
            'kline_1m': 'BTCUSDT:candle1m',
            'kline_5m': 'BTCUSDT:candle5m',
            'kline_1h': 'BTCUSDT:candle1H',
            'kline_1d': 'BTCUSDT:candle1D'
        };
        
        return typeMapping[dataType] || dataType;
    }

    /**
     * 업데이트 빈도 가져오기
     */
    getUpdateFrequency(dataType) {
        const frequencies = {
            'ticker': 1000,      // 1초
            'depth': 500,        // 0.5초
            'trades': 100,       // 0.1초
            'kline_1m': 1000,    // 1초
            'kline_5m': 5000,    // 5초
            'kline_1h': 60000,   // 1분
            'kline_1d': 300000   // 5분
        };
        
        return frequencies[dataType] || 1000;
    }

    /**
     * 기본 데이터 변환기 설정
     */
    setupDefaultTransformers() {
        // 티커 데이터 변환기
        this.dataTransformers.set('ticker', (data) => {
            return {
                symbol: data.instId,
                price: parseFloat(data.last),
                change: parseFloat(data.change),
                changePercent: parseFloat(data.changeUtc),
                volume: parseFloat(data.baseVolume),
                high: parseFloat(data.high24h),
                low: parseFloat(data.low24h),
                timestamp: parseInt(data.ts)
            };
        });
        
        // 깊이 데이터 변환기
        this.dataTransformers.set('depth', (data) => {
            return {
                symbol: data.instId,
                bids: data.bids.map(([price, size]) => [parseFloat(price), parseFloat(size)]),
                asks: data.asks.map(([price, size]) => [parseFloat(price), parseFloat(size)]),
                timestamp: parseInt(data.ts)
            };
        });
        
        // 거래 데이터 변환기
        this.dataTransformers.set('trades', (data) => {
            return data.map(trade => ({
                id: trade.tradeId,
                price: parseFloat(trade.px),
                size: parseFloat(trade.sz),
                side: trade.side,
                timestamp: parseInt(trade.ts)
            }));
        });
        
        // K라인 데이터 변환기
        this.dataTransformers.set('kline', (data) => {
            return data.map(candle => ({
                timestamp: parseInt(candle[0]),
                open: parseFloat(candle[1]),
                high: parseFloat(candle[2]),
                low: parseFloat(candle[3]),
                close: parseFloat(candle[4]),
                volume: parseFloat(candle[5])
            }));
        });
    }

    /**
     * 데이터 변환
     */
    transformData(data, dataType) {
        const baseType = dataType.startsWith('kline') ? 'kline' : dataType;
        const transformer = this.dataTransformers.get(baseType);
        
        if (transformer) {
            return transformer(data);
        }
        
        return data;
    }

    /**
     * 캐시 업데이트
     */
    updateCache(streamKey, data) {
        const cached = this.dataCache.get(streamKey) || {
            data: null,
            timestamp: 0,
            updateCount: 0
        };
        
        cached.data = data;
        cached.timestamp = Date.now();
        cached.updateCount++;
        
        this.dataCache.set(streamKey, cached);
        
        // 오래된 캐시 정리
        this.cleanupOldCache();
    }

    /**
     * 오래된 캐시 정리
     */
    cleanupOldCache() {
        const now = Date.now();
        
        for (const [key, cached] of this.dataCache) {
            if (now - cached.timestamp > this.cacheTimeout) {
                this.dataCache.delete(key);
            }
        }
    }

    /**
     * 배치 처리기 설정
     */
    setupBatchProcessor() {
        setInterval(() => {
            this.processBatchUpdates();
        }, this.batchDelay);
    }

    /**
     * 배치에 추가
     */
    addToBatch(streamKey, data) {
        if (!this.pendingUpdates.has(streamKey)) {
            this.pendingUpdates.set(streamKey, []);
        }
        
        const batch = this.pendingUpdates.get(streamKey);
        batch.push({
            data,
            timestamp: Date.now()
        });
        
        // 배치 크기 제한
        if (batch.length > this.batchSize) {
            batch.splice(0, batch.length - this.batchSize);
        }
    }

    /**
     * 배치 업데이트 처리
     */
    processBatchUpdates() {
        for (const [streamKey, batch] of this.pendingUpdates) {
            if (batch.length === 0) continue;
            
            const subscription = this.subscriptions.get(streamKey);
            if (!subscription) continue;
            
            // 구독자들에게 업데이트 전송
            for (const chartId of subscription.subscribers) {
                this.updateChart(chartId, streamKey, batch);
            }
            
            // 배치 초기화
            batch.length = 0;
        }
        
        this.stats.dataUpdates++;
    }

    /**
     * 차트 업데이트
     */
    updateChart(chartId, streamKey, batch) {
        const binding = this.chartBindings.get(chartId);
        if (!binding) return;
        
        const chart = binding.chart;
        const latestData = batch[batch.length - 1].data;
        
        // 차트 타입별 업데이트
        try {
            if (chart.updateData) {
                chart.updateData(latestData);
            } else if (chart.addDataPoint) {
                chart.addDataPoint(latestData);
            } else if (chart.chart && chart.chart.update) {
                this.updateChartJS(chart, latestData);
            }
            
            binding.lastUpdate = Date.now();
            binding.updateCount++;
            
            this.emit('chartUpdated', {
                chartId,
                streamKey,
                data: latestData,
                updateCount: binding.updateCount
            });
        } catch (error) {
            this.emit('chartUpdateError', {
                chartId,
                streamKey,
                error
            });
        }
    }

    /**
     * Chart.js 업데이트
     */
    updateChartJS(chart, data) {
        const chartInstance = chart.chart;
        
        if (chartInstance.data && chartInstance.data.datasets) {
            // 데이터셋 업데이트 로직
            chartInstance.data.datasets.forEach((dataset, index) => {
                if (data.values && data.values[index] !== undefined) {
                    dataset.data.push(data.values[index]);
                    
                    // 최대 데이터 포인트 수 제한
                    if (dataset.data.length > this.maxDataPoints) {
                        dataset.data.shift();
                    }
                }
            });
            
            // 라벨 업데이트
            if (data.label) {
                chartInstance.data.labels.push(data.label);
                
                if (chartInstance.data.labels.length > this.maxDataPoints) {
                    chartInstance.data.labels.shift();
                }
            }
            
            chartInstance.update('none');
        }
    }

    /**
     * 성능 모니터링 설정
     */
    setupPerformanceMonitoring() {
        setInterval(() => {
            this.emit('performanceStats', {
                ...this.stats,
                subscriptions: this.subscriptions.size,
                chartBindings: this.chartBindings.size,
                cacheSize: this.dataCache.size,
                isConnected: this.isConnected
            });
        }, 10000); // 10초마다
    }

    /**
     * 지연시간 통계 업데이트
     */
    updateLatencyStats(latency) {
        if (this.stats.averageLatency === 0) {
            this.stats.averageLatency = latency;
        } else {
            this.stats.averageLatency = (this.stats.averageLatency * 0.9) + (latency * 0.1);
        }
    }

    /**
     * 핑/퐁 처리
     */
    handlePingPong(data) {
        if (data.ping) {
            this.sendMessage({ pong: data.ping });
        }
    }

    /**
     * 구독 확인 처리
     */
    handleSubscriptionConfirm(data) {
        const streamKey = this.getStreamKey(data.arg);
        const subscription = this.subscriptions.get(streamKey);
        
        if (subscription) {
            subscription.confirmed = true;
            this.emit('subscriptionConfirmed', { streamKey, data });
        }
    }

    /**
     * 연결 해제 처리
     */
    handleDisconnection(event) {
        this.isConnected = false;
        this.emit('disconnected', event);
        
        if (event.code !== 1000) { // 정상 종료가 아닌 경우
            this.attemptReconnection();
        }
    }

    /**
     * 연결 오류 처리
     */
    handleConnectionError(error) {
        this.stats.errors++;
        this.emit('connectionError', error);
        this.attemptReconnection();
    }

    /**
     * 재연결 시도
     */
    attemptReconnection() {
        if (this.reconnectAttempts >= this.maxReconnectAttempts) {
            this.emit('maxReconnectAttemptsReached');
            return;
        }
        
        const delay = this.reconnectDelay * Math.pow(2, this.reconnectAttempts);
        this.reconnectAttempts++;
        
        setTimeout(() => {
            this.emit('reconnecting', { attempt: this.reconnectAttempts });
            this.connect();
        }, delay);
        
        this.stats.reconnections++;
    }

    /**
     * 모든 구독 재구독
     */
    resubscribeAll() {
        for (const [streamKey, subscription] of this.subscriptions) {
            this.sendSubscriptionMessage(streamKey, subscription.type);
        }
    }

    /**
     * 캐시에서 데이터 가져오기
     */
    getCachedData(streamKey) {
        const cached = this.dataCache.get(streamKey);
        return cached ? cached.data : null;
    }

    /**
     * 연결 상태 확인
     */
    isHealthy() {
        return this.isConnected && this.ws && this.ws.readyState === WebSocket.OPEN;
    }

    /**
     * 통계 리셋
     */
    resetStats() {
        this.stats = {
            messagesReceived: 0,
            messagesProcessed: 0,
            dataUpdates: 0,
            errors: 0,
            reconnections: 0,
            averageLatency: 0
        };
    }

    /**
     * 설정 업데이트
     */
    updateSettings(settings) {
        if (settings.batchSize !== undefined) {
            this.batchSize = settings.batchSize;
        }
        
        if (settings.batchDelay !== undefined) {
            this.batchDelay = settings.batchDelay;
        }
        
        if (settings.maxDataPoints !== undefined) {
            this.maxDataPoints = settings.maxDataPoints;
        }
        
        this.emit('settingsUpdated', settings);
    }

    /**
     * 연결 종료
     */
    disconnect() {
        if (this.ws) {
            this.ws.close(1000, 'Normal closure');
        }
        
        this.isConnected = false;
        this.emit('manualDisconnect');
    }

    /**
     * 정리
     */
    destroy() {
        this.disconnect();
        
        // 구독 정리
        this.subscriptions.clear();
        this.chartBindings.clear();
        this.dataStreams.clear();
        this.dataCache.clear();
        this.pendingUpdates.clear();
        
        // 변환기 정리
        this.dataTransformers.clear();
        
        super.destroy();
    }
}

export default RealTimeDataBinder;
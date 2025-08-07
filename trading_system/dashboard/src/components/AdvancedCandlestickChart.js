import { ChartBase } from './ChartBase.js';

/**
 * 고급 캔들스틱 차트
 * - OHLC 데이터 시각화
 * - 기술적 지표 통합
 * - 다중 시간대 지원
 * - 인터랙티브 분석 도구
 */
export class AdvancedCandlestickChart extends ChartBase {
    constructor(container, options = {}) {
        super(container, {
            ...options,
            chartType: 'candlestick' // 커스텀 차트 타입
        });
        
        // 캔들스틱 설정
        this.symbol = options.symbol || 'BTCUSDT';
        this.timeframe = options.timeframe || '1h';
        this.candleCount = options.candleCount || 200;
        
        // OHLC 데이터
        this.ohlcData = [];
        this.volumeData = [];
        this.currentPrice = 0;
        
        // 기술적 지표
        this.indicators = new Map();
        this.enabledIndicators = options.indicators || ['SMA20', 'EMA50', 'RSI', 'MACD'];
        
        // 차트 상태
        this.showVolume = options.showVolume !== false;
        this.showGrid = options.showGrid !== false;
        this.showCrosshair = options.showCrosshair !== false;
        
        // 인터랙션
        this.selectedCandle = null;
        this.zoomLevel = 1;
        this.panOffset = 0;
        
        this.initializeCandlestickChart();
    }

    /**
     * 캔들스틱 차트 초기화
     */
    initializeCandlestickChart() {
        this.createCustomCandlestickChart();
        this.generateMockOHLCData();
        this.calculateTechnicalIndicators();
        this.render();
        this.setupCandlestickEventListeners();
    }

    /**
     * 커스텀 캔들스틱 차트 생성
     */
    createCustomCandlestickChart() {
        // Chart.js는 기본적으로 캔들스틱을 지원하지 않으므로 커스텀 구현
        this.setupCandlestickCanvas();
        this.setupCandlestickOptions();
    }

    /**
     * 캔들스틱 캔버스 설정
     */
    setupCandlestickCanvas() {
        if (this.canvas) {
            this.canvas.remove();
        }
        
        // 메인 캔버스 생성
        this.canvas = document.createElement('canvas');
        this.ctx = this.canvas.getContext('2d');
        
        // 캔버스 크기 설정
        const width = this.element.clientWidth || 800;
        const height = this.element.clientHeight || 400;
        
        this.canvas.width = width;
        this.canvas.height = height;
        this.canvas.style.width = '100%';
        this.canvas.style.height = '100%';
        
        this.element.appendChild(this.canvas);
        
        // 고DPI 지원
        const devicePixelRatio = window.devicePixelRatio || 1;
        if (devicePixelRatio > 1) {
            this.canvas.width = width * devicePixelRatio;
            this.canvas.height = height * devicePixelRatio;
            this.canvas.style.width = width + 'px';
            this.canvas.style.height = height + 'px';
            this.ctx.scale(devicePixelRatio, devicePixelRatio);
        }
        
        // 차트 영역 계산
        this.chartArea = {
            x: 60,
            y: 40,
            width: width - 120,
            height: height - 100
        };
        
        // 볼륨 차트 영역
        if (this.showVolume) {
            this.chartArea.height *= 0.7;
            this.volumeArea = {
                x: this.chartArea.x,
                y: this.chartArea.y + this.chartArea.height + 10,
                width: this.chartArea.width,
                height: (height - 100) * 0.3 - 10
            };
        }
    }

    /**
     * 캔들스틱 차트 옵션 설정
     */
    setupCandlestickOptions() {
        this.candlestickOptions = {
            candleWidth: 8,
            wickWidth: 1,
            candleSpacing: 2,
            bullColor: this.colors.profit,
            bearColor: this.colors.loss,
            wickColor: this.colors.text,
            volumeColor: this.colors.primary,
            gridColor: this.colors.gridLines,
            textColor: this.colors.text,
            crosshairColor: this.colors.warning
        };
    }

    /**
     * 캔들스틱 이벤트 리스너 설정
     */
    setupCandlestickEventListeners() {
        // 마우스 이벤트
        this.canvas.addEventListener('mousemove', (e) => {
            this.handleMouseMove(e);
        });
        
        this.canvas.addEventListener('click', (e) => {
            this.handleMouseClick(e);
        });
        
        // 휠 이벤트 (줌)
        this.canvas.addEventListener('wheel', (e) => {
            e.preventDefault();
            this.handleWheel(e);
        });
        
        // 키보드 이벤트
        document.addEventListener('keydown', (e) => {
            this.handleKeydown(e);
        });
        
        // 터치 이벤트 (모바일)
        this.canvas.addEventListener('touchstart', (e) => {
            this.handleTouchStart(e);
        });
        
        this.canvas.addEventListener('touchmove', (e) => {
            this.handleTouchMove(e);
        });
        
        this.canvas.addEventListener('touchend', (e) => {
            this.handleTouchEnd(e);
        });
    }

    /**
     * 마우스 이동 핸들러
     */
    handleMouseMove(e) {
        const rect = this.canvas.getBoundingClientRect();
        const x = e.clientX - rect.left;
        const y = e.clientY - rect.top;
        
        // 캔들 선택
        const candle = this.getCandleAtPosition(x, y);
        if (candle !== this.selectedCandle) {
            this.selectedCandle = candle;
            this.render();
            
            if (candle) {
                this.showCandleTooltip(e, candle);
            } else {
                this.hideCandleTooltip();
            }
        }
        
        // 크로스헤어 업데이트
        if (this.showCrosshair) {
            this.crosshair = { x, y };
            this.render();
        }
    }

    /**
     * 마우스 클릭 핸들러
     */
    handleMouseClick(e) {
        const rect = this.canvas.getBoundingClientRect();
        const x = e.clientX - rect.left;
        const y = e.clientY - rect.top;
        
        const candle = this.getCandleAtPosition(x, y);
        if (candle) {
            this.emit('candleSelected', candle);
        }
    }

    /**
     * 휠 이벤트 핸들러 (줌)
     */
    handleWheel(e) {
        const delta = e.deltaY > 0 ? 0.9 : 1.1;
        this.zoomLevel = Math.max(0.1, Math.min(5, this.zoomLevel * delta));
        this.render();
        this.emit('zoomChanged', this.zoomLevel);
    }

    /**
     * 키보드 이벤트 핸들러
     */
    handleKeydown(e) {
        switch(e.key) {
            case 'ArrowLeft':
                this.panOffset = Math.max(0, this.panOffset - 10);
                this.render();
                break;
            case 'ArrowRight':
                this.panOffset = Math.min(this.ohlcData.length - this.candleCount, this.panOffset + 10);
                this.render();
                break;
            case '+':
                this.zoomLevel = Math.min(5, this.zoomLevel * 1.1);
                this.render();
                break;
            case '-':
                this.zoomLevel = Math.max(0.1, this.zoomLevel * 0.9);
                this.render();
                break;
        }
    }

    /**
     * 터치 이벤트 핸들러들
     */
    handleTouchStart(e) {
        e.preventDefault();
        this.touchStart = {
            x: e.touches[0].clientX,
            y: e.touches[0].clientY,
            time: Date.now()
        };
    }

    handleTouchMove(e) {
        e.preventDefault();
        if (!this.touchStart) return;
        
        const deltaX = e.touches[0].clientX - this.touchStart.x;
        const newPanOffset = this.panOffset - Math.floor(deltaX / 10);
        this.panOffset = Math.max(0, Math.min(this.ohlcData.length - this.candleCount, newPanOffset));
        this.render();
    }

    handleTouchEnd(e) {
        this.touchStart = null;
    }

    /**
     * 위치에 해당하는 캔들 가져오기
     */
    getCandleAtPosition(x, y) {
        if (x < this.chartArea.x || x > this.chartArea.x + this.chartArea.width ||
            y < this.chartArea.y || y > this.chartArea.y + this.chartArea.height) {
            return null;
        }
        
        const candleWidth = this.candlestickOptions.candleWidth + this.candlestickOptions.candleSpacing;
        const candleIndex = Math.floor((x - this.chartArea.x) / candleWidth) + this.panOffset;
        
        if (candleIndex >= 0 && candleIndex < this.ohlcData.length) {
            return {
                index: candleIndex,
                data: this.ohlcData[candleIndex]
            };
        }
        
        return null;
    }

    /**
     * 차트 렌더링
     */
    render() {
        if (!this.ctx) return;
        
        // 캔버스 초기화
        this.ctx.clearRect(0, 0, this.canvas.width, this.canvas.height);
        
        // 배경 그리기
        this.drawBackground();
        
        // 그리드 그리기
        if (this.showGrid) {
            this.drawGrid();
        }
        
        // Y축 (가격) 그리기
        this.drawPriceAxis();
        
        // X축 (시간) 그리기
        this.drawTimeAxis();
        
        // 캔들스틱 그리기
        this.drawCandles();
        
        // 기술적 지표 그리기
        this.drawTechnicalIndicators();
        
        // 볼륨 차트 그리기
        if (this.showVolume) {
            this.drawVolumeChart();
        }
        
        // 크로스헤어 그리기
        if (this.showCrosshair && this.crosshair) {
            this.drawCrosshair();
        }
        
        // 선택된 캔들 하이라이트
        if (this.selectedCandle) {
            this.highlightCandle(this.selectedCandle);
        }
    }

    /**
     * 배경 그리기
     */
    drawBackground() {
        this.ctx.fillStyle = this.colors.background;
        this.ctx.fillRect(0, 0, this.canvas.width, this.canvas.height);
    }

    /**
     * 그리드 그리기
     */
    drawGrid() {
        this.ctx.strokeStyle = this.candlestickOptions.gridColor;
        this.ctx.lineWidth = 0.5;
        this.ctx.setLineDash([2, 2]);
        
        // 수직 그리드 선
        const candleWidth = this.candlestickOptions.candleWidth + this.candlestickOptions.candleSpacing;
        for (let i = 0; i < this.candleCount; i += 10) {
            const x = this.chartArea.x + (i * candleWidth);
            this.ctx.beginPath();
            this.ctx.moveTo(x, this.chartArea.y);
            this.ctx.lineTo(x, this.chartArea.y + this.chartArea.height);
            this.ctx.stroke();
        }
        
        // 수평 그리드 선
        const priceRange = this.getPriceRange();
        const gridCount = 10;
        for (let i = 0; i <= gridCount; i++) {
            const y = this.chartArea.y + (this.chartArea.height / gridCount) * i;
            this.ctx.beginPath();
            this.ctx.moveTo(this.chartArea.x, y);
            this.ctx.lineTo(this.chartArea.x + this.chartArea.width, y);
            this.ctx.stroke();
        }
        
        this.ctx.setLineDash([]);
    }

    /**
     * 가격 축 그리기
     */
    drawPriceAxis() {
        this.ctx.fillStyle = this.candlestickOptions.textColor;
        this.ctx.font = '12px Inter, sans-serif';
        this.ctx.textAlign = 'right';
        this.ctx.textBaseline = 'middle';
        
        const priceRange = this.getPriceRange();
        const gridCount = 10;
        
        for (let i = 0; i <= gridCount; i++) {
            const price = priceRange.min + (priceRange.max - priceRange.min) * (1 - i / gridCount);
            const y = this.chartArea.y + (this.chartArea.height / gridCount) * i;
            
            this.ctx.fillText(`$${price.toFixed(0)}`, this.chartArea.x - 10, y);
        }
    }

    /**
     * 시간 축 그리기
     */
    drawTimeAxis() {
        this.ctx.fillStyle = this.candlestickOptions.textColor;
        this.ctx.font = '12px Inter, sans-serif';
        this.ctx.textAlign = 'center';
        this.ctx.textBaseline = 'top';
        
        const candleWidth = this.candlestickOptions.candleWidth + this.candlestickOptions.candleSpacing;
        const displayCount = Math.min(this.candleCount, this.ohlcData.length - this.panOffset);
        
        for (let i = 0; i < displayCount; i += Math.max(1, Math.floor(displayCount / 8))) {
            const dataIndex = i + this.panOffset;
            if (dataIndex < this.ohlcData.length) {
                const candle = this.ohlcData[dataIndex];
                const x = this.chartArea.x + (i * candleWidth) + this.candlestickOptions.candleWidth / 2;
                const y = this.chartArea.y + this.chartArea.height + 5;
                
                const date = new Date(candle.timestamp);
                const timeString = this.formatTime(date);
                this.ctx.fillText(timeString, x, y);
            }
        }
    }

    /**
     * 캔들스틱 그리기
     */
    drawCandles() {
        const priceRange = this.getPriceRange();
        const candleWidth = this.candlestickOptions.candleWidth + this.candlestickOptions.candleSpacing;
        const displayCount = Math.min(this.candleCount, this.ohlcData.length - this.panOffset);
        
        for (let i = 0; i < displayCount; i++) {
            const dataIndex = i + this.panOffset;
            if (dataIndex >= this.ohlcData.length) break;
            
            const candle = this.ohlcData[dataIndex];
            const x = this.chartArea.x + (i * candleWidth);
            
            this.drawSingleCandle(candle, x, priceRange);
        }
    }

    /**
     * 단일 캔들 그리기
     */
    drawSingleCandle(candle, x, priceRange) {
        const { open, high, low, close } = candle;
        const isBull = close >= open;
        
        // 가격을 Y 좌표로 변환
        const openY = this.priceToY(open, priceRange);
        const highY = this.priceToY(high, priceRange);
        const lowY = this.priceToY(low, priceRange);
        const closeY = this.priceToY(close, priceRange);
        
        // 심지(wick) 그리기
        this.ctx.strokeStyle = this.candlestickOptions.wickColor;
        this.ctx.lineWidth = this.candlestickOptions.wickWidth;
        this.ctx.beginPath();
        this.ctx.moveTo(x + this.candlestickOptions.candleWidth / 2, highY);
        this.ctx.lineTo(x + this.candlestickOptions.candleWidth / 2, lowY);
        this.ctx.stroke();
        
        // 몸통(body) 그리기
        const bodyTop = Math.min(openY, closeY);
        const bodyHeight = Math.abs(openY - closeY);
        const bodyColor = isBull ? this.candlestickOptions.bullColor : this.candlestickOptions.bearColor;
        
        this.ctx.fillStyle = bodyColor;
        this.ctx.fillRect(x, bodyTop, this.candlestickOptions.candleWidth, Math.max(1, bodyHeight));
        
        // 몸통 테두리
        this.ctx.strokeStyle = bodyColor;
        this.ctx.lineWidth = 1;
        this.ctx.strokeRect(x, bodyTop, this.candlestickOptions.candleWidth, Math.max(1, bodyHeight));
    }

    /**
     * 가격을 Y 좌표로 변환
     */
    priceToY(price, priceRange) {
        const ratio = (price - priceRange.min) / (priceRange.max - priceRange.min);
        return this.chartArea.y + this.chartArea.height - (ratio * this.chartArea.height);
    }

    /**
     * 기술적 지표 그리기
     */
    drawTechnicalIndicators() {
        this.enabledIndicators.forEach(indicator => {
            const indicatorData = this.indicators.get(indicator);
            if (indicatorData) {
                this.drawIndicator(indicator, indicatorData);
            }
        });
    }

    /**
     * 단일 지표 그리기
     */
    drawIndicator(name, data) {
        switch(name) {
            case 'SMA20':
                this.drawMovingAverage(data, '#ff6b6b', 2);
                break;
            case 'EMA50':
                this.drawMovingAverage(data, '#4ecdc4', 2);
                break;
            case 'RSI':
                this.drawRSI(data);
                break;
            case 'MACD':
                this.drawMACD(data);
                break;
        }
    }

    /**
     * 이동평균 그리기
     */
    drawMovingAverage(data, color, lineWidth) {
        this.ctx.strokeStyle = color;
        this.ctx.lineWidth = lineWidth;
        this.ctx.beginPath();
        
        const priceRange = this.getPriceRange();
        const candleWidth = this.candlestickOptions.candleWidth + this.candlestickOptions.candleSpacing;
        let firstPoint = true;
        
        for (let i = 0; i < Math.min(this.candleCount, data.length - this.panOffset); i++) {
            const dataIndex = i + this.panOffset;
            if (dataIndex >= data.length || !data[dataIndex]) continue;
            
            const x = this.chartArea.x + (i * candleWidth) + this.candlestickOptions.candleWidth / 2;
            const y = this.priceToY(data[dataIndex], priceRange);
            
            if (firstPoint) {
                this.ctx.moveTo(x, y);
                firstPoint = false;
            } else {
                this.ctx.lineTo(x, y);
            }
        }
        
        this.ctx.stroke();
    }

    /**
     * RSI 그리기 (하단 패널)
     */
    drawRSI(data) {
        // RSI는 별도 패널에 그리기 (구현 간소화)
        this.emit('indicatorDrawn', { name: 'RSI', data });
    }

    /**
     * MACD 그리기 (하단 패널)
     */
    drawMACD(data) {
        // MACD는 별도 패널에 그리기 (구현 간소화)
        this.emit('indicatorDrawn', { name: 'MACD', data });
    }

    /**
     * 볼륨 차트 그리기
     */
    drawVolumeChart() {
        if (!this.volumeArea || !this.volumeData.length) return;
        
        const maxVolume = Math.max(...this.volumeData.slice(this.panOffset, this.panOffset + this.candleCount));
        const candleWidth = this.candlestickOptions.candleWidth + this.candlestickOptions.candleSpacing;
        const displayCount = Math.min(this.candleCount, this.volumeData.length - this.panOffset);
        
        for (let i = 0; i < displayCount; i++) {
            const dataIndex = i + this.panOffset;
            if (dataIndex >= this.volumeData.length) break;
            
            const volume = this.volumeData[dataIndex];
            const height = (volume / maxVolume) * this.volumeArea.height;
            const x = this.volumeArea.x + (i * candleWidth);
            const y = this.volumeArea.y + this.volumeArea.height - height;
            
            // 볼륨 바의 색상은 해당 캔들의 상승/하락에 따라
            const candle = this.ohlcData[dataIndex];
            const color = candle && candle.close >= candle.open 
                ? this.candlestickOptions.bullColor 
                : this.candlestickOptions.bearColor;
            
            this.ctx.fillStyle = color;
            this.ctx.fillRect(x, y, this.candlestickOptions.candleWidth, height);
        }
    }

    /**
     * 크로스헤어 그리기
     */
    drawCrosshair() {
        if (!this.crosshair) return;
        
        this.ctx.strokeStyle = this.candlestickOptions.crosshairColor;
        this.ctx.lineWidth = 1;
        this.ctx.setLineDash([3, 3]);
        
        // 수직선
        this.ctx.beginPath();
        this.ctx.moveTo(this.crosshair.x, this.chartArea.y);
        this.ctx.lineTo(this.crosshair.x, this.chartArea.y + this.chartArea.height);
        this.ctx.stroke();
        
        // 수평선
        this.ctx.beginPath();
        this.ctx.moveTo(this.chartArea.x, this.crosshair.y);
        this.ctx.lineTo(this.chartArea.x + this.chartArea.width, this.crosshair.y);
        this.ctx.stroke();
        
        this.ctx.setLineDash([]);
    }

    /**
     * 캔들 하이라이트
     */
    highlightCandle(candle) {
        const candleWidth = this.candlestickOptions.candleWidth + this.candlestickOptions.candleSpacing;
        const i = candle.index - this.panOffset;
        const x = this.chartArea.x + (i * candleWidth);
        
        this.ctx.strokeStyle = this.colors.warning;
        this.ctx.lineWidth = 2;
        this.ctx.strokeRect(x - 1, this.chartArea.y, this.candlestickOptions.candleWidth + 2, this.chartArea.height);
    }

    /**
     * 가격 범위 계산
     */
    getPriceRange() {
        let min = Infinity;
        let max = -Infinity;
        
        const startIndex = this.panOffset;
        const endIndex = Math.min(startIndex + this.candleCount, this.ohlcData.length);
        
        for (let i = startIndex; i < endIndex; i++) {
            const candle = this.ohlcData[i];
            min = Math.min(min, candle.low);
            max = Math.max(max, candle.high);
        }
        
        // 패딩 추가
        const padding = (max - min) * 0.1;
        return {
            min: min - padding,
            max: max + padding
        };
    }

    /**
     * 시간 포맷
     */
    formatTime(date) {
        return date.toLocaleDateString('ko-KR', {
            month: 'short',
            day: 'numeric'
        });
    }

    /**
     * 모크 OHLC 데이터 생성
     */
    generateMockOHLCData() {
        this.ohlcData = [];
        this.volumeData = [];
        
        let price = 45000;
        const startTime = Date.now() - (this.candleCount * 60 * 60 * 1000); // 1시간 간격
        
        for (let i = 0; i < this.candleCount; i++) {
            const open = price;
            const change = (Math.random() - 0.5) * 1000; // ±500 변동
            const close = Math.max(open + change, open * 0.95); // 최소 5% 하락 제한
            
            const high = Math.max(open, close) + (Math.random() * 200);
            const low = Math.min(open, close) - (Math.random() * 200);
            
            const volume = Math.random() * 1000 + 100;
            
            this.ohlcData.push({
                timestamp: startTime + (i * 60 * 60 * 1000),
                open,
                high,
                low,
                close,
                volume
            });
            
            this.volumeData.push(volume);
            price = close;
        }
        
        this.currentPrice = price;
    }

    /**
     * 기술적 지표 계산
     */
    calculateTechnicalIndicators() {
        this.indicators.clear();
        
        if (this.ohlcData.length === 0) return;
        
        // SMA 20
        if (this.enabledIndicators.includes('SMA20')) {
            this.indicators.set('SMA20', this.calculateSMA(20));
        }
        
        // EMA 50
        if (this.enabledIndicators.includes('EMA50')) {
            this.indicators.set('EMA50', this.calculateEMA(50));
        }
        
        // RSI
        if (this.enabledIndicators.includes('RSI')) {
            this.indicators.set('RSI', this.calculateRSI(14));
        }
        
        // MACD
        if (this.enabledIndicators.includes('MACD')) {
            this.indicators.set('MACD', this.calculateMACD());
        }
    }

    /**
     * SMA (단순이동평균) 계산
     */
    calculateSMA(period) {
        const sma = [];
        
        for (let i = 0; i < this.ohlcData.length; i++) {
            if (i >= period - 1) {
                let sum = 0;
                for (let j = i - period + 1; j <= i; j++) {
                    sum += this.ohlcData[j].close;
                }
                sma[i] = sum / period;
            } else {
                sma[i] = null;
            }
        }
        
        return sma;
    }

    /**
     * EMA (지수이동평균) 계산
     */
    calculateEMA(period) {
        const ema = [];
        const multiplier = 2 / (period + 1);
        
        for (let i = 0; i < this.ohlcData.length; i++) {
            if (i === 0) {
                ema[i] = this.ohlcData[i].close;
            } else {
                ema[i] = (this.ohlcData[i].close - ema[i - 1]) * multiplier + ema[i - 1];
            }
        }
        
        return ema;
    }

    /**
     * RSI 계산
     */
    calculateRSI(period) {
        const rsi = [];
        const gains = [];
        const losses = [];
        
        for (let i = 1; i < this.ohlcData.length; i++) {
            const change = this.ohlcData[i].close - this.ohlcData[i - 1].close;
            gains[i] = change > 0 ? change : 0;
            losses[i] = change < 0 ? -change : 0;
        }
        
        for (let i = period; i < this.ohlcData.length; i++) {
            const avgGain = gains.slice(i - period + 1, i + 1).reduce((a, b) => a + b) / period;
            const avgLoss = losses.slice(i - period + 1, i + 1).reduce((a, b) => a + b) / period;
            
            if (avgLoss === 0) {
                rsi[i] = 100;
            } else {
                const rs = avgGain / avgLoss;
                rsi[i] = 100 - (100 / (1 + rs));
            }
        }
        
        return rsi;
    }

    /**
     * MACD 계산
     */
    calculateMACD() {
        const ema12 = this.calculateEMA(12);
        const ema26 = this.calculateEMA(26);
        const macdLine = [];
        
        for (let i = 0; i < this.ohlcData.length; i++) {
            if (ema12[i] && ema26[i]) {
                macdLine[i] = ema12[i] - ema26[i];
            } else {
                macdLine[i] = null;
            }
        }
        
        // 신호선 계산 (MACD의 EMA)
        const signalLine = this.calculateEMAFromArray(macdLine, 9);
        
        return {
            macd: macdLine,
            signal: signalLine
        };
    }

    /**
     * 배열에서 EMA 계산
     */
    calculateEMAFromArray(data, period) {
        const ema = [];
        const multiplier = 2 / (period + 1);
        let firstValidIndex = -1;
        
        // 첫 번째 유효한 값 찾기
        for (let i = 0; i < data.length; i++) {
            if (data[i] !== null) {
                firstValidIndex = i;
                break;
            }
        }
        
        if (firstValidIndex === -1) return ema;
        
        for (let i = 0; i < data.length; i++) {
            if (i < firstValidIndex || data[i] === null) {
                ema[i] = null;
            } else if (i === firstValidIndex) {
                ema[i] = data[i];
            } else {
                ema[i] = (data[i] - ema[i - 1]) * multiplier + ema[i - 1];
            }
        }
        
        return ema;
    }

    /**
     * 캔들 툴팁 표시
     */
    showCandleTooltip(event, candle) {
        const tooltip = this.getOrCreateTooltip();
        const data = candle.data;
        
        tooltip.innerHTML = `
            <div class="candlestick-tooltip">
                <div class="tooltip-time">${new Date(data.timestamp).toLocaleString()}</div>
                <div class="tooltip-prices">
                    <div>시가: $${data.open.toFixed(2)}</div>
                    <div>고가: $${data.high.toFixed(2)}</div>
                    <div>저가: $${data.low.toFixed(2)}</div>
                    <div>종가: $${data.close.toFixed(2)}</div>
                </div>
                <div class="tooltip-volume">거래량: ${data.volume.toFixed(2)}</div>
                <div class="tooltip-change">
                    변화: ${((data.close - data.open) / data.open * 100).toFixed(2)}%
                </div>
            </div>
        `;
        
        tooltip.style.display = 'block';
        tooltip.style.left = event.pageX + 10 + 'px';
        tooltip.style.top = event.pageY - 10 + 'px';
    }

    /**
     * 캔들 툴팁 숨기기
     */
    hideCandleTooltip() {
        const tooltip = document.getElementById('candlestick-tooltip');
        if (tooltip) {
            tooltip.style.display = 'none';
        }
    }

    /**
     * 툴팁 엘리먼트 가져오기/생성
     */
    getOrCreateTooltip() {
        let tooltip = document.getElementById('candlestick-tooltip');
        
        if (!tooltip) {
            tooltip = document.createElement('div');
            tooltip.id = 'candlestick-tooltip';
            tooltip.className = 'chart-tooltip';
            tooltip.style.cssText = `
                position: absolute;
                background: ${this.colors.tooltipBg};
                border: 1px solid ${this.colors.border};
                border-radius: 8px;
                padding: 12px;
                font-size: 12px;
                color: ${this.colors.text};
                box-shadow: 0 4px 12px rgba(0, 0, 0, 0.15);
                pointer-events: none;
                z-index: 1000;
                display: none;
                font-family: Inter, sans-serif;
            `;
            
            document.body.appendChild(tooltip);
        }
        
        return tooltip;
    }

    /**
     * OHLC 데이터 업데이트
     */
    updateOHLCData(newData) {
        this.ohlcData = newData.ohlc || [];
        this.volumeData = newData.volume || [];
        this.currentPrice = newData.currentPrice || 0;
        
        this.calculateTechnicalIndicators();
        this.render();
        this.emit('ohlcDataUpdated', newData);
    }

    /**
     * 시간대 변경
     */
    changeTimeframe(timeframe) {
        this.timeframe = timeframe;
        this.emit('timeframeChanged', timeframe);
        // 실제 구현에서는 API 호출하여 새 데이터 가져오기
    }

    /**
     * 지표 토글
     */
    toggleIndicator(indicatorName) {
        const index = this.enabledIndicators.indexOf(indicatorName);
        if (index >= 0) {
            this.enabledIndicators.splice(index, 1);
        } else {
            this.enabledIndicators.push(indicatorName);
        }
        
        this.calculateTechnicalIndicators();
        this.render();
        this.emit('indicatorToggled', { indicator: indicatorName, enabled: index < 0 });
    }

    /**
     * 차트 데이터 내보내기
     */
    exportChartData() {
        return {
            symbol: this.symbol,
            timeframe: this.timeframe,
            ohlcData: this.ohlcData,
            volumeData: this.volumeData,
            indicators: Object.fromEntries(this.indicators),
            currentPrice: this.currentPrice,
            timestamp: Date.now()
        };
    }

    /**
     * 정리
     */
    destroy() {
        this.hideCandleTooltip();
        
        // 툴팁 제거
        const tooltip = document.getElementById('candlestick-tooltip');
        if (tooltip) {
            tooltip.remove();
        }
        
        this.indicators.clear();
        
        super.destroy();
    }
}

export default AdvancedCandlestickChart;
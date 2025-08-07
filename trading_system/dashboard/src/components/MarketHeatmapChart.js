import { ChartBase } from './ChartBase.js';

/**
 * 시장 상관관계 히트맵 차트
 * - 암호화폐 간 상관관계 시각화
 * - 인터랙티브 히트맵
 * - 실시간 상관관계 업데이트
 * - 커스텀 색상 스케일
 */
export class MarketHeatmapChart extends ChartBase {
    constructor(container, options = {}) {
        super(container, {
            ...options,
            chartType: 'scatter' // 히트맵을 위한 기본 타입
        });
        
        // 히트맵 특화 설정
        this.symbols = options.symbols || ['BTC', 'ETH', 'BNB', 'ADA', 'DOT', 'SOL', 'MATIC', 'AVAX'];
        this.correlationMatrix = new Map();
        this.heatmapData = [];
        this.cellSize = options.cellSize || 40;
        this.colorScale = options.colorScale || this.createDefaultColorScale();
        
        // 상관관계 계산 설정
        this.windowSize = options.windowSize || 24; // 24시간
        this.updateInterval = options.updateInterval || 60000; // 1분
        
        // 히트맵 상태
        this.hoveredCell = null;
        this.selectedCells = new Set();
        
        this.initializeHeatmap();
    }

    /**
     * 히트맵 초기화
     */
    initializeHeatmap() {
        this.setupHeatmapCanvas();
        this.generateMockData(); // 실제 구현시 실제 데이터로 교체
        this.render();
    }

    /**
     * 히트맵 캔버스 설정
     */
    setupHeatmapCanvas() {
        // 기존 캔버스 제거
        if (this.canvas) {
            this.canvas.remove();
        }
        
        // 새로운 캔버스 생성
        this.canvas = document.createElement('canvas');
        this.ctx = this.canvas.getContext('2d');
        
        // 캔버스 크기 설정
        const size = this.symbols.length * this.cellSize + 100; // 여백 포함
        this.canvas.width = size;
        this.canvas.height = size;
        this.canvas.style.maxWidth = '100%';
        this.canvas.style.height = 'auto';
        
        this.element.appendChild(this.canvas);
        
        // 고DPI 지원
        const devicePixelRatio = window.devicePixelRatio || 1;
        if (devicePixelRatio > 1) {
            this.canvas.width = size * devicePixelRatio;
            this.canvas.height = size * devicePixelRatio;
            this.canvas.style.width = size + 'px';
            this.canvas.style.height = size + 'px';
            this.ctx.scale(devicePixelRatio, devicePixelRatio);
        }
        
        this.setupHeatmapEventListeners();
    }

    /**
     * 히트맵 이벤트 리스너 설정
     */
    setupHeatmapEventListeners() {
        // 마우스 이동
        this.canvas.addEventListener('mousemove', (e) => {
            const rect = this.canvas.getBoundingClientRect();
            const x = e.clientX - rect.left;
            const y = e.clientY - rect.top;
            
            const cell = this.getCellAtPosition(x, y);
            
            if (cell && cell !== this.hoveredCell) {
                this.hoveredCell = cell;
                this.render();
                this.showTooltip(e, cell);
            } else if (!cell && this.hoveredCell) {
                this.hoveredCell = null;
                this.render();
                this.hideTooltip();
            }
        });

        // 마우스 클릭
        this.canvas.addEventListener('click', (e) => {
            const rect = this.canvas.getBoundingClientRect();
            const x = e.clientX - rect.left;
            const y = e.clientY - rect.top;
            
            const cell = this.getCellAtPosition(x, y);
            if (cell) {
                this.toggleCellSelection(cell);
                this.emit('cellClicked', cell);
            }
        });

        // 마우스 떠남
        this.canvas.addEventListener('mouseleave', () => {
            this.hoveredCell = null;
            this.render();
            this.hideTooltip();
        });
    }

    /**
     * 위치에서 셀 가져오기
     */
    getCellAtPosition(x, y) {
        const margin = 50;
        const cellX = Math.floor((x - margin) / this.cellSize);
        const cellY = Math.floor((y - margin) / this.cellSize);
        
        if (cellX >= 0 && cellX < this.symbols.length && 
            cellY >= 0 && cellY < this.symbols.length) {
            return {
                x: cellX,
                y: cellY,
                symbol1: this.symbols[cellY],
                symbol2: this.symbols[cellX],
                correlation: this.getCorrelation(this.symbols[cellY], this.symbols[cellX])
            };
        }
        
        return null;
    }

    /**
     * 셀 선택 토글
     */
    toggleCellSelection(cell) {
        const cellKey = `${cell.symbol1}-${cell.symbol2}`;
        
        if (this.selectedCells.has(cellKey)) {
            this.selectedCells.delete(cellKey);
        } else {
            this.selectedCells.add(cellKey);
        }
        
        this.render();
    }

    /**
     * 기본 색상 스케일 생성
     */
    createDefaultColorScale() {
        return {
            '-1.0': '#ef4444', // 강한 음의 상관관계 (빨강)
            '-0.7': '#f97316',
            '-0.5': '#f59e0b',
            '-0.3': '#eab308',
            '0.0': '#6b7280',  // 무상관 (회색)
            '0.3': '#84cc16',
            '0.5': '#22c55e',
            '0.7': '#10b981',
            '1.0': '#059669'   // 강한 양의 상관관계 (녹색)
        };
    }

    /**
     * 상관관계 값에 따른 색상 가져오기
     */
    getColorForCorrelation(correlation) {
        const abs = Math.abs(correlation);
        
        if (abs >= 0.8) {
            return correlation > 0 ? '#059669' : '#ef4444';
        } else if (abs >= 0.6) {
            return correlation > 0 ? '#10b981' : '#f97316';
        } else if (abs >= 0.4) {
            return correlation > 0 ? '#22c55e' : '#f59e0b';
        } else if (abs >= 0.2) {
            return correlation > 0 ? '#84cc16' : '#eab308';
        } else {
            return '#6b7280';
        }
    }

    /**
     * 상관관계 가져오기
     */
    getCorrelation(symbol1, symbol2) {
        if (symbol1 === symbol2) return 1.0;
        
        const key1 = `${symbol1}-${symbol2}`;
        const key2 = `${symbol2}-${symbol1}`;
        
        return this.correlationMatrix.get(key1) || this.correlationMatrix.get(key2) || 0;
    }

    /**
     * 상관관계 설정
     */
    setCorrelation(symbol1, symbol2, correlation) {
        const key = `${symbol1}-${symbol2}`;
        this.correlationMatrix.set(key, correlation);
    }

    /**
     * 히트맵 렌더링
     */
    render() {
        if (!this.ctx) return;
        
        // 캔버스 초기화
        this.ctx.clearRect(0, 0, this.canvas.width, this.canvas.height);
        
        // 배경 그리기
        this.drawBackground();
        
        // 라벨 그리기
        this.drawLabels();
        
        // 히트맵 셀 그리기
        this.drawHeatmapCells();
        
        // 범례 그리기
        this.drawLegend();
        
        // 호버/선택 효과
        this.drawEffects();
    }

    /**
     * 배경 그리기
     */
    drawBackground() {
        this.ctx.fillStyle = this.colors.background;
        this.ctx.fillRect(0, 0, this.canvas.width, this.canvas.height);
    }

    /**
     * 라벨 그리기
     */
    drawLabels() {
        this.ctx.fillStyle = this.colors.text;
        this.ctx.font = '12px Inter, sans-serif';
        this.ctx.textAlign = 'center';
        this.ctx.textBaseline = 'middle';
        
        const margin = 50;
        
        // X축 라벨 (상단)
        for (let i = 0; i < this.symbols.length; i++) {
            const x = margin + i * this.cellSize + this.cellSize / 2;
            const y = margin - 10;
            this.ctx.fillText(this.symbols[i], x, y);
        }
        
        // Y축 라벨 (좌측)
        this.ctx.textAlign = 'right';
        for (let i = 0; i < this.symbols.length; i++) {
            const x = margin - 10;
            const y = margin + i * this.cellSize + this.cellSize / 2;
            this.ctx.fillText(this.symbols[i], x, y);
        }
    }

    /**
     * 히트맵 셀 그리기
     */
    drawHeatmapCells() {
        const margin = 50;
        
        for (let row = 0; row < this.symbols.length; row++) {
            for (let col = 0; col < this.symbols.length; col++) {
                const x = margin + col * this.cellSize;
                const y = margin + row * this.cellSize;
                
                const symbol1 = this.symbols[row];
                const symbol2 = this.symbols[col];
                const correlation = this.getCorrelation(symbol1, symbol2);
                
                // 셀 배경색
                this.ctx.fillStyle = this.getColorForCorrelation(correlation);
                this.ctx.fillRect(x, y, this.cellSize, this.cellSize);
                
                // 셀 테두리
                this.ctx.strokeStyle = this.colors.border;
                this.ctx.lineWidth = 1;
                this.ctx.strokeRect(x, y, this.cellSize, this.cellSize);
                
                // 상관관계 값 텍스트
                if (this.cellSize > 30) {
                    this.ctx.fillStyle = this.getTextColorForBackground(correlation);
                    this.ctx.font = '10px Inter, sans-serif';
                    this.ctx.textAlign = 'center';
                    this.ctx.textBaseline = 'middle';
                    
                    const text = correlation.toFixed(2);
                    this.ctx.fillText(text, x + this.cellSize / 2, y + this.cellSize / 2);
                }
            }
        }
    }

    /**
     * 배경색에 따른 텍스트 색상
     */
    getTextColorForBackground(correlation) {
        const abs = Math.abs(correlation);
        return abs > 0.5 ? '#ffffff' : '#000000';
    }

    /**
     * 범례 그리기
     */
    drawLegend() {
        const legendX = this.canvas.width - 80;
        const legendY = 50;
        const legendWidth = 20;
        const legendHeight = this.symbols.length * this.cellSize;
        
        // 범례 그라데이션
        const gradient = this.ctx.createLinearGradient(0, legendY, 0, legendY + legendHeight);
        gradient.addColorStop(0, '#ef4444'); // -1
        gradient.addColorStop(0.25, '#f59e0b'); // -0.5
        gradient.addColorStop(0.5, '#6b7280'); // 0
        gradient.addColorStop(0.75, '#22c55e'); // 0.5
        gradient.addColorStop(1, '#059669'); // 1
        
        this.ctx.fillStyle = gradient;
        this.ctx.fillRect(legendX, legendY, legendWidth, legendHeight);
        
        // 범례 테두리
        this.ctx.strokeStyle = this.colors.border;
        this.ctx.lineWidth = 1;
        this.ctx.strokeRect(legendX, legendY, legendWidth, legendHeight);
        
        // 범례 라벨
        this.ctx.fillStyle = this.colors.text;
        this.ctx.font = '10px Inter, sans-serif';
        this.ctx.textAlign = 'left';
        
        const labels = ['-1.0', '-0.5', '0.0', '0.5', '1.0'];
        for (let i = 0; i < labels.length; i++) {
            const y = legendY + (i / (labels.length - 1)) * legendHeight;
            this.ctx.fillText(labels[i], legendX + legendWidth + 5, y + 3);
        }
        
        // 범례 제목
        this.ctx.font = '12px Inter, sans-serif';
        this.ctx.fillText('상관관계', legendX, legendY - 15);
    }

    /**
     * 호버 및 선택 효과 그리기
     */
    drawEffects() {
        const margin = 50;
        
        // 호버 효과
        if (this.hoveredCell) {
            const x = margin + this.hoveredCell.x * this.cellSize;
            const y = margin + this.hoveredCell.y * this.cellSize;
            
            this.ctx.strokeStyle = this.colors.primary;
            this.ctx.lineWidth = 3;
            this.ctx.strokeRect(x, y, this.cellSize, this.cellSize);
        }
        
        // 선택 효과
        for (const cellKey of this.selectedCells) {
            const [symbol1, symbol2] = cellKey.split('-');
            const row = this.symbols.indexOf(symbol1);
            const col = this.symbols.indexOf(symbol2);
            
            if (row >= 0 && col >= 0) {
                const x = margin + col * this.cellSize;
                const y = margin + row * this.cellSize;
                
                this.ctx.strokeStyle = this.colors.warning;
                this.ctx.lineWidth = 2;
                this.ctx.setLineDash([5, 5]);
                this.ctx.strokeRect(x, y, this.cellSize, this.cellSize);
                this.ctx.setLineDash([]);
            }
        }
    }

    /**
     * 툴팁 표시
     */
    showTooltip(event, cell) {
        const tooltip = this.getOrCreateTooltip();
        
        tooltip.innerHTML = `
            <div class="heatmap-tooltip">
                <div class="tooltip-title">${cell.symbol1} vs ${cell.symbol2}</div>
                <div class="tooltip-correlation">상관관계: <strong>${cell.correlation.toFixed(3)}</strong></div>
                <div class="tooltip-description">${this.getCorrelationDescription(cell.correlation)}</div>
            </div>
        `;
        
        tooltip.style.display = 'block';
        tooltip.style.left = event.pageX + 10 + 'px';
        tooltip.style.top = event.pageY - 10 + 'px';
    }

    /**
     * 상관관계 설명 가져오기
     */
    getCorrelationDescription(correlation) {
        const abs = Math.abs(correlation);
        
        if (abs >= 0.8) {
            return correlation > 0 ? '매우 강한 양의 상관관계' : '매우 강한 음의 상관관계';
        } else if (abs >= 0.6) {
            return correlation > 0 ? '강한 양의 상관관계' : '강한 음의 상관관계';
        } else if (abs >= 0.4) {
            return correlation > 0 ? '중간 양의 상관관계' : '중간 음의 상관관계';
        } else if (abs >= 0.2) {
            return correlation > 0 ? '약한 양의 상관관계' : '약한 음의 상관관계';
        } else {
            return '상관관계 없음';
        }
    }

    /**
     * 툴팁 엘리먼트 가져오기/생성
     */
    getOrCreateTooltip() {
        let tooltip = document.getElementById('heatmap-tooltip');
        
        if (!tooltip) {
            tooltip = document.createElement('div');
            tooltip.id = 'heatmap-tooltip';
            tooltip.className = 'chart-tooltip';
            tooltip.style.cssText = `
                position: absolute;
                background: ${this.colors.tooltipBg};
                border: 1px solid ${this.colors.border};
                border-radius: 6px;
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
     * 툴팁 숨기기
     */
    hideTooltip() {
        const tooltip = document.getElementById('heatmap-tooltip');
        if (tooltip) {
            tooltip.style.display = 'none';
        }
    }

    /**
     * 모크 데이터 생성 (테스트용)
     */
    generateMockData() {
        // 실제 구현에서는 API에서 데이터를 가져옴
        for (let i = 0; i < this.symbols.length; i++) {
            for (let j = 0; j < this.symbols.length; j++) {
                if (i !== j) {
                    // 랜덤 상관관계 생성 (-1 ~ 1)
                    const correlation = (Math.random() - 0.5) * 2;
                    this.setCorrelation(this.symbols[i], this.symbols[j], correlation);
                }
            }
        }
    }

    /**
     * 실제 상관관계 데이터 업데이트
     */
    updateCorrelations(correlationData) {
        this.correlationMatrix.clear();
        
        for (const [pair, correlation] of Object.entries(correlationData)) {
            const [symbol1, symbol2] = pair.split('-');
            this.setCorrelation(symbol1, symbol2, correlation);
        }
        
        this.render();
        this.emit('correlationsUpdated', correlationData);
    }

    /**
     * 상관관계 계산 (가격 데이터 기반)
     */
    calculateCorrelations(priceData) {
        const correlations = {};
        
        for (let i = 0; i < this.symbols.length; i++) {
            for (let j = i + 1; j < this.symbols.length; j++) {
                const symbol1 = this.symbols[i];
                const symbol2 = this.symbols[j];
                
                const prices1 = priceData[symbol1] || [];
                const prices2 = priceData[symbol2] || [];
                
                if (prices1.length > 1 && prices2.length > 1) {
                    const correlation = this.pearsonCorrelation(prices1, prices2);
                    correlations[`${symbol1}-${symbol2}`] = correlation;
                }
            }
        }
        
        this.updateCorrelations(correlations);
        return correlations;
    }

    /**
     * 피어슨 상관계수 계산
     */
    pearsonCorrelation(x, y) {
        const n = Math.min(x.length, y.length);
        if (n < 2) return 0;
        
        // 평균 계산
        const meanX = x.slice(0, n).reduce((a, b) => a + b) / n;
        const meanY = y.slice(0, n).reduce((a, b) => a + b) / n;
        
        // 공분산과 표준편차 계산
        let numerator = 0;
        let sumXSquared = 0;
        let sumYSquared = 0;
        
        for (let i = 0; i < n; i++) {
            const deltaX = x[i] - meanX;
            const deltaY = y[i] - meanY;
            
            numerator += deltaX * deltaY;
            sumXSquared += deltaX * deltaX;
            sumYSquared += deltaY * deltaY;
        }
        
        const denominator = Math.sqrt(sumXSquared * sumYSquared);
        
        return denominator === 0 ? 0 : numerator / denominator;
    }

    /**
     * 히트맵 내보내기
     */
    exportHeatmap() {
        return {
            symbols: this.symbols,
            correlations: Object.fromEntries(this.correlationMatrix),
            timestamp: Date.now()
        };
    }

    /**
     * 정리
     */
    destroy() {
        this.hideTooltip();
        
        // 툴팁 제거
        const tooltip = document.getElementById('heatmap-tooltip');
        if (tooltip) {
            tooltip.remove();
        }
        
        super.destroy();
    }
}

export default MarketHeatmapChart;
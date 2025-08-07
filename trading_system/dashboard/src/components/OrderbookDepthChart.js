import { ChartBase } from './ChartBase.js';

/**
 * 실시간 오더북 깊이 차트
 * - 매수/매도 주문량 시각화
 * - 실시간 오더북 데이터 업데이트
 * - 인터랙티브 가격 레벨 선택
 * - 깊이 분석 기능
 */
export class OrderbookDepthChart extends ChartBase {
    constructor(container, options = {}) {
        super(container, {
            ...options,
            chartType: 'line'
        });
        
        // 오더북 설정
        this.symbol = options.symbol || 'BTCUSDT';
        this.maxLevels = options.maxLevels || 50;
        this.priceRange = options.priceRange || 0.05; // 5% 범위
        
        // 오더북 데이터
        this.bids = []; // 매수 주문
        this.asks = []; // 매도 주문
        this.currentPrice = 0;
        this.spread = 0;
        
        // 차트 상태
        this.selectedPrice = null;
        this.showCumulativeDepth = options.showCumulativeDepth !== false;
        this.showSpreadInfo = options.showSpreadInfo !== false;
        
        this.initializeDepthChart();
    }

    /**
     * 깊이 차트 초기화
     */
    initializeDepthChart() {
        this.setupDepthOptions();
        this.generateMockOrderbook(); // 실제 구현시 실제 데이터로 교체
        this.updateChart();
    }

    /**
     * 깊이 차트 옵션 설정
     */
    setupDepthOptions() {
        const depthOptions = {
            responsive: true,
            maintainAspectRatio: false,
            interaction: {
                intersect: false,
                mode: 'x'
            },
            plugins: {
                legend: {
                    display: true,
                    position: 'top',
                    labels: {
                        color: this.colors.text,
                        font: {
                            family: 'Inter, sans-serif',
                            size: 12
                        },
                        generateLabels: (chart) => {
                            return [
                                {
                                    text: '매수 주문 (Bids)',
                                    fillStyle: this.colors.profit,
                                    strokeStyle: this.colors.profit,
                                    pointStyle: 'rect'
                                },
                                {
                                    text: '매도 주문 (Asks)',
                                    fillStyle: this.colors.loss,
                                    strokeStyle: this.colors.loss,
                                    pointStyle: 'rect'
                                }
                            ];
                        }
                    }
                },
                tooltip: {
                    backgroundColor: this.colors.tooltipBg,
                    titleColor: this.colors.text,
                    bodyColor: this.colors.text,
                    borderColor: this.colors.border,
                    borderWidth: 1,
                    cornerRadius: 8,
                    callbacks: {
                        title: (tooltipItems) => {
                            if (tooltipItems.length > 0) {
                                const price = tooltipItems[0].parsed.x;
                                return `가격: $${price.toLocaleString()}`;
                            }
                            return '';
                        },
                        label: (context) => {
                            const isBid = context.datasetIndex === 0;
                            const volume = context.parsed.y;
                            const cumulative = this.getCumulativeVolume(context.parsed.x, isBid);
                            
                            return [
                                `${isBid ? '매수' : '매도'} 수량: ${volume.toLocaleString()}`,
                                `누적 수량: ${cumulative.toLocaleString()}`
                            ];
                        }
                    }
                }
            },
            scales: {
                x: {
                    type: 'linear',
                    position: 'bottom',
                    title: {
                        display: true,
                        text: '가격 (USDT)',
                        color: this.colors.text,
                        font: {
                            family: 'Inter, sans-serif',
                            size: 12,
                            weight: 'bold'
                        }
                    },
                    grid: {
                        color: this.colors.gridLines,
                        drawBorder: false
                    },
                    ticks: {
                        color: this.colors.text,
                        font: {
                            family: 'Inter, sans-serif',
                            size: 10
                        },
                        callback: (value) => {
                            return `$${value.toLocaleString()}`;
                        }
                    }
                },
                y: {
                    title: {
                        display: true,
                        text: '수량',
                        color: this.colors.text,
                        font: {
                            family: 'Inter, sans-serif',
                            size: 12,
                            weight: 'bold'
                        }
                    },
                    grid: {
                        color: this.colors.gridLines,
                        drawBorder: false
                    },
                    ticks: {
                        color: this.colors.text,
                        font: {
                            family: 'Inter, sans-serif',
                            size: 10
                        },
                        callback: (value) => {
                            return value.toLocaleString();
                        }
                    }
                }
            },
            elements: {
                point: {
                    radius: 0,
                    hoverRadius: 4
                },
                line: {
                    tension: 0,
                    borderWidth: 2
                }
            }
        };

        this.chartOptions = this.mergeOptions(this.chartOptions, depthOptions);
    }

    /**
     * 오더북 데이터 업데이트
     */
    updateOrderbook(orderbookData) {
        this.bids = orderbookData.bids || [];
        this.asks = orderbookData.asks || [];
        this.currentPrice = orderbookData.currentPrice || 0;
        
        // 스프레드 계산
        if (this.bids.length > 0 && this.asks.length > 0) {
            const bestBid = this.bids[0][0];
            const bestAsk = this.asks[0][0];
            this.spread = bestAsk - bestBid;
        }
        
        this.updateChart();
        this.emit('orderbookUpdated', orderbookData);
    }

    /**
     * 차트 업데이트
     */
    updateChart() {
        if (!this.chart) return;
        
        // 데이터셋 생성
        const datasets = this.createDepthDatasets();
        
        this.chart.data = {
            datasets
        };
        
        this.chart.update('none');
    }

    /**
     * 깊이 데이터셋 생성
     */
    createDepthDatasets() {
        const datasets = [];
        
        // 매수 주문 (Bids) - 왼쪽에서 중앙으로
        if (this.bids.length > 0) {
            const bidsData = this.processBidsData();
            
            datasets.push({
                label: '매수 주문',
                data: bidsData.points,
                borderColor: this.colors.profit,
                backgroundColor: this.createGradient(this.colors.profit, 0.3),
                fill: 'origin',
                stepped: 'after',
                pointRadius: 0,
                pointHoverRadius: 4,
                borderWidth: 2
            });
        }
        
        // 매도 주문 (Asks) - 중앙에서 오른쪽으로
        if (this.asks.length > 0) {
            const asksData = this.processAsksData();
            
            datasets.push({
                label: '매도 주문',
                data: asksData.points,
                borderColor: this.colors.loss,
                backgroundColor: this.createGradient(this.colors.loss, 0.3),
                fill: 'origin',
                stepped: 'before',
                pointRadius: 0,
                pointHoverRadius: 4,
                borderWidth: 2
            });
        }
        
        // 현재 가격 선
        if (this.currentPrice > 0) {
            const maxVolume = this.getMaxVolume();
            datasets.push({
                label: '현재 가격',
                data: [
                    { x: this.currentPrice, y: 0 },
                    { x: this.currentPrice, y: maxVolume }
                ],
                borderColor: this.colors.warning,
                backgroundColor: 'transparent',
                borderWidth: 2,
                borderDash: [5, 5],
                pointRadius: 0,
                fill: false
            });
        }
        
        return datasets;
    }

    /**
     * 매수 주문 데이터 처리
     */
    processBidsData() {
        const points = [];
        let cumulativeVolume = 0;
        
        // 가격 순으로 정렬 (높은 가격부터)
        const sortedBids = [...this.bids]
            .sort((a, b) => parseFloat(b[0]) - parseFloat(a[0]))
            .slice(0, this.maxLevels);
        
        for (const [price, quantity] of sortedBids) {
            const priceNum = parseFloat(price);
            const quantityNum = parseFloat(quantity);
            
            if (this.showCumulativeDepth) {
                cumulativeVolume += quantityNum;
                points.push({ x: priceNum, y: cumulativeVolume });
            } else {
                points.push({ x: priceNum, y: quantityNum });
            }
        }
        
        return { points, cumulativeVolume };
    }

    /**
     * 매도 주문 데이터 처리
     */
    processAsksData() {
        const points = [];
        let cumulativeVolume = 0;
        
        // 가격 순으로 정렬 (낮은 가격부터)
        const sortedAsks = [...this.asks]
            .sort((a, b) => parseFloat(a[0]) - parseFloat(b[0]))
            .slice(0, this.maxLevels);
        
        for (const [price, quantity] of sortedAsks) {
            const priceNum = parseFloat(price);
            const quantityNum = parseFloat(quantity);
            
            if (this.showCumulativeDepth) {
                cumulativeVolume += quantityNum;
                points.push({ x: priceNum, y: cumulativeVolume });
            } else {
                points.push({ x: priceNum, y: quantityNum });
            }
        }
        
        return { points, cumulativeVolume };
    }

    /**
     * 그라데이션 생성
     */
    createGradient(color, opacity) {
        if (!this.ctx) return color;
        
        const gradient = this.ctx.createLinearGradient(0, 0, 0, 400);
        gradient.addColorStop(0, this.hexToRgba(color, opacity));
        gradient.addColorStop(1, this.hexToRgba(color, 0.1));
        
        return gradient;
    }

    /**
     * 헥스 컬러를 RGBA로 변환
     */
    hexToRgba(hex, alpha) {
        const result = /^#?([a-f\d]{2})([a-f\d]{2})([a-f\d]{2})$/i.exec(hex);
        if (!result) return hex;
        
        const r = parseInt(result[1], 16);
        const g = parseInt(result[2], 16);
        const b = parseInt(result[3], 16);
        
        return `rgba(${r}, ${g}, ${b}, ${alpha})`;
    }

    /**
     * 최대 볼륨 가져오기
     */
    getMaxVolume() {
        let maxVolume = 0;
        
        this.bids.forEach(([price, quantity]) => {
            maxVolume = Math.max(maxVolume, parseFloat(quantity));
        });
        
        this.asks.forEach(([price, quantity]) => {
            maxVolume = Math.max(maxVolume, parseFloat(quantity));
        });
        
        return maxVolume;
    }

    /**
     * 누적 볼륨 가져오기
     */
    getCumulativeVolume(price, isBid) {
        let cumulative = 0;
        const orders = isBid ? this.bids : this.asks;
        
        for (const [orderPrice, quantity] of orders) {
            const orderPriceNum = parseFloat(orderPrice);
            
            if (isBid && orderPriceNum >= price) {
                cumulative += parseFloat(quantity);
            } else if (!isBid && orderPriceNum <= price) {
                cumulative += parseFloat(quantity);
            }
        }
        
        return cumulative;
    }

    /**
     * 깊이 분석 정보 가져오기
     */
    getDepthAnalysis() {
        if (this.bids.length === 0 || this.asks.length === 0) {
            return null;
        }
        
        const bestBid = parseFloat(this.bids[0][0]);
        const bestAsk = parseFloat(this.asks[0][0]);
        const spread = bestAsk - bestBid;
        const spreadPercentage = (spread / this.currentPrice) * 100;
        
        // 매수/매도 총량 계산
        const totalBidVolume = this.bids.reduce((sum, [price, qty]) => sum + parseFloat(qty), 0);
        const totalAskVolume = this.asks.reduce((sum, [price, qty]) => sum + parseFloat(qty), 0);
        
        // 불균형 계산
        const imbalance = (totalBidVolume - totalAskVolume) / (totalBidVolume + totalAskVolume);
        
        // 주요 가격 레벨 찾기
        const significantLevels = this.findSignificantLevels();
        
        return {
            bestBid,
            bestAsk,
            spread,
            spreadPercentage,
            totalBidVolume,
            totalAskVolume,
            imbalance,
            significantLevels,
            timestamp: Date.now()
        };
    }

    /**
     * 주요 가격 레벨 찾기
     */
    findSignificantLevels() {
        const allOrders = [
            ...this.bids.map(([price, qty]) => ({ price: parseFloat(price), quantity: parseFloat(qty), type: 'bid' })),
            ...this.asks.map(([price, qty]) => ({ price: parseFloat(price), quantity: parseFloat(qty), type: 'ask' }))
        ];
        
        // 수량이 많은 상위 레벨들 찾기
        const significantLevels = allOrders
            .filter(order => order.quantity > this.getAverageOrderSize() * 2)
            .sort((a, b) => b.quantity - a.quantity)
            .slice(0, 10);
        
        return significantLevels;
    }

    /**
     * 평균 주문 크기 계산
     */
    getAverageOrderSize() {
        const allQuantities = [
            ...this.bids.map(([price, qty]) => parseFloat(qty)),
            ...this.asks.map(([price, qty]) => parseFloat(qty))
        ];
        
        if (allQuantities.length === 0) return 0;
        
        return allQuantities.reduce((sum, qty) => sum + qty, 0) / allQuantities.length;
    }

    /**
     * 모크 오더북 데이터 생성 (테스트용)
     */
    generateMockOrderbook() {
        const basePrice = 45000; // BTC 기준 가격
        this.currentPrice = basePrice;
        
        this.bids = [];
        this.asks = [];
        
        // 매수 주문 생성 (현재 가격 아래)
        for (let i = 0; i < this.maxLevels; i++) {
            const price = basePrice - (i * 10) - Math.random() * 10;
            const quantity = Math.random() * 5 + 0.1;
            this.bids.push([price.toFixed(2), quantity.toFixed(4)]);
        }
        
        // 매도 주문 생성 (현재 가격 위)
        for (let i = 0; i < this.maxLevels; i++) {
            const price = basePrice + (i * 10) + Math.random() * 10;
            const quantity = Math.random() * 5 + 0.1;
            this.asks.push([price.toFixed(2), quantity.toFixed(4)]);
        }
        
        // 정렬
        this.bids.sort((a, b) => parseFloat(b[0]) - parseFloat(a[0])); // 높은 가격부터
        this.asks.sort((a, b) => parseFloat(a[0]) - parseFloat(b[0])); // 낮은 가격부터
    }

    /**
     * 깊이 표시 모드 토글
     */
    toggleCumulativeDepth() {
        this.showCumulativeDepth = !this.showCumulativeDepth;
        this.updateChart();
        this.emit('depthModeToggled', this.showCumulativeDepth);
    }

    /**
     * 가격 레벨 선택
     */
    selectPriceLevel(price) {
        this.selectedPrice = price;
        this.highlightPriceLevel(price);
        this.emit('priceLevelSelected', price);
    }

    /**
     * 가격 레벨 하이라이트
     */
    highlightPriceLevel(price) {
        // 구현: 선택된 가격 레벨을 시각적으로 강조
        this.emit('priceLevelHighlighted', price);
    }

    /**
     * 오더북 통계 가져오기
     */
    getOrderbookStats() {
        const analysis = this.getDepthAnalysis();
        if (!analysis) return null;
        
        return {
            symbol: this.symbol,
            currentPrice: this.currentPrice,
            spread: analysis.spread,
            spreadPercentage: analysis.spreadPercentage,
            bidLevels: this.bids.length,
            askLevels: this.asks.length,
            totalBidVolume: analysis.totalBidVolume,
            totalAskVolume: analysis.totalAskVolume,
            marketImbalance: analysis.imbalance,
            significantLevels: analysis.significantLevels.length,
            lastUpdate: analysis.timestamp
        };
    }

    /**
     * 오더북 데이터 내보내기
     */
    exportOrderbook() {
        return {
            symbol: this.symbol,
            timestamp: Date.now(),
            currentPrice: this.currentPrice,
            spread: this.spread,
            bids: this.bids,
            asks: this.asks,
            analysis: this.getDepthAnalysis()
        };
    }

    /**
     * 차트 설정 업데이트
     */
    updateSettings(settings) {
        if (settings.maxLevels !== undefined) {
            this.maxLevels = settings.maxLevels;
        }
        
        if (settings.priceRange !== undefined) {
            this.priceRange = settings.priceRange;
        }
        
        if (settings.showCumulativeDepth !== undefined) {
            this.showCumulativeDepth = settings.showCumulativeDepth;
        }
        
        if (settings.symbol !== undefined) {
            this.symbol = settings.symbol;
        }
        
        this.updateChart();
        this.emit('settingsUpdated', settings);
    }

    /**
     * 포맷 유틸리티
     */
    formatValue(value) {
        if (typeof value === 'number') {
            return value.toFixed(4);
        }
        return value;
    }

    formatTooltipLabel(context) {
        const isBid = context.datasetIndex === 0;
        const price = context.parsed.x;
        const volume = context.parsed.y;
        
        return `${isBid ? '매수' : '매도'}: ${volume.toFixed(4)} @ $${price.toLocaleString()}`;
    }

    /**
     * 정리
     */
    destroy() {
        super.destroy();
    }
}

export default OrderbookDepthChart;
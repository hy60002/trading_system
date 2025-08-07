import { ChartBase } from './ChartBase.js';

/**
 * 볼륨 프로파일 차트
 * - 가격대별 거래량 분석
 * - POC (Point of Control) 표시
 * - VPVR (Volume Profile Visible Range)
 * - 고량/저량 노드 분석
 */
export class VolumeProfileChart extends ChartBase {
    constructor(container, options = {}) {
        super(container, {
            ...options,
            chartType: 'bar' // 볼륨 프로파일용 바차트
        });
        
        // 볼륨 프로파일 설정
        this.priceLevels = options.priceLevels || 100; // 가격 레벨 수
        this.profileType = options.profileType || 'session'; // session, fixed, anchored
        this.sessionStart = options.sessionStart || '09:00';
        this.sessionEnd = options.sessionEnd || '18:00';
        
        // 볼륨 데이터
        this.volumeProfile = new Map(); // 가격대별 볼륨
        this.priceRanges = [];
        this.tradeData = []; // 원본 거래 데이터
        
        // POC 및 주요 레벨
        this.poc = null; // Point of Control (최대 거래량 가격)
        this.highVolumeNodes = [];
        this.lowVolumeNodes = [];
        this.valueArea = { high: null, low: null }; // 70% 거래량 구간
        
        // 차트 상태
        this.showPOC = options.showPOC !== false;
        this.showValueArea = options.showValueArea !== false;
        this.showVolumeNodes = options.showVolumeNodes !== false;
        
        this.initializeVolumeProfile();
    }

    /**
     * 볼륨 프로파일 초기화
     */
    initializeVolumeProfile() {
        this.setupVolumeProfileOptions();
        this.generateMockVolumeData(); // 실제 구현시 실제 데이터로 교체
        this.calculateVolumeProfile();
        this.updateChart();
    }

    /**
     * 볼륨 프로파일 차트 옵션 설정
     */
    setupVolumeProfileOptions() {
        const profileOptions = {
            indexAxis: 'y', // 수평 바 차트
            responsive: true,
            maintainAspectRatio: false,
            plugins: {
                legend: {
                    display: false
                },
                tooltip: {
                    backgroundColor: this.colors.tooltipBg,
                    titleColor: this.colors.text,
                    bodyColor: this.colors.text,
                    borderColor: this.colors.border,
                    borderWidth: 1,
                    callbacks: {
                        title: (tooltipItems) => {
                            if (tooltipItems.length > 0) {
                                const priceRange = tooltipItems[0].label;
                                return `가격대: $${priceRange}`;
                            }
                            return '';
                        },
                        label: (context) => {
                            const volume = context.parsed.x;
                            const percentage = this.getVolumePercentage(volume);
                            
                            return [
                                `거래량: ${volume.toLocaleString()}`,
                                `비율: ${percentage.toFixed(2)}%`
                            ];
                        }
                    }
                }
            },
            scales: {
                x: {
                    title: {
                        display: true,
                        text: '거래량',
                        color: this.colors.text,
                        font: {
                            family: 'Inter, sans-serif',
                            size: 12,
                            weight: 'bold'
                        }
                    },
                    grid: {
                        color: this.colors.gridLines
                    },
                    ticks: {
                        color: this.colors.text,
                        font: {
                            family: 'Inter, sans-serif',
                            size: 10
                        },
                        callback: (value) => {
                            return this.formatVolume(value);
                        }
                    }
                },
                y: {
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
                        color: this.colors.gridLines
                    },
                    ticks: {
                        color: this.colors.text,
                        font: {
                            family: 'Inter, sans-serif',
                            size: 10
                        },
                        callback: (value, index) => {
                            // 가격 범위를 표시
                            const range = this.priceRanges[index];
                            return range ? `$${range.min.toFixed(0)}-${range.max.toFixed(0)}` : '';
                        }
                    }
                }
            },
            elements: {
                bar: {
                    borderWidth: 1
                }
            }
        };

        this.chartOptions = this.mergeOptions(this.chartOptions, profileOptions);
    }

    /**
     * 거래 데이터 업데이트
     */
    updateTradeData(tradeData) {
        this.tradeData = tradeData;
        this.calculateVolumeProfile();
        this.updateChart();
        this.emit('tradeDataUpdated', tradeData);
    }

    /**
     * 볼륨 프로파일 계산
     */
    calculateVolumeProfile() {
        if (this.tradeData.length === 0) return;
        
        // 가격 범위 계산
        const prices = this.tradeData.map(trade => trade.price);
        const minPrice = Math.min(...prices);
        const maxPrice = Math.max(...prices);
        
        // 가격 레벨 구간 생성
        this.createPriceRanges(minPrice, maxPrice);
        
        // 각 구간별 거래량 집계
        this.aggregateVolumeByPrice();
        
        // POC 및 주요 레벨 계산
        this.calculatePOCAndLevels();
        
        // 밸류 에어리어 계산
        this.calculateValueArea();
    }

    /**
     * 가격 범위 구간 생성
     */
    createPriceRanges(minPrice, maxPrice) {
        this.priceRanges = [];
        this.volumeProfile.clear();
        
        const priceStep = (maxPrice - minPrice) / this.priceLevels;
        
        for (let i = 0; i < this.priceLevels; i++) {
            const rangeMin = minPrice + (i * priceStep);
            const rangeMax = minPrice + ((i + 1) * priceStep);
            
            const range = {
                min: rangeMin,
                max: rangeMax,
                mid: (rangeMin + rangeMax) / 2,
                volume: 0,
                trades: 0
            };
            
            this.priceRanges.push(range);
            this.volumeProfile.set(i, range);
        }
    }

    /**
     * 가격대별 거래량 집계
     */
    aggregateVolumeByPrice() {
        for (const trade of this.tradeData) {
            const priceLevel = this.findPriceLevelIndex(trade.price);
            
            if (priceLevel >= 0 && priceLevel < this.priceLevels) {
                const range = this.volumeProfile.get(priceLevel);
                if (range) {
                    range.volume += trade.volume;
                    range.trades += 1;
                    this.volumeProfile.set(priceLevel, range);
                }
            }
        }
    }

    /**
     * 가격에 해당하는 레벨 인덱스 찾기
     */
    findPriceLevelIndex(price) {
        for (let i = 0; i < this.priceRanges.length; i++) {
            const range = this.priceRanges[i];
            if (price >= range.min && price < range.max) {
                return i;
            }
        }
        return -1;
    }

    /**
     * POC 및 주요 레벨 계산
     */
    calculatePOCAndLevels() {
        let maxVolume = 0;
        let pocLevel = null;
        
        // POC (최대 거래량 레벨) 찾기
        for (const [level, range] of this.volumeProfile) {
            if (range.volume > maxVolume) {
                maxVolume = range.volume;
                pocLevel = level;
            }
        }
        
        if (pocLevel !== null) {
            this.poc = this.priceRanges[pocLevel];
        }
        
        // 고량/저량 노드 계산
        this.calculateVolumeNodes();
    }

    /**
     * 볼륨 노드 계산
     */
    calculateVolumeNodes() {
        const volumes = Array.from(this.volumeProfile.values()).map(range => range.volume);
        const avgVolume = volumes.reduce((sum, vol) => sum + vol, 0) / volumes.length;
        const stdDev = this.calculateStandardDeviation(volumes, avgVolume);
        
        this.highVolumeNodes = [];
        this.lowVolumeNodes = [];
        
        for (const [level, range] of this.volumeProfile) {
            if (range.volume > avgVolume + stdDev) {
                this.highVolumeNodes.push({
                    level,
                    range,
                    strength: (range.volume - avgVolume) / stdDev
                });
            } else if (range.volume < avgVolume - stdDev && range.volume > 0) {
                this.lowVolumeNodes.push({
                    level,
                    range,
                    strength: (avgVolume - range.volume) / stdDev
                });
            }
        }
        
        // 강도순으로 정렬
        this.highVolumeNodes.sort((a, b) => b.strength - a.strength);
        this.lowVolumeNodes.sort((a, b) => b.strength - a.strength);
    }

    /**
     * 표준편차 계산
     */
    calculateStandardDeviation(values, mean) {
        const squaredDiffs = values.map(value => Math.pow(value - mean, 2));
        const avgSquaredDiff = squaredDiffs.reduce((sum, diff) => sum + diff, 0) / values.length;
        return Math.sqrt(avgSquaredDiff);
    }

    /**
     * 밸류 에어리어 계산 (70% 거래량 구간)
     */
    calculateValueArea() {
        const totalVolume = Array.from(this.volumeProfile.values())
            .reduce((sum, range) => sum + range.volume, 0);
        
        const targetVolume = totalVolume * 0.7;
        
        // POC부터 시작하여 위아래로 확장
        if (!this.poc) return;
        
        let pocIndex = -1;
        for (let i = 0; i < this.priceRanges.length; i++) {
            if (this.priceRanges[i] === this.poc) {
                pocIndex = i;
                break;
            }
        }
        
        if (pocIndex === -1) return;
        
        let accumulatedVolume = this.poc.volume;
        let lowIndex = pocIndex;
        let highIndex = pocIndex;
        
        // 70% 거래량에 도달할 때까지 위아래로 확장
        while (accumulatedVolume < targetVolume) {
            const canExpandUp = highIndex + 1 < this.priceRanges.length;
            const canExpandDown = lowIndex - 1 >= 0;
            
            if (!canExpandUp && !canExpandDown) break;
            
            const upVolume = canExpandUp ? this.priceRanges[highIndex + 1].volume : 0;
            const downVolume = canExpandDown ? this.priceRanges[lowIndex - 1].volume : 0;
            
            if (upVolume >= downVolume && canExpandUp) {
                highIndex++;
                accumulatedVolume += this.priceRanges[highIndex].volume;
            } else if (canExpandDown) {
                lowIndex--;
                accumulatedVolume += this.priceRanges[lowIndex].volume;
            }
        }
        
        this.valueArea = {
            high: this.priceRanges[highIndex].max,
            low: this.priceRanges[lowIndex].min,
            volume: accumulatedVolume,
            percentage: (accumulatedVolume / totalVolume) * 100
        };
    }

    /**
     * 차트 업데이트
     */
    updateChart() {
        if (!this.chart) return;
        
        const datasets = this.createVolumeProfileDatasets();
        const labels = this.createPriceLabels();
        
        this.chart.data = {
            labels,
            datasets
        };
        
        this.chart.update('none');
    }

    /**
     * 볼륨 프로파일 데이터셋 생성
     */
    createVolumeProfileDatasets() {
        const datasets = [];
        
        // 볼륨 프로파일 바
        const volumeData = [];
        const backgroundColors = [];
        const borderColors = [];
        
        for (let i = 0; i < this.priceRanges.length; i++) {
            const range = this.volumeProfile.get(i);
            volumeData.push(range ? range.volume : 0);
            
            // POC 하이라이트
            if (this.showPOC && this.poc && range === this.poc) {
                backgroundColors.push(this.colors.warning);
                borderColors.push(this.colors.warning);
            }
            // 밸류 에어리어 하이라이트
            else if (this.showValueArea && range && 
                     range.mid >= this.valueArea.low && range.mid <= this.valueArea.high) {
                backgroundColors.push(this.hexToRgba(this.colors.primary, 0.6));
                borderColors.push(this.colors.primary);
            }
            // 고량 노드
            else if (this.showVolumeNodes && this.isHighVolumeNode(i)) {
                backgroundColors.push(this.colors.profit);
                borderColors.push(this.colors.profit);
            }
            // 저량 노드
            else if (this.showVolumeNodes && this.isLowVolumeNode(i)) {
                backgroundColors.push(this.colors.loss);
                borderColors.push(this.colors.loss);
            }
            // 일반 볼륨
            else {
                backgroundColors.push(this.hexToRgba(this.colors.primary, 0.7));
                borderColors.push(this.colors.primary);
            }
        }
        
        datasets.push({
            label: '거래량',
            data: volumeData,
            backgroundColor: backgroundColors,
            borderColor: borderColors,
            borderWidth: 1
        });
        
        return datasets;
    }

    /**
     * 가격 라벨 생성
     */
    createPriceLabels() {
        return this.priceRanges.map(range => 
            `${range.min.toFixed(0)}-${range.max.toFixed(0)}`
        );
    }

    /**
     * 고량 노드 확인
     */
    isHighVolumeNode(level) {
        return this.highVolumeNodes.some(node => node.level === level);
    }

    /**
     * 저량 노드 확인
     */
    isLowVolumeNode(level) {
        return this.lowVolumeNodes.some(node => node.level === level);
    }

    /**
     * 볼륨 비율 계산
     */
    getVolumePercentage(volume) {
        const totalVolume = Array.from(this.volumeProfile.values())
            .reduce((sum, range) => sum + range.volume, 0);
        
        return totalVolume > 0 ? (volume / totalVolume) * 100 : 0;
    }

    /**
     * 볼륨 포맷
     */
    formatVolume(volume) {
        if (volume >= 1000000) {
            return (volume / 1000000).toFixed(1) + 'M';
        } else if (volume >= 1000) {
            return (volume / 1000).toFixed(1) + 'K';
        } else {
            return volume.toFixed(0);
        }
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
     * 모크 볼륨 데이터 생성 (테스트용)
     */
    generateMockVolumeData() {
        this.tradeData = [];
        const basePrice = 45000;
        const numTrades = 10000;
        
        // 정규분포에 가까운 가격 분포로 거래 데이터 생성
        for (let i = 0; i < numTrades; i++) {
            // 가격: 정규분포 근사
            const priceOffset = this.boxMullerRandom() * 2000; // ±2000 범위
            const price = basePrice + priceOffset;
            
            // 거래량: 지수분포
            const volume = Math.random() * Math.random() * 10 + 0.1;
            
            this.tradeData.push({
                price: Math.max(price, basePrice * 0.8), // 최소값 제한
                volume: volume,
                timestamp: Date.now() - Math.random() * 86400000 // 24시간 내
            });
        }
        
        // 가격 순으로 정렬
        this.tradeData.sort((a, b) => a.price - b.price);
    }

    /**
     * Box-Muller 변환을 이용한 정규분포 난수 생성
     */
    boxMullerRandom() {
        if (this.hasSpare) {
            this.hasSpare = false;
            return this.spare;
        }
        
        this.hasSpare = true;
        const u = Math.random();
        const v = Math.random();
        const mag = Math.sqrt(-2 * Math.log(u));
        
        this.spare = mag * Math.cos(2 * Math.PI * v);
        return mag * Math.sin(2 * Math.PI * v);
    }

    /**
     * 프로파일 분석 정보 가져오기
     */
    getProfileAnalysis() {
        if (!this.poc) return null;
        
        return {
            poc: {
                price: this.poc.mid,
                volume: this.poc.volume,
                percentage: this.getVolumePercentage(this.poc.volume)
            },
            valueArea: this.valueArea,
            highVolumeNodes: this.highVolumeNodes.slice(0, 5).map(node => ({
                price: node.range.mid,
                volume: node.range.volume,
                strength: node.strength
            })),
            lowVolumeNodes: this.lowVolumeNodes.slice(0, 5).map(node => ({
                price: node.range.mid,
                volume: node.range.volume,
                strength: node.strength
            })),
            totalVolume: Array.from(this.volumeProfile.values())
                .reduce((sum, range) => sum + range.volume, 0),
            totalTrades: this.tradeData.length,
            priceRange: {
                min: this.priceRanges[0]?.min || 0,
                max: this.priceRanges[this.priceRanges.length - 1]?.max || 0
            }
        };
    }

    /**
     * 프로파일 설정 업데이트
     */
    updateProfileSettings(settings) {
        if (settings.priceLevels !== undefined) {
            this.priceLevels = settings.priceLevels;
        }
        
        if (settings.profileType !== undefined) {
            this.profileType = settings.profileType;
        }
        
        if (settings.showPOC !== undefined) {
            this.showPOC = settings.showPOC;
        }
        
        if (settings.showValueArea !== undefined) {
            this.showValueArea = settings.showValueArea;
        }
        
        if (settings.showVolumeNodes !== undefined) {
            this.showVolumeNodes = settings.showVolumeNodes;
        }
        
        this.calculateVolumeProfile();
        this.updateChart();
        this.emit('profileSettingsUpdated', settings);
    }

    /**
     * 볼륨 프로파일 데이터 내보내기
     */
    exportVolumeProfile() {
        return {
            timestamp: Date.now(),
            settings: {
                priceLevels: this.priceLevels,
                profileType: this.profileType
            },
            volumeProfile: Array.from(this.volumeProfile.entries()).map(([level, range]) => ({
                level,
                priceRange: { min: range.min, max: range.max, mid: range.mid },
                volume: range.volume,
                trades: range.trades
            })),
            analysis: this.getProfileAnalysis()
        };
    }

    /**
     * 값 포맷
     */
    formatValue(value) {
        return this.formatVolume(value);
    }

    /**
     * 정리
     */
    destroy() {
        this.volumeProfile.clear();
        super.destroy();
    }
}

export default VolumeProfileChart;
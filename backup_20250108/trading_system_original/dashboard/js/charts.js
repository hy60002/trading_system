// 📊 Charts Manager for Dashboard Widgets

class ChartsManager {
    constructor() {
        this.charts = new Map();
        this.sparklineData = [];
        this.maxDataPoints = 48; // 24시간 * 2 (30분 간격)
        this.isInitialized = false;
        
        this.initialize();
    }

    initialize() {
        // 스파크라인 초기 데이터 생성 (데모용)
        this.generateInitialSparklineData();
        this.isInitialized = true;
    }

    generateInitialSparklineData() {
        // 24시간 동안의 가상 손익 데이터 생성
        const now = Date.now();
        const interval = 30 * 60 * 1000; // 30분 간격
        
        this.sparklineData = [];
        let currentValue = 0;
        
        for (let i = 0; i < this.maxDataPoints; i++) {
            const timestamp = now - (this.maxDataPoints - i - 1) * interval;
            // 랜덤 워크 시뮬레이션
            const change = (Math.random() - 0.5) * 100;
            currentValue += change;
            
            this.sparklineData.push({
                timestamp,
                value: currentValue,
                pnl: currentValue
            });
        }
    }

    updateSparkline(newPnlValue) {
        const now = Date.now();
        
        // 새 데이터 포인트 추가
        this.sparklineData.push({
            timestamp: now,
            value: newPnlValue,
            pnl: newPnlValue
        });
        
        // 최대 데이터 포인트 수 유지
        if (this.sparklineData.length > this.maxDataPoints) {
            this.sparklineData.shift();
        }
        
        this.renderSparkline();
        this.updateSparklineStats();
    }

    renderSparkline() {
        const svg = document.getElementById('pnl-sparkline');
        if (!svg) return;

        const width = 300;
        const height = 60;
        const padding = 5;

        // 데이터 범위 계산
        const values = this.sparklineData.map(d => d.value);
        const minValue = Math.min(...values);
        const maxValue = Math.max(...values);
        const valueRange = maxValue - minValue || 1;

        // 스케일 함수
        const xScale = (index) => (index / (this.sparklineData.length - 1)) * width;
        const yScale = (value) => height - padding - ((value - minValue) / valueRange) * (height - 2 * padding);

        // 패스 데이터 생성
        const pathData = this.sparklineData.map((d, i) => {
            const x = xScale(i);
            const y = yScale(d.value);
            return i === 0 ? `M${x},${y}` : `L${x},${y}`;
        }).join(' ');

        // 영역 패스 데이터 생성 (그라데이션 채우기용)
        const areaData = `M0,${height} ${pathData} L${width},${height} Z`;

        // SVG 업데이트
        const pathElement = svg.querySelector('.sparkline-path');
        const areaElement = svg.querySelector('.sparkline-area');

        if (pathElement) {
            pathElement.setAttribute('d', pathData);
            
            // 손익에 따른 색상 변경
            const currentPnl = this.sparklineData[this.sparklineData.length - 1].value;
            const color = currentPnl >= 0 ? 'var(--profit-green)' : 'var(--loss-red)';
            pathElement.style.stroke = color;
        }

        if (areaElement) {
            areaElement.setAttribute('d', areaData);
            
            // 그라데이션 업데이트
            this.updateSparklineGradient(svg, this.sparklineData[this.sparklineData.length - 1].value >= 0);
        }
    }

    updateSparklineGradient(svg, isProfit) {
        const gradient = svg.querySelector('#sparklineGradient');
        if (!gradient) return;

        const color = isProfit ? 'var(--profit-green)' : 'var(--loss-red)';
        const stops = gradient.querySelectorAll('stop');
        
        stops.forEach(stop => {
            stop.style.stopColor = color;
        });
    }

    updateSparklineStats() {
        const changeElement = document.getElementById('sparkline-change');
        if (!changeElement || this.sparklineData.length < 2) return;

        const current = this.sparklineData[this.sparklineData.length - 1].value;
        const previous = this.sparklineData[0].value;
        const change = current - previous;
        const changePercent = previous !== 0 ? (change / Math.abs(previous)) * 100 : 0;

        changeElement.textContent = `${changePercent >= 0 ? '+' : ''}${changePercent.toFixed(1)}%`;
        changeElement.className = changePercent >= 0 ? 'positive' : 'negative';
        changeElement.style.color = changePercent >= 0 ? 'var(--profit-green)' : 'var(--loss-red)';
    }

    // 리스크 미터 업데이트
    updateRiskMeter(riskLevel) {
        const riskArc = document.getElementById('risk-arc-active');
        const riskValue = document.getElementById('risk-percentage');
        
        if (!riskArc || !riskValue) return;

        // 각도 계산 (0-100% -> 0-180도)
        const angle = Math.min(riskLevel, 100) * 1.8; // 180도 범위
        const radians = (angle - 90) * (Math.PI / 180);
        
        // 원호의 끝점 계산
        const centerX = 60;
        const centerY = 50;
        const radius = 40;
        const endX = centerX + radius * Math.cos(radians);
        const endY = centerY + radius * Math.sin(radians);
        
        // 큰 호 플래그 (180도 이상인지)
        const largeArcFlag = angle > 180 ? 1 : 0;
        
        // SVG 패스 업데이트
        const pathData = `M 20 50 A ${radius} ${radius} 0 ${largeArcFlag} 1 ${endX} ${endY}`;
        riskArc.setAttribute('d', pathData);
        
        // 리스크 레벨에 따른 색상 변경
        let color;
        if (riskLevel < 30) {
            color = 'var(--profit-green)';
        } else if (riskLevel < 70) {
            color = 'var(--warning-orange)';
        } else {
            color = 'var(--loss-red)';
        }
        
        riskArc.style.stroke = color;
        riskValue.textContent = `${riskLevel}%`;
        riskValue.style.color = color;
    }

    // AI 신뢰도 바 애니메이션
    animateConfidenceBar(targetValue, duration = 1000) {
        const fillElement = document.getElementById('confidence-fill');
        const valueElement = document.getElementById('confidence-value');
        
        if (!fillElement || !valueElement) return;

        const currentWidth = parseFloat(fillElement.style.width) || 0;
        const startTime = performance.now();
        
        const animate = (currentTime) => {
            const elapsed = currentTime - startTime;
            const progress = Math.min(elapsed / duration, 1);
            
            // 이징 함수 (easeOutCubic)
            const easedProgress = 1 - Math.pow(1 - progress, 3);
            
            const currentValue = currentWidth + (targetValue - currentWidth) * easedProgress;
            
            fillElement.style.width = `${currentValue}%`;
            valueElement.textContent = `${Math.round(currentValue)}%`;
            
            // 신뢰도에 따른 색상 변경
            let color;
            if (currentValue < 30) {
                color = 'var(--loss-red)';
            } else if (currentValue < 70) {
                color = 'var(--warning-orange)';
            } else {
                color = 'var(--profit-green)';
            }
            
            fillElement.style.background = `linear-gradient(90deg, var(--loss-red) 0%, var(--warning-orange) 50%, ${color} 100%)`;
            
            if (progress < 1) {
                requestAnimationFrame(animate);
            }
        };
        
        requestAnimationFrame(animate);
    }

    // 원형 프로그레스 차트 (추가 위젯용)
    createCircularProgress(containerId, value, options = {}) {
        const {
            size = 120,
            strokeWidth = 8,
            color = 'var(--active-blue)',
            backgroundColor = 'var(--border-color)',
            duration = 1000
        } = options;

        const container = document.getElementById(containerId);
        if (!container) return;

        const radius = (size - strokeWidth) / 2;
        const circumference = 2 * Math.PI * radius;
        const center = size / 2;

        const svg = document.createElementNS('http://www.w3.org/2000/svg', 'svg');
        svg.setAttribute('width', size);
        svg.setAttribute('height', size);

        // 배경 원
        const backgroundCircle = document.createElementNS('http://www.w3.org/2000/svg', 'circle');
        backgroundCircle.setAttribute('cx', center);
        backgroundCircle.setAttribute('cy', center);
        backgroundCircle.setAttribute('r', radius);
        backgroundCircle.setAttribute('fill', 'none');
        backgroundCircle.setAttribute('stroke', backgroundColor);
        backgroundCircle.setAttribute('stroke-width', strokeWidth);

        // 진행률 원
        const progressCircle = document.createElementNS('http://www.w3.org/2000/svg', 'circle');
        progressCircle.setAttribute('cx', center);
        progressCircle.setAttribute('cy', center);
        progressCircle.setAttribute('r', radius);
        progressCircle.setAttribute('fill', 'none');
        progressCircle.setAttribute('stroke', color);
        progressCircle.setAttribute('stroke-width', strokeWidth);
        progressCircle.setAttribute('stroke-linecap', 'round');
        progressCircle.setAttribute('stroke-dasharray', circumference);
        progressCircle.setAttribute('stroke-dashoffset', circumference);
        progressCircle.style.transform = 'rotate(-90deg)';
        progressCircle.style.transformOrigin = 'center';

        svg.appendChild(backgroundCircle);
        svg.appendChild(progressCircle);
        container.appendChild(svg);

        // 애니메이션
        const targetOffset = circumference - (value / 100) * circumference;
        this.animateStrokeDashoffset(progressCircle, circumference, targetOffset, duration);

        return { svg, progressCircle };
    }

    animateStrokeDashoffset(element, fromValue, toValue, duration) {
        const startTime = performance.now();
        
        const animate = (currentTime) => {
            const elapsed = currentTime - startTime;
            const progress = Math.min(elapsed / duration, 1);
            
            // 이징 함수
            const easedProgress = 1 - Math.pow(1 - progress, 3);
            const currentValue = fromValue + (toValue - fromValue) * easedProgress;
            
            element.setAttribute('stroke-dashoffset', currentValue);
            
            if (progress < 1) {
                requestAnimationFrame(animate);
            }
        };
        
        requestAnimationFrame(animate);
    }

    // 미니 도넛 차트 (포트폴리오 분배용)
    createDonutChart(containerId, data, options = {}) {
        const {
            size = 100,
            innerRadius = 30,
            outerRadius = 45,
            colors = ['var(--profit-green)', 'var(--active-blue)', 'var(--warning-orange)']
        } = options;

        const container = document.getElementById(containerId);
        if (!container) return;

        const total = data.reduce((sum, item) => sum + item.value, 0);
        let currentAngle = 0;

        const svg = document.createElementNS('http://www.w3.org/2000/svg', 'svg');
        svg.setAttribute('width', size);
        svg.setAttribute('height', size);
        svg.setAttribute('viewBox', `0 0 ${size} ${size}`);

        const center = size / 2;

        data.forEach((item, index) => {
            const percentage = item.value / total;
            const angle = percentage * 2 * Math.PI;
            
            if (percentage > 0) {
                const path = this.createArcPath(
                    center, center,
                    innerRadius, outerRadius,
                    currentAngle, currentAngle + angle
                );

                const pathElement = document.createElementNS('http://www.w3.org/2000/svg', 'path');
                pathElement.setAttribute('d', path);
                pathElement.setAttribute('fill', colors[index % colors.length]);
                pathElement.setAttribute('opacity', '0.8');
                
                // 호버 효과
                pathElement.addEventListener('mouseenter', () => {
                    pathElement.setAttribute('opacity', '1');
                    pathElement.style.transform = 'scale(1.05)';
                    pathElement.style.transformOrigin = 'center';
                });
                
                pathElement.addEventListener('mouseleave', () => {
                    pathElement.setAttribute('opacity', '0.8');
                    pathElement.style.transform = 'scale(1)';
                });

                svg.appendChild(pathElement);
            }
            
            currentAngle += angle;
        });

        container.appendChild(svg);
        return svg;
    }

    createArcPath(cx, cy, innerRadius, outerRadius, startAngle, endAngle) {
        const x1 = cx + Math.cos(startAngle) * outerRadius;
        const y1 = cy + Math.sin(startAngle) * outerRadius;
        const x2 = cx + Math.cos(endAngle) * outerRadius;
        const y2 = cy + Math.sin(endAngle) * outerRadius;
        const x3 = cx + Math.cos(endAngle) * innerRadius;
        const y3 = cy + Math.sin(endAngle) * innerRadius;
        const x4 = cx + Math.cos(startAngle) * innerRadius;
        const y4 = cy + Math.sin(startAngle) * innerRadius;

        const largeArcFlag = endAngle - startAngle <= Math.PI ? 0 : 1;

        return `M ${x1} ${y1} A ${outerRadius} ${outerRadius} 0 ${largeArcFlag} 1 ${x2} ${y2} L ${x3} ${y3} A ${innerRadius} ${innerRadius} 0 ${largeArcFlag} 0 ${x4} ${y4} Z`;
    }

    // 차트 데이터 업데이트 (외부에서 호출)
    updateChartData(type, data) {
        switch (type) {
            case 'sparkline':
                this.updateSparkline(data.value);
                break;
            case 'risk':
                this.updateRiskMeter(data.level);
                break;
            case 'confidence':
                this.animateConfidenceBar(data.value);
                break;
        }
    }

    // 모든 차트 초기화
    initializeAllCharts() {
        if (!this.isInitialized) {
            this.initialize();
        }
        
        this.renderSparkline();
        this.updateRiskMeter(25); // 초기 리스크 레벨
        this.animateConfidenceBar(75); // 초기 AI 신뢰도
    }

    // 차트 리사이즈 처리
    handleResize() {
        // 반응형 차트 크기 조정
        this.renderSparkline();
    }

    // 차트 테마 변경
    updateChartsTheme(theme) {
        // 테마에 따른 차트 색상 업데이트
        this.renderSparkline();
        // 기타 차트들도 테마에 맞게 업데이트
    }
}

// 전역 차트 매니저 인스턴스
let chartsManager;

function initializeCharts() {
    chartsManager = new ChartsManager();
    chartsManager.initializeAllCharts();
    
    // 창 크기 변경 시 차트 리사이즈
    window.addEventListener('resize', () => {
        chartsManager.handleResize();
    });
}

// 차트 업데이트 함수들 (외부에서 호출 가능)
function updateSparklineChart(value) {
    if (chartsManager) {
        chartsManager.updateSparkline(value);
    }
}

function updateRiskMeterChart(level) {
    if (chartsManager) {
        chartsManager.updateRiskMeter(level);
    }
}

function updateConfidenceChart(value) {
    if (chartsManager) {
        chartsManager.animateConfidenceBar(value);
    }
}
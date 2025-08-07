"""
Performance Analyzer
Real-time performance analysis and reporting with advanced metrics
"""

import logging
import numpy as np
from collections import defaultdict
from datetime import datetime
from typing import Dict, List
from cachetools import TTLCache

# Import handling for both direct and package imports
try:
    from ..database.db_manager import EnhancedDatabaseManager
except ImportError:
    import sys
    import os
    sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    from database.db_manager import EnhancedDatabaseManager


class PerformanceAnalyzer:
    """Real-time performance analysis and reporting with advanced metrics"""
    
    def __init__(self, db: EnhancedDatabaseManager):
        self.db = db
        self.logger = logging.getLogger(__name__)
        self._performance_cache = TTLCache(maxsize=100, ttl=300)
    
    async def update_daily_performance(self):
        """Update daily performance metrics with comprehensive calculations"""
        today = datetime.now().strftime('%Y-%m-%d')
        
        # Get all trades from today
        with self.db._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                SELECT * FROM trades 
                WHERE DATE(timestamp) = ? AND status = 'closed'
            """, (today,))
            
            trades = [dict(row) for row in cursor.fetchall()]
        
        if not trades:
            # Still update with zeros - 안전한 호출
            try:
                if hasattr(self.db, 'update_daily_performance'):
                    self.db.update_daily_performance(today, self._get_empty_metrics())
                else:
                    self.logger.warning("update_daily_performance 메서드 없음 - 건너뜀")
            except Exception as e:
                self.logger.error(f"일일 성과 업데이트 실패: {e}")
            return
        
        # Calculate comprehensive metrics
        metrics = self._calculate_comprehensive_metrics(trades)
        
        # Update database - 안전한 호출
        try:
            if hasattr(self.db, 'update_daily_performance'):
                self.db.update_daily_performance(today, metrics)
            else:
                self.logger.warning("update_daily_performance 메서드 없음 - 건너뜀")
        except Exception as e:
            self.logger.error(f"일일 성과 업데이트 실패: {e}")
        
        # Clear cache
        self._performance_cache.clear()
    
    def _calculate_comprehensive_metrics(self, trades: List[Dict]) -> Dict:
        """Calculate comprehensive performance metrics"""
        metrics = {
            'total_trades': len(trades),
            'winning_trades': sum(1 for t in trades if t['pnl'] > 0),
            'losing_trades': sum(1 for t in trades if t['pnl'] < 0),
            'total_pnl': sum(t['pnl'] for t in trades),
            'total_pnl_percent': sum(t['pnl_percent'] for t in trades) / 100,  # Convert from percentage
            'total_fees': sum(t.get('fees_paid', 0) for t in trades),
            'total_volume': sum(t['quantity'] * t['price'] for t in trades)
        }
        
        # P&L by symbol
        for symbol in ['BTCUSDT', 'ETHUSDT', 'XRPUSDT']:
            symbol_trades = [t for t in trades if t['symbol'] == symbol]
            symbol_key = f"{symbol[:3].lower()}_pnl"
            metrics[symbol_key] = sum(t['pnl'] for t in symbol_trades)
        
        # Win rate
        if metrics['total_trades'] > 0:
            metrics['win_rate'] = metrics['winning_trades'] / metrics['total_trades']
        else:
            metrics['win_rate'] = 0
        
        # Average win/loss
        winning_pnls = [t['pnl_percent'] / 100 for t in trades if t['pnl'] > 0]
        losing_pnls = [t['pnl_percent'] / 100 for t in trades if t['pnl'] < 0]
        
        metrics['avg_win'] = np.mean(winning_pnls) if winning_pnls else 0
        metrics['avg_loss'] = np.mean(losing_pnls) if losing_pnls else 0
        
        # Best/worst trade
        if trades:
            metrics['best_trade'] = max(t['pnl_percent'] / 100 for t in trades)
            metrics['worst_trade'] = min(t['pnl_percent'] / 100 for t in trades)
        else:
            metrics['best_trade'] = 0
            metrics['worst_trade'] = 0
        
        # Calculate Sharpe ratio
        metrics['sharpe_ratio'] = self._calculate_sharpe_ratio(trades)
        
        # Calculate max drawdown
        metrics['max_drawdown'] = self._calculate_max_drawdown(trades)
        
        # Calculate average Kelly fraction used
        kelly_fractions = [t.get('kelly_fraction', 0) for t in trades if t.get('kelly_fraction')]
        metrics['kelly_fraction'] = np.mean(kelly_fractions) if kelly_fractions else 0
        
        return metrics
    
    def _calculate_sharpe_ratio(self, trades: List[Dict]) -> float:
        """Calculate Sharpe ratio"""
        if len(trades) < 2:
            return 0
        
        returns = [t['pnl_percent'] / 100 for t in trades]
        
        if not returns or np.std(returns) == 0:
            return 0
        
        # Annualized Sharpe ratio (assuming ~20 trades per day, 252 trading days)
        daily_return = np.mean(returns)
        daily_std = np.std(returns)
        
        if daily_std == 0:
            return 0
        
        # Risk-free rate (assuming 0 for crypto)
        sharpe = (daily_return / daily_std) * np.sqrt(252)
        
        return round(sharpe, 2)
    
    def _calculate_max_drawdown(self, trades: List[Dict]) -> float:
        """Calculate maximum drawdown"""
        if not trades:
            return 0
        
        # Calculate cumulative returns
        cumulative_pnl = 0
        peak = 0
        max_dd = 0
        
        for trade in sorted(trades, key=lambda x: x['timestamp']):
            cumulative_pnl += trade['pnl']
            
            if cumulative_pnl > peak:
                peak = cumulative_pnl
            
            drawdown = (peak - cumulative_pnl) / peak if peak > 0 else 0
            max_dd = max(max_dd, drawdown)
        
        return round(max_dd, 4)
    
    def _get_empty_metrics(self) -> Dict:
        """Get empty metrics structure"""
        return {
            'total_trades': 0,
            'winning_trades': 0,
            'losing_trades': 0,
            'total_pnl': 0.0,
            'total_pnl_percent': 0.0,
            'btc_pnl': 0.0,
            'eth_pnl': 0.0,
            'xrp_pnl': 0.0,
            'max_drawdown': 0.0,
            'sharpe_ratio': 0.0,
            'win_rate': 0.0,
            'avg_win': 0.0,
            'avg_loss': 0.0,
            'best_trade': 0.0,
            'worst_trade': 0.0,
            'total_volume': 0.0,
            'total_fees': 0.0,
            'kelly_fraction': 0.0
        }
    
    def generate_performance_report(self, days: int = 7) -> str:
        """Generate comprehensive performance report in Korean"""
        # Check cache first
        cache_key = f"report_{days}"
        cached_report = self._performance_cache.get(cache_key)
        if cached_report:
            return cached_report
        
        # Get performance data
        with self.db._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                SELECT * FROM daily_performance 
                WHERE date >= date('now', '-{} days')
                ORDER BY date DESC
            """.format(days))
            
            daily_data = [dict(row) for row in cursor.fetchall()]
        
        if not daily_data:
            return "해당 기간의 거래 데이터가 없습니다."
        
        # Get recent trades for additional insights
        cursor.execute("""
            SELECT * FROM trades 
            WHERE timestamp >= datetime('now', '-{} days')
            AND status = 'closed'
            ORDER BY timestamp DESC
        """.format(days))
        
        recent_trades = [dict(row) for row in cursor.fetchall()]
        
        # Aggregate metrics
        total_trades = sum(d['total_trades'] for d in daily_data)
        total_pnl = sum(d['total_pnl'] for d in daily_data)
        total_pnl_pct = sum(d['total_pnl_percent'] for d in daily_data)
        total_fees = sum(d.get('total_fees', 0) for d in daily_data)
        
        # Calculate strategy performance
        strategy_performance = self._calculate_strategy_performance(recent_trades)
        
        # Generate report
        report = f"""
📊 거래 성과 보고서 - 최근 {days}일
📅 {datetime.now().strftime('%Y-%m-%d %H:%M')} KST

📈 요약

총 거래 횟수: {total_trades}회
총 손익: ${total_pnl:,.2f} ({total_pnl_pct:+.2f}%)
총 수수료: ${total_fees:,.2f}
순 손익: ${total_pnl - total_fees:,.2f}
일평균 손익: ${total_pnl/days:,.2f}

💎 코인별 성과

비트코인(BTC): ${sum(d['btc_pnl'] for d in daily_data):,.2f}
이더리움(ETH): ${sum(d['eth_pnl'] for d in daily_data):,.2f}
리플(XRP): ${sum(d['xrp_pnl'] for d in daily_data):,.2f}

📊 통계

승률: {np.mean([d['win_rate'] for d in daily_data if d['total_trades'] > 0]):.1%}
평균 수익: {np.mean([d['avg_win'] for d in daily_data if d['avg_win'] > 0]):+.2f}%
평균 손실: {np.mean([d['avg_loss'] for d in daily_data if d['avg_loss'] < 0]):+.2f}%
최고 일일 수익: {max(d['total_pnl_percent'] for d in daily_data):+.2f}%
최악 일일 손실: {min(d['total_pnl_percent'] for d in daily_data):+.2f}%
최대 낙폭: {max(d['max_drawdown'] for d in daily_data):.2%}
샤프 비율: {np.mean([d['sharpe_ratio'] for d in daily_data if d['sharpe_ratio'] != 0]):.2f}
평균 Kelly 지수: {np.mean([d['kelly_fraction'] for d in daily_data if d['kelly_fraction'] > 0]):.3f}

🎯 전략별 성과
{strategy_performance}

📅 일별 상세 내역
"""
        
        # Add daily breakdown
        for day_data in daily_data[:7]:  # Last 7 days
            date = day_data['date']
            daily_pnl = day_data['total_pnl_percent']
            trades = day_data['total_trades']
            win_rate = day_data['win_rate']
            
            emoji = '🟢' if daily_pnl > 0 else '🔴' if daily_pnl < 0 else '⚪'
            report += f"\n{emoji} {date}: {daily_pnl:+.2f}% ({trades}회 거래, 승률 {win_rate:.0%})"
        
        # Cache the report
        self._performance_cache[cache_key] = report
        
        return report
    
    def _calculate_strategy_performance(self, trades: List[Dict]) -> str:
        """Calculate performance by strategy/regime"""
        if not trades:
            return "거래 데이터가 없습니다"
        
        # Group by regime
        regime_performance = defaultdict(lambda: {'count': 0, 'pnl': 0})
        
        for trade in trades:
            regime = trade.get('regime', 'unknown')
            regime_performance[regime]['count'] += 1
            regime_performance[regime]['pnl'] += trade['pnl_percent'] / 100
        
        # Format results with Korean translations
        regime_translations = {
            'trending_up': '상승 추세',
            'trending_down': '하락 추세', 
            'ranging': '횡보',
            'volatile': '변동성 높음',
            'bullish': '강세',
            'bearish': '약세',
            'unknown': '미분류'
        }
        
        results = []
        for regime, data in regime_performance.items():
            avg_pnl = data['pnl'] / data['count'] if data['count'] > 0 else 0
            regime_kr = regime_translations.get(regime, regime)
            results.append(f"• {regime_kr}: 평균 {avg_pnl:+.2f}% ({data['count']}회 거래)")
        
        return '\n'.join(results) if results else "전략 데이터가 없습니다"
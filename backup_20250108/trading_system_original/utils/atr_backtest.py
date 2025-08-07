"""
ATR 기반 손절/익절 백테스팅 시스템
고정 % vs ATR 기반 시스템 성과 비교
"""

import pandas as pd
import numpy as np
from typing import Dict, List, Tuple
import logging
from datetime import datetime, timedelta

try:
    from ..utils.atr_calculator import ATRCalculator
    from ..config.config import TradingConfig
except ImportError:
    import sys
    import os
    sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    from utils.atr_calculator import ATRCalculator
    from config.config import TradingConfig


class ATRBacktester:
    """ATR 기반 vs 고정 % 손절/익절 백테스트"""
    
    def __init__(self, config: TradingConfig):
        self.config = config
        self.logger = logging.getLogger(__name__)
        self.atr_calculator = ATRCalculator(config)
        
    def backtest_atr_stops(self, historical_data: pd.DataFrame, symbol: str = 'BTCUSDT') -> Dict[str, Dict]:
        """
        ATR 기반 vs 고정 손절/익절 백테스트
        
        Args:
            historical_data: OHLCV 데이터
            symbol: 백테스트할 심볼
            
        Returns:
            Dict: 비교 결과
        """
        try:
            self.logger.info(f"🔍 {symbol} ATR vs 고정 손절/익절 백테스트 시작")
            
            if len(historical_data) < 100:
                return {'error': 'Insufficient data for backtesting'}
            
            # 백테스트 설정
            initial_capital = 10000
            leverage = self.config.LEVERAGE.get(symbol, 20)
            
            # 시나리오 1: 고정 손절/익절 (레거시)
            fixed_results = self._backtest_fixed_stops(
                historical_data, symbol, initial_capital, leverage
            )
            
            # 시나리오 2: ATR 기반 손절/익절
            atr_results = self._backtest_atr_stops(
                historical_data, symbol, initial_capital, leverage
            )
            
            # 결과 비교
            comparison = self._compare_results(fixed_results, atr_results)
            
            self.logger.info(f"✅ {symbol} 백테스트 완료")
            
            return {
                'symbol': symbol,
                'data_period': f"{historical_data.index[0]} ~ {historical_data.index[-1]}",
                'total_trades': len(fixed_results['trades']),
                'fixed_stops': fixed_results['summary'],
                'atr_stops': atr_results['summary'],
                'comparison': comparison,
                'recommendation': self._get_recommendation(comparison)
            }
            
        except Exception as e:
            self.logger.error(f"백테스트 오류: {e}")
            return {'error': str(e)}
    
    def _backtest_fixed_stops(self, data: pd.DataFrame, symbol: str, 
                            initial_capital: float, leverage: int) -> Dict:
        """고정 % 손절/익절 백테스트"""
        try:
            # 레거시 고정 설정
            stop_loss_pct = 0.05  # 5%
            take_profit_pct = 0.10  # 10%
            
            trades = []
            capital = initial_capital
            position = None
            
            for i in range(50, len(data)):
                current_price = data.iloc[i]['close']
                
                # 매수 신호 생성 (단순 RSI 기반)
                if position is None and self._generate_entry_signal(data.iloc[i-20:i]):
                    # 포지션 오픈
                    position = {
                        'entry_price': current_price,
                        'entry_time': data.index[i],
                        'side': 'long',
                        'stop_loss': current_price * (1 - stop_loss_pct),
                        'take_profit': current_price * (1 + take_profit_pct),
                        'quantity': (capital * 0.1) * leverage / current_price  # 10% 자본 사용
                    }
                
                # 포지션 관리
                elif position is not None:
                    exit_reason = None
                    exit_price = None
                    
                    # 손절 체크
                    if current_price <= position['stop_loss']:
                        exit_reason = 'stop_loss'
                        exit_price = position['stop_loss']
                    
                    # 익절 체크
                    elif current_price >= position['take_profit']:
                        exit_reason = 'take_profit'
                        exit_price = position['take_profit']
                    
                    # 포지션 종료
                    if exit_reason:
                        pnl = (exit_price - position['entry_price']) * position['quantity']
                        pnl_pct = pnl / (capital * 0.1)
                        
                        trades.append({
                            'entry_time': position['entry_time'],
                            'exit_time': data.index[i],
                            'entry_price': position['entry_price'],
                            'exit_price': exit_price,
                            'pnl': pnl,
                            'pnl_pct': pnl_pct,
                            'exit_reason': exit_reason,
                            'hold_days': (data.index[i] - position['entry_time']).days
                        })
                        
                        capital += pnl
                        position = None
            
            # 결과 요약
            summary = self._calculate_summary(trades, initial_capital, capital)
            
            return {
                'trades': trades,
                'summary': summary
            }
            
        except Exception as e:
            self.logger.error(f"고정 손절 백테스트 오류: {e}")
            return {'trades': [], 'summary': {}}
    
    def _backtest_atr_stops(self, data: pd.DataFrame, symbol: str,
                          initial_capital: float, leverage: int) -> Dict:
        """ATR 기반 손절/익절 백테스트"""
        try:
            atr_settings = self.config.ATR_SETTINGS[symbol]
            
            trades = []
            capital = initial_capital
            position = None
            
            for i in range(50, len(data)):
                current_price = data.iloc[i]['close']
                
                # 매수 신호 생성
                if position is None and self._generate_entry_signal(data.iloc[i-20:i]):
                    # ATR 계산
                    candles = self._df_to_candles(data.iloc[i-20:i])
                    current_atr = self.atr_calculator.calculate_atr(candles, atr_settings['period'])
                    
                    if current_atr > 0:
                        # ATR 기반 손절/익절 계산
                        stops = self.atr_calculator.calculate_dynamic_stops(
                            symbol, current_price, current_atr, 'long'
                        )
                        
                        position = {
                            'entry_price': current_price,
                            'entry_time': data.index[i],
                            'side': 'long',
                            'stop_loss': stops['stop_loss'],
                            'take_profit': stops['take_profit'],
                            'quantity': (capital * 0.1) * leverage / current_price,
                            'atr_value': current_atr
                        }
                
                # 포지션 관리
                elif position is not None:
                    exit_reason = None
                    exit_price = None
                    
                    # 손절 체크
                    if current_price <= position['stop_loss']:
                        exit_reason = 'atr_stop_loss'
                        exit_price = position['stop_loss']
                    
                    # 익절 체크
                    elif current_price >= position['take_profit']:
                        exit_reason = 'atr_take_profit'
                        exit_price = position['take_profit']
                    
                    # 포지션 종료
                    if exit_reason:
                        pnl = (exit_price - position['entry_price']) * position['quantity']
                        pnl_pct = pnl / (capital * 0.1)
                        
                        trades.append({
                            'entry_time': position['entry_time'],
                            'exit_time': data.index[i],
                            'entry_price': position['entry_price'],
                            'exit_price': exit_price,
                            'pnl': pnl,
                            'pnl_pct': pnl_pct,
                            'exit_reason': exit_reason,
                            'hold_days': (data.index[i] - position['entry_time']).days,
                            'atr_value': position['atr_value']
                        })
                        
                        capital += pnl
                        position = None
            
            # 결과 요약
            summary = self._calculate_summary(trades, initial_capital, capital)
            
            return {
                'trades': trades,
                'summary': summary
            }
            
        except Exception as e:
            self.logger.error(f"ATR 손절 백테스트 오류: {e}")
            return {'trades': [], 'summary': {}}
    
    def _generate_entry_signal(self, recent_data: pd.DataFrame) -> bool:
        """단순 RSI 기반 매수 신호"""
        try:
            if len(recent_data) < 14:
                return False
                
            # RSI 계산
            delta = recent_data['close'].diff()
            gain = (delta.where(delta > 0, 0)).rolling(window=14).mean()
            loss = (-delta.where(delta < 0, 0)).rolling(window=14).mean()
            rs = gain / loss
            rsi = 100 - (100 / (1 + rs))
            
            # RSI < 30에서 매수 신호
            return rsi.iloc[-1] < 30
            
        except Exception:
            return False
    
    def _df_to_candles(self, df: pd.DataFrame) -> List[Dict]:
        """DataFrame을 캔들 리스트로 변환"""
        candles = []
        for _, row in df.iterrows():
            candles.append({
                'open': float(row['open']),
                'high': float(row['high']),
                'low': float(row['low']),
                'close': float(row['close']),
                'volume': float(row.get('volume', 0))
            })
        return candles
    
    def _calculate_summary(self, trades: List[Dict], initial_capital: float, 
                          final_capital: float) -> Dict:
        """거래 결과 요약 계산"""
        if not trades:
            return {
                'total_trades': 0,
                'win_rate': 0.0,
                'avg_profit': 0.0,
                'max_drawdown': 0.0,
                'sharpe_ratio': 0.0,
                'total_return': 0.0
            }
        
        # 기본 통계
        total_trades = len(trades)
        winning_trades = [t for t in trades if t['pnl'] > 0]
        losing_trades = [t for t in trades if t['pnl'] <= 0]
        
        win_rate = len(winning_trades) / total_trades if total_trades > 0 else 0
        avg_profit = np.mean([t['pnl_pct'] for t in trades])
        
        # 최대 낙폭 계산
        capital_curve = [initial_capital]
        for trade in trades:
            capital_curve.append(capital_curve[-1] + trade['pnl'])
        
        running_max = np.maximum.accumulate(capital_curve)
        drawdowns = (running_max - capital_curve) / running_max
        max_drawdown = np.max(drawdowns)
        
        # 샤프 비율 (간단 계산)
        returns = [t['pnl_pct'] for t in trades]
        sharpe_ratio = (np.mean(returns) / np.std(returns)) if np.std(returns) > 0 else 0
        
        total_return = (final_capital - initial_capital) / initial_capital
        
        return {
            'total_trades': total_trades,
            'winning_trades': len(winning_trades),
            'losing_trades': len(losing_trades),
            'win_rate': win_rate,
            'avg_profit': avg_profit,
            'avg_win': np.mean([t['pnl_pct'] for t in winning_trades]) if winning_trades else 0,
            'avg_loss': np.mean([t['pnl_pct'] for t in losing_trades]) if losing_trades else 0,
            'max_drawdown': max_drawdown,
            'sharpe_ratio': sharpe_ratio,
            'total_return': total_return,
            'avg_hold_days': np.mean([t['hold_days'] for t in trades])
        }
    
    def _compare_results(self, fixed_results: Dict, atr_results: Dict) -> Dict:
        """결과 비교 분석"""
        fixed_summary = fixed_results['summary']
        atr_summary = atr_results['summary']
        
        return {
            'win_rate_improvement': atr_summary['win_rate'] - fixed_summary['win_rate'],
            'return_improvement': atr_summary['total_return'] - fixed_summary['total_return'],
            'drawdown_improvement': fixed_summary['max_drawdown'] - atr_summary['max_drawdown'],
            'sharpe_improvement': atr_summary['sharpe_ratio'] - fixed_summary['sharpe_ratio'],
            'avg_hold_change': atr_summary['avg_hold_days'] - fixed_summary['avg_hold_days'],
            'trade_count_change': atr_summary['total_trades'] - fixed_summary['total_trades']
        }
    
    def _get_recommendation(self, comparison: Dict) -> str:
        """백테스트 결과 기반 추천"""
        score = 0
        
        # 승률 개선
        if comparison['win_rate_improvement'] > 0.05:
            score += 2
        elif comparison['win_rate_improvement'] > 0:
            score += 1
        
        # 수익률 개선
        if comparison['return_improvement'] > 0.1:
            score += 2
        elif comparison['return_improvement'] > 0:
            score += 1
        
        # 낙폭 개선
        if comparison['drawdown_improvement'] > 0.05:
            score += 2
        elif comparison['drawdown_improvement'] > 0:
            score += 1
        
        # 샤프 비율 개선
        if comparison['sharpe_improvement'] > 0.2:
            score += 1
        
        if score >= 5:
            return "🟢 ATR 기반 시스템 강력 추천 - 모든 지표에서 우수한 성과"
        elif score >= 3:
            return "🟡 ATR 기반 시스템 추천 - 대부분 지표에서 개선"
        elif score >= 1:
            return "🟠 ATR 기반 시스템 조건부 추천 - 일부 개선 확인"
        else:
            return "🔴 고정 손절 시스템 유지 추천 - ATR 시스템 추가 최적화 필요"


def run_atr_backtest(historical_data: pd.DataFrame, config: TradingConfig, 
                    symbol: str = 'BTCUSDT') -> Dict:
    """ATR 백테스트 실행 래퍼"""
    backtester = ATRBacktester(config)
    return backtester.backtest_atr_stops(historical_data, symbol)
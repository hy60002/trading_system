"""
ATR(Average True Range) 기반 동적 손절/익절 계산기
시장 변동성에 적응하는 유연한 리스크 관리 시스템
"""

import numpy as np
import pandas as pd
from typing import Dict, List, Tuple, Optional
import logging


class ATRCalculator:
    """ATR 기반 동적 손절/익절 계산 클래스"""
    
    def __init__(self, config):
        self.config = config
        self.logger = logging.getLogger(__name__)
        
    def calculate_atr(self, candles: List[Dict], period: int = 14) -> float:
        """
        ATR(Average True Range) 계산
        
        Args:
            candles: OHLCV 캔들 데이터 리스트
            period: ATR 계산 기간 (기본 14)
            
        Returns:
            float: ATR 값
        """
        try:
            if len(candles) < period + 1:
                self.logger.warning(f"캔들 데이터 부족: {len(candles)} < {period + 1}")
                return 0.0
            
            # DataFrame으로 변환
            df = pd.DataFrame(candles)
            if df.empty:
                return 0.0
                
            # OHLC 컬럼 확인 및 변환
            required_cols = ['high', 'low', 'close']
            for col in required_cols:
                if col not in df.columns:
                    self.logger.error(f"필수 컬럼 누락: {col}")
                    return 0.0
                df[col] = pd.to_numeric(df[col], errors='coerce')
            
            # True Range 계산
            df['prev_close'] = df['close'].shift(1)
            
            # TR = max(high-low, abs(high-prev_close), abs(low-prev_close))
            df['tr1'] = df['high'] - df['low']
            df['tr2'] = abs(df['high'] - df['prev_close'])
            df['tr3'] = abs(df['low'] - df['prev_close'])
            
            df['true_range'] = df[['tr1', 'tr2', 'tr3']].max(axis=1)
            
            # ATR 계산 (Simple Moving Average)
            atr_values = df['true_range'].rolling(window=period, min_periods=period).mean()
            
            # 최신 ATR 값 반환
            latest_atr = atr_values.iloc[-1]
            
            if pd.isna(latest_atr) or latest_atr <= 0:
                # 폴백: 최근 20개 캔들의 평균 변동폭 사용
                recent_ranges = df['true_range'].tail(20).mean()
                latest_atr = recent_ranges if not pd.isna(recent_ranges) else 0.0
            
            self.logger.debug(f"ATR 계산 완료: {latest_atr:.6f}")
            return float(latest_atr)
            
        except Exception as e:
            self.logger.error(f"ATR 계산 오류: {e}")
            return 0.0
    
    def calculate_dynamic_stops(self, symbol: str, entry_price: float, 
                               current_atr: float, position_side: str) -> Dict[str, float]:
        """
        동적 손절/익절 가격 계산
        
        Args:
            symbol: 거래 심볼
            entry_price: 진입 가격
            current_atr: 현재 ATR 값
            position_side: 포지션 방향 ('long' or 'short')
            
        Returns:
            Dict: {
                'stop_loss': float,
                'take_profit': float,
                'stop_distance_pct': float,
                'profit_distance_pct': float,
                'atr_value': float
            }
        """
        try:
            if symbol not in self.config.ATR_SETTINGS:
                raise ValueError(f"ATR 설정이 없는 심볼: {symbol}")
                
            settings = self.config.ATR_SETTINGS[symbol]
            leverage = self.config.LEVERAGE.get(symbol, 10)
            
            # ATR 기반 거리 계산
            raw_stop_distance = current_atr * settings['stop_multiplier']
            raw_profit_distance = current_atr * settings['profit_multiplier']
            
            # 최소/최대 제한 적용
            min_stop = entry_price * settings['min_stop_distance']
            max_stop = entry_price * settings['max_stop_distance']
            
            # 손절 거리 제한
            stop_distance = max(min_stop, min(raw_stop_distance, max_stop))
            
            # 레버리지 고려한 조정 (레버리지가 높을수록 더 타이트하게)
            leverage_factor = min(1.0, 10.0 / leverage)  # 레버리지 10배 기준으로 정규화
            adjusted_stop_distance = stop_distance * leverage_factor
            
            # 익절 거리는 레버리지 영향 최소화
            profit_distance = raw_profit_distance
            
            # 포지션 방향에 따른 손절/익절 계산
            if position_side.lower() in ['long', 'buy']:
                stop_loss = entry_price - adjusted_stop_distance
                take_profit = entry_price + profit_distance
            else:  # short, sell
                stop_loss = entry_price + adjusted_stop_distance
                take_profit = entry_price - profit_distance
            
            # 퍼센트 거리 계산
            stop_distance_pct = (adjusted_stop_distance / entry_price) * 100
            profit_distance_pct = (profit_distance / entry_price) * 100
            
            result = {
                'stop_loss': round(stop_loss, 8),
                'take_profit': round(take_profit, 8),
                'stop_distance_pct': round(stop_distance_pct, 3),
                'profit_distance_pct': round(profit_distance_pct, 3),
                'atr_value': round(current_atr, 8)
            }
            
            self.logger.info(
                f"💎 {symbol} ATR 동적 손절/익절 계산:\n"
                f"   ATR: ${current_atr:.6f}\n"
                f"   레버리지: {leverage}x (조정계수: {leverage_factor:.2f})\n"
                f"   손절가: ${stop_loss:.6f} ({stop_distance_pct:.2f}%)\n"
                f"   익절가: ${take_profit:.6f} ({profit_distance_pct:.2f}%)\n"
                f"   R:R 비율: 1:{profit_distance_pct/stop_distance_pct:.1f}"
            )
            
            return result
            
        except Exception as e:
            self.logger.error(f"동적 손절/익절 계산 오류: {e}")
            # 폴백: 보수적 고정값 반환
            return self._get_fallback_stops(entry_price, position_side, symbol)
    
    def _get_fallback_stops(self, entry_price: float, position_side: str, symbol: str) -> Dict[str, float]:
        """ATR 계산 실패 시 폴백 손절/익절"""
        leverage = self.config.LEVERAGE.get(symbol, 10)
        
        # 레버리지 고려한 보수적 손절 (최대 2% 가격 변동)
        fallback_stop_pct = min(0.02, 0.20 / leverage)  # 20% 손실 제한
        fallback_profit_pct = fallback_stop_pct * 2  # 1:2 R:R
        
        if position_side.lower() in ['long', 'buy']:
            stop_loss = entry_price * (1 - fallback_stop_pct)
            take_profit = entry_price * (1 + fallback_profit_pct)
        else:
            stop_loss = entry_price * (1 + fallback_stop_pct)
            take_profit = entry_price * (1 - fallback_profit_pct)
        
        self.logger.warning(
            f"⚠️ {symbol} ATR 폴백 모드: "
            f"손절 {fallback_stop_pct:.1%}, 익절 {fallback_profit_pct:.1%}"
        )
        
        return {
            'stop_loss': round(stop_loss, 8),
            'take_profit': round(take_profit, 8),
            'stop_distance_pct': round(fallback_stop_pct * 100, 3),
            'profit_distance_pct': round(fallback_profit_pct * 100, 3),
            'atr_value': 0.0
        }
    
    def validate_atr_quality(self, atr_value: float, recent_candles: List[Dict]) -> bool:
        """ATR 품질 검증"""
        try:
            if atr_value <= 0:
                return False
                
            # 최근 평균 변동폭과 비교
            if len(recent_candles) >= 5:
                df = pd.DataFrame(recent_candles[-5:])
                avg_range = ((df['high'] - df['low']) / df['close']).mean()
                atr_ratio = atr_value / df['close'].iloc[-1]
                
                # ATR이 최근 평균 변동의 0.5~3배 범위 내인지 확인
                if not (0.5 * avg_range <= atr_ratio <= 3.0 * avg_range):
                    self.logger.warning(f"ATR 품질 의심: {atr_ratio:.4f} vs 평균 {avg_range:.4f}")
                    return False
            
            return True
            
        except Exception:
            return False
    
    def calculate_optimal_multipliers(self, symbol: str, historical_data: pd.DataFrame) -> Dict[str, float]:
        """
        역사적 데이터 기반 최적 ATR 배수 계산
        (백테스팅용 - 추후 구현)
        """
        # TODO: 백테스팅을 통한 최적 배수 도출
        settings = self.config.ATR_SETTINGS.get(symbol, {})
        return {
            'stop_multiplier': settings.get('stop_multiplier', 2.0),
            'profit_multiplier': settings.get('profit_multiplier', 3.0)
        }
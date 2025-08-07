"""
Balance Safe Handler
잔고 데이터 안전 처리 및 재시도 로직
"""

import asyncio
import logging
from typing import Dict, Any, Optional, List
from datetime import datetime, timedelta


class BalanceSafeHandler:
    """잔고 데이터 안전 처리 클래스"""
    
    def __init__(self):
        self.logger = logging.getLogger(__name__)
        self._cached_balance = {}
        self._last_successful_fetch = None
        self._retry_count = 0
        self._max_retries = 3
        self._retry_delay = 2.0  # 초
    
    async def get_safe_balance(self, exchange_manager, symbols: List[str] = None,
                              use_cache: bool = True, max_cache_age: int = 60) -> Dict[str, Any]:
        """
        안전한 잔고 조회 with 재시도 로직
        
        Args:
            exchange_manager: 거래소 매니저 인스턴스
            symbols: 조회할 심볼 리스트 (None이면 전체)
            use_cache: 캐시 사용 여부
            max_cache_age: 캐시 최대 보관 시간 (초)
            
        Returns:
            안전하게 처리된 잔고 데이터
        """
        try:
            # 캐시 확인
            if use_cache and self._is_cache_valid(max_cache_age):
                self.logger.debug("캐시된 잔고 데이터 사용")
                return self._cached_balance.copy()
            
            # 잔고 조회 시도
            balance_data = await self._fetch_balance_with_retry(exchange_manager, symbols)
            
            if balance_data:
                # 성공적으로 조회된 경우
                self._cached_balance = balance_data
                self._last_successful_fetch = datetime.now()
                self._retry_count = 0
                
                self.logger.debug(f"잔고 데이터 조회 성공: {len(balance_data.get('balances', {}))}개 항목")
                return balance_data
            
            else:
                # 조회 실패 시 캐시된 데이터나 기본값 반환
                return self._get_fallback_balance()
            
        except Exception as e:
            self.logger.error(f"잔고 조회 중 예외 발생: {e}")
            return self._get_fallback_balance()
    
    async def _fetch_balance_with_retry(self, exchange_manager, symbols: List[str] = None) -> Optional[Dict[str, Any]]:
        """재시도 로직을 포함한 잔고 조회"""
        for attempt in range(self._max_retries):
            try:
                self.logger.debug(f"잔고 조회 시도 {attempt + 1}/{self._max_retries}")
                
                # 실제 잔고 조회 (exchange_manager의 메서드 사용)
                if hasattr(exchange_manager, 'get_balance_async'):
                    balance_data = await exchange_manager.get_balance_async()
                elif hasattr(exchange_manager, 'get_balance'):
                    balance_data = exchange_manager.get_balance()
                elif hasattr(exchange_manager, 'exchange') and hasattr(exchange_manager.exchange, 'fetch_balance'):
                    balance_data = exchange_manager.exchange.fetch_balance()
                else:
                    raise AttributeError("잔고 조회 메서드를 찾을 수 없습니다")
                
                # 잔고 데이터 검증 및 정규화
                normalized_balance = self._normalize_balance_data(balance_data, symbols)
                
                if normalized_balance:
                    return normalized_balance
                else:
                    raise ValueError("잔고 데이터가 비어있습니다")
                
            except Exception as e:
                self.logger.warning(f"잔고 조회 시도 {attempt + 1} 실패: {e}")
                
                if attempt < self._max_retries - 1:
                    # 마지막 시도가 아니면 대기 후 재시도
                    await asyncio.sleep(self._retry_delay * (attempt + 1))
                else:
                    # 모든 시도 실패
                    self.logger.error(f"모든 잔고 조회 시도 실패. 최종 오류: {e}")
                    self._retry_count += 1
        
        return None
    
    def _normalize_balance_data(self, raw_balance: Any, symbols: List[str] = None) -> Dict[str, Any]:
        """
        다양한 형식의 잔고 데이터를 정규화
        
        Args:
            raw_balance: 원시 잔고 데이터
            symbols: 필터링할 심볼 리스트
            
        Returns:
            정규화된 잔고 데이터
        """
        try:
            normalized = {
                'balances': {},
                'total_balance': 0.0,
                'available_balance': 0.0,
                'timestamp': datetime.now().isoformat(),
                'source': 'exchange_api'
            }
            
            if isinstance(raw_balance, dict):
                # CCXT 형식 처리
                if 'total' in raw_balance and isinstance(raw_balance['total'], dict):
                    balances = {}
                    total_value = 0.0
                    available_value = 0.0
                    
                    for currency, amount in raw_balance['total'].items():
                        if amount and amount > 0:
                            free_amount = raw_balance.get('free', {}).get(currency, 0.0)
                            used_amount = raw_balance.get('used', {}).get(currency, 0.0)
                            
                            balances[currency] = {
                                'total': float(amount),
                                'free': float(free_amount),
                                'used': float(used_amount)
                            }
                            
                            total_value += float(amount)
                            available_value += float(free_amount)
                    
                    normalized['balances'] = balances
                    normalized['total_balance'] = total_value
                    normalized['available_balance'] = available_value
                
                # 직접 balances 키가 있는 경우
                elif 'balances' in raw_balance:
                    normalized['balances'] = raw_balance['balances']
                    normalized['total_balance'] = raw_balance.get('total_balance', 0.0)
                    normalized['available_balance'] = raw_balance.get('available_balance', 0.0)
                
                # symbols 필터링
                if symbols and normalized['balances']:
                    filtered_balances = {}
                    for symbol in symbols:
                        currency = symbol.replace('USDT', '').replace('USD', '')
                        if currency in normalized['balances']:
                            filtered_balances[currency] = normalized['balances'][currency]
                    
                    if filtered_balances:
                        normalized['balances'] = filtered_balances
            
            return normalized if normalized['balances'] else None
            
        except Exception as e:
            self.logger.error(f"잔고 데이터 정규화 실패: {e}")
            return None
    
    def _is_cache_valid(self, max_age: int) -> bool:
        """캐시 유효성 검사"""
        if not self._cached_balance or not self._last_successful_fetch:
            return False
        
        age = (datetime.now() - self._last_successful_fetch).total_seconds()
        return age < max_age
    
    def _get_fallback_balance(self) -> Dict[str, Any]:
        """대체 잔고 데이터 반환"""
        fallback = {
            'balances': {},
            'total_balance': 0.0,
            'available_balance': 0.0,
            'timestamp': datetime.now().isoformat(),
            'source': 'fallback',
            'warning': '잔고 데이터를 가져올 수 없어 기본값을 사용합니다'
        }
        
        # 캐시된 데이터가 있으면 사용 (오래된 데이터라도)
        if self._cached_balance and self._cached_balance.get('balances'):
            fallback = self._cached_balance.copy()
            fallback['source'] = 'cached'
            fallback['warning'] = '최신 잔고 데이터를 가져올 수 없어 캐시된 데이터를 사용합니다'
            self.logger.warning("캐시된 잔고 데이터 사용 (최신 조회 실패)")
        else:
            self.logger.warning("잔고 데이터 없음 - 기본값 사용")
        
        return fallback
    
    def get_balance_health_status(self) -> Dict[str, Any]:
        """잔고 시스템 상태 정보"""
        return {
            'last_successful_fetch': self._last_successful_fetch.isoformat() if self._last_successful_fetch else None,
            'retry_count': self._retry_count,
            'cache_valid': self._is_cache_valid(300),  # 5분
            'cached_balances_count': len(self._cached_balance.get('balances', {})),
            'max_retries': self._max_retries,
            'status': 'healthy' if self._retry_count < 5 else 'degraded'
        }


# 전역 인스턴스
balance_handler = BalanceSafeHandler()
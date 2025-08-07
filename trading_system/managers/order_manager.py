"""
Order Manager - Enhanced Order Execution from trading_system2
trading_system2의 향상된 주문 관리 시스템을 기존 시스템에 추가
"""

import time
import logging
from typing import Optional, Dict, Any

# Import configuration - flexible import handling
try:
    from ..config.config import TradingConfig
except ImportError:
    import sys
    import os
    sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    from config.config import TradingConfig


class OrderManager:
    """
    trading_system2에서 가져온 향상된 주문 매니저
    기존 거래 시스템에 재시도 로직과 안정성 기능을 추가
    """
    
    def __init__(self, api_client, config: TradingConfig = None):
        self.api = api_client
        self.logger = logging.getLogger(self.__class__.__name__)
        
        # 설정에서 재시도 횟수 가져오기 (기본값: 3)
        if config and hasattr(config, 'ORDER_RETRY'):
            self.retry = config.ORDER_RETRY
        else:
            self.retry = 3
            
        self.logger.info(f"🔄 OrderManager 초기화 완료 (재시도: {self.retry}회)")
        
    def execute_order(self, symbol: str, side: str, quantity: float, price: float = None) -> Optional[Dict[str, Any]]:
        """
        향상된 주문 실행 - 재시도 로직과 상태 추적 포함
        
        Args:
            symbol: 거래 심볼 (e.g., "BTCUSDT")  
            side: 주문 방향 ("buy" or "sell")
            quantity: 주문 수량
            price: 지정가 (None인 경우 시장가)
            
        Returns:
            성공 시 주문 정보 dict, 실패 시 None
        """
        for attempt in range(1, self.retry + 1):
            try:
                self.logger.info(f"📤 {symbol} 주문 시도 {attempt}/{self.retry}: {side} {quantity} @ {price if price else 'Market'}")
                
                # API 주문 실행
                if price:
                    order = self.api.place_order(symbol, side, quantity, price)
                    self.logger.debug(f"🎯 {symbol} 지정가 주문: {side} {quantity} @ {price}")
                else:
                    order = self.api.place_order(symbol, side, quantity)
                    self.logger.debug(f"⚡ {symbol} 시장가 주문: {side} {quantity}")
                    
                if not order or not order.get("order_id"):
                    raise Exception("주문 ID 없음 - API 응답 오류")
                    
                order_id = order.get("order_id")
                self.logger.info(f"✅ {symbol} 주문 생성 완료: ID={order_id}, Type={'Limit' if price else 'Market'}")
                
                # 주문 상태 확인 (최대 5번, 각 0.5초 간격)
                for check_attempt in range(5):
                    try:
                        status_resp = self.api.get_order_status(order_id)
                        status = status_resp.get("status")
                        
                        self.logger.debug(f"🔍 {symbol} 주문 상태 확인 {check_attempt+1}/5: {status}")
                        
                        if status == "filled":
                            filled_price = status_resp.get("filled_price", "N/A")
                            filled_qty = status_resp.get("filled_quantity", quantity)
                            self.logger.info(f"🎯 {symbol} 주문 체결 완료: ID={order_id}, Price={filled_price}, Qty={filled_qty}")
                            return status_resp
                        elif status in ["cancelled", "rejected"]:
                            self.logger.warning(f"❌ {symbol} 주문 실패: ID={order_id}, Status={status}")
                            break
                        elif status == "partially_filled":
                            filled_qty = status_resp.get("filled_quantity", 0)
                            self.logger.info(f"⏳ {symbol} 부분 체결: ID={order_id}, Filled={filled_qty}/{quantity}")
                            
                        time.sleep(0.5)
                        
                    except Exception as e:
                        self.logger.warning(f"⚠️ {symbol} 주문 상태 확인 오류 (시도 {check_attempt+1}): {e}")
                        
                self.logger.warning(f"⏳ {symbol} 주문 미체결, 재시도 예정 {attempt}/{self.retry}")
                
            except Exception as e:
                self.logger.error(f"❌ {symbol} 주문 실행 오류 (시도 {attempt}/{self.retry}): {e}", exc_info=True)
                
            # 재시도 전 대기 (지수적 백오프)
            if attempt < self.retry:
                wait_time = min(2 ** attempt, 10)  # 최대 10초
                time.sleep(wait_time)
                
        self.logger.error(f"💥 {symbol} 주문 완전 실패: 최대 재시도 횟수 초과")
        return None
        
    def cancel_order(self, symbol: str, order_id: str) -> bool:
        """
        주문 취소 - 재시도 로직 포함
        """
        for attempt in range(1, min(self.retry, 2) + 1):  # 취소는 최대 2번만
            try:
                result = self.api.cancel_order(symbol, order_id)
                if result:
                    self.logger.info(f"✅ {symbol} 주문 취소 완료: {order_id}")
                    return True
            except Exception as e:
                self.logger.error(f"❌ 주문 취소 오류 (시도 {attempt}): {e}")
                
            if attempt < min(self.retry, 2):
                time.sleep(1)
                
        return False
        
    def get_order_status(self, symbol: str, order_id: str) -> Optional[Dict[str, Any]]:
        """
        주문 상태 조회 - 오류 처리 강화
        """
        try:
            return self.api.get_order_status(order_id)
        except Exception as e:
            self.logger.error(f"❌ {symbol} 주문 상태 조회 오류: {e}")
            return None
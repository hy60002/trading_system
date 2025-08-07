"""
Bitget Order Manager
Handles order placement, modification, and position management
"""

import asyncio
import logging
import time
from typing import Dict, List, Optional, Any

try:
    from ...config.config import TradingConfig
    from ...utils.errors import ExchangeError
except ImportError:
    import sys
    import os
    sys.path.append(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
    from config.config import TradingConfig
    from utils.errors import ExchangeError


class OrderManager:
    """Manages order placement and position operations"""
    
    def __init__(self, config: TradingConfig, exchange, utils, ws_manager=None):
        self.config = config
        self.exchange = exchange
        self.utils = utils
        self.ws_manager = ws_manager
        self.logger = logging.getLogger(__name__)
        
        # Error tracking
        self.error_count = 0
        self.max_errors = 5
    
    async def place_order(self, symbol: str, side: str, amount: float, 
                         order_type: str = 'market', price: Optional[float] = None,
                         params: Optional[Dict] = None) -> Dict:
        """Place order with enhanced parameters"""
        await self.utils.check_rate_limit(self.utils.create_rate_limiter())
        
        # 🛡️ PAPER_TRADING 모드 체크
        if self.config.PAPER_TRADING:
            self.logger.info(f"🟡 PAPER_TRADING: {symbol} {side} {amount} @ {price or '시장가'} (모의 주문)")
            # 시뮬레이션 주문 응답 생성
            return {
                'id': f'paper_{int(time.time())}',
                'symbol': symbol,
                'side': side,
                'amount': amount,
                'price': price or (self._get_current_price(symbol) or 50000),
                'filled': amount,
                'status': 'closed',
                'paper_trade': True,
                'timestamp': int(time.time() * 1000)
            }
        
        try:
            market_symbol = self.utils.format_symbol(symbol)
            
            # Set leverage
            leverage = self.config.LEVERAGE.get(symbol, 10)
            await self.set_leverage(symbol, leverage)
            
            # Calculate slippage for market orders
            if order_type == 'market' and self.ws_manager and self.ws_manager.is_connected():
                estimated_price = self._estimate_execution_price(symbol, side)
            else:
                estimated_price = price
            
            # Bitget specific parameters for futures trading
            order_params = {
                'marginMode': 'isolated',  # isolated margin mode
                'timeInForce': 'IOC',      # Immediate or Cancel
                **(params or {})
            }
            
            # Place order
            order = await asyncio.get_event_loop().run_in_executor(
                None,
                self.exchange.create_order,
                market_symbol,
                order_type,
                side,
                amount,
                price,
                order_params
            )
            
            # Calculate actual slippage
            if order_type == 'market' and estimated_price:
                actual_price = order.get('price', estimated_price)
                slippage = abs(actual_price - estimated_price) / estimated_price
                order['slippage'] = slippage
            
            self.error_count = 0
            self.logger.info(f"주문 실행: {symbol} {side} {amount} @ {price or '시장가'}")
            return order
            
        except Exception as e:
            self.error_count = self.utils.handle_error(e, self.error_count, self.max_errors)
            return {}
    
    async def place_stop_loss_order(self, symbol: str, side: str, amount: float, 
                                   stop_price: float) -> Dict:
        """Place stop loss order"""
        params = {
            'stopPrice': stop_price,
            'triggerType': 'market_price',
            'timeInForce': 'GTC'
        }
        
        return await self.place_order(
            symbol, 
            side, 
            amount, 
            'stop_market',
            None,
            params
        )
    
    async def modify_stop_loss(self, symbol: str, order_id: str, new_stop_price: float) -> Dict:
        """Modify existing stop loss order"""
        try:
            await self.utils.check_rate_limit(self.utils.create_rate_limiter())
            
            # 🛡️ PAPER_TRADING 모드 체크
            if self.config.PAPER_TRADING:
                self.logger.info(f"🟡 PAPER_TRADING: {symbol} 스탑로스 수정 {order_id} -> {new_stop_price} (모의)")
                return {
                    'id': order_id,
                    'symbol': symbol,
                    'stopPrice': new_stop_price,
                    'status': 'open',
                    'paper_trade': True
                }
            
            market_symbol = self.utils.format_symbol(symbol)
            
            # Cancel existing order and place new one
            await asyncio.get_event_loop().run_in_executor(
                None,
                self.exchange.cancel_order,
                order_id,
                market_symbol
            )
            
            # Wait a bit for cancellation to process
            await asyncio.sleep(0.5)
            
            # Place new stop loss order
            new_order = await self.place_stop_loss_order(
                symbol, 
                'sell',  # Assuming we're modifying a sell stop loss
                0.001,   # Minimal amount for modification
                new_stop_price
            )
            
            self.error_count = 0
            self.logger.info(f"스탑로스 수정 완료: {symbol} {new_stop_price}")
            return new_order
            
        except Exception as e:
            self.error_count = self.utils.handle_error(e, self.error_count, self.max_errors)
            return {}
    
    async def close_position(self, symbol: str, reason: str = "manual") -> Dict:
        """Close all positions for symbol"""
        try:
            await self.utils.check_rate_limit(self.utils.create_rate_limiter())
            
            # 🛡️ PAPER_TRADING 모드 체크
            if self.config.PAPER_TRADING:
                self.logger.info(f"🟡 PAPER_TRADING: {symbol} 포지션 청산 (이유: {reason}) (모의)")
                return {'symbol': symbol, 'status': 'closed', 'reason': reason, 'paper_trade': True}
            
            market_symbol = self.utils.format_symbol(symbol)
            
            # Get current positions
            positions = await asyncio.get_event_loop().run_in_executor(
                None,
                self.exchange.fetch_positions,
                [market_symbol]
            )
            
            results = []
            for position in positions:
                if position['contracts'] > 0:  # Has open position
                    side = 'sell' if position['side'] == 'long' else 'buy'
                    amount = position['contracts']
                    
                    close_order = await self.place_order(
                        symbol,
                        side,
                        amount,
                        'market'
                    )
                    results.append(close_order)
            
            self.error_count = 0
            self.logger.info(f"포지션 청산 완료: {symbol} (이유: {reason})")
            return {'symbol': symbol, 'orders': results, 'reason': reason}
            
        except Exception as e:
            self.error_count = self.utils.handle_error(e, self.error_count, self.max_errors)
            return {}
    
    async def set_leverage(self, symbol: str, leverage: int):
        """Set leverage for symbol"""
        try:
            await self.utils.check_rate_limit(self.utils.create_rate_limiter())
            
            # 🛡️ PAPER_TRADING 모드 체크
            if self.config.PAPER_TRADING:
                self.logger.debug(f"🟡 PAPER_TRADING: {symbol} 레버리지 설정 {leverage}x (모의)")
                return True
            
            market_symbol = self.utils.format_symbol(symbol)
            
            # Set leverage
            await asyncio.get_event_loop().run_in_executor(
                None,
                self.exchange.set_leverage,
                leverage,
                market_symbol,
                {'marginMode': 'isolated'}
            )
            
            self.logger.debug(f"레버리지 설정: {symbol} {leverage}x")
            return True
            
        except Exception as e:
            # Leverage setting failures are not critical
            self.logger.warning(f"레버리지 설정 실패 {symbol}: {e}")
            return False
    
    async def set_position_mode_oneway(self):
        """Set position mode to one-way (no hedge)"""
        try:
            if self.config.PAPER_TRADING:
                self.logger.info("🟡 PAPER_TRADING: 단방향 포지션 모드 설정 (모의)")
                return True
            
            # Set one-way position mode
            await asyncio.get_event_loop().run_in_executor(
                None,
                self.exchange.set_position_mode,
                False  # One-way mode
            )
            
            self.logger.info("✅ 단방향 포지션 모드 설정 완료")
            return True
            
        except Exception as e:
            self.logger.warning(f"포지션 모드 설정 실패: {e}")
            return False
    
    def _estimate_execution_price(self, symbol: str, side: str) -> Optional[float]:
        """Estimate execution price based on orderbook"""
        if not self.ws_manager:
            return None
            
        price_data = self.ws_manager.price_data.get(symbol, {})
        
        if side == 'buy' and 'ask' in price_data:
            return price_data['ask']
        elif side == 'sell' and 'bid' in price_data:
            return price_data['bid']
        else:
            return price_data.get('price')
    
    def _get_current_price(self, symbol: str) -> Optional[float]:
        """Get current price for symbol"""
        if self.ws_manager:
            return self.ws_manager.get_current_price(symbol)
        return None
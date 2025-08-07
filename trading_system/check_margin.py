import asyncio
from exchange.bitget_manager import EnhancedBitgetExchangeManager
from config.config import TradingConfig

async def check_margin_usage():
    config = TradingConfig()
    exchange = EnhancedBitgetExchangeManager(config)
    
    try:
        await exchange.initialize()
        
        # 잔고에서 사용된 증거금 확인
        balance = await exchange.get_balance()
        print('=== Bitget 증거금 정보 ===')
        
        info = balance.get('info', [{}])[0]
        print(f'총 잔고 (accountEquity): {info.get("accountEquity")}')
        print(f'사용 가능 (available): {info.get("available")}')
        print(f'격리 증거금 (isolatedMargin): {info.get("isolatedMargin")}')
        print(f'미실현 손익 (unrealizedPL): {info.get("unrealizedPL")}')
        
        # 실제 포지션에서 증거금 계산
        positions = await exchange.get_positions()
        total_margin_used = 0
        
        for pos in positions:
            if pos.get('contracts', 0) > 0:
                symbol = pos.get('symbol')
                contracts = pos.get('contracts', 0)
                entry_price = pos.get('entryPrice', 0)
                
                # 올바른 명목 가치 계산 (Bitget 선물)
                # contracts는 이미 USD 단위의 명목가치를 나타냄
                if 'BTC' in symbol:
                    # BTC/USDT에서 0.5251 계약 = $60,116 명목가치
                    nominal_value = contracts * entry_price  # 정확한 계산
                elif 'ETH' in symbol:
                    # ETH/USDT에서 0.27 계약 = $963 명목가치  
                    nominal_value = contracts * entry_price
                else:
                    nominal_value = contracts * entry_price
                
                # 레버리지로 나눈 실제 증거금
                leverage = config.LEVERAGE.get(symbol.replace('/USDT:USDT', 'USDT'), 10)
                actual_margin = nominal_value / leverage
                
                print(f'{symbol}:')
                print(f'  계약수: {contracts}')
                print(f'  진입가: {entry_price}')
                print(f'  명목가치: ${nominal_value:.2f}')
                print(f'  레버리지: {leverage}x')
                print(f'  실제 증거금: ${actual_margin:.2f}')
                print()
                
                total_margin_used += actual_margin
        
        print(f'계산된 총 증거금 사용량: ${total_margin_used:.2f}')
        print(f'Bitget 보고 격리 증거금: ${float(info.get("isolatedMargin", 0)):.2f}')
        
    except Exception as e:
        print(f'오류: {e}')
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    asyncio.run(check_margin_usage())
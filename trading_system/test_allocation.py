import asyncio
from managers.risk_manager import RiskManager
from database.db_manager import EnhancedDatabaseManager
from config.config import TradingConfig

async def test_fixed_allocation():
    config = TradingConfig()
    db = EnhancedDatabaseManager('advanced_trading_v3.db')
    risk_manager = RiskManager(config, db)
    
    # 현재 상태 가져오기
    total_capital = 6096.80  # 실제 잔고
    positions = db.get_open_positions()
    
    print('=== 수정된 자본 할당 계산 테스트 ===')
    print(f'총 자본: ${total_capital:.2f}')
    print(f'현재 포지션 수: {len(positions)}')
    
    # 현재 할당 비율 확인
    ratio = risk_manager.get_current_total_allocation_ratio(total_capital, positions)
    print(f'현재 할당 비율: {ratio:.1%}')
    print(f'실제 사용 증거금: ${total_capital * ratio:.2f}')
    print(f'{config.CAPITAL_ALLOCATION_LIMIT:.0%} 한도 (${total_capital * config.CAPITAL_ALLOCATION_LIMIT:.2f}) 내 여부: {ratio <= config.CAPITAL_ALLOCATION_LIMIT}')
    
    if ratio <= config.CAPITAL_ALLOCATION_LIMIT:
        print()
        print(f'✅ {config.CAPITAL_ALLOCATION_LIMIT:.0%} 한도 내에 있으므로 추가 거래 가능!')
        
        # BTC 추가 할당 계산
        print()
        print('BTCUSDT 추가 할당 계산:')
        allocation = risk_manager.calculate_position_allocation('BTCUSDT', total_capital, positions)
        print(f'결과: {allocation} (type: {type(allocation)})')
        
        # ETH 추가 할당 계산
        print()
        print('ETHUSDT 추가 할당 계산:')
        allocation = risk_manager.calculate_position_allocation('ETHUSDT', total_capital, positions)
        print(f'결과: {allocation} (type: {type(allocation)})')
    else:
        print(f'❌ {config.CAPITAL_ALLOCATION_LIMIT:.0%} 한도 초과로 추가 거래 불가')

if __name__ == "__main__":
    asyncio.run(test_fixed_allocation())
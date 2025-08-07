#!/usr/bin/env python3
import asyncio
import sys
import os

# Add the trading_system directory to the Python path
sys.path.append(os.path.join(os.path.dirname(__file__), 'trading_system'))

from config.config import TradingConfig
from notifications.notification_manager import NotificationManager

async def test_notification():
    print("알림 시스템 테스트 시작...")
    
    # Load config
    config = TradingConfig.from_env()
    print(f"Telegram Token: {config.TELEGRAM_BOT_TOKEN[:10]}...")
    print(f"Chat ID: {config.TELEGRAM_CHAT_ID}")
    
    # Create notification manager
    notifier = NotificationManager(config)
    await notifier.initialize()
    
    print("알림 전송 중...")
    
    # Test trade notification
    await notifier.send_trade_notification(
        symbol="BTCUSDT",
        action="open_long",
        details={
            'price': 45000.0,
            'quantity': 0.01,
            'signal_strength': 0.85,
            'confidence': 78.5,
            'reason': '강력한 상승 시그널 감지'
        }
    )
    
    print("테스트 완료! 텔레그램 확인해보세요.")
    
    # Wait a bit for message to send
    await asyncio.sleep(3)
    
    await notifier.shutdown()

if __name__ == "__main__":
    asyncio.run(test_notification())
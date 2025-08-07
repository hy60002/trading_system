#!/usr/bin/env python3
import asyncio
import aiohttp
import os
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

async def test_telegram():
    token = os.getenv('TELEGRAM_BOT_TOKEN')
    chat_id = os.getenv('TELEGRAM_CHAT_ID')
    
    print(f"Token: {token}")
    print(f"Chat ID: {chat_id}")
    
    if not token or not chat_id:
        print("텔레그램 설정이 없습니다!")
        return
    
    url = f"https://api.telegram.org/bot{token}/sendMessage"
    
    # Test messages
    messages = [
        "Hello! This is a test message",
        "🚀 Trading Test - English",
        "거래 테스트 - 한글 메시지"
    ]
    
    async with aiohttp.ClientSession() as session:
        for i, message in enumerate(messages, 1):
            try:
                data = {
                    "chat_id": chat_id,
                    "text": message,
                    "parse_mode": "Markdown"
                }
                
                print(f"\n테스트 {i}: {message}")
                
                async with session.post(url, data=data) as response:
                    result = await response.json()
                    print(f"응답 상태: {response.status}")
                    print(f"응답 내용: {result}")
                    
                    if result.get('ok'):
                        print("SUCCESS!")
                    else:
                        print(f"FAILED: {result.get('description')}")
                        
                await asyncio.sleep(1)  # Rate limit
                
            except Exception as e:
                print(f"EXCEPTION: {e}")

if __name__ == "__main__":
    asyncio.run(test_telegram())
#!/usr/bin/env python3
"""
WebSocket 연결 테스트 스크립트
"""

import asyncio
import websockets
import json
import logging

# 로깅 설정
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

async def test_websocket():
    """WebSocket 연결 테스트"""
    ws_urls = [
        "wss://ws.bitget.com/v2/ws/public",
        "wss://ws.bitgetapi.com/v2/ws/public", 
        "wss://ws.bitget.com/mix/v1/stream"
    ]
    
    for i, ws_url in enumerate(ws_urls):
        try:
            logger.info(f"🔌 WebSocket 연결 테스트 ({i+1}/{len(ws_urls)}): {ws_url}")
            
            async with websockets.connect(
                ws_url,
                ping_interval=20,
                ping_timeout=10,
                close_timeout=5
            ) as websocket:
                logger.info(f"✅ WebSocket 연결 성공: {ws_url}")
                
                # 구독 테스트
                if "v2" in ws_url:
                    # v2 API 형식
                    subscribe_msg = {
                        "op": "subscribe",
                        "args": [
                            {
                                "instType": "UMCBL",
                                "channel": "ticker",
                                "instId": "BTCUSDT"
                            }
                        ]
                    }
                else:
                    # v1 API 형식
                    subscribe_msg = {
                        "op": "subscribe",
                        "args": [
                            {
                                "instType": "mc",
                                "channel": "ticker",
                                "instId": "BTCUSDT"
                            }
                        ]
                    }
                
                await websocket.send(json.dumps(subscribe_msg))
                logger.info(f"📡 구독 요청 전송: BTCUSDT ticker")
                
                # 응답 기다리기 (5초)
                try:
                    response = await asyncio.wait_for(websocket.recv(), timeout=5.0)
                    logger.info(f"📨 응답 받음: {response[:100]}...")
                    return True, ws_url
                except asyncio.TimeoutError:
                    logger.warning(f"⏰ 응답 시간 초과: {ws_url}")
                    
        except Exception as e:
            logger.error(f"❌ 연결 실패 {ws_url}: {e}")
            continue
    
    return False, None

async def main():
    logger.info("🚀 Bitget WebSocket 연결 테스트 시작")
    success, working_url = await test_websocket()
    
    if success:
        logger.info(f"🎉 WebSocket 연결 성공! 사용 가능한 URL: {working_url}")
    else:
        logger.error("❌ 모든 WebSocket URL 연결 실패")

if __name__ == "__main__":
    asyncio.run(main())
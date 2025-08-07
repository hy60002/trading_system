#!/usr/bin/env python3
"""
GPTBITCOIN 24시간 연속 실행기
오류 발생 시 자동 재시작
"""

import asyncio
import logging
import sys
import time
from datetime import datetime
import subprocess
import traceback

# 로깅 설정
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('continuous_runner.log', encoding='utf-8'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

class ContinuousRunner:
    def __init__(self):
        self.restart_count = 0
        self.max_restarts = 100  # 최대 재시작 횟수
        self.restart_delay = 30  # 재시작 대기 시간 (초)
        self.last_restart_time = None
        
    async def run_trading_system(self):
        """거래 시스템 실행"""
        try:
            # trading_system2.py 임포트 및 실행
            from trading_system2 import main
            await main()
            
        except KeyboardInterrupt:
            logger.info("사용자에 의해 종료됨")
            return False
            
        except Exception as e:
            logger.error(f"거래 시스템 오류: {e}")
            logger.error(f"상세 오류:\n{traceback.format_exc()}")
            return True  # 재시작 필요
    
    def should_restart(self):
        """재시작 여부 판단"""
        current_time = time.time()
        
        # 최대 재시작 횟수 초과
        if self.restart_count >= self.max_restarts:
            logger.error(f"최대 재시작 횟수({self.max_restarts}) 초과")
            return False
        
        # 너무 빈번한 재시작 방지 (1분 내 5회)
        if self.last_restart_time:
            if current_time - self.last_restart_time < 60 and self.restart_count % 5 == 0:
                logger.warning("빈번한 재시작 감지. 5분 대기...")
                time.sleep(300)  # 5분 대기
        
        return True
    
    async def monitor_system_health(self):
        """시스템 상태 모니터링"""
        while True:
            try:
                # 메모리 사용량 체크
                import psutil
                memory_percent = psutil.virtual_memory().percent
                
                if memory_percent > 90:
                    logger.warning(f"메모리 사용량 높음: {memory_percent}%")
                
                # 디스크 공간 체크
                disk_usage = psutil.disk_usage('C:/')
                disk_percent = (disk_usage.used / disk_usage.total) * 100
                
                if disk_percent > 95:
                    logger.error(f"디스크 공간 부족: {disk_percent}%")
                
                await asyncio.sleep(300)  # 5분마다 체크
                
            except Exception as e:
                logger.error(f"시스템 모니터링 오류: {e}")
                await asyncio.sleep(60)
    
    async def run_continuous(self):
        """24시간 연속 실행"""
        logger.info("🚀 GPTBITCOIN 24시간 연속 실행 시작")
        
        # 시스템 모니터링 태스크 시작
        monitor_task = asyncio.create_task(self.monitor_system_health())
        
        while True:
            try:
                start_time = datetime.now()
                logger.info(f"거래 시스템 시작 #{self.restart_count + 1} - {start_time}")
                
                # 거래 시스템 실행
                need_restart = await self.run_trading_system()
                
                if not need_restart:
                    logger.info("정상 종료")
                    break
                
                # 재시작 체크
                if not self.should_restart():
                    break
                
                self.restart_count += 1
                self.last_restart_time = time.time()
                
                logger.info(f"재시작 #{self.restart_count} - {self.restart_delay}초 후")
                await asyncio.sleep(self.restart_delay)
                
            except Exception as e:
                logger.error(f"연속 실행기 오류: {e}")
                logger.error(traceback.format_exc())
                await asyncio.sleep(60)
        
        # 모니터링 태스크 종료
        monitor_task.cancel()
        logger.info("24시간 연속 실행 종료")

async def main():
    runner = ContinuousRunner()
    await runner.run_continuous()

if __name__ == '__main__':
    # psutil 설치 체크
    try:
        import psutil
    except ImportError:
        print("psutil 패키지 설치 중...")
        subprocess.run([sys.executable, '-m', 'pip', 'install', 'psutil'])
        import psutil
    
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\n프로그램이 종료되었습니다.")
    except Exception as e:
        print(f"치명적 오류: {e}")
        traceback.print_exc()
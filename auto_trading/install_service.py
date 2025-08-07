#!/usr/bin/env python3
"""
GPTBITCOIN Windows 서비스 설치 스크립트
관리자 권한으로 실행해야 합니다.
"""

import sys
import os
import subprocess

def create_service_script():
    """Windows 서비스용 스크립트 생성"""
    service_script = """
import win32serviceutil
import win32service
import win32event
import servicemanager
import asyncio
import sys
import os

# 경로 추가
sys.path.append(r'C:\GPTBITCOIN\auto_trading')

from trading_system2 import main

class GPTBitcoinService(win32serviceutil.ServiceFramework):
    _svc_name_ = "GPTBitcoinTrading"
    _svc_display_name_ = "GPTBITCOIN 자동거래 시스템"
    _svc_description_ = "암호화폐 자동거래 시스템 24시간 실행"

    def __init__(self, args):
        win32serviceutil.ServiceFramework.__init__(self, args)
        self.hWaitStop = win32event.CreateEvent(None, 0, 0, None)
        self.is_running = True

    def SvcStop(self):
        self.ReportServiceStatus(win32service.SERVICE_STOP_PENDING)
        self.is_running = False
        win32event.SetEvent(self.hWaitStop)

    def SvcDoRun(self):
        servicemanager.LogMsg(
            servicemanager.EVENTLOG_INFORMATION_TYPE,
            servicemanager.PYS_SERVICE_STARTED,
            (self._svc_name_, '')
        )
        
        try:
            # 비동기 메인 함수 실행
            asyncio.run(self.run_trading_system())
        except Exception as e:
            servicemanager.LogErrorMsg(f"서비스 실행 오류: {e}")

    async def run_trading_system(self):
        try:
            await main()
        except Exception as e:
            servicemanager.LogErrorMsg(f"거래 시스템 오류: {e}")

if __name__ == '__main__':
    win32serviceutil.HandleCommandLine(GPTBitcoinService)
"""
    
    with open('C:/GPTBITCOIN/auto_trading/service.py', 'w', encoding='utf-8') as f:
        f.write(service_script)
    
    print("✅ Windows 서비스 스크립트 생성 완료")

def install_requirements():
    """Windows 서비스 필요 패키지 설치"""
    print("📦 Windows 서비스 패키지 설치 중...")
    subprocess.run([sys.executable, '-m', 'pip', 'install', 'pywin32'])
    print("✅ 패키지 설치 완료")

def install_service():
    """서비스 설치"""
    print("🔧 Windows 서비스 설치 중...")
    os.chdir('C:/GPTBITCOIN/auto_trading')
    subprocess.run([sys.executable, 'service.py', 'install'])
    print("✅ 서비스 설치 완료")

def main():
    print("🚀 GPTBITCOIN Windows 서비스 설치")
    print("=" * 50)
    
    # 관리자 권한 확인
    try:
        import win32api
        import win32con
        if not win32api.GetUserName():
            print("❌ 관리자 권한이 필요합니다!")
            return
    except:
        pass
    
    try:
        install_requirements()
        create_service_script()
        install_service()
        
        print("\n🎉 설치 완료!")
        print("📝 서비스 제어 명령어:")
        print("  시작: net start GPTBitcoinTrading")
        print("  정지: net stop GPTBitcoinTrading")
        print("  제거: python service.py remove")
        
    except Exception as e:
        print(f"❌ 설치 실패: {e}")

if __name__ == '__main__':
    main()
@echo off
echo ===============================================
echo Windows 방화벽 규칙 추가 중...
echo ===============================================

REM 관리자 권한 확인
net session >nul 2>&1
if %errorLevel% == 0 (
    echo 관리자 권한 확인됨.
) else (
    echo 관리자 권한이 필요합니다!
    echo 이 파일을 우클릭하여 "관리자 권한으로 실행"하세요.
    pause
    exit /b 1
)

REM 포트 8000 허용
netsh advfirewall firewall add rule name="GPTBITCOIN Port 8000" dir=in action=allow protocol=TCP localport=8000
echo 포트 8000 허용 규칙 추가됨

REM 포트 3000 허용  
netsh advfirewall firewall add rule name="GPTBITCOIN Port 3000" dir=in action=allow protocol=TCP localport=3000
echo 포트 3000 허용 규칙 추가됨

REM Python.exe 허용
netsh advfirewall firewall add rule name="Python Allow" dir=in action=allow program="C:\Program Files\Python310\python.exe"
echo Python.exe 허용 규칙 추가됨

echo ===============================================
echo 방화벽 규칙 추가 완료!
echo ===============================================
pause
"""
빠른 시작을 위한 단계별 설정 도우미
API 키 설정 및 초기 테스트 자동화
"""

import os
import sys
from pathlib import Path

def print_banner():
    """시작 배너 출력"""
    print("=" * 60)
    print("AI 배달 도우미 - 빠른 시작 도우미")
    print("=" * 60)
    print()

def check_python_version():
    """Python 버전 확인"""
    if sys.version_info < (3, 8):
        print("[오류] Python 3.8 이상이 필요합니다.")
        print(f"현재 버전: {sys.version}")
        return False
    
    print(f"[성공] Python 버전: {sys.version.split()[0]}")
    return True

def check_env_file():
    """환경 변수 파일 확인"""
    env_path = Path(".env")
    example_path = Path(".env.example")
    
    if not env_path.exists():
        if example_path.exists():
            print("[경고] .env 파일이 없습니다.")
            print(".env.example을 참고하여 .env 파일을 생성해주세요.")
            
            create = input("\n.env.example을 .env로 복사하시겠습니까? (y/n): ")
            if create.lower() == 'y':
                import shutil
                shutil.copy(example_path, env_path)
                print("[성공] .env 파일이 생성되었습니다.")
                print("이제 .env 파일을 열어서 실제 API 키를 입력해주세요.")
                return False
        else:
            print("[오류] .env.example 파일을 찾을 수 없습니다.")
            return False
    
    print("[성공] .env 파일 존재")
    return True

def validate_env_variables():
    """필수 환경 변수 확인"""
    from dotenv import load_dotenv
    load_dotenv()
    
    required_vars = {
        'TWILIO_ACCOUNT_SID': 'Twilio Account SID',
        'TWILIO_AUTH_TOKEN': 'Twilio Auth Token', 
        'TWILIO_PHONE_NUMBER': 'Twilio 전화번호',
        'OPENAI_API_KEY': 'OpenAI API 키'
    }
    
    missing_vars = []
    placeholder_vars = []
    
    for var, description in required_vars.items():
        value = os.getenv(var)
        if not value:
            missing_vars.append(f"  - {var}: {description}")
        elif 'your_' in value or 'here' in value:
            placeholder_vars.append(f"  - {var}: {description}")
        else:
            print(f"[성공] {description} 설정됨")
    
    if missing_vars:
        print(f"\n[오류] 누락된 환경 변수:")
        for var in missing_vars:
            print(var)
    
    if placeholder_vars:
        print(f"\n[경고] 기본값으로 설정된 변수 (실제 값으로 변경 필요):")
        for var in placeholder_vars:
            print(var)
    
    return len(missing_vars) == 0 and len(placeholder_vars) == 0

def check_dependencies():
    """패키지 의존성 확인"""
    try:
        import fastapi
        import twilio
        import openai
        import speech_recognition
        import gtts
        print("[성공] 필수 패키지 설치됨")
        return True
    except ImportError as e:
        print(f"[오류] 누락된 패키지: {e.name}")
        print("다음 명령어로 설치하세요:")
        print("pip install -r requirements.txt")
        return False

def run_basic_test():
    """기본 시스템 테스트 실행"""
    print("\n[테스트] 기본 시스템 테스트 실행 중...")
    
    try:
        # 데이터베이스 테스트
        from database import db_manager
        menu_items = db_manager.get_menu_items()
        if len(menu_items) > 0:
            print(f"✅ 데이터베이스: {len(menu_items)}개 메뉴 로드됨")
        else:
            print("⚠️  데이터베이스에 메뉴가 없습니다")
        
        # AI 대화 모듈 테스트 (API 키 없이도 기본 기능 확인)
        from ai_conversation import ai_conversation
        print("✅ AI 대화 모듈 로드됨")
        
        # 음성 처리 모듈 테스트
        from speech_processor import speech_processor
        test_text = "안녕하세요"
        corrected = speech_processor.enhance_speech_recognition(test_text)
        if corrected == test_text:
            print("✅ 음성 처리 모듈 로드됨")
        
        return True
        
    except Exception as e:
        print(f"❌ 시스템 테스트 실패: {e}")
        return False

def show_next_steps():
    """다음 단계 안내"""
    print("\n📋 다음 단계:")
    print("1. API 키 설정 완료 후:")
    print("   python test_system.py")
    print()
    print("2. 서버 실행:")
    print("   python main.py")
    print()
    print("3. 외부 접속을 위한 ngrok 설정:")
    print("   ngrok http 8000")
    print()
    print("4. Twilio 웹훅 URL 설정:")
    print("   https://your-ngrok-url.ngrok.io/voice")
    print()
    print("🆘 자세한 설정 가이드: setup_guide.md 참고")

def main():
    """메인 실행 함수"""
    print_banner()
    
    # 단계별 확인
    if not check_python_version():
        return
        
    if not check_env_file():
        show_next_steps()
        return
    
    if not validate_env_variables():
        print("\n🔧 .env 파일의 API 키를 실제 값으로 수정한 후 다시 실행해주세요.")
        show_next_steps()
        return
    
    if not check_dependencies():
        return
    
    if not run_basic_test():
        return
    
    print("\n🎉 기본 설정이 완료되었습니다!")
    print("\n📞 실제 전화 테스트를 위해서는:")
    print("1. ngrok으로 로컬 서버를 외부에 노출")
    print("2. Twilio 콘솔에서 웹훅 URL 설정")  
    print("3. 구매한 Twilio 번호로 전화 걸어 테스트")
    
    start_server = input("\n지금 서버를 시작하시겠습니까? (y/n): ")
    if start_server.lower() == 'y':
        print("\n🚀 서버를 시작합니다...")
        print("다른 터미널에서 'ngrok http 8000' 실행하세요")
        print("Ctrl+C로 서버를 중지할 수 있습니다")
        print("-" * 60)
        
        # 서버 실행
        try:
            import uvicorn
            from main import app
            uvicorn.run(app, host="localhost", port=8000)
        except KeyboardInterrupt:
            print("\n👋 서버가 중지되었습니다.")
        except Exception as e:
            print(f"\n❌ 서버 시작 오류: {e}")
    else:
        show_next_steps()

if __name__ == "__main__":
    main()
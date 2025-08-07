#!/usr/bin/env python3
"""
API 키 암호화 관리 도구
개발자가 API 키를 안전하게 암호화하고 .env 파일에 저장할 수 있도록 도와주는 스크립트
"""

import os
import sys
import getpass
from typing import Dict, Optional
from crypto_utils import CryptoUtils, encrypt_api_key, decrypt_api_key, is_key_encrypted


class KeyManager:
    """API 키 암호화/복호화 관리자"""
    
    def __init__(self):
        self.crypto = CryptoUtils()
        self.env_file_path = self._find_env_file()
    
    def _find_env_file(self) -> str:
        """환경 파일 찾기"""
        possible_paths = [
            "../.env",
            "../../.env", 
            ".env",
            "../../C:GPTBITCOIN.env"
        ]
        
        for path in possible_paths:
            if os.path.exists(path):
                return path
        
        # 없으면 기본값 반환
        return "../../.env"
    
    def setup_master_key(self):
        """마스터 키 설정"""
        print("🔐 암호화 시스템 설정")
        print("=" * 50)
        
        # 기존 마스터 키 확인
        existing_key = os.getenv('TRADING_SYSTEM_MASTER_KEY')
        if existing_key:
            print("✅ 기존 마스터 키가 감지되었습니다.")
            use_existing = input("기존 키를 사용하시겠습니까? (y/n): ").lower() == 'y'
            if use_existing:
                return existing_key
        
        print("\n새로운 마스터 키를 생성하거나 설정하세요:")
        print("1. 자동 생성 (권장)")
        print("2. 수동 입력")
        
        choice = input("선택 (1-2): ").strip()
        
        if choice == "1":
            # 자동 생성
            master_key = CryptoUtils.generate_master_key()
            print(f"\n🔑 새 마스터 키가 생성되었습니다:")
            print(f"키: {master_key}")
            print("\n⚠️ 중요: 이 키를 안전한 곳에 보관하세요!")
            print("시스템 환경변수에 다음과 같이 설정하세요:")
            print(f"TRADING_SYSTEM_MASTER_KEY={master_key}")
            
        elif choice == "2":
            # 수동 입력
            master_key = getpass.getpass("마스터 키를 입력하세요: ").strip()
            if len(master_key) < 16:
                print("⚠️ 보안을 위해 16자 이상의 키를 사용하는 것이 좋습니다.")
        
        else:
            print("잘못된 선택입니다.")
            return None
        
        # 환경변수 설정 가이드
        print("\n📋 환경변수 설정 방법:")
        print("Windows:")
        print(f'  set TRADING_SYSTEM_MASTER_KEY={master_key}')
        print("Linux/Mac:")
        print(f'  export TRADING_SYSTEM_MASTER_KEY={master_key}')
        
        return master_key
    
    def encrypt_env_file(self):
        """환경 파일의 API 키들을 암호화"""
        if not self.crypto.is_available():
            print("❌ 암호화 시스템을 사용할 수 없습니다. 마스터 키를 설정하세요.")
            return
        
        print(f"🔍 환경 파일 처리: {self.env_file_path}")
        
        if not os.path.exists(self.env_file_path):
            print(f"❌ 환경 파일을 찾을 수 없습니다: {self.env_file_path}")
            return
        
        # 백업 생성
        backup_path = f"{self.env_file_path}.backup"
        if not os.path.exists(backup_path):
            with open(self.env_file_path, 'r') as original:
                with open(backup_path, 'w') as backup:
                    backup.write(original.read())
            print(f"✅ 백업 생성: {backup_path}")
        
        # 환경 파일 읽기
        env_vars = {}
        with open(self.env_file_path, 'r') as f:
            for line in f:
                line = line.strip()
                if '=' in line and not line.startswith('#'):
                    key, value = line.split('=', 1)
                    env_vars[key.strip()] = value.strip()
        
        # 암호화할 키들
        keys_to_encrypt = [
            'BITGET_API_KEY',
            'BITGET_SECRET_KEY', 
            'BITGET_PASSPHRASE',
            'OPENAI_API_KEY',
            'TELEGRAM_BOT_TOKEN',
            'TELEGRAM_CHAT_ID'
        ]
        
        encrypted_count = 0
        for key in keys_to_encrypt:
            if key in env_vars and env_vars[key]:
                if is_key_encrypted(env_vars[key]):
                    print(f"⏭️ {key}는 이미 암호화되어 있습니다.")
                    continue
                
                encrypted_value = self.crypto.encrypt_string(env_vars[key])
                if encrypted_value:
                    env_vars[key] = encrypted_value
                    encrypted_count += 1
                    print(f"🔐 {key} 암호화 완료")
        
        if encrypted_count > 0:
            # 암호화된 내용을 파일에 저장
            with open(self.env_file_path, 'w') as f:
                for key, value in env_vars.items():
                    f.write(f"{key}={value}\n")
            
            print(f"✅ {encrypted_count}개 키가 암호화되어 저장되었습니다.")
        else:
            print("ℹ️ 암호화할 새로운 키가 없습니다.")
    
    def decrypt_env_file(self):
        """환경 파일의 암호화된 키들을 복호화 (개발/디버깅용)"""
        if not self.crypto.is_available():
            print("❌ 암호화 시스템을 사용할 수 없습니다.")
            return
        
        print(f"🔓 환경 파일 복호화: {self.env_file_path}")
        
        if not os.path.exists(self.env_file_path):
            print(f"❌ 환경 파일을 찾을 수 없습니다: {self.env_file_path}")
            return
        
        # 환경 파일 읽기
        env_vars = {}
        with open(self.env_file_path, 'r') as f:
            for line in f:
                line = line.strip()
                if '=' in line and not line.startswith('#'):
                    key, value = line.split('=', 1)
                    env_vars[key.strip()] = value.strip()
        
        # 복호화할 키들 찾기
        decrypted_count = 0
        for key, value in env_vars.items():
            if is_key_encrypted(value):
                decrypted_value = self.crypto.decrypt_string(value)
                if decrypted_value and decrypted_value != value:
                    env_vars[key] = decrypted_value
                    decrypted_count += 1
                    print(f"🔓 {key} 복호화 완료")
        
        if decrypted_count > 0:
            # 복호화된 내용을 파일에 저장
            output_path = f"{self.env_file_path}.decrypted"
            with open(output_path, 'w') as f:
                for key, value in env_vars.items():
                    f.write(f"{key}={value}\n")
            
            print(f"✅ {decrypted_count}개 키가 복호화되어 {output_path}에 저장되었습니다.")
            print("⚠️ 보안상 복호화된 파일은 사용 후 삭제하세요.")
        else:
            print("ℹ️ 복호화할 암호화된 키가 없습니다.")
    
    def verify_keys(self):
        """키 암호화/복호화 검증"""
        if not self.crypto.is_available():
            print("❌ 암호화 시스템을 사용할 수 없습니다.")
            return
        
        print("🔍 API 키 검증 중...")
        
        if not os.path.exists(self.env_file_path):
            print(f"❌ 환경 파일을 찾을 수 없습니다: {self.env_file_path}")
            return
        
        # 환경 파일 읽기
        env_vars = {}
        with open(self.env_file_path, 'r') as f:
            for line in f:
                line = line.strip()
                if '=' in line and not line.startswith('#'):
                    key, value = line.split('=', 1)
                    env_vars[key.strip()] = value.strip()
        
        # 키 상태 확인
        key_status = {}
        keys_to_check = [
            'BITGET_API_KEY',
            'BITGET_SECRET_KEY', 
            'BITGET_PASSPHRASE',
            'OPENAI_API_KEY',
            'TELEGRAM_BOT_TOKEN',
            'TELEGRAM_CHAT_ID'
        ]
        
        for key in keys_to_check:
            if key in env_vars and env_vars[key]:
                value = env_vars[key]
                if is_key_encrypted(value):
                    # 복호화 테스트
                    decrypted = self.crypto.decrypt_string(value)
                    if decrypted and decrypted != value:
                        key_status[key] = "🔐 암호화됨 (정상)"
                    else:
                        key_status[key] = "❌ 암호화됨 (복호화 실패)"
                else:
                    key_status[key] = "🔓 평문 (보안 위험)"
            else:
                key_status[key] = "❌ 누락"
        
        # 결과 출력
        print("\n📊 API 키 상태:")
        print("=" * 40)
        for key, status in key_status.items():
            print(f"{key}: {status}")
        
        # 권장사항
        unencrypted_keys = [k for k, v in key_status.items() if "평문" in v]
        if unencrypted_keys:
            print(f"\n⚠️ 보안 권장: 다음 키들을 암호화하세요: {', '.join(unencrypted_keys)}")


def main():
    """메인 함수"""
    print("🔐 GPTBITCOIN API 키 관리 도구")
    print("=" * 50)
    
    manager = KeyManager()
    
    while True:
        print("\n📋 메뉴:")
        print("1. 마스터 키 설정")
        print("2. API 키 암호화")
        print("3. API 키 복호화 (개발용)")
        print("4. 키 상태 확인")
        print("5. 종료")
        
        choice = input("\n선택 (1-5): ").strip()
        
        if choice == "1":
            manager.setup_master_key()
        elif choice == "2":
            manager.encrypt_env_file()
        elif choice == "3":
            confirm = input("⚠️ 복호화된 키가 파일에 저장됩니다. 계속하시겠습니까? (y/n): ")
            if confirm.lower() == 'y':
                manager.decrypt_env_file()
        elif choice == "4":
            manager.verify_keys()
        elif choice == "5":
            print("👋 종료합니다.")
            break
        else:
            print("잘못된 선택입니다.")


if __name__ == "__main__":
    main()
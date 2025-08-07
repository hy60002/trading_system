"""
암호화 유틸리티 모듈
API 키 등 민감한 정보의 안전한 저장을 위한 암호화/복호화 기능
"""

import os
import base64
import logging
from typing import Optional, Union
from cryptography.fernet import Fernet
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC


class CryptoUtils:
    """암호화/복호화 유틸리티 클래스"""
    
    def __init__(self, master_key: Optional[str] = None):
        self.logger = logging.getLogger(__name__)
        self._fernet = None
        
        # 마스터 키 설정 (환경변수 또는 파라미터)
        if master_key:
            self._init_fernet(master_key)
        else:
            # 환경변수에서 마스터 키 조회
            env_key = os.getenv('TRADING_SYSTEM_MASTER_KEY')
            if env_key:
                self._init_fernet(env_key)
            else:
                self.logger.warning("마스터 키가 설정되지 않았습니다. 암호화 기능을 사용할 수 없습니다.")
    
    def _init_fernet(self, master_key: str):
        """Fernet 암호화 객체 초기화"""
        try:
            # 마스터 키를 기반으로 암호화 키 생성
            password = master_key.encode()
            salt = b'trading_system_salt_2024'  # 고정 솔트 (프로덕션에서는 랜덤 생성 권장)
            
            kdf = PBKDF2HMAC(
                algorithm=hashes.SHA256(),
                length=32,
                salt=salt,
                iterations=100000,
            )
            key = base64.urlsafe_b64encode(kdf.derive(password))
            self._fernet = Fernet(key)
            self.logger.info("✅ 암호화 시스템 초기화 완료")
            
        except Exception as e:
            self.logger.error(f"❌ 암호화 시스템 초기화 실패: {e}")
            self._fernet = None
    
    def encrypt_string(self, plaintext: str) -> Optional[str]:
        """문자열 암호화"""
        if not self._fernet:
            self.logger.warning("암호화 시스템이 초기화되지 않았습니다")
            return None
        
        try:
            if not plaintext:
                return plaintext
            
            # 문자열을 바이트로 변환 후 암호화
            encrypted_bytes = self._fernet.encrypt(plaintext.encode('utf-8'))
            # Base64로 인코딩하여 문자열로 반환
            encrypted_string = base64.urlsafe_b64encode(encrypted_bytes).decode('utf-8')
            
            return f"ENCRYPTED:{encrypted_string}"
            
        except Exception as e:
            self.logger.error(f"문자열 암호화 실패: {e}")
            return None
    
    def decrypt_string(self, encrypted_string: str) -> Optional[str]:
        """문자열 복호화"""
        if not self._fernet:
            self.logger.warning("암호화 시스템이 초기화되지 않았습니다")
            return encrypted_string  # 암호화되지 않은 값으로 간주하고 반환
        
        try:
            if not encrypted_string:
                return encrypted_string
            
            # 암호화된 문자열인지 확인
            if not encrypted_string.startswith('ENCRYPTED:'):
                # 암호화되지 않은 평문으로 간주
                return encrypted_string
            
            # ENCRYPTED: 접두사 제거
            encrypted_data = encrypted_string[10:]  # len('ENCRYPTED:') = 10
            
            # Base64 디코딩
            encrypted_bytes = base64.urlsafe_b64decode(encrypted_data.encode('utf-8'))
            
            # 복호화
            decrypted_bytes = self._fernet.decrypt(encrypted_bytes)
            decrypted_string = decrypted_bytes.decode('utf-8')
            
            return decrypted_string
            
        except Exception as e:
            self.logger.error(f"문자열 복호화 실패: {e}")
            # 복호화 실패 시 원본 문자열 반환 (하위 호환성)
            return encrypted_string
    
    def is_encrypted(self, value: str) -> bool:
        """문자열이 암호화되었는지 확인"""
        return isinstance(value, str) and value.startswith('ENCRYPTED:')
    
    def encrypt_dict(self, data: dict, keys_to_encrypt: list) -> dict:
        """딕셔너리의 특정 키들을 암호화"""
        if not self._fernet:
            return data
        
        encrypted_data = data.copy()
        
        for key in keys_to_encrypt:
            if key in encrypted_data and encrypted_data[key]:
                encrypted_value = self.encrypt_string(str(encrypted_data[key]))
                if encrypted_value:
                    encrypted_data[key] = encrypted_value
        
        return encrypted_data
    
    def decrypt_dict(self, data: dict, keys_to_decrypt: list) -> dict:
        """딕셔너리의 특정 키들을 복호화"""
        if not self._fernet:
            return data
        
        decrypted_data = data.copy()
        
        for key in keys_to_decrypt:
            if key in decrypted_data and decrypted_data[key]:
                decrypted_value = self.decrypt_string(str(decrypted_data[key]))
                if decrypted_value:
                    decrypted_data[key] = decrypted_value
        
        return decrypted_data
    
    @staticmethod
    def generate_master_key() -> str:
        """새로운 마스터 키 생성"""
        return base64.urlsafe_b64encode(os.urandom(32)).decode('utf-8')
    
    def is_available(self) -> bool:
        """암호화 기능 사용 가능 여부 확인"""
        return self._fernet is not None


# 전역 인스턴스 (지연 초기화)
_crypto_instance = None


def get_crypto_utils() -> CryptoUtils:
    """CryptoUtils 싱글톤 인스턴스 반환"""
    global _crypto_instance
    if _crypto_instance is None:
        _crypto_instance = CryptoUtils()
    return _crypto_instance


def encrypt_api_key(api_key: str) -> str:
    """API 키 암호화 (편의 함수)"""
    crypto = get_crypto_utils()
    if crypto.is_available():
        encrypted = crypto.encrypt_string(api_key)
        return encrypted if encrypted else api_key
    return api_key


def decrypt_api_key(encrypted_key: str) -> str:
    """API 키 복호화 (편의 함수)"""
    crypto = get_crypto_utils()
    return crypto.decrypt_string(encrypted_key)


def is_key_encrypted(key: str) -> bool:
    """키가 암호화되었는지 확인 (편의 함수)"""
    crypto = get_crypto_utils()
    return crypto.is_encrypted(key)


# 사용 예시 및 테스트 함수
def test_crypto_utils():
    """암호화 유틸리티 테스트"""
    import logging
    logging.basicConfig(level=logging.INFO)
    
    # 테스트용 마스터 키
    test_master_key = CryptoUtils.generate_master_key()
    print(f"생성된 마스터 키: {test_master_key}")
    
    # 암호화 유틸리티 초기화
    crypto = CryptoUtils(test_master_key)
    
    # 테스트 데이터
    test_api_key = "test_api_key_12345"
    test_secret = "test_secret_67890"
    
    # 암호화 테스트
    encrypted_key = crypto.encrypt_string(test_api_key)
    encrypted_secret = crypto.encrypt_string(test_secret)
    
    print(f"원본 API 키: {test_api_key}")
    print(f"암호화된 API 키: {encrypted_key}")
    
    # 복호화 테스트
    decrypted_key = crypto.decrypt_string(encrypted_key)
    decrypted_secret = crypto.decrypt_string(encrypted_secret)
    
    print(f"복호화된 API 키: {decrypted_key}")
    
    # 검증
    assert test_api_key == decrypted_key, "API 키 암호화/복호화 실패"
    assert test_secret == decrypted_secret, "Secret 암호화/복호화 실패"
    
    print("✅ 모든 테스트 통과")


if __name__ == "__main__":
    test_crypto_utils()
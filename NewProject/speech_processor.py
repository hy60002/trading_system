"""
음성 처리 모듈 (STT/TTS)
Google Speech-to-Text, Text-to-Speech API 연동
"""

import speech_recognition as sr
import requests
import tempfile
import os
from gtts import gTTS
from pydub import AudioSegment
import openai
from loguru import logger
from typing import Optional

class SpeechProcessor:
    """음성 인식 및 합성 처리 클래스"""
    
    def __init__(self):
        self.recognizer = sr.Recognizer()
        openai.api_key = os.getenv("OPENAI_API_KEY")
        logger.info("음성 처리 모듈 초기화 완료")
    
    async def speech_to_text(self, audio_url: str) -> Optional[str]:
        """
        음성을 텍스트로 변환 (STT)
        
        Args:
            audio_url: Twilio 녹음 파일 URL
            
        Returns:
            변환된 텍스트 또는 None
        """
        try:
            logger.info(f"STT 처리 시작: {audio_url}")
            
            # 1. Twilio에서 오디오 파일 다운로드
            audio_data = await self._download_audio(audio_url)
            if not audio_data:
                return None
            
            # 2. 오디오 형식 변환 (필요시)
            processed_audio = self._preprocess_audio(audio_data)
            
            # 3. Google Speech-to-Text 또는 OpenAI Whisper 사용
            text = await self._transcribe_audio(processed_audio)
            
            logger.info(f"STT 결과: {text}")
            return text
            
        except Exception as e:
            logger.error(f"STT 처리 오류: {e}")
            return None
    
    async def _download_audio(self, audio_url: str) -> Optional[bytes]:
        """Twilio 오디오 파일 다운로드"""
        try:
            # Twilio 인증 필요
            auth = (
                os.getenv("TWILIO_ACCOUNT_SID"),
                os.getenv("TWILIO_AUTH_TOKEN")
            )
            
            response = requests.get(audio_url, auth=auth)
            response.raise_for_status()
            
            return response.content
            
        except Exception as e:
            logger.error(f"오디오 다운로드 오류: {e}")
            return None
    
    def _preprocess_audio(self, audio_data: bytes) -> bytes:
        """오디오 전처리 (형식 변환, 노이즈 제거 등)"""
        try:
            # 임시 파일에 저장
            with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as temp_file:
                temp_file.write(audio_data)
                temp_path = temp_file.name
            
            # pydub으로 오디오 처리
            audio = AudioSegment.from_file(temp_path)
            
            # WAV 형식으로 변환, 샘플레이트 조정
            audio = audio.set_frame_rate(16000)  # 16kHz
            audio = audio.set_channels(1)        # 모노
            
            # 처리된 오디오를 바이트로 변환
            processed_path = temp_path.replace(".wav", "_processed.wav")
            audio.export(processed_path, format="wav")
            
            with open(processed_path, "rb") as f:
                processed_data = f.read()
            
            # 임시 파일 정리
            os.unlink(temp_path)
            os.unlink(processed_path)
            
            return processed_data
            
        except Exception as e:
            logger.error(f"오디오 전처리 오류: {e}")
            return audio_data  # 원본 반환
    
    async def _transcribe_audio(self, audio_data: bytes) -> Optional[str]:
        """오디오를 텍스트로 변환"""
        try:
            # 방법 1: OpenAI Whisper (추천)
            if os.getenv("OPENAI_API_KEY"):
                return await self._whisper_transcribe(audio_data)
            
            # 방법 2: Google Speech-to-Text (대체)
            else:
                return await self._google_stt_transcribe(audio_data)
                
        except Exception as e:
            logger.error(f"음성 인식 오류: {e}")
            return None
    
    async def _whisper_transcribe(self, audio_data: bytes) -> Optional[str]:
        """OpenAI Whisper API 사용"""
        try:
            # 임시 파일로 저장
            with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as temp_file:
                temp_file.write(audio_data)
                temp_path = temp_file.name
            
            # Whisper API 호출
            with open(temp_path, "rb") as audio_file:
                transcript = openai.Audio.transcribe(
                    model="whisper-1",
                    file=audio_file,
                    language="ko"  # 한국어 지정
                )
            
            # 임시 파일 정리
            os.unlink(temp_path)
            
            return transcript.text
            
        except Exception as e:
            logger.error(f"Whisper API 오류: {e}")
            return None
    
    async def _google_stt_transcribe(self, audio_data: bytes) -> Optional[str]:
        """Google Speech-to-Text 사용 (대체 방안)"""
        try:
            # 임시 파일로 저장
            with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as temp_file:
                temp_file.write(audio_data)
                temp_path = temp_file.name
            
            # SpeechRecognition 라이브러리 사용
            with sr.AudioFile(temp_path) as source:
                audio = self.recognizer.record(source)
            
            # Google STT API 호출
            text = self.recognizer.recognize_google(
                audio, 
                language='ko-KR'
            )
            
            # 임시 파일 정리
            os.unlink(temp_path)
            
            return text
            
        except sr.UnknownValueError:
            logger.warning("음성을 인식할 수 없습니다")
            return None
        except sr.RequestError as e:
            logger.error(f"Google STT API 오류: {e}")
            return None
    
    def text_to_speech(self, text: str, lang: str = 'ko') -> Optional[bytes]:
        """
        텍스트를 음성으로 변환 (TTS)
        
        Args:
            text: 변환할 텍스트
            lang: 언어 코드 (기본값: 'ko')
            
        Returns:
            MP3 오디오 데이터 또는 None
        """
        try:
            logger.info(f"TTS 처리: {text[:50]}...")
            
            # Google Text-to-Speech 사용
            tts = gTTS(
                text=text,
                lang=lang,
                slow=False  # 자연스러운 속도
            )
            
            # 메모리 버퍼에 저장
            with tempfile.NamedTemporaryFile(suffix=".mp3", delete=False) as temp_file:
                tts.save(temp_file.name)
                
                with open(temp_file.name, "rb") as f:
                    audio_data = f.read()
                
                # 임시 파일 정리
                os.unlink(temp_file.name)
            
            logger.info("TTS 처리 완료")
            return audio_data
            
        except Exception as e:
            logger.error(f"TTS 처리 오류: {e}")
            return None
    
    def enhance_speech_recognition(self, text: str) -> str:
        """
        음성 인식 결과 후처리 및 개선
        
        Args:
            text: 원본 인식 텍스트
            
        Returns:
            개선된 텍스트
        """
        if not text:
            return text
        
        # 일반적인 음성 인식 오류 수정
        corrections = {
            # 음식 관련
            "치킨": ["치킨", "치킴", "치긴", "칰킨"],
            "피자": ["피자", "피져", "삐자"],
            "짜장면": ["짜장면", "자장면", "짜잠면"],
            "탕수육": ["탕수육", "땅수육", "탕슈육"],
            
            # 숫자 관련
            "하나": ["하나", "한개", "1개"],
            "둘": ["둘", "두개", "2개"],
            "셋": ["셋", "세개", "3개"],
            
            # 일반적인 표현
            "배달": ["배달", "배송", "딜리버리"],
            "주문": ["주문", "시켜", "주문해"],
        }
        
        # 오타 수정 적용
        corrected_text = text
        for correct, variants in corrections.items():
            for variant in variants:
                if variant in corrected_text and variant != correct:
                    corrected_text = corrected_text.replace(variant, correct)
        
        return corrected_text.strip()

# 전역 인스턴스
speech_processor = SpeechProcessor()
"""
AI 배달 도우미 메인 애플리케이션
전화를 통한 AI 기반 음식 주문 시스템
"""

from fastapi import FastAPI, Request, Form
from fastapi.responses import Response
import uvicorn
from twilio.twiml import VoiceResponse
from twilio.rest import Client
import os
from dotenv import load_dotenv
from loguru import logger
import asyncio

# 환경 변수 로드
load_dotenv()

# FastAPI 앱 초기화
app = FastAPI(title="AI 배달 도우미", version="1.0.0")

# Twilio 클라이언트 초기화
twilio_client = Client(
    os.getenv("TWILIO_ACCOUNT_SID"),
    os.getenv("TWILIO_AUTH_TOKEN")
)

# 전역 변수로 통화 세션 관리
call_sessions = {}

class AIDeliveryAssistant:
    """AI 배달 도우미 메인 클래스"""
    
    def __init__(self):
        self.logger = logger
        self.setup_logging()
    
    def setup_logging(self):
        """로깅 설정"""
        logger.add("logs/ai_delivery.log", rotation="1 MB", level="INFO")
        logger.info("AI 배달 도우미 시스템 시작")
    
    async def handle_incoming_call(self, call_sid: str, from_number: str):
        """수신 전화 처리"""
        logger.info(f"새로운 전화 수신: {from_number} (Call SID: {call_sid})")
        
        # 세션 초기화
        call_sessions[call_sid] = {
            'phone_number': from_number,
            'conversation_history': [],
            'order_info': {},
            'step': 'greeting'
        }
        
        return self.generate_greeting_response()
    
    def generate_greeting_response(self):
        """인사말 응답 생성"""
        greeting_text = """
        안녕하세요! AI 배달 도우미입니다. 
        오늘 무엇을 드시고 싶으신가요? 
        천천히 말씀해주세요.
        """
        
        response = VoiceResponse()
        response.say(greeting_text, language='ko-KR', voice='woman')
        
        # 사용자 응답 대기 (음성 입력 받기)
        response.record(
            timeout=10,
            max_length=30,
            action='/process_speech',
            method='POST'
        )
        
        return str(response)
    
    async def process_user_speech(self, call_sid: str, recording_url: str):
        """사용자 음성 처리"""
        logger.info(f"음성 처리 시작: {call_sid}")
        
        try:
            # 1. 음성을 텍스트로 변환 (STT)
            user_text = await self.speech_to_text(recording_url)
            logger.info(f"사용자 음성: {user_text}")
            
            # 2. AI 응답 생성
            ai_response = await self.generate_ai_response(call_sid, user_text)
            logger.info(f"AI 응답: {ai_response}")
            
            # 3. 응답을 음성으로 변환하여 전송
            return self.create_voice_response(ai_response)
            
        except Exception as e:
            logger.error(f"음성 처리 오류: {e}")
            return self.create_error_response()
    
    async def speech_to_text(self, recording_url: str) -> str:
        """음성을 텍스트로 변환 (STT)"""
        # TODO: Google STT 또는 OpenAI Whisper 연동
        # 현재는 더미 응답
        return "치킨 주문하고 싶어요"
    
    async def generate_ai_response(self, call_sid: str, user_input: str) -> str:
        """AI 응답 생성 (GPT 연동)"""
        session = call_sessions.get(call_sid, {})
        
        # TODO: OpenAI GPT-4 연동
        # 현재는 간단한 규칙 기반 응답
        if "치킨" in user_input:
            response = "치킨 주문이시군요! 후라이드 치킨과 양념 치킨 중 어떤 것을 드시겠어요?"
            session['step'] = 'menu_selection'
        elif "후라이드" in user_input:
            response = "후라이드 치킨 한 마리 맞죠? 어디로 배달해드릴까요?"
            session['step'] = 'address_input'
        elif "양념" in user_input:
            response = "양념 치킨 한 마리 맞죠? 어디로 배달해드릴까요?"
            session['step'] = 'address_input'
        else:
            response = "죄송해요, 다시 한 번 말씀해주시겠어요? 어떤 음식을 주문하고 싶으신가요?"
        
        # 대화 히스토리 저장
        session['conversation_history'].append({
            'user': user_input,
            'ai': response
        })
        
        return response
    
    def create_voice_response(self, text: str) -> str:
        """텍스트를 음성 응답으로 변환"""
        response = VoiceResponse()
        response.say(text, language='ko-KR', voice='woman')
        
        # 다음 사용자 입력 대기
        response.record(
            timeout=10,
            max_length=30,
            action='/process_speech',
            method='POST'
        )
        
        return str(response)
    
    def create_error_response(self) -> str:
        """오류 응답 생성"""
        response = VoiceResponse()
        response.say(
            "죄송합니다. 기술적인 문제가 발생했습니다. 잠시 후 다시 시도해주세요.",
            language='ko-KR',
            voice='woman'
        )
        return str(response)

# AI 도우미 인스턴스 생성
ai_assistant = AIDeliveryAssistant()

@app.get("/")
async def root():
    """메인 페이지"""
    return {
        "message": "AI 배달 도우미 서비스", 
        "status": "운영 중",
        "version": "1.0.0"
    }

@app.post("/voice")
async def handle_voice(request: Request):
    """Twilio 음성 통화 웹훅 처리"""
    form_data = await request.form()
    call_sid = form_data.get('CallSid')
    from_number = form_data.get('From')
    
    logger.info(f"음성 통화 수신: {from_number}")
    
    # 새로운 통화 처리
    response_xml = await ai_assistant.handle_incoming_call(call_sid, from_number)
    
    return Response(content=response_xml, media_type="application/xml")

@app.post("/process_speech")
async def process_speech(request: Request):
    """사용자 음성 입력 처리"""
    form_data = await request.form()
    call_sid = form_data.get('CallSid')
    recording_url = form_data.get('RecordingUrl')
    
    logger.info(f"음성 녹음 처리: {call_sid}")
    
    # 음성 처리 및 응답 생성
    response_xml = await ai_assistant.process_user_speech(call_sid, recording_url)
    
    return Response(content=response_xml, media_type="application/xml")

@app.get("/call_status/{call_sid}")
async def get_call_status(call_sid: str):
    """통화 상태 조회"""
    session = call_sessions.get(call_sid)
    if session:
        return {
            "call_sid": call_sid,
            "status": "active",
            "conversation_history": session['conversation_history'],
            "current_step": session['step']
        }
    else:
        return {"error": "세션을 찾을 수 없습니다"}

@app.post("/make_test_call")
async def make_test_call(phone_number: str):
    """테스트 전화 발신"""
    try:
        call = twilio_client.calls.create(
            to=phone_number,
            from_=os.getenv("TWILIO_PHONE_NUMBER"),
            url="https://your-server.com/voice"  # 실제 서버 URL로 변경 필요
        )
        
        return {
            "success": True,
            "call_sid": call.sid,
            "message": f"{phone_number}로 테스트 전화를 발신했습니다"
        }
    except Exception as e:
        logger.error(f"전화 발신 오류: {e}")
        return {"success": False, "error": str(e)}

if __name__ == "__main__":
    # 서버 실행
    logger.info("AI 배달 도우미 서버 시작...")
    uvicorn.run(
        "main:app", 
        host=os.getenv("HOST", "localhost"), 
        port=int(os.getenv("PORT", 8000)),
        reload=True
    )
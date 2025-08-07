# API 키 설정 완전 가이드

## 🔑 필요한 API 키 목록

1. **Twilio** (전화 수신/발신)
2. **OpenAI** (GPT-4 대화)
3. **Google Cloud** (음성 처리) - 선택사항

---

## 1️⃣ Twilio 설정 (필수)

### 계정 생성
1. [Twilio 공식 사이트](https://www.twilio.com) 접속
2. "Sign up for free" 클릭
3. 이메일, 비밀번호 입력
4. 휴대폰 번호 인증

### API 키 획득
1. 대시보드 → "Account" → "API keys & tokens"
2. 다음 정보 복사:
   ```
   Account SID: ACxxxxxxxxxxxxxxxxx
   Auth Token: xxxxxxxxxxxxxxxx
   ```

### 전화번호 구매 (월 $1.15)
1. "Phone Numbers" → "Manage" → "Buy a number"
2. 한국(+82) 번호 선택
3. Voice 기능 활성화된 번호 구매

### 웹훅 설정
1. 구매한 번호 클릭
2. "Voice & Fax" 섹션에서:
   - Webhook: `https://your-domain.com/voice`
   - HTTP Method: POST

---

## 2️⃣ OpenAI 설정 (필수)

### 계정 생성 및 결제
1. [OpenAI Platform](https://platform.openai.com) 접속
2. "Sign up" 또는 "Log in"
3. Billing → "Add payment method"에서 카드 등록

### API 키 생성
1. "API keys" 메뉴 클릭
2. "Create new secret key" 버튼
3. 키 이름 입력 (예: "AI-Delivery-Assistant")
4. 생성된 키 복사: `sk-proj-xxxxxxxxxxxxxx`

### 사용량 제한 설정 (권장)
1. "Usage limits" 메뉴
2. Monthly budget: $50 설정 (초기 테스트용)

---

## 3️⃣ Google Cloud 설정 (선택사항)

OpenAI Whisper 대신 Google STT/TTS 사용시에만 필요

### 프로젝트 생성
1. [Google Cloud Console](https://console.cloud.google.com) 접속
2. 새 프로젝트 생성
3. "Speech-to-Text API" 및 "Text-to-Speech API" 활성화

### 서비스 계정 키 생성
1. "IAM & Admin" → "Service Accounts"
2. "Create Service Account"
3. JSON 키 파일 다운로드

---

## 4️⃣ 환경 변수 설정

`.env` 파일을 생성하고 다음과 같이 입력:

```bash
# Twilio 설정
TWILIO_ACCOUNT_SID=ACxxxxxxxxxxxxxxxxx
TWILIO_AUTH_TOKEN=your_auth_token_here
TWILIO_PHONE_NUMBER=+821012345678

# OpenAI 설정
OPENAI_API_KEY=sk-proj-xxxxxxxxxxxxxx

# Google Cloud 설정 (선택사항)
GOOGLE_APPLICATION_CREDENTIALS=path/to/google-credentials.json

# 서버 설정
HOST=localhost
PORT=8000
ENVIRONMENT=development
```

---

## 5️⃣ 테스트 준비

### 패키지 설치
```bash
pip install -r requirements.txt
```

### ngrok 설치 (로컬 테스트용)
1. [ngrok 다운로드](https://ngrok.com/download)
2. 압축 해제 후 PATH에 추가
3. 무료 계정 가입

### 로컬 서버 외부 노출
```bash
# 터미널 1: 서버 실행
python main.py

# 터미널 2: ngrok으로 터널링
ngrok http 8000
```

ngrok에서 제공하는 HTTPS URL을 Twilio 웹훅에 설정

---

## 💰 예상 비용

### 초기 설정 비용
- Twilio 전화번호: $1.15/월
- OpenAI 크레딧: $5 (테스트용)
- **총 초기 비용: 약 $6.15**

### 월간 운영 비용 (100통화 기준)
- Twilio 통화: $3
- OpenAI GPT-4: $5
- Google STT/TTS: $1.5
- **총 월간 비용: 약 $9.5 (약 13,000원)**

---

## ⚡ 빠른 시작 체크리스트

- [ ] Twilio 계정 생성 및 전화번호 구매
- [ ] OpenAI 계정 생성 및 API 키 발급
- [ ] `.env` 파일 작성
- [ ] `pip install -r requirements.txt` 실행
- [ ] `python test_system.py` 테스트 실행
- [ ] ngrok 설치 및 터널링 설정
- [ ] Twilio 웹훅 URL 설정
- [ ] 첫 번째 테스트 전화!

---

## 🆘 문제 해결

### 자주 발생하는 오류

**1. Twilio 인증 오류**
```
TwilioRestException: Unable to create record
```
→ Account SID와 Auth Token 재확인

**2. OpenAI API 오류**
```
openai.error.AuthenticationError
```
→ API 키 재확인 및 결제 정보 확인

**3. 음성 파일 처리 오류**
```
pydub.exceptions.CouldntDecodeError
```
→ ffmpeg 설치 필요: `pip install pydub[mp3]`

---

현재 어떤 단계까지 진행하셨나요? 
각 단계별로 자세히 도움드리겠습니다!
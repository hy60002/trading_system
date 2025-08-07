# 🔑 API 키 설정 단계별 가이드

## 현재 상태
✅ 기본 시스템 구조 완성  
✅ .env 파일 생성 완료  
⚠️ **API 키 설정 필요** ← 현재 단계

---

## 🚀 즉시 필요한 작업

### 1단계: Twilio 계정 생성 (5분)

**📱 휴대폰으로 즉시 가능**

1. **Twilio 가입**
   - 브라우저에서 [www.twilio.com](https://www.twilio.com) 접속
   - "Start for free" 클릭
   - 이메일, 비밀번호 입력
   - 휴대폰 번호로 인증

2. **전화번호 구매** (월 $1.15, 약 1,500원)
   - 대시보드 → "Phone Numbers" → "Buy a number"
   - 국가: South Korea (+82) 선택
   - Voice 기능 포함된 번호 구매

3. **API 키 복사**
   - Account Dashboard에서 다음 정보 복사:
   ```
   Account SID: ACxxxxxxxxxxxxxxxxx
   Auth Token: xxxxxxxxxxxxxxxx
   Phone Number: +821012345678
   ```

### 2단계: OpenAI 계정 설정 (5분)

1. **OpenAI 가입**
   - [platform.openai.com](https://platform.openai.com) 접속
   - "Sign up" 클릭
   - 구글/이메일 계정으로 가입

2. **결제 정보 등록** (필수)
   - Billing → "Add payment method"
   - 신용카드 정보 입력
   - $5 정도 충전 (테스트용)

3. **API 키 생성**
   - "API keys" 메뉴 클릭
   - "Create new secret key" 버튼
   - 키 이름: "AI-Delivery-Assistant"
   - 생성된 키 복사: `sk-proj-xxxxxxxxxxxxxx`

### 3단계: .env 파일 수정

**C:\GPTBITCOIN\NewProject\.env** 파일을 열어서 다음과 같이 수정:

```bash
# Twilio 설정 (1단계에서 얻은 정보)
TWILIO_ACCOUNT_SID=AC여기에_실제_Account_SID_입력
TWILIO_AUTH_TOKEN=여기에_실제_Auth_Token_입력
TWILIO_PHONE_NUMBER=+821012345678

# OpenAI 설정 (2단계에서 얻은 정보)
OPENAI_API_KEY=sk-proj-여기에_실제_API_키_입력

# 나머지는 그대로 유지
HOST=localhost
PORT=8000
ENVIRONMENT=development
```

---

## ⚡ 빠른 테스트 (API 키 설정 후)

### 1. 기본 시스템 테스트
```bash
cd NewProject
python test_system.py
```

### 2. 서버 시작
```bash
python main.py
```

### 3. 외부 접속 설정 (별도 터미널)
```bash
# ngrok 설치 후
ngrok http 8000
```

### 4. Twilio 웹훅 설정
- Twilio 콘솔 → 구매한 전화번호 클릭
- Voice URL: `https://your-ngrok-url.ngrok.io/voice`
- HTTP Method: POST

---

## 💰 예상 비용

### 초기 설정
- Twilio 전화번호: $1.15/월 (약 1,500원)
- OpenAI 크레딧: $5 (약 7,000원, 테스트용)
- **총 초기 비용: $6.15 (약 8,500원)**

### 실제 사용 (100통화/월 기준)
- Twilio 통화료: $3/월
- OpenAI GPT-4: $5/월  
- **총 운영비용: $8/월 (약 11,000원)**

---

## 🎯 완료 후 가능한 기능

✅ **실제 전화 수신**: 구매한 번호로 전화 걸면 AI가 응답  
✅ **음성 인식**: 말한 내용을 텍스트로 변환  
✅ **자연스러운 대화**: GPT-4가 친근하게 응답  
✅ **주문 처리**: 메뉴 선택부터 배달까지 완전 자동화  
✅ **고객 기억**: 이전 주문 내역 저장 및 재주문 기능  

---

## 🆘 문제 발생시

### API 키 관련 오류
```
openai.error.AuthenticationError
```
→ OpenAI API 키 재확인 및 결제 정보 확인

### Twilio 연결 오류  
```
TwilioRestException: Unable to create record
```
→ Account SID와 Auth Token 재확인

### 서버 접속 안됨
→ ngrok 실행 확인 및 방화벽 설정 확인

---

## 📞 즉시 도움

**어려운 부분이 있으시면:**
1. 스크린샷과 함께 오류 메시지 공유
2. 어떤 단계에서 막혔는지 알려주세요
3. 단계별로 함께 진행하겠습니다

**목표: 오늘 내로 첫 번째 AI 전화 통화 성공! 🎉**
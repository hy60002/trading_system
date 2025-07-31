import requests

# 설정값
BOT_TOKEN = "7672620251:AAHVZF42sJZ-Ji4JnpGA8OOIvJrfTs2KN6s"  # BotFather에서 받은 토큰
CHAT_ID = "7269738695"  # 확인한 10자리 숫자 입력
MESSAGE = "자동매매 시스템 테스트 메시지"

# API 요청 URL
url = f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage"
params = {"chat_id": CHAT_ID, "text": MESSAGE}

# 메시지 전송
response = requests.get(url, params=params)

# 결과 출력
print(response.json())  # 응답 확인

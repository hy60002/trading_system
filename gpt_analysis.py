import os
import openai
import pandas as pd
import json
import time
import requests
import schedule
from dotenv import load_dotenv

# 📌 환경 변수 로드
load_dotenv()
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID")

# 📌 GPT 로그 파일 경로
LOG_FILE = "gpt_log.txt"

# 📌 OpenAI API 클라이언트 객체 생성 (최신 API 방식)
client = openai.OpenAI(api_key=OPENAI_API_KEY)

# 📌 텔레그램 메시지 전송 함수
def send_telegram_message(message):
    """텔레그램 + 콘솔에 메시지를 보내는 함수"""
    url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"
    params = {"chat_id": TELEGRAM_CHAT_ID, "text": message}
    try:
        response = requests.get(url, params=params)
        print("텔레그램 응답:", response.json())  # 정상 실행 여부 확인
    except Exception as e:
        print(f"⚠️ 텔레그램 전송 오류: {e}")
    print(message)  # 콘솔에도 출력

# 📌 GPT 분석 결과를 로그 파일에 저장하는 함수
def log_gpt_result(gpt_text):
    """GPT 분석 결과를 gpt_log.txt 파일에 기록하는 함수"""
    try:
        with open(LOG_FILE, "a", encoding="utf-8") as f:
            timestamp = time.strftime("%Y-%m-%d %H:%M:%S")
            f.write(f"📊 {timestamp} - GPT 분석 결과\n{gpt_text}\n" + "="*50 + "\n")
    except Exception as e:
        print(f"🚨 GPT 로그 저장 오류: {e}")

# 📌 최근 2시간 매매 데이터 분석
def analyze_trade_data():
    try:
        df = pd.read_csv("trade_log.csv")
        df["timestamp"] = pd.to_datetime(df["timestamp"])

        # 최근 2시간 데이터 필터링
        last_2_hours = pd.Timestamp.now() - pd.Timedelta(hours=2)
        df_recent = df[df["timestamp"] > last_2_hours]

        total_trades = len(df_recent)
        if total_trades == 0:
            # 최근 2시간 거래가 없는 경우
            return "⚠️ 최근 2시간 동안 거래가 없습니다. 기존 전략 유지가 필요할 수 있습니다."

        # profit_loss 대신 return_pct 컬럼 사용
        win_trades = len(df_recent[df_recent["return_pct"] > 0])
        lose_trades = len(df_recent[df_recent["return_pct"] < 0])
        win_rate = (win_trades / total_trades) * 100 if total_trades > 0 else 0
        avg_profit = df_recent["return_pct"].mean() if total_trades > 0 else 0

        summary = f"""
        📊 **최근 2시간 매매 요약**
        - 총 거래 횟수: {total_trades}
        - 승리 횟수: {win_trades}
        - 패배 횟수: {lose_trades}
        - 승률: {win_rate:.2f}%
        - 평균 손익: {avg_profit:.3f} (return_pct 기준)
        """
        return summary.strip()
    
    except Exception as e:
        return f"⚠️ 데이터 분석 오류: {e}"

# 📌 GPT-4에게 전략 수정 요청 (최신 API 방식 적용)
def get_gpt_analysis(summary):
    """
    GPT-4에게 매매 성과를 분석 요청 및 전략 개선점 요청
    (최신 OpenAI API 적용: client.chat.completions.create 사용)
    """
    # 거래 데이터가 없는 경우에 대한 추가 처리
    if "거래가 없습니다" in summary:
        prompt = f"최근 2시간 동안 거래가 없었습니다. {summary}\n새로운 전략이 필요할까요?"
    else:
        prompt = f"""
        최근 2시간 동안의 매매 성과를 분석하고, 자동매매 전략을 개선할 수 있는 조언을 주세요.

        {summary}

        - 현재 전략: RSI 30 이하 롱, 70 이상 숏
        - 손절 -0.5%, 익절 +0.75%
        - VWAP 이탈 0.5% 기준 사용
        - 매매 빈도 적절한지 평가
        - 새로운 매매 전략을 제안해주세요.
        """

    try:
        response = client.chat.completions.create(  # ✅ 최신 API 방식 적용
            model="gpt-4",
            messages=[{"role": "user", "content": prompt}]
        )
        return response.choices[0].message.content
    except Exception as e:
        return f"⚠️ GPT 분석 오류: {e}"

# 📌 새로운 전략 저장
def save_new_strategy(strategy_text):
    """GPT-4가 제공한 전략을 JSON 파일에 저장"""
    try:
        # 기본 전략 데이터
        strategy_data = {
            "vwap_deviation": 0.5,
            "rsi_long": 30,
            "rsi_short": 70,
            "stop_loss": 0.5,
            "take_profit": 0.75
        }
        # GPT의 답변에서 새로운 전략 정보를 추출하여 JSON에 반영 (예시)
        if "RSI" in strategy_text:
            if "RSI 32" in strategy_text:
                strategy_data["rsi_long"] = 32
            if "RSI 68" in strategy_text:
                strategy_data["rsi_short"] = 68

        with open("strategy.json", "w", encoding="utf-8") as f:
            json.dump(strategy_data, f, ensure_ascii=False, indent=4)
        return "✅ 새로운 전략이 저장되었습니다."
    
    except Exception as e:
        return f"⚠️ 전략 저장 오류: {e}"

# 📌 2시간마다 실행되는 자동 분석 & 전략 수정 함수
def analyze_and_update_strategy():
    """2시간마다 매매 분석 후 GPT-4에게 피드백 요청 & 전략 수정"""
    summary = analyze_trade_data()
    gpt_feedback = get_gpt_analysis(summary)
    strategy_result = save_new_strategy(gpt_feedback)

    message = (
        "📊 **최근 2시간 매매 분석 결과**\n\n"
        f"{summary}\n\n"
        f"💡 **GPT-4 분석:**\n{gpt_feedback}\n\n"
        f"🔄 {strategy_result}"
    )
    send_telegram_message(message)
    log_gpt_result(message)

# 🔹 실행 즉시 분석 실행
print("🚀 GPT 분석 시작: 즉시 실행 후 2시간마다 반복 실행")

# 즉시 한 번 실행
analyze_and_update_strategy()

# 2시간마다 반복 실행
schedule.every(2).hours.do(analyze_and_update_strategy)

while True:
    schedule.run_pending()
    time.sleep(60)  # 1분마다 실행 확인

import ollama
import json

# AI에게 매매 판단 요청
prompt = """
너는 비트코인 트레이딩 전문가야. 
다음과 같은 형식으로만 응답해.
{"decision": "buy" / "sell" / "hold", "reason": "설명"}
지금 비트코인을 매수해야 할까?
"""

# Ollama 실행
response = ollama.chat("mistral", messages=[{"role": "user", "content": prompt}])

# JSON 형식으로 변환
try:
    result = json.loads(response['message']['content'])
    print(f"AI 매매 판단: {result['decision']}")
    print(f"이유: {result['reason']}")
except json.JSONDecodeError:
    print("❌ AI 응답이 JSON 형식이 아닙니다. 다시 시도하세요.")


import whisper
import whisper.audio as wa

# Whisper가 실행파일을 현재 폴더에서 찾을 수 있도록 설정
wa.FFMPEG_PATH = "C:/GPTBITCOIN/ffmpeg.exe"

model = whisper.load_model("base")
result = model.transcribe("C:/GPTBITCOIN/mbs_clip.mp4")

print("\n📝 전체 자막 시작\n")
print(result["text"])
print("\n📝 전체 자막 끝\n")

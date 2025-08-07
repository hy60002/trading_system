# 📁 자동 정리 대상 폴더
$basePath = "C:\GPTBITCOIN"

# 📂 서브폴더 생성
$folders = @(
    "auto_trading",       # 자동매매 관련
    "backtests",          # 백테스트 관련
    "experiments",        # 실험 및 테스트
    "data",               # JSON/CSV 등 데이터
    "models",             # 머신러닝 모델
    "redis",              # Redis 관련
    "super_claude",       # Claude 커맨드
    "callone"             # 전화한끼 프로젝트 (callone)
)

foreach ($folder in $folders) {
    $fullPath = Join-Path $basePath $folder
    if (-not (Test-Path $fullPath)) {
        New-Item -Path $fullPath -ItemType Directory | Out-Null
    }
}

# 📦 파일 이동 규칙
$rules = @{
    "auto_trading" = @("trading_system*.py", "bitgetauto.py", "*auto_trading.py", "*.db", "*trading*.log")
    "backtests"    = @("backtest*.py", "*backtest*.csv", "*backtest*.log", "bb*.py")
    "experiments"  = @("test.py", "launcher.py", "gpt_analysis.py", "ollama_*.py", "don*.py", "config.py", "create_csv.py")
    "data"         = @("*.json", "*.csv")
    "models"       = @("*.pkl", "*.model")
    "redis"        = @("Redis*", "*.zip")
    "super_claude" = @("super_claude.py", ".claude", "CLAUDE.md")
}

# 📂 파일 이동 실행
foreach ($target in $rules.Keys) {
    foreach ($pattern in $rules[$target]) {
        Get-ChildItem -Path $basePath -Filter $pattern -File | ForEach-Object {
            Move-Item $_.FullName -Destination (Join-Path $basePath $target) -Force
        }
    }
}

# 🎉 완료 메시지
Write-Host "✅ GPTBITCOIN 폴더 정리 완료! 기능별로 깔끔하게 정돈됐습니다." -ForegroundColor Green

# ☁️ 클라우드 서버 24시간 실행 가이드

## 🚀 AWS EC2 설정

### 1. EC2 인스턴스 생성
```bash
# Ubuntu 20.04 LTS 선택
# t3.small 이상 권장 (RAM 2GB+)
# 보안 그룹: 8000 포트 열기 (대시보드용)
```

### 2. 환경 설정
```bash
# 업데이트
sudo apt update && sudo apt upgrade -y

# Python 3.9+ 설치
sudo apt install python3.9 python3.9-pip python3.9-venv -y

# Git 설치
sudo apt install git -y

# 프로젝트 클론
git clone https://github.com/your-repo/gptbitcoin.git
cd gptbitcoin/auto_trading

# 가상환경 생성
python3.9 -m venv venv
source venv/bin/activate

# 의존성 설치
pip install -r requirements.txt
```

### 3. systemd 서비스 등록
```bash
# 서비스 파일 생성
sudo nano /etc/systemd/system/gptbitcoin.service
```

```ini
[Unit]
Description=GPTBITCOIN 자동거래 시스템
After=network.target
Wants=network.target

[Service]
Type=simple
User=ubuntu
WorkingDirectory=/home/ubuntu/gptbitcoin/auto_trading
Environment=PATH=/home/ubuntu/gptbitcoin/auto_trading/venv/bin
ExecStart=/home/ubuntu/gptbitcoin/auto_trading/venv/bin/python trading_system2.py
Restart=always
RestartSec=30
StandardOutput=journal
StandardError=journal

[Install]
WantedBy=multi-user.target
```

```bash
# 서비스 등록 및 시작
sudo systemctl daemon-reload
sudo systemctl enable gptbitcoin
sudo systemctl start gptbitcoin

# 상태 확인
sudo systemctl status gptbitcoin

# 로그 확인
sudo journalctl -u gptbitcoin -f
```

## 🐋 Docker 컨테이너

### 1. Dockerfile 생성
```dockerfile
FROM python:3.9-slim

WORKDIR /app

# 의존성 설치
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# 소스 코드 복사
COPY . .

# 환경 변수 설정
ENV PYTHONUNBUFFERED=1

# 컨테이너 실행
CMD ["python", "trading_system2.py"]
```

### 2. Docker Compose
```yaml
version: '3.8'
services:
  gptbitcoin:
    build: .
    container_name: gptbitcoin-trading
    restart: unless-stopped
    environment:
      - API_TOKEN=${API_TOKEN}
      - TELEGRAM_BOT_TOKEN=${TELEGRAM_BOT_TOKEN}
      - TELEGRAM_CHAT_ID=${TELEGRAM_CHAT_ID}
    volumes:
      - ./data:/app/data
      - ./logs:/app/logs
    ports:
      - "8000:8000"
```

```bash
# 실행
docker-compose up -d

# 로그 확인
docker-compose logs -f
```

## 📱 VPS (가상 사설 서버)

### 추천 서비스
- **DigitalOcean**: $6/월 (1GB RAM)
- **Vultr**: $6/월 (1GB RAM)  
- **Linode**: $5/월 (1GB RAM)
- **AWS Lightsail**: $5/월

### 최소 사양
- **CPU**: 1코어
- **RAM**: 2GB (권장)
- **저장공간**: 25GB
- **네트워크**: 무제한

## 🔧 고급 설정

### Nginx 리버스 프록시
```nginx
server {
    listen 80;
    server_name your-domain.com;

    location / {
        proxy_pass http://localhost:8000;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
    }
}
```

### SSL 인증서 (Let's Encrypt)
```bash
sudo apt install certbot python3-certbot-nginx
sudo certbot --nginx -d your-domain.com
```

### 방화벽 설정
```bash
sudo ufw allow ssh
sudo ufw allow 80
sudo ufw allow 443
sudo ufw enable
```
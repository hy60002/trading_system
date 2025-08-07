"""
Trading System Configuration
Centralized configuration management for the trading system
"""

import os
from dataclasses import dataclass, field
from typing import Dict, List, Tuple, Any
from dotenv import load_dotenv

# 암호화 유틸리티 import
try:
    from ..utils.crypto_utils import decrypt_api_key, is_key_encrypted
except ImportError:
    # 상대 import 실패 시 절대 import 시도
    import sys
    import os
    sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    try:
        from utils.crypto_utils import decrypt_api_key, is_key_encrypted
    except ImportError:
        # 암호화 유틸리티를 사용할 수 없는 경우 더미 함수 정의
        def decrypt_api_key(key): return key
        def is_key_encrypted(key): return False


@dataclass
class TradingConfig:
    """Centralized configuration with validation"""
    # API Keys
    BITGET_API_KEY: str = ""
    BITGET_SECRET_KEY: str = ""
    BITGET_PASSPHRASE: str = ""
    OPENAI_API_KEY: str = ""
    TELEGRAM_BOT_TOKEN: str = ""
    TELEGRAM_CHAT_ID: str = ""
    
    def __post_init__(self):
        """Load environment variables after initialization"""
        # Try .env locations in priority order
        project_root = os.path.dirname(os.path.dirname(os.path.dirname(__file__)))
        env_paths = [
            ".env",  # Current directory (highest priority)
            os.path.join(project_root, ".env"),  # Project root
            os.path.join(project_root, "CGPTBITCOIN.env"),  # Alternative name
            "../.env",  # Parent directory
            "../../.env",  # Grandparent directory
        ]
        
        env_loaded = False
        for env_path in env_paths:
            if os.path.exists(env_path):
                load_dotenv(env_path)
                env_loaded = True
                break
        
        if not env_loaded:
            # Fallback to system environment variables
            print("Warning: .env file not found, using system environment variables")
        
        # Load API keys from environment
        raw_bitget_api_key = os.getenv("BITGET_API_KEY", self.BITGET_API_KEY)
        raw_bitget_secret_key = os.getenv("BITGET_SECRET_KEY", self.BITGET_SECRET_KEY)
        raw_bitget_passphrase = os.getenv("BITGET_PASSPHRASE", self.BITGET_PASSPHRASE)
        raw_openai_api_key = os.getenv("OPENAI_API_KEY", self.OPENAI_API_KEY)
        raw_telegram_bot_token = os.getenv("TELEGRAM_BOT_TOKEN", self.TELEGRAM_BOT_TOKEN)
        raw_telegram_chat_id = os.getenv("TELEGRAM_CHAT_ID", self.TELEGRAM_CHAT_ID)
        
        # 🔐 보안 강화: 암호화된 키들을 자동으로 복호화
        try:
            self.BITGET_API_KEY = decrypt_api_key(raw_bitget_api_key)
            self.BITGET_SECRET_KEY = decrypt_api_key(raw_bitget_secret_key)
            self.BITGET_PASSPHRASE = decrypt_api_key(raw_bitget_passphrase)
            self.OPENAI_API_KEY = decrypt_api_key(raw_openai_api_key)
            self.TELEGRAM_BOT_TOKEN = decrypt_api_key(raw_telegram_bot_token)
            self.TELEGRAM_CHAT_ID = decrypt_api_key(raw_telegram_chat_id)
            
            # 암호화된 키 감지 및 로깅 (보안상 실제 값은 로그하지 않음)
            encrypted_keys = []
            if is_key_encrypted(raw_bitget_api_key):
                encrypted_keys.append("BITGET_API_KEY")
            if is_key_encrypted(raw_bitget_secret_key):
                encrypted_keys.append("BITGET_SECRET_KEY")
            if is_key_encrypted(raw_bitget_passphrase):
                encrypted_keys.append("BITGET_PASSPHRASE")
            if is_key_encrypted(raw_openai_api_key):
                encrypted_keys.append("OPENAI_API_KEY")
            if is_key_encrypted(raw_telegram_bot_token):
                encrypted_keys.append("TELEGRAM_BOT_TOKEN")
            if is_key_encrypted(raw_telegram_chat_id):
                encrypted_keys.append("TELEGRAM_CHAT_ID")
                
            if encrypted_keys:
                print(f"🔐 암호화된 키 감지 및 복호화 완료: {', '.join(encrypted_keys)}")
            
        except Exception as e:
            print(f"⚠️ API 키 복호화 중 오류 발생: {e}")
            # 복호화 실패 시 원본 값 사용
            self.BITGET_API_KEY = raw_bitget_api_key
            self.BITGET_SECRET_KEY = raw_bitget_secret_key
            self.BITGET_PASSPHRASE = raw_bitget_passphrase
            self.OPENAI_API_KEY = raw_openai_api_key
            self.TELEGRAM_BOT_TOKEN = raw_telegram_bot_token
            self.TELEGRAM_CHAT_ID = raw_telegram_chat_id
    
    # Trading Symbols (Fixed) - BTC, ETH Only
    SYMBOLS: List[str] = field(default_factory=lambda: ["BTCUSDT", "ETHUSDT"])
    
    # Fixed Leverage
    LEVERAGE: Dict[str, int] = field(default_factory=lambda: {
        "BTCUSDT": 20,
        "ETHUSDT": 10
    })
    
    # Portfolio Allocation - BTC 70% : ETH 30%
    PORTFOLIO_WEIGHTS: Dict[str, float] = field(default_factory=lambda: {
        "BTCUSDT": 0.70,  # 70%
        "ETHUSDT": 0.30   # 30%
    })
    
    # Position Size Ranges (% of allocated capital) - Optimized for 100% allocation
    POSITION_SIZE_RANGE: Dict[str, Dict[str, float]] = field(default_factory=lambda: {
        "BTCUSDT": {"min": 0.20, "standard": 0.35, "max": 0.50},  # Increased for better capital utilization
        "ETHUSDT": {"min": 0.15, "standard": 0.30, "max": 0.45}   # Increased for better capital utilization
    })
    
    # Max Positions per Symbol
    MAX_POSITIONS: Dict[str, int] = field(default_factory=lambda: {
        "BTCUSDT": 3,
        "ETHUSDT": 2
    })
    
    # Entry Conditions by Symbol
    ENTRY_CONDITIONS: Dict[str, Dict[str, Any]] = field(default_factory=lambda: {
        "BTCUSDT": {
            "signal_threshold": 0.25,
            "confidence_required": 45,
            "timeframe_agreement": 0.25,
            "allow_pyramid": True
        },
        "ETHUSDT": {
            "signal_threshold": 0.4,
            "confidence_required": 55,
            "timeframe_agreement": 0.4,
            "allow_pyramid": False,
            "btc_correlation_check": True
        },
    })
    
    # 💰 OPTIMIZED: Maximum Total Capital Allocation (100% of allocated funds)
    MAX_TOTAL_ALLOCATION: float = 1.0  # 자동매매 계좌 자금 100% 활용 (이미 전체 자금의 일부만 이체됨)
    
    # 🛡️ SAFETY: Paper Trading Mode (실전 거래 전 테스트용)
    PAPER_TRADING: bool = False  # True: 시뮬레이션 모드, False: 실전 거래
    
    # 🔥 ATR 기반 동적 손절/익절 시스템
    ATR_SETTINGS: Dict[str, Dict[str, float]] = field(default_factory=lambda: {
        "BTCUSDT": {
            "period": 14,  # ATR 계산 기간
            "stop_multiplier": 2.0,  # 손절 = ATR × 2.0
            "profit_multiplier": 3.0,  # 익절 = ATR × 3.0
            "min_stop_distance": 0.001,  # 최소 손절 거리 (0.1%)
            "max_stop_distance": 0.01,   # 최대 손절 거리 (1%)
        },
        "ETHUSDT": {
            "period": 14,
            "stop_multiplier": 2.5,  # ETH는 변동성이 더 크므로 더 넓게
            "profit_multiplier": 3.5,
            "min_stop_distance": 0.0015,
            "max_stop_distance": 0.015,
        }
    })
    
    # ⚡ 개선된 트레일링 스톱 (현실적 활성화 조건)
    TRAILING_STOP: Dict[str, Dict[str, float]] = field(default_factory=lambda: {
        "BTCUSDT": {"activate": 0.01, "distance": 0.005},  # 1% 수익시 활성화, 0.5% 추적
        "ETHUSDT": {"activate": 0.015, "distance": 0.007}  # 1.5% 수익시 활성화, 0.7% 추적
    })
    
    # 🛡️ 레거시 지원 (폴백용 - ATR 실패 시 사용)
    FALLBACK_STOP_LOSS: Dict[str, float] = field(default_factory=lambda: {
        "BTCUSDT": 0.01,   # 1% (레버리지 20배 고려)
        "ETHUSDT": 0.02    # 2% (레버리지 10배 고려)
    })
    
    FALLBACK_TAKE_PROFIT: Dict[str, float] = field(default_factory=lambda: {
        "BTCUSDT": 0.02,   # 2% (1:2 R:R)
        "ETHUSDT": 0.04    # 4% (1:2 R:R)
    })
    
    # Timeframe Settings
    TIMEFRAMES: Dict[str, str] = field(default_factory=lambda: {
        '5m': 'five_minutes',
        '15m': 'fifteen_minutes',
        '30m': 'thirty_minutes',
        '1h': 'one_hour',
        '4h': 'four_hours'
    })
    
    # Timeframe Weights by Symbol
    TIMEFRAME_WEIGHTS: Dict[str, Dict[str, float]] = field(default_factory=lambda: {
        "BTCUSDT": {'4h': 0.5, '1h': 0.3, '15m': 0.2},
        "ETHUSDT": {'1h': 0.5, '30m': 0.3, '15m': 0.2},
        "XRPUSDT": {'1h': 0.6, '30m': 0.4}
    })
    
    # Trading Limits
    DAILY_TRADE_LIMITS: Dict[str, Dict[str, int]] = field(default_factory=lambda: {
        "BTCUSDT": {"max_trades": 10, "max_loss_trades": 3, "cooldown_minutes": 30},
        "ETHUSDT": {"max_trades": 3, "max_loss_trades": 1, "cooldown_minutes": 120},
        "XRPUSDT": {"max_trades": 2, "max_loss_trades": 1, "cooldown_minutes": 240}
    })
    
    # Fee Configuration
    MAKER_FEE: float = 0.0002  # 0.02%
    TAKER_FEE: float = 0.0006  # 0.06%
    
    # Performance Targets
    DAILY_LOSS_LIMIT: float = 0.05  # 5%
    WEEKLY_LOSS_LIMIT: float = 0.15  # 15%
    MONTHLY_TARGET: float = 0.40  # 40%
    MAX_DRAWDOWN: float = 0.20  # 20%
    
    # Kelly Criterion Settings
    KELLY_FRACTION: float = 0.25  # Use 25% of Kelly suggestion for safety
    MIN_TRADES_FOR_KELLY: int = 20  # Minimum trades for Kelly calculation
    
    # ML Model Settings
    ML_RETRAIN_HOURS: int = 24  # Retrain every 24 hours
    ML_MIN_PERFORMANCE: float = 0.50  # 50% accuracy requirement
    ML_PREDICTION_WINDOW: int = 1000  # Track last 1000 predictions
    ML_WEIGHT: float = 0.8  # 80% weight for ML predictions
    NEWS_WEIGHT: float = 0.2  # 20% weight for news sentiment
    
    # News Filtering Settings  
    MIN_NEWS_CONFIDENCE: float = 0.6  # 60% minimum confidence (더 엄격한 필터링)
    TRUSTED_NEWS_SOURCES: Dict[str, float] = field(default_factory=lambda: {
        "Reuters": 0.95,
        "Bloomberg": 0.95,
        "CoinDesk": 0.85,
        "CoinTelegraph": 0.75,
        "The Block": 0.80,
        "Decrypt": 0.70
    })
    
    SUSPICIOUS_KEYWORDS: List[str] = field(default_factory=lambda: [
        'pump', 'guaranteed', 'moon', '100x', 'insider', 'leaked',
        'exclusive tip', 'buy now', 'don\'t miss', 'last chance'
    ])
    
    # System Settings
    TIMEZONE: str = "Asia/Seoul"
    DATABASE_PATH: str = "advanced_trading_v3.db"
    REDIS_HOST: str = "localhost"
    REDIS_PORT: int = 6379
    LOG_LEVEL: str = "INFO"
    USE_WEBSOCKET: bool = True
    ENABLE_BACKTESTING: bool = True
    ENABLE_ML_MODELS: bool = True
    ENABLE_LIVE_TRADING: bool = True  # Enable/disable actual trading
    MAX_RETRIES: int = 3
    RETRY_DELAY: int = 5
    ANALYSIS_INTERVAL: int = 15  # Analysis interval in minutes (비용 최적화)
    TRADING_CYCLE_INTERVAL: int = 300  # Trading cycle interval in seconds (5 minutes)
    
    # OpenAI Cost Optimization (활성화됨)
    USE_GPT_4: bool = False  # GPT-3.5-turbo 사용 (비용 최적화)
    NEWS_ANALYSIS_INTERVAL: int = 900  # 15분 간격 (비용 최적화)
    TECHNICAL_ANALYSIS_INTERVAL: int = 900  # 15분 간격 (비용 최적화)
    ENABLE_COST_OPTIMIZATION: bool = True  # 비용 최적화 활성화
    
    # WebSocket URLs
    BITGET_WS_URL: str = "wss://ws.bitget.com/mix/v1/stream"
    
    # Cache Settings
    CACHE_TTL: int = 60  # seconds
    INDICATOR_CACHE_SIZE: int = 1000
    
    # System Timing Settings (하드코딩 제거)
    WS_HEALTH_CHECK_INTERVAL: int = 30  # WebSocket 헬스체크 간격 (초)
    WS_MESSAGE_TIMEOUT: int = 60  # WebSocket 메시지 타임아웃 (초)
    NETWORK_RETRY_WAIT: int = 30  # 네트워크 재시도 대기시간 (초)
    NOTIFICATION_MIN_INTERVAL: int = 60  # 알림 최소 간격 (초)
    HTTP_TIMEOUT: int = 30  # HTTP 요청 타임아웃 (초)
    CAPITAL_UPDATE_INTERVAL: int = 30  # 자본 추적 업데이트 간격 (초)
    
    def validate(self) -> list:
        """Check for missing essential configuration"""
        required_fields = [
            'BITGET_API_KEY',
            'BITGET_SECRET_KEY',
            'BITGET_PASSPHRASE'
        ]
        missing = []
        for field_name in required_fields:
            if not getattr(self, field_name, None):
                missing.append(field_name)
        return missing
    
    @classmethod
    def from_env(cls, env_path: str = ".env") -> 'TradingConfig':
        """Load configuration from environment"""
        # The __post_init__ method will handle .env loading automatically
        config = cls()
        # Environment variables are already loaded by __post_init__
        
        return config
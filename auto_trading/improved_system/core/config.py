"""
Enhanced Trading System Configuration with Security Improvements
Author: Enhanced by Claude Code
Version: 4.0
Security Level: High
"""

import os
import secrets
import hashlib
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Any
from dotenv import load_dotenv
from cryptography.fernet import Fernet
import logging

# Setup secure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

@dataclass
class SecurityConfig:
    """Security configuration with encryption support"""
    # Generate secure random token if not provided
    API_TOKEN: str = field(default_factory=lambda: secrets.token_urlsafe(32))
    ENCRYPTION_KEY: Optional[bytes] = None
    SESSION_TIMEOUT: int = 3600  # 1 hour
    MAX_LOGIN_ATTEMPTS: int = 3
    RATE_LIMIT_REQUESTS: int = 100
    RATE_LIMIT_WINDOW: int = 60  # seconds
    
    def __post_init__(self):
        """Initialize encryption after object creation"""
        if self.ENCRYPTION_KEY is None:
            self.ENCRYPTION_KEY = Fernet.generate_key()

@dataclass 
class TradingConfig:
    """Enhanced trading configuration with validation and security"""
    
    # API Credentials (loaded from environment only)
    BITGET_API_KEY: str = ""
    BITGET_SECRET_KEY: str = ""
    BITGET_PASSPHRASE: str = ""
    OPENAI_API_KEY: str = ""
    TELEGRAM_BOT_TOKEN: str = ""
    TELEGRAM_CHAT_ID: str = ""
    
    # Security Configuration
    security: SecurityConfig = field(default_factory=SecurityConfig)
    
    # Trading Symbols (Configurable)
    SYMBOLS: List[str] = field(default_factory=lambda: ["BTCUSDT", "ETHUSDT", "XRPUSDT"])
    
    # Risk Management
    LEVERAGE: Dict[str, int] = field(default_factory=lambda: {
        "BTCUSDT": 20,
        "ETHUSDT": 10, 
        "XRPUSDT": 10
    })
    
    # Portfolio Configuration
    PORTFOLIO_WEIGHTS: Dict[str, float] = field(default_factory=lambda: {
        "BTCUSDT": 0.7,
        "ETHUSDT": 0.2,
        "XRPUSDT": 0.1
    })
    
    # Position Size Management
    POSITION_SIZE_RANGE: Dict[str, Dict[str, float]] = field(default_factory=lambda: {
        "BTCUSDT": {"min": 0.15, "standard": 0.25, "max": 0.35},
        "ETHUSDT": {"min": 0.05, "standard": 0.10, "max": 0.15},
        "XRPUSDT": {"min": 0.03, "standard": 0.05, "max": 0.08}
    })
    
    # Max Positions Configuration
    MAX_POSITIONS: Dict[str, int] = field(default_factory=lambda: {
        "BTCUSDT": 3,
        "ETHUSDT": 1,
        "XRPUSDT": 1
    })
    
    # Performance Settings
    INDICATOR_CACHE_SIZE: int = 1000
    CACHE_TTL: int = 300  # 5 minutes
    WS_RECONNECT_DELAY: int = 5
    MAX_RECONNECT_ATTEMPTS: int = 10
    
    # Database Configuration
    DATABASE_URL: str = "sqlite:///improved_trading_system.db"
    DATABASE_POOL_SIZE: int = 5
    DATABASE_TIMEOUT: int = 30
    
    # Logging Configuration
    LOG_LEVEL: str = "INFO"
    LOG_FILE: str = "improved_trading_system.log"
    LOG_MAX_SIZE: int = 10485760  # 10MB
    LOG_BACKUP_COUNT: int = 5
    
    @classmethod
    def from_env(cls, env_path: str = ".env") -> 'TradingConfig':
        """Create configuration from environment variables with validation"""
        load_dotenv(env_path)
        
        config = cls()
        
        # Load and validate API credentials
        required_keys = [
            'BITGET_API_KEY',
            'BITGET_SECRET_KEY', 
            'BITGET_PASSPHRASE'
        ]
        
        missing_keys = []
        for key in required_keys:
            value = os.getenv(key)
            if not value:
                missing_keys.append(key)
            else:
                setattr(config, key, value)
        
        if missing_keys:
            raise ValueError(f"Missing required environment variables: {missing_keys}")
        
        # Load optional keys
        config.OPENAI_API_KEY = os.getenv("OPENAI_API_KEY", "")
        config.TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN", "")
        config.TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID", "")
        
        # Load custom API token or generate secure one
        custom_token = os.getenv('API_TOKEN')
        if custom_token:
            config.security.API_TOKEN = custom_token
        
        # Validate configuration
        config.validate()
        
        logger.info("Configuration loaded successfully from environment")
        return config
    
    def validate(self) -> bool:
        """Validate configuration parameters"""
        errors = []
        
        # Validate portfolio weights sum to 1.0
        weight_sum = sum(self.PORTFOLIO_WEIGHTS.values())
        if abs(weight_sum - 1.0) > 0.01:
            errors.append(f"Portfolio weights sum to {weight_sum}, should be 1.0")
        
        # Validate leverage values
        for symbol, leverage in self.LEVERAGE.items():
            if leverage < 1 or leverage > 100:
                errors.append(f"Invalid leverage for {symbol}: {leverage}")
        
        # Validate position size ranges
        for symbol, ranges in self.POSITION_SIZE_RANGE.items():
            if ranges["min"] >= ranges["max"]:
                errors.append(f"Invalid position size range for {symbol}")
        
        # Validate symbols consistency
        for symbol in self.SYMBOLS:
            if symbol not in self.PORTFOLIO_WEIGHTS:
                errors.append(f"Symbol {symbol} missing portfolio weight")
            if symbol not in self.LEVERAGE:
                errors.append(f"Symbol {symbol} missing leverage setting")
        
        if errors:
            error_msg = "Configuration validation failed:\n" + "\n".join(errors)
            logger.error(error_msg)
            raise ValueError(error_msg)
        
        logger.info("Configuration validation successful")
        return True
    
    def get_secure_hash(self) -> str:
        """Generate secure hash of configuration for validation"""
        config_str = f"{self.BITGET_API_KEY}{self.SYMBOLS}{self.LEVERAGE}"
        return hashlib.sha256(config_str.encode()).hexdigest()
    
    def mask_secrets(self) -> Dict[str, Any]:
        """Return configuration with masked secrets for logging"""
        masked_config = {}
        for key, value in self.__dict__.items():
            if any(secret_key in key.upper() for secret_key in ['KEY', 'SECRET', 'PASSWORD', 'TOKEN']):
                if isinstance(value, str) and len(value) > 0:
                    masked_config[key] = f"{value[:4]}{'*' * (len(value) - 8)}{value[-4:]}" if len(value) > 8 else "***"
                else:
                    masked_config[key] = "***"
            else:
                masked_config[key] = value
        return masked_config

class ConfigManager:
    """Singleton configuration manager"""
    _instance = None
    _config = None
    
    def __new__(cls):
        if cls._instance is None:
            cls._instance = super(ConfigManager, cls).__new__(cls)
        return cls._instance
    
    def get_config(self) -> TradingConfig:
        """Get current configuration"""
        if self._config is None:
            self._config = TradingConfig.from_env()
        return self._config
    
    def reload_config(self, env_path: str = ".env") -> TradingConfig:
        """Reload configuration from environment"""
        self._config = TradingConfig.from_env(env_path)
        logger.info("Configuration reloaded")
        return self._config
    
    def update_config(self, **kwargs) -> None:
        """Update specific configuration values"""
        if self._config is None:
            self._config = TradingConfig.from_env()
        
        for key, value in kwargs.items():
            if hasattr(self._config, key):
                setattr(self._config, key, value)
                logger.info(f"Updated config: {key}")
            else:
                logger.warning(f"Unknown config key: {key}")
        
        # Re-validate after updates
        self._config.validate()

# Global configuration instance
config_manager = ConfigManager()
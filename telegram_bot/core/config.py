from pydantic_settings import BaseSettings, SettingsConfigDict
from pydantic import SecretStr, Field, validator, DirectoryPath
from typing import List, Dict, Any, Optional
from pathlib import Path
from datetime import timedelta
import json
import os

class Settings(BaseSettings):
    """Application settings"""
    
    # Application
    APP_NAME: str = "Law Consultation Bot"
    VERSION: str = "1.0.0"
    DEBUG: bool = Field(default=False)
    ENVIRONMENT: str = Field(default="development")
    
    # Paths
    BASE_DIR: Path = Field(default=Path(__file__).parent.parent.parent)
    STATIC_DIR: Path = Field(default=None)
    MEDIA_DIR: Path = Field(default=None)
    LOGS_DIR: Path = Field(default=None)
    BACKUP_DIR: Path = Field(default=None)
    
    # Security
    SECRET_KEY: SecretStr
    API_TOKEN_EXPIRE_MINUTES: int = 60
    REFRESH_TOKEN_EXPIRE_DAYS: int = 7
    JWT_ALGORITHM: str = "HS256"
    ALLOWED_HOSTS: List[str] = ["*"]
    CORS_ORIGINS: List[str] = ["*"]
    
    # Bot
    BOT_TOKEN: SecretStr
    ADMIN_IDS: List[int] = []
    BOT_WEBHOOK_SECRET: Optional[SecretStr] = None
    BOT_WEBHOOK_PATH: Optional[str] = None
    BOT_WEBHOOK_URL: Optional[str] = None
    
    # Database
    DB_HOST: str
    DB_PORT: int = 5432
    DB_USER: str
    DB_PASSWORD: SecretStr
    DB_NAME: str
    DB_POOL_SIZE: int = 20
    DB_MAX_OVERFLOW: int = 10
    DB_POOL_TIMEOUT: int = 30
    DB_POOL_RECYCLE: int = 1800
    DB_STATEMENT_TIMEOUT: int = 30000  # 30s
    DB_COMMAND_TIMEOUT: int = 30
    DB_ECHO: bool = False
    DB_SLOW_QUERY_THRESHOLD: float = 1.0  # seconds
    
    # Redis
    REDIS_HOST: str
    REDIS_PORT: int = 6379
    REDIS_PASSWORD: Optional[SecretStr] = None
    REDIS_DB: int = 0
    REDIS_MAX_CONNECTIONS: int = 10
    REDIS_SOCKET_TIMEOUT: int = 5
    REDIS_RETRY_ON_TIMEOUT: bool = True
    
    # Payment Systems
    CLICK_MERCHANT_ID: Optional[SecretStr] = None
    CLICK_SERVICE_ID: Optional[str] = None
    CLICK_SECRET_KEY: Optional[SecretStr] = None
    CLICK_RETURN_URL: Optional[str] = None
    
    PAYME_MERCHANT_ID: Optional[SecretStr] = None
    PAYME_SECRET_KEY: Optional[SecretStr] = None
    PAYME_RETURN_URL: Optional[str] = None
    
    UZUM_MERCHANT_ID: Optional[SecretStr] = None
    UZUM_SECRET_KEY: Optional[SecretStr] = None
    UZUM_RETURN_URL: Optional[str] = None
    
    # Monitoring
    SENTRY_DSN: Optional[SecretStr] = None
    SENTRY_ENVIRONMENT: Optional[str] = None
    SENTRY_TRACES_SAMPLE_RATE: float = 1.0
    
    PROMETHEUS_ENABLED: bool = True
    PROMETHEUS_PORT: int = 9090
    
    GRAYLOG_HOST: Optional[str] = None
    GRAYLOG_PORT: Optional[int] = None
    
    # Logging
    LOG_LEVEL: str = "INFO"
    LOG_FORMAT: str = "json"
    LOG_FILE: Optional[str] = None
    LOG_MAX_SIZE: int = 10 * 1024 * 1024  # 10MB
    LOG_BACKUP_COUNT: int = 5
    
    # Cache
    CACHE_TTL: int = 3600  # 1 hour
    CACHE_PREFIX: str = "law_bot"
    
    # API
    API_V1_PREFIX: str = "/api/v1"
    API_TITLE: str = "Law Bot API"
    API_DESCRIPTION: str = "API for Law Consultation Telegram Bot"
    API_VERSION: str = "1.0.0"
    
    # Admin Panel
    ADMIN_PANEL_URL: str = "/admin"
    ADMIN_PANEL_TITLE: str = "Law Bot Admin"
    
    # Feature Flags
    FEATURES: Dict[str, bool] = {
        "payment_system": True,
        "auto_answers": True,
        "notifications": True,
        "admin_panel": True
    }
    
    # Business Rules
    BUSINESS_RULES: Dict[str, Any] = {
        "min_question_length": 10,
        "max_question_length": 1000,
        "min_consultation_amount": 50000,
        "max_consultation_amount": 1000000,
        "consultation_duration": 60,
        "cancellation_period": 24,
        "working_hours": {
            "start": 9,
            "end": 18
        }
    }

    @validator("STATIC_DIR", "MEDIA_DIR", "LOGS_DIR", "BACKUP_DIR", pre=True)
    def build_paths(cls, v, values):
        if v is None:
            base_dir = values.get("BASE_DIR", Path(__file__).parent.parent.parent)
            if "STATIC_DIR" in values.keys():
                return base_dir / "static"
            elif "MEDIA_DIR" in values.keys():
                return base_dir / "media"
            elif "LOGS_DIR" in values.keys():
                return base_dir / "logs"
            elif "BACKUP_DIR" in values.keys():
                return base_dir / "backups"
        return v

    @property
    def DATABASE_URL(self) -> str:
        """Get SQLAlchemy database URL"""
        return (
            f"postgresql+asyncpg://{self.DB_USER}:"
            f"{self.DB_PASSWORD.get_secret_value()}"
            f"@{self.DB_HOST}:{self.DB_PORT}/{self.DB_NAME}"
        )
    
    @property
    def REDIS_URL(self) -> str:
        """Get Redis URL"""
        if self.REDIS_PASSWORD:
            return (
                f"redis://:{self.REDIS_PASSWORD.get_secret_value()}"
                f"@{self.REDIS_HOST}:{self.REDIS_PORT}/{self.REDIS_DB}"
            )
        return f"redis://{self.REDIS_HOST}:{self.REDIS_PORT}/{self.REDIS_DB}"
    
    @property
    def CLICK_CONFIG(self) -> Dict[str, Any]:
        """Get Click payment system config"""
        if not (self.CLICK_MERCHANT_ID and self.CLICK_SECRET_KEY):
            return {}
            
        return {
            'merchant_id': self.CLICK_MERCHANT_ID.get_secret_value(),
            'service_id': self.CLICK_SERVICE_ID,
            'secret_key': self.CLICK_SECRET_KEY.get_secret_value(),
            'return_url': self.CLICK_RETURN_URL
        }
    
    @property
    def PAYME_CONFIG(self) -> Dict[str, Any]:
        """Get Payme payment system config"""
        if not (self.PAYME_MERCHANT_ID and self.PAYME_SECRET_KEY):
            return {}
            
        return {
            'merchant_id': self.PAYME_MERCHANT_ID.get_secret_value(),
            'secret_key': self.PAYME_SECRET_KEY.get_secret_value(),
            'return_url': self.PAYME_RETURN_URL
        }
    
    @property
    def UZUM_CONFIG(self) -> Dict[str, Any]:
        """Get Uzum payment system config"""
        if not (self.UZUM_MERCHANT_ID and self.UZUM_SECRET_KEY):
            return {}
            
        return {
            'merchant_id': self.UZUM_MERCHANT_ID.get_secret_value(),
            'secret_key': self.UZUM_SECRET_KEY.get_secret_value(),
            'return_url': self.UZUM_RETURN_URL
        }

    def get_feature_flag(self, feature: str) -> bool:
        """Get feature flag value"""
        return self.FEATURES.get(feature, False)
    
    def get_business_rule(self, rule: str) -> Any:
        """Get business rule value"""
        return self.BUSINESS_RULES.get(rule)

    def configure_sentry(self) -> None:
        """Configure Sentry error tracking"""
        if self.SENTRY_DSN:
            import sentry_sdk
            from sentry_sdk.integrations.fastapi import FastApiIntegration
            from sentry_sdk.integrations.sqlalchemy import SqlalchemyIntegration
            from sentry_sdk.integrations.redis import RedisIntegration
            
            sentry_sdk.init(
                dsn=self.SENTRY_DSN.get_secret_value(),
                environment=self.SENTRY_ENVIRONMENT or self.ENVIRONMENT,
                traces_sample_rate=self.SENTRY_TRACES_SAMPLE_RATE,
                integrations=[
                    FastApiIntegration(),
                    SqlalchemyIntegration(),
                    RedisIntegration()
                ]
            )

    def configure_prometheus(self) -> None:
        """Configure Prometheus metrics"""
        if self.PROMETHEUS_ENABLED:
            from prometheus_client import start_http_server
            start_http_server(self.PROMETHEUS_PORT)

    def get_log_config(self) -> Dict[str, Any]:
        """Get logging configuration"""
        return {
            'version': 1,
            'disable_existing_loggers': False,
            'formatters': {
                'json': {
                    '()': 'pythonjsonlogger.jsonlogger.JsonFormatter',
                    'format': '%(asctime)s %(name)s %(levelname)s %(message)s'
                },
                'standard': {
                    'format': '%(asctime)s [%(levelname)s] %(name)s: %(message)s'
                }
            },
            'handlers': {
                'console': {
                    'class': 'logging.StreamHandler',
                    'formatter': 'json' if self.LOG_FORMAT == 'json' else 'standard',
                    'level': self.LOG_LEVEL
                },
                'file': {
                    'class': 'logging.handlers.RotatingFileHandler',
                    'filename': self.LOG_FILE or str(self.LOGS_DIR / 'app.log'),
                    'maxBytes': self.LOG_MAX_SIZE,
                    'backupCount': self.LOG_BACKUP_COUNT,
                    'formatter': 'json' if self.LOG_FORMAT == 'json' else 'standard',
                    'level': self.LOG_LEVEL
                }
            },
            'root': {
                'handlers': ['console', 'file'],
                'level': self.LOG_LEVEL
            }
        }

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=True,
        extra="allow"
    )

# Create settings instance
settings = Settings()

# Create required directories
for path in [settings.STATIC_DIR, settings.MEDIA_DIR, settings.LOGS_DIR, settings.BACKUP_DIR]:
    path.mkdir(parents=True, exist_ok=True)

# Configure monitoring if enabled
if settings.ENVIRONMENT == "production":
    settings.configure_sentry()

if settings.PROMETHEUS_ENABLED:
    settings.configure_prometheus()
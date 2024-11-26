import logging
import logging.handlers
from datetime import datetime
from pathlib import Path
import json
from pythonjsonlogger import jsonlogger
import sys
from typing import Optional,Dict,Any,Tuple
import graylog
import sentry_sdk

from telegram_bot.core.config import settings

class CustomJsonFormatter(jsonlogger.JsonFormatter):
    """Custom JSON formatter for structured logging"""
    
    def add_fields(self, log_record: Dict[str, Any], record: logging.LogRecord, message_dict: Dict) -> None:
        super().add_fields(log_record, record, message_dict)
        
        # Add basic fields
        log_record['timestamp'] = datetime.utcnow().isoformat()
        log_record['level'] = record.levelname
        log_record['logger'] = record.name
        
        # Add custom fields
        if hasattr(record, 'user_id'):
            log_record['user_id'] = record.user_id
        if hasattr(record, 'request_id'):
            log_record['request_id'] = record.request_id
        if hasattr(record, 'ip_address'):
            log_record['ip_address'] = record.ip_address
            
        # Add error details if present
        if 'exc_info' in message_dict:
            log_record['error'] = {
                'type': record.exc_info[0].__name__ if record.exc_info else None,
                'message': str(record.exc_info[1]) if record.exc_info else None,
                'traceback': self.formatException(record.exc_info) if record.exc_info else None
            }

def setup_logging(
    log_level: str = "INFO",
    log_format: str = "json",
    log_file: Optional[str] = None,
    log_dir: Optional[Path] = None
) -> logging.Logger:
    """Setup application logging with comprehensive configuration"""
    
    # Create logs directory if needed
    if log_dir:
        log_dir.mkdir(parents=True, exist_ok=True)
        if not log_file:
            log_file = log_dir / f"telegram_bot_{datetime.now().strftime('%Y-%m-%d')}.log"
    
    # Configure handlers
    handlers = []
    
    # Console handler
    console_handler = logging.StreamHandler(sys.stdout)
    if log_format == "json":
        formatter = CustomJsonFormatter(
            '%(timestamp)s %(level)s %(name)s %(message)s'
        )
    else:
        formatter = logging.Formatter(
            '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
        )
    console_handler.setFormatter(formatter)
    handlers.append(console_handler)
    
    # File handler
    if log_file:
        file_handler = logging.handlers.RotatingFileHandler(
            log_file,
            maxBytes=10*1024*1024,  # 10MB 
            backupCount=5,
            encoding='utf-8'
        )
        file_handler.setFormatter(formatter)
        handlers.append(file_handler)
    
    # Graylog handler
    if settings.GRAYLOG_HOST:
        graylog_handler = graylog.GELFUDPHandler(
            host=settings.GRAYLOG_HOST,
            port=settings.GRAYLOG_PORT,
            facility=settings.APP_NAME
        )
        handlers.append(graylog_handler)
    
    # Sentry integration
    if settings.SENTRY_DSN:
        sentry_sdk.init(
            dsn=settings.SENTRY_DSN,
            environment=settings.ENVIRONMENT,
            traces_sample_rate=1.0,
            profiles_sample_rate=1.0
        )
    
    # Configure root logger
    logging.basicConfig(
        level=getattr(logging, log_level.upper()),
        handlers=handlers,
        force=True
    )
    
    # Set levels for third-party loggers
    logging.getLogger('aiohttp').setLevel(logging.WARNING)
    logging.getLogger('aiogram').setLevel(logging.INFO)
    logging.getLogger('sqlalchemy').setLevel(logging.WARNING)
    logging.getLogger('urllib3').setLevel(logging.WARNING)
    
    # Create logger
    logger = logging.getLogger('telegram_bot')
    logger.setLevel(getattr(logging, log_level.upper()))
    
    return logger

class LoggerAdapter(logging.LoggerAdapter):
    """Custom logger adapter for adding context"""
    
    def process(self, msg: str, kwargs: Dict[str, Any]) -> Tuple[str, Dict[str, Any]]:
        extra = kwargs.get('extra', {})
        
        # Add context from adapter
        if hasattr(self.extra, 'user_id'):
            extra['user_id'] = self.extra.user_id
        if hasattr(self.extra, 'request_id'):
            extra['request_id'] = self.extra.request_id
            
        kwargs['extra'] = extra
        return msg, kwargs

class AsyncLoggerAdapter(LoggerAdapter):
    """Async logger adapter for coroutines"""
    
    async def alog(
        self,
        level: int,
        msg: str,
        *args,
        **kwargs
    ) -> None:
        """Async logging method"""
        if self.isEnabledFor(level):
            msg, kwargs = self.process(msg, kwargs)
            self.logger._log(level, msg, args, **kwargs)

def get_logger(name: str, **kwargs) -> logging.Logger:
    """Get logger with context"""
    logger = logging.getLogger(name)
    return LoggerAdapter(logger, kwargs)

# Create global logger instance
logger = get_logger(__name__)

__all__ = [
    'setup_logging',
    'get_logger', 
    'logger',
    'LoggerAdapter',
    'AsyncLoggerAdapter'
]
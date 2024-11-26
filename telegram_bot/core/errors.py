from typing import Optional, Dict, Any
from fastapi import HTTPException, status
import logging
from telegram_bot.core.constants import TEXTS

logger = logging.getLogger(__name__)

class BotError(Exception):
    """Base error class"""
    def __init__(
        self,
        message: str,
        user_message: Optional[Dict[str, str]] = None,
        details: Optional[Dict[str, Any]] = None,
        status_code: int = 500
    ):
        super().__init__(message)
        self.message = message
        self.user_message = user_message or TEXTS
        self.details = details or {}
        self.status_code = status_code
        
    def get_user_message(self, language: str) -> str:
        """Get localized error message"""
        if isinstance(self.user_message, dict):
            return self.user_message.get(language, self.user_message.get('ru', str(self)))
        return str(self)

class ValidationError(BotError):
    """Validation error"""
    def __init__(
        self,
        message: str,
        field: Optional[str] = None,
        details: Optional[Dict] = None
    ):
        super().__init__(
            message=message,
            user_message=TEXTS['validation_error'],
            details={
                'field': field,
                **(details or {})
            },
            status_code=422
        )

class AuthenticationError(BotError):
    """Authentication error"""
    def __init__(self, message: str = "Authentication failed"):
        super().__init__(
            message=message,
            user_message=TEXTS['auth_error'],
            status_code=401
        )

class AuthorizationError(BotError):
    """Authorization error"""
    def __init__(self, message: str = "Permission denied"):
        super().__init__(
            message=message,
            user_message=TEXTS['permission_error'], 
            status_code=403
        )

class PaymentError(BotError):
    """Payment error"""
    def __init__(
        self,
        message: str,
        provider: Optional[str] = None,
        transaction_id: Optional[str] = None
    ):
        super().__init__(
            message=message,
            user_message=TEXTS['payment_error'],
            details={
                'provider': provider,
                'transaction_id': transaction_id
            },
            status_code=402
        )

class NotFoundError(BotError):
    """Not found error"""
    def __init__(self, message: str, resource: Optional[str] = None):
        super().__init__(
            message=message,
            user_message=TEXTS['not_found'],
            details={'resource': resource},
            status_code=404
        )

class RateLimitError(BotError):
    """Rate limit error"""
    def __init__(self, message: str = "Rate limit exceeded"):
        super().__init__(
            message=message,
            user_message=TEXTS['rate_limit'],
            status_code=429
        )

class ServiceUnavailableError(BotError):
    """Service unavailable error"""
    def __init__(self, message: str, service: Optional[str] = None):
        super().__init__(
            message=message,
            user_message=TEXTS['service_unavailable'],
            details={'service': service},
            status_code=503
        )


# Добавляем в файл /telegram_bot/core/errors.py

class DatabaseError(BotError):
    """Database operation error"""
    def __init__(self, message: str = "Database error occurred"):
        super().__init__(
            message=message,
            user_message=TEXTS['database_error'],
            status_code=500
        )

class ConsultationError(BotError):
    """Consultation related error"""
    def __init__(self, message: str = "Consultation error"):
        super().__init__(
            message=message,
            user_message=TEXTS['consultation_error'],
            status_code=400
        )

class PaymentProcessingError(BotError):
    """Payment processing error"""
    def __init__(
        self,
        message: str = "Payment processing failed",
        provider: Optional[str] = None,
        transaction_id: Optional[str] = None
    ):
        super().__init__(
            message=message,
            user_message=TEXTS['payment_error'],
            details={
                'provider': provider,
                'transaction_id': transaction_id
            },
            status_code=402
        )

class QuestionError(BotError):
    """Question related error"""
    def __init__(self, message: str = "Question error"):
        super().__init__(
            message=message,
            user_message=TEXTS['question_error'],
            status_code=400
        )

class AutoAnswerError(BotError):
    """Auto answer generation error"""
    def __init__(self, message: str = "Failed to generate auto answer"):
        super().__init__(
            message=message,
            user_message=TEXTS['auto_answer_error'],
            status_code=500
        )

class ConfigurationError(BotError):
    """Configuration error"""
    def __init__(self, message: str = "Configuration error"):
        super().__init__(
            message=message,
            user_message=TEXTS['system_error'],
            status_code=500
        )

class ServiceUnavailableError(BotError):
    """Service unavailable error"""
    def __init__(self, service: str, message: str = "Service unavailable"):
        super().__init__(
            message=message,
            user_message=TEXTS['service_unavailable'],
            details={'service': service},
            status_code=503
        )

class RateLimitExceededError(BotError):
    """Rate limit exceeded error"""
    def __init__(self, message: str = "Rate limit exceeded"):
        super().__init__(
            message=message,
            user_message=TEXTS['rate_limit'],
            status_code=429
        )

class CacheError(BotError):
    """Cache operation error"""
    def __init__(self, message: str = "Cache error"):
        super().__init__(
            message=message,
            user_message=TEXTS['system_error'],
            status_code=500
        )

class NotificationError(BotError):
    """Notification sending error"""
    def __init__(self, message: str = "Failed to send notification"):
        super().__init__(
            message=message,
            user_message=TEXTS['notification_error'],
            status_code=500
        )



async def error_handler(error: Exception, language: str = 'ru') -> Dict:
    """Global error handler"""
    if isinstance(error, BotError):
        # Log error
        logger.error(
            f"Bot error: {error.message}",
            extra={
                'error_type': type(error).__name__,
                'details': error.details
            }
        )
        
        # Return error response
        return {
            'error': error.message,
            'user_message': error.get_user_message(language),
            'details': error.details,
            'code': error.status_code
        }
        
    # Handle unknown errors
    logger.error(f"Unexpected error: {str(error)}", exc_info=True)
    
    return {
        'error': 'Internal server error',
        'user_message': TEXTS[language]['error'],
        'code': 500
    }

# Export errors and handler
__all__ = [
    'BotError',
    'ValidationError',
    'AuthenticationError', 
    'AuthorizationError',
    'PaymentError',
    'NotFoundError',
    'RateLimitError',
    'ServiceUnavailableError',
    'DatabaseError',
    'ConsultationError',
    'PaymentProcessingError',
    'QuestionError',
    'AutoAnswerError',
    'ConfigurationError',
    'RateLimitExceededError',
    'CacheError',
    'NotificationError',
    'error_handler'
]
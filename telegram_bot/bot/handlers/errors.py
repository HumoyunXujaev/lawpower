from aiogram import Router, F
from aiogram.types import ErrorEvent, Update
import logging
from datetime import datetime
import traceback
from typing import Any, Awaitable, Callable, Dict, Union
from aiogram import Bot, Dispatcher
from aiogram import BaseMiddleware
from telegram_bot.core.constants import TEXTS
from telegram_bot.services.analytics import AnalyticsService
from telegram_bot.core.config import settings
from telegram_bot.core.errors import (
    ValidationError,
    DatabaseError,
    AuthenticationError,
    PaymentError,
    RateLimitError
)

logger = logging.getLogger(__name__)
router = Router(name='errors')

@router.errors()
async def error_handler(event: ErrorEvent, analytics: AnalyticsService):
    """Global error handler"""
    try:
        # Get update and user info
        update: Update = event.update
        user_id = None
        language = 'ru'
        
        if update.message:
            user_id = update.message.from_user.id
            language = update.message.from_user.language_code
        elif update.callback_query:
            user_id = update.callback_query.from_user.id
            language = update.callback_query.from_user.language_code
            
        # Log error details
        error_data = {
            'user_id': user_id,
            'update_id': update.update_id,
            'error_type': type(event.exception).__name__,
            'error_msg': str(event.exception),
            'traceback': traceback.format_exc(),
            'timestamp': datetime.utcnow().isoformat()
        }
        
        logger.error(
            f"Error handling update {update.update_id}",
            extra={'error_data': error_data},
            exc_info=True
        )
        
        # Track error
        if analytics:
            await analytics.track_event(
                user_id=user_id,
                event_type='bot_error',
                data=error_data
            )
        
        # Prepare user message based on error type
        if isinstance(event.exception, ValidationError):
            error_text = TEXTS[language]['validation_error']
        elif isinstance(event.exception, DatabaseError):
            error_text = TEXTS[language]['database_error']
        elif isinstance(event.exception, AuthenticationError):
            error_text = TEXTS[language]['auth_error']
        elif isinstance(event.exception, PaymentError):
            error_text = TEXTS[language]['payment_error']
        elif isinstance(event.exception, RateLimitError):
            error_text = TEXTS[language]['rate_limit']
        else:
            error_text = TEXTS[language]['error']
        
        # Send error message to user
        if update.message:
            await update.message.answer(error_text)
        elif update.callback_query:
            await update.callback_query.message.answer(error_text)
        
        # Notify admins in production
        if settings.ENVIRONMENT == "production":
            admin_text = (
                f"❌ Error in bot:\n\n"
                f"User ID: {user_id}\n"
                f"Update ID: {update.update_id}\n"
                f"Error type: {type(event.exception).__name__}\n"
                f"Error: {str(event.exception)}\n\n"
                f"Traceback:\n<code>{traceback.format_exc()}</code>"
            )
            
            from telegram_bot.bot import bot
            for admin_id in settings.ADMIN_IDS:
                try:
                    await bot.send_message(
                        admin_id,
                        admin_text,
                        parse_mode="HTML"
                    )
                except Exception as e:
                    logger.error(f"Error notifying admin {admin_id}: {e}")
                    
    except Exception as e:
        logger.error(f"Error in error handler: {e}", exc_info=True)

@router.errors(F.update.message)
async def message_error_handler(event: ErrorEvent):
    """Handle message errors"""
    update: Update = event.update
    try:
        logger.error(
            f"Error handling message: {event.exception}",
            extra={
                'user_id': update.message.from_user.id,
                'message_id': update.message.message_id,
                'chat_id': update.message.chat.id
            },
            exc_info=True
        )
        
        # Send generic error message
        await update.message.answer(
            TEXTS[update.message.from_user.language_code]['error']
        )
        
    except Exception as e:
        logger.error(f"Error in message error handler: {e}", exc_info=True)

@router.errors(F.update.callback_query)
async def callback_error_handler(event: ErrorEvent):
    """Handle callback query errors"""
    update: Update = event.update
    try:
        logger.error(
            f"Error handling callback query: {event.exception}",
            extra={
                'user_id': update.callback_query.from_user.id,
                'callback_data': update.callback_query.data,
                'message_id': update.callback_query.message.message_id
            },
            exc_info=True
        )
        
        # Answer callback query with error
        await update.callback_query.answer(
            TEXTS[update.callback_query.from_user.language_code]['error'],
            show_alert=True
        )
        
    except Exception as e:
        logger.error(f"Error in callback error handler: {e}", exc_info=True)

def register_handlers(dp: Dispatcher):
    """Register error handlers"""
    dp.include_router(router)

# Error handling middleware
class ErrorHandlingMiddleware(BaseMiddleware):
    async def __call__(
        self,
        handler: Callable[[Update, Dict[str, Any]], Awaitable[Any]],
        event: Update,
        data: Dict[str, Any]
    ) -> Any:
        try:
            return await handler(event, data)
        except Exception as e:
            # Get error event
            error_event = ErrorEvent(
                update=event,
                exception=e
            )
            
            # Handle error
            await error_handler(
                error_event,
                data.get('analytics_service')
            )
            
            # Don't propagate error
            return None

# Export error handlers
__all__ = [
    'error_handler',
    'message_error_handler',
    'callback_error_handler',
    'register_handlers',
    'ErrorHandlingMiddleware'
]

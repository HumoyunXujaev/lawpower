from typing import Any, Awaitable, Callable, Dict, Union
from aiogram import BaseMiddleware
from aiogram.types import Message, CallbackQuery, Update
from sqlalchemy.ext.asyncio import AsyncSession
import logging
from datetime import datetime
import json
import traceback
from telegram_bot.core.constants import TEXTS


from telegram_bot.core.database import get_session
from telegram_bot.models import User
from telegram_bot.services.analytics import AnalyticsService
from telegram_bot.core.monitoring import metrics_manager
from telegram_bot.utils.cache import cache
from telegram_bot.core.errors import (
    ValidationError,
    DatabaseError,
    AuthenticationError
)

logger = logging.getLogger(__name__)

class DatabaseMiddleware(BaseMiddleware):
    """Database session middleware"""
    
    async def __call__(
        self,
        handler: Callable[[Update, Dict[str, Any]], Awaitable[Any]],
        event: Update,
        data: Dict[str, Any]
    ) -> Any:
        async with get_session() as session:
            data['session'] = session
            try:
                return await handler(event, data)
            finally:
                await session.close()

class AuthenticationMiddleware(BaseMiddleware):
    """User authentication middleware"""
    
    async def __call__(
        self,
        handler: Callable[[Update, Dict[str, Any]], Awaitable[Any]],
        event: Update,
        data: Dict[str, Any]
    ) -> Any:
        # Get user info
        if isinstance(event.event, (Message, CallbackQuery)):
            tg_user = event.event.from_user
            session: AsyncSession = data['session']
            
            try:
                # Try to get user from cache
                user_key = f"user:{tg_user.id}"
                user_data = await cache.get(user_key)
                
                if user_data:
                    user = User(**user_data)
                else:
                    # Get or create user
                    from sqlalchemy import select
                    result = await session.execute(
                        select(User).where(User.telegram_id == tg_user.id)
                    )
                    user = result.scalar_one_or_none()
                    
                    if not user:
                        user = User(
                            telegram_id=tg_user.id,
                            username=tg_user.username,
                            full_name=tg_user.full_name
                        )
                        session.add(user)
                        await session.commit()
                        await session.refresh(user)
                    
                    # Cache user data
                    await cache.set(
                        user_key,
                        user.to_dict(),
                        timeout=3600
                    )
                
                # Update user info if needed
                if (
                    user.username != tg_user.username or
                    user.full_name != tg_user.full_name
                ):
                    user.username = tg_user.username
                    user.full_name = tg_user.full_name
                    await session.commit()
                    await cache.delete(user_key)
                
                # Add user to data
                data['user'] = user
                
            except Exception as e:
                logger.error(f"Auth error: {e}", exc_info=True)
                raise AuthenticationError("Failed to authenticate user")
        
        return await handler(event, data)

class LanguageMiddleware(BaseMiddleware):
    """User language middleware"""
    
    async def __call__(
        self,
        handler: Callable[[Update, Dict[str, Any]], Awaitable[Any]],
        event: Update,
        data: Dict[str, Any]
    ) -> Any:
        if isinstance(event.event, (Message, CallbackQuery)):
            user: User = data.get('user')
            if user:
                # Set default language if not set
                if not user.language:
                    user.language = 'uz'  # Default to Uzbek
                    session: AsyncSession = data['session']
                    await session.commit()
                    
                # Add language to data
                data['language'] = user.language
                
        return await handler(event, data)

class UserActivityMiddleware(BaseMiddleware):
    """Track user activity"""
    
    async def __call__(
        self,
        handler: Callable[[Update, Dict[str, Any]], Awaitable[Any]],
        event: Update,
        data: Dict[str, Any]
    ) -> Any:
        if isinstance(event.event, (Message, CallbackQuery)):
            user: User = data.get('user')
            if user:
                try:
                    # Update last active timestamp
                    user.last_active = datetime.utcnow()
                    session: AsyncSession = data['session']
                    await session.commit()
                    
                    # Update cache
                    await cache.set(
                        f"user_active:{user.id}",
                        True,
                        timeout=86400
                    )
                    
                    # Track activity
                    analytics = AnalyticsService(session)
                    await analytics.track_user_activity(
                        user_id=user.id,
                        activity_type='message' if isinstance(event.event, Message) else 'callback',
                        metadata={
                            'content_type': event.event.content_type if isinstance(event.event, Message) else None,
                            'command': event.event.text if isinstance(event.event, Message) and event.event.text.startswith('/') else None
                        }
                    )
                    
                except Exception as e:
                    logger.error(f"Error tracking activity: {e}")
        
        return await handler(event, data)

class RateLimitMiddleware(BaseMiddleware):
    """Rate limiting middleware"""
    
    DEFAULT_RATE = 30  # messages per minute
    INCREASED_RATE = 60  # for admins/special users
    
    async def __call__(
        self,
        handler: Callable[[Update, Dict[str, Any]], Awaitable[Any]],
        event: Update,
        data: Dict[str, Any]
    ) -> Any:
        if isinstance(event.event, (Message, CallbackQuery)):
            user: User = data.get('user')
            if user:
                try:
                    # Get rate limit based on user role
                    rate_limit = self.INCREASED_RATE if user.is_admin else self.DEFAULT_RATE
                    
                    # Check rate limit
                    key = f"rate_limit:{user.id}"
                    count = await cache.increment(key)
                    if count == 1:
                        await cache.expire(key, 60)  # 1 minute window
                        
                    if count > rate_limit:
                        # Rate limit exceeded
                        if isinstance(event.event, Message):
                            await event.event.answer(
                                TEXTS[user.language]['rate_limit_exceeded']
                            )
                        return
                        
                except Exception as e:
                    logger.error(f"Rate limit error: {e}")
        
        return await handler(event, data)

class MetricsMiddleware(BaseMiddleware):
    """Metrics collection middleware"""
    
    async def __call__(
        self,
        handler: Callable[[Update, Dict[str, Any]], Awaitable[Any]],
        event: Update,
        data: Dict[str, Any]
    ) -> Any:
        start_time = datetime.utcnow()
        
        try:
            # Track request
            if isinstance(event.event, Message):
                metrics_manager.track_bot_message(
                    message_type=event.event.content_type
                )
            elif isinstance(event.event, CallbackQuery):
                metrics_manager.track_bot_callback()
            
            # Execute handler
            result = await handler(event, data)
            
            # Calculate duration
            duration = (datetime.utcnow() - start_time).total_seconds()
            
            # Track response time
            metrics_manager.observe(
                'bot_response_time',
                duration,
                labels={
                    'handler_type': 'message' if isinstance(event.event, Message) else 'callback'
                }
            )
            
            return result
            
        except Exception as e:
            # Track error
            metrics_manager.track_bot_error(
                error_type=type(e).__name__
            )
            raise

class LoggingMiddleware(BaseMiddleware):
    """Enhanced logging middleware"""
    
    async def __call__(
        self,
        handler: Callable[[Update, Dict[str, Any]], Awaitable[Any]],
        event: Update,
        data: Dict[str, Any]
    ) -> Any:
        # Prepare log data
        user: User = data.get('user')
        log_data = {
            'user_id': user.id if user else None,
            'telegram_id': user.telegram_id if user else None,
            'update_id': event.update_id,
            'timestamp': datetime.utcnow().isoformat()
        }
        
        if isinstance(event.event, Message):
            log_data.update({
                'event_type': 'message',
                'content_type': event.event.content_type,
                'text': event.event.text if event.event.content_type == 'text' else None
            })
        elif isinstance(event.event, CallbackQuery):
            log_data.update({
                'event_type': 'callback',
                'data': event.event.data
            })
        
        try:
            # Log request
            logger.info(
                f"Incoming {log_data['event_type']}",
                extra={'data': log_data}
            )
            
            # Execute handler
            start_time = datetime.utcnow()
            result = await handler(event, data)
            duration = (datetime.utcnow() - start_time).total_seconds()
            
            # Log response
            log_data['duration'] = duration
            logger.info(
                f"Completed {log_data['event_type']}",
                extra={'data': log_data}
            )
            
            return result
            
        except Exception as e:
            # Log error
            log_data['error'] = str(e)
            log_data['traceback'] = traceback.format_exc()
            logger.error(
                f"Error in {log_data['event_type']}",
                extra={'data': log_data},
                exc_info=True
            )
            raise

class ErrorHandlerMiddleware(BaseMiddleware):
    """Global error handling middleware"""
    
    async def __call__(
        self,
        handler: Callable[[Update, Dict[str, Any]], Awaitable[Any]],
        event: Update,
        data: Dict[str, Any]
    ) -> Any:
        try:
            return await handler(event, data)
            
        except ValidationError as e:
            await self._handle_validation_error(event, e, data)
            
        except DatabaseError as e:
            await self._handle_database_error(event, e, data)
            
        except AuthenticationError as e:
            await self._handle_auth_error(event, e, data)
            
        except Exception as e:
            await self._handle_unknown_error(event, e, data)
    
    async def _handle_validation_error(
        self,
        event: Update,
        error: ValidationError,
        data: Dict
    ):
        """Handle validation errors"""
        user: User = data.get('user')
        if isinstance(event.event, (Message, CallbackQuery)):
            await event.event.answer(
                TEXTS[user.language]['validation_error'] if user else str(error)
            )
    
    async def _handle_database_error(
        self,
        event: Update,
        error: DatabaseError,
        data: Dict
    ):
        """Handle database errors"""
        logger.error(f"Database error: {error}", exc_info=True)
        user: User = data.get('user')
        if isinstance(event.event, (Message, CallbackQuery)):
            await event.event.answer(
                TEXTS[user.language]['error'] if user else "System error"
            )
    
    async def _handle_auth_error(
        self,
        event: Update,
        error: AuthenticationError,
        data: Dict
    ):
        """Handle authentication errors"""
        logger.error(f"Auth error: {error}", exc_info=True)
        if isinstance(event.event, (Message, CallbackQuery)):
            await event.event.answer(
                "Authentication error. Please try again."
            )
    
    async def _handle_unknown_error(
        self,
        event: Update,
        error: Exception,
        data: Dict
    ):
        """Handle unknown errors"""
        logger.error(
            f"Unknown error: {error}",
            exc_info=True,
            extra={'update_id': event.update_id}
        )
        
        user: User = data.get('user')
        if isinstance(event.event, (Message, CallbackQuery)):
            await event.event.answer(
                TEXTS[user.language]['error'] if user else "System error"
            )

# Register all middlewares
def setup_middlewares(dp):
    """Setup all middlewares"""
    middlewares = [
        DatabaseMiddleware(),
        AuthenticationMiddleware(),
        LanguageMiddleware(),
        UserActivityMiddleware(),
        RateLimitMiddleware(),
        MetricsMiddleware(),
        LoggingMiddleware(),
        ErrorHandlerMiddleware()
    ]
    
    for middleware in middlewares:
        dp.message.middleware(middleware)
        dp.callback_query.middleware(middleware)

__all__ = [
    'DatabaseMiddleware',
    'AuthenticationMiddleware',
    'LanguageMiddleware',
    'UserActivityMiddleware',
    'RateLimitMiddleware',
    'MetricsMiddleware',
    'LoggingMiddleware',
    'ErrorHandlerMiddleware',
    'setup_middlewares'
]

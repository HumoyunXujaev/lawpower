from aiogram import Bot, Dispatcher
from aiogram.fsm.storage.redis import RedisStorage
from aiogram.fsm.storage.memory import MemoryStorage
import logging

from telegram_bot.core.config import settings
from telegram_bot.services.cache_service import cache_service
from telegram_bot.bot.handlers import (
    register_user_handlers,
    register_admin_handlers,
    register_error_handlers,
    register_consultation_handlers,
    register_question_handlers,
    register_payment_handlers
)
from telegram_bot.bot.middlewares import (
    DatabaseMiddleware,
    RateLimitMiddleware,
    LoggingMiddleware,
    ErrorHandlerMiddleware,
    AuthenticationMiddleware,
    LanguageMiddleware,
    UserActivityMiddleware
)

logger = logging.getLogger(__name__)

# Initialize bot
bot = Bot(token=settings.BOT_TOKEN.get_secret_value(), parse_mode="HTML")

# Initialize FSM storage
if settings.REDIS_URL:
    storage = RedisStorage(redis=cache_service.redis)
else:
    storage = MemoryStorage()
    logger.warning("Using MemoryStorage for FSM - not recommended for production")

# Initialize dispatcher
dp = Dispatcher(storage=storage)

async def setup_bot():
    """Setup bot with all handlers and middlewares"""
    try:
        # Register middlewares
        dp.message.middleware(DatabaseMiddleware())
        dp.message.middleware(RateLimitMiddleware())
        dp.message.middleware(LoggingMiddleware())
        dp.message.middleware(ErrorHandlerMiddleware())
        dp.message.middleware(AuthenticationMiddleware())
        dp.message.middleware(LanguageMiddleware())
        dp.message.middleware(UserActivityMiddleware())
        
        # Register callback query middlewares
        dp.callback_query.middleware(DatabaseMiddleware())
        dp.callback_query.middleware(RateLimitMiddleware())
        dp.callback_query.middleware(LoggingMiddleware())
        dp.callback_query.middleware(ErrorHandlerMiddleware())
        dp.callback_query.middleware(AuthenticationMiddleware())
        dp.callback_query.middleware(LanguageMiddleware())
        dp.callback_query.middleware(UserActivityMiddleware())
        
        # Register handlers
        register_user_handlers(dp)
        register_admin_handlers(dp)
        register_error_handlers(dp)
        register_consultation_handlers(dp)
        register_question_handlers(dp)
        register_payment_handlers(dp)
        
        logger.info("Bot setup completed successfully")
        
    except Exception as e:
        logger.error(f"Error setting up bot: {e}", exc_info=True)
        raise

async def start_polling():
    """Start bot polling"""
    try:
        # Setup bot
        await setup_bot()
        
        # Start polling
        await dp.start_polling(bot, skip_updates=True)
        
        logger.info("Bot polling started")
        
    except Exception as e:
        logger.error(f"Error starting bot: {e}", exc_info=True)
        raise

async def stop_polling():
    """Stop bot polling"""
    try:
        await dp.stop_polling()
        await bot.session.close()
        
        logger.info("Bot polling stopped")
        
    except Exception as e:
        logger.error(f"Error stopping bot: {e}", exc_info=True)

__all__ = [
    'bot',
    'dp',
    'setup_bot',
    'start_polling',
    'stop_polling'
]

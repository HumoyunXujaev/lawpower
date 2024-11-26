from typing import Dict, Any
import logging
from aiogram import Dispatcher

from telegram_bot.bot.handlers.users import register_user_handlers
from telegram_bot.bot.handlers.admin import register_admin_handlers
from telegram_bot.bot.handlers.questions import register_question_handlers
from telegram_bot.bot.handlers.consultations import register_consultation_handlers
from telegram_bot.bot.handlers.payments import register_payment_handlers
from telegram_bot.bot.handlers.faq import register_faq_handlers
from telegram_bot.bot.handlers.support import register_support_handlers
from telegram_bot.bot.handlers.errors import register_error_handlers

logger = logging.getLogger(__name__)

def setup_handlers(dp: Dispatcher) -> None:
    """Setup all bot handlers"""
    handlers = [
        ("users", register_user_handlers),
        ("admin", register_admin_handlers),
        ("questions", register_question_handlers),
        ("consultations", register_consultation_handlers), 
        ("payments", register_payment_handlers),
        ("faq", register_faq_handlers),
        ("support", register_support_handlers),
        ("errors", register_error_handlers)
    ]

    for name, register_func in handlers:
        try:
            register_func(dp)
            logger.info(f"Successfully registered {name} handlers")
        except Exception as e:
            logger.error(f"Failed to register {name} handlers: {e}")
            raise

__all__ = ['setup_handlers']
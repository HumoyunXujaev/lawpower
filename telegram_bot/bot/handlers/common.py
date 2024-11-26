from aiogram import Router, F
from aiogram.filters import Command, CommandStart
from aiogram.types import Message, CallbackQuery
from aiogram.fsm.context import FSMContext
from datetime import datetime
import logging

from telegram_bot.core.config import settings
from telegram_bot.core.constants import TEXTS
from telegram_bot.models import User, Question, Answer
from telegram_bot.services.analytics import AnalyticsService
from telegram_bot.services.questions import QuestionService
from telegram_bot.core.cache import cache_service as cache
from telegram_bot.bot.states import UserState
from telegram_bot.bot.keyboards import (
    get_language_keyboard,
    get_main_menu,
    get_help_keyboard,
    get_settings_keyboard
)

logger = logging.getLogger(__name__)
router = Router(name='common')

@router.message(CommandStart())
async def cmd_start(message: Message, state: FSMContext, user: User, session):
    """Handle /start command"""
    try:
        # Clear state
        await state.clear()
        
        # Track analytics
        analytics = AnalyticsService(session)
        await analytics.track_event(
            user_id=user.id,
            event_type="bot_start",
            data={
                "source": message.get_args() or "direct",
                "platform": message.from_user.language_code
            }
        )
        
        # Show language selection for new users
        if not user.language:
            await message.answer(
                "🌐 Выберите язык / Tilni tanlang",
                reply_markup=get_language_keyboard()
            )
            await state.set_state(UserState.selecting_language)
        else:
            await message.answer(
                TEXTS[user.language]['welcome_back'],
                reply_markup=get_main_menu(user.language)
            )
            
        # Update activity
        user.last_active = datetime.utcnow()
        await session.commit()
        await cache.set(f"user_active:{user.id}", True, expire=86400)
        
    except Exception as e:
        logger.error(f"Error in start command: {e}")
        await message.answer("An error occurred. Please try again.")

@router.message(Command("help"))
async def cmd_help(message: Message, user: User, session):
    """Handle /help command"""
    try:
        # Get FAQ questions
        question_service = QuestionService(session)
        faq = await question_service.get_faq_questions(user.language)
        
        # Format help message
        text = TEXTS[user.language]['help_message'] + "\n\n"
        
        if faq:
            text += "📝 " + TEXTS[user.language]['faq_title'] + "\n\n"
            for q in faq[:5]:
                text += f"❓ {q.question_text}\n"
                if q.answers:
                    text += f"✅ {q.answers[0].answer_text}\n"
                text += "\n"
        
        await message.answer(
            text,
            reply_markup=get_help_keyboard(user.language)
        )
        
        # Track analytics
        analytics = AnalyticsService(session)
        await analytics.track_event(
            user_id=user.id,
            event_type="help_request"
        )
        
    except Exception as e:
        logger.error(f"Error in help command: {e}")
        await message.answer(TEXTS[user.language]['error'])

@router.message(Command("settings"))
async def cmd_settings(message: Message, user: User):
    """Handle /settings command"""
    try:
        await message.answer(
            TEXTS[user.language]['settings_menu'],
            reply_markup=get_settings_keyboard(user.language)
        )
    except Exception as e:
        logger.error(f"Error in settings command: {e}")
        await message.answer(TEXTS[user.language]['error'])

@router.callback_query(F.data.startswith("language:"))
async def change_language(callback: CallbackQuery, user: User, session):
    """Handle language change"""
    try:
        language = callback.data.split(":")[1]
        old_language = user.language
        
        # Update user language
        user.language = language
        await session.commit()
        
        # Clear cache
        await cache.delete(f"user:{user.id}")
        
        # Send confirmation
        await callback.message.edit_text(
            TEXTS[language]['language_changed']
        )
        
        # Show main menu
        await callback.message.answer(
            TEXTS[language]['welcome'],
            reply_markup=get_main_menu(language)
        )
        
        # Track analytics
        analytics = AnalyticsService(session)
        await analytics.track_event(
            user_id=user.id,
            event_type="language_change",
            data={
                "old_language": old_language,
                "new_language": language
            }
        )
        
    except Exception as e:
        logger.error(f"Error changing language: {e}")
        await callback.message.answer(TEXTS[user.language]['error'])

@router.message(Command("cancel"))
async def cmd_cancel(message: Message, state: FSMContext, user: User):
    """Handle /cancel command"""
    try:
        current_state = await state.get_state()
        
        if current_state is None:
            await message.answer(
                TEXTS[user.language]['nothing_to_cancel'],
                reply_markup=get_main_menu(user.language)
            )
            return
            
        # Clear state
        await state.clear()
        
        await message.answer(
            TEXTS[user.language]['cancelled'],
            reply_markup=get_main_menu(user.language)
        )
        
    except Exception as e:
        logger.error(f"Error in cancel command: {e}")
        await message.answer(TEXTS[user.language]['error'])
from aiogram import Router, F, Dispatcher
from aiogram.filters import Command, CommandStart
from aiogram.types import Message, CallbackQuery
from aiogram.fsm.context import FSMContext
import logging

from telegram_bot.core.constants import TEXTS
from telegram_bot.models import User
from telegram_bot.services.analytics import AnalyticsService
from telegram_bot.bot.keyboards import (
    get_start_keyboard,
    get_language_keyboard,
    get_settings_keyboard
)
from telegram_bot.bot.states import UserState

logger = logging.getLogger(__name__)
router = Router(name='users')

@router.message(CommandStart())
async def cmd_start(message: Message, user: User, state: FSMContext, session):
    """Handle /start command"""
    try:
        # Clear any existing state
        await state.clear()
        
        # Track analytics
        analytics = AnalyticsService(session)
        await analytics.track_event(
            user_id=user.id,
            event_type='bot_start',
            data={
                'source': message.get_args() or 'direct',
                'platform': message.from_user.language_code
            }
        )
        
        # Check if language is set
        if not user.language:
            await message.answer(
                "🌐 Выберите язык / Tilni tanlang",
                reply_markup=get_language_keyboard()
            )
            await state.set_state(UserState.selecting_language)
        else:
            await message.answer(
                TEXTS[user.language]['welcome_back'],
                reply_markup=get_start_keyboard(user.language)
            )
        
    except Exception as e:
        logger.error(f"Error in start command: {e}", exc_info=True)
        await message.answer("An error occurred. Please try again.")

@router.callback_query(F.data.startswith("language:"))
async def process_language_selection(
    callback: CallbackQuery,
    user: User,
    state: FSMContext,
    session
):
    """Handle language selection"""
    try:
        language = callback.data.split(":")[1]
        
        # Update user language
        user.language = language
        await session.commit()
        
        # Send welcome message
        await callback.message.edit_text(
            TEXTS[language]['welcome'],
            reply_markup=get_start_keyboard(language)
        )
        
        # Clear state
        await state.clear()
        
        # Track language selection
        analytics = AnalyticsService(session)
        await analytics.track_event(
            user_id=user.id,
            event_type='language_selected',
            data={'language': language}
        )
        
    except Exception as e:
        logger.error(f"Error selecting language: {e}", exc_info=True)
        await callback.message.edit_text("An error occurred. Please try again.")

@router.message(Command("help"))
async def cmd_help(message: Message, user: User):
    """Handle /help command"""
    try:
        await message.answer(
            TEXTS[user.language]['help_message'],
            reply_markup=get_start_keyboard(user.language)
        )
    except Exception as e:
        logger.error(f"Error in help command: {e}", exc_info=True)
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
        logger.error(f"Error in settings command: {e}", exc_info=True)
        await message.answer(TEXTS[user.language]['error'])

@router.message(Command("profile"))
async def cmd_profile(message: Message, user: User, session):
    """Handle /profile command"""
    try:
        # Get user statistics
        analytics = AnalyticsService(session)
        stats = await analytics.get_user_stats(user.id)
        
        # Format profile text
        text = TEXTS[user.language]['profile_info'].format(
            full_name=user.full_name,
            username=f"@{user.username}" if user.username else "-",
            language=user.language.upper(),
            join_date=user.created_at.strftime("%d.%m.%Y"),
            questions_count=stats['questions_count'],
            consultations_count=stats['consultations_count']
        )
        
        await message.answer(
            text,
            reply_markup=get_start_keyboard(user.language)
        )
        
    except Exception as e:
        logger.error(f"Error in profile command: {e}", exc_info=True)
        await message.answer(TEXTS[user.language]['error'])

@router.message(Command("cancel"))
async def cmd_cancel(message: Message, state: FSMContext, user: User):
    """Handle /cancel command"""
    try:
        current_state = await state.get_state()
        if current_state is None:
            await message.answer(
                TEXTS[user.language]['nothing_to_cancel'],
                reply_markup=get_start_keyboard(user.language)
            )
            return
            
        await state.clear()
        await message.answer(
            TEXTS[user.language]['cancelled'],
            reply_markup=get_start_keyboard(user.language)
        )
        
    except Exception as e:
        logger.error(f"Error in cancel command: {e}", exc_info=True)
        await message.answer(TEXTS[user.language]['error'])

def register_handlers(dp: Dispatcher):
    """Register user handlers"""
    dp.include_router(router)

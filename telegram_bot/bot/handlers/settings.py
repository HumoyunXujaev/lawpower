from aiogram import Router, F, Dispatcher
from aiogram.filters import Command
from aiogram.types import Message, CallbackQuery
from aiogram.fsm.context import FSMContext
import logging

from telegram_bot.core.constants import TEXTS
from telegram_bot.models import User
from telegram_bot.services.analytics import AnalyticsService
from telegram_bot.bot.keyboards import (
    get_start_keyboard,
    get_settings_keyboard,
    get_notification_settings_keyboard,
    get_language_keyboard
)
from telegram_bot.bot.states import SettingsState

logger = logging.getLogger(__name__)
router = Router(name='settings')

@router.message(Command("settings"))
@router.message(F.text.in_([TEXTS['uz']['settings'], TEXTS['ru']['settings']]))
async def show_settings(message: Message, user: User):
    """Show settings menu"""
    try:
        await message.answer(
            TEXTS[user.language]['settings_menu'],
            reply_markup=get_settings_keyboard(user.language)
        )
    except Exception as e:
        logger.error(f"Error showing settings: {e}", exc_info=True)
        await message.answer(TEXTS[user.language]['error'])

@router.callback_query(F.data == "settings:language")
async def change_language(callback: CallbackQuery, user: User):
    """Show language selection"""
    try:
        await callback.message.edit_text(
            "🌐 Выберите язык / Tilni tanlang",
            reply_markup=get_language_keyboard()
        )
    except Exception as e:
        logger.error(f"Error changing language: {e}", exc_info=True)
        await callback.message.edit_text(TEXTS[user.language]['error'])

@router.callback_query(F.data == "settings:notifications")
async def notification_settings(callback: CallbackQuery, user: User, session):
    """Show notification settings"""
    try:
        # Get current settings
        settings = user.settings.get('notifications', {})
        
        await callback.message.edit_text(
            TEXTS[user.language]['notification_settings'],
            reply_markup=get_notification_settings_keyboard(
                user.language,
                settings
            )
        )
        
    except Exception as e:
        logger.error(f"Error showing notification settings: {e}", exc_info=True)
        await callback.message.edit_text(TEXTS[user.language]['error'])

@router.callback_query(F.data.startswith("notifications:"))
async def toggle_notification(callback: CallbackQuery, user: User, session):
    """Toggle notification setting"""
    try:
        notification_type = callback.data.split(":")[1]
        
        # Get current settings
        settings = user.settings.get('notifications', {})
        
        # Toggle setting
        current = settings.get(notification_type, True)
        settings[notification_type] = not current
        
        # Update user settings
        if 'notifications' not in user.settings:
            user.settings['notifications'] = {}
        user.settings['notifications'] = settings
        await session.commit()
        
        # Update keyboard
        await callback.message.edit_reply_markup(
            reply_markup=get_notification_settings_keyboard(
                user.language,
                settings
            )
        )
        
        # Track setting change
        analytics = AnalyticsService(session)
        await analytics.track_event(
            user_id=user.id,
            event_type='notification_setting_changed',
            data={
                'type': notification_type,
                'enabled': settings[notification_type]
            }
        )
        
    except Exception as e:
        logger.error(f"Error toggling notification: {e}", exc_info=True)
        await callback.message.edit_text(TEXTS[user.language]['error'])

@router.callback_query(F.data == "settings:profile")
async def show_profile(callback: CallbackQuery, user: User, session):
    """Show user profile"""
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
        
        await callback.message.edit_text(
            text,
            reply_markup=get_settings_keyboard(user.language)
        )
        
        # Track profile viewed
        await analytics.track_event(
            user_id=user.id,
            event_type='profile_viewed'
        )
        
    except Exception as e:
        logger.error(f"Error showing profile: {e}", exc_info=True)
        await callback.message.edit_text(TEXTS[user.language]['error'])

@router.callback_query(F.data == "back_to_menu")
async def back_to_menu(callback: CallbackQuery, user: User):
    """Return to main menu"""
    try:
        await callback.message.edit_text(
            TEXTS[user.language]['main_menu'],
            reply_markup=get_start_keyboard(user.language)
        )
    except Exception as e:
        logger.error(f"Error returning to menu: {e}", exc_info=True)
        await callback.message.edit_text(TEXTS[user.language]['error'])

def register_handlers(dp: Dispatcher):
    """Register settings handlers"""
    dp.include_router(router)

# Register message handlers
router.message.register(
    show_settings,
    Command("settings")
)
router.message.register(
    show_settings,
    F.text.in_([TEXTS['uz']['settings'], TEXTS['ru']['settings']])
)

# Register callback handlers
router.callback_query.register(
    change_language,
    F.data == "settings:language"
)
router.callback_query.register(
    notification_settings,
    F.data == "settings:notifications"
)
router.callback_query.register(
    toggle_notification,
    F.data.startswith("notifications:")
)
router.callback_query.register(
    show_profile,
    F.data == "settings:profile"
)
router.callback_query.register(
    back_to_menu,
    F.data == "back_to_menu"
)

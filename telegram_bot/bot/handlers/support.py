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
    get_support_keyboard,
    get_contact_keyboard,
    get_cancel_keyboard
)
from aiogram.types import (
    InlineKeyboardMarkup,
    InlineKeyboardButton,
    ReplyKeyboardMarkup,
    KeyboardButton,
    ReplyKeyboardRemove
)
from telegram_bot.bot.states import SupportState
from telegram_bot.core.config import settings

logger = logging.getLogger(__name__)
router = Router(name='support')

@router.message(Command("support"))
@router.message(F.text.in_([TEXTS['uz']['support'], TEXTS['ru']['support']]))
async def show_support(message: Message, user: User):
    """Show support menu"""
    try:
        await message.answer(
            TEXTS[user.language]['support_menu'],
            reply_markup=get_support_keyboard(user.language)
        )
    except Exception as e:
        logger.error(f"Error showing support: {e}", exc_info=True)
        await message.answer(TEXTS[user.language]['error'])

@router.callback_query(F.data == "support:contact")
async def start_support_chat(callback: CallbackQuery, state: FSMContext, user: User):
    """Start support chat"""
    try:
        await callback.message.edit_text(
            TEXTS[user.language]['describe_problem'],
            reply_markup=get_cancel_keyboard(user.language)
        )
        await state.set_state(SupportState.describing_issue)
        
    except Exception as e:
        logger.error(f"Error starting support chat: {e}", exc_info=True)
        await callback.message.edit_text(TEXTS[user.language]['error'])

@router.message(SupportState.describing_issue)
async def process_support_message(
    message: Message,
    state: FSMContext,
    user: User,
    session
):
    """Process support message"""
    try:
        # Save message to database and forward to support
        from telegram_bot.bot import bot
        
        # Forward to support chat/users
        support_text = (
            f"💬 Новое сообщение в поддержку\n\n"
            f"👤 {user.full_name}"
            f"{f' (@{user.username})' if user.username else ''}\n"
            f"🆔 {user.id}\n"
            f"🌐 {user.language.upper()}\n\n"
            f"📝 {message.text}"
        )
        
        # Send to support users
        sent = False
        for admin_id in settings.ADMIN_IDS:
            try:
                await bot.send_message(
                    admin_id,
                    support_text,
                    reply_markup=get_admin_support_keyboard(user.id)
                )
                sent = True
            except Exception as e:
                logger.error(f"Error forwarding to admin {admin_id}: {e}")
        
        if sent:
            await message.answer(
                TEXTS[user.language]['support_message_sent'],
                reply_markup=get_start_keyboard(user.language)
            )
        else:
            await message.answer(
                TEXTS[user.language]['support_unavailable'],
                reply_markup=get_start_keyboard(user.language)
            )
        
        # Track support request
        analytics = AnalyticsService(session)
        await analytics.track_event(
            user_id=user.id,
            event_type='support_message_sent',
            data={'message': message.text}
        )
        
        # Clear state
        await state.clear()
        
    except Exception as e:
        logger.error(f"Error processing support message: {e}", exc_info=True)
        await message.answer(TEXTS[user.language]['error'])
        await state.clear()

@router.callback_query(F.data == "support:faq")
async def show_faq(callback: CallbackQuery, user: User, session):
    """Show FAQ section"""
    try:
        from telegram_bot.services.questions import QuestionService
        
        # Get FAQ questions
        question_service = QuestionService(session)
        faq_questions = await question_service.get_faq_questions(user.language)
        
        if not faq_questions:
            await callback.message.edit_text(
                TEXTS[user.language]['no_faq'],
                reply_markup=get_support_keyboard(user.language)
            )
            return
        
        # Format FAQ text
        text = TEXTS[user.language]['faq_title'] + "\n\n"
        
        for i, question in enumerate(faq_questions, 1):
            text += f"{i}. ❓ {question.question_text}\n"
            if question.answers:
                text += f"✅ {question.answers[0].answer_text}\n"
            text += "\n"
        
        await callback.message.edit_text(
            text,
            reply_markup=get_support_keyboard(user.language)
        )
        
        # Track FAQ viewed
        analytics = AnalyticsService(session)
        await analytics.track_event(
            user_id=user.id,
            event_type='faq_viewed'
        )
        
    except Exception as e:
        logger.error(f"Error showing FAQ: {e}", exc_info=True)
        await callback.message.edit_text(TEXTS[user.language]['error'])

@router.callback_query(F.data == "support:report")
async def start_report(callback: CallbackQuery, state: FSMContext, user: User):
    """Start problem report"""
    try:
        await callback.message.edit_text(
            TEXTS[user.language]['describe_problem'],
            reply_markup=get_cancel_keyboard(user.language)
        )
        await state.set_state(SupportState.reporting_problem)
        
    except Exception as e:
        logger.error(f"Error starting report: {e}", exc_info=True)
        await callback.message.edit_text(TEXTS[user.language]['error'])

@router.message(SupportState.reporting_problem)
async def process_report(
    message: Message,
    state: FSMContext,
    user: User,
    session
):
    """Process problem report"""
    try:
        from telegram_bot.bot import bot
        
        # Format report message
        report_text = (
            f"⚠️ Новый репорт о проблеме\n\n"
            f"👤 {user.full_name}"
            f"{f' (@{user.username})' if user.username else ''}\n"
            f"🆔 {user.id}\n"
            f"🌐 {user.language.upper()}\n\n"
            f"📝 {message.text}"
        )
        
        # Send to admins
        sent = False
        for admin_id in settings.ADMIN_IDS:
            try:
                await bot.send_message(
                    admin_id,
                    report_text,
                    reply_markup=get_admin_report_keyboard(user.id)
                )
                sent = True
            except Exception as e:
                logger.error(f"Error sending report to admin {admin_id}: {e}")
        
        if sent:
            await message.answer(
                TEXTS[user.language]['report_sent'],
                reply_markup=get_start_keyboard(user.language)
            )
        else:
            await message.answer(
                TEXTS[user.language]['report_error'],
                reply_markup=get_start_keyboard(user.language)
            )
        
        # Track report
        analytics = AnalyticsService(session)
        await analytics.track_event(
            user_id=user.id,
            event_type='problem_reported',
            data={'message': message.text}
        )
        
        # Clear state
        await state.clear()
        
    except Exception as e:
        logger.error(f"Error processing report: {e}", exc_info=True)
        await message.answer(TEXTS[user.language]['error'])
        await state.clear()

def get_admin_support_keyboard(user_id: int):
    """Generate keyboard for admin support response"""
    return InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(
                text="✍️ Ответить",
                callback_data=f"admin:reply:{user_id}"
            )
        ],
        [
            InlineKeyboardButton(
                text="❌ Закрыть",
                callback_data=f"admin:close_support:{user_id}"
            )
        ]
    ])

def get_admin_report_keyboard(user_id: int):
    """Generate keyboard for admin report response"""
    return InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(
                text="✅ Принято",
                callback_data=f"admin:accept_report:{user_id}"
            )
        ],
        [
            InlineKeyboardButton(
                text="❌ Отклонить",
                callback_data=f"admin:reject_report:{user_id}"
            )
        ]
    ])

def register_handlers(dp: Dispatcher):
    """Register support handlers"""
    dp.include_router(router)

# Register message handlers
router.message.register(
    show_support,
    Command("support")
)
router.message.register(
    show_support,
    F.text.in_([TEXTS['uz']['support'], TEXTS['ru']['support']])
)
router.message.register(
    process_support_message,
    SupportState.describing_issue
)
router.message.register(
    process_report,
    SupportState.reporting_problem
)

# Register callback handlers
router.callback_query.register(
    start_support_chat,
    F.data == "support:contact"
)
router.callback_query.register(
    show_faq,
    F.data == "support:faq"
)
router.callback_query.register(
    start_report,
    F.data == "support:report"
)

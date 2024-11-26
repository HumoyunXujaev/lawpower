from aiogram import Router, F
from aiogram.filters import Command
from aiogram.types import Message, CallbackQuery
from aiogram.fsm.context import FSMContext
import logging

from telegram_bot.core.constants import TEXTS
from telegram_bot.models import User
from telegram_bot.services.questions import QuestionService
from telegram_bot.services.auto_answer import AutoAnswerService
from telegram_bot.bot.keyboards import (
    get_main_menu_keyboard,
    get_rating_keyboard
)
from telegram_bot.bot.states import QuestionState

logger = logging.getLogger(__name__)
router = Router(name='questions')

@router.message(F.text.in_([TEXTS['uz']['ask_question'], TEXTS['ru']['ask_question']]))
async def start_question(message: Message, state: FSMContext, user: User):
    """Start question asking flow"""
    try:
        await message.answer(
            TEXTS[user.language]['enter_question'],
            reply_markup=None
        )
        await state.set_state(QuestionState.waiting_for_question)
    except Exception as e:
        logger.error(f"Error starting question: {e}", exc_info=True)
        await message.answer(TEXTS[user.language]['error'])

@router.message(QuestionState.waiting_for_question)
async def process_question(
    message: Message,
    state: FSMContext,
    user: User,
    session
):
    """Process user's question and try to auto-answer"""
    try:
        question_text = message.text.strip()
        
        # Validate question
        if len(question_text) < 10:
            await message.answer(TEXTS[user.language]['question_too_short'])
            return
            
        if len(question_text) > 1000:
            await message.answer(TEXTS[user.language]['question_too_long'])
            return

        # Create question
        question_service = QuestionService(session)
        question = await question_service.create_question(
            user_id=user.id,
            question_text=question_text,
            language=user.language
        )

        # Try auto-answer
        auto_answer_service = AutoAnswerService(session)
        answer = await auto_answer_service.get_answer(
            question_text=question_text,
            language=user.language
        )

        if answer and answer['confidence'] >= 0.85:
            # Create auto-answer
            await question_service.create_answer(
                question_id=question.id,
                answer_text=answer['answer_text'],
                is_auto=True,
                metadata={
                    'confidence': answer['confidence'],
                    'source': answer['source']
                }
            )

            # Send answer with rating request
            await message.answer(
                f"{TEXTS[user.language]['auto_answer']}\n\n{answer['answer_text']}",
                reply_markup=get_rating_keyboard(user.language)
            )
        else:
            # Send confirmation and notify
            # If no auto-answer, send confirmation
            await message.answer(
                TEXTS[user.language]['question_received'],
                reply_markup=get_main_menu_keyboard(user.language)
            )
            
            # Notify admins about new question
            await notify_admins_new_question(question)

        # Clear state
        await state.clear()

    except Exception as e:
        logger.error(f"Error processing question: {e}", exc_info=True)
        await message.answer(TEXTS[user.language]['error'])
        await state.clear()

@router.callback_query(F.data.startswith("rate:"))
async def process_rating(
    callback: CallbackQuery,
    user: User,
    state: FSMContext,
    session
):
    """Process answer rating"""
    try:
        rating = int(callback.data.split(":")[1])
        
        # Get question from state
        data = await state.get_data()
        answer_id = data.get('current_answer_id')
        
        if not answer_id:
            await callback.answer(TEXTS[user.language]['error'])
            return

        # Save rating
        question_service = QuestionService(session)
        await question_service.rate_answer(
            answer_id=answer_id,
            rating=rating
        )

        # Thank user
        await callback.message.edit_text(
            TEXTS[user.language]['rating_saved'],
            reply_markup=get_main_menu_keyboard(user.language)
        )
        
        # Clear state
        await state.clear()

    except Exception as e:
        logger.error(f"Error processing rating: {e}", exc_info=True)
        await callback.message.edit_text(TEXTS[user.language]['error'])

@router.message(Command("my_questions"))
async def show_questions_history(
    message: Message,
    user: User,
    session
):
    """Show user's question history"""
    try:
        question_service = QuestionService(session)
        questions = await question_service.get_user_questions(user.id)

        if not questions:
            await message.answer(
                TEXTS[user.language]['no_questions'],
                reply_markup=get_main_menu_keyboard(user.language)
            )
            return

        # Format questions text
        text = TEXTS[user.language]['your_questions'] + "\n\n"
        
        for q in questions:
            text += f"❓ {q.question_text}\n"
            if q.answers:
                text += f"✅ {q.answers[0].answer_text}\n"
            text += f"📅 {q.created_at.strftime('%d.%m.%Y %H:%M')}\n\n"
            
            if len(text) > 3500:  # Split long messages
                await message.answer(text)
                text = ""

        if text:
            await message.answer(
                text, 
                reply_markup=get_main_menu_keyboard(user.language)
            )

    except Exception as e:
        logger.error(f"Error showing questions: {e}", exc_info=True)
        await message.answer(TEXTS[user.language]['error'])

async def notify_admins_new_question(question: "Question"):
    """Notify admins about new question"""
    try:
        from telegram_bot.bot import bot
        from telegram_bot.core.config import settings

        text = (
            f"📝 {TEXTS['ru']['new_question']}\n\n"
            f"👤 {question.user.full_name}"
            f"{f' (@{question.user.username})' if question.user.username else ''}\n"
            f"🌐 {question.language.upper()}\n\n"
            f"❓ {question.question_text}"
        )

        for admin_id in settings.ADMIN_IDS:
            try:
                await bot.send_message(
                    admin_id,
                    text,
                    reply_markup=get_admin_question_keyboard(question.id)
                )
            except Exception as e:
                logger.error(f"Error notifying admin {admin_id}: {e}")

    except Exception as e:
        logger.error(f"Error in admin notification: {e}", exc_info=True)

def register_handlers(dp):
    """Register question handlers"""
    dp.include_router(router)
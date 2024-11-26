from aiogram import Router, F
from aiogram.types import Message, CallbackQuery
from aiogram.fsm.context import FSMContext
from aiogram.filters import Command
import logging

from telegram_bot.core.constants import TEXTS
from telegram_bot.models import User, Question
from telegram_bot.services.questions import QuestionService
from telegram_bot.bot.states import QuestionState
from telegram_bot.bot.keyboards import (
    get_main_menu,
    get_similar_questions_keyboard,
    get_category_keyboard
)

logger = logging.getLogger(__name__)
router = Router(name='messages')

@router.message(Command("cancel"))
async def cancel_handler(message: Message, state: FSMContext, user: User):
    """Handle cancel command"""
    current_state = await state.get_state()
    if current_state is None:
        return
        
    await state.clear()
    await message.answer(
        TEXTS[user.language]['cancelled'],
        reply_markup=get_main_menu(user.language)
    )

@router.message(QuestionState.waiting_for_question)
async def process_question(message: Message, state: FSMContext, user: User, session):
    """Process user's question"""
    try:
        question_text = message.text.strip()
        
        # Validate question length
        if len(question_text) < 10:
            await message.answer(
                TEXTS[user.language]['question_too_short'],
                reply_markup=get_main_menu(user.language)
            )
            return
            
        if len(question_text) > 1000:
            await message.answer(
                TEXTS[user.language]['question_too_long'],
                reply_markup=get_main_menu(user.language)
            )
            return
        
        # Get question service
        question_service = QuestionService(session)
        
        # Find similar questions
        similar = await question_service.find_similar_questions(
            question_text,
            user.language
        )
        
        if similar:
            # Save question data
            await state.update_data(
                question_text=question_text,
                similar_questions=[(q.id, score) for q, score in similar]
            )
            await state.set_state(QuestionState.viewing_similar)
            
            # Format similar questions text
            text = TEXTS[user.language]['similar_questions_found'] + "\n\n"
            
            for i, (question, score) in enumerate(similar, 1):
                text += f"{i}. ❓ {question.question_text}\n"
                if question.answers:
                    text += f"✅ {question.answers[0].answer_text}\n"
                text += "\n"
            
            text += TEXTS[user.language]['similar_questions_prompt']
            
            await message.answer(
                text,
                reply_markup=get_similar_questions_keyboard(user.language)
            )
            
        else:
            # Create new question
            question = await question_service.create_question(
                user_id=user.id,
                question_text=question_text,
                language=user.language
            )
            
            await message.answer(
                TEXTS[user.language]['question_received'],
                reply_markup=get_main_menu(user.language)
            )
            
            # Clear state
            await state.clear()
            
            # Notify admins
            await notify_admins_new_question(question)
        
    except Exception as e:
        logger.error(f"Error processing question: {e}")
        await message.answer(
            TEXTS[user.language]['error'],
            reply_markup=get_main_menu(user.language)
        )
        await state.clear()

async def notify_admins_new_question(question: Question):
    """Notify admins about new question"""
    from telegram_bot.bot import bot
    from telegram_bot.core.config import settings
    
    text = f"📝 {TEXTS['ru']['new_question']}\n\n"
    text += f"👤 {question.user.full_name}"
    if question.user.username:
        text += f" (@{question.user.username})\n"
    else:
        text += "\n"
    text += f"🌐 {question.language.upper()}\n\n"
    text += f"❓ {question.question_text}"
    
    for admin_id in settings.ADMIN_IDS:
        try:
            await bot.send_message(admin_id, text)
        except Exception as e:
            logger.error(f"Error notifying admin {admin_id}: {e}")

@router.callback_query(F.data == "ask_anyway")
async def ask_anyway(callback: CallbackQuery, state: FSMContext, user: User, session):
    """Handle ask anyway button"""
    try:
        data = await state.get_data()
        question_text = data.get('question_text')
        
        if not question_text:
            await callback.answer(TEXTS[user.language]['error'])
            await state.clear()
            return
        
        # Create question
        question_service = QuestionService(session)
        question = await question_service.create_question(
            user_id=user.id,
            question_text=question_text,
            language=user.language
        )
        
        await callback.message.edit_text(
            TEXTS[user.language]['question_received'],
            reply_markup=get_main_menu(user.language)
        )
        
        # Notify admins
        await notify_admins_new_question(question)
        
        # Clear state
        await state.clear()
        
    except Exception as e:
        logger.error(f"Error asking anyway: {e}")
        await callback.message.edit_text(
            TEXTS[user.language]['error'],
            reply_markup=get_main_menu(user.language)
        )
        await state.clear()
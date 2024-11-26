# from aiogram import Router, F, Dispatcher
# from aiogram.filters import Command
# from aiogram.types import Message, CallbackQuery
# from aiogram.fsm.context import FSMContext
# import logging
# from datetime import datetime, timedelta
# from sqlalchemy import select
# import asyncio
# from telegram_bot.core.config import settings
# from telegram_bot.models import (
#     User, Question, Consultation,
#     ConsultationStatus, PaymentStatus,FAQ
# )
# from aiogram.types import (
#     InlineKeyboardMarkup,
#     InlineKeyboardButton,
#     ReplyKeyboardMarkup,
#     KeyboardButton,
#     ReplyKeyboardRemove
# )
# from telegram_bot.services.questions import QuestionService
# from telegram_bot.services.consultations import ConsultationService
# from telegram_bot.services.analytics import AnalyticsService
# from telegram_bot.bot.keyboards import (
#     get_admin_menu_keyboard,
#     get_admin_question_keyboard,
#     get_admin_consultation_keyboard,
#     get_admin_user_keyboard,
#     get_admin_broadcast_keyboard,
#     get_cancel_keyboard
# )
# from telegram_bot.bot.states import AdminState
# from telegram_bot.core.constants import TEXTS

# logger = logging.getLogger(__name__)
# router = Router(name='admin')

# @router.message(Command("admin"))
# async def cmd_admin(message: Message, user: User):
#     """Admin panel entry point"""
#     try:
#         if user.telegram_id not in settings.ADMIN_IDS:
#             return
            
#         await message.answer(
#             "👨‍💼 Админ-панель",
#             reply_markup=get_admin_menu_keyboard()
#         )
        
#     except Exception as e:
#         logger.error(f"Error in admin command: {e}", exc_info=True)
#         await message.answer("Произошла ошибка")

# @router.callback_query(F.data == "admin:stats")
# async def show_admin_stats(callback: CallbackQuery, user: User, session):
#     """Show admin statistics"""
#     try:
#         if user.telegram_id not in settings.ADMIN_IDS:
#             return
            
#         analytics = AnalyticsService(session)
#         stats = await analytics.get_dashboard_stats()
        
#         text = "📊 Статистика\n\n"
        
#         # Users stats
#         text += "👥 Пользователи:\n"
#         text += f"Всего: {stats['users']['total']:,}\n"
#         text += f"Активных: {stats['users']['active']:,}\n"
#         text += f"Новых за неделю: {stats['users']['new_week']:,}\n\n"
        
#         # Questions stats
#         text += "❓ Вопросы:\n"
#         text += f"Всего: {stats['questions']['total']:,}\n"
#         text += f"Без ответа: {stats['questions']['unanswered']:,}\n"
#         text += f"Авто-ответы: {stats['questions']['auto_answered']:,}\n\n"
        
#         # Consultations stats
#         text += "📅 Консультации:\n"
#         text += f"Всего: {stats['consultations']['total']:,}\n"
#         text += f"Ожидают: {stats['consultations']['pending']:,}\n"
#         text += f"Доход за месяц: {stats['consultations']['monthly_revenue']:,.0f} сум\n"
        
#         await callback.message.edit_text(
#             text,
#             reply_markup=get_admin_menu_keyboard()
#         )
        
#     except Exception as e:
#         logger.error(f"Error showing admin stats: {e}", exc_info=True)
#         await callback.message.edit_text("Произошла ошибка")

# @router.callback_query(F.data == "admin:questions")
# async def show_admin_questions(callback: CallbackQuery, user: User, session):
#     """Show unanswered questions"""
#     try:
#         if user.telegram_id not in settings.ADMIN_IDS:
#             return
            
#         question_service = QuestionService(session)
#         questions = await question_service.get_unanswered_questions(limit=10)
        
#         if not questions:
#             await callback.message.edit_text(
#                 "Нет неотвеченных вопросов",
#                 reply_markup=get_admin_menu_keyboard()
#             )
#             return
            
#         text = "❓ Неотвеченные вопросы:\n\n"
        
#         for q in questions:
#             text += f"👤 {q.user.full_name}"
#             if q.user.username:
#                 text += f" (@{q.user.username})"
#             text += f"\n📝 {q.question_text}\n"
#             text += f"🕒 {q.created_at.strftime('%d.%m.%Y %H:%M')}\n\n"
            
#         await callback.message.edit_text(
#             text,
#             reply_markup=get_admin_question_keyboard(questions)
#         )
        
#     except Exception as e:
#         logger.error(f"Error showing admin questions: {e}", exc_info=True)
#         await callback.message.edit_text("Произошла ошибка")

# @router.callback_query(F.data.startswith("admin:answer:"))
# async def answer_question(callback: CallbackQuery, state: FSMContext, user: User):
#     """Start answering question"""
#     try:
#         if user.telegram_id not in settings.ADMIN_IDS:
#             return
            
#         question_id = int(callback.data.split(":")[2])
        
#         # Save question ID in state
#         await state.set_state(AdminState.answering_question)
#         await state.update_data(question_id=question_id)
        
#         await callback.message.edit_text(
#             "📝 Введите ответ на вопрос:",
#             reply_markup=get_cancel_keyboard('ru')
#         )
        
#     except Exception as e:
#         logger.error(f"Error starting answer: {e}", exc_info=True)
#         await callback.message.edit_text("Произошла ошибка")

# @router.message(AdminState.answering_question)
# async def process_answer(message: Message, state: FSMContext, user: User, session):
#     """Process answer to question"""
#     try:
#         if user.telegram_id not in settings.ADMIN_IDS:
#             return
            
#         # Get question ID from state
#         data = await state.get_data()
#         question_id = data.get('question_id')
        
#         if not question_id:
#             await message.answer("Произошла ошибка")
#             await state.clear()
#             return
            
#         # Save answer
#         question_service = QuestionService(session)
#         answer = await question_service.create_answer(
#             question_id=question_id,
#             answer_text=message.text,
#             created_by=user.id
#         )
        
#         # Send answer to user
#         question = await question_service.get_question(question_id)
#         if question and question.user:
#             from telegram_bot.bot import bot
#             await bot.send_message(
#                 question.user.telegram_id,
#                 f"✅ Ответ на ваш вопрос:\n\n"
#                 f"❓ {question.question_text}\n\n"
#                 f"📝 {answer.answer_text}"
#             )
        
#         # Clear state
#         await state.clear()
        
#         # Show success message
#         await message.answer(
#             "✅ Ответ отправлен",
#             reply_markup=get_admin_menu_keyboard()
#         )
        
#         # Track answer
#         analytics = AnalyticsService(session)
#         await analytics.track_event(
#             user_id=user.id,
#             event_type="admin_answer",
#             data={"question_id": question_id}
#         )
        
#     except Exception as e:
#         logger.error(f"Error processing answer: {e}", exc_info=True)
#         await message.answer("Произошла ошибка")
#         await state.clear()

# @router.callback_query(F.data == "admin:broadcast")
# async def start_broadcast(callback: CallbackQuery, state: FSMContext, user: User):
#     """Start broadcast message"""
#     try:
#         if user.telegram_id not in settings.ADMIN_IDS:
#             return
            
#         await state.set_state(AdminState.creating_broadcast)
        
#         await callback.message.edit_text(
#             "📢 Введите сообщение для рассылки:",
#             reply_markup=get_cancel_keyboard('ru')
#         )
        
#     except Exception as e:
#         logger.error(f"Error starting broadcast: {e}", exc_info=True)
#         await callback.message.edit_text("Произошла ошибка")

# @router.message(AdminState.creating_broadcast)
# async def process_broadcast_message(message: Message, state: FSMContext, user: User):
#     """Save broadcast message and select target"""
#     try:
#         if user.telegram_id not in settings.ADMIN_IDS:
#             return
            
#         # Save message text
#         await state.update_data(broadcast_text=message.text)
        
#         # Show targeting options
#         await message.answer(
#             "📊 Выберите целевую аудиторию:",
#             reply_markup=get_admin_broadcast_keyboard()
#         )
        
#         await state.set_state(AdminState.selecting_broadcast_target)
        
#     except Exception as e:
#         logger.error(f"Error processing broadcast: {e}", exc_info=True)
#         await message.answer("Произошла ошибка")
#         await state.clear()

# @router.callback_query(F.data.startswith("broadcast:"), AdminState.selecting_broadcast_target)
# async def send_broadcast(callback: CallbackQuery, state: FSMContext, user: User, session):
#     """Send broadcast message"""
#     try:
#         if user.telegram_id not in settings.ADMIN_IDS:
#             return
            
#         target = callback.data.split(":")[1]
        
#         # Get message text
#         data = await state.get_data()
#         text = data.get('broadcast_text')
        
#         if not text:
#             await callback.message.edit_text("Произошла ошибка")
#             await state.clear()
#             return
            
#         # Get target users
#         query = select(User.telegram_id).filter(User.is_blocked == False)
        
#         if target == "active":
#             # Only users active in last 7 days
#             week_ago = datetime.utcnow() - timedelta(days=7)
#             query = query.filter(User.last_active >= week_ago)
#         elif target in ("uz", "ru"):
#             # Users with specific language
#             query = query.filter(User.language == target)
            
#         result = await session.execute(query)
#         user_ids = result.scalars().all()
        
#         # Send messages
#         from telegram_bot.bot import bot
#         success = 0
#         failed = 0
        
#         for uid in user_ids:
#             try:
#                 await bot.send_message(uid, text)
#                 success += 1
#                 await asyncio.sleep(0.05)  # Avoid flood limits
#             except Exception as e:
#                 logger.error(f"Error sending broadcast to {uid}: {e}")
#                 failed += 1
        
#         # Show results
#         await callback.message.edit_text(
#             f"📊 Результаты рассылки:\n\n"
#             f"✅ Успешно: {success}\n"
#             f"❌ Ошибки: {failed}\n"
#             f"📧 Всего: {len(user_ids)}",
#             reply_markup=get_admin_menu_keyboard()
#         )
        
#         # Track broadcast
#         analytics = AnalyticsService(session)
#         await analytics.track_event(
#             user_id=user.id,
#             event_type="broadcast_sent",
#             data={
#                 "target": target,
#                 "success": success,
#                 "failed": failed,
#                 "total": len(user_ids)
#             }
#         )
        
#         # Clear state
#         await state.clear()
        
#     except Exception as e:
#         logger.error(f"Error sending broadcast: {e}", exc_info=True)
#         await callback.message.edit_text("Произошла ошибка")
#         await state.clear()

# @router.callback_query(F.data.startswith("admin:user:"))
# async def show_user_details(callback: CallbackQuery, user: User, session):
#     """Show user details"""
#     try:
#         if user.telegram_id not in settings.ADMIN_IDS:
#             return
            
#         target_id = int(callback.data.split(":")[2])
        
#         # Get user
#         target_user = await session.get(User, target_id)
#         if not target_user:
#             await callback.answer("Пользователь не найден")
#             return
            
#         # Get user statistics
#         analytics = AnalyticsService(session)
#         stats = await analytics.get_user_stats(target_id)
        
#         text = (
#             f"👤 Пользователь: {target_user.full_name}\n"
#             f"🆔 ID: {target_user.telegram_id}\n"
#             f"👤 Username: {f'@{target_user.username}' if target_user.username else '-'}\n"
#             f"🌐 Язык: {target_user.language.upper()}\n"
#             f"📅 Регистрация: {target_user.created_at.strftime('%d.%m.%Y')}\n"
#             f"⏱ Последняя активность: {target_user.last_active.strftime('%d.%m.%Y %H:%M') if target_user.last_active else '-'}\n\n"
#             f"📊 Статистика:\n"
#             f"❓ Вопросов: {stats['questions_count']}\n"
#             f"📅 Консультаций: {stats['consultations_count']}\n"
#             f"💰 Всего оплачено: {stats['total_spent']:,.0f} сум\n"
#             f"⭐️ Средняя оценка: {stats['average_rating']:.1f}/5\n\n"
#             f"🚫 Заблокирован: {'Да' if target_user.is_blocked else 'Нет'}"
#         )
        
#         await callback.message.edit_text(
#             text,
#             reply_markup=get_admin_user_keyboard(target_id)
#         )
        
#     except Exception as e:
#         logger.error(f"Error showing user details: {e}", exc_info=True)
#         await callback.message.edit_text("Произошла ошибка")

# @router.callback_query(F.data.startswith("admin:block:"))
# async def toggle_user_block(callback: CallbackQuery, user: User, session):
#     """Toggle user block status"""
#     try:
#         if user.telegram_id not in settings.ADMIN_IDS:
#             return
            
#         target_id = int(callback.data.split(":")[2])
        
#         # Get user
#         target_user = await session.get(User, target_id)
#         if not target_user:
#             await callback.answer("Пользователь не найден")
#             return
            
#         # Toggle block status
#         target_user.is_blocked = not target_user.is_blocked
#         await session.commit()
        
#         # Send notification to user
#         from telegram_bot.bot import bot
#         try:
#             if target_user.is_blocked:
#                 await bot.send_message(
#                     target_user.telegram_id,
#                     TEXTS[target_user.language]['account_blocked']
#                 )
#             else:
#                 await bot.send_message(
#                     target_user.telegram_id,
#                     TEXTS[target_user.language]['account_unblocked']
#                 )
#         except Exception as e:
#             logger.error(f"Error notifying user about block status: {e}")
        
#         # Show updated user details
#         await show_user_details(callback, user, session)
        
#     except Exception as e:
#         logger.error(f"Error toggling user block: {e}", exc_info=True)
#         await callback.message.edit_text("Произошла ошибка")

# @router.callback_query(F.data == "admin:consultations")
# async def show_admin_consultations(callback: CallbackQuery, user: User, session):
#     """Show pending consultations"""
#     try:
#         if user.telegram_id not in settings.ADMIN_IDS:
#             return
            
#         consultation_service = ConsultationService(session)
#         consultations = await consultation_service.get_pending_consultations()
        
#         if not consultations:
#             await callback.message.edit_text(
#                 "Нет ожидающих консультаций",
#                 reply_markup=get_admin_menu_keyboard()
#             )
#             return
            
#         text = "📅 Ожидающие консультации:\n\n"
        
#         for consultation in consultations:
#             text += f"👤 {consultation.user.full_name}"
#             if consultation.user.username:
#                 text += f" (@{consultation.user.username})"
#             text += f"\n📞 {consultation.phone_number}\n"
#             text += f"💰 {consultation.amount:,.0f} сум\n"
#             text += f"📝 {consultation.description}\n"
#             text += f"🕒 {consultation.created_at.strftime('%d.%m.%Y %H:%M')}\n\n"
            
#         await callback.message.edit_text(
#             text,
#             reply_markup=get_admin_consultation_keyboard(consultations)
#         )
        
#     except Exception as e:
#         logger.error(f"Error showing consultations: {e}", exc_info=True)
#         await callback.message.edit_text("Произошла ошибка")

# @router.callback_query(F.data.startswith("admin:consultation:"))
# async def handle_consultation_action(callback: CallbackQuery, user: User, session):
#     """Handle consultation actions"""
#     try:
#         if user.telegram_id not in settings.ADMIN_IDS:
#             return
            
#         action, consultation_id = callback.data.split(":")[2:]
#         consultation_id = int(consultation_id)
        
#         consultation_service = ConsultationService(session)
#         consultation = await consultation_service.get_consultation(consultation_id)
        
#         if not consultation:
#             await callback.answer("Консультация не найдена")
#             return
            
#         if action == "approve":
#             # Approve consultation
#             await consultation_service.approve_consultation(consultation_id)
            
#             # Notify user
#             from telegram_bot.bot import bot
#             await bot.send_message(
#                 consultation.user.telegram_id,
#                 TEXTS[consultation.user.language]['consultation_approved']
#             )
            
#         elif action == "reject":
#             # Reject consultation
#             await consultation_service.reject_consultation(consultation_id)
            
#             # Notify user
#             from telegram_bot.bot import bot
#             await bot.send_message(
#                 consultation.user.telegram_id,
#                 TEXTS[consultation.user.language]['consultation_rejected']
#             )
        
#         # Show updated consultations list
#         await show_admin_consultations(callback, user, session)
        
#     except Exception as e:
#         logger.error(f"Error handling consultation action: {e}", exc_info=True)
#         await callback.message.edit_text("Произошла ошибка")


# @router.callback_query(F.data == "admin:faq")
# async def show_faq_list(callback: CallbackQuery, user: User, session):
#     """Show FAQ list to admin"""
#     if user.telegram_id not in settings.ADMIN_IDS:
#         return
        
#     # Get FAQ entries
#     result = await session.execute(
#         select(FAQ).order_by(FAQ.order.asc())
#     )
#     faqs = result.scalars().all()
    
#     text = "📋 FAQ List:\n\n"
#     for faq in faqs:
#         text += f"ID: {faq.id}\n"
#         text += f"Q: {faq.question[:50]}...\n"
#         text += f"Language: {faq.language}\n"
#         text += f"Status: {'✅' if faq.is_published else '❌'}\n\n"
        
#     keyboard = [
#         [InlineKeyboardButton(
#             text="➕ Add FAQ",
#             callback_data="admin:faq:add"
#         )],
#         [InlineKeyboardButton(
#             text="◀️ Back",
#             callback_data="admin:menu"
#         )]
#     ]
    
#     await callback.message.edit_text(
#         text,
#         reply_markup=InlineKeyboardMarkup(inline_keyboard=keyboard)
#     )

# @router.callback_query(F.data == "admin:faq:add")
# async def add_faq(callback: CallbackQuery, state: FSMContext, user: User):
#     """Start FAQ creation process"""
#     if user.telegram_id not in settings.ADMIN_IDS:
#         return
        
#     await state.set_state(AdminState.creating_faq)
#     await callback.message.edit_text(
#         "Please enter the question for FAQ:",
#         reply_markup=get_cancel_keyboard()
#     )

# @router.message(AdminState.creating_faq)
# async def process_faq_question(message: Message, state: FSMContext, session):
#     """Process FAQ question"""
#     await state.update_data(question=message.text)
#     await state.set_state(AdminState.creating_faq_answer)
#     await message.answer("Now enter the answer:")

# @router.message(AdminState.creating_faq_answer)
# async def process_faq_answer(message: Message, state: FSMContext, session):
#     """Process FAQ answer"""
#     data = await state.get_data()
    
#     faq = FAQ(
#         question=data['question'],
#         answer=message.text,
#         language='ru'  # Default language
#     )
#     session.add(faq)
#     await session.commit()
    
#     await state.clear()
#     await message.answer(
#         "✅ FAQ created successfully!",
#         reply_markup=get_admin_menu_keyboard()
#     )

# def register_handlers(dp: Dispatcher):
#     """Register admin handlers"""
#     dp.include_router(router)

# # Register message handlers
# router.message.register(cmd_admin, Command("admin"))
# router.message.register(
#     process_answer,
#     AdminState.answering_question
# )
# router.message.register(
#     process_broadcast_message,
#     AdminState.creating_broadcast
# )

# # Register callback handlers
# router.callback_query.register(
#     show_admin_stats,
#     F.data == "admin:stats"
# )
# router.callback_query.register(
#     show_admin_questions,
#     F.data == "admin:questions"
# )
# router.callback_query.register(
#     answer_question,
#     F.data.startswith("admin:answer:")
# )
# router.callback_query.register(
#     start_broadcast,
#     F.data == "admin:broadcast"
# )
# router.callback_query.register(
#     send_broadcast,
#     F.data.startswith("broadcast:"),
#     AdminState.selecting_broadcast_target
# )
# router.callback_query.register(
#     show_user_details,
#     F.data.startswith("admin:user:")
# )

# router.callback_query.register(
#     toggle_user_block,
#     F.data.startswith("admin:block:")
# )
# router.callback_query.register(
#     show_admin_consultations,
#     F.data == "admin:consultations"
# )
# router.callback_query.register(
#     handle_consultation_action,
#     F.data.startswith("admin:consultation:")
# )





from aiogram import Router, F, Dispatcher
from aiogram.filters import Command
from aiogram.types import Message, CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.fsm.context import FSMContext
import logging
from datetime import datetime, timedelta
from sqlalchemy import select, func
import asyncio

from telegram_bot.core.config import settings
from telegram_bot.models import (
    User, Question, Answer, Consultation,
    ConsultationStatus, PaymentStatus
)
from telegram_bot.services.analytics import AnalyticsService
from telegram_bot.services.questions import QuestionService
from telegram_bot.services.consultations import ConsultationService
from telegram_bot.bot.filters import IsAdmin
from telegram_bot.bot.states import AdminState
from telegram_bot.core.constants import TEXTS

logger = logging.getLogger(__name__)
router = Router(name='admin')

# Admin command handlers
@router.message(Command("admin"), IsAdmin())
async def admin_panel(message: Message):
    """Admin panel entry point"""
    keyboard = [
        [
            InlineKeyboardButton(text="📊 Statistics", callback_data="admin:stats"),
            InlineKeyboardButton(text="👥 Users", callback_data="admin:users")
        ],
        [
            InlineKeyboardButton(text="❓ Questions", callback_data="admin:questions"),
            InlineKeyboardButton(text="📅 Consultations", callback_data="admin:consultations")
        ],
        [
            InlineKeyboardButton(text="📢 Broadcast", callback_data="admin:broadcast"),
            InlineKeyboardButton(text="⚙️ Settings", callback_data="admin:settings")
        ]
    ]
    await message.answer(
        "👨‍💼 Welcome to Admin Panel\nSelect an option:",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=keyboard)
    )

@router.callback_query(F.data == "admin:stats", IsAdmin())
async def show_statistics(callback: CallbackQuery, session):
    """Show system statistics"""
    analytics = AnalyticsService(session)
    stats = await analytics.get_dashboard_stats()
    
    text = "📊 System Statistics\n\n"
    text += f"👥 Users: {stats['users']['total']}\n"
    text += f"➕ New today: {stats['users']['new_today']}\n"
    text += f"❓ Questions: {stats['questions']['total']}\n"
    text += f"✅ Answered: {stats['questions']['answered']}\n"
    text += f"📅 Consultations: {stats['consultations']['total']}\n"
    text += f"💰 Revenue: {stats['revenue']['total']:,.0f} sum\n"
    
    back_button = InlineKeyboardButton(text="◀️ Back", callback_data="admin:back")
    await callback.message.edit_text(
        text,
        reply_markup=InlineKeyboardMarkup(inline_keyboard=[[back_button]])
    )

@router.callback_query(F.data == "admin:broadcast", IsAdmin())
async def start_broadcast(callback: CallbackQuery, state: FSMContext):
    """Start broadcast message creation"""
    await state.set_state(AdminState.creating_broadcast)
    
    keyboard = [
        [
            InlineKeyboardButton(text="❌ Cancel", callback_data="admin:cancel")
        ]
    ]
    await callback.message.edit_text(
        "📢 Enter broadcast message text:",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=keyboard)
    )

@router.message(AdminState.creating_broadcast, IsAdmin())
async def process_broadcast_message(message: Message, state: FSMContext, session):
    """Process broadcast message text"""
    broadcast_text = message.text
    
    # Target selection keyboard
    keyboard = [
        [
            InlineKeyboardButton(text="👥 All Users", callback_data="broadcast:all"),
            InlineKeyboardButton(text="✅ Active Users", callback_data="broadcast:active")
        ],
        [
            InlineKeyboardButton(text="🇺🇿 Uzbek", callback_data="broadcast:uz"),
            InlineKeyboardButton(text="🇷🇺 Russian", callback_data="broadcast:ru")
        ],
        [
            InlineKeyboardButton(text="❌ Cancel", callback_data="admin:cancel")
        ]
    ]
    
    await state.update_data(broadcast_text=broadcast_text)
    await message.answer(
        "Select target audience:",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=keyboard)
    )
    await state.set_state(AdminState.selecting_broadcast_target)

@router.callback_query(F.data.startswith("broadcast:"), AdminState.selecting_broadcast_target, IsAdmin())
async def send_broadcast(callback: CallbackQuery, state: FSMContext, session):
    """Send broadcast message to selected audience"""
    target = callback.data.split(":")[1]
    data = await state.get_data()
    text = data['broadcast_text']
    
    # Get target users
    query = select(User.telegram_id).filter(User.is_blocked == False)
    if target == "active":
        week_ago = datetime.utcnow() - timedelta(days=7)
        query = query.filter(User.last_active >= week_ago)
    elif target in ["uz", "ru"]:
        query = query.filter(User.language == target)
        
    result = await session.execute(query)
    user_ids = result.scalars().all()
    
    # Send messages
    from telegram_bot.bot import bot
    sent = 0
    failed = 0
    
    for user_id in user_ids:
        try:
            await bot.send_message(user_id, text)
            sent += 1
            await asyncio.sleep(0.05)  # Rate limiting
        except Exception as e:
            logger.error(f"Failed to send broadcast to {user_id}: {e}")
            failed += 1
            
    # Show results
    await callback.message.edit_text(
        f"📊 Broadcast Results:\n\n"
        f"✅ Successfully sent: {sent}\n"
        f"❌ Failed: {failed}\n"
        f"👥 Total users: {len(user_ids)}"
    )
    await state.clear()

@router.callback_query(F.data == "admin:questions", IsAdmin())
async def show_questions(callback: CallbackQuery, session):
    """Show unanswered questions"""
    question_service = QuestionService(session)
    questions = await question_service.get_unanswered_questions(limit=10)
    
    if not questions:
        await callback.message.edit_text(
            "No unanswered questions",
            reply_markup=InlineKeyboardMarkup(inline_keyboard=[
                [InlineKeyboardButton(text="◀️ Back", callback_data="admin:back")]
            ])
        )
        return
        
    text = "❓ Unanswered Questions:\n\n"
    keyboard = []
    
    for q in questions:
        text += f"👤 {q.user.full_name}"
        if q.user.username:
            text += f" (@{q.user.username})"
        text += f"\n📝 {q.question_text}\n\n"
        
        keyboard.append([
            InlineKeyboardButton(
                text=f"Answer #{q.id}",
                callback_data=f"admin:answer:{q.id}"
            )
        ])
        
    keyboard.append([
        InlineKeyboardButton(text="◀️ Back", callback_data="admin:back")
    ])
    
    await callback.message.edit_text(
        text,
        reply_markup=InlineKeyboardMarkup(inline_keyboard=keyboard)
    )

@router.callback_query(F.data.startswith("admin:answer:"), IsAdmin())
async def start_answer(callback: CallbackQuery, state: FSMContext):
    """Start answering a question"""
    question_id = int(callback.data.split(":")[2])
    await state.set_state(AdminState.answering_question)
    await state.update_data(question_id=question_id)
    
    keyboard = [
        [InlineKeyboardButton(text="❌ Cancel", callback_data="admin:cancel")]
    ]
    await callback.message.edit_text(
        "Enter your answer:",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=keyboard)
    )

@router.message(AdminState.answering_question, IsAdmin())
async def process_answer(message: Message, state: FSMContext, session):
    """Process answer to question"""
    data = await state.get_data()
    question_id = data['question_id']
    
    question_service = QuestionService(session)
    question = await question_service.get_question(question_id)
    
    if not question:
        await message.answer("Question not found")
        await state.clear()
        return
        
    # Create answer
    answer = await question_service.create_answer(
        question_id=question_id,
        answer_text=message.text,
        created_by=message.from_user.id
    )
    
    # Notify user
    from telegram_bot.bot import bot
    await bot.send_message(
        question.user.telegram_id,
        f"✅ Your question has been answered:\n\n"
        f"❓ {question.question_text}\n\n"
        f"📝 {answer.answer_text}"
    )
    
    await message.answer("✅ Answer sent successfully")
    await state.clear()

@router.callback_query(F.data == "admin:users", IsAdmin())
async def show_users(callback: CallbackQuery, session):
    """Show user management panel"""
    total_users = await session.scalar(select(func.count(User.id)))
    active_users = await session.scalar(
        select(func.count(User.id))
        .filter(
            User.is_active == True,
            User.is_blocked == False
        )
    )
    
    text = "👥 User Management\n\n"
    text += f"Total users: {total_users}\n"
    text += f"Active users: {active_users}\n\n"
    text += "Select action:"
    
    keyboard = [
        [
            InlineKeyboardButton(text="📊 Statistics", callback_data="admin:user_stats"),
            InlineKeyboardButton(text="🔍 Search", callback_data="admin:user_search")
        ],
        [
            InlineKeyboardButton(text="⚠️ Blocked", callback_data="admin:blocked_users"),
            InlineKeyboardButton(text="◀️ Back", callback_data="admin:back")
        ]
    ]
    
    await callback.message.edit_text(
        text,
        reply_markup=InlineKeyboardMarkup(inline_keyboard=keyboard)
    )

@router.callback_query(F.data == "admin:settings", IsAdmin())
async def show_settings(callback: CallbackQuery):
    """Show admin settings panel"""
    keyboard = [
        [
            InlineKeyboardButton(text="🌐 Bot Settings", callback_data="admin:bot_settings"),
            InlineKeyboardButton(text="💳 Payment Settings", callback_data="admin:payment_settings")
        ],
        [
            InlineKeyboardButton(text="👥 User Roles", callback_data="admin:user_roles"),
            InlineKeyboardButton(text="⚙️ System Settings", callback_data="admin:system_settings")
        ],
        [
            InlineKeyboardButton(text="◀️ Back", callback_data="admin:back")
        ]
    ]
    
    await callback.message.edit_text(
        "⚙️ Admin Settings\nSelect category:",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=keyboard)
    )

# Register handlers
def register_handlers(dp: Dispatcher):
    """Register admin handlers"""
    dp.include_router(router)

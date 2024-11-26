from aiogram import Router, F
from aiogram.filters import Command
from aiogram.types import Message, CallbackQuery
from aiogram.fsm.context import FSMContext
from datetime import datetime, timedelta
import logging
from decimal import Decimal

from telegram_bot.core.constants import TEXTS
from telegram_bot.models import User, ConsultationStatus, PaymentProvider
from telegram_bot.services.consultations import ConsultationService
from telegram_bot.services.payments import PaymentService
from telegram_bot.core.errors import ValidationError
from telegram_bot.bot.keyboards import (
    get_consultation_type_keyboard,
    get_contact_keyboard,
    get_payment_methods_keyboard,
    get_consultation_time_keyboard,
    get_confirm_keyboard,
    get_main_menu_keyboard
)
from telegram_bot.bot.states import ConsultationState
from telegram_bot.utils.validators import validator

logger = logging.getLogger(__name__)
router = Router(name='consultations')

CONSULTATION_PRICES = {
    'online': Decimal('50000.00'),
    'office': Decimal('100000.00')
}

@router.message(Command("book"))
@router.message(F.text.in_([TEXTS['uz']['consultation'], TEXTS['ru']['consultation']]))
async def start_consultation(message: Message, state: FSMContext, user: User):
    """Start consultation booking process"""
    try:
        # Show consultation types
        await message.answer(
            TEXTS[user.language]['select_consultation_type'],
            reply_markup=get_consultation_type_keyboard(user.language)
        )
        await state.set_state(ConsultationState.selecting_type)
        
    except Exception as e:
        logger.error(f"Error starting consultation: {e}")
        await message.answer(TEXTS[user.language]['error'])
        await state.clear()

@router.callback_query(ConsultationState.selecting_type)
async def process_type_selection(callback: CallbackQuery, state: FSMContext, user: User):
    """Process consultation type selection"""
    try:
        consultation_type = callback.data.split(':')[1]
        if consultation_type not in CONSULTATION_PRICES:
            await callback.answer(TEXTS[user.language]['invalid_type'])
            return
            
        # Save type and show contact request
        await state.update_data(
            consultation_type=consultation_type,
            amount=CONSULTATION_PRICES[consultation_type]
        )
        
        await callback.message.edit_text(
            TEXTS[user.language]['enter_phone'],
            reply_markup=get_contact_keyboard(user.language)
        )
        await state.set_state(ConsultationState.entering_phone)
        
    except Exception as e:
        logger.error(f"Error processing consultation type: {e}")
        await callback.message.edit_text(TEXTS[user.language]['error'])
        await state.clear()

@router.message(ConsultationState.entering_phone)
async def process_phone(message: Message, state: FSMContext, user: User):
    """Process phone number input"""
    try:
        # Get phone number from contact or text
        if message.contact:
            phone = message.contact.phone_number
        else:
            phone = message.text
            
        # Validate phone
        try:
            phone = validator.phone_number(phone)
        except ValidationError:
            await message.answer(
                TEXTS[user.language]['invalid_phone'],
                reply_markup=get_contact_keyboard(user.language)
            )
            return
            
        # Save phone and request description
        await state.update_data(phone_number=phone)
        
        await message.answer(
            TEXTS[user.language]['describe_problem'],
            reply_markup=None
        )
        await state.set_state(ConsultationState.entering_description)
        
    except Exception as e:
        logger.error(f"Error processing phone: {e}")
        await message.answer(TEXTS[user.language]['error'])
        await state.clear()

@router.message(ConsultationState.entering_description)
async def process_description(message: Message, state: FSMContext, user: User, session):
    """Process consultation description"""
    try:
        description = message.text.strip()
        
        # Validate description
        try:
            description = validator.text_length(
                description,
                min_length=20,
                max_length=1000
            )
        except ValidationError:
            await message.answer(TEXTS[user.language]['invalid_description'])
            return
            
        # Get consultation data
        data = await state.get_data()
        
        # Create consultation
        consultation_service = ConsultationService(session)
        consultation = await consultation_service.create_consultation(
            user_id=user.id,
            consultation_type=data['consultation_type'],
            amount=data['amount'],
            phone_number=data['phone_number'],
            description=description
        )
        
        # Show payment methods
        await message.answer(
            TEXTS[user.language]['select_payment'].format(
                amount=data['amount']
            ),
            reply_markup=get_payment_methods_keyboard(
                language=user.language,
                consultation_id=consultation.id,
                amount=data['amount']
            )
        )
        
        # Update state
        await state.update_data(consultation_id=consultation.id)
        await state.set_state(ConsultationState.selecting_payment)
        
    except Exception as e:
        logger.error(f"Error processing description: {e}")
        await message.answer(TEXTS[user.language]['error'])
        await state.clear()

@router.callback_query(ConsultationState.selecting_payment)
async def process_payment_selection(callback: CallbackQuery, state: FSMContext, user: User, session):
    """Process payment method selection"""
    try:
        provider = callback.data.split(':')[1]
        if provider not in PaymentProvider.__members__:
            await callback.answer(TEXTS[user.language]['invalid_provider'])
            return
            
        # Get consultation data
        data = await state.get_data()
        
        # Create payment
        payment_service = PaymentService(session)
        payment, payment_url = await payment_service.create_payment(
            provider=PaymentProvider[provider],
            amount=data['amount'],
            consultation_id=data['consultation_id']
        )
        
        # Show payment link
        from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
        
        await callback.message.edit_text(
            TEXTS[user.language]['payment_link'].format(
                amount=data['amount'],
                provider=provider
            ),
            reply_markup=InlineKeyboardMarkup(inline_keyboard=[
                [InlineKeyboardButton(
                    text=TEXTS[user.language]['pay'],
                    url=payment_url
                )],
                [InlineKeyboardButton(
                    text=TEXTS[user.language]['cancel'],
                    callback_data='cancel_payment'
                )]
            ])
        )
        
        # Update state
        await state.update_data(payment_id=payment.id)
        await state.set_state(ConsultationState.awaiting_payment)
        
    except Exception as e:
        logger.error(f"Error processing payment selection: {e}")
        await callback.message.edit_text(TEXTS[user.language]['error'])
        await state.clear()

@router.callback_query(F.data == "cancel_payment", ConsultationState.awaiting_payment)
async def cancel_payment(callback: CallbackQuery, state: FSMContext, user: User, session):
    """Cancel payment"""
    try:
        data = await state.get_data()
        
        # Cancel consultation
        consultation_service = ConsultationService(session)
        await consultation_service.cancel_consultation(
            consultation_id=data['consultation_id']
        )
        
        await callback.message.edit_text(
            TEXTS[user.language]['payment_cancelled'],
            reply_markup=get_main_menu_keyboard(user.language)
        )
        
        await state.clear()
        
    except Exception as e:
        logger.error(f"Error cancelling payment: {e}")
        await callback.message.edit_text(TEXTS[user.language]['error'])
        await state.clear()

@router.callback_query(ConsultationState.selecting_time)
async def process_time_selection(callback: CallbackQuery, state: FSMContext, user: User, session):
    """Process consultation time selection"""
    try:
        selected_time = datetime.fromisoformat(callback.data.split(':')[1])
        
        # Get consultation data
        data = await state.get_data()
        
        # Schedule consultation
        consultation_service = ConsultationService(session)
        await consultation_service.schedule_consultation(
            consultation_id=data['consultation_id'],
            scheduled_time=selected_time
        )
        
        # Show confirmation
        await callback.message.edit_text(
            TEXTS[user.language]['consultation_scheduled'].format(
                time=selected_time.strftime("%d.%m.%Y %H:%M")
            ),
            reply_markup=get_main_menu_keyboard(user.language)
        )
        
        await state.clear()
        
    except Exception as e:
        logger.error(f"Error scheduling consultation: {e}")
        await callback.message.edit_text(TEXTS[user.language]['error'])
        await state.clear()

@router.message(Command("my_consultations"))
async def show_consultations(message: Message, user: User, session):
    """Show user's consultations"""
    try:
        consultation_service = ConsultationService(session)
        consultations = await consultation_service.get_user_consultations(user.id)
        
        if not consultations:
            await message.answer(
                TEXTS[user.language]['no_consultations'],
                reply_markup=get_main_menu_keyboard(user.language)
            )
            return
            
        # Format consultations list
        text = TEXTS[user.language]['your_consultations'] + "\n\n"
        
        for consultation in consultations:
            text += f"📅 {consultation.created_at.strftime('%d.%m.%Y')}\n"
            text += f"💰 {consultation.amount:,.0f} сум\n"
            text += f"📝 {consultation.description[:100]}...\n"
            text += f"✅ {TEXTS[user.language][f'status_{consultation.status.value.lower()}']} \n"
            
            if consultation.scheduled_time:
                text += f"🕒 {consultation.scheduled_time.strftime('%d.%m.%Y %H:%M')}\n"
                
            text += "\n"
            
            if len(text) > 4000:  # Telegram message limit
                await message.answer(text)
                text = ""
                
        if text:
            await message.answer(
                text,
                reply_markup=get_main_menu_keyboard(user.language)
            )
            
    except Exception as e:
        logger.error(f"Error showing consultations: {e}")
        await message.answer(TEXTS[user.language]['error'])

def register_handlers(dp):
    """Register consultation handlers"""
    dp.include_router(router)
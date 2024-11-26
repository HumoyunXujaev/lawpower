from aiogram import Router, F, Dispatcher
from aiogram.filters import Command
from aiogram.types import Message, CallbackQuery
from aiogram.fsm.context import FSMContext
import logging
from telegram_bot.core.database import Base, get_session
from sqlalchemy.ext.asyncio import AsyncSession

from decimal import Decimal
from aiogram.types import (
    InlineKeyboardMarkup,
    InlineKeyboardButton,
    ReplyKeyboardMarkup,
    KeyboardButton,
    ReplyKeyboardRemove
)
from telegram_bot.core.constants import TEXTS
from telegram_bot.models import User, Payment, ConsultationStatus, PaymentStatus
from telegram_bot.services.payments import PaymentService
from telegram_bot.services.consultations import ConsultationService
from telegram_bot.services.analytics import AnalyticsService
from telegram_bot.bot.keyboards import (
    get_start_keyboard,
    get_payment_methods_keyboard,
    get_consultation_actions_keyboard
)
from telegram_bot.bot.states import PaymentState
from telegram_bot.utils.validators import validator
from fastapi.responses import JSONResponse
from fastapi import Request,Depends
from datetime import datetime

logger = logging.getLogger(__name__)
router = Router(name='payments')

@router.callback_query(F.data.startswith("pay:"))
async def process_payment_selection(
    callback: CallbackQuery,
    state: FSMContext,
    user: User,
    session
):
    """Process payment method selection"""
    try:
        _, provider, consultation_id, amount = callback.data.split(":")
        consultation_id = int(consultation_id)
        amount = Decimal(amount)
        
        # Validate amount and consultation
        consultation_service = ConsultationService(session)
        consultation = await consultation_service.get_consultation(consultation_id)
        
        if not consultation:
            await callback.answer(TEXTS[user.language]['not_found'])
            return
            
        if consultation.user_id != user.id:
            await callback.answer(TEXTS[user.language]['not_your_consultation'])
            return
            
        if consultation.status != ConsultationStatus.PENDING:
            await callback.answer(TEXTS[user.language]['already_paid'])
            return
            
        # Create payment
        payment_service = PaymentService(session)
        payment_url = await payment_service.create_payment(
            provider=provider,
            amount=amount,
            consultation_id=consultation_id,
            user_id=user.id
        )
        
        # Save payment info to state
        await state.update_data(
            payment_provider=provider,
            consultation_id=consultation_id,
            amount=str(amount)
        )
        await state.set_state(PaymentState.awaiting_payment)
        
        # Send payment link
        await callback.message.edit_text(
            TEXTS[user.language]['payment_link'].format(
                amount=amount,
                provider=provider.upper()
            ),
            reply_markup=InlineKeyboardMarkup(inline_keyboard=[
                [
                    InlineKeyboardButton(
                        text=TEXTS[user.language]['pay'],
                        url=payment_url
                    )
                ],
                [
                    InlineKeyboardButton(
                        text=TEXTS[user.language]['cancel'],
                        callback_data="cancel_payment"
                    )
                ]
            ])
        )
        
        # Track payment initiated
        analytics = AnalyticsService(session)
        await analytics.track_event(
            user_id=user.id,
            event_type='payment_initiated',
            data={
                'consultation_id': consultation_id,
                'amount': float(amount),
                'provider': provider
            }
        )
        
    except Exception as e:
        logger.error(f"Error processing payment selection: {e}", exc_info=True)
        await callback.message.edit_text(TEXTS[user.language]['error'])

@router.callback_query(F.data == "cancel_payment")
async def cancel_payment(callback: CallbackQuery, state: FSMContext, user: User):
    """Cancel payment"""
    try:
        # Get payment data
        data = await state.get_data()
        consultation_id = data.get('consultation_id')
        
        if consultation_id:
            await callback.message.edit_text(
                TEXTS[user.language]['payment_cancelled'],
                reply_markup=get_consultation_actions_keyboard(
                    consultation_id,
                    user.language
                )
            )
        else:
            await callback.message.edit_text(
                TEXTS[user.language]['payment_cancelled'],
                reply_markup=get_start_keyboard(user.language)
            )
            
        # Clear state
        await state.clear()
        
    except Exception as e:
        logger.error(f"Error cancelling payment: {e}", exc_info=True)
        await callback.message.edit_text(TEXTS[user.language]['error'])

async def process_payment_callback(data: dict, session):
    """Process payment callback from payment system"""
    try:
        payment_service = PaymentService(session)
        consultation_service = ConsultationService(session)
        
        # Verify payment
        payment = await payment_service.verify_payment(data)
        if not payment:
            logger.error("Invalid payment callback")
            return False
            
        # Get consultation
        consultation = await consultation_service.get_consultation(
            payment.consultation_id
        )
        if not consultation:
            logger.error(f"Consultation not found: {payment.consultation_id}")
            return False
            
        # Update payment status
        payment.status = PaymentStatus.COMPLETED
        await session.commit()
        
        # Update consultation status
        consultation.status = ConsultationStatus.PAID
        await session.commit()
        
        # Send notification to user
        from telegram_bot.bot import bot
        try:
            await bot.send_message(
                consultation.user.telegram_id,
                TEXTS[consultation.user.language]['payment_success'],
                reply_markup=get_consultation_actions_keyboard(
                    consultation.id,
                    consultation.user.language
                )
            )
        except Exception as e:
            logger.error(f"Error notifying user: {e}")
            
        # Track payment
        analytics = AnalyticsService(session)
        await analytics.track_event(
            user_id=consultation.user_id,
            event_type='payment_completed',
            data={
                'consultation_id': consultation.id,
                'payment_id': payment.id,
                'amount': float(payment.amount)
            }
        )
        
        return True
        
    except Exception as e:
        logger.error(f"Error processing payment callback: {e}", exc_info=True)
        return False

@router.callback_query(F.data.startswith("refund:"))
async def process_refund_request(
    callback: CallbackQuery,
    user: User,
    session
):
    """Process refund request"""
    try:
        consultation_id = int(callback.data.split(":")[1])
        
        # Validate consultation
        consultation_service = ConsultationService(session)
        consultation = await consultation_service.get_consultation(consultation_id)
        
        if not consultation:
            await callback.answer(TEXTS[user.language]['not_found'])
            return
            
        if consultation.user_id != user.id:
            await callback.answer(TEXTS[user.language]['not_your_consultation'])
            return
            
        # Check if refund is possible
        if consultation.status not in [ConsultationStatus.PAID, ConsultationStatus.SCHEDULED]:
            await callback.answer(TEXTS[user.language]['refund_not_available'])
            return
            
        # Create refund
        payment_service = PaymentService(session)
        refund = await payment_service.create_refund(consultation_id)
        
        if refund:
            await callback.message.edit_text(
                TEXTS[user.language]['refund_initiated'],
                reply_markup=get_start_keyboard(user.language)
            )
            
            # Track refund request
            analytics = AnalyticsService(session)
            await analytics.track_event(
                user_id=user.id,
                event_type='refund_requested',
                data={'consultation_id': consultation_id}
            )
        else:
            await callback.message.edit_text(
                TEXTS[user.language]['refund_error'],
                reply_markup=get_start_keyboard(user.language)
            )
            
    except Exception as e:
        logger.error(f"Error processing refund: {e}", exc_info=True)
        await callback.message.edit_text(TEXTS[user.language]['error'])

async def process_refund_callback(data: dict, session):
    """Process refund callback from payment system"""
    try:
        payment_service = PaymentService(session)
        consultation_service = ConsultationService(session)
        
        # Verify refund
        refund = await payment_service.verify_refund(data)
        if not refund:
            logger.error("Invalid refund callback")
            return False
            
        # Get consultation
        consultation = await consultation_service.get_consultation(
            refund.consultation_id
        )
        if not consultation:
            logger.error(f"Consultation not found: {refund.consultation_id}")
            return False
            
        # Update consultation status
        consultation.status = ConsultationStatus.CANCELLED
        await session.commit()
        
        # Send notification to user
        from telegram_bot.bot import bot
        try:
            await bot.send_message(
                consultation.user.telegram_id,
                TEXTS[consultation.user.language]['refund_completed'],
                reply_markup=get_start_keyboard(consultation.user.language)
            )
        except Exception as e:
            logger.error(f"Error notifying user about refund: {e}")
            
        # Track refund
        analytics = AnalyticsService(session)
        await analytics.track_event(
            user_id=consultation.user_id,
            event_type='refund_completed',
            data={
                'consultation_id': consultation.id,
                'refund_id': refund.id,
                'amount': float(refund.amount)
            }
        )
        
        return True
        
    except Exception as e:
        logger.error(f"Error processing refund callback: {e}", exc_info=True)
        return False
    


@router.callback_query(F.data.startswith("pay:"))
async def handle_payment_selection(
    callback: CallbackQuery,
    user: User,
    state: FSMContext,
    session
):
    """Handle payment method selection"""
    try:
        provider, consultation_id = callback.data.split(":")[1:]
        consultation_id = int(consultation_id)
        
        # Get consultation
        consultation_service = ConsultationService(session)
        consultation = await consultation_service.get_consultation(consultation_id)
        
        if not consultation:
            await callback.answer(TEXTS[user.language]['consultation_not_found'])
            return
        
        if consultation.user_id != user.id:
            await callback.answer(TEXTS[user.language]['not_your_consultation'])
            return
            
        # Create payment
        payment_service = PaymentService(session)
        payment_url = await payment_service.create_payment(
            provider=provider,
            amount=consultation.amount,
            consultation_id=consultation_id
        )
        
        if not payment_url:
            await callback.message.edit_text(
                TEXTS[user.language]['payment_error']
            )
            return
            
        # Send payment link
        keyboard = [
            [InlineKeyboardButton(
                text=TEXTS[user.language]['pay'],
                url=payment_url
            )],
            [InlineKeyboardButton(
                text=TEXTS[user.language]['cancel'],
                callback_data=f"cancel_payment:{consultation_id}"
            )]
        ]
        
        await callback.message.edit_text(
            TEXTS[user.language]['payment_instruction'].format(
                amount=consultation.amount,
                provider=provider.upper()
            ),
            reply_markup=InlineKeyboardMarkup(inline_keyboard=keyboard)
        )
        
        # Track payment initiation
        analytics = AnalyticsService(session)
        await analytics.track_event(
            user_id=user.id,
            event_type='payment_initiated',
            data={
                'provider': provider,
                'amount': float(consultation.amount),
                'consultation_id': consultation_id
            }
        )
        
    except Exception as e:
        logger.error(f"Error handling payment selection: {e}")
        await callback.message.edit_text(TEXTS[user.language]['error'])

@router.callback_query(F.data.startswith("cancel_payment:"))
async def handle_payment_cancellation(
    callback: CallbackQuery,
    user: User,
    session
):
    """Handle payment cancellation"""
    try:
        consultation_id = int(callback.data.split(":")[1])
        
        # Get consultation
        consultation_service = ConsultationService(session)
        consultation = await consultation_service.get_consultation(consultation_id)
        
        if not consultation:
            await callback.answer(TEXTS[user.language]['consultation_not_found'])
            return
            
        if consultation.user_id != user.id:
            await callback.answer(TEXTS[user.language]['not_your_consultation'])
            return
            
        # Update consultation status
        consultation.status = ConsultationStatus.CANCELLED
        consultation.cancelled_at = datetime.utcnow()
        await session.commit()
        
        await callback.message.edit_text(
            TEXTS[user.language]['payment_cancelled'],
            reply_markup=get_start_keyboard(user.language)
        )
        
        # Track cancellation
        analytics = AnalyticsService(session)
        await analytics.track_event(
            user_id=user.id,
            event_type='payment_cancelled',
            data={'consultation_id': consultation_id}
        )
        
    except Exception as e:
        logger.error(f"Error handling payment cancellation: {e}")
        await callback.message.edit_text(TEXTS[user.language]['error'])

@router.post("/payment/webhook/{provider}")
async def payment_webhook(
    provider: str,
    request: Request,
    session: AsyncSession = Depends(get_session)
):
    """Handle payment webhook callbacks"""
    try:
        # Verify signature
        payment_service = PaymentService(session)
        signature_valid = await payment_service.verify_signature(
            provider,
            await request.json()
        )
        
        if not signature_valid:
            return JSONResponse(
                status_code=400,
                content={"error": "Invalid signature"}
            )
            
        # Process payment
        payment_data = await request.json()
        success = await payment_service.process_payment(
            provider,
            payment_data
        )
        
        if not success:
            return JSONResponse(
                status_code=400,
                content={"error": "Payment processing failed"}
            )
            
        return {"status": "success"}
        
    except Exception as e:
        logger.error(f"Error processing payment webhook: {e}")
        return JSONResponse(
            status_code=500,
            content={"error": "Internal server error"}
        )

def register_handlers(dp: Dispatcher):
    """Register payment handlers"""
    dp.include_router(router)

# Register callback handlers
router.callback_query.register(
    process_payment_selection,
    F.data.startswith("pay:")
)
router.callback_query.register(
    cancel_payment,
    F.data == "cancel_payment"
)
router.callback_query.register(
    process_refund_request,
    F.data.startswith("refund:")
)

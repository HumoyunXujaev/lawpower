# telegram_bot/services/consultations/service.py

from typing import List, Optional, Dict, Any, Tuple
from datetime import datetime, timedelta
from decimal import Decimal
from sqlalchemy import select, func, or_, and_
import logging

from telegram_bot.models import (
    Consultation, ConsultationStatus, User,
    Payment, PaymentStatus
)
from telegram_bot.services.base import BaseService
from telegram_bot.core.errors import ValidationError
from telegram_bot.core.cache import cache_service as cache
from telegram_bot.core.constants import TEXTS
from telegram_bot.utils.validators import validator

logger = logging.getLogger(__name__)

class ConsultationService(BaseService[Consultation]):
    """Enhanced consultation service"""
    
    WORK_HOURS = {
        'start': 9,  # 9 AM
        'end': 18    # 6 PM
    }
    WORKING_DAYS = [0, 1, 2, 3, 4, 5]  # Monday to Saturday
    SLOT_DURATION = 60  # minutes
    
    def __init__(self, session):
        super().__init__(Consultation, session)
        self.cache = cache
        
    async def create_consultation(
        self,
        user_id: int,
        consultation_type: str,
        amount: Decimal,
        phone_number: str,
        description: str,
        metadata: Dict = None
    ) -> Consultation:
        """Create new consultation request"""
        try:
            # Validate phone number
            phone_number = validator.phone_number(phone_number)
            
            # Validate amount
            if amount < Decimal('50000') or amount > Decimal('1000000'):
                raise ValidationError("Invalid consultation amount")
                
            # Create consultation
            consultation = await self.create(
                user_id=user_id,
                consultation_type=consultation_type,
                amount=amount,
                phone_number=phone_number,
                description=description,
                status=ConsultationStatus.PENDING,
                metadata=metadata or {
                    'created_at': datetime.utcnow().isoformat()
                }
            )
            
            # Notify admins
            await self._notify_admins_new_consultation(consultation)
            
            return consultation
            
        except ValidationError:
            raise
        except Exception as e:
            logger.error(f"Error creating consultation: {e}")
            raise ValidationError("Failed to create consultation")
            
    async def get_available_slots(
        self,
        date: datetime,
        consultation_type: str = None
    ) -> List[datetime]:
        """Get available consultation time slots"""
        if date.date() < datetime.now().date():
            return []
            
        if date.weekday() not in self.WORKING_DAYS:
            return []
            
        # Try cache
        cache_key = f"slots:{date.date()}:{consultation_type or 'all'}"
        cached = await self.cache.get(cache_key)
        if cached:
            return [datetime.fromisoformat(dt) for dt in cached]
            
        # Get booked slots
        booked_slots = await self.session.execute(
            select(Consultation.scheduled_time)
            .filter(
                func.date(Consultation.scheduled_time) == date.date(),
                Consultation.status.in_([
                    ConsultationStatus.SCHEDULED,
                    ConsultationStatus.CONFIRMED
                ])
            )
        )
        booked_times = {slot.scheduled_time for slot in booked_slots.scalars()}
        
        # Generate available slots
        available_slots = []
        current_time = datetime.combine(
            date.date(),
            datetime.min.time().replace(hour=self.WORK_HOURS['start'])
        )
        
        while current_time.hour < self.WORK_HOURS['end']:
            if (current_time > datetime.now() and
                current_time not in booked_times):
                available_slots.append(current_time)
            current_time += timedelta(minutes=self.SLOT_DURATION)
        
        # Cache results
        await self.cache.set(
            cache_key,
            [dt.isoformat() for dt in available_slots],
            timeout=300  # 5 minutes
        )
        
        return available_slots
        
    async def schedule_consultation(
        self,
        consultation_id: int,
        scheduled_time: datetime
    ) -> bool:
        """Schedule confirmed consultation"""
        consultation = await self.get(consultation_id)
        if not consultation:
            return False
            
        if consultation.status != ConsultationStatus.PAID:
            raise ValidationError("Consultation must be paid first")
            
        # Validate time
        if not self._is_valid_time(scheduled_time):
            raise ValidationError("Invalid consultation time")
            
        # Check availability
        if not await self._is_time_available(scheduled_time):
            raise ValidationError("Selected time is not available")
            
        # Update consultation
        consultation.scheduled_time = scheduled_time
        consultation.status = ConsultationStatus.SCHEDULED
        consultation.metadata['scheduled_at'] = datetime.utcnow().isoformat()
        
        await self.session.commit()
        
        # Clear cache
        await self.cache.delete_pattern('slots:*')
        
        # Send notifications
        await self._notify_about_scheduling(consultation)
        
        return True
        
    def _is_valid_time(self, dt: datetime) -> bool:
        """Check if time is valid for consultation"""
        return (
            dt.weekday() in self.WORKING_DAYS and
            self.WORK_HOURS['start'] <= dt.hour < self.WORK_HOURS['end']
        )
        
    async def _is_time_available(
        self,
        dt: datetime,
        exclude_id: Optional[int] = None
    ) -> bool:
        """Check if time slot is available"""
        query = select(Consultation).filter(
            Consultation.scheduled_time == dt,
            Consultation.status.in_([
                ConsultationStatus.SCHEDULED,
                ConsultationStatus.CONFIRMED
            ])
        )
        
        if exclude_id:
            query = query.filter(Consultation.id != exclude_id)
            
        result = await self.session.execute(query)
        return not bool(result.scalar_one_or_none())
        
    async def confirm_payment(
        self,
        consultation_id: int,
        payment_id: str,
        amount: Decimal
    ) -> bool:
        """Confirm consultation payment"""
        consultation = await self.get(consultation_id)
        if not consultation:
            return False
            
        if consultation.status != ConsultationStatus.PENDING:
            raise ValidationError("Invalid consultation status")
            
        if consultation.amount != amount:
            raise ValidationError("Payment amount mismatch")
            
        # Update status
        consultation.status = ConsultationStatus.PAID
        consultation.metadata['payment_id'] = payment_id
        consultation.metadata['paid_at'] = datetime.utcnow().isoformat()
        
        await self.session.commit()
        
        # Notify user
        await self._notify_user(
            consultation,
            'payment_confirmed'
        )
        
        return True
        
    async def cancel_consultation(
        self,
        consultation_id: int,
        reason: Optional[str] = None,
        cancelled_by_user: bool = True
    ) -> bool:
        """Cancel consultation"""
        consultation = await self.get(consultation_id)
        if not consultation:
            return False
            
        # Can only cancel pending or scheduled consultations
        if consultation.status not in [
            ConsultationStatus.PENDING,
            ConsultationStatus.SCHEDULED
        ]:
            raise ValidationError("Cannot cancel this consultation")
            
        # Update status
        consultation.status = ConsultationStatus.CANCELLED
        consultation.metadata['cancelled_at'] = datetime.utcnow().isoformat()
        consultation.metadata['cancelled_by_user'] = cancelled_by_user
        
        if reason:
            consultation.metadata['cancellation_reason'] = reason
            
        await self.session.commit()
        
        # Process refund if needed
        if consultation.status == ConsultationStatus.PAID:
            await self._process_refund(consultation)
            
        # Notify user
        await self._notify_user(
            consultation,
            'consultation_cancelled',
            reason=reason
        )
        
        return True
        
    async def complete_consultation(
        self,
        consultation_id: int,
        notes: Optional[str] = None,
        rating: Optional[int] = None,
        feedback: Optional[str] = None
    ) -> bool:
        """Complete consultation"""
        consultation = await self.get(consultation_id)
        if not consultation:
            return False
            
        if consultation.status != ConsultationStatus.SCHEDULED:
            raise ValidationError("Cannot complete this consultation")
            
        # Update consultation
        consultation.status = ConsultationStatus.COMPLETED
        consultation.metadata['completed_at'] = datetime.utcnow().isoformat()
        
        if notes:
            consultation.metadata['completion_notes'] = notes
            
        if rating:
            consultation.metadata['rating'] = rating
            consultation.metadata['feedback'] = feedback
            
        await self.session.commit()
        
        # Request feedback if not provided
        if not rating:
            await self._request_feedback(consultation)
            
        return True
        
    async def _notify_user(
        self,
        consultation: Consultation,
        message_type: str,
        **kwargs
    ) -> None:
        """Send notification to user"""
        try:
            from telegram_bot.bot import bot
            
            user = await self.session.get(User, consultation.user_id)
            if not user:
                return
                
            text = TEXTS[user.language][message_type]
            
            # Add consultation details
            text += f"\n\n📅 {consultation.created_at.strftime('%d.%m.%Y')}"
            text += f"\n💰 {consultation.amount:,.0f} сум"
            
            if consultation.scheduled_time:
                text += f"\n🕒 {consultation.scheduled_time.strftime('%d.%m.%Y %H:%M')}"
                
            if kwargs.get('reason'):
                text += f"\n\n{TEXTS[user.language]['cancellation_reason']}: {kwargs['reason']}"
                
            await bot.send_message(
                user.telegram_id,
                text
            )
            
        except Exception as e:
            logger.error(f"Error notifying user: {e}")
            
    async def _notify_admins_new_consultation(
        self,
        consultation: Consultation
    ) -> None:
        """Notify admins about new consultation"""
        try:
            from telegram_bot.bot import bot
            from telegram_bot.core.config import settings
            
            user = await self.session.get(User, consultation.user_id)
            if not user:
                return
                
            text = (
                "🆕 New consultation request\n\n"
                f"👤 {user.full_name}"
                f"{f' (@{user.username})' if user.username else ''}\n"
                f"📞 {consultation.phone_number}\n"
                f"💰 {consultation.amount:,.0f} sum\n\n"
                f"📝 {consultation.description}"
            )
            
            for admin_id in settings.ADMIN_IDS:
                try:
                    await bot.send_message(admin_id, text)
                except Exception as e:
                    logger.error(f"Error notifying admin {admin_id}: {e}")
                    
        except Exception as e:
            logger.error(f"Error notifying admins: {e}")
            
    async def _notify_about_scheduling(
        self,
        consultation: Consultation
    ) -> None:
        """Send scheduling notifications"""
        try:
            from telegram_bot.bot import bot
            
            user = await self.session.get(User, consultation.user_id)
            if not user:
                return
                
            # Notify user
            text = TEXTS[user.language]['consultation_scheduled'].format(
                time=consultation.scheduled_time.strftime("%d.%m.%Y %H:%M")
            )
            
            await bot.send_message(
                user.telegram_id,
                text
            )
            
            # Schedule reminders
            reminders = [
                (timedelta(days=1), 'consultation_reminder_24h'),
                (timedelta(hours=2), 'consultation_reminder_2h'),
                (timedelta(minutes=30), 'consultation_reminder_30m')
            ]
            
            for delta, reminder_type in reminders:
                reminder_time = consultation.scheduled_time - delta
                if reminder_time > datetime.utcnow():
                    await self.cache.set(
                        f"reminder:{consultation.id}:{reminder_type}",
                        {
                            'consultation_id': consultation.id,
                            'type': reminder_type,
                            'scheduled_for': reminder_time.isoformat()
                        },
                        timeout=int(delta.total_seconds())
                    )
                    
        except Exception as e:
            logger.error(f"Error sending scheduling notifications: {e}")
            
    async def _process_refund(self, consultation: Consultation) -> bool:
        """Process consultation refund"""
        try:
            if not consultation.metadata.get('payment_id'):
                return False
                
            from telegram_bot.services.payments import payment_service
            
            success = await payment_service.process_refund(
                payment_id=consultation.metadata['payment_id'],
                amount=consultation.amount
            )
            
            if success:
                consultation.metadata['refunded'] = True
                consultation.metadata['refund_time'] = datetime.utcnow().isoformat()
                await self.session.commit()
                
                # Notify user
                await self._notify_user(
                    consultation,
                    'payment_refunded'
                )
                
            return success
            
        except Exception as e:
            logger.error(f"Error processing refund: {e}")
            return False

consultation_service = ConsultationService(None)  # Session will be injected

__all__ = ['ConsultationService', 'consultation_service']
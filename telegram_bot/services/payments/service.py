# File: telegram_bot/services/payments/service.py

from decimal import Decimal
from typing import Optional, Dict, Any, Tuple
import logging
from datetime import datetime
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from telegram_bot.models import Payment, PaymentStatus, PaymentProvider
from telegram_bot.core.errors import PaymentError
from telegram_bot.services.base import BaseService
from telegram_bot.core.cache import cache_service
from .providers import get_payment_provider

logger = logging.getLogger(__name__)

class PaymentService(BaseService[Payment]):
    """Unified payment processing service"""
    
    def __init__(self, session: AsyncSession):
        super().__init__(Payment, session)
        
        # Payment limits
        self.MIN_AMOUNT = Decimal('1000.00')
        self.MAX_AMOUNT = Decimal('10000000.00')
        
    async def create_payment(
        self,
        amount: Decimal,
        consultation_id: int,
        provider: str,
        user_id: int,
        return_url: Optional[str] = None,
        metadata: Dict = None
    ) -> Tuple[Payment, str]:
        """Create new payment and get payment URL"""
        # Validate amount
        if amount < self.MIN_AMOUNT or amount > self.MAX_AMOUNT:
            raise PaymentError(
                f"Amount must be between {self.MIN_AMOUNT} and {self.MAX_AMOUNT}"
            )
            
        try:
            # Get payment provider
            payment_provider = get_payment_provider(provider)
            
            # Create payment record
            payment = await self.create(
                amount=amount,
                consultation_id=consultation_id,
                provider=PaymentProvider[provider.upper()],
                status=PaymentStatus.PENDING,
                user_id=user_id,
                metadata=metadata or {
                    'created_at': datetime.utcnow().isoformat(),
                    'return_url': return_url
                }
            )
            
            # Get payment URL from provider
            payment_url = await payment_provider.create_payment(
                amount=amount,
                order_id=f"order_{payment.id}",
                return_url=return_url
            )
            
            if not payment_url:
                raise PaymentError("Failed to get payment URL")
                
            # Update payment record
            payment.metadata['payment_url'] = payment_url
            await self.session.commit()
            
            # Cache payment data
            await cache_service.set(
                f"payment:{payment.id}",
                payment.to_dict(),
                timeout=900  # 15 minutes
            )
            
            return payment, payment_url
            
        except Exception as e:
            logger.error(f"Error creating payment: {e}")
            raise PaymentError(f"Payment creation failed: {str(e)}")

    async def process_callback(
        self,
        provider: str,
        data: Dict
    ) -> bool:
        """Process payment callback"""
        try:
            # Get payment provider
            payment_provider = get_payment_provider(provider)
            
            # Verify and parse callback
            payment_data = await payment_provider.process_callback(data)
            if not payment_data:
                logger.error("Failed to parse callback data")
                return False
                
            # Get payment
            payment = await self._get_payment_by_order(payment_data['order_id'])
            if not payment:
                logger.error("Payment not found")
                return False
                
            # Update payment status
            old_status = payment.status
            payment.status = PaymentStatus[payment_data['status']]
            payment.transaction_id = payment_data.get('transaction_id')
            payment.metadata.update({
                'callback_data': data,
                'processed_at': datetime.utcnow().isoformat()
            })
            
            await self.session.commit()
            
            # Clear cache
            await cache_service.delete(f"payment:{payment.id}")
            
            # Handle status change
            if old_status != payment.status:
                await self._handle_payment_status_change(payment)
                
            return True
            
        except Exception as e:
            logger.error(f"Error processing payment callback: {e}")
            return False

    async def process_refund(
        self,
        payment_id: int,
        amount: Optional[Decimal] = None,
        reason: Optional[str] = None
    ) -> bool:
        """Process payment refund"""
        try:
            # Get payment
            payment = await self.get(payment_id)
            if not payment:
                raise PaymentError("Payment not found")
                
            if payment.status != PaymentStatus.COMPLETED:
                raise PaymentError("Only completed payments can be refunded")
                
            # Get payment provider
            payment_provider = get_payment_provider(
                payment.provider.value.lower()
            )
            
            # Process refund
            refund_success = await payment_provider.process_refund(
                payment.transaction_id,
                amount
            )
            
            if refund_success:
                # Update payment status
                payment.status = PaymentStatus.REFUNDED
                payment.metadata['refund'] = {
                    'amount': str(amount) if amount else None,
                    'reason': reason,
                    'refunded_at': datetime.utcnow().isoformat()
                }
                await self.session.commit()
                
                # Clear cache
                await cache_service.delete(f"payment:{payment.id}")
                
                # Notify user
                await self._notify_user_about_refund(payment)
                
            return refund_success
            
        except Exception as e:
            logger.error(f"Error processing refund: {e}")
            return False

    async def verify_payment(self, payment_id: int) -> bool:
        """Verify payment status with provider"""
        try:
            payment = await self.get(payment_id)
            if not payment:
                return False
                
            payment_provider = get_payment_provider(
                payment.provider.value.lower()
            )
            
            return await payment_provider.verify_payment(
                payment.transaction_id
            )
            
        except Exception as e:
            logger.error(f"Error verifying payment: {e}")
            return False

    async def _get_payment_by_order(self, order_id: str) -> Optional[Payment]:
        """Get payment by order ID"""
        if not order_id.startswith('order_'):
            return None
            
        try:
            payment_id = int(order_id.split('_')[1])
            return await self.get(payment_id)
        except (ValueError, IndexError):
            return None

    async def _handle_payment_status_change(self, payment: Payment) -> None:
        """Handle payment status change"""
        try:
            if payment.status == PaymentStatus.COMPLETED:
                # Update consultation status
                from telegram_bot.models import Consultation
                consultation = await self.session.get(
                    Consultation,
                    payment.consultation_id
                )
                if consultation:
                    consultation.status = 'PAID'
                    consultation.metadata['payment_completed_at'] = \
                        datetime.utcnow().isoformat()
                    await self.session.commit()
                    
                # Notify user
                await self._notify_user_about_payment(payment)
                
            # Track payment event
            await self._track_payment_event(payment)
            
        except Exception as e:
            logger.error(f"Error handling payment status change: {e}")

    async def _notify_user_about_payment(self, payment: Payment) -> None:
        """Notify user about payment status"""
        try:
            from telegram_bot.bot import bot
            from telegram_bot.core.constants import TEXTS
            
            user = await self.session.get('User', payment.user_id)
            if user:
                await bot.send_message(
                    user.telegram_id,
                    TEXTS[user.language]['payment_success']
                )
                
        except Exception as e:
            logger.error(f"Error notifying user about payment: {e}")

    async def _notify_user_about_refund(self, payment: Payment) -> None:
        """Notify user about refund"""
        try:
            from telegram_bot.bot import bot
            from telegram_bot.core.constants import TEXTS
            
            user = await self.session.get('User', payment.user_id)
            if user:
                await bot.send_message(
                    user.telegram_id,
                    TEXTS[user.language]['payment_refunded']
                )
                
        except Exception as e:
            logger.error(f"Error notifying user about refund: {e}")

    async def _track_payment_event(self, payment: Payment) -> None:
        """Track payment analytics"""
        try:
            event_data = {
                'payment_id': payment.id,
                'status': payment.status.value,
                'amount': float(payment.amount),
                'provider': payment.provider.value
            }
            
            # Update cache stats
            await cache_service.increment(
                f"stats:payments:{payment.status.value}"
            )
            await cache_service.increment(
                f"stats:payments:{payment.provider.value}",
                float(payment.amount)
            )
            
            # Track user stats
            user_key = f"user:payments:{payment.user_id}"
            user_stats = await cache_service.get(user_key) or {
                'total': 0,
                'amount': 0
            }
            user_stats['total'] += 1
            user_stats['amount'] += float(payment.amount)
            await cache_service.set(user_key, user_stats)
            
        except Exception as e:
            logger.error(f"Error tracking payment event: {e}")
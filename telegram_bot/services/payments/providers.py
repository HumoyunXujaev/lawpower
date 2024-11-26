from typing import Optional, Dict, Any, Tuple
from decimal import Decimal
import logging
from datetime import datetime
import hmac
import hashlib
import aiohttp
import base64
from sqlalchemy import select

from telegram_bot.models import Payment, PaymentStatus, PaymentProvider
from telegram_bot.core.errors import PaymentError
from telegram_bot.core.config import settings
from telegram_bot.core.cache import cache_service
from telegram_bot.services.base import BaseService

logger = logging.getLogger(__name__)

class PaymentProviderBase:
    """Base payment provider implementation"""
    def __init__(self, config: Dict[str, Any]):
        self.config = config
    
    def _generate_signature(self, data: str, key: Optional[str] = None) -> str:
        key = key or self.config.get('secret_key', '')
        return hmac.new(
            key.encode(),
            data.encode(),
            hashlib.sha256
        ).hexdigest()

class ClickProvider(PaymentProviderBase):
    """Click payment provider"""
    async def create_payment_url(
        self,
        amount: Decimal,
        order_id: str,
        return_url: Optional[str] = None
    ) -> Optional[str]:
        try:
            timestamp = int(datetime.utcnow().timestamp())
            sign_string = f"{self.config['merchant_id']}{amount}{order_id}{timestamp}"
            signature = self._generate_signature(sign_string)
            
            params = {
                'merchant_id': self.config['merchant_id'],
                'amount': str(amount),
                'transaction_param': order_id,
                'return_url': return_url or self.config.get('return_url'),
                'sign_time': timestamp,
                'sign_string': signature
            }
            
            query = '&'.join(f"{k}={v}" for k, v in params.items())
            return f"https://my.click.uz/services/pay?{query}"
        except Exception as e:
            logger.error(f"Error creating Click payment: {e}")
            return None

    async def verify_callback(self, data: Dict) -> bool:
        try:
            sign_string = (
                f"{data['click_trans_id']}"
                f"{self.config['secret_key']}"
                f"{data['merchant_trans_id']}"
                f"{data['amount']}"
                f"{data['sign_time']}"
            )
            signature = self._generate_signature(sign_string)
            return signature == data['sign_string']
        except Exception as e:
            logger.error(f"Error verifying Click signature: {e}")
            return False

class PaymeProvider(PaymentProviderBase):
    """Payme payment provider"""
    def _get_auth_token(self) -> str:
        return base64.b64encode(
            f"{self.config['merchant_id']}:{self.config['secret_key']}".encode()
        ).decode()

    async def create_payment_url(
        self,
        amount: Decimal,
        order_id: str,
        return_url: Optional[str] = None
    ) -> Optional[str]:
        try:
            amount_tiyins = int(amount * 100)
            
            data = {
                'method': 'cards.create',
                'params': {
                    'amount': amount_tiyins,
                    'account': {'order_id': order_id},
                    'return_url': return_url or self.config.get('return_url')
                }
            }
            
            headers = {
                'X-Auth': self._get_auth_token(),
                'Content-Type': 'application/json'
            }
            
            async with aiohttp.ClientSession() as session:
                async with session.post(
                    'https://checkout.payme.uz/api',
                    json=data,
                    headers=headers
                ) as response:
                    result = await response.json()
                    
                    if 'error' in result:
                        raise PaymentError(
                            f"Payme error: {result['error']['message']}"
                        )
                    
                    return f"https://checkout.payme.uz/pay/{result['result']['card_token']}"
        except Exception as e:
            logger.error(f"Error creating Payme payment: {e}")
            return None

class UzumProvider(PaymentProviderBase):
    """Uzum payment provider"""
    async def create_payment_url(
        self,
        amount: Decimal,
        order_id: str,
        return_url: Optional[str] = None
    ) -> Optional[str]:
        try:
            data = {
                'merchantId': self.config['merchant_id'],
                'amount': str(amount),
                'orderId': order_id,
                'currency': 'UZS',
                'returnUrl': return_url or self.config.get('return_url'),
                'timestamp': datetime.utcnow().isoformat()
            }
            
            data['signature'] = self._generate_signature(
                ';'.join(f"{k}={v}" for k, v in sorted(data.items()))
            )
            
            async with aiohttp.ClientSession() as session:
                async with session.post(
                    'https://api.uzum.uz/payment/create',
                    json=data
                ) as response:
                    result = await response.json()
                    
                    if not result.get('success'):
                        raise PaymentError(
                            f"Uzum error: {result.get('message')}"
                        )
                    
                    return result['data']['paymentUrl']
        except Exception as e:
            logger.error(f"Error creating Uzum payment: {e}")
            return None

class UnifiedPaymentService(BaseService[Payment]):
    """Unified payment service"""
    
    def __init__(self, session):
        super().__init__(Payment, session)
        self.cache = cache_service
        self.providers = {
            'click': ClickProvider(settings.CLICK_CONFIG),
            'payme': PaymeProvider(settings.PAYME_CONFIG),
            'uzum': UzumProvider(settings.UZUM_CONFIG)
        }
        
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
        if amount < self.MIN_AMOUNT or amount > self.MAX_AMOUNT:
            raise PaymentError(
                f"Amount must be between {self.MIN_AMOUNT} and {self.MAX_AMOUNT}"
            )
            
        try:
            provider_instance = self.providers.get(provider)
            if not provider_instance:
                raise PaymentError(f"Unknown payment provider: {provider}")
            
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
            
            payment_url = await provider_instance.create_payment_url(
                amount=amount,
                order_id=f"order_{payment.id}",
                return_url=return_url
            )
            
            if not payment_url:
                raise PaymentError("Failed to get payment URL")
            
            payment.metadata['payment_url'] = payment_url
            await self.session.commit()
            
            await self.cache.set(
                f"payment:{payment.id}",
                payment.to_dict(),
                timeout=900
            )
            
            return payment, payment_url
            
        except Exception as e:
            logger.error(f"Error creating payment: {e}")
            raise PaymentError(str(e))

    async def process_callback(
        self,
        provider: str,
        data: Dict
    ) -> bool:
        """Process payment callback"""
        try:
            provider_instance = self.providers.get(provider)
            if not provider_instance:
                raise PaymentError(f"Unknown provider: {provider}")
                
            if not await provider_instance.verify_callback(data):
                raise PaymentError("Invalid callback signature")
                
            # Process payment data
            payment_id = int(data.get('order_id', '').split('_')[1])
            payment = await self.get(payment_id)
            
            if not payment:
                raise PaymentError("Payment not found")
                
            # Update payment status
            old_status = payment.status
            payment.status = PaymentStatus.COMPLETED
            payment.metadata.update({
                'callback_data': data,
                'processed_at': datetime.utcnow().isoformat()
            })
            
            await self.session.commit()
            await self.cache.delete(f"payment:{payment.id}")
            
            # Handle status change
            if old_status != payment.status:
                await self._handle_payment_status_change(payment)
                
            return True
            
        except Exception as e:
            logger.error(f"Error processing callback: {e}")
            return False

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
                await self._notify_user(
                    payment.user_id,
                    'payment_success'
                )
        except Exception as e:
            logger.error(f"Error handling status change: {e}")

    async def _notify_user(
        self,
        user_id: int,
        message_type: str,
        **kwargs
    ) -> None:
        """Send notification to user"""
        try:
            from telegram_bot.bot import bot
            from telegram_bot.models import User
            
            user = await self.session.get(User, user_id)
            if user:
                await bot.send_message(
                    user.telegram_id,
                    self._get_message_text(user.language, message_type, **kwargs)
                )
        except Exception as e:
            logger.error(f"Error notifying user: {e}")

# Create service instance
payment_service = UnifiedPaymentService(None)  # Session will be injected
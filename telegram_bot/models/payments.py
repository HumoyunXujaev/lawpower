from sqlalchemy import Column, Integer, String, Enum as SQLEnum, Numeric, JSON, ForeignKey, Index
from sqlalchemy.orm import relationship
from enum import Enum as PyEnum
from datetime import datetime

from telegram_bot.models.base import TimeStampedBase, MetadataMixin

class PaymentProvider(str, PyEnum):
    CLICK = 'click'
    PAYME = 'payme'
    UZUM = 'uzum'

class PaymentStatus(str, PyEnum):
    PENDING = 'pending'
    PROCESSING = 'processing'
    COMPLETED = 'completed'
    FAILED = 'failed'
    CANCELLED = 'cancelled'
    REFUNDED = 'refunded'

class PaymentType(str, PyEnum):
    CONSULTATION = 'consultation'
    SUBSCRIPTION = 'subscription'
    OTHER = 'other'

class Payment(TimeStampedBase, MetadataMixin):
    """Enhanced payment model with complete transaction tracking"""
    __tablename__ = 'payments'
    
    # Core fields
    user_id = Column(Integer, ForeignKey('users.id', ondelete='CASCADE'), nullable=False)
    consultation_id = Column(Integer, ForeignKey('consultations.id', ondelete='CASCADE'), nullable=True)
    
    # Payment details
    amount = Column(Numeric(10, 2), nullable=False)
    currency = Column(String, default='UZS', nullable=False)
    provider = Column(SQLEnum(PaymentProvider), nullable=False)
    type = Column(SQLEnum(PaymentType), default=PaymentType.CONSULTATION)
    status = Column(SQLEnum(PaymentStatus), default=PaymentStatus.PENDING)
    
    # Provider details
    provider_transaction_id = Column(String)
    provider_payment_url = Column(String)
    provider_response = Column(JSON, default={})
    
    # Refund details
    refund_amount = Column(Numeric(10, 2))
    refund_reason = Column(String)
    refund_transaction_id = Column(String)
    
    # Relationships
    user = relationship("User", back_populates="payments")
    consultation = relationship("Consultation", back_populates="payments")
    
    # Indexes
    __table_args__ = (
        Index('idx_payment_user', 'user_id'),
        Index('idx_payment_consultation', 'consultation_id'),
        Index('idx_payment_status', 'status'),
        Index('idx_payment_provider', 'provider'),
        Index('idx_payment_transaction', 'provider_transaction_id'),
    )
    
    @property
    def is_refundable(self) -> bool:
        """Check if payment can be refunded"""
        return (
            self.status == PaymentStatus.COMPLETED and
            not self.refund_amount and
            not self.metadata.get('no_refund', False)
        )
        
    def complete(self, transaction_id: str) -> None:
        """Complete payment"""
        self.status = PaymentStatus.COMPLETED
        self.provider_transaction_id = transaction_id
        self.metadata['completed_at'] = datetime.utcnow().isoformat()
        
    def fail(self, error: str = None) -> None:
        """Mark payment as failed"""
        self.status = PaymentStatus.FAILED
        if error:
            self.metadata['error'] = error
        self.metadata['failed_at'] = datetime.utcnow().isoformat()
        
    def cancel(self, reason: str = None) -> None:
        """Cancel payment"""
        self.status = PaymentStatus.CANCELLED
        if reason:
            self.metadata['cancellation_reason'] = reason
        self.metadata['cancelled_at'] = datetime.utcnow().isoformat()
        
    def refund(
        self,
        amount: Numeric,
        reason: str = None,
        transaction_id: str = None
    ) -> None:
        """Refund payment"""
        if not self.is_refundable:
            raise ValueError("Payment cannot be refunded")
            
        self.status = PaymentStatus.REFUNDED
        self.refund_amount = amount
        self.refund_reason = reason
        self.refund_transaction_id = transaction_id
        self.metadata['refunded_at'] = datetime.utcnow().isoformat()
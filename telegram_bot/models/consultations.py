from sqlalchemy import (
    Column, String, Integer, Boolean, ForeignKey, Text, 
    Numeric, DateTime, Enum as SQLEnum, Index, UniqueConstraint,
    CheckConstraint
)
from sqlalchemy.orm import relationship
from sqlalchemy.dialects.postgresql import JSONB
from enum import Enum
from datetime import datetime, timedelta

from telegram_bot.models.base import BaseModel, SoftDeleteMixin, AuditMixin, MetadataMixin

class ConsultationType(str, Enum):
    ONLINE = 'online'
    OFFICE = 'office'

class ConsultationStatus(str, Enum):
    PENDING = 'pending'
    CONFIRMED = 'confirmed'
    PAID = 'paid'
    SCHEDULED = 'scheduled'
    IN_PROGRESS = 'in_progress'
    COMPLETED = 'completed'
    CANCELLED = 'cancelled'
    REFUNDED = 'refunded'

class PaymentStatus(str, Enum):
    PENDING = 'pending'
    PROCESSING = 'processing'
    COMPLETED = 'completed'
    FAILED = 'failed'
    CANCELLED = 'cancelled'
    REFUNDED = 'refunded'

class PaymentProvider(str, Enum):
    CLICK = 'click'
    PAYME = 'payme'
    UZUM = 'uzum'

class Consultation(BaseModel, SoftDeleteMixin, AuditMixin, MetadataMixin):
    """Enhanced consultation model with complete tracking"""
    __tablename__ = 'consultations'

    # Core fields
    user_id = Column(Integer, ForeignKey('users.id', ondelete='CASCADE'), nullable=False)
    type = Column(SQLEnum(ConsultationType), nullable=False)
    status = Column(SQLEnum(ConsultationStatus), default=ConsultationStatus.PENDING)
    category = Column(String)
    language = Column(String(2), nullable=False)

    # Scheduling
    scheduled_time = Column(DateTime(timezone=True))
    duration = Column(Integer, default=60)  # minutes
    timezone = Column(String, default='Asia/Tashkent')
    reschedule_count = Column(Integer, default=0)
    rescheduled_from = Column(DateTime(timezone=True))
    cancellation_deadline = Column(DateTime(timezone=True))

    # Payment
    amount = Column(Numeric(10, 2), nullable=False)
    currency = Column(String, default='UZS', nullable=False)
    is_paid = Column(Boolean, default=False)
    paid_at = Column(DateTime(timezone=True))
    refunded_at = Column(DateTime(timezone=True))
    refund_amount = Column(Numeric(10, 2))
    refund_reason = Column(String)

    # Contact info
    phone_number = Column(String, nullable=False)
    email = Column(String)
    problem_description = Column(Text, nullable=False)
    additional_notes = Column(Text)

    # Meeting details
    meeting_url = Column(String)
    meeting_id = Column(String)
    meeting_password = Column(String)
    office_location = Column(String)
    office_room = Column(String)

    # Consultation details
    lawyer_id = Column(Integer, ForeignKey('users.id', ondelete='SET NULL'))
    lawyer_notes = Column(Text)
    summary = Column(Text)
    recording_url = Column(String)
    documents = Column(JSONB, default=[])

    # Rating and feedback
    rating = Column(Integer)
    client_feedback = Column(Text)
    lawyer_feedback = Column(Text)
    has_feedback = Column(Boolean, default=False)

    # Tracking
    completed_at = Column(DateTime(timezone=True))
    cancelled_at = Column(DateTime(timezone=True))
    cancellation_reason = Column(String)
    last_reminder_sent = Column(DateTime(timezone=True))
    reminder_count = Column(Integer, default=0)

    # Relationships
    user = relationship('User', foreign_keys=[user_id], back_populates='consultations')
    lawyer = relationship('User', foreign_keys=[lawyer_id])
    payments = relationship('Payment', back_populates='consultation', cascade='all, delete-orphan')
    feedback = relationship('ConsultationFeedback', back_populates='consultation', cascade='all, delete-orphan')

    # Constraints and Indexes
    __table_args__ = (
        CheckConstraint('amount >= 0', name='positive_amount'),
        CheckConstraint(
            "status != 'completed' OR (rating IS NOT NULL AND completed_at IS NOT NULL)",
            name='completed_consultation_check'
        ),
        Index('ix_consultations_user_id', user_id),
        Index('ix_consultations_lawyer_id', lawyer_id),
        Index('ix_consultations_status', status),
        Index('ix_consultations_type', type),
        Index('ix_consultations_scheduled_time', scheduled_time),
        Index('ix_consultations_completed_at', completed_at),
    )

    @property
    def can_reschedule(self) -> bool:
        """Check if consultation can be rescheduled"""
        if not self.scheduled_time:
            return False
        return (
            self.status in [ConsultationStatus.SCHEDULED, ConsultationStatus.CONFIRMED] and
            self.reschedule_count < 3 and
            datetime.utcnow() + timedelta(hours=24) < self.scheduled_time
        )

    @property
    def can_cancel(self) -> bool:
        """Check if consultation can be cancelled"""
        if not self.scheduled_time:
            return True
        return (
            self.status not in [ConsultationStatus.COMPLETED, ConsultationStatus.CANCELLED] and
            (not self.cancellation_deadline or datetime.utcnow() < self.cancellation_deadline)
        )

    def mark_paid(self, payment_id: str = None) -> None:
        """Mark consultation as paid"""
        self.is_paid = True
        self.paid_at = datetime.utcnow()
        self.status = ConsultationStatus.PAID
        if payment_id:
            self.metadata['payment_id'] = payment_id

    def schedule(self, scheduled_time: datetime) -> None:
        """Schedule consultation"""
        if self.scheduled_time:
            self.reschedule_count += 1
            self.rescheduled_from = self.scheduled_time
        self.scheduled_time = scheduled_time
        self.status = ConsultationStatus.SCHEDULED
        self.cancellation_deadline = scheduled_time - timedelta(hours=24)

class ConsultationFeedback(BaseModel):
    """Consultation feedback model"""
    __tablename__ = 'consultation_feedback'

    consultation_id = Column(Integer, ForeignKey('consultations.id', ondelete='CASCADE'), nullable=False)
    user_id = Column(Integer, ForeignKey('users.id', ondelete='CASCADE'), nullable=False)
    rating = Column(Integer, nullable=False)
    feedback_text = Column(Text)
    feedback_type = Column(String, default='client')  # client/lawyer
    is_public = Column(Boolean, default=True)
    metadata = Column(JSONB, default={})

    # Specific feedback fields
    professionalism_rating = Column(Integer)
    communication_rating = Column(Integer)
    knowledge_rating = Column(Integer)
    punctuality_rating = Column(Integer)
    value_rating = Column(Integer)

    # Relationships
    consultation = relationship('Consultation', back_populates='feedback')
    user = relationship('User', back_populates='feedback')

    # Indexes
    __table_args__ = (
        CheckConstraint('rating >= 1 AND rating <= 5', name='valid_rating'),
        Index('ix_consultation_feedback_consultation_id', consultation_id),
        Index('ix_consultation_feedback_user_id', user_id),
        UniqueConstraint('consultation_id', 'user_id', 'feedback_type', name='uq_consultation_feedback'),
    )

class Payment(BaseModel, AuditMixin):
    """Enhanced payment model with full transaction tracking"""
    __tablename__ = 'payments'

    # Core fields
    consultation_id = Column(Integer, ForeignKey('consultations.id', ondelete='CASCADE'), nullable=False)
    user_id = Column(Integer, ForeignKey('users.id', ondelete='CASCADE'), nullable=False)
    amount = Column(Numeric(10, 2), nullable=False)
    currency = Column(String, default='UZS', nullable=False)
    provider = Column(SQLEnum(PaymentProvider), nullable=False)
    status = Column(SQLEnum(PaymentStatus), default=PaymentStatus.PENDING)

    # Transaction details
    transaction_id = Column(String)
    provider_transaction_id = Column(String)
    provider_payment_url = Column(String)
    provider_response = Column(JSONB, default={})
    payment_method = Column(String)

    # Refund details
    refund_amount = Column(Numeric(10, 2))
    refund_reason = Column(String)
    refund_transaction_id = Column(String)
    refunded_at = Column(DateTime(timezone=True))

    # Additional info
    error_message = Column(String)
    metadata = Column(JSONB, default={})

    # Relationships
    consultation = relationship('Consultation', back_populates='payments')
    user = relationship('User', back_populates='payments')

    # Indexes and Constraints
    __table_args__ = (
        CheckConstraint('amount > 0', name='positive_payment_amount'),
        Index('ix_payments_consultation_id', consultation_id),
        Index('ix_payments_user_id', user_id),
        Index('ix_payments_status', status),
        Index('ix_payments_transaction_id', transaction_id),
        Index('ix_payments_provider_transaction_id', provider_transaction_id),
        UniqueConstraint('provider_transaction_id', 'provider', name='uq_provider_transaction'),
    )

    @property
    def is_refundable(self) -> bool:
        """Check if payment can be refunded"""
        return (
            self.status == PaymentStatus.COMPLETED and
            not self.refund_amount and
            (datetime.utcnow() - self.created_at).days <= 30
        )

    def process_refund(
        self,
        amount: Numeric,
        reason: str,
        transaction_id: str = None
    ) -> None:
        """Process payment refund"""
        if not self.is_refundable:
            raise ValueError("Payment cannot be refunded")
            
        self.status = PaymentStatus.REFUNDED
        self.refund_amount = amount
        self.refund_reason = reason
        self.refund_transaction_id = transaction_id
        self.refunded_at = datetime.utcnow()
        self.metadata['refund'] = {
            'amount': str(amount),
            'reason': reason,
            'transaction_id': transaction_id,
            'processed_at': datetime.utcnow().isoformat()
        }

# Export models
__all__ = [
    'Consultation',
    'ConsultationFeedback',
    'Payment',
    'ConsultationType',
    'ConsultationStatus',
    'PaymentStatus',
    'PaymentProvider'
]
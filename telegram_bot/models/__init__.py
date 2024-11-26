from telegram_bot.models.base import Base, BaseModel, TimestampMixin
from telegram_bot.models.users import (
    User,
    UserEvent,
    UserNotification,
    UserRole,
    UserStatus
)
from telegram_bot.models.questions import (
    Question,
    Answer, 
    QuestionFeedback,
    AnswerFeedback,
    QuestionCategory,
    QuestionStatus
)
from telegram_bot.models.consultations import (
    Consultation,
    ConsultationFeedback,
    Payment,
    ConsultationType,
    ConsultationStatus,
    PaymentStatus,
    PaymentProvider
)
from telegram_bot.models.faq import (
    FAQ,
    FAQFeedback, 
    FAQCategory
)
from sqlalchemy.orm import relationship
# Configure relationships
Question.user = relationship('User', back_populates='questions')
Answer.question = relationship('Question', back_populates='answers')
Consultation.user = relationship('User', back_populates='consultations')
Payment.consultation = relationship('Consultation', back_populates='payments')
FAQ.category = relationship('FAQCategory', back_populates='faqs')

__all__ = [
    'Base',
    'BaseModel',
    'TimestampMixin',
    'User',
    'UserEvent',
    'UserNotification',
    'UserRole',
    'UserStatus',
    'Question',
    'Answer',
    'QuestionFeedback',
    'AnswerFeedback',
    'QuestionCategory',
    'QuestionStatus',
    'Consultation',
    'ConsultationFeedback',
    'Payment',
    'ConsultationType',
    'ConsultationStatus', 
    'PaymentStatus',
    'PaymentProvider',
    'FAQ',
    'FAQFeedback',
    'FAQCategory'
]
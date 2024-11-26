from telegram_bot.core.config import settings
from telegram_bot.core.database import db
from telegram_bot.core.cache import cache_service
from telegram_bot.core.monitoring import metrics_manager
from telegram_bot.bot import bot, dp
from telegram_bot.services import (
    AnalyticsService,
    QuestionService,
    ConsultationService,
    PaymentService,
    NotificationService,
    FAQService
)
from telegram_bot.models import (
    User,
    Question,
    Answer,
    Consultation,
    Payment,
    FAQ,
    UserNotification,
    UserEvent
)

__version__ = "1.0.0"

__all__ = [
    'settings',
    'db',
    'cache_service',
    'metrics_manager',
    'bot',
    'dp',
    # Services
    'AnalyticsService',
    'QuestionService',
    'ConsultationService',
    'PaymentService',
    'NotificationService',
    'FAQService',
    # Models
    'User',
    'Question',
    'Answer',
    'Consultation',
    'Payment',
    'FAQ',
    'UserNotification',
    'UserEvent'
]
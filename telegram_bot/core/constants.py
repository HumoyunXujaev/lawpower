from typing import Dict, Any
from enum import Enum
from decimal import Decimal
from datetime import timedelta

class UserRole(str, Enum):
    USER = 'USER'
    ADMIN = 'ADMIN'
    SUPPORT = 'SUPPORT'
    MODERATOR = 'MODERATOR'

class ConsultationStatus(str, Enum):
    PENDING = 'PENDING'
    PAID = 'PAID'
    SCHEDULED = 'SCHEDULED'
    COMPLETED = 'COMPLETED'
    CANCELLED = 'CANCELLED'

class PaymentStatus(str, Enum):
    PENDING = 'PENDING'
    PROCESSING = 'PROCESSING'
    COMPLETED = 'COMPLETED'
    FAILED = 'FAILED'
    REFUNDED = 'REFUNDED'

class PaymentProvider(str, Enum):
    CLICK = 'CLICK'
    PAYME = 'PAYME'
    UZUM = 'UZUM'

class Language(str, Enum):
    UZ = 'uz'
    RU = 'ru'

# System Constants
RATE_LIMITS = {
    'default': 30,  # requests per minute
    'payment': 5,   # payment requests per minute
    'questions': 10 # questions per minute
}

CACHE_TIMEOUTS = {
    'user': 3600,           # 1 hour
    'session': 86400,       # 24 hours
    'verification': 300,    # 5 minutes
    'payment': 900,        # 15 minutes
    'analytics': 300       # 5 minutes
}

ERROR_MESSAGES = {
    'validation': {
        'uz': 'Ma\'lumotlar noto\'g\'ri',
        'ru': 'Неверные данные'
    },
    'payment': {
        'uz': 'To\'lov xatosi',
        'ru': 'Ошибка оплаты'
    },
    'server': {
        'uz': 'Server xatosi',
        'ru': 'Ошибка сервера'
    }
}

# Business Rules Constants
CONSULTATION_RULES = {
    'min_amount': Decimal('50000.00'),
    'max_amount': Decimal('1000000.00'),
    'duration': 60,  # minutes
    'cancel_timeout': timedelta(hours=2),
    'reschedule_timeout': timedelta(hours=4),
    'types': {
        'online': {
            'price': Decimal('50000.00'),
            'duration': 30
        },
        'office': {
            'price': Decimal('100000.00'),
            'duration': 60
        }
    }
}

QUESTION_RULES = {
    'min_length': 10,
    'max_length': 1000,
    'max_per_day': 20,
    'similarity_threshold': 0.7
}

WORKING_HOURS = {
    'start': 9,  # 9 AM
    'end': 18,   # 6 PM
    'days': [0, 1, 2, 3, 4, 5]  # Monday to Saturday
}

NOTIFICATION_TYPES = {
    'consultation_reminder': {
        'template': 'consultation_reminder',
        'timeout': timedelta(hours=1)
    },
    'payment_reminder': {
        'template': 'payment_reminder',
        'timeout': timedelta(hours=4)
    },
    'question_answered': {
        'template': 'question_answered',
        'timeout': timedelta(days=1)
    }
}

PAYMENT_CONFIG = {
    'click': {
        'merchant_id': '12345',
        'service_id': '12345',
        'timeout': 900,  # 15 minutes
        'min_amount': Decimal('1000.00'),
        'max_amount': Decimal('10000000.00')
    },
    'payme': {
        'merchant_id': '12345',
        'timeout': 900,
        'min_amount': Decimal('1000.00'),
        'max_amount': Decimal('10000000.00')
    },
    'uzum': {
        'merchant_id': '12345',
        'timeout': 900,
        'min_amount': Decimal('1000.00'),
        'max_amount': Decimal('10000000.00')
    }
}

ANALYTICS_CONFIG = {
    'retention_days': 90,
    'metrics_interval': 300,  # 5 minutes
    'dashboard_cache': 300,
    'export_limit': 10000
}

SYSTEM_LIMITS = {
    'max_connections': 100,
    'request_timeout': 30,
    'file_size_limit': 10 * 1024 * 1024,  # 10MB
    'max_retries': 3,
    'batch_size': 1000
}

# Message Templates
MESSAGES = {
    'uz': {
        'welcome': """
🤖 Yuridik maslahat botiga xush kelibsiz!

Bot orqali siz:
• Savol berishingiz
• Bepul konsultatsiya olishingiz
• Advokat bilan bog'lanishingiz mumkin

Quyidagi tugmalardan birini tanlang:
        """,
        'welcome_back': "Qaytganingizdan xursandmiz! Sizga qanday yordam bera olaman?",
        'contact_support': "Operatorlar bilan bog'lanish",
        'ask_question': "❓ Savol berish",
        'my_questions': "📝 Savollarim",
        'settings': "⚙️ Sozlamalar",
        'help': "🆘 Yordam",
        'language_changed': "✅ Til muvaffaqiyatli o'zgartirildi",
        'consultation_booked': "✅ Konsultatsiya band qilindi",
        'payment_pending': "⏳ To'lov kutilmoqda",
        'payment_success': "✅ To'lov muvaffaqiyatli amalga oshirildi",
        'payment_failed': "❌ To'lov amalga oshmadi"
    },
    'ru': {
        'welcome': """
🤖 Добро пожаловать в бот юридической консультации!

Через бот вы можете:
• Задать вопрос
• Получить бесплатную консультацию
• Связаться с адвокатом

Выберите одну из кнопок ниже:
        """,
        'welcome_back': "Рады видеть вас снова! Как я могу вам помочь?",
        'contact_support': "Связаться с операторами",
        'ask_question': "❓ Задать вопрос",
        'my_questions': "📝 Мои вопросы",
        'settings': "⚙️ Настройки",
        'help': "🆘 Помощь",
        'language_changed': "✅ Язык успешно изменен",
        'consultation_booked': "✅ Консультация забронирована",
        'payment_pending': "⏳ Ожидание оплаты",
        'payment_success': "✅ Оплата успешно выполнена",
        'payment_failed': "❌ Ошибка оплаты"
    }
}


TEXTS = {
    'uz': {
        'welcome': """
🤖 Yuridik maslahat botiga xush kelibsiz!

Bot orqali siz:
• Savol berishingiz
• Bepul konsultatsiya olishingiz
• Advokat bilan bog'lanishingiz mumkin

Quyidagi tugmalardan birini tanlang:
        """,
        'ask_question': '❓ Savol berish',
        'my_questions': '📝 Savollarim',
        'consultation': '📅 Konsultatsiya',
        'support': '🆘 Yordam',
        'settings': '⚙️ Sozlamalar',
        'select_language': '🌐 Tilni tanlang',
        'language_changed': '✅ Til muvaffaqiyatli o\'zgartirildi',
        'select_consultation_type': 'Konsultatsiya turini tanlang:',
        'online_consultation': '🌐 Online konsultatsiya',
        'office_consultation': '🏢 Ofisda konsultatsiya',
        'request_contact': 'Iltimos, telefon raqamingizni yuboring:',
        'invalid_phone': '❌ Noto\'g\'ri telefon raqami formati. Qaytadan urinib ko\'ring.',
        'describe_problem': 'Muammongizni batafsil yozing:',
        'payment_instruction': 'To\'lov miqdori: {amount} so\'m\nTo\'lov tizimi: {provider}\n\nTo\'lovni amalga oshirish uchun quyidagi tugmani bosing:',
        'payment_cancelled': '❌ To\'lov bekor qilindi',
        'payment_success': '✅ To\'lov muvaffaqiyatli amalga oshirildi',
        'consultation_scheduled': '✅ Konsultatsiya {time} ga belgilandi',
        'select_time': 'Qulay vaqtni tanlang:',
        'cancel': '❌ Bekor qilish',
        'back': '◀️ Orqaga',
        'error': '❌ Xatolik yuz berdi. Iltimos, qaytadan urinib ko\'ring.'
    },
    'ru': {
        'welcome': """
🤖 Добро пожаловать в бот юридической консультации!

Через бот вы можете:
• Задать вопрос
• Получить бесплатную консультацию
• Связаться с адвокатом

Выберите одну из кнопок ниже:
        """,
        'ask_question': '❓ Задать вопрос',
        'my_questions': '📝 Мои вопросы',
        'consultation': '📅 Консультация',
        'support': '🆘 Поддержка',
        'settings': '⚙️ Настройки',
        'select_language': '🌐 Выберите язык',
        'language_changed': '✅ Язык успешно изменен',
        'select_consultation_type': 'Выберите тип консультации:',
        'online_consultation': '🌐 Онлайн консультация',
        'office_consultation': '🏢 Консультация в офисе',
        'request_contact': 'Пожалуйста, отправьте ваш номер телефона:',
        'invalid_phone': '❌ Неверный формат номера телефона. Попробуйте еще раз.',
        'describe_problem': 'Опишите подробно вашу проблему:',
        'payment_instruction': 'Сумма к оплате: {amount} сум\nСистема оплаты: {provider}\n\nНажмите кнопку ниже для оплаты:',
        'payment_cancelled': '❌ Оплата отменена',
        'payment_success': '✅ Оплата успешно выполнена',
        'consultation_scheduled': '✅ Консультация назначена на {time}',
        'select_time': 'Выберите удобное время:',
        'cancel': '❌ Отмена',
        'back': '◀️ Назад',
        'error': '❌ Произошла ошибка. Пожалуйста, попробуйте еще раз.'
    }
}

FAQ_TEXTS = {
    'uz': {
        'faq_categories': '📚 Tez-tez so\'raladigan savollar bo\'limlari:',
        'select_faq': 'Savolni tanlang:',
        'no_faqs_in_category': 'Bu bo\'limda hozircha savollar yo\'q.',
        'faq_not_found': 'Savol topilmadi.',
        'enter_faq_search': 'Qidirilayotgan savolni kiriting:',
        'no_faq_results': 'Sizning so\'rovingiz bo\'yicha savollar topilmadi.',
        'search_faq': '🔍 Qidirish',
        'helpful': '👍 Foydali',
        'not_helpful': '👎 Foydali emas',
        'thanks_feedback': 'Fikr-mulohaza uchun rahmat!',
        'back_to_category': '◀️ Bo\'limga qaytish',
        'back_to_categories': '◀️ Bo\'limlarga qaytish'
    },
    'ru': {
        'faq_categories': '📚 Разделы часто задаваемых вопросов:',
        'select_faq': 'Выберите вопрос:',
        'no_faqs_in_category': 'В этом разделе пока нет вопросов.',
        'faq_not_found': 'Вопрос не найден.',
        'enter_faq_search': 'Введите искомый вопрос:',
        'no_faq_results': 'По вашему запросу вопросов не найдено.',
        'search_faq': '🔍 Поиск',
        'helpful': '👍 Полезно',
        'not_helpful': '👎 Не полезно',
        'thanks_feedback': 'Спасибо за отзыв!',
        'back_to_category': '◀️ Назад к разделу',
        'back_to_categories': '◀️ Назад к разделам'
    }
}

# Add FAQ texts to main TEXTS dictionary
for lang in ['uz', 'ru']:
    TEXTS[lang].update(FAQ_TEXTS[lang])

    
# Admin Configuration
ADMIN_CONFIG = {
    'dashboard': {
        'cache_timeout': 300,
        'metrics_interval': 60,
        'max_recent_actions': 100
    },
    'notifications': {
        'error_threshold': 5,
        'warning_threshold': 3
    },
    'export': {
        'formats': ['csv', 'xlsx'],
        'max_records': 10000
    }
}

class SystemMetrics:
    """System metrics configuration"""
    REQUEST_COUNT = 'request_count'
    ERROR_COUNT = 'error_count'
    RESPONSE_TIME = 'response_time'
    ACTIVE_USERS = 'active_users'
    DB_CONNECTIONS = 'db_connections'
    CACHE_HITS = 'cache_hits'
    QUESTIONS_TOTAL = 'questions_total'
    ANSWERS_TOTAL = 'answers_total'
    CONSULTATIONS_TOTAL = 'consultations_total'
    PAYMENTS_TOTAL = 'payments_total'

# Export all constants
__all__ = [
    'UserRole',
    'ConsultationStatus',
    'PaymentStatus',
    'PaymentProvider',
    'Language',
    'RATE_LIMITS',
    'CACHE_TIMEOUTS',
    'ERROR_MESSAGES',
    'CONSULTATION_RULES',
    'QUESTION_RULES',
    'WORKING_HOURS',
    'NOTIFICATION_TYPES',
    'PAYMENT_CONFIG',
    'ANALYTICS_CONFIG',
    'SYSTEM_LIMITS',
    'MESSAGES',
    'ADMIN_CONFIG',
    'SystemMetrics'
]
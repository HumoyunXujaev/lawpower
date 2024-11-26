from aiogram.types import (
    InlineKeyboardMarkup,
    InlineKeyboardButton,
    ReplyKeyboardMarkup,
    KeyboardButton,
    ReplyKeyboardRemove
)
from typing import List, Optional, Dict
from datetime import datetime
from telegram_bot.models import FAQ
from telegram_bot.core.constants import TEXTS
from telegram_bot.models import Question, Consultation

from aiogram.types import (
    InlineKeyboardMarkup,
    InlineKeyboardButton,
    ReplyKeyboardMarkup,
    KeyboardButton,
    ReplyKeyboardRemove
)
from typing import List, Optional
from telegram_bot.core.constants import TEXTS

def get_language_keyboard() -> InlineKeyboardMarkup:
    """Language selection keyboard"""
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(text="🇺🇿 O'zbek", callback_data="language:uz"),
                InlineKeyboardButton(text="🇷🇺 Русский", callback_data="language:ru")
            ]
        ]
    )

def get_main_menu_keyboard(language: str) -> ReplyKeyboardMarkup:
    """Main menu keyboard"""
    return ReplyKeyboardMarkup(
        keyboard=[
            [
                KeyboardButton(text=TEXTS[language]['ask_question']),
                KeyboardButton(text=TEXTS[language]['consultation'])
            ],
            [
                KeyboardButton(text=TEXTS[language]['my_questions']),
                KeyboardButton(text=TEXTS[language]['faq'])
            ],
            [
                KeyboardButton(text=TEXTS[language]['support']),
                KeyboardButton(text=TEXTS[language]['settings'])
            ]
        ],
        resize_keyboard=True
    )

def get_contact_keyboard(language: str) -> ReplyKeyboardMarkup:
    """Contact sharing keyboard"""
    return ReplyKeyboardMarkup(
        keyboard=[
            [
                KeyboardButton(
                    text=TEXTS[language]['share_contact'],
                    request_contact=True
                )
            ],
            [
                KeyboardButton(text=TEXTS[language]['cancel'])
            ]
        ],
        resize_keyboard=True,
        one_time_keyboard=True
    )

def get_consultation_type_keyboard(language: str) -> InlineKeyboardMarkup:
    """Consultation type selection keyboard"""
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text=TEXTS[language]['online_consultation'],
                    callback_data="consultation_type:online"
                )
            ],
            [
                InlineKeyboardButton(
                    text=TEXTS[language]['office_consultation'],
                    callback_data="consultation_type:office"
                )
            ],
            [
                InlineKeyboardButton(
                    text=TEXTS[language]['cancel'],
                    callback_data="cancel"
                )
            ]
        ]
    )

def get_payment_methods_keyboard(
    language: str,
    amount: float,
    consultation_id: int
) -> InlineKeyboardMarkup:
    """Payment methods keyboard"""
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text="Click",
                    callback_data=f"pay:click:{consultation_id}:{amount}"
                ),
                InlineKeyboardButton(
                    text="Payme",
                    callback_data=f"pay:payme:{consultation_id}:{amount}"
                )
            ],
            [
                InlineKeyboardButton(
                    text="Uzum",
                    callback_data=f"pay:uzum:{consultation_id}:{amount}"
                )
            ],
            [
                InlineKeyboardButton(
                    text=TEXTS[language]['cancel'],
                    callback_data="cancel"
                )
            ]
        ]
    )

def get_faq_keyboard(language: str) -> InlineKeyboardMarkup:
    """FAQ categories keyboard"""
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text=TEXTS[language]['general_questions'],
                    callback_data="faq:general"
                )
            ],
            [
                InlineKeyboardButton(
                    text=TEXTS[language]['consultation_questions'],
                    callback_data="faq:consultation"
                )
            ],
            [
                InlineKeyboardButton(
                    text=TEXTS[language]['payment_questions'],
                    callback_data="faq:payment"
                )
            ],
            [
                InlineKeyboardButton(
                    text=TEXTS[language]['back'],
                    callback_data="back_to_menu"
                )
            ]
        ]
    )

def get_settings_keyboard(language: str) -> InlineKeyboardMarkup:
    """Settings keyboard"""
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text=TEXTS[language]['change_language'],
                    callback_data="settings:language"
                )
            ],
            [
                InlineKeyboardButton(
                    text=TEXTS[language]['notifications'],
                    callback_data="settings:notifications"
                )
            ],
            [
                InlineKeyboardButton(
                    text=TEXTS[language]['profile'],
                    callback_data="settings:profile"
                )
            ],
            [
                InlineKeyboardButton(
                    text=TEXTS[language]['back'],
                    callback_data="back_to_menu"
                )
            ]
        ]
    )

def get_rating_keyboard(language: str) -> InlineKeyboardMarkup:
    """Rating keyboard"""
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(text="⭐", callback_data="rate:1"),
                InlineKeyboardButton(text="⭐⭐", callback_data="rate:2"),
                InlineKeyboardButton(text="⭐⭐⭐", callback_data="rate:3"),
                InlineKeyboardButton(text="⭐⭐⭐⭐", callback_data="rate:4"),
                InlineKeyboardButton(text="⭐⭐⭐⭐⭐", callback_data="rate:5")
            ],
            [
                InlineKeyboardButton(
                    text=TEXTS[language]['skip'],
                    callback_data="rate:skip"
                )
            ]
        ]
    )

def get_support_keyboard(language: str) -> InlineKeyboardMarkup:
    """Support keyboard"""
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text=TEXTS[language]['contact_support'],
                    callback_data="support:contact"
                )
            ],
            [
                InlineKeyboardButton(
                    text=TEXTS[language]['faq'],
                    callback_data="support:faq"
                )
            ],
            [
                InlineKeyboardButton(
                    text=TEXTS[language]['report_problem'],
                    callback_data="support:report"
                )
            ],
            [
                InlineKeyboardButton(
                    text=TEXTS[language]['back'],
                    callback_data="back_to_menu"
                )
            ]
        ]
    )

def get_start_keyboard(language: str) -> ReplyKeyboardMarkup:
    """Main menu keyboard"""
    keyboard = [
        [
            KeyboardButton(text=TEXTS[language]['ask_question']),
            KeyboardButton(text=TEXTS[language]['consultation'])
        ],
        [
            KeyboardButton(text=TEXTS[language]['my_questions']),
            KeyboardButton(text=TEXTS[language]['faq'])
        ],
        [
            KeyboardButton(text=TEXTS[language]['support']),
            KeyboardButton(text=TEXTS[language]['settings'])
        ]
    ]
    return ReplyKeyboardMarkup(
        keyboard=keyboard,
        resize_keyboard=True,
        one_time_keyboard=False
    )

def get_cancel_keyboard(language: str) -> ReplyKeyboardMarkup:
    """Cancel button keyboard"""
    keyboard = [[KeyboardButton(text=TEXTS[language]['cancel'])]]
    return ReplyKeyboardMarkup(
        keyboard=keyboard,
        resize_keyboard=True,
        one_time_keyboard=True
    )

def get_question_category_keyboard(language: str) -> InlineKeyboardMarkup:
    """Question category selection keyboard"""
    categories = [
        ('family', '👨‍👩‍👧‍👦'),
        ('property', '🏠'),
        ('business', '💼'),
        ('criminal', '⚖️'),
        ('other', '❓')
    ]
    
    keyboard = []
    for category, emoji in categories:
        keyboard.append([
            InlineKeyboardButton(
                text=f"{emoji} {TEXTS[language][f'category_{category}']}",
                callback_data=f"category:{category}"
            )
        ])
    
    keyboard.append([
        InlineKeyboardButton(
            text=TEXTS[language]['cancel'],
            callback_data="cancel"
        )
    ])
    
    return InlineKeyboardMarkup(inline_keyboard=keyboard)

def get_similar_questions_keyboard(
    questions: List[Question],
    language: str
) -> InlineKeyboardMarkup:
    """Similar questions keyboard"""
    keyboard = []
    
    # Add question buttons
    for i, question in enumerate(questions, 1):
        keyboard.append([
            InlineKeyboardButton(
                text=f"{i}. {question.question_text[:50]}...",
                callback_data=f"similar:{question.id}"
            )
        ])
    
    # Add action buttons
    keyboard.extend([
        [
            InlineKeyboardButton(
                text=TEXTS[language]['ask_anyway'],
                callback_data="ask_anyway"
            )
        ],
        [
            InlineKeyboardButton(
                text=TEXTS[language]['cancel'],
                callback_data="cancel_question"
            )
        ]
    ])
    
    return InlineKeyboardMarkup(inline_keyboard=keyboard)


def get_consultation_time_keyboard(
    language: str,
    available_times: List[datetime]
) -> InlineKeyboardMarkup:
    """Consultation time selection keyboard"""
    keyboard = []
    
    # Group times by date
    times_by_date = {}
    for time in available_times:
        date_str = time.strftime('%Y-%m-%d')
        if date_str not in times_by_date:
            times_by_date[date_str] = []
        times_by_date[date_str].append(time)
    
    # Create keyboard with dates and times
    for date_str, times in times_by_date.items():
        # Add date header
        keyboard.append([
            InlineKeyboardButton(
                text=datetime.strptime(date_str, '%Y-%m-%d').strftime('%d.%m.%Y'),
                callback_data=f"date_header:{date_str}"
            )
        ])
        
        # Add time slots in rows of 3
        time_row = []
        for time in times:
            time_row.append(
                InlineKeyboardButton(
                    text=time.strftime('%H:%M'),
                    callback_data=f"time:{time.isoformat()}"
                )
            )
            if len(time_row) == 3:
                keyboard.append(time_row)
                time_row = []
        if time_row:
            keyboard.append(time_row)
    
    # Add cancel button
    keyboard.append([
        InlineKeyboardButton(
            text=TEXTS[language]['cancel'],
            callback_data="cancel_consultation"
        )
    ])
    
    return InlineKeyboardMarkup(inline_keyboard=keyboard)

def get_confirm_cancel_keyboard(language: str) -> InlineKeyboardMarkup:
    """Confirm/cancel keyboard"""
    keyboard = [
        [
            InlineKeyboardButton(
                text=TEXTS[language]['confirm'],
                callback_data="confirm"
            ),
            InlineKeyboardButton(
                text=TEXTS[language]['cancel'],
                callback_data="cancel"
            )
        ]
    ]
    return InlineKeyboardMarkup(inline_keyboard=keyboard)


def get_notification_settings_keyboard(
    language: str,
    settings: Dict[str, bool]
) -> InlineKeyboardMarkup:
    """Notification settings keyboard"""
    keyboard = []
    
    # Add notification toggles
    notification_types = [
        ('questions', '❓'),
        ('consultations', '📅'),
        ('news', '📢'),
        ('support', '🆘')
    ]
    
    for type_key, emoji in notification_types:
        status = settings.get(type_key, True)
        keyboard.append([
            InlineKeyboardButton(
                text=f"{emoji} {TEXTS[language][f'notify_{type_key}']} {'✅' if status else '❌'}",
                callback_data=f"notifications:{type_key}"
            )
        ])
    
    # Add back button
    keyboard.append([
        InlineKeyboardButton(
            text=TEXTS[language]['back'],
            callback_data="settings:main"
        )
    ])
    
    return InlineKeyboardMarkup(inline_keyboard=keyboard)

def get_admin_menu_keyboard() -> InlineKeyboardMarkup:
    """Admin main menu keyboard"""
    keyboard = [
        [
            InlineKeyboardButton(
                text="📊 Statistics",
                callback_data="admin:stats"
            )
        ],
        [
            InlineKeyboardButton(
                text="❓ Questions",
                callback_data="admin:questions"
            ),
            InlineKeyboardButton(
                text="📅 Consultations",
                callback_data="admin:consultations"
            )
        ],
        [
            InlineKeyboardButton(
                text="👥 Users",
                callback_data="admin:users"
            ),
            InlineKeyboardButton(
                text="📢 Broadcast",
                callback_data="admin:broadcast"
            )
        ],
        [
            InlineKeyboardButton(
                text="⚙️ Settings",
                callback_data="admin:settings"
            )
        ]
    ]
    return InlineKeyboardMarkup(inline_keyboard=keyboard)

def get_rating_keyboard(language: str) -> InlineKeyboardMarkup:
    """Rating keyboard with stars"""
    keyboard = []
    
    # Add star ratings
    for i in range(1, 6):
        keyboard.append([
            InlineKeyboardButton(
                text="⭐" * i,
                callback_data=f"rate:{i}"
            )
        ])
    
    # Add skip button
    keyboard.append([
        InlineKeyboardButton(
            text=TEXTS[language]['skip'],
            callback_data="rate:skip"
        )
    ])
    
    return InlineKeyboardMarkup(inline_keyboard=keyboard)

def get_consultation_actions_keyboard(
    consultation: Consultation,
    language: str
) -> InlineKeyboardMarkup:
    """Consultation actions keyboard based on status"""
    keyboard = []
    
    if consultation.status == 'PENDING':
        keyboard.extend([
            [
                InlineKeyboardButton(
                    text=TEXTS[language]['pay_now'],
                    callback_data=f"consultation:pay:{consultation.id}"
                )
            ],
            [
                InlineKeyboardButton(
                    text=TEXTS[language]['cancel_consultation'],
                    callback_data=f"consultation:cancel:{consultation.id}"
                )
            ]
        ])
    elif consultation.status == 'PAID':
        keyboard.append([
            InlineKeyboardButton(
                text=TEXTS[language]['choose_time'],
                callback_data=f"consultation:schedule:{consultation.id}"
            )
        ])
    elif consultation.status == 'SCHEDULED':
        keyboard.extend([
            [
                InlineKeyboardButton(
                    text=TEXTS[language]['reschedule'],
                    callback_data=f"consultation:reschedule:{consultation.id}"
                )
            ],
            [
                InlineKeyboardButton(
                    text=TEXTS[language]['cancel_consultation'],
                    callback_data=f"consultation:cancel:{consultation.id}"
                )
            ]
        ])
    elif consultation.status == 'COMPLETED':
        if not consultation.feedback:
            keyboard.append([
                InlineKeyboardButton(
                    text=TEXTS[language]['leave_feedback'],
                    callback_data=f"consultation:feedback:{consultation.id}"
                )
            ])
    
    return InlineKeyboardMarkup(inline_keyboard=keyboard)

def get_admin_question_keyboard(question_id: int) -> InlineKeyboardMarkup:
    """Admin question management keyboard"""
    keyboard = [
        [
            InlineKeyboardButton(
                text="✍️ Answer",
                callback_data=f"admin:answer:{question_id}"
            )
        ],
        [
            InlineKeyboardButton(
                text="🔄 Auto Answer",
                callback_data=f"admin:auto_answer:{question_id}"
            )
        ],
        [
            InlineKeyboardButton(
                text="❌ Delete",
                callback_data=f"admin:delete_question:{question_id}"
            )
        ],
        [
            InlineKeyboardButton(
                text="◀️ Back",
                callback_data="admin:questions"
            )
        ]
    ]
    return InlineKeyboardMarkup(inline_keyboard=keyboard)

def get_admin_user_keyboard(user_id: int) -> InlineKeyboardMarkup:
    """Admin user management keyboard"""
    keyboard = [
        [
            InlineKeyboardButton(
                text="📝 Edit Roles",
                callback_data=f"admin:edit_roles:{user_id}"
            ),
            InlineKeyboardButton(
                text="🚫 Block/Unblock",
                callback_data=f"admin:toggle_block:{user_id}"
            )
        ],
        [
            InlineKeyboardButton(
                text="📨 Send Message",
                callback_data=f"admin:message_user:{user_id}"
            ),
            InlineKeyboardButton(
                text="📊 Statistics",
                callback_data=f"admin:user_stats:{user_id}"
            )
        ],
        [
            InlineKeyboardButton(
                text="◀️ Back",
                callback_data="admin:users"
            )
        ]
    ]
    return InlineKeyboardMarkup(inline_keyboard=keyboard)

def get_admin_consultation_keyboard(consultation_id: int) -> InlineKeyboardMarkup:
    """Admin consultation management keyboard"""
    keyboard = [
        [
            InlineKeyboardButton(
                text="✅ Approve",
                callback_data=f"admin:approve_consultation:{consultation_id}"
            )
        ],
        [
            InlineKeyboardButton(
                text="📅 Schedule",
                callback_data=f"admin:schedule_consultation:{consultation_id}"
            )
        ],
        [
            InlineKeyboardButton(
                text="❌ Reject",
                callback_data=f"admin:reject_consultation:{consultation_id}"
            )
        ],
        [
            InlineKeyboardButton(
                text="💬 Send Message",
                callback_data=f"admin:message_consultation:{consultation_id}"
            )
        ],
        [
            InlineKeyboardButton(
                text="◀️ Back",
                callback_data="admin:consultations"
            )
        ]
    ]
    return InlineKeyboardMarkup(inline_keyboard=keyboard)

def get_admin_broadcast_keyboard() -> InlineKeyboardMarkup:
    """Admin broadcast targeting keyboard"""
    keyboard = [
        [
            InlineKeyboardButton(
                text="👥 All Users",
                callback_data="broadcast:all"
            )
        ],
        [
            InlineKeyboardButton(
                text="✅ Active Users",
                callback_data="broadcast:active"
            )
        ],
        [
            InlineKeyboardButton(
                text="🇺🇿 Uzbek",
                callback_data="broadcast:uz"
            ),
            InlineKeyboardButton(
                text="🇷🇺 Russian",
                callback_data="broadcast:ru"
            )
        ],
        [
            InlineKeyboardButton(
                text="❌ Cancel",
                callback_data="admin:menu"
            )
        ]
    ]
    return InlineKeyboardMarkup(inline_keyboard=keyboard)

def get_support_keyboard(language: str) -> InlineKeyboardMarkup:
    """Support menu keyboard"""
    keyboard = [
        [
            InlineKeyboardButton(
                text=TEXTS[language]['contact_support'],
                callback_data="support:contact"
            )
        ],
        [
            InlineKeyboardButton(
                text=TEXTS[language]['faq'],
                callback_data="support:faq"
            )
        ],
        [
            InlineKeyboardButton(
                text=TEXTS[language]['report_problem'],
                callback_data="support:report"
            )
        ],
        [
            InlineKeyboardButton(
                text=TEXTS[language]['back'],
                callback_data="back_to_menu"
            )
        ]
    ]
    return InlineKeyboardMarkup(inline_keyboard=keyboard)

def get_consultation_calendar_keyboard(
    year: int,
    month: int,
    language: str
) -> InlineKeyboardMarkup:
    """Generate calendar keyboard for consultation scheduling"""
    import calendar
    
    keyboard = []
    
    # Add month and year header
    month_names = {
        'uz': ['Yanvar', 'Fevral', 'Mart', 'Aprel', 'May', 'Iyun', 
               'Iyul', 'Avgust', 'Sentabr', 'Oktabr', 'Noyabr', 'Dekabr'],
        'ru': ['Январь', 'Февраль', 'Март', 'Апрель', 'Май', 'Июнь',
               'Июль', 'Август', 'Сентябрь', 'Октябрь', 'Ноябрь', 'Декабрь']
    }
    
    keyboard.append([
        InlineKeyboardButton(
            text=f"{month_names[language][month-1]} {year}",
            callback_data="ignore"
        )
    ])
    
    # Add weekday headers
    weekdays = {
        'uz': ['Du', 'Se', 'Ch', 'Pa', 'Ju', 'Sh', 'Ya'],
        'ru': ['Пн', 'Вт', 'Ср', 'Чт', 'Пт', 'Сб', 'Вс']
    }
    keyboard.append([
        InlineKeyboardButton(text=day, callback_data="ignore")
        for day in weekdays[language]
    ])
    
    # Add calendar days
    cal = calendar.monthcalendar(year, month)
    for week in cal:
        row = []
        for day in week:
            if day == 0:
                row.append(InlineKeyboardButton(
                    text=" ",
                    callback_data="ignore"
                ))
            else:
                row.append(InlineKeyboardButton(
                    text=str(day),
                    callback_data=f"date:{year}-{month:02d}-{day:02d}"
                ))
        keyboard.append(row)
    
    # Add navigation buttons
    nav_buttons = []
    
    # Previous month
    if month == 1:
        prev_year = year - 1
        prev_month = 12
    else:
        prev_year = year
        prev_month = month - 1
        
    nav_buttons.append(InlineKeyboardButton(
        text="◀️",
        callback_data=f"calendar:{prev_year}:{prev_month}"
    ))
    
    # Next month
    if month == 12:
        next_year = year + 1
        next_month = 1
    else:
        next_year = year
        next_month = month + 1
        
    nav_buttons.append(InlineKeyboardButton(
        text="▶️",
        callback_data=f"calendar:{next_year}:{next_month}"
    ))
    
    keyboard.append(nav_buttons)
    
    # Add cancel button
    keyboard.append([
        InlineKeyboardButton(
            text=TEXTS[language]['cancel'],
            callback_data="cancel"
        )
    ])
    
    return InlineKeyboardMarkup(inline_keyboard=keyboard)

def get_consultation_time_keyboard(
    date: str,
    language: str,
    booked_times: List[str] = None
) -> InlineKeyboardMarkup:
    """Generate time selection keyboard for consultation"""
    keyboard = []
    booked_times = booked_times or []
    
    # Available time slots (9:00 - 18:00)
    time_slots = []
    for hour in range(9, 18):
        for minute in [0, 30]:
            time_slots.append(f"{hour:02d}:{minute:02d}")
    
    # Add time buttons in rows of 3
    row = []
    for time in time_slots:
        if len(row) == 3:
            keyboard.append(row)
            row = []
            
        is_booked = f"{date} {time}" in booked_times
        row.append(InlineKeyboardButton(
            text=f"❌ {time}" if is_booked else time,
            callback_data=f"time:{date}:{time}" if not is_booked else "ignore"
        ))
        
    if row:
        keyboard.append(row)
    
    # Add back and cancel buttons
    keyboard.append([
        InlineKeyboardButton(
            text=TEXTS[language]['back'],
            callback_data=f"calendar_back:{date}"
        ),
        InlineKeyboardButton(
            text=TEXTS[language]['cancel'],
            callback_data="cancel"
        )
    ])
    
    return InlineKeyboardMarkup(inline_keyboard=keyboard)




def get_faq_categories_keyboard(language: str) -> InlineKeyboardMarkup:
    """Generate FAQ categories keyboard"""
    categories = [
        ('general', '📝'),
        ('payment', '💳'),
        ('consultation', '👨‍💼'),
        ('technical', '⚙️')
    ]
    
    keyboard = []
    for category, emoji in categories:
        keyboard.append([
            InlineKeyboardButton(
                text=f"{emoji} {TEXTS[language][f'category_{category}']}",
                callback_data=f"faq_cat:{category}"
            )
        ])
    
    # Add back button
    keyboard.append([
        InlineKeyboardButton(
            text=TEXTS[language]['back'],
            callback_data="start"
        )
    ])
    
    return InlineKeyboardMarkup(inline_keyboard=keyboard)

def get_faq_list_keyboard(
    faqs: List[FAQ],
    language: str
) -> InlineKeyboardMarkup:
    """Generate FAQ list keyboard"""
    keyboard = []
    
    for faq in faqs:
        # Truncate question if too long
        question = faq.question[:50] + "..." if len(faq.question) > 50 else faq.question
        
        keyboard.append([
            InlineKeyboardButton(
                text=question,
                callback_data=f"faq:{faq.id}"
            )
        ])
    
    # Add back button
    keyboard.append([
        InlineKeyboardButton(
            text=TEXTS[language]['back'],
            callback_data="faq_categories"
        )
    ])
    
    return InlineKeyboardMarkup(inline_keyboard=keyboard)

def get_faq_rating_keyboard(faq_id: int) -> InlineKeyboardMarkup:
    """Generate FAQ rating keyboard"""
    keyboard = [
        [
            InlineKeyboardButton(
                text="👍 Helpful",
                callback_data=f"faq_rate:{faq_id}:1"
            ),
            InlineKeyboardButton(
                text="👎 Not helpful",
                callback_data=f"faq_rate:{faq_id}:0"
            )
        ],
        [
            InlineKeyboardButton(
                text="◀️ Back to categories",
                callback_data="faq_categories"
            )
        ]
    ]
    
    return InlineKeyboardMarkup(inline_keyboard=keyboard)


def get_faq_feedback_keyboard(language: str) -> InlineKeyboardMarkup:
    """Generate FAQ feedback keyboard"""
    keyboard = [
        [
            InlineKeyboardButton(
                text=TEXTS[language]['skip_feedback'],
                callback_data="skip_faq_feedback"
            )
        ],
        [
            InlineKeyboardButton(
                text=TEXTS[language]['back_to_categories'],
                callback_data="faq_categories"
            )
        ]
    ]
    return InlineKeyboardMarkup(inline_keyboard=keyboard)

def get_faq_navigation_keyboard(
    language: str,
    category_id: int = None,
    show_helpful: bool = False,
    faq_id: int = None
) -> InlineKeyboardMarkup:
    """Generate FAQ navigation keyboard"""
    keyboard = []
    
    if show_helpful and faq_id:
        # Add helpful/not helpful buttons
        keyboard.append([
            InlineKeyboardButton(
                text=TEXTS[language]['helpful'],
                callback_data=f"faq_helpful:{faq_id}:1"
            ),
            InlineKeyboardButton(
                text=TEXTS[language]['not_helpful'],
                callback_data=f"faq_helpful:{faq_id}:0"
            )
        ])
    
    # Add navigation buttons
    nav_row = []
    
    if category_id:
        nav_row.append(
            InlineKeyboardButton(
                text=TEXTS[language]['back_to_category'],
                callback_data=f"faq_cat:{category_id}"
            )
        )
    
    nav_row.append(
        InlineKeyboardButton(
            text=TEXTS[language]['back_to_categories'],
            callback_data="faq_categories"
        )
    )
    
    keyboard.append(nav_row)
    
    # Add search button
    keyboard.append([
        InlineKeyboardButton(
            text=TEXTS[language]['search_faq'],
            callback_data="faq_search"
        )
    ])
    
    return InlineKeyboardMarkup(inline_keyboard=keyboard)

def get_suggested_faqs_keyboard(
    faqs: List[FAQ],
    language: str,
    category_id: int = None
) -> InlineKeyboardMarkup:
    """Generate keyboard for suggested FAQs"""
    keyboard = []
    
    for faq in faqs:
        keyboard.append([
            InlineKeyboardButton(
                text=f"📌 {faq.question[:50]}...",
                callback_data=f"faq:{faq.id}"
            )
        ])
    
    # Add navigation
    nav_row = []
    
    if category_id:
        nav_row.append(
            InlineKeyboardButton(
                text=TEXTS[language]['back_to_category'],
                callback_data=f"faq_cat:{category_id}"
            )
        )
    
    nav_row.append(
        InlineKeyboardButton(
            text=TEXTS[language]['back_to_categories'],
            callback_data="faq_categories"
        )
    )
    
    keyboard.append(nav_row)
    
    return InlineKeyboardMarkup(inline_keyboard=keyboard)

def get_pagination_keyboard(
    current_page: int,
    total_pages: int,
    callback_prefix: str
) -> List[List[InlineKeyboardButton]]:
    """Generate pagination buttons"""
    keyboard = []
    
    # Add navigation buttons
    nav_buttons = []
    
    if current_page > 1:
        nav_buttons.append(
            InlineKeyboardButton(
                text="◀️",
                callback_data=f"{callback_prefix}:page:{current_page-1}"
            )
        )
    
    nav_buttons.append(
        InlineKeyboardButton(
            text=f"{current_page}/{total_pages}",
            callback_data="pagination_info"
        )
    )
    
    if current_page < total_pages:
        nav_buttons.append(
            InlineKeyboardButton(
                text="▶️",
                callback_data=f"{callback_prefix}:page:{current_page+1}"
            )
        )
    
    keyboard.append(nav_buttons)
    return keyboard

# Helper function to add pagination to any keyboard
def add_pagination(
    keyboard: List[List[InlineKeyboardButton]],
    current_page: int,
    total_pages: int,
    callback_prefix: str
) -> InlineKeyboardMarkup:
    """Add pagination buttons to existing keyboard"""
    if total_pages > 1:
        pagination = get_pagination_keyboard(
            current_page,
            total_pages,
            callback_prefix
        )
        keyboard.extend(pagination)
    return InlineKeyboardMarkup(inline_keyboard=keyboard)

# Export all keyboard functions
__all__ = [
    'get_start_keyboard',
    'get_language_keyboard',
    'get_contact_keyboard',
    'get_cancel_keyboard',
    'get_question_category_keyboard',
    'get_similar_questions_keyboard',
    'get_consultation_type_keyboard',
    'get_payment_methods_keyboard',
    'get_consultation_time_keyboard',
    'get_confirm_cancel_keyboard',
    'get_settings_keyboard',
    'get_notification_settings_keyboard',
    'get_admin_menu_keyboard',
    'get_rating_keyboard',
    'get_consultation_actions_keyboard',
    'get_admin_question_keyboard',
    'get_admin_user_keyboard',
    'get_admin_consultation_keyboard',
    'get_admin_broadcast_keyboard',
    'get_support_keyboard',
    'get_faq_keyboard',
    'get_pagination_keyboard',
    'add_pagination'
]

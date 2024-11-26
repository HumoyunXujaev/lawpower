from aiogram.filters import BaseFilter
from aiogram.types import Message, CallbackQuery
from typing import Union, Optional
from datetime import datetime, timedelta

from telegram_bot.core.config import settings
from telegram_bot.models import User
from telegram_bot.utils.cache import cache

class IsAdmin(BaseFilter):
    """Check if user is admin"""
    async def __call__(self, event: Union[Message, CallbackQuery]) -> bool:
        return event.from_user.id in settings.ADMIN_IDS

class IsSupport(BaseFilter):
    """Check if user is support"""
    async def __call__(self, event: Union[Message, CallbackQuery], user: User) -> bool:
        return any(role == 'SUPPORT' for role in user.roles)

class IsModerator(BaseFilter):
    """Check if user is moderator"""
    async def __call__(self, event: Union[Message, CallbackQuery], user: User) -> bool:
        return any(role in ['ADMIN', 'MODERATOR', 'SUPPORT'] for role in user.roles)

class HasActiveSubscription(BaseFilter):
    """Check if user has active subscription"""
    async def __call__(self, event: Union[Message, CallbackQuery], user: User) -> bool:
        subscription = await cache.get(f"subscription:{user.id}")
        if not subscription:
            return False
        return datetime.fromisoformat(subscription['expires_at']) > datetime.utcnow()

class RateLimit(BaseFilter):
    """Rate limiting filter"""
    
    def __init__(self, rate: int, per: int):
        self.rate = rate  # Number of requests
        self.per = per    # Time period in seconds
    
    async def __call__(self, event: Union[Message, CallbackQuery]) -> bool:
        user_id = event.from_user.id
        key = f"rate_limit:{user_id}:{event.chat.id}"
        
        # Get current count
        count = await cache.get(key) or 0
        
        if count >= self.rate:
            return False
        
        # Increment count
        pipe = cache.redis.pipeline()
        pipe.incr(key)
        pipe.expire(key, self.per)
        await pipe.execute()
        
        return True

class HasCompletedRegistration(BaseFilter):
    """Check if user has completed registration"""
    async def __call__(self, event: Union[Message, CallbackQuery], user: User) -> bool:
        return bool(user.language and user.full_name)

class IsBlocked(BaseFilter):
    """Check if user is blocked"""
    async def __call__(self, event: Union[Message, CallbackQuery], user: User) -> bool:
        return user.is_blocked

class HasActiveConsultation(BaseFilter):
    """Check if user has active consultation"""
    async def __call__(self, event: Union[Message, CallbackQuery], user: User) -> bool:
        return await cache.exists(f"active_consultation:{user.id}")

class IsWorkingHours(BaseFilter):
    """Check if current time is within working hours"""
    
    def __init__(
        self,
        start_hour: int = 9,
        end_hour: int = 18,
        working_days: set = None
    ):
        self.start_hour = start_hour
        self.end_hour = end_hour
        self.working_days = working_days or {0, 1, 2, 3, 4}  # Mon-Fri
    
    async def __call__(self, event: Union[Message, CallbackQuery]) -> bool:
        now = datetime.now()
        return (
            now.weekday() in self.working_days and
            self.start_hour <= now.hour < self.end_hour
        )

class HasPermission(BaseFilter):
    """Check if user has specific permission"""
    
    def __init__(self, permission: str):
        self.permission = permission
    
    async def __call__(self, event: Union[Message, CallbackQuery], user: User) -> bool:
        user_permissions = await cache.get(f"permissions:{user.id}")
        if not user_permissions:
            return False
        return self.permission in user_permissions

class ContentTypeFilter(BaseFilter):
    """Filter messages by content type"""
    
    def __init__(self, content_types: Union[str, list]):
        self.content_types = (
            [content_types] if isinstance(content_types, str) else content_types
        )
    
    async def __call__(self, message: Message) -> bool:
        return message.content_type in self.content_types

class TextLengthFilter(BaseFilter):
    """Filter messages by text length"""
    
    def __init__(self, min_length: Optional[int] = None, max_length: Optional[int] = None):
        self.min_length = min_length
        self.max_length = max_length
    
    async def __call__(self, message: Message) -> bool:
        if not message.text:
            return False
            
        text_length = len(message.text)
        
        if self.min_length and text_length < self.min_length:
            return False
            
        if self.max_length and text_length > self.max_length:
            return False
            
        return True

class RegexFilter(BaseFilter):
    """Filter messages by regex pattern"""
    
    def __init__(self, pattern: str):
        import re
        self.pattern = re.compile(pattern)
    
    async def __call__(self, message: Message) -> bool:
        if not message.text:
            return False
        return bool(self.pattern.match(message.text))

class LanguageFilter(BaseFilter):
    """Filter messages by user language"""
    
    def __init__(self, languages: Union[str, list]):
        self.languages = [languages] if isinstance(languages, str) else languages
    
    async def __call__(self, event: Union[Message, CallbackQuery], user: User) -> bool:
        return user.language in self.languages

class ChatTypeFilter(BaseFilter):
    """Filter messages by chat type"""
    
    def __init__(self, chat_types: Union[str, list]):
        self.chat_types = [chat_types] if isinstance(chat_types, str) else chat_types
    
    async def __call__(self, message: Message) -> bool:
        return message.chat.type in self.chat_types

class StateFilter(BaseFilter):
    """Filter by current user state"""
    
    def __init__(self, states: Union[str, list]):
        from telegram_bot.bot.states import STATE_MAPPING
        self.states = [states] if isinstance(states, str) else states
        self.state_objects = []
        
        for state in self.states:
            if ':' in state:
                group, state_name = state.split(':')
                if group in STATE_MAPPING:
                    state_obj = getattr(STATE_MAPPING[group], state_name, None)
                    if state_obj:
                        self.state_objects.append(state_obj)
    
    async def __call__(
        self,
        event: Union[Message, CallbackQuery],
        state: Optional[str] = None
    ) -> bool:
        if not state:
            return False
        return state in self.state_objects

# Composite filters
class AdminCommand(BaseFilter):
    """Combined filter for admin commands"""
    async def __call__(
        self,
        message: Message,
        user: User,
        state: Optional[str] = None
    ) -> bool:
        is_admin = await IsAdmin()(message)
        is_command = message.content_type == 'text' and message.text.startswith('/')
        return is_admin and is_command

class ModeratorAction(BaseFilter):
    """Combined filter for moderator actions"""
    async def __call__(
        self,
        event: Union[Message, CallbackQuery],
        user: User
    ) -> bool:
        is_moderator = await IsModerator()(event, user)
        is_working_hours = await IsWorkingHours()(event)
        return is_moderator and is_working_hours

# Export all filters
__all__ = [
    'IsAdmin',
    'IsSupport',
    'IsModerator',
    'HasActiveSubscription',
    'RateLimit',
    'HasCompletedRegistration',
    'IsBlocked',
    'HasActiveConsultation',
    'IsWorkingHours',
    'HasPermission',
    'ContentTypeFilter',
    'TextLengthFilter',
    'RegexFilter',
    'LanguageFilter',
    'ChatTypeFilter',
    'StateFilter',
    'AdminCommand',
    'ModeratorAction',
    'UserActivityFilter',
    'PaymentStatusFilter',
    'ConsultationStatusFilter',
    'QuestionCategoryFilter',
    'NotificationFilter'
]

class UserActivityFilter(BaseFilter):
    """Filter users by activity status"""
    
    def __init__(self, days: int = 7):
        self.days = days
    
    async def __call__(self, event: Union[Message, CallbackQuery], user: User) -> bool:
        if not user.last_active:
            return False
            
        time_diff = datetime.utcnow() - user.last_active
        return time_diff.days <= self.days

class PaymentStatusFilter(BaseFilter):
    """Filter by payment status"""
    
    def __init__(self, statuses: Union[str, list]):
        self.statuses = [statuses] if isinstance(statuses, str) else statuses
    
    async def __call__(self, event: Union[Message, CallbackQuery], payment_status: str) -> bool:
        return payment_status in self.statuses

class ConsultationStatusFilter(BaseFilter):
    """Filter by consultation status"""
    
    def __init__(self, statuses: Union[str, list]):
        self.statuses = [statuses] if isinstance(statuses, str) else statuses
    
    async def __call__(
        self,
        event: Union[Message, CallbackQuery],
        consultation_status: str
    ) -> bool:
        return consultation_status in self.statuses

class QuestionCategoryFilter(BaseFilter):
    """Filter questions by category"""
    
    def __init__(self, categories: Union[str, list]):
        self.categories = [categories] if isinstance(categories, str) else categories
    
    async def __call__(
        self,
        event: Union[Message, CallbackQuery],
        question_category: str
    ) -> bool:
        return question_category in self.categories

class NotificationFilter(BaseFilter):
    """Filter by notification settings"""
    
    def __init__(self, notification_type: str):
        self.notification_type = notification_type
    
    async def __call__(self, event: Union[Message, CallbackQuery], user: User) -> bool:
        user_settings = await cache.get(f"notification_settings:{user.id}")
        if not user_settings:
            return True  # Default to allowing notifications
        return user_settings.get(self.notification_type, True)

class UserRoleFilter(BaseFilter):
    """Filter users by role"""
    
    def __init__(self, roles: Union[str, list]):
        self.roles = [roles] if isinstance(roles, str) else roles
    
    async def __call__(self, event: Union[Message, CallbackQuery], user: User) -> bool:
        return any(role in user.roles for role in self.roles)

class UserSubscriptionFilter(BaseFilter):
    """Filter by subscription level"""
    
    def __init__(self, subscription_types: Union[str, list]):
        self.subscription_types = (
            [subscription_types]
            if isinstance(subscription_types, str)
            else subscription_types
        )
    
    async def __call__(self, event: Union[Message, CallbackQuery], user: User) -> bool:
        subscription = await cache.get(f"subscription:{user.id}")
        if not subscription:
            return False
        return subscription.get('type') in self.subscription_types

class MessageFrequencyFilter(BaseFilter):
    """Filter based on message frequency"""
    
    def __init__(self, max_messages: int, time_window: int):
        self.max_messages = max_messages
        self.time_window = time_window
    
    async def __call__(self, message: Message) -> bool:
        user_id = message.from_user.id
        key = f"message_frequency:{user_id}"
        
        # Get message history
        message_times = await cache.get(key) or []
        current_time = datetime.utcnow()
        
        # Filter out old messages
        message_times = [
            t for t in message_times
            if (current_time - datetime.fromisoformat(t)).total_seconds() <= self.time_window
        ]
        
        # Check frequency
        if len(message_times) >= self.max_messages:
            return False
        
        # Add new message time
        message_times.append(current_time.isoformat())
        await cache.set(key, message_times, expire=self.time_window)
        
        return True

class FileTypeFilter(BaseFilter):
    """Filter file uploads by type"""
    
    def __init__(self, allowed_types: Union[str, list]):
        self.allowed_types = [allowed_types] if isinstance(allowed_types, str) else allowed_types
    
    async def __call__(self, message: Message) -> bool:
        if not message.document:
            return False
            
        file_ext = message.document.file_name.split('.')[-1].lower()
        return file_ext in self.allowed_types

class UserVerificationFilter(BaseFilter):
    """Filter by user verification status"""
    
    async def __call__(self, event: Union[Message, CallbackQuery], user: User) -> bool:
        verified = await cache.get(f"verified:{user.id}")
        return bool(verified)

class ChainFilter(BaseFilter):
    """Combine multiple filters with AND logic"""
    
    def __init__(self, filters: list):
        self.filters = filters
    
    async def __call__(
        self,
        event: Union[Message, CallbackQuery],
        **kwargs
    ) -> bool:
        return all(
            await filter_(event, **kwargs)
            for filter_ in self.filters
        )

class AnyFilter(BaseFilter):
    """Combine multiple filters with OR logic"""
    
    def __init__(self, filters: list):
        self.filters = filters
    
    async def __call__(
        self,
        event: Union[Message, CallbackQuery],
        **kwargs
    ) -> bool:
        return any(
            await filter_(event, **kwargs)
            for filter_ in self.filters
        )

class CustomFilter(BaseFilter):
    """Create custom filter with callable"""
    
    def __init__(self, func: callable):
        self.func = func
    
    async def __call__(
        self,
        event: Union[Message, CallbackQuery],
        **kwargs
    ) -> bool:
        return await self.func(event, **kwargs)

# Helper functions
def create_filter_chain(*filters: BaseFilter) -> ChainFilter:
    """Create chain of filters"""
    return ChainFilter(list(filters))

def create_any_filter(*filters: BaseFilter) -> AnyFilter:
    """Create OR combination of filters"""
    return AnyFilter(list(filters))

def create_custom_filter(func: callable) -> CustomFilter:
    """Create custom filter from callable"""
    return CustomFilter(func)

# Common filter combinations
admin_only = create_filter_chain(IsAdmin(), IsWorkingHours())
support_only = create_filter_chain(IsSupport(), IsWorkingHours())
moderator_only = create_filter_chain(IsModerator(), IsWorkingHours())
active_user = create_filter_chain(
    HasCompletedRegistration(),
    UserActivityFilter(days=30),
    ~IsBlocked()
)
premium_user = create_filter_chain(
    active_user,
    HasActiveSubscription()
)
verified_user = create_filter_chain(
    active_user,
    UserVerificationFilter()
)

# Export additional items
__all__.extend([
    'UserRoleFilter',
    'UserSubscriptionFilter',
    'MessageFrequencyFilter',
    'FileTypeFilter',
    'UserVerificationFilter',
    'ChainFilter',
    'AnyFilter',
    'CustomFilter',
    'create_filter_chain',
    'create_any_filter',
    'create_custom_filter',
    'admin_only',
    'support_only',
    'moderator_only',
    'active_user',
    'premium_user',
    'verified_user'
])
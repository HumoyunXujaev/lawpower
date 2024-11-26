from sqlalchemy import (
    Column, String, BigInteger, Boolean, DateTime, 
    Integer, ForeignKey, Enum as SQLEnum, Index,
    Table, UniqueConstraint, Text, Float
)
from sqlalchemy.orm import relationship
from sqlalchemy.dialects.postgresql import ARRAY, JSONB
from enum import Enum
from datetime import datetime

from telegram_bot.models.base import BaseModel, SoftDeleteMixin, AuditMixin, MetadataMixin

class UserRole(str, Enum):
    USER = 'USER'
    ADMIN = 'ADMIN'
    SUPPORT = 'SUPPORT'
    MODERATOR = 'MODERATOR'

class UserStatus(str, Enum):
    ACTIVE = 'ACTIVE'
    BLOCKED = 'BLOCKED'
    SUSPENDED = 'SUSPENDED'
    DELETED = 'DELETED'

class User(BaseModel, SoftDeleteMixin, AuditMixin, MetadataMixin):
    """Enhanced user model with complete profile and security"""
    __tablename__ = 'users'

    # Core fields
    telegram_id = Column(BigInteger, unique=True, nullable=False)
    username = Column(String)
    full_name = Column(String)
    phone_number = Column(String)
    email = Column(String)
    language = Column(String(2), default='uz', nullable=False)
    
    # Security and authentication
    password_hash = Column(String)
    is_active = Column(Boolean, default=True, nullable=False)
    is_verified = Column(Boolean, default=False, nullable=False)
    is_blocked = Column(Boolean, default=False, nullable=False)
    block_reason = Column(String)
    
    # Status and activity
    status = Column(SQLEnum(UserStatus), default=UserStatus.ACTIVE, nullable=False)
    last_active = Column(DateTime(timezone=True))
    last_login = Column(DateTime(timezone=True))
    
    # Roles and permissions
    roles = Column(ARRAY(String), default=['USER'], nullable=False)
    permissions = Column(ARRAY(String), default=[])
    
    # Settings and preferences
    settings = Column(JSONB, default={}, nullable=False)
    notification_preferences = Column(JSONB, default={
        'questions': True,
        'consultations': True,
        'marketing': True,
        'support': True
    }, nullable=False)
    
    # Statistics and metrics
    metrics = Column(JSONB, default={
        'questions_asked': 0,
        'consultations_completed': 0,
        'total_spent': 0,
        'avg_rating': 0
    }, nullable=False)

    # Address and contact info
    region = Column(String)
    city = Column(String)
    address = Column(Text)
    additional_contacts = Column(JSONB, default={})

    # Audit fields
    registration_ip = Column(String)
    registration_device = Column(String)
    last_ip = Column(String)
    last_device = Column(String)
    login_attempts = Column(Integer, default=0)
    
    # Social network links
    social_networks = Column(JSONB, default={})
    
    # Analytics data
    analytics = Column(JSONB, default={
        'visits': [],
        'actions': [],
        'preferences': {}
    })

    # Security settings
    two_factor_enabled = Column(Boolean, default=False)
    two_factor_secret = Column(String)
    backup_codes = Column(ARRAY(String), default=[])

    # Relationships
    questions = relationship('Question', back_populates='user', lazy='dynamic')
    answers = relationship('Answer', back_populates='user', lazy='dynamic')
    consultations = relationship('Consultation', back_populates='user', lazy='dynamic')
    payments = relationship('Payment', back_populates='user', lazy='dynamic')
    notifications = relationship('UserNotification', back_populates='user', lazy='dynamic')
    events = relationship('UserEvent', back_populates='user', lazy='dynamic')
    feedback = relationship('ConsultationFeedback', back_populates='user', lazy='dynamic')
    faq_feedback = relationship('FAQFeedback', back_populates='user', lazy='dynamic')

    # Indexes
    __table_args__ = (
        Index('ix_users_telegram_id', telegram_id),
        Index('ix_users_username', username),
        Index('ix_users_status', status),
        Index('ix_users_language', language),
        Index('ix_users_roles', roles, postgresql_using='gin'),
        Index('ix_users_last_active', last_active),
        Index('ix_users_region', region),
        Index('ix_users_is_blocked', is_blocked),
        UniqueConstraint('telegram_id', name='uq_users_telegram_id'),
    )

    @property
    def is_admin(self) -> bool:
        """Check if user is admin"""
        return 'ADMIN' in self.roles

    @property
    def is_support(self) -> bool:
        """Check if user is support"""
        return 'SUPPORT' in self.roles

    def has_role(self, role: str) -> bool:
        """Check if user has role"""
        return role in self.roles

    def add_role(self, role: str) -> None:
        """Add role to user"""
        if role not in self.roles:
            self.roles = self.roles + [role]

    def remove_role(self, role: str) -> None:
        """Remove role from user"""
        self.roles = [r for r in self.roles if r != role]

    def has_permission(self, permission: str) -> bool:
        """Check if user has permission"""
        return permission in (self.permissions or [])

    def update_last_active(self) -> None:
        """Update last active timestamp"""
        self.last_active = datetime.utcnow()

    def increment_login_attempts(self) -> None:
        """Increment failed login attempts"""
        self.login_attempts = (self.login_attempts or 0) + 1

    def reset_login_attempts(self) -> None:
        """Reset failed login attempts"""
        self.login_attempts = 0

    def update_metrics(self, metric: str, value: float = 1) -> None:
        """Update user metrics"""
        if self.metrics is None:
            self.metrics = {}
        if metric not in self.metrics:
            self.metrics[metric] = 0
        self.metrics[metric] += value

    def get_notification_settings(self, notification_type: str) -> bool:
        """Get notification preference"""
        return self.notification_preferences.get(notification_type, True)

    def update_notification_settings(self, notification_type: str, enabled: bool) -> None:
        """Update notification preference"""
        self.notification_preferences[notification_type] = enabled

    def track_visit(self, ip: str = None, device: str = None) -> None:
        """Track user visit"""
        visit = {
            'timestamp': datetime.utcnow().isoformat(),
            'ip': ip,
            'device': device
        }
        if not self.analytics.get('visits'):
            self.analytics['visits'] = []
        self.analytics['visits'].append(visit)

    def track_action(self, action_type: str, details: dict = None) -> None:
        """Track user action"""
        action = {
            'type': action_type,
            'timestamp': datetime.utcnow().isoformat(),
            'details': details or {}
        }
        if not self.analytics.get('actions'):
            self.analytics['actions'] = []
        self.analytics['actions'].append(action)

    def get_stats(self) -> dict:
        """Get user statistics"""
        return {
            'questions_count': self.metrics.get('questions_asked', 0),
            'consultations_count': self.metrics.get('consultations_completed', 0),
            'total_spent': self.metrics.get('total_spent', 0),
            'avg_rating': self.metrics.get('avg_rating', 0),
            'last_active': self.last_active,
            'member_since': self.created_at
        }

class UserEvent(BaseModel):
    """User activity event tracking"""
    __tablename__ = 'user_events'

    user_id = Column(Integer, ForeignKey('users.id', ondelete='CASCADE'), nullable=False)
    event_type = Column(String, nullable=False)
    event_data = Column(JSONB, default={})
    ip_address = Column(String)
    user_agent = Column(String)
    session_id = Column(String)
    platform = Column(String)
    device_info = Column(JSONB, default={})
    location_data = Column(JSONB, default={})
    event_metadata = Column(JSONB, default={})
    is_processed = Column(Boolean, default=False)
    processed_at = Column(DateTime(timezone=True))
    
    # Analytics fields
    duration = Column(Float)  # For tracking event duration if applicable
    performance_metrics = Column(JSONB, default={})  # For tracking performance data
    error_data = Column(JSONB, default={})  # For tracking any errors during the event

    # Relationships
    user = relationship('User', back_populates='events')

    # Indexes
    __table_args__ = (
        Index('ix_user_events_user_id', user_id),
        Index('ix_user_events_event_type', event_type),
        Index('ix_user_events_created_at', 'created_at'),
        Index('ix_user_events_is_processed', is_processed),
    )

    def mark_processed(self) -> None:
        """Mark event as processed"""
        self.is_processed = True
        self.processed_at = datetime.utcnow()

    def add_performance_metric(self, metric: str, value: float) -> None:
        """Add performance metric"""
        if not self.performance_metrics:
            self.performance_metrics = {}
        self.performance_metrics[metric] = value

    def add_error(self, error: str, details: dict = None) -> None:
        """Add error details"""
        if not self.error_data:
            self.error_data = {}
        self.error_data['error'] = error
        if details:
            self.error_data['details'] = details
        self.error_data['timestamp'] = datetime.utcnow().isoformat()

class UserNotification(BaseModel):
    """User notification model"""
    __tablename__ = 'user_notifications'

    user_id = Column(Integer, ForeignKey('users.id', ondelete='CASCADE'), nullable=False)
    title = Column(String, nullable=False)
    message = Column(Text, nullable=False)
    notification_type = Column(String, nullable=False)
    priority = Column(String, default='normal')
    is_read = Column(Boolean, default=False)
    read_at = Column(DateTime(timezone=True))
    scheduled_for = Column(DateTime(timezone=True))
    sent_at = Column(DateTime(timezone=True))
    metadata = Column(JSONB, default={})
    
    # Additional fields
    category = Column(String)  # For categorizing notifications
    expiry_date = Column(DateTime(timezone=True))  # When notification expires
    action_url = Column(String)  # URL for notification action
    action_data = Column(JSONB, default={})  # Additional action data
    image_url = Column(String)  # URL for notification image
    seen_at = Column(DateTime(timezone=True))  # When notification was seen
    interaction_count = Column(Integer, default=0)  # Number of times user interacted
    is_archived = Column(Boolean, default=False)  # If notification is archived
    archived_at = Column(DateTime(timezone=True))  # When notification was archived
    campaign_id = Column(String)  # For tracking marketing campaigns
    
    # Relationships
    user = relationship('User', back_populates='notifications')

    # Indexes
    __table_args__ = (
        Index('ix_user_notifications_user_id', user_id),
        Index('ix_user_notifications_type', notification_type),
        Index('ix_user_notifications_is_read', is_read),
        Index('ix_user_notifications_scheduled_for', scheduled_for),
        Index('ix_user_notifications_sent_at', sent_at),
        Index('ix_user_notifications_campaign_id', campaign_id),
    )

    def mark_as_read(self) -> None:
        """Mark notification as read"""
        if not self.is_read:
            self.is_read = True
            self.read_at = datetime.utcnow()

    def mark_as_seen(self) -> None:
        """Mark notification as seen"""
        if not self.seen_at:
            self.seen_at = datetime.utcnow()

    def mark_as_sent(self) -> None:
        """Mark notification as sent"""
        self.sent_at = datetime.utcnow()

    def increment_interaction(self) -> None:
        """Increment interaction count"""
        self.interaction_count += 1

    def archive(self) -> None:
        """Archive notification"""
        if not self.is_archived:
            self.is_archived = True
            self.archived_at = datetime.utcnow()

    def is_expired(self) -> bool:
        """Check if notification is expired"""
        if self.expiry_date:
            return datetime.utcnow() > self.expiry_date
        return False

    def should_send(self) -> bool:
        """Check if notification should be sent"""
        return (
            not self.sent_at and
            not self.is_archived and
            not self.is_expired() and
            (not self.scheduled_for or datetime.utcnow() >= self.scheduled_for)
        )
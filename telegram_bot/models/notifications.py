from sqlalchemy import Column, String, Integer, Boolean, JSON, ForeignKey, Enum as SQLEnum, DateTime, Text
from sqlalchemy.orm import relationship
from sqlalchemy.dialects.postgresql import JSONB
from enum import Enum as PyEnum
from datetime import datetime

from telegram_bot.models.base import BaseModel, TimestampMixin, MetadataMixin

class NotificationType(str, PyEnum):
    SYSTEM = 'system'
    QUESTION = 'question'
    CONSULTATION = 'consultation'
    PAYMENT = 'payment'
    MARKETING = 'marketing'
    REMINDER = 'reminder'
    SUPPORT = 'support'

class NotificationStatus(str, PyEnum):
    PENDING = 'pending'
    SENT = 'sent'
    DELIVERED = 'delivered'
    READ = 'read'
    FAILED = 'failed'
    CANCELLED = 'cancelled'

class NotificationPriority(str, PyEnum):
    LOW = 'low'
    MEDIUM = 'medium'
    HIGH = 'high'
    URGENT = 'urgent'

class Notification(BaseModel, TimestampMixin, MetadataMixin):
    """User notification model with templating support"""
    __tablename__ = 'notifications'
    
    user_id = Column(Integer, ForeignKey('users.id', ondelete='CASCADE'), nullable=False)
    template_id = Column(Integer, ForeignKey('notification_templates.id'), nullable=True)
    
    type = Column(SQLEnum(NotificationType), nullable=False)
    priority = Column(SQLEnum(NotificationPriority), default=NotificationPriority.MEDIUM)
    status = Column(SQLEnum(NotificationStatus), default=NotificationStatus.PENDING)
    
    title = Column(String, nullable=False)
    message = Column(Text, nullable=False)
    
    scheduled_for = Column(DateTime(timezone=True), nullable=True)
    sent_at = Column(DateTime(timezone=True), nullable=True)
    delivered_at = Column(DateTime(timezone=True), nullable=True)
    read_at = Column(DateTime(timezone=True), nullable=True)
    
    error_message = Column(String, nullable=True)
    retry_count = Column(Integer, default=0)
    
    data = Column(JSONB, default={}, nullable=False)
    
    # Relationships
    user = relationship('User', back_populates='notifications')
    template = relationship('NotificationTemplate', back_populates='notifications')
    
    def mark_sent(self) -> None:
        """Mark notification as sent"""
        self.status = NotificationStatus.SENT
        self.sent_at = datetime.utcnow()
        
    def mark_delivered(self) -> None:
        """Mark notification as delivered"""
        self.status = NotificationStatus.DELIVERED
        self.delivered_at = datetime.utcnow()
        
    def mark_read(self) -> None:
        """Mark notification as read"""
        self.status = NotificationStatus.READ
        self.read_at = datetime.utcnow()
        
    def mark_failed(self, error: str) -> None:
        """Mark notification as failed"""
        self.status = NotificationStatus.FAILED
        self.error_message = error
        self.retry_count += 1

class NotificationTemplate(BaseModel, TimestampMixin):
    """Notification template model with localization support"""
    __tablename__ = 'notification_templates'
    
    name = Column(String, unique=True, nullable=False)
    description = Column(Text)
    
    title_template_uz = Column(Text, nullable=False)
    title_template_ru = Column(Text, nullable=False)
    
    message_template_uz = Column(Text, nullable=False)
    message_template_ru = Column(Text, nullable=False)
    
    type = Column(SQLEnum(NotificationType), nullable=False)
    priority = Column(SQLEnum(NotificationPriority), default=NotificationPriority.MEDIUM)
    
    is_active = Column(Boolean, default=True)
    metadata = Column(JSONB, default={})
    
    # Relationships
    notifications = relationship('Notification', back_populates='template')
    
    def render(self, language: str, data: dict) -> tuple[str, str]:
        """Render notification title and message from template"""
        title_template = getattr(self, f'title_template_{language}')
        message_template = getattr(self, f'message_template_{language}')
        
        try:
            title = title_template.format(**data)
            message = message_template.format(**data)
            return title, message
        except KeyError as e:
            raise ValueError(f"Missing template data key: {e}")

# Export models
__all__ = [
    'Notification',
    'NotificationTemplate',
    'NotificationType',
    'NotificationStatus',
    'NotificationPriority'
]
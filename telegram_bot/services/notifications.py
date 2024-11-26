from typing import Optional, List, Dict, Any
from datetime import datetime, timedelta
import logging
from sqlalchemy import select, func, or_, and_
from sqlalchemy.ext.asyncio import AsyncSession

from telegram_bot.models.notifications import NotificationType, NotificationPriority, NotificationStatus
from telegram_bot.models import User, UserNotification
from telegram_bot.core.cache import cache_service as cache
from telegram_bot.core.errors import ValidationError
from telegram_bot.services.base import BaseService
import asyncio
logger = logging.getLogger(__name__)

class NotificationService(BaseService):
    """Enhanced notification service with queuing and scheduling"""
    
    def __init__(self, session: AsyncSession):
        super().__init__(UserNotification, session)
        self.cache = cache
        
        # Notification templates cache key
        self.TEMPLATES_KEY = "notification:templates"
        
        # Notification rate limits (per user per hour)
        self.RATE_LIMITS = {
            NotificationType.MARKETING: 2,
            NotificationType.SYSTEM_UPDATE: 5,
            NotificationType.SUPPORT: 10
        }
    
    async def create_notification(
        self,
        user_id: int,
        notification_type: NotificationType,
        title: str,
        message: str,
        priority: NotificationPriority = NotificationPriority.MEDIUM,
        schedule_time: Optional[datetime] = None,
        metadata: Dict = None
    ) -> Optional[UserNotification]:
        """Create and optionally schedule notification"""
        try:
            # Check rate limits
            if not await self._check_rate_limit(user_id, notification_type):
                logger.warning(f"Rate limit exceeded for user {user_id} and type {notification_type}")
                return None
            
            # Create notification record
            notification = await self.create(
                user_id=user_id,
                type=notification_type,
                priority=priority,
                title=title,
                message=message,
                status=NotificationStatus.PENDING,
                schedule_time=schedule_time,
                metadata=metadata or {
                    'created_at': datetime.utcnow().isoformat()
                }
            )
            
            # If no schedule time or scheduled for now, send immediately
            if not schedule_time or schedule_time <= datetime.utcnow():
                await self._send_notification(notification)
            else:
                # Schedule notification
                await self._schedule_notification(notification)
            
            return notification
            
        except Exception as e:
            logger.error(f"Error creating notification: {e}")
            return None
    
    async def create_bulk_notifications(
        self,
        user_ids: List[int],
        notification_type: NotificationType,
        title: str,
        message: str,
        priority: NotificationPriority = NotificationPriority.MEDIUM,
        metadata: Dict = None
    ) -> int:
        """Create notifications for multiple users"""
        try:
            sent_count = 0
            
            for user_id in user_ids:
                notification = await self.create_notification(
                    user_id=user_id,
                    notification_type=notification_type,
                    title=title,
                    message=message,
                    priority=priority,
                    metadata=metadata
                )
                if notification:
                    sent_count += 1
                
                # Add small delay to prevent overload
                await asyncio.sleep(0.1)
            
            return sent_count
            
        except Exception as e:
            logger.error(f"Error creating bulk notifications: {e}")
            return 0

    async def _send_notification(self, notification: UserNotification) -> bool:
        """Send notification via appropriate channel"""
        try:
            # Get user
            user = await self.session.get(User, notification.user_id)
            if not user:
                logger.error(f"User not found for notification {notification.id}")
                return False
            
            # Check user preferences
            if not await self._check_user_preferences(user, notification.type):
                logger.info(f"Notification {notification.id} skipped due to user preferences")
                return False
            
            # Send via Telegram
            from telegram_bot.bot import bot
            
            # Format message
            text = f"*{notification.title}*\n\n{notification.message}"
            
            # Add buttons if specified in metadata
            keyboard = None
            if notification.metadata.get('buttons'):
                from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
                keyboard = InlineKeyboardMarkup(inline_keyboard=[
                    [InlineKeyboardButton(
                        text=btn['text'],
                        callback_data=btn['callback_data']
                    ) for btn in notification.metadata['buttons']]
                ])
            
            # Send message
            try:
                await bot.send_message(
                    user.telegram_id,
                    text,
                    parse_mode="Markdown",
                    reply_markup=keyboard
                )
                
                # Update notification status
                notification.status = NotificationStatus.DELIVERED
                notification.metadata['delivered_at'] = datetime.utcnow().isoformat()
                await self.session.commit()
                
                # Update cache
                await self._update_notification_cache(notification)
                
                return True
                
            except Exception as e:
                logger.error(f"Error sending notification {notification.id}: {e}")
                notification.status = NotificationStatus.FAILED
                notification.metadata['error'] = str(e)
                await self.session.commit()
                return False
            
        except Exception as e:
            logger.error(f"Error in _send_notification: {e}")
            return False

    async def _schedule_notification(self, notification: UserNotification) -> bool:
        """Schedule notification for later delivery"""
        try:
            if not notification.schedule_time:
                return False
            
            # Calculate delay
            delay = (notification.schedule_time - datetime.utcnow()).total_seconds()
            if delay <= 0:
                return await self._send_notification(notification)
            
            # Add to schedule queue
            await self.cache.set(
                f"scheduled_notification:{notification.id}",
                notification.to_dict(),
                timeout=int(delay)
            )
            
            return True
            
        except Exception as e:
            logger.error(f"Error scheduling notification: {e}")
            return False

    async def mark_as_read(
        self,
        notification_id: int,
        user_id: int
    ) -> bool:
        """Mark notification as read"""
        try:
            notification = await self.get(notification_id)
            if not notification or notification.user_id != user_id:
                return False
            
            notification.status = NotificationStatus.READ
            notification.metadata['read_at'] = datetime.utcnow().isoformat()
            await self.session.commit()
            
            # Update cache
            await self._update_notification_cache(notification)
            
            return True
            
        except Exception as e:
            logger.error(f"Error marking notification as read: {e}")
            return False

    async def get_user_notifications(
        self,
        user_id: int,
        types: Optional[List[NotificationType]] = None,
        status: Optional[NotificationStatus] = None,
        limit: int = 50,
        offset: int = 0
    ) -> List[UserNotification]:
        """Get user notifications with filtering"""
        try:
            query = select(UserNotification).filter(
                UserNotification.user_id == user_id
            )
            
            if types:
                query = query.filter(UserNotification.type.in_(types))
            
            if status:
                query = query.filter(UserNotification.status == status)
            
            query = query.order_by(
                UserNotification.created_at.desc()
            ).offset(offset).limit(limit)
            
            result = await self.session.execute(query)
            return list(result.scalars().all())
            
        except Exception as e:
            logger.error(f"Error getting user notifications: {e}")
            return []

    async def get_unread_count(self, user_id: int) -> int:
        """Get count of unread notifications"""
        try:
            cache_key = f"unread_notifications:{user_id}"
            
            # Try cache
            cached = await self.cache.get(cache_key)
            if cached is not None:
                return cached
            
            # Get from database
            result = await self.session.execute(
                select(func.count())
                .select_from(UserNotification)
                .filter(
                    UserNotification.user_id == user_id,
                    UserNotification.status.in_([
                        NotificationStatus.PENDING,
                        NotificationStatus.DELIVERED
                    ])
                )
            )
            count = result.scalar() or 0
            
            # Cache result
            await self.cache.set(cache_key, count, timeout=300)
            
            return count
            
        except Exception as e:
            logger.error(f"Error getting unread count: {e}")
            return 0

    async def delete_old_notifications(self, days: int = 30) -> int:
        """Delete old notifications"""
        try:
            cutoff = datetime.utcnow() - timedelta(days=days)
            
            result = await self.session.execute(
                select(UserNotification)
                .filter(
                    UserNotification.created_at < cutoff,
                    UserNotification.status.in_([
                        NotificationStatus.DELIVERED,
                        NotificationStatus.READ,
                        NotificationStatus.FAILED
                    ])
                )
            )
            notifications = result.scalars().all()
            
            for notification in notifications:
                await self.session.delete(notification)
            
            await self.session.commit()
            
            return len(notifications)
            
        except Exception as e:
            logger.error(f"Error deleting old notifications: {e}")
            return 0

    async def _check_rate_limit(
        self,
        user_id: int,
        notification_type: NotificationType
    ) -> bool:
        """Check if user has exceeded rate limit"""
        if notification_type not in self.RATE_LIMITS:
            return True
            
        limit = self.RATE_LIMITS[notification_type]
        cache_key = f"notification_rate:{user_id}:{notification_type}"
        
        count = await self.cache.get(cache_key) or 0
        if count >= limit:
            return False
            
        await self.cache.increment(cache_key)
        if count == 0:
            await self.cache.expire(cache_key, 3600)  # 1 hour
            
        return True

    async def _check_user_preferences(
        self,
        user: User,
        notification_type: NotificationType
    ) -> bool:
        """Check if user has enabled this notification type"""
        preferences = user.notification_preferences or {}
        return preferences.get(notification_type, True)

    async def _update_notification_cache(self, notification: UserNotification):
        """Update notification in cache"""
        # Update unread count
        if notification.status == NotificationStatus.READ:
            cache_key = f"unread_notifications:{notification.user_id}"
            count = await self.cache.get(cache_key)
            if count is not None and count > 0:
                await self.cache.set(cache_key, count - 1)

# Create service instance
notification_service = NotificationService(None)  # Session will be injected

async def setup_notification_scheduler():
    """Setup background task for processing scheduled notifications"""
    while True:
        try:
            # Get all scheduled notifications
            now = datetime.utcnow()
            pattern = "scheduled_notification:*"
            
            scheduled = await cache.get_by_pattern(pattern)
            
            for key, notification_data in scheduled.items():
                notification_id = int(key.split(":")[-1])
                
                # Get notification
                notification = await notification_service.get(notification_id)
                if not notification:
                    await cache.delete(key)
                    continue
                
                # Check if it's time to send
                if notification.schedule_time <= now:
                    await notification_service._send_notification(notification)
                    await cache.delete(key)
            
            # Sleep for a short interval
            await asyncio.sleep(60)  # Check every minute
            
        except Exception as e:
            logger.error(f"Error in notification scheduler: {e}")
            await asyncio.sleep(60)

__all__ = ['NotificationService', 'notification_service', 'setup_notification_scheduler']
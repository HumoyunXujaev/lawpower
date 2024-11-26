from typing import Optional, List, Dict, Any
from datetime import datetime, timedelta
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from telegram_bot.models import User, UserEvent, UserNotification
from telegram_bot.services.base import BaseService
from telegram_bot.core.constants import UserRole
from telegram_bot.core.security import hash_password
from telegram_bot.models import (
    User, Question, Answer, Consultation, ConsultationStatus,
)
from telegram_bot.services.base import update
class UserService(BaseService[User]):
    """User service"""
    
    async def get_by_telegram_id(
        self,
        telegram_id: int
    ) -> Optional[User]:
        """Get user by telegram ID"""
        cache_key = f"user_tg:{telegram_id}"
        
        # Try to get from cache
        cached = await self.cache.get(cache_key)
        if cached:
            return User.from_dict(cached)
        
        # Get from database
        result = await self.session.execute(
            select(User).filter(User.telegram_id == telegram_id)
        )
        user = result.scalar_one_or_none()
        
        # Cache result
        if user:
            await self.cache.set(cache_key, user.to_dict())
        
        return user
    
    async def create_user(
        self,
        telegram_id: int,
        username: Optional[str] = None,
        full_name: Optional[str] = None,
        language: str = 'uz'
    ) -> User:
        """Create new user"""
        user = await self.create(
            telegram_id=telegram_id,
            username=username,
            full_name=full_name,
            language=language
        )
        
        # Cache user
        await self.cache.set(
            f"user_tg:{telegram_id}",
            user.to_dict()
        )
        
        return user
    
    async def update_user_language(
        self,
        user_id: int,
        language: str
    ) -> Optional[User]:
        """Update user language"""
        user = await self.update(
            user_id,
            language=language
        )
        
        if user:
            # Update cache
            await self.cache.delete(f"user_tg:{user.telegram_id}")
        
        return user
    
    async def get_active_users(
        self,
        days: int = 7
    ) -> List[User]:
        """Get active users for last N days"""
        since = datetime.utcnow() - timedelta(days=days)
        
        result = await self.session.execute(
            select(User).filter(
                User.last_active >= since,
                User.is_blocked == False
            )
        )
        return list(result.scalars().all())
    
    async def get_user_stats(
        self,
        user_id: int
    ) -> Dict[str, Any]:
        """Get user statistics"""

        user = await self.get(user_id)
        if not user:
            return {}
    
        # Get questions count
        questions_count = await self.session.scalar(
            select(func.count(Question.id)).filter(
                Question.user_id == user_id
            )
        )
        
        # Get consultations count
        consultations_count = await self.session.scalar(
            select(func.count(Consultation.id)).filter(
                Consultation.user_id == user_id
            )
        )
        
        # Get total spent amount
        total_spent = await self.session.scalar(
            select(func.sum(Consultation.amount)).filter(
                Consultation.user_id == user_id,
                Consultation.status == ConsultationStatus.COMPLETED
            )
        )
        
        return {
            'questions_count': questions_count,
            'consultations_count': consultations_count,
            'total_spent': float(total_spent or 0),
            'last_active': user.last_active,
            'join_date': user.created_at
        }
    
    async def track_user_activity(
        self,
        user_id: int,
        activity_type: str,
        metadata: Dict = None
    ) -> None:
        """Track user activity"""
        # Update last active
        await self.update(
            user_id,
            last_active=datetime.utcnow()
        )
        
        # Create activity event
        event = UserEvent(
            user_id=user_id,
            event_type=activity_type,
            event_data=metadata or {}
        )
        self.session.add(event)
        await self.session.commit()
    
    async def create_notification(
        self,
        user_id: int,
        title: str,
        message: str,
        notification_type: str,
        metadata: Dict = None
    ) -> UserNotification:
        """Create user notification"""
        notification = UserNotification(
            user_id=user_id,
            title=title,
            message=message,
            type=notification_type,
            metadata=metadata or {}
        )
        self.session.add(notification)
        await self.session.commit()
        
        # Invalidate notifications cache
        await self.cache.delete(f"user_notifications:{user_id}")
        
        return notification
    
    async def get_unread_notifications(
        self,
        user_id: int
    ) -> List[UserNotification]:
        """Get unread notifications"""
        cache_key = f"user_notifications:{user_id}"
        
        # Try from cache
        cached = await self.cache.get(cache_key)
        if cached:
            return [UserNotification.from_dict(n) for n in cached]
        
        # Get from database
        result = await self.session.execute(
            select(UserNotification)
            .filter(
                UserNotification.user_id == user_id,
                UserNotification.is_read == False
            )
            .order_by(UserNotification.created_at.desc())
        )
        notifications = list(result.scalars().all())
        
        # Cache result
        await self.cache.set(
            cache_key,
            [n.to_dict() for n in notifications]
        )
        
        return notifications
    
    async def mark_notifications_read(
        self,
        user_id: int,
        notification_ids: List[int] = None
    ) -> None:
        """Mark notifications as read"""
        query = update(UserNotification).where(
            UserNotification.user_id == user_id,
            UserNotification.is_read == False
        )
        
        if notification_ids:
            query = query.where(
                UserNotification.id.in_(notification_ids)
            )
            
        await self.session.execute(
            query.values(is_read=True)
        )
        await self.session.commit()
        
        # Invalidate cache
        await self.cache.delete(f"user_notifications:{user_id}")
    
    async def get_user_roles(
        self,
        user_id: int
    ) -> List[UserRole]:
        """Get user roles"""
        user = await self.get(user_id)
        return user.roles if user else []
    
    async def add_user_role(
        self,
        user_id: int,
        role: UserRole
    ) -> bool:
        """Add role to user"""
        user = await self.get(user_id)
        if not user:
            return False
            
        user.add_role(role)
        await self.session.commit()
        
        # Invalidate cache
        await self.cache.delete(f"user_tg:{user.telegram_id}")
        
        return True
    
    async def remove_user_role(
        self,
        user_id: int,
        role: UserRole
    ) -> bool:
        """Remove role from user"""
        user = await self.get(user_id)
        if not user:
            return False
            
        user.remove_role(role)
        await self.session.commit()
        
        # Invalidate cache
        await self.cache.delete(f"user_tg:{user.telegram_id}")
        
        return True
    
    async def get_admin_users(self) -> List[User]:
        """Get all admin users"""
        result = await self.session.execute(
            select(User).filter(
                User.roles.contains([UserRole.ADMIN])
            )
        )
        return list(result.scalars().all())
    
    async def update_user_settings(
        self,
        user_id: int,
        settings: Dict
    ) -> Optional[User]:
        """Update user settings"""
        user = await self.get(user_id)
        if not user:
            return None
            
        user.update_settings(settings)
        await self.session.commit()
        
        # Invalidate cache
        await self.cache.delete(f"user_tg:{user.telegram_id}")
        
        return user
    
    async def get_user_activity(
        self,
        user_id: int,
        days: int = 30
    ) -> List[Dict]:
        """Get user activity history"""
        since = datetime.utcnow() - timedelta(days=days)
        
        result = await self.session.execute(
            select(UserEvent)
            .filter(
                UserEvent.user_id == user_id,
                UserEvent.created_at >= since
            )
            .order_by(UserEvent.created_at.desc())
        )
        events = result.scalars().all()
        
        return [
            {
                'type': event.event_type,
                'data': event.event_data,
                'created_at': event.created_at.isoformat()
            }
            for event in events
        ]
    
    async def get_user_metrics(
        self,
        user_id: int
    ) -> Dict[str, Any]:
        """Get user metrics"""
        # Get questions metrics
        questions_result = await self.session.execute(
            select(
                func.count(Question.id).label('total'),
                func.count(Question.id)
                .filter(Question.is_answered == True)
                .label('answered')
            )
            .filter(Question.user_id == user_id)
        )
        questions_metrics = questions_result.first()
        
        # Get consultations metrics
        consultations_result = await self.session.execute(
            select(
                func.count(Consultation.id).label('total'),
                func.count(Consultation.id)
                .filter(Consultation.status == ConsultationStatus.COMPLETED)
                .label('completed'),
                func.sum(Consultation.amount)
                .filter(Consultation.status == ConsultationStatus.COMPLETED)
                .label('spent')
            )
            .filter(Consultation.user_id == user_id)
        )
        consultations_metrics = consultations_result.first()
        
        return {
            'questions': {
                'total': questions_metrics.total,
                'answered': questions_metrics.answered,
                'unanswered': questions_metrics.total - questions_metrics.answered
            },
            'consultations': {
                'total': consultations_metrics.total,
                'completed': consultations_metrics.completed,
                'spent': float(consultations_metrics.spent or 0)
            }
        }
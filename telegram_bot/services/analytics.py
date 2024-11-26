from typing import Dict, Any, List, Optional
from datetime import datetime, timedelta
from sqlalchemy import select, func, case, and_, or_
import logging
import json
from telegram_bot.models import (
    User, Question, Answer, Consultation, Payment,
    ConsultationStatus, PaymentStatus, UserEvent
)
from telegram_bot.core.cache import cache_service as cache

logger = logging.getLogger(__name__)

class AnalyticsService:
    """Enhanced analytics service for comprehensive data analysis"""
    
    def __init__(self, session):
        self.session = session
        self.cache = cache
        
    async def get_dashboard_stats(self) -> Dict[str, Any]:
        """Get comprehensive dashboard statistics"""
        try:
            cache_key = "dashboard_stats"
            cached = await self.cache.get(cache_key)
            if cached:
                return cached
                
            # Get time ranges
            now = datetime.utcnow()
            today = now.replace(hour=0, minute=0, second=0, microsecond=0)
            week_ago = now - timedelta(days=7)
            month_ago = now - timedelta(days=30)
            
            # Get user stats
            users_stats = await self._get_users_stats(week_ago, month_ago)
            
            # Get questions stats
            questions_stats = await self._get_questions_stats(week_ago, month_ago)
            
            # Get consultations stats
            consultations_stats = await self._get_consultations_stats(week_ago, month_ago)
            
            # Get revenue stats
            revenue_stats = await self._get_revenue_stats(today, week_ago, month_ago)
            
            # Get system health metrics
            health_metrics = await self._get_system_health()
            
            stats = {
                'users': users_stats,
                'questions': questions_stats,
                'consultations': consultations_stats,
                'revenue': revenue_stats,
                'system_health': health_metrics,
                'updated_at': now.isoformat()
            }
            
            # Cache for 5 minutes
            await self.cache.set(cache_key, stats, timeout=300)
            
            return stats
            
        except Exception as e:
            logger.error(f"Error getting dashboard stats: {e}")
            return {}

    async def _get_users_stats(
        self,
        week_ago: datetime,
        month_ago: datetime
    ) -> Dict[str, Any]:
        """Get detailed user statistics"""
        try:
            result = await self.session.execute(
                select(
                    func.count(User.id).label('total'),
                    func.count(User.id)
                    .filter(User.created_at >= week_ago)
                    .label('new_week'),
                    func.count(User.id)
                    .filter(User.created_at >= month_ago)
                    .label('new_month'),
                    func.count(User.id)
                    .filter(User.is_blocked == False)
                    .label('active'),
                    func.count(User.id)
                    .filter(User.last_active >= week_ago)
                    .label('active_week'),
                    func.count(User.id)
                    .filter(User.language == 'uz')
                    .label('uz_users'),
                    func.count(User.id)
                    .filter(User.language == 'ru')
                    .label('ru_users')
                )
            )
            stats = result.mappings().first()
            
            # Calculate growth rates
            total = stats['total'] or 0
            new_week = stats['new_week'] or 0
            new_month = stats['new_month'] or 0
            
            week_growth = (new_week / (total - new_week) * 100) if total > new_week else 0
            month_growth = (new_month / (total - new_month) * 100) if total > new_month else 0
            
            return {
                'total_users': total,
                'new_users_week': new_week,
                'new_users_month': new_month,
                'active_users': stats['active'],
                'active_users_week': stats['active_week'],
                'growth_rate_week': round(week_growth, 2),
                'growth_rate_month': round(month_growth, 2),
                'languages': {
                    'uz': stats['uz_users'],
                    'ru': stats['ru_users']
                }
            }
            
        except Exception as e:
            logger.error(f"Error getting user stats: {e}")
            return {}

    async def _get_questions_stats(
        self,
        week_ago: datetime,
        month_ago: datetime
    ) -> Dict[str, Any]:
        """Get detailed question statistics"""
        try:
            result = await self.session.execute(
                select(
                    func.count(Question.id).label('total'),
                    func.count(Question.id)
                    .filter(Question.created_at >= week_ago)
                    .label('new_week'),
                    func.count(Question.id)
                    .filter(~Question.answers.any())
                    .label('unanswered'),
                    func.count(Question.id)
                    .filter(Question.answers.any(Answer.is_auto == True))
                    .label('auto_answered'),
                    func.avg(Answer.rating)
                    .label('avg_rating')
                )
                .outerjoin(Answer)
            )
            stats = result.mappings().first()
            
            # Get category distribution
            categories_result = await self.session.execute(
                select(
                    Question.category,
                    func.count(Question.id).label('count')
                )
                .filter(Question.category.isnot(None))
                .group_by(Question.category)
            )
            categories = {
                row.category: row.count
                for row in categories_result
            }
            
            return {
                'total_questions': stats['total'],
                'new_questions_week': stats['new_week'],
                'unanswered_questions': stats['unanswered'],
                'auto_answered_questions': stats['auto_answered'],
                'average_rating': round(float(stats['avg_rating'] or 0), 2),
                'categories': categories
            }
            
        except Exception as e:
            logger.error(f"Error getting question stats: {e}")
            return {}

    async def _get_consultations_stats(
        self,
        week_ago: datetime,
        month_ago: datetime
    ) -> Dict[str, Any]:
        """Get detailed consultation statistics"""
        try:
            result = await self.session.execute(
                select(
                    func.count(Consultation.id).label('total'),
                    func.count(Consultation.id)
                    .filter(Consultation.created_at >= week_ago)
                    .label('new_week'),
                    func.count(Consultation.id)
                    .filter(Consultation.status == ConsultationStatus.PENDING)
                    .label('pending'),
                    func.count(Consultation.id)
                    .filter(Consultation.status == ConsultationStatus.COMPLETED)
                    .label('completed'),
                    func.avg(Consultation.rating)
                    .filter(Consultation.status == ConsultationStatus.COMPLETED)
                    .label('avg_rating')
                )
            )
            stats = result.mappings().first()
            
            return {
                'total_consultations': stats['total'],
                'new_consultations_week': stats['new_week'],
                'pending_consultations': stats['pending'],
                'completed_consultations': stats['completed'],
                'average_rating': round(float(stats['avg_rating'] or 0), 2),
                'completion_rate': round(stats['completed'] / stats['total'] * 100, 2) if stats['total'] else 0
            }
            
        except Exception as e:
            logger.error(f"Error getting consultation stats: {e}")
            return {}

    async def _get_revenue_stats(
        self,
        today: datetime,
        week_ago: datetime,
        month_ago: datetime
    ) -> Dict[str, Any]:
        """Get detailed revenue statistics"""
        try:
            result = await self.session.execute(
                select(
                    func.sum(Payment.amount)
                    .filter(Payment.status == PaymentStatus.COMPLETED)
                    .label('total'),
                    func.sum(Payment.amount)
                    .filter(
                        Payment.status == PaymentStatus.COMPLETED,
                        Payment.created_at >= today
                    )
                    .label('today'),
                    func.sum(Payment.amount)
                    .filter(
                        Payment.status == PaymentStatus.COMPLETED,
                        Payment.created_at >= week_ago
                    )
                    .label('week'),
                    func.sum(Payment.amount)
                    .filter(
                        Payment.status == PaymentStatus.COMPLETED,
                        Payment.created_at >= month_ago
                    )
                    .label('month')
                )
            )
            totals = result.mappings().first()
            
            # Get provider distribution
            providers_result = await self.session.execute(
                select(
                    Payment.provider,
                    func.count(Payment.id).label('count'),
                    func.sum(Payment.amount).label('amount')
                )
                .filter(Payment.status == PaymentStatus.COMPLETED)
                .group_by(Payment.provider)
            )
            providers = {
                row.provider: {
                    'count': row.count,
                    'amount': float(row.amount or 0)
                }
                for row in providers_result
            }
            
            return {
                'total_revenue': float(totals['total'] or 0),
                'revenue_today': float(totals['today'] or 0),
                'revenue_week': float(totals['week'] or 0),
                'revenue_month': float(totals['month'] or 0),
                'by_provider': providers
            }
            
        except Exception as e:
            logger.error(f"Error getting revenue stats: {e}")
            return {}

    async def _get_system_health(self) -> Dict[str, Any]:
        """Get system health metrics"""
        try:
            import psutil
            
            return {
                'cpu_usage': psutil.cpu_percent(),
                'memory_usage': psutil.virtual_memory().percent,
                'disk_usage': psutil.disk_usage('/').percent,
                'cache_hit_rate': await self.cache.get_hit_rate(),
                'error_rate': await self._get_error_rate()
            }
            
        except Exception as e:
            logger.error(f"Error getting system health: {e}")
            return {}

    async def _get_error_rate(self) -> float:
        """Calculate error rate for last hour"""
        try:
            hour_ago = datetime.utcnow() - timedelta(hours=1)
            
            result = await self.session.execute(
                select(
                    func.count(UserEvent.id).label('total'),
                    func.count(UserEvent.id)
                    .filter(UserEvent.event_type == 'error')
                    .label('errors')
                )
                .filter(UserEvent.created_at >= hour_ago)
            )
            stats = result.mappings().first()
            
            return round(stats['errors'] / stats['total'] * 100, 2) if stats['total'] else 0
            
        except Exception as e:
            logger.error(f"Error calculating error rate: {e}")
            return 0

    async def get_user_activity(
        self,
        user_id: int,
        days: int = 30
    ) -> List[Dict[str, Any]]:
        """Get user activity history"""
        try:
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
            
        except Exception as e:
            logger.error(f"Error getting user activity: {e}")
            return []

    async def track_event(
        self,
        user_id: int,
        event_type: str,
        data: Dict = None
    ) -> None:
        """Track user event"""
        try:
            event = UserEvent(
                user_id=user_id,
                event_type=event_type,
                event_data=data or {}
            )
            self.session.add(event)
            await self.session.commit()
            
        except Exception as e:
            logger.error(f"Error tracking event: {e}")

    async def export_data(
        self,
        start_date: datetime,
        end_date: datetime,
        data_type: str
    ) -> List[Dict[str, Any]]:
        """Export analytics data"""
        try:
            if data_type == 'users':
                data = await self._export_users(start_date, end_date)
            elif data_type == 'questions':
                data = await self._export_questions(start_date, end_date)
            elif data_type == 'consultations':
                data = await self._export_consultations(start_date, end_date)
            elif data_type == 'payments':
                data = await self._export_payments(start_date, end_date)
            else:
                raise ValueError(f"Unknown data type: {data_type}")
                
            return data
            
        except Exception as e:
            logger.error(f"Error exporting data: {e}")
            return []
# File: /telegram_bot/admin/views.py

from fastapi import APIRouter, Depends, HTTPException, Query
from typing import List, Optional
from datetime import datetime, timedelta
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func,or_, and_
from sqlalchemy.orm import joinedload
from telegram_bot.core.database import get_session
from telegram_bot.admin.auth import get_current_admin
from telegram_bot.models import User, Question, Consultation, Payment,Answer
from telegram_bot.services.analytics import AnalyticsService
from telegram_bot.services.payments import PaymentManager
from telegram_bot.services.questions import QuestionService
from telegram_bot.services.consultations import ConsultationService
import logging
router = APIRouter(prefix="/admin", tags=["admin"])
logger = logging.getLogger(__name__)

@router.get("/dashboard")
async def get_dashboard(
    session: AsyncSession = Depends(get_session),
    admin: User = Depends(get_current_admin)
):
    """Get admin dashboard data"""
    analytics = AnalyticsService(session)
    
    # Get period stats
    today = datetime.now()
    week_ago = today - timedelta(days=7)
    month_ago = today - timedelta(days=30)
    
    # Get user stats
    users_stats = await analytics.get_users_stats(
        start_date=month_ago
    )
    
    # Get questions stats
    question_service = QuestionService(session)
    questions_stats = await question_service.get_question_stats(
        start_date=month_ago
    )
    
    # Get consultation stats
    consultation_service = ConsultationService(session)
    consultations_stats = await consultation_service.get_consultation_stats(
        start_date=month_ago
    )
    
    # Get payment stats
    payment_manager = PaymentManager(session)
    payments_stats = await payment_manager.get_payment_stats(
        start_date=month_ago
    )
    
    return {
        "users": {
            "total": users_stats["total_users"],
            "active": users_stats["active_users"],
            "new_today": users_stats["new_users_today"],
            "new_week": users_stats["new_users_week"],
            "by_language": users_stats["language_distribution"]
        },
        "questions": {
            "total": questions_stats["total_questions"],
            "unanswered": questions_stats["unanswered_questions"],
            "auto_answered": questions_stats["auto_answered_questions"],
            "categories": questions_stats["category_distribution"]
        },
        "consultations": {
            "total": consultations_stats["total_consultations"],
            "pending": consultations_stats["pending_consultations"],
            "completed": consultations_stats["completed_consultations"],
            "revenue": float(consultations_stats["total_revenue"])
        },
        "payments": {
            "total": payments_stats["total_payments"],
            "amount": float(payments_stats["total_amount"]),
            "by_provider": payments_stats["by_provider"],
            "by_status": payments_stats["by_status"]
        }
    }

@router.get("/users")
async def get_users(
    skip: int = 0,
    limit: int = 50,
    search: Optional[str] = None,
    language: Optional[str] = None,
    is_active: Optional[bool] = None,
    sort: Optional[str] = None,
    session: AsyncSession = Depends(get_session),
    admin: User = Depends(get_current_admin)
):
    """Get users list"""
    query = select(User)
    
    # Apply filters
    if search:
        query = query.filter(
            or_(
                User.username.ilike(f"%{search}%"),
                User.full_name.ilike(f"%{search}%")
            )
        )
    if language:
        query = query.filter(User.language == language)
    if is_active is not None:
        query = query.filter(User.is_active == is_active)
        
    # Apply sorting
    if sort:
        if sort.startswith("-"):
            query = query.order_by(desc(getattr(User, sort[1:])))
        else:
            query = query.order_by(getattr(User, sort))
    
    # Get total count
    total = await session.scalar(
        select(func.count()).select_from(query.subquery())
    )
    
    # Apply pagination
    query = query.offset(skip).limit(limit)
    
    # Execute query
    result = await session.execute(query)
    users = result.scalars().all()
    
    return {
        "total": total,
        "items": [
            {
                "id": user.id,
                "telegram_id": user.telegram_id,
                "username": user.username,
                "full_name": user.full_name,
                "language": user.language,
                "is_active": user.is_active,
                "created_at": user.created_at.isoformat()
            }
            for user in users
        ]
    }

@router.get("/questions")
async def get_questions(
    skip: int = 0,
    limit: int = 50,
    status: Optional[str] = None,
    category: Optional[str] = None,
    language: Optional[str] = None,
    session: AsyncSession = Depends(get_session),
    admin: User = Depends(get_current_admin)
):
    """Get questions list"""
    query = select(Question).options(
        joinedload(Question.user),
        joinedload(Question.answers)
    )
    
    # Apply filters
    if status == "unanswered":
        query = query.filter(~Question.answers.any())
    elif status == "answered":
        query = query.filter(Question.answers.any())
    elif status == "auto":
        query = query.filter(
            Question.answers.any(Answer.is_auto == True)
        )
    
    if category:
        query = query.filter(Question.category == category)
    if language:
        query = query.filter(Question.language == language)
        
    # Get total count
    total = await session.scalar(
        select(func.count()).select_from(query.subquery())
    )
    
    # Apply pagination
    query = query.offset(skip).limit(limit)
    
    # Execute query
    result = await session.execute(query)
    questions = result.unique().scalars().all()
    
    return {
        "total": total,
        "items": [
            {
                "id": q.id,
                "text": q.question_text,
                "language": q.language,
                "category": q.category,
                "user": {
                    "id": q.user.id,
                    "username": q.user.username,
                    "full_name": q.user.full_name
                },
                "answers": [
                    {
                        "id": a.id,
                        "text": a.answer_text,
                        "is_auto": a.is_auto,
                        "created_at": a.created_at.isoformat()
                    }
                    for a in q.answers
                ],
                "created_at": q.created_at.isoformat()
            }
            for q in questions
        ]
    }

@router.get("/consultations") 
async def get_consultations(
    skip: int = 0,
    limit: int = 50,
    status: Optional[str] = None,
    session: AsyncSession = Depends(get_session),
    admin: User = Depends(get_current_admin)
):
    """Get consultations list"""
    query = select(Consultation).options(
        joinedload(Consultation.user),
        joinedload(Consultation.payments)
    )
    
    # File: /telegram_bot/admin/views.py (продолжение)

    # Apply filters
    if status:
        query = query.filter(Consultation.status == status)
        
    # Get total count
    total = await session.scalar(
        select(func.count()).select_from(query.subquery())
    )
    
    # Apply pagination
    query = query.offset(skip).limit(limit)
    
    # Execute query
    result = await session.execute(query)
    consultations = result.unique().scalars().all()
    
    return {
        "total": total,
        "items": [
            {
                "id": c.id,
                "status": c.status.value,
                "amount": float(c.amount),
                "scheduled_time": c.scheduled_time.isoformat() if c.scheduled_time else None,
                "user": {
                    "id": c.user.id,
                    "username": c.user.username,
                    "full_name": c.user.full_name
                },
                "payments": [
                    {
                        "id": p.id,
                        "provider": p.provider,
                        "status": p.status.value,
                        "amount": float(p.amount),
                        "created_at": p.created_at.isoformat()
                    }
                    for p in c.payments
                ],
                "created_at": c.created_at.isoformat()
            }
            for c in consultations
        ]
    }

@router.get("/payments")
async def get_payments(
    skip: int = 0,
    limit: int = 50,
    provider: Optional[str] = None,
    status: Optional[str] = None,
    session: AsyncSession = Depends(get_session),
    admin: User = Depends(get_current_admin)
):
    """Get payments list"""
    query = select(Payment).options(
        joinedload(Payment.consultation)
    )
    
    # Apply filters
    if provider:
        query = query.filter(Payment.provider == provider)
    if status:
        query = query.filter(Payment.status == status)
        
    # Get total count
    total = await session.scalar(
        select(func.count()).select_from(query.subquery())
    )
    
    # Apply pagination
    query = query.offset(skip).limit(limit)
    
    # Execute query
    result = await session.execute(query)
    payments = result.unique().scalars().all()
    
    return {
        "total": total,
        "items": [
            {
                "id": p.id,
                "provider": p.provider,
                "status": p.status.value,
                "amount": float(p.amount),
                "consultation": {
                    "id": p.consultation.id,
                    "status": p.consultation.status.value,
                    "user": {
                        "id": p.consultation.user.id,
                        "username": p.consultation.user.username,
                        "full_name": p.consultation.user.full_name
                    }
                },
                "transaction_id": p.transaction_id,
                "created_at": p.created_at.isoformat()
            }
            for p in payments
        ]
    }

@router.post("/broadcast")
async def send_broadcast(
    message: str,
    users: Optional[List[int]] = None,
    language: Optional[str] = None,
    session: AsyncSession = Depends(get_session),
    admin: User = Depends(get_current_admin)
):
    """Send broadcast message to users"""
    from telegram_bot.bot import bot
    
    # Build user query
    query = select(User.telegram_id)
    
    if users:
        query = query.filter(User.id.in_(users))
    if language:
        query = query.filter(User.language == language)
        
    # Get user IDs
    result = await session.execute(query)
    user_ids = result.scalars().all()
    
    if not user_ids:
        raise HTTPException(
            status_code=400,
            detail="No users match the criteria"
        )
    
    # Send messages
    success = 0
    failed = 0
    
    for user_id in user_ids:
        try:
            await bot.send_message(user_id, message)
            success += 1
        except Exception as e:
            logger.error(f"Error sending broadcast to {user_id}: {e}")
            failed += 1
    
    return {
        "success": True,
        "sent": success,
        "failed": failed,
        "total": len(user_ids)
    }

@router.get("/analytics")
async def get_analytics(
    start_date: datetime,
    end_date: datetime,
    session: AsyncSession = Depends(get_session),
    admin: User = Depends(get_current_admin)
):
    """Get analytics data"""
    analytics = AnalyticsService(session)
    
    return {
        "users": await analytics.get_users_stats(start_date, end_date),
        "questions": await analytics.get_question_stats(start_date, end_date),
        "consultations": await analytics.get_consultation_stats(start_date, end_date),
        "payments": await analytics.get_payment_stats(start_date, end_date),
        "performance": await analytics.get_performance_metrics()
    }

@router.post("/notifications")
async def send_notification(
    user_id: int,
    title: str,
    message: str,
    notification_type: str,
    session: AsyncSession = Depends(get_session),
    admin: User = Depends(get_current_admin)
):
    """Send notification to user"""
    from telegram_bot.services.notifications import NotificationService
    
    notification_service = NotificationService(session)
    notification = await notification_service.send_notification(
        user_id=user_id,
        title=title,
        message=message,
        notification_type=notification_type
    )
    
    if not notification:
        raise HTTPException(
            status_code=400,
            detail="Failed to send notification"
        )
        
    return {
        "success": True,
        "notification_id": notification.id
    }

@router.get("/system/health")
async def get_system_health(
    session: AsyncSession = Depends(get_session),
    admin: User = Depends(get_current_admin)
):
    """Get system health status"""
    # Check database
    try:
        await session.execute(select(1))
        db_status = "healthy"
    except:
        db_status = "unhealthy"
    
    # Check cache
    try:
        from telegram_bot.core.cache import cache_service as cache

        await cache.ping()
        cache_status = "healthy"
    except:
        cache_status = "unhealthy"
    
    # Check bot
    from telegram_bot.bot import bot
    try:
        me = await bot.get_me()
        bot_status = "healthy"
    except:
        bot_status = "unhealthy"
    
    # Get system metrics
    import psutil
    
    return {
        "status": all([
            s == "healthy" 
            for s in [db_status, cache_status, bot_status]
        ]),
        "components": {
            "database": db_status,
            "cache": cache_status,
            "bot": bot_status
        },
        "metrics": {
            "cpu": psutil.cpu_percent(),
            "memory": psutil.virtual_memory().percent,
            "disk": psutil.disk_usage('/').percent
        }
    }
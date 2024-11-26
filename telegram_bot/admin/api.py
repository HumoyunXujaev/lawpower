from fastapi import APIRouter, Depends, HTTPException, Query, Body, Request,Response
from fastapi.security import OAuth2PasswordBearer
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func, or_, and_
from typing import Optional, List, Dict, Any
from datetime import datetime, timedelta
import logging
from decimal import Decimal
from sqlalchemy.orm import joinedload
import asyncio
from sqlalchemy import event, text
from telegram_bot.core.database import get_session
from telegram_bot.core.security import (
    verify_token,
    create_access_token,
)
from telegram_bot.admin.auth import get_current_admin
from telegram_bot.models import (
    User, Question, Answer, Consultation, Payment,
    ConsultationStatus, PaymentStatus
)
from telegram_bot.services.analytics import AnalyticsService
from telegram_bot.services.questions import QuestionService
from telegram_bot.services.consultations import ConsultationService
from telegram_bot.core.cache import cache_service as cache
from telegram_bot.core.config import settings

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/admin", tags=["admin"])

@router.get("/dashboard")
async def get_dashboard_data(
    request: Request,
    session: AsyncSession = Depends(get_session),
    admin: User = Depends(get_current_admin)
):
    """Get admin dashboard data"""
    try:
        # Check cache
        cache_key = f"admin:dashboard:{admin.id}"
        cached = await cache.get(cache_key)
        if cached:
            return cached

        analytics = AnalyticsService(session)
        
        # Get user statistics
        users_stats = await analytics.get_users_stats()
        
        # Get questions statistics
        question_service = QuestionService(session)
        questions_stats = await question_service.get_question_stats()
        
        # Get consultation statistics
        consultation_service = ConsultationService(session)
        consultations_stats = await consultation_service.get_consultation_stats()
        
        # Get revenue data
        revenue_stats = await analytics.get_revenue_stats()
        
        # Get recent activity
        activity = await analytics.get_recent_activity()
        
        dashboard_data = {
            "users": {
                "total": users_stats["total"],
                "active": users_stats["active"],
                "growth_rate": users_stats["growth_rate"],
                "language_distribution": users_stats["languages"]
            },
            "questions": {
                "total": questions_stats["total_questions"],
                "answered": questions_stats["answered_questions"],
                "answer_rate": questions_stats["answer_rate"],
                "categories": questions_stats["categories"]
            },
            "consultations": {
                "total": consultations_stats["total_consultations"],
                "completed": consultations_stats["completed_consultations"],
                "revenue": consultations_stats["total_revenue"],
                "average_rating": consultations_stats["average_rating"]
            },
            "revenue": {
                "today": revenue_stats["today"],
                "this_week": revenue_stats["this_week"],
                "this_month": revenue_stats["this_month"],
                "by_payment_method": revenue_stats["by_provider"]
            },
            "activity": activity,
            "timestamp": datetime.utcnow().isoformat()
        }
        
        # Cache for 5 minutes
        await cache.set(cache_key, dashboard_data, timeout=300)
        
        return dashboard_data
        
    except Exception as e:
        logger.error(f"Error getting dashboard data: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="Internal server error")

@router.get("/users")
async def get_users(
    skip: int = Query(0, ge=0),
    limit: int = Query(50, gt=0, le=100),
    search: Optional[str] = None,
    status: Optional[str] = None,
    language: Optional[str] = None,
    sort_by: str = Query("created_at", enum=["created_at", "last_active"]),
    order: str = Query("desc", enum=["asc", "desc"]),
    session: AsyncSession = Depends(get_session),
    admin: User = Depends(get_current_admin)
):
    """Get paginated users list"""
    try:
        # Build query
        query = select(User)
        
        # Apply filters
        if search:
            query = query.filter(
                or_(
                    User.username.ilike(f"%{search}%"),
                    User.full_name.ilike(f"%{search}%")
                )
            )
        
        if status == "active":
            query = query.filter(
                User.is_active == True,
                User.is_blocked == False
            )
        elif status == "blocked":
            query = query.filter(User.is_blocked == True)
            
        if language:
            query = query.filter(User.language == language)
            
        # Apply sorting
        if order == "desc":
            query = query.order_by(getattr(User, sort_by).desc())
        else:
            query = query.order_by(getattr(User, sort_by).asc())
            
        # Get total count
        total = await session.scalar(
            select(func.count()).select_from(query.subquery())
        )
        
        # Get paginated results
        query = query.offset(skip).limit(limit)
        result = await session.execute(query)
        users = result.scalars().all()
        
        # Get additional stats for users
        analytics = AnalyticsService(session)
        users_data = []
        
        for user in users:
            stats = await analytics.get_user_stats(user.id)
            users_data.append({
                "id": user.id,
                "telegram_id": user.telegram_id,
                "username": user.username,
                "full_name": user.full_name,
                "language": user.language,
                "is_active": user.is_active,
                "is_blocked": user.is_blocked,
                "created_at": user.created_at.isoformat(),
                "last_active": user.last_active.isoformat() if user.last_active else None,
                "stats": {
                    "questions_count": stats["questions_count"],
                    "consultations_count": stats["consultations_count"],
                    "total_spent": stats["total_spent"]
                }
            })
            
        return {
            "total": total,
            "page": skip // limit + 1,
            "pages": (total + limit - 1) // limit,
            "items": users_data
        }
        
    except Exception as e:
        logger.error(f"Error getting users: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="Internal server error")

@router.post("/users/{user_id}/block")
async def toggle_user_block(
    user_id: int,
    reason: str = Body(...),
    session: AsyncSession = Depends(get_session),
    admin: User = Depends(get_current_admin)
):
    """Toggle user block status"""
    try:
        user = await session.get(User, user_id)
        if not user:
            raise HTTPException(status_code=404, detail="User not found")
            
        # Toggle block status
        user.is_blocked = not user.is_blocked
        
        # Update metadata
        user.metadata = user.metadata or {}
        if user.is_blocked:
            user.metadata["blocked_at"] = datetime.utcnow().isoformat()
            user.metadata["blocked_by"] = admin.id
            user.metadata["block_reason"] = reason
        else:
            user.metadata["unblocked_at"] = datetime.utcnow().isoformat()
            user.metadata["unblocked_by"] = admin.id
            
        await session.commit()
        
        # Clear cache
        await cache.delete(f"user:{user_id}")
        
        # Notify user
        from telegram_bot.bot import bot
        if user.is_blocked:
            await bot.send_message(
                user.telegram_id,
                f"Your account has been blocked. Reason: {reason}"
            )
        else:
            await bot.send_message(
                user.telegram_id,
                "Your account has been unblocked."
            )
            
        return {"success": True, "is_blocked": user.is_blocked}
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error toggling user block: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="Internal server error")

@router.get("/questions")
async def get_questions(
    skip: int = Query(0, ge=0),
    limit: int = Query(50, gt=0, le=100),
    status: Optional[str] = None,
    language: Optional[str] = None,
    category: Optional[str] = None,
    search: Optional[str] = None,
    session: AsyncSession = Depends(get_session),
    admin: User = Depends(get_current_admin)
):
    """Get paginated questions list"""
    try:
        # Build query
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
            
        if language:
            query = query.filter(Question.language == language)
            
        if category:
            query = query.filter(Question.category == category)
            
        if search:
            query = query.filter(Question.question_text.ilike(f"%{search}%"))
            
        # Get total count
        total = await session.scalar(
            select(func.count()).select_from(query.subquery())
        )
        
        # Get paginated results
        query = query.order_by(Question.created_at.desc())
        query = query.offset(skip).limit(limit)
        result = await session.execute(query)
        questions = result.unique().scalars().all()
        
        return {
            "total": total,
            "page": skip // limit + 1,
            "pages": (total + limit - 1) // limit,
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
                            "rating": a.rating,
                            "created_at": a.created_at.isoformat()
                        }
                        for a in q.answers
                    ],
                    "created_at": q.created_at.isoformat()
                }
                for q in questions
            ]
        }
        
    except Exception as e:
        logger.error(f"Error getting questions: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="Internal server error")

@router.post("/questions/{question_id}/answer")
async def create_answer(
    question_id: int,
    data: Dict = Body(...),
    session: AsyncSession = Depends(get_session),
    admin: User = Depends(get_current_admin)
):
    """Create answer for question"""
    try:
        question_service = QuestionService(session)
        question = await question_service.get_question(question_id)
        
        if not question:
            raise HTTPException(status_code=404, detail="Question not found")
            
        # Create answer
        answer = await question_service.create_answer(
            question_id=question_id,
            answer_text=data["text"],
            created_by=admin.id
        )
        
        # Notify user
        from telegram_bot.bot import bot
        await bot.send_message(
            question.user.telegram_id,
            f"Your question has been answered:\n\n"
            f"Q: {question.question_text}\n\n"
            f"A: {answer.answer_text}"
        )
        
        return {
            "success": True,
            "answer": {
                "id": answer.id,
                "text": answer.answer_text,
                "created_at": answer.created_at.isoformat()
            }
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error creating answer: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="Internal server error")

@router.get("/consultations")
async def get_consultations(
    skip: int = Query(0, ge=0),
    limit: int = Query(50, gt=0, le=100),
    status: Optional[str] = None,
    date_from: Optional[datetime] = None,
    date_to: Optional[datetime] = None,
    session: AsyncSession = Depends(get_session),
    admin: User = Depends(get_current_admin)
):
    """Get paginated consultations list"""
    try:
        # Build query
        query = select(Consultation).options(
            joinedload(Consultation.user),
            joinedload(Consultation.payments)
        )
        
        # Apply filters
        if status:
            query = query.filter(
                Consultation.status == ConsultationStatus[status]
            )
            
        if date_from:
            query = query.filter(Consultation.created_at >= date_from)
        if date_to:
            query = query.filter(Consultation.created_at <= date_to)
            
        # Get total count
        total = await session.scalar(
            select(func.count()).select_from(query.subquery())
        )
        
        # Get paginated results
        query = query.order_by(Consultation.created_at.desc())
        query = query.offset(skip).limit(limit)
        result = await session.execute(query)
        consultations = result.unique().scalars().all()
        
        return {
            "total": total,
            "page": skip // limit + 1,
            "pages": (total + limit - 1) // limit,
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
                            "status": p.status.value,
                            "provider": p.provider.value,
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
        
    except Exception as e:
        logger.error(f"Error getting consultations: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="Internal server error")

@router.post("/consultations/{consultation_id}/status")
async def update_consultation_status(
    consultation_id: int,
    data: Dict = Body(...),
    session: AsyncSession = Depends(get_session),
    admin: User = Depends(get_current_admin)
):
    """Update consultation status"""
    try:
        consultation_service = ConsultationService(session)
        consultation = await consultation_service.get_consultation(consultation_id)
        
        if not consultation:
            raise HTTPException(status_code=404, detail="Consultation not found")
            
        # Update status
        new_status = ConsultationStatus[data["status"]]
        old_status = consultation.status
        
        consultation.status = new_status
        consultation.metadata = consultation.metadata or {}
        consultation.metadata["status_history"] = consultation.metadata.get("status_history", [])
        consultation.metadata["status_history"].append({
            "from": old_status.value,
            "to": new_status.value,
            "changed_by": admin.id,
            "changed_at": datetime.utcnow().isoformat(),
            "reason": data.get("reason")
        })
        
        # Handle scheduled time
        if new_status == ConsultationStatus.SCHEDULED and "scheduled_time" in data:
            consultation.scheduled_time = datetime.fromisoformat(data["scheduled_time"])
            
        await session.commit()
        
        # Notify user
        from telegram_bot.bot import bot
        notification = f"Your consultation status has been updated to: {new_status.value}"
        if consultation.scheduled_time:
            notification += f"\nScheduled for: {consultation.scheduled_time.strftime('%Y-%m-%d %H:%M')}"
            
        await bot.send_message(
            consultation.user.telegram_id,
            notification
        )
        
        return {
            "success": True,
            "status": new_status.value,
            "scheduled_time": consultation.scheduled_time.isoformat() if consultation.scheduled_time else None
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error updating consultation status: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="Internal server error")

@router.get("/analytics/export")
async def export_analytics(
    start_date: datetime,
    end_date: datetime,
    report_type: str = Query(..., enum=["users", "questions", "consultations", "payments"]),
    format: str = Query("csv", enum=["csv", "xlsx"]),
    session: AsyncSession = Depends(get_session),
    admin: User = Depends(get_current_admin)
):
    """Export analytics data"""
    try:
        analytics = AnalyticsService(session)
        
        if report_type == "users":
            data = await analytics.export_users_data(start_date, end_date)
        elif report_type == "questions":
            data = await analytics.export_questions_data(start_date, end_date)
        elif report_type == "consultations":
            data = await analytics.export_consultations_data(start_date, end_date)
        else:
            data = await analytics.export_payments_data(start_date, end_date)
            
        # Generate file
        filename = f"{report_type}_{start_date.date()}_{end_date.date()}"
        if format == "csv":
            file_content = analytics.generate_csv(data)
            media_type = "text/csv"
            filename += ".csv"
        else:
            file_content = analytics.generate_excel(data)
            media_type = "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
            filename += ".xlsx"
            
        # Track export
        await analytics.track_admin_action(
            admin_id=admin.id,
            action="export_data",
            details={
                "type": report_type,
                "format": format,
                "start_date": start_date.isoformat(),
                "end_date": end_date.isoformat()
            }
        )
        
        return Response(
            content=file_content,
            media_type=media_type,
            headers={
                'Content-Disposition': f'attachment; filename="{filename}"'
            }
        )
        
    except Exception as e:
        logger.error(f"Error exporting analytics: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="Internal server error")

@router.post("/broadcast")
async def send_broadcast(
    data: Dict = Body(...),
    session: AsyncSession = Depends(get_session),
    admin: User = Depends(get_current_admin)
):
    """Send broadcast message to users"""
    try:
        # Validate message
        if not data.get("message"):
            raise HTTPException(status_code=400, detail="Message is required")
            
        # Build user query
        query = select(User.telegram_id).filter(User.is_blocked == False)
        
        # Apply filters
        if data.get("language"):
            query = query.filter(User.language == data["language"])
            
        if data.get("active_only"):
            week_ago = datetime.utcnow() - timedelta(days=7)
            query = query.filter(User.last_active >= week_ago)
            
        # Get user IDs
        result = await session.execute(query)
        user_ids = result.scalars().all()
        
        if not user_ids:
            raise HTTPException(status_code=400, detail="No users match the criteria")
            
        # Send messages
        from telegram_bot.bot import bot
        sent = 0
        failed = 0
        
        for user_id in user_ids:
            try:
                await bot.send_message(
                    user_id,
                    data["message"],
                    parse_mode=data.get("parse_mode", "HTML")
                )
                sent += 1
                await asyncio.sleep(0.05)  # Rate limiting
            except Exception as e:
                logger.error(f"Error sending broadcast to {user_id}: {e}")
                failed += 1
                
        # Track broadcast
        analytics = AnalyticsService(session)
        await analytics.track_admin_action(
            admin_id=admin.id,
            action="broadcast",
            details={
                "sent": sent,
                "failed": failed,
                "total": len(user_ids),
                "filters": {
                    "language": data.get("language"),
                    "active_only": data.get("active_only")
                }
            }
        )
        
        return {
            "success": True,
            "sent": sent,
            "failed": failed,
            "total": len(user_ids)
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error sending broadcast: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="Internal server error")

@router.get("/logs")
async def get_system_logs(
    level: str = Query("ERROR", enum=["DEBUG", "INFO", "WARNING", "ERROR"]),
    start_date: Optional[datetime] = None,
    end_date: Optional[datetime] = None,
    limit: int = Query(100, le=1000),
    session: AsyncSession = Depends(get_session),
    admin: User = Depends(get_current_admin)
):
    """Get system logs"""
    try:
        # Build log query
        query = "SELECT timestamp, level, message, data FROM system_logs WHERE level >= :level"
        params = {"level": level}
        
        if start_date:
            query += " AND timestamp >= :start_date"
            params["start_date"] = start_date
            
        if end_date:
            query += " AND timestamp <= :end_date"
            params["end_date"] = end_date
            
        query += " ORDER BY timestamp DESC LIMIT :limit"
        params["limit"] = limit
        
        result = await session.execute(text(query), params)
        logs = result.mappings().all()
        
        return {
            "total": len(logs),
            "items": [
                {
                    "timestamp": log["timestamp"].isoformat(),
                    "level": log["level"],
                    "message": log["message"],
                    "data": log["data"]
                }
                for log in logs
            ]
        }
        
    except Exception as e:
        logger.error(f"Error getting system logs: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="Internal server error")

@router.get("/system/health")
async def get_system_health(
    session: AsyncSession = Depends(get_session),
    admin: User = Depends(get_current_admin)
):
    """Get system health status"""
    try:
        # Check database
        db_status = await session.execute(text("SELECT 1"))
        db_healthy = bool(db_status.scalar())
        
        # Check Redis
        redis_healthy = await cache.health_check()
        
        # Check bot
        from telegram_bot.bot import bot
        try:
            bot_info = await bot.get_me()
            bot_healthy = True
        except Exception:
            bot_healthy = False
            
        # Get system metrics
        import psutil
        cpu_percent = psutil.cpu_percent()
        memory = psutil.virtual_memory()
        disk = psutil.disk_usage('/')
        
        return {
            "status": "healthy" if all([db_healthy, redis_healthy, bot_healthy]) else "unhealthy",
            "timestamp": datetime.utcnow().isoformat(),
            "components": {
                "database": {
                    "status": "up" if db_healthy else "down"
                },
                "cache": {
                    "status": "up" if redis_healthy else "down"
                },
                "bot": {
                    "status": "up" if bot_healthy else "down"
                }
            },
            "metrics": {
                "cpu_usage": cpu_percent,
                "memory_usage": {
                    "total": memory.total,
                    "used": memory.used,
                    "percent": memory.percent
                },
                "disk_usage": {
                    "total": disk.total,
                    "used": disk.used,
                    "percent": disk.percent
                }
            }
        }
        
    except Exception as e:
        logger.error(f"Error getting system health: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="Internal server error")

@router.post("/system/cache/clear")
async def clear_system_cache(session,
    cache_type: str = Query(..., enum=["all", "users", "questions", "stats"]),
    admin: User = Depends(get_current_admin),
    
):
    """Clear system cache"""
    try:
        if cache_type == "all":
            await cache.clear_all()
        else:
            pattern = f"{cache_type}:*"
            await cache.clear_pattern(pattern)
            
        # Track action
        analytics = AnalyticsService(session)
        await analytics.track_admin_action(
            admin_id=admin.id,
            action="clear_cache",
            details={"type": cache_type}
        )
        
        return {"success": True}
        
    except Exception as e:
        logger.error(f"Error clearing cache: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="Internal server error")


@router.get("/faq/categories")
async def get_faq_categories(
    language: Optional[str] = None,
    session: AsyncSession = Depends(get_session),
    admin: User = Depends(get_current_admin)
):
    """Get FAQ categories"""
    faq_service = FAQService(session)
    categories = await faq_service.get_faq_categories(language)
    return {"items": categories}

@router.post("/faq/categories")
async def create_faq_category(
    name: dict,  # {'uz': '...', 'ru': '...'}
    description: Optional[dict] = None,
    icon: Optional[str] = None,
    session: AsyncSession = Depends(get_session),
    admin: User = Depends(get_current_admin)
):
    """Create FAQ category"""
    faq_service = FAQService(session)
    category = await faq_service.create_category(
        name=name,
        description=description,
        icon=icon
    )
    return category

@router.get("/faq/{category_id}")
async def get_category_faqs(
    category_id: int,
    language: Optional[str] = None,
    session: AsyncSession = Depends(get_session),
    admin: User = Depends(get_current_admin)
):
    """Get FAQs in category"""
    faq_service = FAQService(session)
    faqs = await faq_service.get_category_faqs(category_id, language)
    return {"items": faqs}

@router.post("/faq")
async def create_faq(
    category_id: int,
    question: dict,  # {'uz': '...', 'ru': '...'}
    answer: dict,    # {'uz': '...', 'ru': '...'}
    is_published: bool = True,
    session: AsyncSession = Depends(get_session),
    admin: User = Depends(get_current_admin)
):
    """Create FAQ"""
    faq_service = FAQService(session)
    faq = await faq_service.create_faq(
        category_id=category_id,
        question=question,
        answer=answer,
        is_published=is_published
    )
    return faq

@router.get("/analytics/dashboard")
async def get_analytics_dashboard(
    period: str = Query("week", enum=["day", "week", "month"]),
    session: AsyncSession = Depends(get_session),
    admin: User = Depends(get_current_admin)
):
    """Get analytics dashboard data"""
    analytics = AnalyticsService(session)
    
    # Get date range
    end_date = datetime.utcnow()
    if period == "day":
        start_date = end_date - timedelta(days=1)
    elif period == "week":
        start_date = end_date - timedelta(weeks=1)
    else:
        start_date = end_date - timedelta(days=30)
        
    # Get analytics data
    data = await analytics.get_dashboard_stats(
        start_date=start_date,
        end_date=end_date
    )
    
    return data

@router.get("/analytics/export")
async def export_analytics(
    start_date: datetime,
    end_date: datetime,
    format: str = Query("csv", enum=["csv", "xlsx"]),
    session: AsyncSession = Depends(get_session),
    admin: User = Depends(get_current_admin)
):
    """Export analytics data"""
    analytics = AnalyticsService(session)
    
    data = await analytics.export_data(
        start_date=start_date,
        end_date=end_date
    )
    
    if format == "csv":
        return analytics.export_csv(data)
    else:
        return analytics.export_excel(data)

@router.get("/users/stats")
async def get_user_statistics(
    period: str = Query("week", enum=["day", "week", "month"]),
    session: AsyncSession = Depends(get_session),
    admin: User = Depends(get_current_admin)
):
    """Get user statistics"""
    analytics = AnalyticsService(session)
    
    end_date = datetime.utcnow()
    if period == "day":
        start_date = end_date - timedelta(days=1)
    elif period == "week":
        start_date = end_date - timedelta(weeks=1)
    else:
        start_date = end_date - timedelta(days=30)
        
    stats = await analytics.get_user_stats(
        start_date=start_date,
        end_date=end_date
    )
    
    return stats

@router.get("/users/active")
async def get_active_users(
    days: int = Query(7, ge=1, le=30),
    session: AsyncSession = Depends(get_session),
    admin: User = Depends(get_current_admin)
):
    """Get active users"""
    analytics = AnalyticsService(session)
    users = await analytics.get_active_users(days=days)
    return {"items": users}



def register_admin_routes(app):
    """Register admin routes"""
    app.include_router(router)
import asyncio
import logging
from datetime import datetime, timedelta
from typing import Optional, Dict, Any
from sqlalchemy import select, func
from sqlalchemy import event, text
from sqlalchemy.orm import joinedload
from telegram_bot.core.cache import cache_service as cache


from telegram_bot.core.database import get_session
from telegram_bot.models import (
    User, Question, Consultation, ConsultationStatus,
    Payment, PaymentStatus
)
from telegram_bot.services.analytics import AnalyticsService
from telegram_bot.services.auto_answer import AutoAnswerTrainer

logger = logging.getLogger(__name__)

class BackgroundTaskManager:
    """Background task manager for scheduled operations"""
    
    def __init__(self):
        self._running = False
        self._tasks = []
        
    async def start(self):
        """Start background tasks"""
        if self._running:
            return
            
        self._running = True
        
        # Start periodic tasks
        self._tasks.extend([
            asyncio.create_task(self._run_periodic(
                self._train_auto_answer,
                hours=24
            )),
            asyncio.create_task(self._run_periodic(
                self._cleanup_expired_data,
                hours=1
            )),
            asyncio.create_task(self._run_periodic(
                self._update_statistics,
                minutes=5
            )),
            asyncio.create_task(self._run_periodic(
                self._process_scheduled_consultations,
                minutes=1
            )),
            asyncio.create_task(self._run_periodic(
                self._health_check,
                minutes=1
            ))
        ])
        
        logger.info("Background tasks started")
        
    async def stop(self):
        """Stop all background tasks"""
        self._running = False
        
        for task in self._tasks:
            task.cancel()
            
        await asyncio.gather(*self._tasks, return_exceptions=True)
        self._tasks.clear()
        
        logger.info("Background tasks stopped")
        
    async def _run_periodic(
        self,
        func: callable,
        days: int = 0,
        hours: int = 0,
        minutes: int = 0
    ):
        """Run periodic task"""
        interval = timedelta(
            days=days,
            hours=hours,
            minutes=minutes
        ).total_seconds()
        
        while self._running:
            try:
                await func()
            except Exception as e:
                logger.error(f"Error in periodic task {func.__name__}: {e}")
            await asyncio.sleep(interval)
            
    async def _train_auto_answer(self):
        """Train auto-answer models"""
        try:
            async with get_session() as session:
                trainer = AutoAnswerTrainer(session)
                
                # Train for each language
                for language in ['uz', 'ru']:
                    success = await trainer.train_model(language)
                    if success:
                        logger.info(f"Auto-answer model trained for {language}")
                        
                    # Evaluate model
                    metrics = await trainer.evaluate_model(language)
                    await cache.set(
                        f"auto_answer:metrics:{language}",
                        metrics
                    )
                    
        except Exception as e:
            logger.error(f"Error training auto-answer: {e}")
            
    async def _cleanup_expired_data(self):
        """Clean up expired data"""
        try:
            async with get_session() as session:
                # Clean up expired payments
                expired_time = datetime.utcnow() - timedelta(hours=24)
                expired_payments = await session.execute(
                    select(Payment)
                    .filter(
                        Payment.status == PaymentStatus.PENDING,
                        Payment.created_at < expired_time
                    )
                )
                
                for payment in expired_payments.scalars():
                    payment.status = PaymentStatus.EXPIRED

                # Archive old questions
                archive_time = datetime.utcnow() - timedelta(days=90)
                old_questions = await session.execute(
                    select(Question)
                    .filter(
                        Question.created_at < archive_time,
                        Question.is_answered == True
                    )
                )
                
                for question in old_questions.scalars():
                    question.archived = True
                    question.metadata = question.metadata or {}
                    question.metadata["archived_at"] = datetime.utcnow().isoformat()
                    
                # Clean up user sessions
                session_expiry = datetime.utcnow() - timedelta(days=30)
                await session.execute(
                    text("DELETE FROM user_sessions WHERE last_activity < :expiry"),
                    {"expiry": session_expiry}
                )
                
                await session.commit()
                logger.info("Cleanup completed successfully")
                
        except Exception as e:
            logger.error(f"Error in cleanup task: {e}")
            
    async def _update_statistics(self):
        """Update system statistics"""
        try:
            async with get_session() as session:
                analytics = AnalyticsService(session)
                
                # Update user statistics
                user_stats = await analytics.get_users_stats()
                await cache.set("stats:users", user_stats, timeout=300)
                
                # Update question statistics
                question_stats = await analytics.get_question_stats()
                await cache.set("stats:questions", question_stats, timeout=300)
                
                # Update consultation statistics
                consultation_stats = await analytics.get_consultation_stats()
                await cache.set("stats:consultations", consultation_stats, timeout=300)
                
                # Update revenue statistics
                revenue_stats = await analytics.get_revenue_stats()
                await cache.set("stats:revenue", revenue_stats, timeout=300)
                
                logger.info("Statistics updated successfully")
                
        except Exception as e:
            logger.error(f"Error updating statistics: {e}")
            
    async def _process_scheduled_consultations(self):
        """Process scheduled consultations"""
        try:
            async with get_session() as session:
                # Get upcoming consultations
                now = datetime.utcnow()
                upcoming = now + timedelta(minutes=30)
                
                scheduled = await session.execute(
                    select(Consultation)
                    .filter(
                        Consultation.status == ConsultationStatus.SCHEDULED,
                        Consultation.scheduled_time.between(now, upcoming)
                    )
                    .options(joinedload(Consultation.user))
                )
                
                from telegram_bot.bot import bot
                
                for consultation in scheduled.scalars():
                    # Send reminder to user
                    try:
                        await bot.send_message(
                            consultation.user.telegram_id,
                            f"Reminder: Your consultation is scheduled for "
                            f"{consultation.scheduled_time.strftime('%H:%M')} "
                            f"(in {(consultation.scheduled_time - now).minutes} minutes)"
                        )
                        
                        # Update reminder sent flag
                        consultation.metadata = consultation.metadata or {}
                        consultation.metadata["reminder_sent"] = True
                        consultation.metadata["reminder_sent_at"] = now.isoformat()
                        
                    except Exception as e:
                        logger.error(f"Error sending reminder for consultation {consultation.id}: {e}")
                        
                await session.commit()
                
        except Exception as e:
            logger.error(f"Error processing scheduled consultations: {e}")
            
    async def _health_check(self):
        """Perform system health check"""
        try:
            health_data = {
                "timestamp": datetime.utcnow().isoformat(),
                "status": "healthy",
                "components": {}
            }
            
            # Check database
            try:
                async with get_session() as session:
                    await session.execute(text("SELECT 1"))
                health_data["components"]["database"] = {"status": "up"}
            except Exception as e:
                health_data["components"]["database"] = {
                    "status": "down",
                    "error": str(e)
                }
                health_data["status"] = "degraded"
                
            # Check Redis
            try:
                redis_ok = await cache.health_check()
                health_data["components"]["cache"] = {
                    "status": "up" if redis_ok else "down"
                }
                if not redis_ok:
                    health_data["status"] = "degraded"
            except Exception as e:
                health_data["components"]["cache"] = {
                    "status": "down",
                    "error": str(e)
                }
                health_data["status"] = "degraded"
                
            # Check bot
            try:
                from telegram_bot.bot import bot
                me = await bot.get_me()
                health_data["components"]["bot"] = {"status": "up"}
            except Exception as e:
                health_data["components"]["bot"] = {
                    "status": "down",
                    "error": str(e)
                }
                health_data["status"] = "degraded"
                
            # Check system resources
            import psutil
            system_metrics = {
                "cpu_percent": psutil.cpu_percent(),
                "memory_percent": psutil.virtual_memory().percent,
                "disk_percent": psutil.disk_usage('/').percent
            }
            
            # Check if any resource is critical
            for metric, value in system_metrics.items():
                if value > 90:  # Critical threshold
                    health_data["status"] = "degraded"
                    
            health_data["metrics"] = system_metrics
            
            # Save health status
            await cache.set(
                "system:health",
                health_data,
                timeout=60
            )
            
            # Alert if system is unhealthy
            if health_data["status"] != "healthy":
                await self._send_health_alert(health_data)
                
        except Exception as e:
            logger.error(f"Error in health check: {e}")
            
    async def _send_health_alert(self, health_data: Dict[str, Any]):
        """Send health alert to admins"""
        try:
            from telegram_bot.bot import bot
            from telegram_bot.core.config import settings
            
            alert_message = (
                "🚨 System Health Alert 🚨\n\n"
                f"Status: {health_data['status']}\n"
                f"Time: {health_data['timestamp']}\n\n"
                "Component Status:\n"
            )
            
            for component, data in health_data["components"].items():
                status = data["status"]
                error = data.get("error", "")
                alert_message += f"- {component}: {status}\n"
                if error:
                    alert_message += f"  Error: {error}\n"
                    
            alert_message += "\nSystem Metrics:\n"
            metrics = health_data["metrics"]
            alert_message += (
                f"- CPU: {metrics['cpu_percent']}%\n"
                f"- Memory: {metrics['memory_percent']}%\n"
                f"- Disk: {metrics['disk_percent']}%"
            )
            
            # Send to all admins
            for admin_id in settings.ADMIN_IDS:
                try:
                    await bot.send_message(admin_id, alert_message)
                except Exception as e:
                    logger.error(f"Error sending alert to admin {admin_id}: {e}")
                    
        except Exception as e:
            logger.error(f"Error sending health alert: {e}")

# Create global instance
background_tasks = BackgroundTaskManager()

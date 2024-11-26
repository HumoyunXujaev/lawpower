from prometheus_client import Counter, Histogram, Gauge, Summary
import psutil
from typing import Dict, Any, Optional
import logging
from datetime import datetime, timedelta
from sqlalchemy import select, func
import json
import asyncio
from telegram_bot.core.database import get_session
from telegram_bot.models import User, Question, Consultation, Payment
from telegram_bot.utils.cache import cache

logger = logging.getLogger(__name__)

class MetricsManager:
    """Comprehensive metrics management system"""
    
    def __init__(self):
        # System metrics
        self.cpu_usage = Gauge(
            'system_cpu_usage',
            'System CPU usage percentage'
        )
        self.memory_usage = Gauge(
            'system_memory_usage_bytes',
            'System memory usage in bytes'
        )
        self.disk_usage = Gauge(
            'system_disk_usage_bytes',
            'System disk usage in bytes'
        )
        
        # Application metrics
        self.requests_total = Counter(
            'app_requests_total',
            'Total HTTP requests',
            ['method', 'endpoint']
        )
        self.request_duration = Histogram(
            'app_request_duration_seconds',
            'HTTP request duration in seconds',
            ['method', 'endpoint']
        )
        
        # Bot metrics
        self.bot_messages = Counter(
            'bot_messages_total',
            'Total bot messages',
            ['type']
        )
        self.bot_callbacks = Counter(
            'bot_callbacks_total',
            'Total bot callbacks'
        )
        self.bot_errors = Counter(
            'bot_errors_total',
            'Total bot errors',
            ['type']
        )
        
        # Business metrics
        self.questions_total = Counter(
            'bot_questions_total',
            'Total questions asked',
            ['language']
        )
        self.answers_total = Counter(
            'bot_answers_total',
            'Total answers given',
            ['type']
        )
        self.consultations_total = Counter(
            'bot_consultations_total',
            'Total consultations',
            ['status']
        )
        self.payments_total = Counter(
            'bot_payments_total',
            'Total payments',
            ['status', 'provider']  
        )
        
        # Performance metrics
        self.response_times = Histogram(
            'bot_response_time_seconds',
            'Bot response time in seconds'
        )
        self.db_query_duration = Histogram(
            'bot_db_query_duration_seconds',
            'Database query duration in seconds'
        )
        self.cache_operations = Counter(
            'bot_cache_operations_total',
            'Total cache operations',
            ['operation', 'status']
        )
        
        # Start background collection
        asyncio.create_task(self._collect_metrics())
        
    async def _collect_metrics(self):
        """Periodically collect system metrics"""
        while True:
            try:
                await self.collect_system_metrics()
                await self.collect_business_metrics()
                await asyncio.sleep(60)  # Collect every minute
            except Exception as e:
                logger.error(f"Error collecting metrics: {e}")
                await asyncio.sleep(60)
                
    async def collect_system_metrics(self):
        """Collect system resource metrics"""
        try:
            # CPU metrics
            cpu_percent = psutil.cpu_percent()
            self.cpu_usage.set(cpu_percent)
            
            # Memory metrics
            memory = psutil.virtual_memory()
            self.memory_usage.set(memory.used)
            
            # Disk metrics
            disk = psutil.disk_usage('/')
            self.disk_usage.set(disk.used)
            
        except Exception as e:
            logger.error(f"Error collecting system metrics: {e}")
            
    async def collect_business_metrics(self):
        """Collect business metrics"""
        try:
            async with get_session() as session:
                # Questions metrics
                questions = await session.execute(
                    select(
                        Question.language,
                        func.count(Question.id)
                    ).group_by(Question.language)
                )
                for lang, count in questions:
                    self.questions_total.labels(language=lang).inc(count)
                
                # Consultations metrics
                consultations = await session.execute(
                    select(
                        Consultation.status,
                        func.count(Consultation.id)
                    ).group_by(Consultation.status)
                )
                for status, count in consultations:
                    self.consultations_total.labels(status=status.value).inc(count)
                    
                # Payments metrics
                payments = await session.execute(
                    select(
                        Payment.status,
                        Payment.provider,
                        func.count(Payment.id)
                    ).group_by(Payment.status, Payment.provider)
                )
                for status, provider, count in payments:
                    self.payments_total.labels(
                        status=status.value,
                        provider=provider.value
                    ).inc(count)
                    
        except Exception as e:
            logger.error(f"Error collecting business metrics: {e}")
    
    def track_request(self, method: str, endpoint: str, duration: float):
        """Track HTTP request"""
        self.requests_total.labels(
            method=method,
            endpoint=endpoint
        ).inc()
        
        self.request_duration.labels(
            method=method,
            endpoint=endpoint
        ).observe(duration)
        
    def track_bot_message(self, message_type: str):
        """Track bot message"""
        self.bot_messages.labels(type=message_type).inc()
        
    def track_bot_callback(self):
        """Track bot callback"""
        self.bot_callbacks.inc()
        
    def track_bot_error(self, error_type: str):
        """Track bot error"""
        self.bot_errors.labels(type=error_type).inc()
        
    def track_response_time(self, duration: float):
        """Track bot response time"""
        self.response_times.observe(duration)
        
    def track_db_query(self, duration: float):
        """Track database query duration"""
        self.db_query_duration.observe(duration)
        
    def track_cache(self, operation: str, hit: bool = None):
        """Track cache operation"""
        status = 'hit' if hit else 'miss' if hit is not None else 'unknown'
        self.cache_operations.labels(
            operation=operation,
            status=status
        ).inc()

# Create metrics manager instance
metrics_manager = MetricsManager()

__all__ = ['metrics_manager']
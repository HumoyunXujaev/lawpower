from typing import AsyncGenerator, Optional, Dict, Any, List
from sqlalchemy.ext.asyncio import (
    create_async_engine,
    AsyncSession,
    AsyncEngine,
    async_sessionmaker
)
from sqlalchemy.pool import AsyncAdaptedQueuePool
from sqlalchemy import event, text
from sqlalchemy.exc import SQLAlchemyError
from contextlib import asynccontextmanager
import logging
from datetime import datetime
import json

from telegram_bot.core.config import settings
from telegram_bot.core.monitoring import metrics_manager
from telegram_bot.models.base import Base
from telegram_bot.core.errors import DatabaseError

from typing import AsyncGenerator
from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker, AsyncSession
from telegram_bot.core.config import settings
from telegram_bot.models.base import Base
import logging

logger = logging.getLogger(__name__)

# Create async engine
engine = create_async_engine(
    settings.DATABASE_URL,
    echo=settings.DB_ECHO,
    pool_size=settings.DB_POOL_SIZE,
    max_overflow=settings.DB_MAX_OVERFLOW
)

# Create session factory
async_session_maker = async_sessionmaker(
    engine,
    expire_on_commit=False,
    class_=AsyncSession
)

async def init_db():
    """Initialize database"""
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

async def get_session() -> AsyncGenerator[AsyncSession, None]:
    """Get database session"""
    async with async_session_maker() as session:
        try:
            yield session
        finally:
            await session.close()

async def close_db():
    """Close database connections"""
    await engine.dispose()


logger = logging.getLogger(__name__)

class DatabaseManager:
    """Enhanced database manager"""
    
    def __init__(self):
        self._engine: Optional[AsyncEngine] = None
        self._sessionmaker: Optional[async_sessionmaker] = None
        self.Base = Base
        
    async def init(self) -> None:
        """Initialize database connection"""
        if not self._engine:
            # Create engine
            self._engine = create_async_engine(
                settings.DATABASE_URL,
                echo=settings.DB_ECHO,
                pool_size=settings.DB_POOL_SIZE,
                max_overflow=settings.DB_MAX_OVERFLOW,
                poolclass=AsyncAdaptedQueuePool,
                pool_pre_ping=True,
                pool_timeout=settings.DB_POOL_TIMEOUT,
                pool_recycle=settings.DB_POOL_RECYCLE,
                json_serializer=json.dumps,
                json_deserializer=json.loads,
                connect_args={
                    "statement_timeout": settings.DB_STATEMENT_TIMEOUT,
                    "command_timeout": settings.DB_COMMAND_TIMEOUT
                }
            )
            
            # Create session maker
            self._sessionmaker = async_sessionmaker(
                self._engine,
                class_=AsyncSession,
                expire_on_commit=False,
                autoflush=False
            )
            
            # Add event listeners
            event.listen(
                self._engine.sync_engine,
                'before_cursor_execute',
                self._before_cursor_execute
            )
            event.listen(
                self._engine.sync_engine,
                'after_cursor_execute',
                self._after_cursor_execute
            )
            
            logger.info("Database engine initialized")
            
    async def create_all(self) -> None:
        """Create all database tables"""
        if not self._engine:
            await self.init()
            
        async with self._engine.begin() as conn:
            await conn.run_sync(self.Base.metadata.create_all)
            
        logger.info("Database tables created")
        
    async def drop_all(self) -> None:
        """Drop all database tables"""
        if self._engine:
            async with self._engine.begin() as conn:
                await conn.run_sync(self.Base.metadata.drop_all)
                
            logger.info("Database tables dropped")
            
    @asynccontextmanager
    async def session(self) -> AsyncGenerator[AsyncSession, None]:
        """Get database session"""
        if not self._sessionmaker:
            await self.init()
            
        session: AsyncSession = self._sessionmaker()
        try:
            yield session
        except SQLAlchemyError as e:
            logger.error(f"Database session error: {e}")
            await session.rollback()
            raise DatabaseError(str(e))
        finally:
            await session.close()
            
    async def close(self) -> None:
        """Close database connections"""
        if self._engine:
            await self._engine.dispose()
            self._engine = None
            self._sessionmaker = None
            logger.info("Database connections closed")
            
    async def get_stats(self) -> Dict[str, Any]:
        """Get database statistics"""
        try:
            async with self.session() as session:
                # Get general stats
                result = await session.execute(text("""
                    SELECT 
                        pg_database_size(current_database()) as db_size,
                        pg_size_pretty(pg_database_size(current_database())) as db_size_pretty,
                        (SELECT count(*) FROM pg_stat_activity) as connections,
                        (SELECT count(*) FROM pg_stat_activity WHERE state = 'active') as active_connections,
                        age(datfrozenxid) as transaction_age
                    FROM pg_database 
                    WHERE datname = current_database()
                """))
                stats = result.mappings().first()
                
                # Get table stats
                result = await session.execute(text("""
                    SELECT 
                        schemaname,
                        relname,
                        n_live_tup as row_count,
                        pg_size_pretty(pg_total_relation_size(relid)) as total_size
                    FROM pg_stat_user_tables
                    ORDER BY n_live_tup DESC
                """))
                tables = result.mappings().all()
                
                return {
                    "database_size": stats["db_size"],
                    "database_size_pretty": stats["db_size_pretty"],
                    "total_connections": stats["connections"],
                    "active_connections": stats["active_connections"],
                    "transaction_age": stats["transaction_age"],
                    "tables": [dict(t) for t in tables],
                    "timestamp": datetime.utcnow().isoformat()
                }
                
        except Exception as e:
            logger.error(f"Error getting database stats: {e}")
            return {}
            
    async def check_connection(self) -> bool:
        """Check database connection"""
        try:
            async with self.session() as session:
                await session.execute(text("SELECT 1"))
                return True
        except Exception as e:
            logger.error(f"Database connection check failed: {e}")
            return False
            
    async def vacuum(self, table: Optional[str] = None) -> None:
        """Run VACUUM on database or specific table"""
        try:
            async with self.session() as session:
                if table:
                    await session.execute(
                        text(f"VACUUM ANALYZE {table}")
                    )
                else:
                    await session.execute(text("VACUUM ANALYZE"))
                    
            logger.info(f"VACUUM completed for {table or 'all tables'}")
            
        except Exception as e:
            logger.error(f"Error running VACUUM: {e}")
            
    async def backup(self, backup_path: str) -> bool:
        """Create database backup"""
        try:
            import subprocess
            
            # Create backup command
            command = [
                'pg_dump',
                '-h', settings.DB_HOST,
                '-p', str(settings.DB_PORT),
                '-U', settings.DB_USER,
                '-F', 'c',  # Custom format
                '-f', backup_path,
                settings.DB_NAME
            ]
            
            # Set password environment variable
            env = {
                'PGPASSWORD': settings.DB_PASSWORD.get_secret_value()
            }
            
            # Run backup
            process = subprocess.run(
                command,
                env=env,
                capture_output=True,
                text=True
            )
            
            if process.returncode == 0:
                logger.info(f"Database backup created at {backup_path}")
                return True
            else:
                logger.error(f"Backup error: {process.stderr}")
                return False
                
        except Exception as e:
            logger.error(f"Error creating backup: {e}")
            return False
            
    async def restore(self, backup_path: str) -> bool:
        """Restore database from backup"""
        try:
            import subprocess
            
            # Create restore command
            command = [
                'pg_restore',
                '-h', settings.DB_HOST,
                '-p', str(settings.DB_PORT),
                '-U', settings.DB_USER,
                '-d', settings.DB_NAME,
                '-c',  # Clean (drop) database objects before recreating
                backup_path
            ]
            
            # Set password environment variable
            env = {
                'PGPASSWORD': settings.DB_PASSWORD.get_secret_value()
            }
            
            # Run restore
            process = subprocess.run(
                command,
                env=env,
                capture_output=True,
                text=True
            )
            
            if process.returncode == 0:
                logger.info(f"Database restored from {backup_path}")
                return True
            else:
                logger.error(f"Restore error: {process.stderr}")
                return False
                
        except Exception as e:
            logger.error(f"Error restoring backup: {e}")
            return False
            
    def _before_cursor_execute(
        self,
        conn,
        cursor,
        statement,
        parameters,
        context,
        executemany
    ):
        """Handler for before cursor execute event"""
        context._query_start_time = datetime.utcnow()
        metrics_manager.track_db_query(
            operation=statement.split()[0].lower()
        )
        
    def _after_cursor_execute(
        self,
        conn,
        cursor,
        statement,
        parameters,
        context,
        executemany
    ):
        """Handler for after cursor execute event"""
        total_time = (datetime.utcnow() - context._query_start_time).total_seconds()
        
        # Track query duration
        metrics_manager.track_db_query_duration(total_time)
        
        # Log slow queries
        if total_time > settings.DB_SLOW_QUERY_THRESHOLD:
            logger.warning(
                f"Slow query detected: {total_time:.2f}s\n"
                f"Query: {statement}\n"
                f"Parameters: {parameters}"
            )

class DatabaseSession:
    """Database session context manager"""
    
    def __init__(self, session: AsyncSession):
        self.session = session
        
    async def __aenter__(self) -> AsyncSession:
        return self.session
        
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        if exc_type is not None:
            await self.session.rollback()
        await self.session.close()

class QueryBuilder:
    """SQL query builder helper"""
    
    def __init__(self, model):
        self.model = model
        self.query = None
        
    def select(self, *columns):
        """Start SELECT query"""
        from sqlalchemy import select
        self.query = select(*columns or [self.model])
        return self
        
    def where(self, *criteria):
        """Add WHERE clause"""
        if self.query is not None:
            self.query = self.query.where(*criteria)
        return self
        
    def order_by(self, *columns):
        """Add ORDER BY clause"""
        if self.query is not None:
            self.query = self.query.order_by(*columns)
        return self
        
    def limit(self, limit: int):
        """Add LIMIT clause"""
        if self.query is not None:
            self.query = self.query.limit(limit)
        return self
        
    def offset(self, offset: int):
        """Add OFFSET clause"""
        if self.query is not None:
            self.query = self.query.offset(offset)
        return self
        
    def join(self, *props, **kwargs):
        """Add JOIN clause"""
        if self.query is not None:
            self.query = self.query.join(*props, **kwargs)
        return self
        
    def get_query(self):
        """Get built query"""
        return self.query

class BulkOperations:
    """Helper for bulk database operations"""
    
    def __init__(self, session: AsyncSession):
        self.session = session
        
    async def bulk_insert(
        self,
        model,
        items: List[Dict[str, Any]],
        chunk_size: int = 1000
    ) -> int:
        """Bulk insert records"""
        inserted = 0
        
        # Split items into chunks
        for i in range(0, len(items), chunk_size):
            chunk = items[i:i + chunk_size]
            
            # Create model instances
            instances = [model(**item) for item in chunk]
            
            # Add to session
            self.session.add_all(instances)
            
            try:
                await self.session.commit()
                inserted += len(chunk)
            except Exception as e:
                await self.session.rollback()
                logger.error(f"Error in bulk insert: {e}")
                raise
                
        return inserted
        
    async def bulk_update(
        self,
        model,
        items: List[Dict[str, Any]],
        chunk_size: int = 1000
    ) -> int:
        """Bulk update records"""
        from sqlalchemy import update
        updated = 0
        
        # Split items into chunks
        for i in range(0, len(items), chunk_size):
            chunk = items[i:i + chunk_size]
            
            try:
                # Update chunk
                stmt = update(model).where(
                    model.id.in_([item['id'] for item in chunk])
                )
                result = await self.session.execute(stmt)
                updated += result.rowcount
                
                await self.session.commit()
            except Exception as e:
                await self.session.rollback()
                logger.error(f"Error in bulk update: {e}")
                raise
                
        return updated

# Create global instances
db = DatabaseManager()
query_builder = QueryBuilder

async def get_session() -> AsyncGenerator[AsyncSession, None]:
    """Get database session - dependency for FastAPI"""
    async with db.session() as session:
        yield session

__all__ = [
    'db',
    'get_session',
    'DatabaseSession',
    'QueryBuilder',
    'BulkOperations'
]
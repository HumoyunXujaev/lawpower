from datetime import datetime
from typing import Any, Dict, List, Optional, TypeVar, Generic
from sqlalchemy import Column, Integer, DateTime, func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import as_declarative, declared_attr
from sqlalchemy.dialects.postgresql import JSONB
import logging

from telegram_bot.utils.cache import cache
from telegram_bot.core.monitoring import metrics_manager

logger = logging.getLogger(__name__)

ModelType = TypeVar("ModelType")

@as_declarative()
class Base:
    """Base model class"""
    id: Any
    __name__: str
    
    @declared_attr
    def __tablename__(cls) -> str:
        return cls.__name__.lower()
        
    def to_dict(self) -> Dict:
        """Convert model to dictionary"""
        return {
            column.name: getattr(self, column.name)
            for column in self.__table__.columns
        }
    
    @classmethod 
    def from_dict(cls, data: Dict) -> "Base":
        """Create model from dictionary"""
        return cls(**data)

class TimeStampedBase(Base):
    """Base class with timestamp fields"""
    __abstract__ = True
    
    id = Column(Integer, primary_key=True)
    created_at = Column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False
    )
    updated_at = Column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False
    )

class SoftDeleteMixin:
    """Mixin for soft delete"""
    deleted_at = Column(DateTime(timezone=True), nullable=True)
    
    def soft_delete(self) -> None:
        """Mark record as deleted"""
        self.deleted_at = datetime.utcnow()
    
    @property
    def is_deleted(self) -> bool:
        """Check if record is deleted"""
        return self.deleted_at is not None

class MetadataMixin:
    """Mixin for metadata"""
    metadata_ = Column(
        'metadata',
        JSONB,
        nullable=False,
        server_default='{}'
    )
    
    def update_metadata(self, data: Dict) -> None:
        """Update metadata"""
        self.metadata_.update(data)
    
    def get_metadata(self, key: str, default: Any = None) -> Any:
        """Get metadata value"""
        return self.metadata_.get(key, default)

class AuditMixin:
    """Mixin for audit fields"""
    created_by = Column(Integer, nullable=True)
    updated_by = Column(Integer, nullable=True)
    
    def set_created_by(self, user_id: int) -> None:
        """Set created by"""
        self.created_by = user_id
    
    def set_updated_by(self, user_id: int) -> None:
        """Set updated by"""
        self.updated_by = user_id

class BaseService(Generic[ModelType]):
    """Base service with CRUD operations"""
    
    def __init__(
        self,
        model: type[ModelType],
        session: AsyncSession
    ):
        self.model = model
        self.session = session
        
    async def get(self, id: int) -> Optional[ModelType]:
        """Get by ID with caching"""
        # Try cache
        cache_key = f"{self.model.__tablename__}:{id}"
        cached = await cache.get(cache_key)
        if cached:
            metrics_manager.track_cache('get', hit=True)
            return self.model.from_dict(cached)
            
        # Get from database
        start = datetime.utcnow()
        result = await self.session.execute(
            select(self.model).filter_by(id=id)
        )
        metrics_manager.track_db_query(
            (datetime.utcnow() - start).total_seconds()
        )
        
        instance = result.scalar_one_or_none()
        if instance:
            await cache.set(cache_key, instance.to_dict())
            
        metrics_manager.track_cache('get', hit=False)
        return instance
    
    async def create(self, **data) -> ModelType:
        """Create new record"""
        instance = self.model(**data)
        
        # Set audit fields
        if isinstance(instance, AuditMixin):
            instance.created_by = data.get('created_by')
            
        self.session.add(instance)
        
        start = datetime.utcnow()
        await self.session.commit()
        await self.session.refresh(instance)
        metrics_manager.track_db_query(
            (datetime.utcnow() - start).total_seconds()
        )
        
        # Cache new instance
        cache_key = f"{self.model.__tablename__}:{instance.id}"
        await cache.set(cache_key, instance.to_dict())
        
        return instance
    
    async def update(
        self,
        id: int,
        **data
    ) -> Optional[ModelType]:
        """Update record"""
        instance = await self.get(id)
        if not instance:
            return None
            
        # Update fields
        for key, value in data.items():
            setattr(instance, key, value)
            
        # Set audit fields
        if isinstance(instance, AuditMixin):
            instance.updated_by = data.get('updated_by')
            
        start = datetime.utcnow()
        await self.session.commit()
        await self.session.refresh(instance)
        metrics_manager.track_db_query(
            (datetime.utcnow() - start).total_seconds()
        )
        
        # Update cache
        cache_key = f"{self.model.__tablename__}:{id}" 
        await cache.set(cache_key, instance.to_dict())
        
        return instance
    
    async def delete(self, id: int) -> bool:
        """Delete record"""
        instance = await self.get(id)
        if not instance:
            return False
            
        # Soft delete if supported
        if isinstance(instance, SoftDeleteMixin):
            instance.soft_delete()
            await self.session.commit()
        else:
            await self.session.delete(instance)
            await self.session.commit()
            
        # Clear cache
        cache_key = f"{self.model.__tablename__}:{id}"
        await cache.delete(cache_key)
        
        return True
    
    async def list(
        self,
        offset: int = 0,
        limit: int = 100,
        filters: Dict = None,
        order_by: str = None
    ) -> List[ModelType]:
        """Get filtered list"""
        query = select(self.model)
        
        # Apply filters
        if filters:
            for field, value in filters.items():
                if value is not None:
                    query = query.filter(getattr(self.model, field) == value)
                    
        # Apply ordering
        if order_by:
            if order_by.startswith('-'):
                query = query.order_by(getattr(self.model, order_by[1:]).desc())
            else:
                query = query.order_by(getattr(self.model, order_by).asc())
                
        # Apply pagination
        query = query.offset(offset).limit(limit)
        
        start = datetime.utcnow()
        result = await self.session.execute(query)
        metrics_manager.track_db_query(
            (datetime.utcnow() - start).total_seconds()
        )
        
        return list(result.scalars().all())
    
    async def count(self, filters: Dict = None) -> int:
        """Count records"""
        query = select(func.count()).select_from(self.model)
        
        if filters:
            for field, value in filters.items():
                if value is not None:
                    query = query.filter(getattr(self.model, field) == value)
                    
        start = datetime.utcnow()
        result = await self.session.execute(query)
        metrics_manager.track_db_query(
            (datetime.utcnow() - start).total_seconds()
        )
        
        return result.scalar_one()

# Export classes
__all__ = [
    'Base',
    'TimeStampedBase', 
    'SoftDeleteMixin',
    'MetadataMixin',
    'AuditMixin',
    'BaseService'
]
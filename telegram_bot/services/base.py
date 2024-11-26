from typing import TypeVar, Type, Generic, Optional, List, Dict, Any
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from sqlalchemy import update, delete, func
import logging
from datetime import datetime

from telegram_bot.core.cache import cache_service as cache

from telegram_bot.models.base import Base
from telegram_bot.core.errors import (
    DatabaseError,
    ValidationError,
    NotFoundError
)

ModelType = TypeVar("ModelType", bound=Base)
logger = logging.getLogger(__name__)

class BaseService(Generic[ModelType]):
    """Enhanced base service with improved error handling and validation"""
    
    def __init__(
        self,
        model: Type[ModelType],
        session: AsyncSession,
        cache: Optional[Cache] = None
    ):
        self.model = model
        self.session = session
        self.cache = cache or Cache()
        
    async def get(self, id: int) -> Optional[ModelType]:
        """Get single record by ID with caching"""
        try:
            # Try cache first
            cache_key = f"{self.model.__tablename__}:{id}"
            cached = await self.cache.get(cache_key)
            if cached:
                return self.model(**cached)
            
            # Get from database
            result = await self.session.execute(
                select(self.model).filter(self.model.id == id)
            )
            instance = result.scalar_one_or_none()
            
            # Cache if found
            if instance:
                await self.cache.set(
                    cache_key,
                    instance.to_dict(),
                    timeout=3600
                )
            
            return instance
            
        except Exception as e:
            logger.error(f"Error getting {self.model.__name__} {id}: {e}")
            raise DatabaseError(f"Error retrieving {self.model.__name__}")
            
    async def create(self, **data) -> ModelType:
        """Create new record with validation"""
        try:
            # Validate data
            self.validate_create(data)
            
            # Create instance
            instance = self.model(**data)
            self.session.add(instance)
            await self.session.commit()
            await self.session.refresh(instance)
            
            # Cache new instance
            cache_key = f"{self.model.__tablename__}:{instance.id}"
            await self.cache.set(
                cache_key,
                instance.to_dict(),
                timeout=3600
            )
            
            return instance
            
        except ValidationError:
            raise
        except Exception as e:
            logger.error(f"Error creating {self.model.__name__}: {e}")
            raise DatabaseError(f"Error creating {self.model.__name__}")
            
    async def update(
        self,
        id: int,
        **data
    ) -> ModelType:
        """Update record with validation"""
        try:
            # Get existing
            instance = await self.get(id)
            if not instance:
                raise NotFoundError(f"{self.model.__name__} not found")
                
            # Validate data
            self.validate_update(instance, data)
            
            # Update attributes
            for field, value in data.items():
                setattr(instance, field, value)
                
            await self.session.commit()
            await self.session.refresh(instance)
            
            # Update cache
            cache_key = f"{self.model.__tablename__}:{id}"
            await self.cache.set(
                cache_key,
                instance.to_dict(),
                timeout=3600
            )
            
            return instance
            
        except (ValidationError, NotFoundError):
            raise
        except Exception as e:
            logger.error(f"Error updating {self.model.__name__} {id}: {e}")
            raise DatabaseError(f"Error updating {self.model.__name__}")
            
    async def delete(self, id: int) -> bool:
        """Delete record"""
        try:
            instance = await self.get(id)
            if not instance:
                raise NotFoundError(f"{self.model.__name__} not found")
                
            await self.session.delete(instance)
            await self.session.commit()
            
            # Delete from cache
            cache_key = f"{self.model.__tablename__}:{id}"
            await self.cache.delete(cache_key)
            
            return True
            
        except NotFoundError:
            raise
        except Exception as e:
            logger.error(f"Error deleting {self.model.__name__} {id}: {e}")
            raise DatabaseError(f"Error deleting {self.model.__name__}")
            
    async def get_many(
        self,
        filters: Dict = None,
        order_by: str = None,
        skip: int = 0,
        limit: int = 100
    ) -> List[ModelType]:
        """Get filtered, ordered and paginated records"""
        try:
            query = select(self.model)
            
            # Apply filters
            if filters:
                for field, value in filters.items():
                    if value is not None:
                        if isinstance(value, (list, tuple)):
                            query = query.filter(
                                getattr(self.model, field).in_(value)
                            )
                        else:
                            query = query.filter(
                                getattr(self.model, field) == value
                            )
                            
            # Apply ordering
            if order_by:
                if order_by.startswith("-"):
                    query = query.order_by(
                        getattr(self.model, order_by[1:]).desc()
                    )
                else:
                    query = query.order_by(
                        getattr(self.model, order_by).asc()
                    )
                    
            # Apply pagination
            query = query.offset(skip).limit(limit)
            
            result = await self.session.execute(query)
            return list(result.scalars().all())
            
        except Exception as e:
            logger.error(f"Error getting {self.model.__name__} list: {e}")
            raise DatabaseError(f"Error retrieving {self.model.__name__} list")
            
    async def count(self, filters: Dict = None) -> int:
        """Count filtered records"""
        try:
            query = select(func.count(self.model.id))
            
            # Apply filters
            if filters:
                for field, value in filters.items():
                    if value is not None:
                        if isinstance(value, (list, tuple)):
                            query = query.filter(
                                getattr(self.model, field).in_(value)
                            )
                        else:
                            query = query.filter(
                                getattr(self.model, field) == value
                            )
                            
            result = await self.session.execute(query)
            return result.scalar_one()
            
        except Exception as e:
            logger.error(f"Error counting {self.model.__name__}: {e}")
            raise DatabaseError(f"Error counting {self.model.__name__}")
    
    def validate_create(self, data: Dict) -> None:
        """Validate create data"""
        pass
        
    def validate_update(self, instance: ModelType, data: Dict) -> None:
        """Validate update data"""
        pass
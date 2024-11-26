from datetime import datetime
from typing import Any, Dict, List, Optional, TypeVar, Type
from sqlalchemy import Column, Integer, DateTime, String, func, MetaData,Boolean
from sqlalchemy.ext.declarative import declared_attr, declarative_base
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import declared_attr
import logging
from telegram_bot.core.errors import ValidationError

logger = logging.getLogger(__name__)

# Naming convention for constraints
convention = {
    "ix": "ix_%(column_0_label)s",
    "uq": "uq_%(table_name)s_%(column_0_name)s",
    "ck": "ck_%(table_name)s_%(constraint_name)s",
    "fk": "fk_%(table_name)s_%(column_0_name)s_%(referred_table_name)s",
    "pk": "pk_%(table_name)s"
}

metadata = MetaData(naming_convention=convention)
Base = declarative_base(metadata=metadata)

class TimestampMixin:
    """Mixin for models with timestamp fields"""
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False)

class SoftDeleteMixin:
    """Mixin for soft delete functionality"""
    deleted_at = Column(DateTime(timezone=True), nullable=True)
    is_deleted = Column(Boolean, default=False, server_default='false', nullable=False)
    deleted_by = Column(Integer, nullable=True)

    def soft_delete(self, user_id: Optional[int] = None) -> None:
        """Soft delete record"""
        self.deleted_at = datetime.utcnow()
        self.is_deleted = True
        if user_id:
            self.deleted_by = user_id

    def restore(self) -> None:
        """Restore soft deleted record"""
        self.deleted_at = None
        self.is_deleted = False
        self.deleted_by = None

class MetadataMixin:
    """Mixin for models with metadata field"""
    metadata_ = Column('metadata', JSONB, nullable=False, server_default='{}')

    def update_metadata(self, data: Dict[str, Any]) -> None:
        """Update metadata dictionary"""
        if not self.metadata_:
            self.metadata_ = {}
        self.metadata_.update(data)

    def get_metadata(self, key: str, default: Any = None) -> Any:
        """Get metadata value by key"""
        return self.metadata_.get(key, default)

class AuditMixin:
    """Mixin for audit fields"""
    created_by_id = Column(Integer, nullable=True)
    updated_by_id = Column(Integer, nullable=True)
    created_ip = Column(String, nullable=True)
    updated_ip = Column(String, nullable=True)
    revision = Column(Integer, default=1, nullable=False)

    def update_audit(self, user_id: Optional[int] = None, ip: Optional[str] = None) -> None:
        """Update audit fields"""
        self.updated_by_id = user_id
        self.updated_ip = ip
        self.revision += 1

class BaseModel(Base):
    """Base model with common functionality"""
    __abstract__ = True

    id = Column(Integer, primary_key=True)

    @declared_attr
    def __tablename__(cls) -> str:
        """Generate table name from class name"""
        return cls.__name__.lower()

    def to_dict(self, exclude: Optional[List[str]] = None) -> Dict[str, Any]:
        """Convert model to dictionary"""
        data = {}
        exclude = exclude or []
        
        for column in self.__table__.columns:
            if column.name not in exclude:
                value = getattr(self, column.name)
                if isinstance(value, datetime):
                    value = value.isoformat()
                data[column.name] = value
        return data

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "BaseModel":
        """Create model instance from dictionary"""
        return cls(**{
            k: v for k, v in data.items() 
            if k in cls.__table__.columns
        })

    def update(self, data: Dict[str, Any]) -> None:
        """Update model attributes"""
        for key, value in data.items():
            if hasattr(self, key):
                setattr(self, key, value)

    def __repr__(self) -> str:
        """String representation"""
        return f"<{self.__class__.__name__}(id={self.id})>"

class FullAuditModel(BaseModel, TimestampMixin, SoftDeleteMixin, MetadataMixin, AuditMixin):
    """Base model with all audit functionality"""
    __abstract__ = True

# Type variable for models
ModelType = TypeVar("ModelType", bound=BaseModel)

# Export all
__all__ = [
    'Base',
    'BaseModel',
    'FullAuditModel',
    'TimestampMixin',
    'SoftDeleteMixin',
    'MetadataMixin', 
    'AuditMixin',
    'ModelType'
]
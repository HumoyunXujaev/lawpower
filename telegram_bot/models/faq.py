from sqlalchemy import (
    Column, String, Text, Boolean, Integer, ForeignKey,
    Index, UniqueConstraint, Enum as SQLEnum, DateTime,
    CheckConstraint
)
from sqlalchemy.orm import relationship
from sqlalchemy.dialects.postgresql import ARRAY, JSONB, TSVECTOR
from datetime import datetime
from enum import Enum

from telegram_bot.models.base import BaseModel, AuditMixin, MetadataMixin

class FAQCategory(str, Enum):
    GENERAL = 'general'
    LEGAL = 'legal'
    PAYMENT = 'payment'
    CONSULTATION = 'consultation'
    TECHNICAL = 'technical'
    BUSINESS = 'business'
    FAMILY = 'family'
    PROPERTY = 'property'
    OTHER = 'other'

class FAQ(BaseModel, AuditMixin, MetadataMixin):
    """Enhanced FAQ model with multilingual support and analytics"""
    __tablename__ = 'faqs'

    # Core fields
    category_id = Column(Integer, ForeignKey('faq_categories.id', ondelete='SET NULL'))
    parent_id = Column(Integer, ForeignKey('faqs.id', ondelete='SET NULL'))
    order = Column(Integer, default=0)

    # Content - Uzbek
    title_uz = Column(String, nullable=False)
    question_uz = Column(Text, nullable=False)
    answer_uz = Column(Text, nullable=False)
    short_answer_uz = Column(String)

    # Content - Russian
    title_ru = Column(String, nullable=False)
    question_ru = Column(Text, nullable=False)
    answer_ru = Column(Text, nullable=False)
    short_answer_ru = Column(String)

    # Status and visibility
    is_published = Column(Boolean, default=True)
    is_featured = Column(Boolean, default=False)
    publish_date = Column(DateTime(timezone=True))
    unpublish_date = Column(DateTime(timezone=True))
    last_reviewed_at = Column(DateTime(timezone=True))
    last_updated_at = Column(DateTime(timezone=True))
    
    # Search optimization
    search_vector = Column(TSVECTOR)
    tags = Column(ARRAY(String), default=[])
    keywords = Column(ARRAY(String), default=[])
    related_faqs = Column(ARRAY(Integer), default=[])

    # Analytics
    view_count = Column(Integer, default=0)
    helpful_count = Column(Integer, default=0)
    not_helpful_count = Column(Integer, default=0)
    search_count = Column(Integer, default=0)
    auto_answer_count = Column(Integer, default=0)

    # Rich content
    attachments = Column(JSONB, default=[])
    related_links = Column(JSONB, default=[])
    references = Column(JSONB, default=[])
    revision_history = Column(JSONB, default=[])

    # Relationships
    category = relationship('FAQCategory', back_populates='faqs')
    children = relationship(
        'FAQ',
        backref=relationship('parent', remote_side=[id]),
        cascade='all, delete-orphan'
    )
    feedback = relationship('FAQFeedback', back_populates='faq', cascade='all, delete-orphan')

    # Indexes and Constraints
    __table_args__ = (
        CheckConstraint(
            'length(question_uz) >= 10 AND length(question_ru) >= 10',
            name='question_min_length'
        ),
        CheckConstraint(
            'length(answer_uz) >= 20 AND length(answer_ru) >= 20',
            name='answer_min_length'
        ),
        Index('ix_faqs_category_id', category_id),
        Index('ix_faqs_parent_id', parent_id),
        Index('ix_faqs_order', order),
        Index('ix_faqs_is_published', is_published),
        Index('ix_faqs_search_vector', search_vector, postgresql_using='gin'),
        Index('ix_faqs_tags', tags, postgresql_using='gin')
    )

    def get_title(self, language: str) -> str:
        """Get localized title"""
        return getattr(self, f'title_{language}')

    def get_question(self, language: str) -> str:
        """Get localized question"""
        return getattr(self, f'question_{language}')

    def get_answer(self, language: str) -> str:
        """Get localized answer"""
        return getattr(self, f'answer_{language}')

    def get_short_answer(self, language: str) -> str:
        """Get localized short answer"""
        return getattr(self, f'short_answer_{language}')

    def update_content(
        self,
        language: str,
        title: str = None,
        question: str = None,
        answer: str = None,
        short_answer: str = None,
        editor_id: int = None
    ) -> None:
        """Update FAQ content with revision tracking"""
        if not self.revision_history:
            self.revision_history = []
            
        # Save current version to history
        self.revision_history.append({
            'editor_id': editor_id,
            'timestamp': datetime.utcnow().isoformat(),
            'changes': {
                f'title_{language}': getattr(self, f'title_{language}'),
                f'question_{language}': getattr(self, f'question_{language}'),
                f'answer_{language}': getattr(self, f'answer_{language}'),
                f'short_answer_{language}': getattr(self, f'short_answer_{language}')
            }
        })
        
        # Update content
        if title:
            setattr(self, f'title_{language}', title)
        if question:
            setattr(self, f'question_{language}', question)
        if answer:
            setattr(self, f'answer_{language}', answer)
        if short_answer:
            setattr(self, f'short_answer_{language}', short_answer)
            
        self.last_updated_at = datetime.utcnow()

    def increment_view(self) -> None:
        """Increment view counter"""
        self.view_count += 1
        self.metadata['last_viewed'] = datetime.utcnow().isoformat()

    def increment_search(self) -> None:
        """Increment search counter"""
        self.search_count += 1
        self.metadata['last_searched'] = datetime.utcnow().isoformat()

    def mark_helpful(self, is_helpful: bool) -> None:
        """Mark FAQ as helpful/not helpful"""
        if is_helpful:
            self.helpful_count += 1
        else:
            self.not_helpful_count += 1

    @property
    def helpfulness_ratio(self) -> float:
        """Calculate helpfulness ratio"""
        total = self.helpful_count + self.not_helpful_count
        return self.helpful_count / total if total > 0 else 0

    @property
    def is_active(self) -> bool:
        """Check if FAQ is currently active"""
        now = datetime.utcnow()
        return (
            self.is_published and
            (not self.publish_date or self.publish_date <= now) and
            (not self.unpublish_date or self.unpublish_date > now)
        )

class FAQFeedback(BaseModel):
    """FAQ feedback model"""
    __tablename__ = 'faq_feedback'

    faq_id = Column(Integer, ForeignKey('faqs.id', ondelete='CASCADE'), nullable=False)
    user_id = Column(Integer, ForeignKey('users.id', ondelete='CASCADE'), nullable=False)
    is_helpful = Column(Boolean, nullable=False)
    feedback_text = Column(Text)
    feedback_type = Column(String, default='general')
    rating = Column(Integer)
    metadata = Column(JSONB, default={})

    # Additional fields
    platform = Column(String)
    user_agent = Column(String)
    session_id = Column(String)
    source = Column(String)  # Where the feedback was submitted from

    # Relationships
    faq = relationship('FAQ', back_populates='feedback')
    user = relationship('User', back_populates='faq_feedback')

    # Indexes and Constraints
    __table_args__ = (
        CheckConstraint('rating IS NULL OR (rating >= 1 AND rating <= 5)', name='valid_rating'),
        Index('ix_faq_feedback_faq_id', faq_id),
        Index('ix_faq_feedback_user_id', user_id),
        UniqueConstraint('faq_id', 'user_id', name='uq_faq_user_feedback')
    )

class FAQCategoryModel(BaseModel, AuditMixin):
    """FAQ category model"""
    __tablename__ = 'faq_categories'

    # Multilingual content
    name_uz = Column(String, nullable=False)
    name_ru = Column(String, nullable=False)
    description_uz = Column(Text)
    description_ru = Column(Text)

    # Display
    icon = Column(String)
    order = Column(Integer, default=0)
    parent_id = Column(Integer, ForeignKey('faq_categories.id', ondelete='SET NULL'))
    slug = Column(String, unique=True)
    color = Column(String)
    is_visible = Column(Boolean, default=True)

    # Status
    is_active = Column(Boolean, default=True)
    metadata = Column(JSONB, default={})

    # Relationships
    faqs = relationship('FAQ', back_populates='category', lazy='dynamic')
    children = relationship(
        'FAQCategoryModel',
        backref=relationship('parent', remote_side=[id]),
        cascade='all, delete-orphan'
    )

    # Indexes
    __table_args__ = (
        Index('ix_faq_categories_parent_id', parent_id),
        Index('ix_faq_categories_order', order),
        Index('ix_faq_categories_slug', slug),
        Index('ix_faq_categories_is_active', is_active)
    )

    def get_name(self, language: str) -> str:
        """Get localized name"""
        return getattr(self, f'name_{language}')

    def get_description(self, language: str) -> str:
        """Get localized description"""
        return getattr(self, f'description_{language}')

    @property
    def has_children(self) -> bool:
        """Check if category has child categories"""
        return bool(self.children)

    @property
    def faq_count(self) -> int:
        """Get count of active FAQs in this category"""
        return self.faqs.filter(FAQ.is_published == True).count()

# Export models
__all__ = [
    'FAQ',
    'FAQFeedback',
    'FAQCategoryModel',
    'FAQCategory'
]
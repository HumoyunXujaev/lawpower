from sqlalchemy import (
    Column, String, Integer, Boolean, ForeignKey, Text, 
    Float, Index, UniqueConstraint, Enum as SQLEnum,
    CheckConstraint, DateTime
)
from sqlalchemy.orm import relationship
from sqlalchemy.dialects.postgresql import ARRAY, JSONB, TSVECTOR
from sqlalchemy.ext.hybrid import hybrid_property
from enum import Enum
from datetime import datetime

from telegram_bot.models.base import BaseModel, SoftDeleteMixin, AuditMixin, MetadataMixin

class QuestionCategory(str, Enum):
    GENERAL = 'general'
    FAMILY = 'family'
    PROPERTY = 'property'
    BUSINESS = 'business'
    CRIMINAL = 'criminal'
    LABOR = 'labor'
    TAX = 'tax'
    CIVIL = 'civil'
    OTHER = 'other'

class QuestionStatus(str, Enum):
    NEW = 'new'
    PENDING = 'pending'
    ANSWERED = 'answered'
    ARCHIVED = 'archived'
    DELETED = 'deleted'

class Question(BaseModel, SoftDeleteMixin, AuditMixin, MetadataMixin):
    """Enhanced question model with search capabilities"""
    __tablename__ = 'questions'

    # Core fields
    user_id = Column(Integer, ForeignKey('users.id', ondelete='CASCADE'), nullable=False)
    question_text = Column(Text, nullable=False)
    category = Column(SQLEnum(QuestionCategory), nullable=True)
    language = Column(String(2), nullable=False)
    status = Column(SQLEnum(QuestionStatus), default=QuestionStatus.NEW, nullable=False)

    # Status and visibility
    is_answered = Column(Boolean, default=False)
    is_public = Column(Boolean, default=True)
    is_archived = Column(Boolean, default=False)
    answer_count = Column(Integer, default=0)
    auto_answered = Column(Boolean, default=False)

    # Search and categorization
    search_vector = Column(TSVECTOR)
    tags = Column(ARRAY(String), default=[])
    similar_questions = Column(ARRAY(Integer), default=[])

    # Analytics
    view_count = Column(Integer, default=0)
    helpful_count = Column(Integer, default=0)
    not_helpful_count = Column(Integer, default=0)
    avg_rating = Column(Float, default=0.0)
    search_count = Column(Integer, default=0)

    # Additional fields
    priority = Column(Integer, default=0)
    last_viewed_at = Column(DateTime(timezone=True))
    last_answered_at = Column(DateTime(timezone=True))
    context_data = Column(JSONB, default={})
    attachments = Column(JSONB, default=[])

    # Relationships
    user = relationship('User', back_populates='questions')
    answers = relationship('Answer', back_populates='question', cascade='all, delete-orphan')
    feedback = relationship('QuestionFeedback', back_populates='question', cascade='all, delete-orphan')

    # Indexes and Constraints
    __table_args__ = (
        CheckConstraint(
            'length(question_text) >= 10',
            name='question_min_length'
        ),
        Index('ix_questions_user_id', user_id),
        Index('ix_questions_category', category),
        Index('ix_questions_language', language),
        Index('ix_questions_status', status),
        Index('ix_questions_is_answered', is_answered),
        Index('ix_questions_search_vector', search_vector, postgresql_using='gin'),
        Index('ix_questions_tags', tags, postgresql_using='gin'),
    )

    def increment_view(self) -> None:
        """Increment view counter"""
        self.view_count += 1
        self.last_viewed_at = datetime.utcnow()

    def mark_helpful(self, is_helpful: bool = True) -> None:
        """Mark question as helpful"""
        if is_helpful:
            self.helpful_count += 1
        else:
            self.not_helpful_count += 1

    def update_answer_count(self) -> None:
        """Update answer count and status"""
        self.answer_count = len(self.answers)
        if self.answer_count > 0:
            self.is_answered = True
            self.last_answered_at = datetime.utcnow()
            self.status = QuestionStatus.ANSWERED

    def add_similar_question(self, question_id: int) -> None:
        """Add similar question reference"""
        if question_id not in (self.similar_questions or []):
            if self.similar_questions is None:
                self.similar_questions = []
            self.similar_questions.append(question_id)

    @property
    def helpfulness_ratio(self) -> float:
        """Calculate helpfulness ratio"""
        total = self.helpful_count + self.not_helpful_count
        return self.helpful_count / total if total > 0 else 0

    @property
    def is_recent(self) -> bool:
        """Check if question is recent (less than 24 hours old)"""
        if not self.created_at:
            return False
        return (datetime.utcnow() - self.created_at).days < 1

class Answer(BaseModel, AuditMixin, MetadataMixin):
    """Enhanced answer model with ratings and feedback"""
    __tablename__ = 'answers'

    # Core fields
    question_id = Column(Integer, ForeignKey('questions.id', ondelete='CASCADE'), nullable=False)
    user_id = Column(Integer, ForeignKey('users.id', ondelete='SET NULL'))
    answer_text = Column(Text, nullable=False)
    language = Column(String(2), nullable=False)

    # Answer type and status
    is_auto = Column(Boolean, default=False)
    is_accepted = Column(Boolean, default=False)
    is_public = Column(Boolean, default=True)
    is_edited = Column(Boolean, default=False)
    edit_count = Column(Integer, default=0)

    # Rating and feedback
    rating = Column(Float)
    rating_count = Column(Integer, default=0)
    helpful_count = Column(Integer, default=0)
    not_helpful_count = Column(Integer, default=0)

    # AI/ML related fields
    confidence_score = Column(Float)
    source_type = Column(String)  # 'ml', 'similar', 'faq'
    source_id = Column(Integer)  # Reference to source question/FAQ
    model_version = Column(String)
    processing_time = Column(Float)
    
    # Additional fields
    references = Column(JSONB, default=[])
    attachments = Column(JSONB, default=[])
    last_edited_at = Column(DateTime(timezone=True))
    edit_history = Column(JSONB, default=[])

    # Relationships
    question = relationship('Question', back_populates='answers')
    user = relationship('User', back_populates='answers')
    feedback = relationship('AnswerFeedback', back_populates='answer', cascade='all, delete-orphan')

    # Indexes and Constraints
    __table_args__ = (
        CheckConstraint(
            'length(answer_text) >= 20',
            name='answer_min_length'
        ),
        Index('ix_answers_question_id', question_id),
        Index('ix_answers_user_id', user_id),
        Index('ix_answers_rating', rating),
        Index('ix_answers_is_auto', is_auto),
    )

    def add_rating(self, rating: float, is_helpful: bool = None) -> None:
        """Add rating"""
        if self.rating is None:
            self.rating = rating
            self.rating_count = 1
        else:
            total = self.rating * self.rating_count + rating
            self.rating_count += 1
            self.rating = total / self.rating_count

        if is_helpful is not None:
            if is_helpful:
                self.helpful_count += 1
            else:
                self.not_helpful_count += 1

    def edit_answer(self, new_text: str, editor_id: int) -> None:
        """Edit answer text"""
        if not self.edit_history:
            self.edit_history = []
            
        self.edit_history.append({
            'previous_text': self.answer_text,
            'editor_id': editor_id,
            'edited_at': datetime.utcnow().isoformat()
        })
        
        self.answer_text = new_text
        self.is_edited = True
        self.edit_count += 1
        self.last_edited_at = datetime.utcnow()

class QuestionFeedback(BaseModel):
    """Question feedback model"""
    __tablename__ = 'question_feedback'

    # Core fields
    question_id = Column(Integer, ForeignKey('questions.id', ondelete='CASCADE'), nullable=False)
    user_id = Column(Integer, ForeignKey('users.id', ondelete='CASCADE'), nullable=False)
    rating = Column(Integer)
    feedback_text = Column(Text)
    is_helpful = Column(Boolean)
    
    # Additional fields
    category = Column(String)  # Categorization of feedback
    sentiment = Column(Float)  # Sentiment analysis score
    processed_feedback = Column(JSONB, default={})  # Processed feedback data
    metadata = Column(JSONB, default={})

    # Relationships
    question = relationship('Question', back_populates='feedback')
    user = relationship('User')

    # Indexes and Constraints
    __table_args__ = (
        CheckConstraint(
            'rating BETWEEN 1 AND 5',
            name='valid_rating_range'
        ),
        Index('ix_question_feedback_question_id', question_id),
        Index('ix_question_feedback_user_id', user_id),
        UniqueConstraint(
            'question_id', 'user_id',
            name='uq_question_user_feedback'
        )
    )

class AnswerFeedback(BaseModel):
    """Answer feedback model"""
    __tablename__ = 'answer_feedback'

    # Core fields
    answer_id = Column(Integer, ForeignKey('answers.id', ondelete='CASCADE'), nullable=False)
    user_id = Column(Integer, ForeignKey('users.id', ondelete='CASCADE'), nullable=False)
    rating = Column(Integer)
    feedback_text = Column(Text)
    is_helpful = Column(Boolean)
    
    # Additional fields
    category = Column(String)
    sentiment = Column(Float)
    processed_feedback = Column(JSONB, default={})
    metadata = Column(JSONB, default={})

    # Specific feedback aspects
    clarity_rating = Column(Integer)
    completeness_rating = Column(Integer)
    accuracy_rating = Column(Integer)
    usefulness_rating = Column(Integer)

    # Relationships
    answer = relationship('Answer', back_populates='feedback')
    user = relationship('User')

    # Indexes and Constraints
    __table_args__ = (
        CheckConstraint(
            'rating BETWEEN 1 AND 5',
            name='valid_rating_range'
        ),
        Index('ix_answer_feedback_answer_id', answer_id),
        Index('ix_answer_feedback_user_id', user_id),
        UniqueConstraint(
            'answer_id', 'user_id',
            name='uq_answer_user_feedback'
        )
    )

# Export models
__all__ = [
    'Question',
    'Answer',
    'QuestionFeedback',
    'AnswerFeedback',
    'QuestionCategory',
    'QuestionStatus'
]
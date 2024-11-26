from typing import List, Optional, Dict, Any
from datetime import datetime
from sqlalchemy import select, func, or_
import logging

from telegram_bot.models import Question, Answer, User
from telegram_bot.services.base import BaseService
from telegram_bot.core.cache import cache_service
from telegram_bot.utils.text_processor import text_processor
from telegram_bot.core.errors import ValidationError

logger = logging.getLogger(__name__)

class QuestionService(BaseService[Question]):
    """Enhanced question service with auto-answer capabilities"""
    
    def __init__(self, session):
        super().__init__(Question, session)
        self.cache = cache_service
        
    async def create_question(
        self,
        user_id: int,
        question_text: str,
        language: str,
        category: Optional[str] = None,
        metadata: Dict = None
    ) -> Question:
        """Create new question"""
        try:
            # Validate text length
            if len(question_text) < 10:
                raise ValidationError("Question text too short")
            if len(question_text) > 1000:
                raise ValidationError("Question text too long")
                
            # Create question
            question = await self.create(
                user_id=user_id,
                question_text=question_text,
                language=language,
                category=category,
                metadata=metadata or {
                    'created_at': datetime.utcnow().isoformat()
                }
            )
            
            # Find similar questions
            similar = await self.find_similar_questions(
                question_text,
                language,
                limit=3
            )
            
            if similar:
                question.similar_questions = [q.id for q in similar]
                await self.session.commit()
            
            # Clear cache
            await self.cache.delete_pattern(f"questions:user:{user_id}:*")
            
            return question
            
        except Exception as e:
            logger.error(f"Error creating question: {e}")
            raise

    async def create_answer(
        self,
        question_id: int,
        answer_text: str,
        created_by: Optional[int] = None,
        is_auto: bool = False,
        metadata: Dict = None
    ) -> Answer:
        """Create answer for question"""
        try:
            # Get question
            question = await self.get(question_id)
            if not question:
                raise ValidationError("Question not found")
                
            # Create answer
            answer = Answer(
                question_id=question_id,
                answer_text=answer_text,
                user_id=created_by,
                is_auto=is_auto,
                metadata=metadata or {
                    'created_at': datetime.utcnow().isoformat()
                }
            )
            
            self.session.add(answer)
            
            # Update question status
            question.is_answered = True
            question.status = 'ANSWERED'
            question.answer_count = len(question.answers) + 1
            
            await self.session.commit()
            
            # Clear cache
            await self.cache.delete_pattern(f"questions:{question_id}:*")
            
            return answer
            
        except Exception as e:
            logger.error(f"Error creating answer: {e}")
            raise

    async def find_similar_questions(
        self,
        question_text: str,
        language: str,
        limit: int = 5,
        threshold: float = 0.7
    ) -> List[Question]:
        """Find similar questions using text similarity"""
        try:
            # Get recent questions
            result = await self.session.execute(
                select(Question)
                .filter(
                    Question.language == language,
                    Question.is_answered == True
                )
                .order_by(Question.created_at.desc())
                .limit(100)
            )
            questions = result.scalars().all()
            
            if not questions:
                return []
            
            # Calculate similarities
            similarities = []
            for q in questions:
                score = text_processor.get_text_similarity(
                    question_text,
                    q.question_text,
                    language
                )
                if score >= threshold:
                    similarities.append((q, score))
            
            # Sort by similarity
            similarities.sort(key=lambda x: x[1], reverse=True)
            
            return [q for q, _ in similarities[:limit]]
            
        except Exception as e:
            logger.error(f"Error finding similar questions: {e}")
            return []

    async def get_user_questions(
        self,
        user_id: int,
        include_answers: bool = True
    ) -> List[Question]:
        """Get user's questions"""
        try:
            cache_key = f"questions:user:{user_id}"
            
            # Try cache
            cached = await self.cache.get(cache_key)
            if cached:
                return [Question(**q) for q in cached]
            
            # Get from database
            query = select(Question).filter(
                Question.user_id == user_id
            ).order_by(Question.created_at.desc())
            
            if include_answers:
                from sqlalchemy.orm import selectinload
                query = query.options(
                    selectinload(Question.answers)
                )
            
            result = await self.session.execute(query)
            questions = list(result.scalars().all())
            
            # Cache result
            await self.cache.set(
                cache_key,
                [q.to_dict() for q in questions],
                timeout=300
            )
            
            return questions
            
        except Exception as e:
            logger.error(f"Error getting user questions: {e}")
            return []

    async def get_unanswered_questions(
        self,
        limit: int = 50,
        offset: int = 0
    ) -> List[Question]:
        """Get unanswered questions"""
        try:
            result = await self.session.execute(
                select(Question)
                .filter(Question.is_answered == False)
                .order_by(Question.created_at.desc())
                .offset(offset)
                .limit(limit)
            )
            return list(result.scalars().all())
            
        except Exception as e:
            logger.error(f"Error getting unanswered questions: {e}")
            return []

# Create service instance  
question_service = QuestionService(None)  # Session will be injected
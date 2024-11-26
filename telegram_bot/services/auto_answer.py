from typing import Optional, Dict, Any, List, Tuple
from datetime import datetime
import logging
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
import numpy as np
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity
import joblib

from telegram_bot.models import Question, Answer, FAQ
from telegram_bot.core.cache import cache_service
from telegram_bot.utils.text_processor import text_processor
from telegram_bot.core.errors import AutoAnswerError

logger = logging.getLogger(__name__)

class EnhancedAutoAnswerService:
    """Enhanced auto-answer service with ML capabilities"""
    
    def __init__(self, session: AsyncSession):
        self.session = session
        self.cache = cache_service
        
        # Initialize ML components
        self.vectorizer = TfidfVectorizer(
            max_features=5000,
            ngram_range=(1, 3),
            stop_words=['ru', 'uz']
        )
        self.model = None
        self.load_model()
        
        # Similarity thresholds
        self.SIMILARITY_THRESHOLD = 0.75
        self.CONFIDENCE_THRESHOLD = 0.85
        
    def load_model(self) -> None:
        """Load ML model"""
        try:
            self.model = joblib.load('models/answer_model.joblib')
        except Exception as e:
            logger.error(f"Error loading model: {e}")
            self.model = None
            
    async def get_answer(
        self,
        question_text: str,
        language: str
    ) -> Optional[Dict[str, Any]]:
        """Get automated answer for question"""
        try:
            # Try cache first
            cache_key = f"auto_answer:{language}:{hash(question_text)}"
            cached = await self.cache.get(cache_key)
            if cached:
                return cached
                
            # Clean and process text
            processed_text = text_processor.clean_text(question_text)
            
            # Try FAQ first
            faq_answer = await self._get_faq_answer(processed_text, language)
            if faq_answer:
                await self.cache.set(cache_key, faq_answer, timeout=3600)
                return faq_answer
                
            # Try similar questions
            similar_answer = await self._get_similar_answer(processed_text, language)
            if similar_answer:
                await self.cache.set(cache_key, similar_answer, timeout=3600)
                return similar_answer
                
            # Use ML model as fallback
            if self.model:
                model_answer = self._get_model_answer(processed_text)
                if model_answer:
                    await self.cache.set(cache_key, model_answer, timeout=3600)
                    return model_answer
                    
            return None
            
        except Exception as e:
            logger.error(f"Error getting auto answer: {e}")
            raise AutoAnswerError("Failed to generate auto answer")
            
    async def _get_faq_answer(
        self,
        question: str,
        language: str
    ) -> Optional[Dict[str, Any]]:
        """Get answer from FAQ database"""
        try:
            # Get relevant FAQs
            result = await self.session.execute(
                select(FAQ)
                .filter(FAQ.language == language)
                .filter(FAQ.is_published == True)
            )
            faqs = result.scalars().all()
            
            if not faqs:
                return None
                
            # Calculate similarities
            similarities = []
            for faq in faqs:
                score = text_processor.get_text_similarity(
                    question,
                    faq.question,
                    language
                )
                if score >= self.SIMILARITY_THRESHOLD:
                    similarities.append((faq, score))
                    
            if not similarities:
                return None
                
            # Get best match
            best_match = max(similarities, key=lambda x: x[1])
            faq, score = best_match
            
            return {
                'answer_text': faq.answer,
                'confidence': score,
                'source': 'faq',
                'metadata': {
                    'faq_id': faq.id,
                    'category': faq.category
                }
            }
            
        except Exception as e:
            logger.error(f"Error getting FAQ answer: {e}")
            return None
            
    async def _get_similar_answer(
        self,
        question: str,
        language: str
    ) -> Optional[Dict[str, Any]]:
        """Get answer from similar questions"""
        try:
            # Get answered questions
            result = await self.session.execute(
                select(Question)
                .filter(Question.language == language)
                .filter(Question.is_answered == True)
            )
            questions = result.scalars().all()
            
            if not questions:
                return None
                
            # Calculate similarities
            similarities = []
            for q in questions:
                score = text_processor.get_text_similarity(
                    question,
                    q.question_text,
                    language
                )
                if score >= self.SIMILARITY_THRESHOLD:
                    similarities.append((q, score))
                    
            if not similarities:
                return None
                
            # Get best match
            best_match = max(similarities, key=lambda x: x[1])
            question, score = best_match
            
            answer = await self._get_best_answer(question.id)
            if not answer:
                return None
                
            return {
                'answer_text': answer.answer_text,
                'confidence': score,
                'source': 'similar',
                'metadata': {
                    'question_id': question.id,
                    'answer_id': answer.id
                }
            }
            
        except Exception as e:
            logger.error(f"Error getting similar answer: {e}")
            return None
            
    def _get_model_answer(self, question: str) -> Optional[Dict[str, Any]]:
        """Get answer using ML model"""
        try:
            if not self.model:
                return None
                
            prediction = self.model.predict([question])[0]
            confidence = float(self.model.predict_proba([question]).max())
            
            if confidence < self.CONFIDENCE_THRESHOLD:
                return None
                
            return {
                'answer_text': prediction,
                'confidence': confidence,
                'source': 'model',
                'metadata': {
                    'model_version': getattr(self.model, 'version', 'unknown')
                }
            }
            
        except Exception as e:
            logger.error(f"Error getting model answer: {e}")
            return None
            
    async def train_model(
        self,
        language: str = None,
        force: bool = False
    ) -> bool:
        """Train answer generation model"""
        try:
            # Get training data
            query = select(Question).filter(
                Question.is_answered == True
            )
            if language:
                query = query.filter(Question.language == language)
                
            result = await self.session.execute(query)
            questions = result.scalars().all()
            
            if not questions and not force:
                return False
                
            # Prepare data
            X = [q.question_text for q in questions]
            y = []
            
            for question in questions:
                answer = await self._get_best_answer(question.id)
                y.append(answer.answer_text if answer else '')
                
            # Create and train model
            from sklearn.pipeline import Pipeline
            from sklearn.ensemble import RandomForestClassifier
            
            model = Pipeline([
                ('tfidf', self.vectorizer),
                ('clf', RandomForestClassifier())
            ])
            
            model.fit(X, y)
            model.version = datetime.utcnow().isoformat()
            
            # Save model
            joblib.dump(model, 'models/answer_model.joblib')
            self.model = model
            
            return True
            
        except Exception as e:
            logger.error(f"Error training model: {e}")
            return False
            
    async def _get_best_answer(self, question_id: int) -> Optional[Answer]:
        """Get best answer for question"""
        result = await self.session.execute(
            select(Answer)
            .filter(Answer.question_id == question_id)
            .order_by(Answer.rating.desc())
        )
        return result.scalar_one_or_none()
        
    async def evaluate_model(
        self,
        language: str = None
    ) -> Dict[str, float]:
        """Evaluate model performance"""
        try:
            if not self.model:
                return {}
                
            # Get test questions
            query = select(Question).filter(
                Question.is_answered == True
            )
            if language:
                query = query.filter(Question.language == language)
                
            result = await self.session.execute(query)
            questions = result.scalars().all()
            
            correct = 0
            total = len(questions)
            
            for question in questions:
                answer = await self.get_answer(
                    question.question_text,
                    question.language
                )
                
                if answer and answer['source'] == 'model':
                    actual_answer = await self._get_best_answer(question.id)
                    if actual_answer:
                        similarity = text_processor.get_text_similarity(
                            answer['answer_text'],
                            actual_answer.answer_text,
                            question.language
                        )
                        if similarity >= 0.8:
                            correct += 1
                            
            return {
                'accuracy': correct / total if total > 0 else 0,
                'coverage': total / len(questions) if questions else 0,
                'model_version': getattr(self.model, 'version', 'unknown')
            }
            
        except Exception as e:
            logger.error(f"Error evaluating model: {e}")
            return {}

auto_answer_service = EnhancedAutoAnswerService(None)  # Session will be injected
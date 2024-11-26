from typing import List, Optional, Dict
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession
from telegram_bot.models import FAQ, Question
from telegram_bot.core.cache import cache_service
from telegram_bot.utils.text_processor import text_processor

class FAQService:
    def __init__(self, session: AsyncSession):
        self.session = session
        self.cache = cache_service

    async def create_faq(
        self,
        question: Dict[str, str],  # {'uz': '...', 'ru': '...'}
        answer: Dict[str, str],    # {'uz': '...', 'ru': '...'}
        category: str,
        order: Optional[int] = None,
        tags: List[str] = None,
        metadata: Dict = None
    ) -> FAQ:
        """Create new FAQ entry"""
        if not order:
            result = await self.session.execute(
                select(func.max(FAQ.order))
            )
            max_order = result.scalar() or 0
            order = max_order + 1

        faq = FAQ(
            question=question,
            answer=answer,
            category=category,
            order=order,
            tags=tags or [],
            metadata=metadata or {},
            is_published=True
        )
        
        self.session.add(faq)
        await self.session.commit()
        await self.session.refresh(faq)

        # Clear cache
        await self.cache.delete_pattern("faq:*")

        return faq

    async def get_faq_list(
        self,
        language: str,
        category: Optional[str] = None
    ) -> List[FAQ]:
        """Get FAQ list with optional category filter"""
        cache_key = f"faq:list:{language}:{category or 'all'}"
        cached = await self.cache.get(cache_key)
        if cached:
            return [FAQ(**item) for item in cached]

        query = select(FAQ).filter(
            FAQ.is_published == True
        ).order_by(FAQ.order)

        if category:
            query = query.filter(FAQ.category == category)

        result = await self.session.execute(query)
        faqs = result.scalars().all()

        # Cache results
        await self.cache.set(
            cache_key,
            [faq.to_dict() for faq in faqs],
            timeout=3600
        )

        return faqs

    async def search_faq(
        self,
        query: str,
        language: str
    ) -> List[Dict]:
        """Search FAQs by query"""
        faqs = await self.get_faq_list(language)
        
        results = []
        for faq in faqs:
            # Get similarity score
            score = text_processor.get_text_similarity(
                query,
                faq.question[language],
                language
            )
            if score > 0.3:  # Minimum similarity threshold
                results.append({
                    'faq': faq,
                    'score': score
                })

        # Sort by relevance
        results.sort(key=lambda x: x['score'], reverse=True)
        return results[:5]  # Return top 5 results

    async def track_faq_view(self, faq_id: int) -> None:
        """Track FAQ view"""
        faq = await self.session.get(FAQ, faq_id)
        if faq:
            faq.view_count += 1
            await self.session.commit()
            await self.cache.delete_pattern("faq:*")

# Create service instance
faq_service = FAQService(None)  # Session will be injected
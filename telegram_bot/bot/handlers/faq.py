from aiogram import Router, F
from aiogram.filters import Command
from aiogram.types import Message, CallbackQuery
from aiogram.fsm.context import FSMContext
import logging

from telegram_bot.models import User, FAQ, FAQCategory
from telegram_bot.services.faq import FAQService
from telegram_bot.core.constants import TEXTS
from telegram_bot.bot.keyboards import (
    get_faq_categories_keyboard,
    get_faq_list_keyboard,
    get_faq_navigation_keyboard
)

logger = logging.getLogger(__name__)
router = Router(name='faq')

@router.message(Command("faq"))
@router.message(F.text.in_(["FAQ", "Часто задаваемые вопросы", "Ko'p so'raladigan savollar"]))
async def cmd_faq(message: Message, user: User, session):
    """Show FAQ categories"""
    try:
        faq_service = FAQService(session)
        categories = await faq_service.get_categories(user.language)
        
        await message.answer(
            TEXTS[user.language]['faq_categories'],
            reply_markup=get_faq_categories_keyboard(categories, user.language)
        )
        
    except Exception as e:
        logger.error(f"Error showing FAQ categories: {e}")
        await message.answer(TEXTS[user.language]['error'])

@router.callback_query(F.data.startswith("faq_cat:"))
async def show_category_faqs(callback: CallbackQuery, user: User, session):
    """Show FAQs in category"""
    try:
        category_id = int(callback.data.split(":")[1])
        
        faq_service = FAQService(session)
        faqs = await faq_service.get_category_faqs(category_id, user.language)
        
        if not faqs:
            await callback.message.edit_text(
                TEXTS[user.language]['no_faqs_in_category'],
                reply_markup=get_faq_navigation_keyboard(user.language)
            )
            return
        
        await callback.message.edit_text(
            TEXTS[user.language]['select_faq'],
            reply_markup=get_faq_list_keyboard(faqs, user.language)
        )
        
    except Exception as e:
        logger.error(f"Error showing category FAQs: {e}")
        await callback.message.edit_text(TEXTS[user.language]['error'])

@router.callback_query(F.data.startswith("faq:"))
async def show_faq(callback: CallbackQuery, user: User, session):
    """Show FAQ answer"""
    try:
        faq_id = int(callback.data.split(":")[1])
        
        faq_service = FAQService(session)
        faq = await faq_service.get(faq_id)
        
        if not faq:
            await callback.answer(TEXTS[user.language]['faq_not_found'])
            return
        
        # Track view
        await faq_service.track_view(faq_id)
        
        # Format message
        message = f"❓ {faq.question}\n\n✅ {faq.answer}"
        
        # Add attachments if any
        if faq.attachments:
            message += "\n\n📎 Прикрепленные файлы:"
            for attachment in faq.attachments:
                if attachment['type'] == 'photo':
                    # Send photo separately
                    await callback.message.answer_photo(
                        attachment['file_id'],
                        caption=attachment.get('caption')
                    )
                elif attachment['type'] == 'document':
                    await callback.message.answer_document(
                        attachment['file_id'],
                        caption=attachment.get('caption')
                    )
        
        # Add related questions if any
        if faq.metadata.get('related_questions'):
            message += "\n\n🔗 Похожие вопросы:\n"
            for related in faq.metadata['related_questions'][:3]:
                message += f"• {related['question']}\n"
        
        await callback.message.edit_text(
            message,
            reply_markup=get_faq_navigation_keyboard(
                user.language,
                faq.category_id,
                show_helpful=True,
                faq_id=faq.id
            ),
            parse_mode="HTML"
        )
        
        # Save last viewed FAQ for user
        await state.update_data(last_faq_id=faq.id)
        
    except Exception as e:
        logger.error(f"Error showing FAQ: {e}")
        await callback.message.edit_text(TEXTS[user.language]['error'])

@router.callback_query(F.data.startswith("faq_helpful:"))
async def track_helpfulness(callback: CallbackQuery, user: User, session, state: FSMContext):
    """Track if FAQ was helpful"""
    try:
        _, faq_id, helpful = callback.data.split(":")
        faq_id = int(faq_id)
        helpful = helpful == "1"
        
        faq_service = FAQService(session)
        await faq_service.track_view(faq_id, helpful)
        
        # Show feedback form if not helpful
        if not helpful:
            await state.set_state("waiting_faq_feedback")
            await state.update_data(faq_id=faq_id)
            
            await callback.message.edit_text(
                TEXTS[user.language]['ask_feedback'],
                reply_markup=get_faq_feedback_keyboard(user.language)
            )
        else:
            await callback.answer(TEXTS[user.language]['thanks_feedback'])
            
            # Show suggested questions based on this FAQ
            suggested = await faq_service.get_suggested_faqs(faq_id, user.language)
            if suggested:
                await callback.message.edit_text(
                    TEXTS[user.language]['suggested_faqs'],
                    reply_markup=get_faq_list_keyboard(suggested, user.language)
                )
            else:
                # Return to category
                faq = await faq_service.get(faq_id)
                if faq:
                    await show_category_faqs(callback, user, session)
        
    except Exception as e:
        logger.error(f"Error tracking FAQ helpfulness: {e}")
        await callback.answer(TEXTS[user.language]['error'])

@router.message(state="waiting_faq_feedback")
async def process_faq_feedback(message: Message, state: FSMContext, user: User, session):
    """Process detailed feedback for FAQ"""
    try:
        data = await state.get_data()
        faq_id = data.get('faq_id')
        
        if not faq_id:
            await state.clear()
            return
            
        faq_service = FAQService(session)
        await faq_service.add_feedback(faq_id, message.text, user.id)
        
        await message.answer(
            TEXTS[user.language]['thanks_detailed_feedback'],
            reply_markup=get_faq_categories_keyboard(
                await faq_service.get_categories(user.language),
                user.language
            )
        )
        
        await state.clear()
        
    except Exception as e:
        logger.error(f"Error processing FAQ feedback: {e}")
        await message.answer(TEXTS[user.language]['error'])
        await state.clear()

@router.callback_query(F.data == "faq_search")
async def start_faq_search(callback: CallbackQuery, state: FSMContext, user: User):
    """Start FAQ search"""
    try:
        await state.set_state("faq_search")
        
        await callback.message.edit_text(
            TEXTS[user.language]['enter_faq_search'],
            reply_markup=get_faq_navigation_keyboard(user.language)
        )
        
    except Exception as e:
        logger.error(f"Error starting FAQ search: {e}")
        await callback.message.edit_text(TEXTS[user.language]['error'])

@router.message(state="faq_search")
async def search_faqs(message: Message, state: FSMContext, user: User, session):
    """Search FAQs"""
    try:
        query = message.text.strip()
        
        if len(query) < 3:
            await message.answer(TEXTS[user.language]['search_query_too_short'])
            return
            
        faq_service = FAQService(session)
        results = await faq_service.search_faqs(query, user.language)
        
        if not results:
            await message.answer(
                TEXTS[user.language]['no_faq_results'],
                reply_markup=get_faq_navigation_keyboard(user.language)
            )
            await state.clear()
            return
            
        # Format search results
        text = TEXTS[user.language]['search_results'].format(count=len(results))
        
        await message.answer(
            text,
            reply_markup=get_faq_list_keyboard(
                [result['faq'] for result in results],
                user.language
            )
        )
        
        await state.clear()
        
        # Track search query
        analytics_service = AnalyticsService(session)
        await analytics_service.track_event(
            user_id=user.id,
            event_type='faq_search',
            data={'query': query, 'results_count': len(results)}
        )
        
    except Exception as e:
        logger.error(f"Error searching FAQs: {e}")
        await message.answer(TEXTS[user.language]['error'])
        await state.clear()

@router.callback_query(F.data == "faq_categories")
async def show_categories(callback: CallbackQuery, user: User, session):
    """Show FAQ categories"""
    try:
        faq_service = FAQService(session)
        categories = await faq_service.get_categories(user.language)
        
        await callback.message.edit_text(
            TEXTS[user.language]['faq_categories'],
            reply_markup=get_faq_categories_keyboard(categories, user.language)
        )
        
    except Exception as e:
        logger.error(f"Error showing categories: {e}")
        await callback.message.edit_text(TEXTS[user.language]['error'])

def register_handlers(dp):
    """Register FAQ handlers"""
    dp.include_router(router)
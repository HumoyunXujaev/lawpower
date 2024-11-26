import asyncio
import uvicorn
import nltk
from telegram_bot.app import app
from telegram_bot.core.database import init_db
from telegram_bot.bot import start_polling, stop_polling
from telegram_bot.services.background_tasks import background_tasks

# Download required NLTK data
try:
    nltk.download('punkt')
    nltk.download('stopwords')
except Exception as e:
    print(f"Warning: Failed to download NLTK data: {e}")

async def startup():
    """Initialize application"""
    # Initialize database
    await init_db()
    
    # Start background tasks
    await background_tasks.start()
    
    # Start bot polling
    await start_polling()

async def shutdown():
    """Cleanup application"""
    # Stop bot polling
    await stop_polling()
    
    # Stop background tasks
    await background_tasks.stop()

if __name__ == "__main__":
    # Setup startup and shutdown events
    app.add_event_handler("startup", startup)
    app.add_event_handler("shutdown", shutdown)
    
    # Run application
    uvicorn.run(
        "main:app",
        host="0.0.0.0",
        port=8000,
        reload=True
    )
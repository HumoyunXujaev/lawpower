import asyncio
from telegram_bot.core.logging import setup_logging
from fastapi import FastAPI, Request
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.cors import CORSMiddleware
from contextlib import asynccontextmanager
from fastapi.responses import JSONResponse
from telegram_bot.core.config import settings
from telegram_bot.core.database import init_db
from telegram_bot.bot import start_polling, stop_polling
from telegram_bot.admin.api import router as admin_router

@asynccontextmanager
async def lifespan(app: FastAPI):
    """Lifecycle manager for the application"""
    # Startup
    await init_db()
    await start_polling()
    
    yield
    
    # Shutdown
    from telegram_bot.bot import stop_polling
    await stop_polling()

app = FastAPI(
    title=settings.APP_NAME,
    description="Law Consultation Telegram Bot",
    version=settings.VERSION,
    lifespan=lifespan
)

# Setup logging
logger = setup_logging(
    log_level=settings.LOG_LEVEL,
    log_format=settings.LOG_FORMAT,
    log_file=settings.LOG_FILE
)


# Add CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"]
)

# Mount static files
app.mount(
    "/static",
    StaticFiles(directory=str(settings.STATIC_DIR)),
    name="static"
)

# Add admin routes
app.include_router(
    admin_router,
    prefix="/admin",
    tags=["admin"]
)

# Add health check endpoint
@app.get("/health")
async def health_check():
    return {
        "status": "healthy",
        "version": settings.VERSION,
        "environment": settings.ENVIRONMENT
    }

# Add error handlers
@app.exception_handler(500)
async def internal_error_handler(request: Request, exc: Exception):
    logger.error(f"Internal error: {exc}", exc_info=True)
    return JSONResponse(
        status_code=500,
        content={"message": "Internal server error"}
    )
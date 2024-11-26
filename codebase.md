# .github\workflows\ci.yml

```yml
name: CI/CD Pipeline

on:
  push:
    branches: [ main, develop ]
    tags: [ 'v*' ]
  pull_request:
    branches: [ main, develop ]

jobs:
  test:
    runs-on: ubuntu-latest
    
    services:
      postgres:
        image: postgres:16
        env:
          POSTGRES_DB: telegram_bot_test
          POSTGRES_USER: postgres
          POSTGRES_PASSWORD: postgres
        ports:
          - 5432:5432
        options: >-
          --health-cmd pg_isready
          --health-interval 10s
          --health-timeout 5s
          --health-retries 5
      
      redis:
        image: redis:7
        ports:
          - 6379:6379
        options: >-
          --health-cmd "redis-cli ping"
          --health-interval 10s
          --health-timeout 5s
          --health-retries 5

    steps:
    - uses: actions/checkout@v4
      with:
        fetch-depth: 0
    
    - name: Set up Python
      uses: actions/setup-python@v5
      with:
        python-version: '3.11'
        cache: 'pip'
    
    - name: Install dependencies
      run: |
        python -m pip install --upgrade pip
        pip install -r requirements.txt
        pip install -r requirements.dev.txt
    
    - name: Security check
      run: |
        pip install safety
        safety check
        
    - name: Run linting
      run: |
        ruff check .
        black . --check
        mypy telegram_bot
    
    - name: Run tests
      env:
        ENVIRONMENT: test
        DB_HOST: localhost
        DB_PORT: 5432
        DB_USER: postgres
        DB_PASSWORD: postgres
        DB_NAME: telegram_bot_test
        REDIS_HOST: localhost
        REDIS_PORT: 6379
        REDIS_PASSWORD: ""
        SECRET_KEY: test_secret_key_123
        BOT_TOKEN: ${{ secrets.TEST_BOT_TOKEN }}
        ADMIN_IDS: "[123456789]"
      run: |
        pytest --cov=telegram_bot --cov-report=xml -v
    
    - name: Upload coverage
      uses: codecov/codecov-action@v3
      with:
        file: ./coverage.xml
        fail_ci_if_error: true

  build:
    needs: test
    runs-on: ubuntu-latest
    if: github.event_name == 'push' && (github.ref == 'refs/heads/main' || github.ref == 'refs/heads/develop' || startsWith(github.ref, 'refs/tags/v'))
    
    steps:
    - uses: actions/checkout@v4
    
    - name: Set up Docker Buildx
      uses: docker/setup-buildx-action@v3
    
    - name: Login to Docker Hub
      uses: docker/login-action@v3
      with:
        username: ${{ secrets.DOCKERHUB_USERNAME }}
        password: ${{ secrets.DOCKERHUB_TOKEN }}
    
    - name: Build and push
      uses: docker/build-push-action@v5
      with:
        context: .
        push: true
        tags: |
          ${{ secrets.DOCKERHUB_USERNAME }}/telegram-bot:${{ github.sha }}
          ${{ github.ref == 'refs/heads/main' && format('{0}/telegram-bot:latest', secrets.DOCKERHUB_USERNAME) || '' }}
        cache-from: type=registry,ref=${{ secrets.DOCKERHUB_USERNAME }}/telegram-bot:buildcache
        cache-to: type=registry,ref=${{ secrets.DOCKERHUB_USERNAME }}/telegram-bot:buildcache,mode=max

  deploy-staging:
    needs: build
    if: github.ref == 'refs/heads/develop'
    runs-on: ubuntu-latest
    environment: staging
    
    steps:
    - name: Deploy to staging
      uses: appleboy/ssh-action@master
      with:
        host: ${{ secrets.STAGING_HOST }}
        username: ${{ secrets.STAGING_USERNAME }}
        key: ${{ secrets.STAGING_SSH_KEY }}
        script: |
          cd /opt/telegram-bot
          docker-compose pull
          docker-compose up -d
          docker system prune -f

  deploy-production:
    needs: build
    if: github.ref == 'refs/heads/main' || startsWith(github.ref, 'refs/tags/v')
    runs-on: ubuntu-latest
    environment: production
    
    steps:
    - name: Deploy to production
      uses: appleboy/ssh-action@master
      with:
        host: ${{ secrets.PROD_HOST }}
        username: ${{ secrets.PROD_USERNAME }}
        key: ${{ secrets.PROD_SSH_KEY }}
        script: |
          cd /opt/telegram-bot
          docker-compose pull
          docker-compose up -d
          docker system prune -f
    
    - name: Create Sentry release
      uses: getsentry/action-release@v1
      env:
        SENTRY_AUTH_TOKEN: ${{ secrets.SENTRY_AUTH_TOKEN }}
        SENTRY_ORG: ${{ secrets.SENTRY_ORG }}
        SENTRY_PROJECT: ${{ secrets.SENTRY_PROJECT }}
      with:
        environment: production
        version: ${{ github.sha }}
```

# .github\workflows\deploy.yml

```yml
name: Deploy

on:
  push:
    branches: [ main ]
    tags: [ 'v*' ]

jobs:
  deploy:
    runs-on: ubuntu-latest
    
    steps:
    - uses: actions/checkout@v4
    
    - name: Set up Docker Buildx
      uses: docker/setup-buildx-action@v3
    
    - name: Login to Docker Hub
      uses: docker/login-action@v3
      with:
        username: ${{ secrets.DOCKERHUB_USERNAME }}
        password: ${{ secrets.DOCKERHUB_TOKEN }}
    
    - name: Build and push
      uses: docker/build-push-action@v5
      with:
        context: .
        push: true
        tags: |
          ${{ secrets.DOCKERHUB_USERNAME }}/telegram-bot:${{ github.sha }}
          ${{ github.ref == 'refs/heads/main' && format('{0}/telegram-bot:latest', secrets.DOCKERHUB_USERNAME) || '' }}
    
    - name: Deploy to production
      uses: appleboy/ssh-action@master
      with:
        host: ${{ secrets.PROD_HOST }}
        username: ${{ secrets.PROD_USERNAME }}
        key: ${{ secrets.PROD_SSH_KEY }}
        script: |
          cd /opt/telegram-bot
          docker-compose pull
          docker-compose up -d
          docker system prune -f
    
    - name: Create Sentry release
      uses: getsentry/action-release@v1
      env:
        SENTRY_AUTH_TOKEN: ${{ secrets.SENTRY_AUTH_TOKEN }}
        SENTRY_ORG: ${{ secrets.SENTRY_ORG }}
        SENTRY_PROJECT: ${{ secrets.SENTRY_PROJECT }}
      with:
        environment: production
        version: ${{ github.sha }}
```

# .gitignore

```
# Python __pycache__/ *.py[cod] *$py.class *.so .Python build/ develop-eggs/ dist/ downloads/ eggs/ .eggs/ lib/ lib64/ parts/ sdist/ var/ wheels/ *.egg-info/ .installed.cfg *.egg # Virtual Environment venv/ env/ ENV/ # IDE .idea/ .vscode/ *.swp *.swo # Logs logs/ *.log # Local development .env .env.local .env.*.local # Database *.sqlite3 *.db # Media media/ static/ # Cache .cache/ .pytest_cache/ # Coverage reports htmlcov/ .coverage .coverage.* coverage.xml # Docker .docker/ # Backups *.bak *.backup
```

# alembic\alembic.ini

```ini
[alembic] script_location = telegram_bot/alembic prepend_sys_path = . version_path_separator = os [post_write_hooks] hooks = black, isort black.type = console_scripts black.entrypoint = black black.options = -l 88 -t py311 isort.type = console_scripts isort.entrypoint = isort isort.options = --profile black [loggers] keys = root,sqlalchemy,alembic [handlers] keys = console,file [formatters] keys = generic [logger_root] level = WARN handlers = console,file qualname = [logger_sqlalchemy] level = WARN handlers = qualname = sqlalchemy.engine [logger_alembic] level = INFO handlers = console,file qualname = alembic propagate = 0 [handler_console] class = StreamHandler args = (sys.stderr,) level = NOTSET formatter = generic [handler_file] class = FileHandler args = ('alembic.log', 'a') level = NOTSET formatter = generic [formatter_generic] format = %(levelname)-5.5s [%(name)s] %(message)s datefmt = %H:%M:%S
```

# alembic\env.py

```py
import os
import sys
import asyncio
from logging.config import fileConfig

from sqlalchemy import pool
from sqlalchemy.engine import Connection
from sqlalchemy.ext.asyncio import async_engine_from_config

from alembic import context

# Add parent directory to Python path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from telegram_bot.core.config import settings
from telegram_bot.models.base import Base

# this is the Alembic Config object
config = context.config

if config.config_file_name is not None:
    fileConfig(config.config_file_name)

target_metadata = Base.metadata

def get_url():
    return settings.ASYNC_DATABASE_URL

def run_migrations_offline() -> None:
    """Run migrations in 'offline' mode."""
    url = get_url()
    context.configure(
        url=url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
    )

    with context.begin_transaction():
        context.run_migrations()

def do_run_migrations(connection: Connection) -> None:
    context.configure(connection=connection, target_metadata=target_metadata)

    with context.begin_transaction():
        context.run_migrations()

async def run_async_migrations() -> None:
    """Run migrations in 'online' mode."""
    configuration = config.get_section(config.config_ini_section)
    configuration["sqlalchemy.url"] = get_url()

    connectable = async_engine_from_config(
        configuration,
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )

    async with connectable.connect() as connection:
        await connection.run_sync(do_run_migrations)

    await connectable.dispose()

def run_migrations_online() -> None:
    """Run migrations in 'online' mode."""
    asyncio.run(run_async_migrations())

if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
```

# alembic\versions\initial_migration.py

```py
"""Database migrations

Revision ID: 001
Create Date: 2024-03-17 12:00:00.000000
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers
revision = '001' 
down_revision = None
branch_labels = None
depends_on = None

def upgrade() -> None:
    # Create enum types
    op.execute("""
        CREATE TYPE user_role AS ENUM ('USER', 'ADMIN', 'SUPPORT');
        CREATE TYPE language AS ENUM ('uz', 'ru');
        CREATE TYPE consultation_status AS ENUM (
            'PENDING', 'PAID', 'SCHEDULED', 'COMPLETED', 'CANCELLED'
        );
        CREATE TYPE payment_status AS ENUM (
            'PENDING', 'PROCESSING', 'COMPLETED', 'FAILED', 'REFUNDED'
        );
        CREATE TYPE payment_provider AS ENUM ('CLICK', 'PAYME');
    """)
    
    # Users table
    op.create_table(
        'users',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('telegram_id', sa.BigInteger(), nullable=False),
        sa.Column('username', sa.String(), nullable=True),
        sa.Column('full_name', sa.String(), nullable=True),
        sa.Column('language', postgresql.ENUM('uz', 'ru', name='language'), nullable=False),
        sa.Column('roles', postgresql.ARRAY(sa.String()), nullable=False),
        sa.Column('is_active', sa.Boolean(), nullable=False, server_default='true'),
        sa.Column('is_blocked', sa.Boolean(), nullable=False, server_default='false'),
        sa.Column('last_active', sa.DateTime(timezone=True), nullable=True),
        sa.Column('settings', postgresql.JSONB(), nullable=False, server_default='{}'),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.text('now()')),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.text('now()')),
        sa.Column('deleted_at', sa.DateTime(timezone=True), nullable=True),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('telegram_id')
    )
    op.create_index('ix_users_telegram_id', 'users', ['telegram_id'])
    op.create_index('ix_users_username', 'users', ['username'])

    # Questions table
    op.create_table(
        'questions',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('user_id', sa.Integer(), nullable=False),
        sa.Column('question_text', sa.Text(), nullable=False),
        sa.Column('language', postgresql.ENUM('uz', 'ru', name='language'), nullable=False),
        sa.Column('category', sa.String(), nullable=True),
        sa.Column('tags', postgresql.ARRAY(sa.String()), nullable=True),
        sa.Column('is_answered', sa.Boolean(), nullable=False, server_default='false'),
        sa.Column('view_count', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('analytics', postgresql.JSONB(), nullable=False, server_default='{}'),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.text('now()')),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.text('now()')),
        sa.Column('deleted_at', sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(['user_id'], ['users.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index('ix_questions_user_id', 'questions', ['user_id'])
    op.create_index('ix_questions_category', 'questions', ['category'])

    # Answers table
    op.create_table(
        'answers',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('question_id', sa.Integer(), nullable=False),
        sa.Column('answer_text', sa.Text(), nullable=False),
        sa.Column('is_auto', sa.Boolean(), nullable=False, server_default='false'),
        sa.Column('is_accepted', sa.Boolean(), nullable=False, server_default='false'),
        sa.Column('rating', sa.Float(), nullable=True),
        sa.Column('created_by', sa.Integer(), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.text('now()')),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.text('now()')),
        sa.ForeignKeyConstraint(['created_by'], ['users.id'], ondelete='SET NULL'),
        sa.ForeignKeyConstraint(['question_id'], ['questions.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id')
    )

    # Consultations table
    op.create_table(
        'consultations',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('user_id', sa.Integer(), nullable=False),
        sa.Column('status', postgresql.ENUM('PENDING', 'PAID', 'SCHEDULED', 'COMPLETED', 'CANCELLED', name='consultation_status'), nullable=False),
        sa.Column('phone_number', sa.String(), nullable=False),
        sa.Column('problem_description', sa.Text(), nullable=True),
        sa.Column('amount', sa.Numeric(precision=10, scale=2), nullable=False),
        sa.Column('scheduled_time', sa.DateTime(timezone=True), nullable=True),
        sa.Column('duration', sa.Integer(), nullable=True),
        sa.Column('notes', sa.Text(), nullable=True),
        sa.Column('metadata', postgresql.JSONB(), nullable=False, server_default='{}'),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.text('now()')),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.text('now()')),
        sa.ForeignKeyConstraint(['user_id'], ['users.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index('ix_consultations_user_id', 'consultations', ['user_id'])
    op.create_index('ix_consultations_status', 'consultations', ['status'])

    # Payments table  
    op.create_table(
        'payments',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('consultation_id', sa.Integer(), nullable=False),
        sa.Column('amount', sa.Numeric(precision=10, scale=2), nullable=False),
        sa.Column('provider', postgresql.ENUM('CLICK', 'PAYME', name='payment_provider'), nullable=False),
        sa.Column('status', postgresql.ENUM('PENDING', 'PROCESSING', 'COMPLETED', 'FAILED', 'REFUNDED', name='payment_status'), nullable=False),
        sa.Column('transaction_id', sa.String(), nullable=True),
        sa.Column('payment_data', postgresql.JSONB(), nullable=False, server_default='{}'),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.text('now()')),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.text('now()')),
        sa.ForeignKeyConstraint(['consultation_id'], ['consultations.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index('ix_payments_transaction_id', 'payments', ['transaction_id'], unique=True)

    # User events table
    op.create_table(
        'user_events',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('user_id', sa.Integer(), nullable=False),
        sa.Column('event_type', sa.String(), nullable=False),
        sa.Column('event_data', postgresql.JSONB(), nullable=False, server_default='{}'),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.text('now()')),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.text('now()')),
        sa.ForeignKeyConstraint(['user_id'], ['users.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index('ix_user_events_user_id', 'user_events', ['user_id'])
    op.create_index('ix_user_events_event_type', 'user_events', ['event_type'])

def downgrade() -> None:
    # Drop tables
    op.drop_table('user_events')
    op.drop_table('payments')
    op.drop_table('consultations') 
    op.drop_table('answers')
    op.drop_table('questions')
    op.drop_table('users')
    
    # Drop enum types
    op.execute("""
        DROP TYPE IF EXISTS payment_provider;
        DROP TYPE IF EXISTS payment_status;
        DROP TYPE IF EXISTS consultation_status;
        DROP TYPE IF EXISTS language;
        DROP TYPE IF EXISTS user_role;
    """)
```

# docker-compose.yml

```yml
version: '3.8'

services:
  bot:
    build: 
      context: .
      dockerfile: docker/Dockerfile
    restart: unless-stopped
    depends_on:
      postgres:
        condition: service_healthy
      redis:
        condition: service_healthy
    environment:
      - ENVIRONMENT=${ENVIRONMENT:-development}
      - BOT_TOKEN=${BOT_TOKEN}
      - DB_HOST=postgres
      - DB_PORT=5432
      - DB_USER=${DB_USER:-postgres}
      - DB_PASSWORD=${DB_PASSWORD:-postgres}
      - DB_NAME=${DB_NAME:-telegram_bot}
      - REDIS_HOST=redis
      - REDIS_PORT=6379
      - REDIS_PASSWORD=${REDIS_PASSWORD:-redispass}
      - SECRET_KEY=${SECRET_KEY:-supersecretkey}
    volumes:
      - ./logs:/app/logs
      - ./media:/app/media
    networks:
      - bot_network
    healthcheck:
      test: ["CMD", "python", "-c", "import requests; requests.get('http://localhost:8000/health')"]
      interval: 30s
      timeout: 10s
      retries: 3

  postgres:
    image: postgres:16-alpine
    restart: unless-stopped
    environment:
      - POSTGRES_DB=${DB_NAME:-telegram_bot}
      - POSTGRES_USER=${DB_USER:-postgres}
      - POSTGRES_PASSWORD=${DB_PASSWORD:-postgres}
      - PGDATA=/var/lib/postgresql/data/pgdata
    volumes:
      - postgres_data:/var/lib/postgresql/data
    ports:
      - "5432:5432"
    networks:
      - bot_network
    healthcheck:
      test: ["CMD-SHELL", "pg_isready -U ${DB_USER:-postgres} -d ${DB_NAME:-telegram_bot}"]
      interval: 10s
      timeout: 5s
      retries: 5

  redis:
    image: redis:7-alpine
    restart: unless-stopped
    command: redis-server --requirepass ${REDIS_PASSWORD:-redispass}
    volumes:
      - redis_data:/data
    ports:
      - "6379:6379"
    networks:
      - bot_network
    healthcheck:
      test: ["CMD", "redis-cli", "--raw", "ping"]
      interval: 10s
      timeout: 5s
      retries: 5

  adminer:
    image: adminer
    restart: unless-stopped
    ports:
      - "8080:8080"
    depends_on:
      - postgres
    networks:
      - bot_network

volumes:
  postgres_data:
  redis_data:

networks:
  bot_network:
    driver: bridge
```

# docker\docker-compose.prod.yml

```yml
version: '3.8'

services:
  bot:
    build: 
      context: .
      dockerfile: docker/Dockerfile
      args:
        - ENVIRONMENT=production
    restart: always
    deploy:
      resources:
        limits:
          cpus: '1'
          memory: 1G
    healthcheck:
      test: ["CMD", "python", "-c", "import requests; requests.get('http://localhost:8000/health')"]
      interval: 30s
      timeout: 10s
      retries: 3
    environment:
      - ENVIRONMENT=production
      - BOT_TOKEN=${BOT_TOKEN}
      - DB_HOST=postgres
      - DB_PORT=5432
      - DB_USER=${DB_USER:-postgres}
      - DB_PASSWORD=${DB_PASSWORD:-postgres}
      - DB_NAME=${DB_NAME:-telegram_bot}
      - REDIS_HOST=redis
      - REDIS_PORT=6379
      - REDIS_PASSWORD=${REDIS_PASSWORD:-redispass}
      - SECRET_KEY=${SECRET_KEY:-supersecretkey}
    volumes:
      - ./logs:/app/logs
      - ./media:/app/media
    networks:
      - bot_network
    depends_on:
      postgres:
        condition: service_healthy
      redis:
        condition: service_healthy

  postgres:
    image: postgres:16-alpine
    restart: always
    deploy:
      resources:
        limits:
          cpus: '2'
          memory: 2G
    environment:
      - POSTGRES_DB=${DB_NAME:-telegram_bot}
      - POSTGRES_USER=${DB_USER:-postgres}
      - POSTGRES_PASSWORD=${DB_PASSWORD:-postgres}
    volumes:
      - postgres_data:/var/lib/postgresql/data
      - ./backups:/backups
    healthcheck:
      test: ["CMD-SHELL", "pg_isready -U ${DB_USER:-postgres}"]
      interval: 10s
      timeout: 5s
      retries: 5
    networks:
      - bot_network

  redis:
    image: redis:7-alpine
    restart: always
    deploy:
      resources:
        limits:
          cpus: '0.5'
          memory: 512M
    command: redis-server --requirepass ${REDIS_PASSWORD:-redispass}
    volumes:
      - redis_data:/data
    healthcheck:
      test: ["CMD", "redis-cli", "ping"]
      interval: 10s
      timeout: 5s
      retries: 5
    networks:
      - bot_network
  
  nginx:
    image: nginx:alpine
    restart: always
    ports:
      - "80:80"
      - "443:443"
    volumes:
      - ./nginx/conf.d:/etc/nginx/conf.d
      - ./nginx/ssl:/etc/nginx/ssl
      - ./static:/static
      - ./media:/media
    networks:
      - bot_network
    depends_on:
      - bot

volumes:
  postgres_data:
  redis_data:

networks:
  bot_network:
    driver: bridge
```

# docker\Dockerfile

```
FROM python:3.11-slim # Set environment variables ENV PYTHONDONTWRITEBYTECODE=1 \ PYTHONUNBUFFERED=1 \ PIP_NO_CACHE_DIR=1 \ PIP_DISABLE_PIP_VERSION_CHECK=1 # Set working directory WORKDIR /app # Install system dependencies RUN apt-get update && apt-get install -y --no-install-recommends \ build-essential \ libpq-dev \ && rm -rf /var/lib/apt/lists/* # Install Python dependencies COPY requirements.txt . RUN pip install --no-cache-dir -r requirements.txt # Create required directories RUN mkdir -p logs media static # Copy project files COPY . . # Set entrypoint COPY docker/entrypoint.sh /entrypoint.sh RUN chmod +x /entrypoint.sh ENTRYPOINT ["/entrypoint.sh"]
```

# docker\entrypoint.sh

```sh
#!/bin/bash set -e echo "Waiting for PostgreSQL..." until PGPASSWORD=$DB_PASSWORD psql -h "$DB_HOST" -U "$DB_USER" -d "$DB_NAME" -c '\q'; do echo "PostgreSQL is unavailable - sleeping" sleep 1 done echo "PostgreSQL is up" echo "Waiting for Redis..." until redis-cli -h "$REDIS_HOST" -p "$REDIS_PORT" -a "$REDIS_PASSWORD" ping | grep -q "PONG"; do echo "Redis is unavailable - sleeping" sleep 1 done echo "Redis is up" echo "Running database migrations..." alembic upgrade head echo "Starting application..." if [ "$ENVIRONMENT" = "production" ]; then echo "Starting in production mode..." exec gunicorn telegram_bot.main:app \ --workers 4 \ --worker-class uvicorn.workers.UvicornWorker \ --bind 0.0.0.0:8000 \ --access-logfile - \ --error-logfile - \ --log-level info else echo "Starting in development mode..." exec uvicorn telegram_bot.main:app --host 0.0.0.0 --port 8000 --reload fi
```

# requirements.txt

```txt
# Core dependencies fastapi==0.110.0 uvicorn[standard]==0.27.1 pydantic==2.5.3 pydantic-settings==2.2.1 python-dotenv==1.0.1 sqlalchemy[asyncio]==2.0.27 alembic==1.13.1 asyncpg==0.29.0 greenlet==3.0.0 # Telegram aiogram==3.4.1 # Cache & Queue redis==5.0.1 cachetools==5.3.3 # Security python-jose[cryptography]==3.3.0 passlib[bcrypt]==1.7.4 python-multipart==0.0.9 # Text Processing pymorphy2==0.9.1 rapidfuzz==3.6.1 phonenumbers==8.13.31 # Monitoring & Logging prometheus-client==0.19.0 python-json-logger==2.0.7 # Utils gunicorn==21.2.0 httpx==0.27.0 orjson==3.9.15 nltk==3.8.1 scikit-learn==1.4.1.post1 numpy>=1.26.4 sentry-sdk[fastapi]==1.40.6 aiohttp==3.9.5 aiofiles==23.2.1 apscheduler==3.10.4 jinja2==3.1.4 # Development pytest==8.0.2 pytest-asyncio==0.23.8 pytest-cov==4.1.0 black==24.2.0 isort==5.13.2 mypy==1.8.0 ruff==0.3.0
```

# telegram_bot\__init__.py

```py
from telegram_bot.core.config import settings
from telegram_bot.core.database import db
from telegram_bot.core.cache import cache_service
from telegram_bot.core.monitoring import metrics_manager
from telegram_bot.bot import bot, dp
from telegram_bot.services import (
    AnalyticsService,
    QuestionService,
    ConsultationService,
    PaymentService,
    NotificationService,
    FAQService
)
from telegram_bot.models import (
    User,
    Question,
    Answer,
    Consultation,
    Payment,
    FAQ,
    UserNotification,
    UserEvent
)

__version__ = "1.0.0"

__all__ = [
    'settings',
    'db',
    'cache_service',
    'metrics_manager',
    'bot',
    'dp',
    # Services
    'AnalyticsService',
    'QuestionService',
    'ConsultationService',
    'PaymentService',
    'NotificationService',
    'FAQService',
    # Models
    'User',
    'Question',
    'Answer',
    'Consultation',
    'Payment',
    'FAQ',
    'UserNotification',
    'UserEvent'
]
```

# telegram_bot\admin\api.py

```py
from fastapi import APIRouter, Depends, HTTPException, Query, Body, Request,Response
from fastapi.security import OAuth2PasswordBearer
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func, or_, and_
from typing import Optional, List, Dict, Any
from datetime import datetime, timedelta
import logging
from decimal import Decimal
from sqlalchemy.orm import joinedload
import asyncio
from sqlalchemy import event, text
from telegram_bot.core.database import get_session
from telegram_bot.core.security import (
    verify_token,
    create_access_token,
)
from telegram_bot.admin.auth import get_current_admin
from telegram_bot.models import (
    User, Question, Answer, Consultation, Payment,
    ConsultationStatus, PaymentStatus
)
from telegram_bot.services.analytics import AnalyticsService
from telegram_bot.services.questions import QuestionService
from telegram_bot.services.consultations import ConsultationService
from telegram_bot.core.cache import cache_service as cache
from telegram_bot.core.config import settings

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/admin", tags=["admin"])

@router.get("/dashboard")
async def get_dashboard_data(
    request: Request,
    session: AsyncSession = Depends(get_session),
    admin: User = Depends(get_current_admin)
):
    """Get admin dashboard data"""
    try:
        # Check cache
        cache_key = f"admin:dashboard:{admin.id}"
        cached = await cache.get(cache_key)
        if cached:
            return cached

        analytics = AnalyticsService(session)
        
        # Get user statistics
        users_stats = await analytics.get_users_stats()
        
        # Get questions statistics
        question_service = QuestionService(session)
        questions_stats = await question_service.get_question_stats()
        
        # Get consultation statistics
        consultation_service = ConsultationService(session)
        consultations_stats = await consultation_service.get_consultation_stats()
        
        # Get revenue data
        revenue_stats = await analytics.get_revenue_stats()
        
        # Get recent activity
        activity = await analytics.get_recent_activity()
        
        dashboard_data = {
            "users": {
                "total": users_stats["total"],
                "active": users_stats["active"],
                "growth_rate": users_stats["growth_rate"],
                "language_distribution": users_stats["languages"]
            },
            "questions": {
                "total": questions_stats["total_questions"],
                "answered": questions_stats["answered_questions"],
                "answer_rate": questions_stats["answer_rate"],
                "categories": questions_stats["categories"]
            },
            "consultations": {
                "total": consultations_stats["total_consultations"],
                "completed": consultations_stats["completed_consultations"],
                "revenue": consultations_stats["total_revenue"],
                "average_rating": consultations_stats["average_rating"]
            },
            "revenue": {
                "today": revenue_stats["today"],
                "this_week": revenue_stats["this_week"],
                "this_month": revenue_stats["this_month"],
                "by_payment_method": revenue_stats["by_provider"]
            },
            "activity": activity,
            "timestamp": datetime.utcnow().isoformat()
        }
        
        # Cache for 5 minutes
        await cache.set(cache_key, dashboard_data, timeout=300)
        
        return dashboard_data
        
    except Exception as e:
        logger.error(f"Error getting dashboard data: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="Internal server error")

@router.get("/users")
async def get_users(
    skip: int = Query(0, ge=0),
    limit: int = Query(50, gt=0, le=100),
    search: Optional[str] = None,
    status: Optional[str] = None,
    language: Optional[str] = None,
    sort_by: str = Query("created_at", enum=["created_at", "last_active"]),
    order: str = Query("desc", enum=["asc", "desc"]),
    session: AsyncSession = Depends(get_session),
    admin: User = Depends(get_current_admin)
):
    """Get paginated users list"""
    try:
        # Build query
        query = select(User)
        
        # Apply filters
        if search:
            query = query.filter(
                or_(
                    User.username.ilike(f"%{search}%"),
                    User.full_name.ilike(f"%{search}%")
                )
            )
        
        if status == "active":
            query = query.filter(
                User.is_active == True,
                User.is_blocked == False
            )
        elif status == "blocked":
            query = query.filter(User.is_blocked == True)
            
        if language:
            query = query.filter(User.language == language)
            
        # Apply sorting
        if order == "desc":
            query = query.order_by(getattr(User, sort_by).desc())
        else:
            query = query.order_by(getattr(User, sort_by).asc())
            
        # Get total count
        total = await session.scalar(
            select(func.count()).select_from(query.subquery())
        )
        
        # Get paginated results
        query = query.offset(skip).limit(limit)
        result = await session.execute(query)
        users = result.scalars().all()
        
        # Get additional stats for users
        analytics = AnalyticsService(session)
        users_data = []
        
        for user in users:
            stats = await analytics.get_user_stats(user.id)
            users_data.append({
                "id": user.id,
                "telegram_id": user.telegram_id,
                "username": user.username,
                "full_name": user.full_name,
                "language": user.language,
                "is_active": user.is_active,
                "is_blocked": user.is_blocked,
                "created_at": user.created_at.isoformat(),
                "last_active": user.last_active.isoformat() if user.last_active else None,
                "stats": {
                    "questions_count": stats["questions_count"],
                    "consultations_count": stats["consultations_count"],
                    "total_spent": stats["total_spent"]
                }
            })
            
        return {
            "total": total,
            "page": skip // limit + 1,
            "pages": (total + limit - 1) // limit,
            "items": users_data
        }
        
    except Exception as e:
        logger.error(f"Error getting users: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="Internal server error")

@router.post("/users/{user_id}/block")
async def toggle_user_block(
    user_id: int,
    reason: str = Body(...),
    session: AsyncSession = Depends(get_session),
    admin: User = Depends(get_current_admin)
):
    """Toggle user block status"""
    try:
        user = await session.get(User, user_id)
        if not user:
            raise HTTPException(status_code=404, detail="User not found")
            
        # Toggle block status
        user.is_blocked = not user.is_blocked
        
        # Update metadata
        user.metadata = user.metadata or {}
        if user.is_blocked:
            user.metadata["blocked_at"] = datetime.utcnow().isoformat()
            user.metadata["blocked_by"] = admin.id
            user.metadata["block_reason"] = reason
        else:
            user.metadata["unblocked_at"] = datetime.utcnow().isoformat()
            user.metadata["unblocked_by"] = admin.id
            
        await session.commit()
        
        # Clear cache
        await cache.delete(f"user:{user_id}")
        
        # Notify user
        from telegram_bot.bot import bot
        if user.is_blocked:
            await bot.send_message(
                user.telegram_id,
                f"Your account has been blocked. Reason: {reason}"
            )
        else:
            await bot.send_message(
                user.telegram_id,
                "Your account has been unblocked."
            )
            
        return {"success": True, "is_blocked": user.is_blocked}
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error toggling user block: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="Internal server error")

@router.get("/questions")
async def get_questions(
    skip: int = Query(0, ge=0),
    limit: int = Query(50, gt=0, le=100),
    status: Optional[str] = None,
    language: Optional[str] = None,
    category: Optional[str] = None,
    search: Optional[str] = None,
    session: AsyncSession = Depends(get_session),
    admin: User = Depends(get_current_admin)
):
    """Get paginated questions list"""
    try:
        # Build query
        query = select(Question).options(
            joinedload(Question.user),
            joinedload(Question.answers)
        )
        
        # Apply filters
        if status == "unanswered":
            query = query.filter(~Question.answers.any())
        elif status == "answered":
            query = query.filter(Question.answers.any())
        elif status == "auto":
            query = query.filter(
                Question.answers.any(Answer.is_auto == True)
            )
            
        if language:
            query = query.filter(Question.language == language)
            
        if category:
            query = query.filter(Question.category == category)
            
        if search:
            query = query.filter(Question.question_text.ilike(f"%{search}%"))
            
        # Get total count
        total = await session.scalar(
            select(func.count()).select_from(query.subquery())
        )
        
        # Get paginated results
        query = query.order_by(Question.created_at.desc())
        query = query.offset(skip).limit(limit)
        result = await session.execute(query)
        questions = result.unique().scalars().all()
        
        return {
            "total": total,
            "page": skip // limit + 1,
            "pages": (total + limit - 1) // limit,
            "items": [
                {
                    "id": q.id,
                    "text": q.question_text,
                    "language": q.language,
                    "category": q.category,
                    "user": {
                        "id": q.user.id,
                        "username": q.user.username,
                        "full_name": q.user.full_name
                    },
                    "answers": [
                        {
                            "id": a.id,
                            "text": a.answer_text,
                            "is_auto": a.is_auto,
                            "rating": a.rating,
                            "created_at": a.created_at.isoformat()
                        }
                        for a in q.answers
                    ],
                    "created_at": q.created_at.isoformat()
                }
                for q in questions
            ]
        }
        
    except Exception as e:
        logger.error(f"Error getting questions: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="Internal server error")

@router.post("/questions/{question_id}/answer")
async def create_answer(
    question_id: int,
    data: Dict = Body(...),
    session: AsyncSession = Depends(get_session),
    admin: User = Depends(get_current_admin)
):
    """Create answer for question"""
    try:
        question_service = QuestionService(session)
        question = await question_service.get_question(question_id)
        
        if not question:
            raise HTTPException(status_code=404, detail="Question not found")
            
        # Create answer
        answer = await question_service.create_answer(
            question_id=question_id,
            answer_text=data["text"],
            created_by=admin.id
        )
        
        # Notify user
        from telegram_bot.bot import bot
        await bot.send_message(
            question.user.telegram_id,
            f"Your question has been answered:\n\n"
            f"Q: {question.question_text}\n\n"
            f"A: {answer.answer_text}"
        )
        
        return {
            "success": True,
            "answer": {
                "id": answer.id,
                "text": answer.answer_text,
                "created_at": answer.created_at.isoformat()
            }
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error creating answer: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="Internal server error")

@router.get("/consultations")
async def get_consultations(
    skip: int = Query(0, ge=0),
    limit: int = Query(50, gt=0, le=100),
    status: Optional[str] = None,
    date_from: Optional[datetime] = None,
    date_to: Optional[datetime] = None,
    session: AsyncSession = Depends(get_session),
    admin: User = Depends(get_current_admin)
):
    """Get paginated consultations list"""
    try:
        # Build query
        query = select(Consultation).options(
            joinedload(Consultation.user),
            joinedload(Consultation.payments)
        )
        
        # Apply filters
        if status:
            query = query.filter(
                Consultation.status == ConsultationStatus[status]
            )
            
        if date_from:
            query = query.filter(Consultation.created_at >= date_from)
        if date_to:
            query = query.filter(Consultation.created_at <= date_to)
            
        # Get total count
        total = await session.scalar(
            select(func.count()).select_from(query.subquery())
        )
        
        # Get paginated results
        query = query.order_by(Consultation.created_at.desc())
        query = query.offset(skip).limit(limit)
        result = await session.execute(query)
        consultations = result.unique().scalars().all()
        
        return {
            "total": total,
            "page": skip // limit + 1,
            "pages": (total + limit - 1) // limit,
            "items": [
                {
                    "id": c.id,
                    "status": c.status.value,
                    "amount": float(c.amount),
                    "scheduled_time": c.scheduled_time.isoformat() if c.scheduled_time else None,
                    "user": {
                        "id": c.user.id,
                        "username": c.user.username,
                        "full_name": c.user.full_name
                    },
                    "payments": [
                        {
                            "id": p.id,
                            "status": p.status.value,
                            "provider": p.provider.value,
                            "amount": float(p.amount),
                            "created_at": p.created_at.isoformat()
                        }
                        for p in c.payments
                    ],
                    "created_at": c.created_at.isoformat()
                }
                for c in consultations
            ]
        }
        
    except Exception as e:
        logger.error(f"Error getting consultations: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="Internal server error")

@router.post("/consultations/{consultation_id}/status")
async def update_consultation_status(
    consultation_id: int,
    data: Dict = Body(...),
    session: AsyncSession = Depends(get_session),
    admin: User = Depends(get_current_admin)
):
    """Update consultation status"""
    try:
        consultation_service = ConsultationService(session)
        consultation = await consultation_service.get_consultation(consultation_id)
        
        if not consultation:
            raise HTTPException(status_code=404, detail="Consultation not found")
            
        # Update status
        new_status = ConsultationStatus[data["status"]]
        old_status = consultation.status
        
        consultation.status = new_status
        consultation.metadata = consultation.metadata or {}
        consultation.metadata["status_history"] = consultation.metadata.get("status_history", [])
        consultation.metadata["status_history"].append({
            "from": old_status.value,
            "to": new_status.value,
            "changed_by": admin.id,
            "changed_at": datetime.utcnow().isoformat(),
            "reason": data.get("reason")
        })
        
        # Handle scheduled time
        if new_status == ConsultationStatus.SCHEDULED and "scheduled_time" in data:
            consultation.scheduled_time = datetime.fromisoformat(data["scheduled_time"])
            
        await session.commit()
        
        # Notify user
        from telegram_bot.bot import bot
        notification = f"Your consultation status has been updated to: {new_status.value}"
        if consultation.scheduled_time:
            notification += f"\nScheduled for: {consultation.scheduled_time.strftime('%Y-%m-%d %H:%M')}"
            
        await bot.send_message(
            consultation.user.telegram_id,
            notification
        )
        
        return {
            "success": True,
            "status": new_status.value,
            "scheduled_time": consultation.scheduled_time.isoformat() if consultation.scheduled_time else None
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error updating consultation status: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="Internal server error")

@router.get("/analytics/export")
async def export_analytics(
    start_date: datetime,
    end_date: datetime,
    report_type: str = Query(..., enum=["users", "questions", "consultations", "payments"]),
    format: str = Query("csv", enum=["csv", "xlsx"]),
    session: AsyncSession = Depends(get_session),
    admin: User = Depends(get_current_admin)
):
    """Export analytics data"""
    try:
        analytics = AnalyticsService(session)
        
        if report_type == "users":
            data = await analytics.export_users_data(start_date, end_date)
        elif report_type == "questions":
            data = await analytics.export_questions_data(start_date, end_date)
        elif report_type == "consultations":
            data = await analytics.export_consultations_data(start_date, end_date)
        else:
            data = await analytics.export_payments_data(start_date, end_date)
            
        # Generate file
        filename = f"{report_type}_{start_date.date()}_{end_date.date()}"
        if format == "csv":
            file_content = analytics.generate_csv(data)
            media_type = "text/csv"
            filename += ".csv"
        else:
            file_content = analytics.generate_excel(data)
            media_type = "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
            filename += ".xlsx"
            
        # Track export
        await analytics.track_admin_action(
            admin_id=admin.id,
            action="export_data",
            details={
                "type": report_type,
                "format": format,
                "start_date": start_date.isoformat(),
                "end_date": end_date.isoformat()
            }
        )
        
        return Response(
            content=file_content,
            media_type=media_type,
            headers={
                'Content-Disposition': f'attachment; filename="{filename}"'
            }
        )
        
    except Exception as e:
        logger.error(f"Error exporting analytics: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="Internal server error")

@router.post("/broadcast")
async def send_broadcast(
    data: Dict = Body(...),
    session: AsyncSession = Depends(get_session),
    admin: User = Depends(get_current_admin)
):
    """Send broadcast message to users"""
    try:
        # Validate message
        if not data.get("message"):
            raise HTTPException(status_code=400, detail="Message is required")
            
        # Build user query
        query = select(User.telegram_id).filter(User.is_blocked == False)
        
        # Apply filters
        if data.get("language"):
            query = query.filter(User.language == data["language"])
            
        if data.get("active_only"):
            week_ago = datetime.utcnow() - timedelta(days=7)
            query = query.filter(User.last_active >= week_ago)
            
        # Get user IDs
        result = await session.execute(query)
        user_ids = result.scalars().all()
        
        if not user_ids:
            raise HTTPException(status_code=400, detail="No users match the criteria")
            
        # Send messages
        from telegram_bot.bot import bot
        sent = 0
        failed = 0
        
        for user_id in user_ids:
            try:
                await bot.send_message(
                    user_id,
                    data["message"],
                    parse_mode=data.get("parse_mode", "HTML")
                )
                sent += 1
                await asyncio.sleep(0.05)  # Rate limiting
            except Exception as e:
                logger.error(f"Error sending broadcast to {user_id}: {e}")
                failed += 1
                
        # Track broadcast
        analytics = AnalyticsService(session)
        await analytics.track_admin_action(
            admin_id=admin.id,
            action="broadcast",
            details={
                "sent": sent,
                "failed": failed,
                "total": len(user_ids),
                "filters": {
                    "language": data.get("language"),
                    "active_only": data.get("active_only")
                }
            }
        )
        
        return {
            "success": True,
            "sent": sent,
            "failed": failed,
            "total": len(user_ids)
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error sending broadcast: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="Internal server error")

@router.get("/logs")
async def get_system_logs(
    level: str = Query("ERROR", enum=["DEBUG", "INFO", "WARNING", "ERROR"]),
    start_date: Optional[datetime] = None,
    end_date: Optional[datetime] = None,
    limit: int = Query(100, le=1000),
    session: AsyncSession = Depends(get_session),
    admin: User = Depends(get_current_admin)
):
    """Get system logs"""
    try:
        # Build log query
        query = "SELECT timestamp, level, message, data FROM system_logs WHERE level >= :level"
        params = {"level": level}
        
        if start_date:
            query += " AND timestamp >= :start_date"
            params["start_date"] = start_date
            
        if end_date:
            query += " AND timestamp <= :end_date"
            params["end_date"] = end_date
            
        query += " ORDER BY timestamp DESC LIMIT :limit"
        params["limit"] = limit
        
        result = await session.execute(text(query), params)
        logs = result.mappings().all()
        
        return {
            "total": len(logs),
            "items": [
                {
                    "timestamp": log["timestamp"].isoformat(),
                    "level": log["level"],
                    "message": log["message"],
                    "data": log["data"]
                }
                for log in logs
            ]
        }
        
    except Exception as e:
        logger.error(f"Error getting system logs: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="Internal server error")

@router.get("/system/health")
async def get_system_health(
    session: AsyncSession = Depends(get_session),
    admin: User = Depends(get_current_admin)
):
    """Get system health status"""
    try:
        # Check database
        db_status = await session.execute(text("SELECT 1"))
        db_healthy = bool(db_status.scalar())
        
        # Check Redis
        redis_healthy = await cache.health_check()
        
        # Check bot
        from telegram_bot.bot import bot
        try:
            bot_info = await bot.get_me()
            bot_healthy = True
        except Exception:
            bot_healthy = False
            
        # Get system metrics
        import psutil
        cpu_percent = psutil.cpu_percent()
        memory = psutil.virtual_memory()
        disk = psutil.disk_usage('/')
        
        return {
            "status": "healthy" if all([db_healthy, redis_healthy, bot_healthy]) else "unhealthy",
            "timestamp": datetime.utcnow().isoformat(),
            "components": {
                "database": {
                    "status": "up" if db_healthy else "down"
                },
                "cache": {
                    "status": "up" if redis_healthy else "down"
                },
                "bot": {
                    "status": "up" if bot_healthy else "down"
                }
            },
            "metrics": {
                "cpu_usage": cpu_percent,
                "memory_usage": {
                    "total": memory.total,
                    "used": memory.used,
                    "percent": memory.percent
                },
                "disk_usage": {
                    "total": disk.total,
                    "used": disk.used,
                    "percent": disk.percent
                }
            }
        }
        
    except Exception as e:
        logger.error(f"Error getting system health: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="Internal server error")

@router.post("/system/cache/clear")
async def clear_system_cache(session,
    cache_type: str = Query(..., enum=["all", "users", "questions", "stats"]),
    admin: User = Depends(get_current_admin),
    
):
    """Clear system cache"""
    try:
        if cache_type == "all":
            await cache.clear_all()
        else:
            pattern = f"{cache_type}:*"
            await cache.clear_pattern(pattern)
            
        # Track action
        analytics = AnalyticsService(session)
        await analytics.track_admin_action(
            admin_id=admin.id,
            action="clear_cache",
            details={"type": cache_type}
        )
        
        return {"success": True}
        
    except Exception as e:
        logger.error(f"Error clearing cache: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="Internal server error")


@router.get("/faq/categories")
async def get_faq_categories(
    language: Optional[str] = None,
    session: AsyncSession = Depends(get_session),
    admin: User = Depends(get_current_admin)
):
    """Get FAQ categories"""
    faq_service = FAQService(session)
    categories = await faq_service.get_faq_categories(language)
    return {"items": categories}

@router.post("/faq/categories")
async def create_faq_category(
    name: dict,  # {'uz': '...', 'ru': '...'}
    description: Optional[dict] = None,
    icon: Optional[str] = None,
    session: AsyncSession = Depends(get_session),
    admin: User = Depends(get_current_admin)
):
    """Create FAQ category"""
    faq_service = FAQService(session)
    category = await faq_service.create_category(
        name=name,
        description=description,
        icon=icon
    )
    return category

@router.get("/faq/{category_id}")
async def get_category_faqs(
    category_id: int,
    language: Optional[str] = None,
    session: AsyncSession = Depends(get_session),
    admin: User = Depends(get_current_admin)
):
    """Get FAQs in category"""
    faq_service = FAQService(session)
    faqs = await faq_service.get_category_faqs(category_id, language)
    return {"items": faqs}

@router.post("/faq")
async def create_faq(
    category_id: int,
    question: dict,  # {'uz': '...', 'ru': '...'}
    answer: dict,    # {'uz': '...', 'ru': '...'}
    is_published: bool = True,
    session: AsyncSession = Depends(get_session),
    admin: User = Depends(get_current_admin)
):
    """Create FAQ"""
    faq_service = FAQService(session)
    faq = await faq_service.create_faq(
        category_id=category_id,
        question=question,
        answer=answer,
        is_published=is_published
    )
    return faq

@router.get("/analytics/dashboard")
async def get_analytics_dashboard(
    period: str = Query("week", enum=["day", "week", "month"]),
    session: AsyncSession = Depends(get_session),
    admin: User = Depends(get_current_admin)
):
    """Get analytics dashboard data"""
    analytics = AnalyticsService(session)
    
    # Get date range
    end_date = datetime.utcnow()
    if period == "day":
        start_date = end_date - timedelta(days=1)
    elif period == "week":
        start_date = end_date - timedelta(weeks=1)
    else:
        start_date = end_date - timedelta(days=30)
        
    # Get analytics data
    data = await analytics.get_dashboard_stats(
        start_date=start_date,
        end_date=end_date
    )
    
    return data

@router.get("/analytics/export")
async def export_analytics(
    start_date: datetime,
    end_date: datetime,
    format: str = Query("csv", enum=["csv", "xlsx"]),
    session: AsyncSession = Depends(get_session),
    admin: User = Depends(get_current_admin)
):
    """Export analytics data"""
    analytics = AnalyticsService(session)
    
    data = await analytics.export_data(
        start_date=start_date,
        end_date=end_date
    )
    
    if format == "csv":
        return analytics.export_csv(data)
    else:
        return analytics.export_excel(data)

@router.get("/users/stats")
async def get_user_statistics(
    period: str = Query("week", enum=["day", "week", "month"]),
    session: AsyncSession = Depends(get_session),
    admin: User = Depends(get_current_admin)
):
    """Get user statistics"""
    analytics = AnalyticsService(session)
    
    end_date = datetime.utcnow()
    if period == "day":
        start_date = end_date - timedelta(days=1)
    elif period == "week":
        start_date = end_date - timedelta(weeks=1)
    else:
        start_date = end_date - timedelta(days=30)
        
    stats = await analytics.get_user_stats(
        start_date=start_date,
        end_date=end_date
    )
    
    return stats

@router.get("/users/active")
async def get_active_users(
    days: int = Query(7, ge=1, le=30),
    session: AsyncSession = Depends(get_session),
    admin: User = Depends(get_current_admin)
):
    """Get active users"""
    analytics = AnalyticsService(session)
    users = await analytics.get_active_users(days=days)
    return {"items": users}



def register_admin_routes(app):
    """Register admin routes"""
    app.include_router(router)
```

# telegram_bot\admin\auth.py

```py
from datetime import datetime, timedelta
from typing import Optional
from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from jose import JWTError, jwt
from passlib.context import CryptContext
from sqlalchemy.ext.asyncio import AsyncSession

from telegram_bot.core.config import settings
from telegram_bot.core.database import get_session
from telegram_bot.models import User
from sqlalchemy import select
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="admin/token")

class AuthService:
    def __init__(self, session: AsyncSession):
        self.session = session

    def verify_password(self, plain_password: str, hashed_password: str) -> bool:
        return pwd_context.verify(plain_password, hashed_password)

    def get_password_hash(self, password: str) -> str:
        return pwd_context.hash(password)

    def create_access_token(self, data: dict, expires_delta: Optional[timedelta] = None) -> str:
        to_encode = data.copy()
        if expires_delta:
            expire = datetime.utcnow() + expires_delta
        else:
            expire = datetime.utcnow() + timedelta(minutes=60)
        to_encode.update({"exp": expire})
        encoded_jwt = jwt.encode(
            to_encode,
            settings.SECRET_KEY.get_secret_value(),
            algorithm="HS256"
        )
        return encoded_jwt

    async def authenticate_user(self, username: str, password: str) -> Optional[User]:
        user = await self.get_user_by_username(username)
        if not user or not user.is_admin:
            return None
        if not self.verify_password(password, user.password_hash):
            return None
        return user

    async def get_user_by_username(self, username: str) -> Optional[User]:
        query = select(User).where(User.username == username)
        result = await self.session.execute(query)
        return result.scalar_one_or_none()

async def get_current_admin(
    token: str = Depends(oauth2_scheme),
    session: AsyncSession = Depends(get_session)
) -> User:
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )
    try:
        payload = jwt.decode(
            token,
            settings.SECRET_KEY.get_secret_value(),
            algorithms=["HS256"]
        )
        username: str = payload.get("sub")
        if username is None:
            raise credentials_exception
    except JWTError:
        raise credentials_exception

    auth_service = AuthService(session)
    user = await auth_service.get_user_by_username(username)
    if user is None or not user.is_admin:
        raise credentials_exception
    return user
```

# telegram_bot\admin\templates\base.html

```html
<!-- File: /telegram_bot/admin/templates/base.html --> <!DOCTYPE html> <html lang="en"> <head> <meta charset="UTF-8"> <meta name="viewport" content="width=device-width, initial-scale=1.0"> <title>{% block title %}Law Bot Admin{% endblock %}</title> <!-- Tailwind CSS --> <script src="https://cdn.tailwindcss.com"></script> <!-- Chart.js --> <script src="https://cdn.jsdelivr.net/npm/chart.js"></script> <!-- Font Awesome --> <link rel="stylesheet" href="https://cdnjs.cloudflare.com/ajax/libs/font-awesome/6.0.0/css/all.min.css"> </head> <body class="bg-gray-100"> <div class="min-h-screen flex"> <!-- Sidebar --> <aside class="w-64 bg-indigo-700 text-white"> <div class="p-4"> <h1 class="text-2xl font-bold">Law Bot Admin</h1> </div> <nav class="mt-8"> <a href="{{ url_for('admin.dashboard') }}" class="block py-2.5 px-4 rounded transition duration-200 hover:bg-indigo-600 {% if request.endpoint == 'admin.dashboard' %}bg-indigo-800{% endif %}"> <i class="fas fa-home mr-2"></i> Dashboard </a> <a href="{{ url_for('admin.users') }}" class="block py-2.5 px-4 rounded transition duration-200 hover:bg-indigo-600 {% if request.endpoint == 'admin.users' %}bg-indigo-800{% endif %}"> <i class="fas fa-users mr-2"></i> Users </a> <a href="{{ url_for('admin.questions') }}" class="block py-2.5 px-4 rounded transition duration-200 hover:bg-indigo-600 {% if request.endpoint == 'admin.questions' %}bg-indigo-800{% endif %}"> <i class="fas fa-question-circle mr-2"></i> Questions </a> <a href="{{ url_for('admin.consultations') }}" class="block py-2.5 px-4 rounded transition duration-200 hover:bg-indigo-600 {% if request.endpoint == 'admin.consultations' %}bg-indigo-800{% endif %}"> <i class="fas fa-calendar mr-2"></i> Consultations </a> <a href="{{ url_for('admin.payments') }}" class="block py-2.5 px-4 rounded transition duration-200 hover:bg-indigo-600 {% if request.endpoint == 'admin.payments' %}bg-indigo-800{% endif %}"> <i class="fas fa-credit-card mr-2"></i> Payments </a> <a href="{{ url_for('admin.analytics') }}" class="block py-2.5 px-4 rounded transition duration-200 hover:bg-indigo-600 {% if request.endpoint == 'admin.analytics' %}bg-indigo-800{% endif %}"> <i class="fas fa-chart-line mr-2"></i> Analytics </a> <a href="{{ url_for('admin.settings') }}" class="block py-2.5 px-4 rounded transition duration-200 hover:bg-indigo-600 {% if request.endpoint == 'admin.settings' %}bg-indigo-800{% endif %}"> <i class="fas fa-cog mr-2"></i> Settings </a> </nav> </aside> <!-- Main Content --> <main class="flex-1 p-8"> {% block content %}{% endblock %} </main> </div> <!-- JavaScript --> {% block scripts %}{% endblock %} </body> </html>
```

# telegram_bot\admin\templates\consultations.html

```html
<!-- File: /telegram_bot/admin/templates/consultations.html --> {% extends "base.html" %} {% block title %}Consultations - Law Bot Admin{% endblock %} {% block content %} <div class="space-y-6"> <!-- Header --> <div class="flex items-center justify-between"> <h1 class="text-2xl font-semibold text-gray-900">Consultations</h1> <!-- Filters --> <div class="flex space-x-4"> <select class="rounded-lg border-gray-300 focus:ring-indigo-500 focus:border-indigo-500" v-model="status"> <option value="">All Status</option> <option value="PENDING">Pending</option> <option value="PAID">Paid</option> <option value="SCHEDULED">Scheduled</option> <option value="COMPLETED">Completed</option> <option value="CANCELLED">Cancelled</option> </select> <input type="date" class="rounded-lg border-gray-300 focus:ring-indigo-500 focus:border-indigo-500" v-model="date"> </div> </div> <!-- Consultations Table --> <div class="bg-white shadow overflow-hidden sm:rounded-lg"> <table class="min-w-full divide-y divide-gray-200"> <thead class="bg-gray-50"> <tr> <th class="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider"> Client </th> <th class="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider"> Status </th> <th class="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider"> Amount </th> <th class="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider"> Scheduled </th> <th class="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider"> Payment </th> <!-- File: /telegram_bot/admin/templates/consultations.html (продолжение) --> <th class="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider"> Actions </th> </tr> </thead> <tbody class="bg-white divide-y divide-gray-200"> {% for consultation in consultations %} <tr> <td class="px-6 py-4 whitespace-nowrap"> <div class="flex items-center"> <div> <div class="text-sm font-medium text-gray-900"> {{ consultation.user.full_name }} </div> <div class="text-sm text-gray-500"> {{ consultation.user.phone_number }} </div> </div> </div> </td> <td class="px-6 py-4 whitespace-nowrap"> <span class="px-2 inline-flex text-xs leading-5 font-semibold rounded-full {% if consultation.status == 'PENDING' %}bg-yellow-100 text-yellow-800 {% elif consultation.status == 'PAID' %}bg-blue-100 text-blue-800 {% elif consultation.status == 'SCHEDULED' %}bg-purple-100 text-purple-800 {% elif consultation.status == 'COMPLETED' %}bg-green-100 text-green-800 {% else %}bg-red-100 text-red-800{% endif %}"> {{ consultation.status }} </span> </td> <td class="px-6 py-4 whitespace-nowrap text-sm text-gray-500"> {{ consultation.amount | money }} </td> <td class="px-6 py-4 whitespace-nowrap text-sm text-gray-500"> {% if consultation.scheduled_time %} {{ consultation.scheduled_time | datetime }} {% else %} Not scheduled {% endif %} </td> <td class="px-6 py-4 whitespace-nowrap"> {% if consultation.payments %} {% for payment in consultation.payments %} <div class="text-sm"> <span class="font-medium text-gray-900">{{ payment.provider }}</span> <span class="px-2 inline-flex text-xs leading-5 font-semibold rounded-full {% if payment.status == 'COMPLETED' %}bg-green-100 text-green-800 {% elif payment.status == 'PENDING' %}bg-yellow-100 text-yellow-800 {% else %}bg-red-100 text-red-800{% endif %}"> {{ payment.status }} </span> </div> {% endfor %} {% else %} <span class="text-sm text-gray-500">No payments</span> {% endif %} </td> <td class="px-6 py-4 whitespace-nowrap text-right text-sm font-medium"> <button @click="viewConsultation({{ consultation.id }})" class="text-indigo-600 hover:text-indigo-900 mr-3"> View </button> {% if consultation.status == 'PENDING' %} <button @click="approveConsultation({{ consultation.id }})" class="text-green-600 hover:text-green-900 mr-3"> Approve </button> {% endif %} {% if consultation.status == 'PAID' %} <button @click="scheduleConsultation({{ consultation.id }})" class="text-blue-600 hover:text-blue-900 mr-3"> Schedule </button> {% endif %} {% if consultation.status != 'COMPLETED' and consultation.status != 'CANCELLED' %} <button @click="cancelConsultation({{ consultation.id }})" class="text-red-600 hover:text-red-900"> Cancel </button> {% endif %} </td> </tr> {% endfor %} </tbody> </table> </div> <!-- Pagination --> <div class="bg-white px-4 py-3 flex items-center justify-between border-t border-gray-200 sm:px-6"> <div class="flex-1 flex justify-between sm:hidden"> {% if pagination.has_prev %} <a href="?page={{ pagination.prev_num }}" class="relative inline-flex items-center px-4 py-2 border border-gray-300 text-sm font-medium rounded-md text-gray-700 bg-white hover:bg-gray-50"> Previous </a> {% endif %} {% if pagination.has_next %} <a href="?page={{ pagination.next_num }}" class="ml-3 relative inline-flex items-center px-4 py-2 border border-gray-300 text-sm font-medium rounded-md text-gray-700 bg-white hover:bg-gray-50"> Next </a> {% endif %} </div> <div class="hidden sm:flex-1 sm:flex sm:items-center sm:justify-between"> <div> <p class="text-sm text-gray-700"> Showing <span class="font-medium">{{ pagination.start }}</span> to <span class="font-medium">{{ pagination.end }}</span> of <span class="font-medium">{{ pagination.total }}</span> results </p> </div> <div> <nav class="relative z-0 inline-flex rounded-md shadow-sm -space-x-px"> {% for page in pagination.iter_pages() %} {% if page %} <a href="?page={{ page }}" class="relative inline-flex items-center px-4 py-2 border border-gray-300 bg-white text-sm font-medium {% if page == pagination.page %}text-indigo-600 border-indigo-500{% else %}text-gray-700 hover:bg-gray-50{% endif %}"> {{ page }} </a> {% else %} <span class="relative inline-flex items-center px-4 py-2 border border-gray-300 bg-white text-sm font-medium text-gray-700"> ... </span> {% endif %} {% endfor %} </nav> </div> </div> </div> </div> <!-- Schedule Modal --> <div v-if="showScheduleModal" class="fixed z-10 inset-0 overflow-y-auto"> <div class="flex items-end justify-center min-h-screen pt-4 px-4 pb-20 text-center sm:block sm:p-0"> <div class="fixed inset-0 bg-gray-500 bg-opacity-75 transition-opacity"></div> <div class="inline-block align-bottom bg-white rounded-lg text-left overflow-hidden shadow-xl transform transition-all sm:my-8 sm:align-middle sm:max-w-lg sm:w-full"> <div class="bg-white px-4 pt-5 pb-4 sm:p-6 sm:pb-4"> <div class="sm:flex sm:items-start"> <div class="mt-3 text-center sm:mt-0 sm:text-left w-full"> <h3 class="text-lg leading-6 font-medium text-gray-900"> Schedule Consultation </h3> <div class="mt-4 space-y-4"> <div> <label class="block text-sm font-medium text-gray-700"> Date </label> <input type="date" v-model="scheduleDate" class="mt-1 block w-full rounded-md border-gray-300 shadow-sm focus:border-indigo-500 focus:ring-indigo-500"> </div> <div> <label class="block text-sm font-medium text-gray-700"> Time </label> <select v-model="scheduleTime" class="mt-1 block w-full rounded-md border-gray-300 shadow-sm focus:border-indigo-500 focus:ring-indigo-500"> <option v-for="time in availableTimes" :value="time"> {{ time }} </option> </select> </div> </div> </div> </div> </div> <div class="bg-gray-50 px-4 py-3 sm:px-6 sm:flex sm:flex-row-reverse"> <button @click="submitSchedule" class="w-full inline-flex justify-center rounded-md border border-transparent shadow-sm px-4 py-2 bg-indigo-600 text-base font-medium text-white hover:bg-indigo-700 focus:outline-none focus:ring-2 focus:ring-offset-2 focus:ring-indigo-500 sm:ml-3 sm:w-auto sm:text-sm"> Schedule </button> <button @click="showScheduleModal = false" class="mt-3 w-full inline-flex justify-center rounded-md border border-gray-300 shadow-sm px-4 py-2 bg-white text-base font-medium text-gray-700 hover:bg-gray-50 focus:outline-none focus:ring-2 focus:ring-offset-2 focus:ring-indigo-500 sm:mt-0 sm:ml-3 sm:w-auto sm:text-sm"> Cancel </button> </div> </div> </div> </div> {% endblock %} {% block scripts %} <script> new Vue({ el: '#app', data: { status: '', date: '', showScheduleModal: false, selectedConsultation: null, scheduleDate: '', scheduleTime: '', availableTimes: [], consultations: {{ consultations | tojson }}, pagination: {{ pagination | tojson }} }, methods: { async viewConsultation(consultationId) { window.location.href = `/admin/consultations/${consultationId}`; }, async approveConsultation(consultationId) { if (confirm('Are you sure you want to approve this consultation?')) { try { const response = await fetch(`/api/admin/consultations/${consultationId}/approve`, { method: 'POST' }); if (response.ok) { window.location.reload(); } else { alert('Failed to approve consultation'); } } catch (error) { console.error('Error:', error); alert('Failed to approve consultation'); } } }, async scheduleConsultation(consultationId) { this.selectedConsultation = consultationId; this.showScheduleModal = true; await this.loadAvailableTimes(); }, async loadAvailableTimes() { try { const response = await fetch(`/api/admin/consultations/available-times?date=${this.scheduleDate}`); const data = await response.json(); this.availableTimes = data.times; } catch (error) { console.error('Error:', error); alert('Failed to load available times'); } }, async submitSchedule() { try { const response = await fetch(`/api/admin/consultations/${this.selectedConsultation}/schedule`, { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ date: this.scheduleDate, time: this.scheduleTime }) }); if (response.ok) { window.location.reload(); } else { alert('Failed to schedule consultation'); } } catch (error) { console.error('Error:', error); alert('Failed to schedule consultation'); } }, async cancelConsultation(consultationId) { if (confirm('Are you sure you want to cancel this consultation?')) { try { const response = await fetch(`/api/admin/consultations/${consultationId}/cancel`, { method: 'POST' }); if (response.ok) { window.location.reload(); } else { alert('Failed to cancel consultation'); } } catch (error) { console.error('Error:', error); alert('Failed to cancel consultation'); } } } }, watch: { status() { this.fetchConsultations(); }, date() { this.fetchConsultations(); }, scheduleDate() { this.loadAvailableTimes(); } }, methods: { async fetchConsultations() { try { const params = new URLSearchParams({ status: this.status, date: this.date }); const response = await fetch(`/api/admin/consultations?${params}`); const data = await response.json(); this.consultations = data.items; this.pagination = data.pagination; } catch (error) { console.error('Error:', error); } } } }); </script> {% endblock %}
```

# telegram_bot\admin\templates\dashboard.html

```html
{% extends "base.html" %} {% block title %}Dashboard - Law Bot Admin{% endblock %} {% block content %} <!-- File: /telegram_bot/admin/templates/dashboard.html (продолжение) --> <div class="space-y-6"> <!-- Stats Cards --> <div class="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-6"> <!-- Users Card --> <div class="bg-white rounded-lg shadow p-6"> <div class="flex items-center justify-between"> <h3 class="text-gray-500 text-sm font-medium">Total Users</h3> <i class="fas fa-users text-indigo-500"></i> </div> <p class="mt-2 text-3xl font-semibold">{{ stats.users.total }}</p> <div class="mt-2 flex items-center text-sm"> <span class="text-green-500">↑ {{ stats.users.new_week }}</span> <span class="ml-2 text-gray-500">vs last week</span> </div> </div> <!-- Questions Card --> <div class="bg-white rounded-lg shadow p-6"> <div class="flex items-center justify-between"> <h3 class="text-gray-500 text-sm font-medium">Questions</h3> <i class="fas fa-question-circle text-indigo-500"></i> </div> <p class="mt-2 text-3xl font-semibold">{{ stats.questions.total }}</p> <div class="mt-2 flex items-center text-sm"> <span class="text-yellow-500">{{ stats.questions.unanswered }}</span> <span class="ml-2 text-gray-500">unanswered</span> </div> </div> <!-- Consultations Card --> <div class="bg-white rounded-lg shadow p-6"> <div class="flex items-center justify-between"> <h3 class="text-gray-500 text-sm font-medium">Consultations</h3> <i class="fas fa-calendar text-indigo-500"></i> </div> <p class="mt-2 text-3xl font-semibold">{{ stats.consultations.total }}</p> <div class="mt-2 flex items-center text-sm"> <span class="text-blue-500">{{ stats.consultations.pending }}</span> <span class="ml-2 text-gray-500">pending</span> </div> </div> <!-- Revenue Card --> <div class="bg-white rounded-lg shadow p-6"> <div class="flex items-center justify-between"> <h3 class="text-gray-500 text-sm font-medium">Revenue</h3> <i class="fas fa-dollar-sign text-indigo-500"></i> </div> <p class="mt-2 text-3xl font-semibold">{{ stats.payments.amount | money }}</p> <div class="mt-2 flex items-center text-sm"> <span class="text-green-500">↑ {{ stats.payments.growth }}%</span> <span class="ml-2 text-gray-500">vs last month</span> </div> </div> </div> <!-- Charts --> <div class="grid grid-cols-1 lg:grid-cols-2 gap-6"> <!-- Users Growth Chart --> <div class="bg-white rounded-lg shadow p-6"> <h3 class="text-lg font-medium text-gray-900">User Growth</h3> <canvas id="usersChart" height="300"></canvas> </div> <!-- Revenue Chart --> <div class="bg-white rounded-lg shadow p-6"> <h3 class="text-lg font-medium text-gray-900">Revenue</h3> <canvas id="revenueChart" height="300"></canvas> </div> </div> <!-- Recent Activity --> <div class="bg-white rounded-lg shadow p-6"> <h3 class="text-lg font-medium text-gray-900 mb-4">Recent Activity</h3> <div class="space-y-4"> {% for activity in recent_activity %} <div class="flex items-center"> <div class="w-8 h-8 rounded-full bg-indigo-100 flex items-center justify-center"> <i class="fas fa-{{ activity.icon }} text-indigo-500"></i> </div> <div class="ml-4"> <p class="text-sm font-medium text-gray-900">{{ activity.text }}</p> <p class="text-sm text-gray-500">{{ activity.time | timeago }}</p> </div> </div> {% endfor %} </div> </div> </div> {% endblock %} {% block scripts %} <script> // Users Growth Chart const usersCtx = document.getElementById('usersChart').getContext('2d'); new Chart(usersCtx, { type: 'line', data: { labels: {{ users_chart.labels | tojson }}, datasets: [{ label: 'New Users', data: {{ users_chart.data | tojson }}, borderColor: '#6366F1', tension: 0.3 }] }, options: { responsive: true, maintainAspectRatio: false } }); // Revenue Chart const revenueCtx = document.getElementById('revenueChart').getContext('2d'); new Chart(revenueCtx, { type: 'bar', data: { labels: {{ revenue_chart.labels | tojson }}, datasets: [{ label: 'Revenue', data: {{ revenue_chart.data | tojson }}, backgroundColor: '#6366F1' }] }, options: { responsive: true, maintainAspectRatio: false } }); </script> {% endblock %}
```

# telegram_bot\admin\templates\login.html

```html
<!DOCTYPE html> <html lang="en"> <head> <meta charset="UTF-8"> <meta name="viewport" content="width=device-width, initial-scale=1.0"> <title>Admin Login | Law Bot</title> <script src="https://cdn.tailwindcss.com"></script> </head> <body class="bg-gray-100"> <div class="min-h-screen flex items-center justify-center"> <div class="max-w-md w-full"> <div class="bg-white py-8 px-6 shadow-lg rounded-lg"> <div class="text-center mb-8"> <h2 class="text-2xl font-bold text-gray-900">Admin Panel</h2> <p class="mt-2 text-sm text-gray-600">Please sign in to continue</p> </div> <form id="loginForm" class="space-y-6"> <div> <label for="username" class="block text-sm font-medium text-gray-700">Username</label> <input type="text" id="username" name="username" required class="mt-1 block w-full px-3 py-2 border border-gray-300 rounded-md shadow-sm focus:outline-none focus:ring-indigo-500 focus:border-indigo-500"> </div> <div> <label for="password" class="block text-sm font-medium text-gray-700">Password</label> <input type="password" id="password" name="password" required class="mt-1 block w-full px-3 py-2 border border-gray-300 rounded-md shadow-sm focus:outline-none focus:ring-indigo-500 focus:border-indigo-500"> </div> <div class="flex items-center justify-between"> <div class="flex items-center"> <input type="checkbox" id="remember" name="remember" class="h-4 w-4 text-indigo-600 focus:ring-indigo-500 border-gray-300 rounded"> <label for="remember" class="ml-2 block text-sm text-gray-900">Remember me</label> </div> </div> <div> <button type="submit" class="w-full flex justify-center py-2 px-4 border border-transparent rounded-md shadow-sm text-sm font-medium text-white bg-indigo-600 hover:bg-indigo-700 focus:outline-none focus:ring-2 focus:ring-offset-2 focus:ring-indigo-500"> Sign in </button> </div> </form> <!-- Error message --> <div id="errorMessage" class="mt-4 hidden"> <div class="bg-red-50 border-l-4 border-red-400 p-4"> <div class="flex"> <div class="flex-shrink-0"> <svg class="h-5 w-5 text-red-400" xmlns="http://www.w3.org/2000/svg" viewBox="0 0 20 20" fill="currentColor"> <path fill-rule="evenodd" d="M10 18a8 8 0 100-16 8 8 0 000 16zM8.707 7.293a1 1 0 00-1.414 1.414L8.586 10l-1.293 1.293a1 1 0 101.414 1.414L10 11.414l1.293 1.293a1 1 0 001.414-1.414L11.414 10l1.293-1.293a1 1 0 00-1.414-1.414L10 8.586 8.707 7.293z" clip-rule="evenodd" /> </svg> </div> <div class="ml-3"> <p class="text-sm text-red-700" id="errorText"></p> </div> </div> </div> </div> </div> </div> </div> <script> document.getElementById('loginForm').addEventListener('submit', async (e) => { e.preventDefault(); const username = document.getElementById('username').value; const password = document.getElementById('password').value; const remember = document.getElementById('remember').checked; try { const response = await fetch('/admin/token', { method: 'POST', headers: { 'Content-Type': 'application/x-www-form-urlencoded', }, body: `username=${encodeURIComponent(username)}&password=${encodeURIComponent(password)}` }); if (response.ok) { const data = await response.json(); if (remember) { localStorage.setItem('admin_token', data.access_token); } else { sessionStorage.setItem('admin_token', data.access_token); } window.location.href = '/admin'; } else { const errorData = await response.json(); showError(errorData.detail || 'Invalid credentials'); } } catch (error) { showError('An error occurred. Please try again.'); } }); function showError(message) { const errorDiv = document.getElementById('errorMessage'); const errorText = document.getElementById('errorText'); errorText.textContent = message; errorDiv.classList.remove('hidden'); } </script> </body> </html>
```

# telegram_bot\admin\templates\payments.html

```html
<!-- File: /telegram_bot/admin/templates/payments.html --> {% extends "base.html" %} {% block title %}Payments - Law Bot Admin{% endblock %} {% block content %} <div class="space-y-6"> <!-- Header --> <div class="flex items-center justify-between"> <h1 class="text-2xl font-semibold text-gray-900">Payments</h1> <!-- Filters --> <div class="flex space-x-4"> <select class="rounded-lg border-gray-300 focus:ring-indigo-500 focus:border-indigo-500" v-model="status"> <option value="">All Status</option> <option value="PENDING">Pending</option> <option value="COMPLETED">Completed</option> <option value="FAILED">Failed</option> <option value="REFUNDED">Refunded</option> </select> <select class="rounded-lg border-gray-300 focus:ring-indigo-500 focus:border-indigo-500" v-model="provider"> <option value="">All Providers</option> <option value="click">Click</option> <option value="payme">Payme</option> <option value="uzum">Uzum</option> </select> <div class="flex space-x-2"> <input type="date" class="rounded-lg border-gray-300 focus:ring-indigo-500 focus:border-indigo-500" v-model="startDate" placeholder="Start Date"> <input type="date" class="rounded-lg border-gray-300 focus:ring-indigo-500 focus:border-indigo-500" v-model="endDate" placeholder="End Date"> </div> </div> </div> <!-- Stats Cards --> <div class="grid grid-cols-1 md:grid-cols-3 gap-6"> <!-- Total Payments --> <div class="bg-white rounded-lg shadow p-6"> <div class="flex items-center justify-between"> <h3 class="text-gray-500 text-sm font-medium">Total Payments</h3> <i class="fas fa-money-bill text-green-500"></i> </div> <p class="mt-2 text-3xl font-semibold">{{ stats.total_payments }}</p> <div class="mt-2 flex items-center text-sm"> <span class="text-gray-500">{{ stats.total_amount | money }}</span> </div> </div> <!-- Success Rate --> <div class="bg-white rounded-lg shadow p-6"> <div class="flex items-center justify-between"> <h3 class="text-gray-500 text-sm font-medium">Success Rate</h3> <i class="fas fa-chart-line text-blue-500"></i> </div> <p class="mt-2 text-3xl font-semibold">{{ stats.success_rate }}%</p> <div class="mt-2 flex items-center text-sm"> <span class="text-gray-500">{{ stats.completed_payments }} successful</span> </div> </div> <!-- Average Amount --> <div class="bg-white rounded-lg shadow p-6"> <div class="flex items-center justify-between"> <h3 class="text-gray-500 text-sm font-medium">Average Amount</h3> <i class="fas fa-calculator text-purple-500"></i> </div> <p class="mt-2 text-3xl font-semibold">{{ stats.average_amount | money }}</p> <div class="mt-2 flex items-center text-sm"> <span class="text-gray-500">per transaction</span> </div> </div> </div> <!-- Payments Table --> <div class="bg-white shadow rounded-lg"> <table class="min-w-full divide-y divide-gray-200"> <thead class="bg-gray-50"> <tr> <th class="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider"> Transaction ID </th> <th class="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider"> Provider </th> <th class="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider"> Amount </th> <th class="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider"> Status </th> <th class="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider"> User </th> <th class="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider"> Date </th> <th class="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider"> Actions </th> </tr> </thead> <tbody class="bg-white divide-y divide-gray-200"> {% for payment in payments %} <tr> <td class="px-6 py-4 whitespace-nowrap text-sm font-medium text-gray-900"> {{ payment.transaction_id }} </td> <td class="px-6 py-4 whitespace-nowrap"> <span class="px-2 inline-flex text-xs leading-5 font-semibold rounded-full {% if payment.provider == 'click' %}bg-blue-100 text-blue-800 {% elif payment.provider == 'payme' %}bg-green-100 text-green-800 {% else %}bg-purple-100 text-purple-800{% endif %}"> {{ payment.provider | upper }} </span> </td> <td class="px-6 py-4 whitespace-nowrap text-sm text-gray-500"> {{ payment.amount | money }} </td> <td class="px-6 py-4 whitespace-nowrap"> <span class="px-2 inline-flex text-xs leading-5 font-semibold rounded-full {% if payment.status == 'COMPLETED' %}bg-green-100 text-green-800 {% elif payment.status == 'PENDING' %}bg-yellow-100 text-yellow-800 {% elif payment.status == 'FAILED' %}bg-red-100 text-red-800 {% else %}bg-gray-100 text-gray-800{% endif %}"> {{ payment.status }} </span> </td> <td class="px-6 py-4 whitespace-nowrap"> <div class="text-sm"> <div class="font-medium text-gray-900"> {{ payment.consultation.user.full_name }} </div> <div class="text-gray-500"> @{{ payment.consultation.user.username }} </div> </div> </td> <td class="px-6 py-4 whitespace-nowrap text-sm text-gray-500"> {{ payment.created_at | datetime }} </td> <td class="px-6 py-4 whitespace-nowrap text-sm font-medium"> <button @click="viewPayment({{ payment.id }})" class="text-indigo-600 hover:text-indigo-900 mr-3"> View </button> {% if payment.status == 'COMPLETED' %} <button @click="refundPayment({{ payment.id }})" class="text-red-600 hover:text-red-900"> Refund </button> {% endif %} </td> </tr> {% endfor %} </tbody> </table> </div> <!-- Pagination --> <div class="bg-white px-4 py-3 flex items-center justify-between border-t border-gray-200 sm:px-6"> <div class="flex-1 flex justify-between items-center"> <div> <p class="text-sm text-gray-700"> Showing <span class="font-medium">{{ pagination.start }}</span> to <span class="font-medium">{{ pagination.end }}</span> of <span class="font-medium">{{ pagination.total }}</span> results </p> </div> <div> <nav class="relative z-0 inline-flex rounded-md shadow-sm -space-x-px"> {% for page in pagination.iter_pages() %} {% if page %} <a href="?page={{ page }}" class="relative inline-flex items-center px-4 py-2 border border-gray-300 bg-white text-sm font-medium {% if page == pagination.page %}text-indigo-600 border-indigo-500{% else %}text-gray-700 hover:bg-gray-50{% endif %}"> {{ page }} </a> {% else %} <span class="relative inline-flex items-center px-4 py-2 border border-gray-300 bg-white text-sm font-medium text-gray-700"> ... </span> {% endif %} {% endfor %} </nav> </div> </div> </div> </div> <!-- Payment Details Modal --> <div v-if="showPaymentDetails" class="fixed z-10 inset-0 overflow-y-auto"> <div class="flex items-end justify-center min-h-screen pt-4 px-4 pb-20 text-center sm:block sm:p-0"> <div class="fixed inset-0 bg-gray-500 bg-opacity-75 transition-opacity"></div> <div class="inline-block align-bottom bg-white rounded-lg text-left overflow-hidden shadow-xl transform transition-all sm:my-8 sm:align-middle sm:max-w-lg sm:w-full"> <div class="bg-white px-4 pt-5 pb-4 sm:p-6 sm:pb-4"> <div class="sm:flex sm:items-start"> <div class="mt-3 text-center sm:mt-0 sm:text-left w-full"> <h3 class="text-lg leading-6 font-medium text-gray-900"> Payment Details </h3> <div class="mt-4 space-y-4"> <div class="grid grid-cols-2 gap-4"> <div> <label class="block text-sm font-medium text-gray-700"> Transaction ID </label> <p class="mt-1 text-sm text-gray-900"> {{ selectedPayment.transaction_id }} </p> </div> <div> <label class="block text-sm font-medium text-gray-700"> Amount </label> <p class="mt-1 text-sm text-gray-900"> {{ selectedPayment.amount | money }} </p> </div> <div> <label class="block text-sm font-medium text-gray-700"> Status </label> <p class="mt-1"> <span class="px-2 inline-flex text-xs leading-5 font-semibold rounded-full {% if selectedPayment.status == 'COMPLETED' %}bg-green-100 text-green-800 {% elif selectedPayment.status == 'PENDING' %}bg-yellow-100 text-yellow-800 {% elif selectedPayment.status == 'FAILED' %}bg-red-100 text-red-800 {% else %}bg-gray-100 text-gray-800{% endif %}"> {{ selectedPayment.status }} </span> </p> </div> <div> <label class="block text-sm font-medium text-gray-700"> Provider </label> <p class="mt-1"> <span class="px-2 inline-flex text-xs leading-5 font-semibold rounded-full {% if selectedPayment.provider == 'click' %}bg-blue-100 text-blue-800 {% elif selectedPayment.provider == 'payme' %}bg-green-100 text-green-800 {% else %}bg-purple-100 text-purple-800{% endif %}"> {{ selectedPayment.provider | upper }} </span> </p> </div> </div> <!-- Payment Timeline --> <div class="mt-6"> <h4 class="text-sm font-medium text-gray-900">Payment Timeline</h4> <div class="mt-2 flow-root"> <ul class="-mb-8"> {% for event in selectedPayment.timeline %} <li> <div class="relative pb-8"> <span class="absolute top-4 left-4 -ml-px h-full w-0.5 bg-gray-200"></span> <div class="relative flex space-x-3"> <div> <span class="h-8 w-8 rounded-full flex items-center justify-center ring-8 ring-white {% if event.type == 'created' %}bg-gray-400 {% elif event.type == 'completed' %}bg-green-500 {% elif event.type == 'failed' %}bg-red-500 {% else %}bg-blue-500{% endif %}"> <i class="fas fa-{{ event.icon }} text-white"></i> </span> </div> <div class="min-w-0 flex-1 pt-1.5 flex justify-between space-x-4"> <div> <p class="text-sm text-gray-500"> {{ event.description }} </p> </div> <div class="text-right text-sm whitespace-nowrap text-gray-500"> {{ event.time | timeago }} </div> </div> </div> </div> </li> {% endfor %} </ul> </div> </div> <!-- File: /telegram_bot/admin/templates/payments.html (продолжение) --> <!-- Payment Metadata --> <div class="mt-6"> <h4 class="text-sm font-medium text-gray-900">Additional Details</h4> <div class="mt-2 border rounded-lg overflow-hidden"> <div class="px-4 py-5 sm:p-6"> <dl class="grid grid-cols-1 gap-x-4 gap-y-6 sm:grid-cols-2"> <div> <dt class="text-sm font-medium text-gray-500"> Order ID </dt> <dd class="mt-1 text-sm text-gray-900"> {{ selectedPayment.metadata.order_id }} </dd> </div> <div> <dt class="text-sm font-medium text-gray-500"> IP Address </dt> <dd class="mt-1 text-sm text-gray-900"> {{ selectedPayment.metadata.ip_address }} </dd> </div> <div> <dt class="text-sm font-medium text-gray-500"> User Agent </dt> <dd class="mt-1 text-sm text-gray-900"> {{ selectedPayment.metadata.user_agent }} </dd> </div> <div> <dt class="text-sm font-medium text-gray-500"> Payment Method </dt> <dd class="mt-1 text-sm text-gray-900"> {{ selectedPayment.metadata.payment_method }} </dd> </div> </dl> </div> </div> </div> <!-- Error Details (if any) --> {% if selectedPayment.error %} <div class="mt-6"> <h4 class="text-sm font-medium text-gray-900">Error Details</h4> <div class="mt-2 p-4 rounded-lg bg-red-50 text-red-700"> <p class="text-sm"> <strong>Error Code:</strong> {{ selectedPayment.error.code }} </p> <p class="text-sm mt-1"> <strong>Message:</strong> {{ selectedPayment.error.message }} </p> </div> </div> {% endif %} </div> </div> </div> </div> <div class="bg-gray-50 px-4 py-3 sm:px-6 sm:flex sm:flex-row-reverse"> {% if selectedPayment.status == 'COMPLETED' %} <button @click="refundPayment(selectedPayment.id)" class="w-full inline-flex justify-center rounded-md border border-transparent shadow-sm px-4 py-2 bg-red-600 text-base font-medium text-white hover:bg-red-700 focus:outline-none focus:ring-2 focus:ring-offset-2 focus:ring-red-500 sm:ml-3 sm:w-auto sm:text-sm"> Refund Payment </button> {% endif %} <button @click="closePaymentDetails" class="mt-3 w-full inline-flex justify-center rounded-md border border-gray-300 shadow-sm px-4 py-2 bg-white text-base font-medium text-gray-700 hover:bg-gray-50 focus:outline-none focus:ring-2 focus:ring-offset-2 focus:ring-indigo-500 sm:mt-0 sm:w-auto sm:text-sm"> Close </button> </div> </div> </div> </div> <!-- Refund Modal --> <div v-if="showRefundModal" class="fixed z-10 inset-0 overflow-y-auto"> <div class="flex items-end justify-center min-h-screen pt-4 px-4 pb-20 text-center sm:block sm:p-0"> <div class="fixed inset-0 bg-gray-500 bg-opacity-75 transition-opacity"></div> <div class="inline-block align-bottom bg-white rounded-lg text-left overflow-hidden shadow-xl transform transition-all sm:my-8 sm:align-middle sm:max-w-lg sm:w-full"> <div class="bg-white px-4 pt-5 pb-4 sm:p-6 sm:pb-4"> <div class="sm:flex sm:items-start"> <div class="mx-auto flex-shrink-0 flex items-center justify-center h-12 w-12 rounded-full bg-red-100 sm:mx-0 sm:h-10 sm:w-10"> <i class="fas fa-exclamation-triangle text-red-600"></i> </div> <div class="mt-3 text-center sm:mt-0 sm:ml-4 sm:text-left"> <h3 class="text-lg leading-6 font-medium text-gray-900"> Refund Payment </h3> <div class="mt-2"> <p class="text-sm text-gray-500"> Are you sure you want to refund this payment? This action cannot be undone. </p> <div class="mt-4"> <label class="block text-sm font-medium text-gray-700"> Refund Amount </label> <div class="mt-1 relative rounded-md shadow-sm"> <div class="absolute inset-y-0 left-0 pl-3 flex items-center pointer-events-none"> <span class="text-gray-500 sm:text-sm">$</span> </div> <input type="number" v-model="refundAmount" :max="selectedPayment.amount" class="focus:ring-indigo-500 focus:border-indigo-500 block w-full pl-7 pr-12 sm:text-sm border-gray-300 rounded-md" placeholder="0.00"> </div> <p class="mt-1 text-sm text-gray-500"> Maximum amount: {{ selectedPayment.amount | money }} </p> </div> <div class="mt-4"> <label class="block text-sm font-medium text-gray-700"> Refund Reason </label> <textarea v-model="refundReason" rows="3" class="shadow-sm focus:ring-indigo-500 focus:border-indigo-500 block w-full sm:text-sm border-gray-300 rounded-md" placeholder="Enter reason for refund"></textarea> </div> </div> </div> </div> </div> <div class="bg-gray-50 px-4 py-3 sm:px-6 sm:flex sm:flex-row-reverse"> <button @click="submitRefund" :disabled="!isValidRefund" class="w-full inline-flex justify-center rounded-md border border-transparent shadow-sm px-4 py-2 bg-red-600 text-base font-medium text-white hover:bg-red-700 focus:outline-none focus:ring-2 focus:ring-offset-2 focus:ring-red-500 sm:ml-3 sm:w-auto sm:text-sm disabled:opacity-50 disabled:cursor-not-allowed"> Refund </button> <button @click="closeRefundModal" class="mt-3 w-full inline-flex justify-center rounded-md border border-gray-300 shadow-sm px-4 py-2 bg-white text-base font-medium text-gray-700 hover:bg-gray-50 focus:outline-none focus:ring-2 focus:ring-offset-2 focus:ring-indigo-500 sm:mt-0 sm:w-auto sm:text-sm"> Cancel </button> </div> </div> </div> </div> {% endblock %} {% block scripts %} <script> new Vue({ el: '#app', data: { status: '', provider: '', startDate: '', endDate: '', payments: {{ payments | tojson }}, stats: {{ stats | tojson }}, pagination: {{ pagination | tojson }}, showPaymentDetails: false, showRefundModal: false, selectedPayment: null, refundAmount: 0, refundReason: '' }, computed: { isValidRefund() { return this.refundAmount > 0 && this.refundAmount <= this.selectedPayment?.amount && this.refundReason.length >= 10; } }, methods: { async fetchPayments() { try { const params = new URLSearchParams({ status: this.status, provider: this.provider, start_date: this.startDate, end_date: this.endDate }); const response = await fetch(`/api/admin/payments?${params}`); const data = await response.json(); this.payments = data.items; this.stats = data.stats; this.pagination = data.pagination; } catch (error) { console.error('Error:', error); } }, async viewPayment(paymentId) { try { const response = await fetch(`/api/admin/payments/${paymentId}`); this.selectedPayment = await response.json(); this.showPaymentDetails = true; } catch (error) { console.error('Error:', error); alert('Failed to load payment details'); } }, closePaymentDetails() { this.showPaymentDetails = false; this.selectedPayment = null; }, refundPayment(paymentId) { this.showRefundModal = true; this.refundAmount = this.selectedPayment.amount; }, closeRefundModal() { this.showRefundModal = false; this.refundAmount = 0; this.refundReason = ''; }, async submitRefund() { try { const response = await fetch(`/api/admin/payments/${this.selectedPayment.id}/refund`, { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ amount: this.refundAmount, reason: this.refundReason }) }); if (response.ok) { this.closeRefundModal(); this.closePaymentDetails(); await this.fetchPayments(); } else { alert('Failed to process refund'); } } catch (error) { console.error('Error:', error); alert('Failed to process refund'); } }, formatMoney(amount) { return new Intl.NumberFormat('uz-UZ', { style: 'currency', currency: 'UZS' }).format(amount); }, formatDate(date) { return new Date(date).toLocaleDateString('uz-UZ', { year: 'numeric', month: 'long', day: 'numeric', hour: '2-digit', minute: '2-digit' }); } }, watch: { status() { this.fetchPayments(); }, provider() { this.fetchPayments(); }, startDate() { this.fetchPayments(); }, endDate() { this.fetchPayments(); } }, created() { this.fetchPayments(); } }); </script> {% endblock %}
```

# telegram_bot\admin\templates\questions.html

```html
<!-- File: /telegram_bot/admin/templates/questions.html --> {% extends "base.html" %} {% block title %}Questions - Law Bot Admin{% endblock %} {% block content %} <div class="space-y-6"> <!-- Header --> <div class="flex items-center justify-between"> <h1 class="text-2xl font-semibold text-gray-900">Questions</h1> <!-- Filters --> <div class="flex space-x-4"> <input type="text" placeholder="Search questions..." class="rounded-lg border-gray-300 focus:ring-indigo-500 focus:border-indigo-500" v-model="search"> <select class="rounded-lg border-gray-300 focus:ring-indigo-500 focus:border-indigo-500" v-model="status"> <option value="">All Status</option> <option value="unanswered">Unanswered</option> <option value="answered">Answered</option> <option value="auto">Auto-answered</option> </select> <select class="rounded-lg border-gray-300 focus:ring-indigo-500 focus:border-indigo-500" v-model="category"> <option value="">All Categories</option> {% for cat in categories %} <option value="{{ cat.value }}">{{ cat.label }}</option> {% endfor %} </select> <select class="rounded-lg border-gray-300 focus:ring-indigo-500 focus:border-indigo-500" v-model="language"> <option value="">All Languages</option> <option value="uz">Uzbek</option> <option value="ru">Russian</option> <!-- File: /telegram_bot/admin/templates/questions.html (продолжение) --> </select> </div> </div> <!-- Questions List --> <div class="space-y-6"> {% for question in questions %} <div class="bg-white shadow rounded-lg p-6"> <div class="flex justify-between items-start"> <!-- Question Info --> <div class="space-y-4 flex-1"> <div class="flex items-center space-x-2"> <span class="text-sm text-gray-500">{{ question.user.full_name }}</span> <span class="text-sm text-gray-500">•</span> <span class="text-sm text-gray-500">{{ question.created_at | timeago }}</span> <span class="px-2 inline-flex text-xs leading-5 font-semibold rounded-full {% if question.language == 'uz' %}bg-green-100 text-green-800 {% else %}bg-blue-100 text-blue-800{% endif %}"> {{ question.language | upper }} </span> {% if question.category %} <span class="px-2 inline-flex text-xs leading-5 font-semibold rounded-full bg-gray-100 text-gray-800"> {{ question.category }} </span> {% endif %} </div> <p class="text-gray-900 text-lg">{{ question.text }}</p> <!-- Answers --> {% if question.answers %} <div class="mt-4 pl-4 border-l-4 border-indigo-500 space-y-4"> {% for answer in question.answers %} <div class="space-y-2"> <div class="flex items-center space-x-2"> <span class="text-sm font-medium text-gray-900">Answer</span> {% if answer.is_auto %} <span class="px-2 inline-flex text-xs leading-5 font-semibold rounded-full bg-yellow-100 text-yellow-800"> Auto </span> {% endif %} <span class="text-sm text-gray-500">{{ answer.created_at | timeago }}</span> </div> <p class="text-gray-700">{{ answer.text }}</p> </div> {% endfor %} </div> {% endif %} </div> <!-- Actions --> <div class="ml-6 flex flex-col space-y-2"> {% if not question.answers %} <button @click="answerQuestion({{ question.id }})" class="inline-flex items-center px-4 py-2 border border-transparent rounded-md shadow-sm text-sm font-medium text-white bg-indigo-600 hover:bg-indigo-700 focus:outline-none focus:ring-2 focus:ring-offset-2 focus:ring-indigo-500"> <i class="fas fa-reply mr-2"></i> Answer </button> {% endif %} <button @click="tryAutoAnswer({{ question.id }})" class="inline-flex items-center px-4 py-2 border border-transparent rounded-md shadow-sm text-sm font-medium text-white bg-green-600 hover:bg-green-700 focus:outline-none focus:ring-2 focus:ring-offset-2 focus:ring-green-500"> <i class="fas fa-robot mr-2"></i> Auto Answer </button> <button @click="deleteQuestion({{ question.id }})" class="inline-flex items-center px-4 py-2 border border-transparent rounded-md shadow-sm text-sm font-medium text-white bg-red-600 hover:bg-red-700 focus:outline-none focus:ring-2 focus:ring-offset-2 focus:ring-red-500"> <i class="fas fa-trash mr-2"></i> Delete </button> </div> </div> </div> {% endfor %} </div> <!-- Pagination --> <div class="bg-white px-4 py-3 flex items-center justify-between border-t border-gray-200 sm:px-6 rounded-lg shadow"> <div class="flex-1 flex justify-between sm:hidden"> {% if pagination.has_prev %} <a href="?page={{ pagination.prev_num }}" class="relative inline-flex items-center px-4 py-2 border border-gray-300 text-sm font-medium rounded-md text-gray-700 bg-white hover:bg-gray-50"> Previous </a> {% endif %} {% if pagination.has_next %} <a href="?page={{ pagination.next_num }}" class="relative inline-flex items-center px-4 py-2 border border-gray-300 text-sm font-medium rounded-md text-gray-700 bg-white hover:bg-gray-50"> Next </a> {% endif %} </div> <div class="hidden sm:flex-1 sm:flex sm:items-center sm:justify-between"> <div> <p class="text-sm text-gray-700"> Showing <span class="font-medium">{{ pagination.start }}</span> to <span class="font-medium">{{ pagination.end }}</span> of <span class="font-medium">{{ pagination.total }}</span> results </p> </div> <div> <nav class="relative z-0 inline-flex rounded-md shadow-sm -space-x-px"> {% for page in pagination.iter_pages() %} {% if page %} <a href="?page={{ page }}" class="relative inline-flex items-center px-4 py-2 border border-gray-300 bg-white text-sm font-medium {% if page == pagination.page %}text-indigo-600 border-indigo-500{% else %}text-gray-700 hover:bg-gray-50{% endif %}"> {{ page }} </a> {% else %} <span class="relative inline-flex items-center px-4 py-2 border border-gray-300 bg-white text-sm font-medium text-gray-700"> ... </span> {% endif %} {% endfor %} </nav> </div> </div> </div> </div> <!-- Answer Modal --> <div v-if="showAnswerModal" class="fixed z-10 inset-0 overflow-y-auto" aria-labelledby="modal-title" role="dialog" aria-modal="true"> <div class="flex items-end justify-center min-h-screen pt-4 px-4 pb-20 text-center sm:block sm:p-0"> <div class="fixed inset-0 bg-gray-500 bg-opacity-75 transition-opacity" aria-hidden="true"></div> <div class="inline-block align-bottom bg-white rounded-lg text-left overflow-hidden shadow-xl transform transition-all sm:my-8 sm:align-middle sm:max-w-lg sm:w-full"> <div class="bg-white px-4 pt-5 pb-4 sm:p-6 sm:pb-4"> <div class="sm:flex sm:items-start"> <div class="mt-3 text-center sm:mt-0 sm:text-left w-full"> <h3 class="text-lg leading-6 font-medium text-gray-900" id="modal-title"> Answer Question </h3> <div class="mt-2"> <p class="text-sm text-gray-500 mb-4">{{ selectedQuestion.text }}</p> <textarea v-model="answerText" rows="4" class="shadow-sm focus:ring-indigo-500 focus:border-indigo-500 block w-full sm:text-sm border-gray-300 rounded-md" placeholder="Type your answer..."></textarea> </div> </div> </div> </div> <div class="bg-gray-50 px-4 py-3 sm:px-6 sm:flex sm:flex-row-reverse"> <button @click="submitAnswer" type="button" class="w-full inline-flex justify-center rounded-md border border-transparent shadow-sm px-4 py-2 bg-indigo-600 text-base font-medium text-white hover:bg-indigo-700 focus:outline-none focus:ring-2 focus:ring-offset-2 focus:ring-indigo-500 sm:ml-3 sm:w-auto sm:text-sm"> Submit </button> <button @click="showAnswerModal = false" type="button" class="mt-3 w-full inline-flex justify-center rounded-md border border-gray-300 shadow-sm px-4 py-2 bg-white text-base font-medium text-gray-700 hover:bg-gray-50 focus:outline-none focus:ring-2 focus:ring-offset-2 focus:ring-indigo-500 sm:mt-0 sm:ml-3 sm:w-auto sm:text-sm"> Cancel </button> </div> </div> </div> </div> {% endblock %} {% block scripts %} <script> new Vue({ el: '#app', data: { search: '', status: '', category: '', language: '', showAnswerModal: false, selectedQuestion: null, answerText: '', questions: {{ questions | tojson }}, pagination: {{ pagination | tojson }} }, methods: { async answerQuestion(questionId) { this.selectedQuestion = this.questions.find(q => q.id === questionId); this.showAnswerModal = true; }, async submitAnswer() { try { const response = await fetch(`/api/admin/questions/${this.selectedQuestion.id}/answer`, { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ text: this.answerText }) }); if (response.ok) { // Reload questions window.location.reload(); } else { alert('Failed to submit answer'); } } catch (error) { console.error('Error:', error); alert('Failed to submit answer'); } }, async tryAutoAnswer(questionId) { try { const response = await fetch(`/api/admin/questions/${questionId}/auto-answer`, { method: 'POST' }); if (response.ok) { window.location.reload(); } else { alert('Failed to generate auto answer'); } } catch (error) { console.error('Error:', error); alert('Failed to generate auto answer'); } }, async deleteQuestion(questionId) { if (confirm('Are you sure you want to delete this question?')) { try { const response = await fetch(`/api/admin/questions/${questionId}`, { method: 'DELETE' }); if (response.ok) { window.location.reload(); } else { alert('Failed to delete question'); } } catch (error) { console.error('Error:', error); alert('Failed to delete question'); } } } }, watch: { search: _.debounce(function(val) { // Implement search this.fetchQuestions(); }, 300), status() { this.fetchQuestions(); }, category() { this.fetchQuestions(); }, language() { this.fetchQuestions(); } }, methods: { async fetchQuestions() { try { const params = new URLSearchParams({ search: this.search, status: this.status, category: this.category, language: this.language }); const response = await fetch(`/api/admin/questions?${params}`); const data = await response.json(); this.questions = data.items; this.pagination = data.pagination; } catch (error) { console.error('Error:', error); } } } }); </script> {% endblock %}
```

# telegram_bot\admin\templates\users.html

```html
<!-- File: /telegram_bot/admin/templates/users.html --> {% extends "base.html" %} {% block title %}Users - Law Bot Admin{% endblock %} {% block content %} <div class="space-y-6"> <!-- Header --> <div class="flex items-center justify-between"> <h1 class="text-2xl font-semibold text-gray-900">Users</h1> <!-- Search & Filters --> <div class="flex space-x-4"> <input type="text" placeholder="Search users..." class="rounded-lg border-gray-300 focus:ring-indigo-500 focus:border-indigo-500" v-model="search"> <select class="rounded-lg border-gray-300 focus:ring-indigo-500 focus:border-indigo-500" v-model="language"> <option value="">All Languages</option> <option value="uz">Uzbek</option> <option value="ru">Russian</option> </select> <select class="rounded-lg border-gray-300 focus:ring-indigo-500 focus:border-indigo-500" v-model="status"> <option value="">All Status</option> <option value="active">Active</option> <option value="blocked">Blocked</option> </select> </div> </div> <!-- Users Table --> <div class="bg-white shadow rounded-lg"> <table class="min-w-full divide-y divide-gray-200"> <thead class="bg-gray-50"> <tr> <th class="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider"> User </th> <th class="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider"> Language </th> <th class="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider"> Status </th> <th class="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider"> Joined </th> <th class="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider"> Actions </th> </tr> </thead> <tbody class="bg-white divide-y divide-gray-200"> {% for user in users %} <tr> <td class="px-6 py-4 whitespace-nowrap"> <div class="flex items-center"> <div> <div class="text-sm font-medium text-gray-900"> {{ user.full_name }} </div> <div class="text-sm text-gray-500"> @{{ user.username }} </div> </div> </div> </td> <td class="px-6 py-4 whitespace-nowrap"> <span class="px-2 inline-flex text-xs leading-5 font-semibold rounded-full {% if user.language == 'uz' %}bg-green-100 text-green-800 {% else %}bg-blue-100 text-blue-800{% endif %}"> {{ user.language | upper }} </span> </td> <td class="px-6 py-4 whitespace-nowrap"> <span class="px-2 inline-flex text-xs leading-5 font-semibold rounded-full {% if user.is_blocked %}bg-red-100 text-red-800 {% else %}bg-green-100 text-green-800{% endif %}"> {{ 'Blocked' if user.is_blocked else 'Active' }} </span> </td> <td class="px-6 py-4 whitespace-nowrap text-sm text-gray-500"> {{ user.created_at | date }} </td> <td class="px-6 py-4 whitespace-nowrap text-sm font-medium"> <button class="text-indigo-600 hover:text-indigo-900" @click="viewUser({{ user.id }})"> View </button> <button class="ml-3 text-red-600 hover:text-red-900" @click="toggleBlock({{ user.id }})"> {{ 'Unblock' if user.is_blocked else 'Block' }} </button> </td> </tr> {% endfor %} </tbody> </table> </div> <!-- Pagination --> <div class="bg-white px-4 py-3 flex items-center justify-between border-t border-gray-200 sm:px-6"> <div class="flex-1 flex justify-between sm:hidden"> <button class="relative inline-flex items-center px-4 py-2 border border-gray-300 text-sm font-medium rounded-md text-gray-700 bg-white hover:text-gray-500"> Previous </button> <button class="ml-3 relative inline-flex items-center px-4 py-2 border border-gray-300 text-sm font-medium rounded-md text-gray-700 bg-white hover:text-gray-500"> Next </button> </div> <div class="hidden sm:flex-1 sm:flex sm:items-center sm:justify-between"> <div> <p class="text-sm text-gray-700"> Showing <span class="font-medium">{{ pagination.start }}</span> to <span class="font-medium">{{ pagination.end }}</span> of <span class="font-medium">{{ pagination.total }}</span> results </p> </div> <div> <nav class="relative z-0 inline-flex rounded-md shadow-sm -space-x-px"> {% for page in pagination.pages %} <a href="?page={{ page }}" class="relative inline-flex items-center px-4 py-2 border border-gray-300 bg-white text-sm font-medium text-gray-700 hover:bg-gray-50 {% if page == pagination.current %}text-indigo-600 border-indigo-500{% endif %}"> {{ page }} </a> {% endfor %} </nav> </div> </div> </div> </div> {% endblock %} {% block scripts %} <script> new Vue({ el: '#app', data: { search: '', language: '', status: '', users: {{ users | tojson }}, pagination: {{ pagination | tojson }} }, methods: { async viewUser(userId) { // Implement user view }, async toggleBlock(userId) { // Implement user blocking } }, watch: { search: _.debounce(function(val) { // Implement search }, 300) } }); </script> {% endblock %}
```

# telegram_bot\admin\templates\webapp.html

```html
<!DOCTYPE html> <html lang="en"> <head> <meta charset="UTF-8"> <meta name="viewport" content="width=device-width, initial-scale=1.0"> <title>Law Bot Admin</title> <script src="https://cdn.tailwindcss.com"></script> <script src="https://unpkg.com/vue@3/dist/vue.global.js"></script> <script src="https://cdnjs.cloudflare.com/ajax/libs/moment.js/2.29.4/moment.min.js"></script> <script src="https://cdnjs.cloudflare.com/ajax/libs/Chart.js/3.7.0/chart.min.js"></script> </head> <body class="bg-gray-100 dark:bg-gray-900"> <div id="app" class="h-screen flex overflow-hidden" v-cloak> <!-- Sidebar --> <aside class="w-64 bg-white dark:bg-gray-800 border-r border-gray-200 dark:border-gray-700"> <div class="h-full px-3 py-4 overflow-y-auto"> <div class="flex items-center mb-8"> <img src="/static/logo.svg" class="h-8 w-8 mr-3" alt="Logo"> <span class="text-xl font-semibold dark:text-white">Law Bot Admin</span> </div> <nav class="space-y-2"> <a v-for="item in menuItems" :key="item.id" @click="currentPage = item.id" :class="[ 'flex items-center p-3 rounded-lg cursor-pointer', currentPage === item.id ? 'bg-blue-100 dark:bg-blue-900 text-blue-600 dark:text-blue-300' : 'hover:bg-gray-100 dark:hover:bg-gray-700 text-gray-700 dark:text-gray-300' ]"> <i :class="item.icon" class="w-5 h-5 mr-2"></i> <span>{{ item.name }}</span> </a> </nav> </div> </aside> <!-- Main Content --> <div class="flex-1 flex flex-col overflow-hidden"> <!-- Top Header --> <header class="bg-white dark:bg-gray-800 shadow"> <div class="mx-auto px-4 sm:px-6 lg:px-8"> <div class="flex items-center justify-between h-16"> <h1 class="text-2xl font-semibold text-gray-900 dark:text-white"> {{ currentPageTitle }} </h1> <div class="flex items-center space-x-4"> <!-- Search --> <div class="relative"> <input type="text" v-model="searchQuery" @input="handleSearch" placeholder="Search..." class="w-64 px-4 py-2 rounded-lg border border-gray-300 dark:border-gray-600 bg-white dark:bg-gray-700 text-gray-900 dark:text-white"> </div> <!-- Theme Toggle --> <button @click="toggleTheme" class="p-2 rounded-lg hover:bg-gray-100 dark:hover:bg-gray-700"> <i :class="isDark ? 'fas fa-sun' : 'fas fa-moon'" class="text-gray-500 dark:text-gray-400"></i> </button> <!-- User Menu --> <div class="relative"> <button @click="showUserMenu = !showUserMenu" class="flex items-center space-x-2 p-2 rounded-lg hover:bg-gray-100 dark:hover:bg-gray-700"> <img :src="user.avatar" class="h-8 w-8 rounded-full"> <span class="text-gray-700 dark:text-gray-300">{{ user.name }}</span> </button> <!-- Dropdown Menu --> <div v-if="showUserMenu" class="absolute right-0 mt-2 w-48 bg-white dark:bg-gray-800 rounded-lg shadow-lg border border-gray-200 dark:border-gray-700"> <a href="#" class="block px-4 py-2 text-gray-700 dark:text-gray-300 hover:bg-gray-100 dark:hover:bg-gray-700"> Profile </a> <a href="#" class="block px-4 py-2 text-gray-700 dark:text-gray-300 hover:bg-gray-100 dark:hover:bg-gray-700"> Settings </a> <a href="#" class="block px-4 py-2 text-red-600 hover:bg-gray-100 dark:hover:bg-gray-700"> Logout </a> </div> </div> </div> </div> </div> </header> <!-- Main Content Area --> <main class="flex-1 overflow-y-auto bg-gray-50 dark:bg-gray-900 p-6"> <!-- Dashboard --> <div v-if="currentPage === 'dashboard'" class="space-y-6"> <!-- Stats Cards --> <div class="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-6"> <div v-for="stat in stats" :key="stat.title" class="bg-white dark:bg-gray-800 rounded-lg p-6 shadow-sm"> <div class="flex items-center justify-between"> <h3 class="text-sm font-medium text-gray-500 dark:text-gray-400"> {{ stat.title }} </h3> <i :class="stat.icon" class="text-gray-400 dark:text-gray-500"></i> </div> <p class="mt-2 text-3xl font-semibold text-gray-900 dark:text-white"> {{ stat.value }} </p> <div class="mt-2 flex items-center text-sm"> <span :class="stat.trend >= 0 ? 'text-green-500' : 'text-red-500'"> {{ stat.trend >= 0 ? '↑' : '↓' }} {{ Math.abs(stat.trend) }}% </span> <span class="ml-2 text-gray-500 dark:text-gray-400">vs last week</span> </div> </div> </div> <!-- Charts --> <div class="grid grid-cols-1 lg:grid-cols-2 gap-6"> <div class="bg-white dark:bg-gray-800 rounded-lg p-6 shadow-sm"> <h3 class="text-lg font-medium text-gray-900 dark:text-white mb-4"> User Growth </h3> <canvas ref="userChart" height="300"></canvas> </div> <div class="bg-white dark:bg-gray-800 rounded-lg p-6 shadow-sm"> <h3 class="text-lg font-medium text-gray-900 dark:text-white mb-4"> Questions Overview </h3> <canvas ref="questionChart" height="300"></canvas> </div> </div> </div> <!-- Questions --> <div v-if="currentPage === 'questions'" class="space-y-6"> <div class="bg-white dark:bg-gray-800 rounded-lg shadow-sm"> <div class="p-6 border-b border-gray-200 dark:border-gray-700"> <div class="flex items-center justify-between"> <h2 class="text-lg font-medium text-gray-900 dark:text-white"> Questions </h2> <div class="flex space-x-2"> <button v-for="filter in questionFilters" :key="filter.value" @click="currentQuestionFilter = filter.value" :class="[ 'px-3 py-2 rounded-lg text-sm font-medium', currentQuestionFilter === filter.value ? 'bg-blue-100 dark:bg-blue-900 text-blue-600 dark:text-blue-300' : 'text-gray-500 dark:text-gray-400 hover:bg-gray-100 dark:hover:bg-gray-700' ]"> {{ filter.label }} </button> </div> </div> </div> <div class="divide-y divide-gray-200 dark:divide-gray-700"> <div v-for="question in filteredQuestions" :key="question.id" class="p-6"> <div class="flex justify-between items-start"> <div> <div class="flex items-center space-x-2 text-sm text-gray-500 dark:text-gray-400"> <span>{{ question.user.full_name }}</span> <span>{{ formatDate(question.created_at) }}</span> <span :class="question.language === 'uz' ? 'text-green-500' : 'text-blue-500'"> {{ question.language.toUpperCase() }} </span> </div> <p class="mt-2 text-gray-900 dark:text-white"> {{ question.question_text }} </p> <div v-if="question.answers.length" class="mt-4 pl-4 border-l-2 border-gray-200 dark:border-gray-700"> <div v-for="answer in question.answers" :key="answer.id" class="mb-2"> <div class="flex items-center space-x-2"> <span class="text-sm font-medium text-gray-900 dark:text-white"> Answer </span> <span v-if="answer.is_auto" class="px-2 py-0.5 text-xs bg-yellow-100 dark:bg-yellow-900 text-yellow-800 dark:text-yellow-300 rounded"> Auto </span> </div> <p class="mt-1 text-gray-600 dark:text-gray-300"> {{ answer.answer_text }} </p> </div> </div> </div> <div class="flex space-x-2"> <button v-if="!question.answers.length" @click="openAnswerModal(question)" class="px-3 py-1 text-sm font-medium text-white bg-blue-600 hover:bg-blue-700 rounded"> Answer </button> <button @click="deleteQuestion(question)" class="px-3 py-1 text-sm font-medium text-white bg-red-600 hover:bg-red-700 rounded"> Delete </button> </div> </div> </div> </div> </div> </div> <!-- Consultations --> <div v-if="currentPage === 'consultations'" class="space-y-6"> <div class="bg-white dark:bg-gray-800 rounded-lg shadow-sm"> <div class="p-6 border-b border-gray-200 dark:border-gray-700"> <div class="flex items-center justify-between"> <h2 class="text-lg font-medium text-gray-900 dark:text-white"> Consultations </h2> <div class="flex space-x-2"> <button v-for="status in consultationStatuses" :key="status.value" @click="currentConsultationStatus = status.value" :class="[ 'px-3 py-2 rounded-lg text-sm font-medium', currentConsultationStatus === status.value ? 'bg-blue-100 dark:bg-blue-900 text-blue-600 dark:text-blue-300' : 'text-gray-500 dark:text-gray-400 hover:bg-gray-100 dark:hover:bg-gray-700' ]"> {{ status.label }} </button> </div> </div> </div> <div class="overflow-x-auto"> <table class="min-w-full divide-y divide-gray-200 dark:divide-gray-700"> <thead class="bg-gray-50 dark:bg-gray-700"> <tr> <th scope="col" class="px-6 py-3 text-left text-xs font-medium text-gray-500 dark:text-gray-300 uppercase tracking-wider"> User </th> <th scope="col" class="px-6 py-3 text-left text-xs font-medium text-gray-500 dark:text-gray-300 uppercase tracking-wider"> Status </th> <th scope="col" class="px-6 py-3 text-left text-xs font-medium text-gray-500 dark:text-gray-300 uppercase tracking-wider"> Amount </th> <th scope="col" class="px-6 py-3 text-left text-xs font-medium text-gray-500 dark:text-gray-300 uppercase tracking-wider"> Scheduled </th> <th scope="col" class="px-6 py-3 text-left text-xs font-medium text-gray-500 dark:text-gray-300 uppercase tracking-wider"> Actions </th> </tr> </thead> <tbody class="bg-white dark:bg-gray-800 divide-y divide-gray-200 dark:divide-gray-700"> <tr v-for="consultation in filteredConsultations" :key="consultation.id"> <td class="px-6 py-4 whitespace-nowrap"> <div class="flex items-center"> <div> <div class="text-sm font-medium text-gray-900 dark:text-white"> {{ consultation.user.full_name }} </div> <div class="text-sm text-gray-500 dark:text-gray-400"> {{ consultation.phone_number }} </div> </div> </div> </td> <td class="px-6 py-4 whitespace-nowrap"> <span :class="getStatusClass(consultation.status)"> {{ consultation.status }} </span> </td> <td class="px-6 py-4 whitespace-nowrap text-sm text-gray-500 dark:text-gray-400"> {{ formatMoney(consultation.amount) }} </td> <td class="px-6 py-4 whitespace-nowrap text-sm text-gray-500 dark:text-gray-400"> {{ consultation.scheduled_time ? formatDate(consultation.scheduled_time) : '-' }} </td> <td class="px-6 py-4 whitespace-nowrap text-right text-sm font-medium"> <button @click="viewConsultation(consultation)" class="text-blue-600 dark:text-blue-400 hover:text-blue-900 dark:hover:text-blue-300"> View </button> </td> </tr> </tbody> </table> </div> </div> </div> </main> </div> </div> <!-- Modals --> <div v-if="showAnswerModal" class="fixed inset-0 bg-gray-500 bg-opacity-75 flex items-center justify-center"> <div class="bg-white dark:bg-gray-800 rounded-lg p-6 max-w-lg w-full"> <h3 class="text-lg font-medium text-gray-900 dark:text-white mb-4"> Answer Question </h3> <div class="mb-4"> <p class="text-gray-600 dark:text-gray-300">{{ selectedQuestion?.question_text }}</p> </div> <div> <label class="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-2"> Your Answer </label> <textarea v-model="answerText" rows="4" class="w-full px-3 py-2 border border-gray-300 dark:border-gray-600 rounded-lg focus:outline-none focus:ring-2 focus:ring-blue-500 bg-white dark:bg-gray-700 text-gray-900 dark:text-white" placeholder="Type your answer..."></textarea> </div> <div class="mt-6 flex justify-end space-x-3"> <button @click="closeAnswerModal" class="px-4 py-2 text-sm font-medium text-gray-700 dark:text-gray-300 hover:bg-gray-100 dark:hover:bg-gray-700 rounded-lg"> Cancel </button> <button @click="submitAnswer" :disabled="!answerText" class="px-4 py-2 text-sm font-medium text-white bg-blue-600 hover:bg-blue-700 rounded-lg disabled:opacity-50"> Submit </button> </div> </div> </div> <script> const { createApp } = Vue createApp({ data() { return { currentPage: 'dashboard', searchQuery: '', isDark: false, showUserMenu: false, showAnswerModal: false, answerText: '', selectedQuestion: null, user: { name: 'Admin User', avatar: 'https://ui-avatars.com/api/?name=Admin+User' }, menuItems: [ { id: 'dashboard', name: 'Dashboard', icon: 'fas fa-chart-line' }, { id: 'questions', name: 'Questions', icon: 'fas fa-question-circle' }, { id: 'consultations', name: 'Consultations', icon: 'fas fa-calendar' }, { id: 'users', name: 'Users', icon: 'fas fa-users' }, { id: 'settings', name: 'Settings', icon: 'fas fa-cog' } ], stats: [ { title: 'Total Users', value: '1,234', trend: 12, icon: 'fas fa-users' }, { title: 'Active Questions', value: '56', trend: -5, icon: 'fas fa-question-circle' }, { title: 'Consultations', value: '89', trend: 8, icon: 'fas fa-calendar' }, { title: 'Monthly Revenue', value: '$12,345', trend: 15, icon: 'fas fa-dollar-sign' } ], questions: [], consultations: [], currentQuestionFilter: 'all', currentConsultationStatus: 'all', questionFilters: [ { value: 'all', label: 'All' }, { value: 'unanswered', label: 'Unanswered' }, { value: 'answered', label: 'Answered' }, { value: 'auto', label: 'Auto-answered' } ], consultationStatuses: [ { value: 'all', label: 'All' }, { value: 'pending', label: 'Pending' }, { value: 'scheduled', label: 'Scheduled' }, { value: 'completed', label: 'Completed' }, { value: 'cancelled', label: 'Cancelled' } ] } }, computed: { currentPageTitle() { const page = this.menuItems.find(item => item.id === this.currentPage) return page ? page.name : '' }, filteredQuestions() { if (this.currentQuestionFilter === 'all') { return this.questions } return this.questions.filter(q => { switch(this.currentQuestionFilter) { case 'unanswered': return !q.answers.length case 'answered': return q.answers.length && !q.answers.some(a => a.is_auto) case 'auto': return q.answers.some(a => a.is_auto) } }) }, filteredConsultations() { if (this.currentConsultationStatus === 'all') { return this.consultations } return this.consultations.filter(c => c.status.toLowerCase() === this.currentConsultationStatus ) } }, methods: { async fetchData() { try { const [questions, consultations] = await Promise.all([ fetch('/api/admin/questions').then(r => r.json()), fetch('/api/admin/consultations').then(r => r.json()) ]) this.questions = questions.items this.consultations = consultations.items } catch (error) { console.error('Error fetching data:', error) } }, formatDate(date) { return moment(date).format('DD.MM.YYYY HH:mm') }, formatMoney(amount) { return new Intl.NumberFormat('uz-UZ', { style: 'currency', currency: 'UZS' }).format(amount) }, handleSearch() { clearTimeout(this.searchTimeout) this.searchTimeout = setTimeout(async () => { try { const response = await fetch( `/api/admin/search?q=${this.searchQuery}&type=${this.currentPage}` ) const data = await response.json() if (this.currentPage === 'questions') { this.questions = data.items } else if (this.currentPage === 'consultations') { this.consultations = data.items } } catch (error) { console.error('Search error:', error) } }, 300) }, toggleTheme() { this.isDark = !this.isDark document.documentElement.classList.toggle('dark', this.isDark) localStorage.setItem('theme', this.isDark ? 'dark' : 'light') }, openAnswerModal(question) { this.selectedQuestion = question this.answerText = '' this.showAnswerModal = true }, closeAnswerModal() { this.showAnswerModal = false this.selectedQuestion = null this.answerText = '' }, async submitAnswer() { try { const response = await fetch( `/api/admin/questions/${this.selectedQuestion.id}/answer`, { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ answer_text: this.answerText }) } ) if (response.ok) { await this.fetchData() this.closeAnswerModal() } } catch (error) { console.error('Error submitting answer:', error) } }, getStatusClass(status) { const classes = { 'PENDING': 'bg-yellow-100 text-yellow-800', 'PAID': 'bg-green-100 text-green-800', 'SCHEDULED': 'bg-blue-100 text-blue-800', 'COMPLETED': 'bg-gray-100 text-gray-800', 'CANCELLED': 'bg-red-100 text-red-800' } return `px-2 py-1 text-xs font-medium rounded-full ${classes[status] || ''}` }, initCharts() { // User Growth Chart const userCtx = this.$refs.userChart.getContext('2d') new Chart(userCtx, { type: 'line', data: { labels: ['Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun'], datasets: [{ label: 'New Users', data: [65, 78, 90, 85, 99, 112], borderColor: '#3B82F6', tension: 0.3 }] }, options: { responsive: true, maintainAspectRatio: false } }) // Questions Chart const questionCtx = this.$refs.questionChart.getContext('2d') new Chart(questionCtx, { type: 'bar', data: { labels: ['Answered', 'Unanswered', 'Auto'], datasets: [{ data: [45, 25, 30], backgroundColor: [ '#10B981', '#EF4444', '#F59E0B' ] }] }, options: { responsive: true, maintainAspectRatio: false, plugins: { legend: { display: false } } } }) } }, mounted() { this.isDark = localStorage.getItem('theme') === 'dark' document.documentElement.classList.toggle('dark', this.isDark) this.fetchData() this.initCharts() // Set up auto-refresh setInterval(this.fetchData, 30000) // Refresh every 30 seconds } }).mount('#app') </script> <!-- Icons --> <link rel="stylesheet" href="https://cdnjs.cloudflare.com/ajax/libs/font-awesome/6.0.0/css/all.min.css"> </body> </html>
```

# telegram_bot\admin\views.py

```py
# File: /telegram_bot/admin/views.py

from fastapi import APIRouter, Depends, HTTPException, Query
from typing import List, Optional
from datetime import datetime, timedelta
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func,or_, and_
from sqlalchemy.orm import joinedload
from telegram_bot.core.database import get_session
from telegram_bot.admin.auth import get_current_admin
from telegram_bot.models import User, Question, Consultation, Payment,Answer
from telegram_bot.services.analytics import AnalyticsService
from telegram_bot.services.payments import PaymentManager
from telegram_bot.services.questions import QuestionService
from telegram_bot.services.consultations import ConsultationService
import logging
router = APIRouter(prefix="/admin", tags=["admin"])
logger = logging.getLogger(__name__)

@router.get("/dashboard")
async def get_dashboard(
    session: AsyncSession = Depends(get_session),
    admin: User = Depends(get_current_admin)
):
    """Get admin dashboard data"""
    analytics = AnalyticsService(session)
    
    # Get period stats
    today = datetime.now()
    week_ago = today - timedelta(days=7)
    month_ago = today - timedelta(days=30)
    
    # Get user stats
    users_stats = await analytics.get_users_stats(
        start_date=month_ago
    )
    
    # Get questions stats
    question_service = QuestionService(session)
    questions_stats = await question_service.get_question_stats(
        start_date=month_ago
    )
    
    # Get consultation stats
    consultation_service = ConsultationService(session)
    consultations_stats = await consultation_service.get_consultation_stats(
        start_date=month_ago
    )
    
    # Get payment stats
    payment_manager = PaymentManager(session)
    payments_stats = await payment_manager.get_payment_stats(
        start_date=month_ago
    )
    
    return {
        "users": {
            "total": users_stats["total_users"],
            "active": users_stats["active_users"],
            "new_today": users_stats["new_users_today"],
            "new_week": users_stats["new_users_week"],
            "by_language": users_stats["language_distribution"]
        },
        "questions": {
            "total": questions_stats["total_questions"],
            "unanswered": questions_stats["unanswered_questions"],
            "auto_answered": questions_stats["auto_answered_questions"],
            "categories": questions_stats["category_distribution"]
        },
        "consultations": {
            "total": consultations_stats["total_consultations"],
            "pending": consultations_stats["pending_consultations"],
            "completed": consultations_stats["completed_consultations"],
            "revenue": float(consultations_stats["total_revenue"])
        },
        "payments": {
            "total": payments_stats["total_payments"],
            "amount": float(payments_stats["total_amount"]),
            "by_provider": payments_stats["by_provider"],
            "by_status": payments_stats["by_status"]
        }
    }

@router.get("/users")
async def get_users(
    skip: int = 0,
    limit: int = 50,
    search: Optional[str] = None,
    language: Optional[str] = None,
    is_active: Optional[bool] = None,
    sort: Optional[str] = None,
    session: AsyncSession = Depends(get_session),
    admin: User = Depends(get_current_admin)
):
    """Get users list"""
    query = select(User)
    
    # Apply filters
    if search:
        query = query.filter(
            or_(
                User.username.ilike(f"%{search}%"),
                User.full_name.ilike(f"%{search}%")
            )
        )
    if language:
        query = query.filter(User.language == language)
    if is_active is not None:
        query = query.filter(User.is_active == is_active)
        
    # Apply sorting
    if sort:
        if sort.startswith("-"):
            query = query.order_by(desc(getattr(User, sort[1:])))
        else:
            query = query.order_by(getattr(User, sort))
    
    # Get total count
    total = await session.scalar(
        select(func.count()).select_from(query.subquery())
    )
    
    # Apply pagination
    query = query.offset(skip).limit(limit)
    
    # Execute query
    result = await session.execute(query)
    users = result.scalars().all()
    
    return {
        "total": total,
        "items": [
            {
                "id": user.id,
                "telegram_id": user.telegram_id,
                "username": user.username,
                "full_name": user.full_name,
                "language": user.language,
                "is_active": user.is_active,
                "created_at": user.created_at.isoformat()
            }
            for user in users
        ]
    }

@router.get("/questions")
async def get_questions(
    skip: int = 0,
    limit: int = 50,
    status: Optional[str] = None,
    category: Optional[str] = None,
    language: Optional[str] = None,
    session: AsyncSession = Depends(get_session),
    admin: User = Depends(get_current_admin)
):
    """Get questions list"""
    query = select(Question).options(
        joinedload(Question.user),
        joinedload(Question.answers)
    )
    
    # Apply filters
    if status == "unanswered":
        query = query.filter(~Question.answers.any())
    elif status == "answered":
        query = query.filter(Question.answers.any())
    elif status == "auto":
        query = query.filter(
            Question.answers.any(Answer.is_auto == True)
        )
    
    if category:
        query = query.filter(Question.category == category)
    if language:
        query = query.filter(Question.language == language)
        
    # Get total count
    total = await session.scalar(
        select(func.count()).select_from(query.subquery())
    )
    
    # Apply pagination
    query = query.offset(skip).limit(limit)
    
    # Execute query
    result = await session.execute(query)
    questions = result.unique().scalars().all()
    
    return {
        "total": total,
        "items": [
            {
                "id": q.id,
                "text": q.question_text,
                "language": q.language,
                "category": q.category,
                "user": {
                    "id": q.user.id,
                    "username": q.user.username,
                    "full_name": q.user.full_name
                },
                "answers": [
                    {
                        "id": a.id,
                        "text": a.answer_text,
                        "is_auto": a.is_auto,
                        "created_at": a.created_at.isoformat()
                    }
                    for a in q.answers
                ],
                "created_at": q.created_at.isoformat()
            }
            for q in questions
        ]
    }

@router.get("/consultations") 
async def get_consultations(
    skip: int = 0,
    limit: int = 50,
    status: Optional[str] = None,
    session: AsyncSession = Depends(get_session),
    admin: User = Depends(get_current_admin)
):
    """Get consultations list"""
    query = select(Consultation).options(
        joinedload(Consultation.user),
        joinedload(Consultation.payments)
    )
    
    # File: /telegram_bot/admin/views.py (продолжение)

    # Apply filters
    if status:
        query = query.filter(Consultation.status == status)
        
    # Get total count
    total = await session.scalar(
        select(func.count()).select_from(query.subquery())
    )
    
    # Apply pagination
    query = query.offset(skip).limit(limit)
    
    # Execute query
    result = await session.execute(query)
    consultations = result.unique().scalars().all()
    
    return {
        "total": total,
        "items": [
            {
                "id": c.id,
                "status": c.status.value,
                "amount": float(c.amount),
                "scheduled_time": c.scheduled_time.isoformat() if c.scheduled_time else None,
                "user": {
                    "id": c.user.id,
                    "username": c.user.username,
                    "full_name": c.user.full_name
                },
                "payments": [
                    {
                        "id": p.id,
                        "provider": p.provider,
                        "status": p.status.value,
                        "amount": float(p.amount),
                        "created_at": p.created_at.isoformat()
                    }
                    for p in c.payments
                ],
                "created_at": c.created_at.isoformat()
            }
            for c in consultations
        ]
    }

@router.get("/payments")
async def get_payments(
    skip: int = 0,
    limit: int = 50,
    provider: Optional[str] = None,
    status: Optional[str] = None,
    session: AsyncSession = Depends(get_session),
    admin: User = Depends(get_current_admin)
):
    """Get payments list"""
    query = select(Payment).options(
        joinedload(Payment.consultation)
    )
    
    # Apply filters
    if provider:
        query = query.filter(Payment.provider == provider)
    if status:
        query = query.filter(Payment.status == status)
        
    # Get total count
    total = await session.scalar(
        select(func.count()).select_from(query.subquery())
    )
    
    # Apply pagination
    query = query.offset(skip).limit(limit)
    
    # Execute query
    result = await session.execute(query)
    payments = result.unique().scalars().all()
    
    return {
        "total": total,
        "items": [
            {
                "id": p.id,
                "provider": p.provider,
                "status": p.status.value,
                "amount": float(p.amount),
                "consultation": {
                    "id": p.consultation.id,
                    "status": p.consultation.status.value,
                    "user": {
                        "id": p.consultation.user.id,
                        "username": p.consultation.user.username,
                        "full_name": p.consultation.user.full_name
                    }
                },
                "transaction_id": p.transaction_id,
                "created_at": p.created_at.isoformat()
            }
            for p in payments
        ]
    }

@router.post("/broadcast")
async def send_broadcast(
    message: str,
    users: Optional[List[int]] = None,
    language: Optional[str] = None,
    session: AsyncSession = Depends(get_session),
    admin: User = Depends(get_current_admin)
):
    """Send broadcast message to users"""
    from telegram_bot.bot import bot
    
    # Build user query
    query = select(User.telegram_id)
    
    if users:
        query = query.filter(User.id.in_(users))
    if language:
        query = query.filter(User.language == language)
        
    # Get user IDs
    result = await session.execute(query)
    user_ids = result.scalars().all()
    
    if not user_ids:
        raise HTTPException(
            status_code=400,
            detail="No users match the criteria"
        )
    
    # Send messages
    success = 0
    failed = 0
    
    for user_id in user_ids:
        try:
            await bot.send_message(user_id, message)
            success += 1
        except Exception as e:
            logger.error(f"Error sending broadcast to {user_id}: {e}")
            failed += 1
    
    return {
        "success": True,
        "sent": success,
        "failed": failed,
        "total": len(user_ids)
    }

@router.get("/analytics")
async def get_analytics(
    start_date: datetime,
    end_date: datetime,
    session: AsyncSession = Depends(get_session),
    admin: User = Depends(get_current_admin)
):
    """Get analytics data"""
    analytics = AnalyticsService(session)
    
    return {
        "users": await analytics.get_users_stats(start_date, end_date),
        "questions": await analytics.get_question_stats(start_date, end_date),
        "consultations": await analytics.get_consultation_stats(start_date, end_date),
        "payments": await analytics.get_payment_stats(start_date, end_date),
        "performance": await analytics.get_performance_metrics()
    }

@router.post("/notifications")
async def send_notification(
    user_id: int,
    title: str,
    message: str,
    notification_type: str,
    session: AsyncSession = Depends(get_session),
    admin: User = Depends(get_current_admin)
):
    """Send notification to user"""
    from telegram_bot.services.notifications import NotificationService
    
    notification_service = NotificationService(session)
    notification = await notification_service.send_notification(
        user_id=user_id,
        title=title,
        message=message,
        notification_type=notification_type
    )
    
    if not notification:
        raise HTTPException(
            status_code=400,
            detail="Failed to send notification"
        )
        
    return {
        "success": True,
        "notification_id": notification.id
    }

@router.get("/system/health")
async def get_system_health(
    session: AsyncSession = Depends(get_session),
    admin: User = Depends(get_current_admin)
):
    """Get system health status"""
    # Check database
    try:
        await session.execute(select(1))
        db_status = "healthy"
    except:
        db_status = "unhealthy"
    
    # Check cache
    try:
        from telegram_bot.core.cache import cache_service as cache

        await cache.ping()
        cache_status = "healthy"
    except:
        cache_status = "unhealthy"
    
    # Check bot
    from telegram_bot.bot import bot
    try:
        me = await bot.get_me()
        bot_status = "healthy"
    except:
        bot_status = "unhealthy"
    
    # Get system metrics
    import psutil
    
    return {
        "status": all([
            s == "healthy" 
            for s in [db_status, cache_status, bot_status]
        ]),
        "components": {
            "database": db_status,
            "cache": cache_status,
            "bot": bot_status
        },
        "metrics": {
            "cpu": psutil.cpu_percent(),
            "memory": psutil.virtual_memory().percent,
            "disk": psutil.disk_usage('/').percent
        }
    }
```

# telegram_bot\app.py

```py
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
```

# telegram_bot\bot\__init__.py

```py
from aiogram import Bot, Dispatcher
from aiogram.fsm.storage.redis import RedisStorage
from aiogram.fsm.storage.memory import MemoryStorage
import logging

from telegram_bot.core.config import settings
from telegram_bot.services.cache_service import cache_service
from telegram_bot.bot.handlers import (
    register_user_handlers,
    register_admin_handlers,
    register_error_handlers,
    register_consultation_handlers,
    register_question_handlers,
    register_payment_handlers
)
from telegram_bot.bot.middlewares import (
    DatabaseMiddleware,
    RateLimitMiddleware,
    LoggingMiddleware,
    ErrorHandlerMiddleware,
    AuthenticationMiddleware,
    LanguageMiddleware,
    UserActivityMiddleware
)

logger = logging.getLogger(__name__)

# Initialize bot
bot = Bot(token=settings.BOT_TOKEN.get_secret_value(), parse_mode="HTML")

# Initialize FSM storage
if settings.REDIS_URL:
    storage = RedisStorage(redis=cache_service.redis)
else:
    storage = MemoryStorage()
    logger.warning("Using MemoryStorage for FSM - not recommended for production")

# Initialize dispatcher
dp = Dispatcher(storage=storage)

async def setup_bot():
    """Setup bot with all handlers and middlewares"""
    try:
        # Register middlewares
        dp.message.middleware(DatabaseMiddleware())
        dp.message.middleware(RateLimitMiddleware())
        dp.message.middleware(LoggingMiddleware())
        dp.message.middleware(ErrorHandlerMiddleware())
        dp.message.middleware(AuthenticationMiddleware())
        dp.message.middleware(LanguageMiddleware())
        dp.message.middleware(UserActivityMiddleware())
        
        # Register callback query middlewares
        dp.callback_query.middleware(DatabaseMiddleware())
        dp.callback_query.middleware(RateLimitMiddleware())
        dp.callback_query.middleware(LoggingMiddleware())
        dp.callback_query.middleware(ErrorHandlerMiddleware())
        dp.callback_query.middleware(AuthenticationMiddleware())
        dp.callback_query.middleware(LanguageMiddleware())
        dp.callback_query.middleware(UserActivityMiddleware())
        
        # Register handlers
        register_user_handlers(dp)
        register_admin_handlers(dp)
        register_error_handlers(dp)
        register_consultation_handlers(dp)
        register_question_handlers(dp)
        register_payment_handlers(dp)
        
        logger.info("Bot setup completed successfully")
        
    except Exception as e:
        logger.error(f"Error setting up bot: {e}", exc_info=True)
        raise

async def start_polling():
    """Start bot polling"""
    try:
        # Setup bot
        await setup_bot()
        
        # Start polling
        await dp.start_polling(bot, skip_updates=True)
        
        logger.info("Bot polling started")
        
    except Exception as e:
        logger.error(f"Error starting bot: {e}", exc_info=True)
        raise

async def stop_polling():
    """Stop bot polling"""
    try:
        await dp.stop_polling()
        await bot.session.close()
        
        logger.info("Bot polling stopped")
        
    except Exception as e:
        logger.error(f"Error stopping bot: {e}", exc_info=True)

__all__ = [
    'bot',
    'dp',
    'setup_bot',
    'start_polling',
    'stop_polling'
]

```

# telegram_bot\bot\filters.py

```py
from aiogram.filters import BaseFilter
from aiogram.types import Message, CallbackQuery
from typing import Union, Optional
from datetime import datetime, timedelta

from telegram_bot.core.config import settings
from telegram_bot.models import User
from telegram_bot.utils.cache import cache

class IsAdmin(BaseFilter):
    """Check if user is admin"""
    async def __call__(self, event: Union[Message, CallbackQuery]) -> bool:
        return event.from_user.id in settings.ADMIN_IDS

class IsSupport(BaseFilter):
    """Check if user is support"""
    async def __call__(self, event: Union[Message, CallbackQuery], user: User) -> bool:
        return any(role == 'SUPPORT' for role in user.roles)

class IsModerator(BaseFilter):
    """Check if user is moderator"""
    async def __call__(self, event: Union[Message, CallbackQuery], user: User) -> bool:
        return any(role in ['ADMIN', 'MODERATOR', 'SUPPORT'] for role in user.roles)

class HasActiveSubscription(BaseFilter):
    """Check if user has active subscription"""
    async def __call__(self, event: Union[Message, CallbackQuery], user: User) -> bool:
        subscription = await cache.get(f"subscription:{user.id}")
        if not subscription:
            return False
        return datetime.fromisoformat(subscription['expires_at']) > datetime.utcnow()

class RateLimit(BaseFilter):
    """Rate limiting filter"""
    
    def __init__(self, rate: int, per: int):
        self.rate = rate  # Number of requests
        self.per = per    # Time period in seconds
    
    async def __call__(self, event: Union[Message, CallbackQuery]) -> bool:
        user_id = event.from_user.id
        key = f"rate_limit:{user_id}:{event.chat.id}"
        
        # Get current count
        count = await cache.get(key) or 0
        
        if count >= self.rate:
            return False
        
        # Increment count
        pipe = cache.redis.pipeline()
        pipe.incr(key)
        pipe.expire(key, self.per)
        await pipe.execute()
        
        return True

class HasCompletedRegistration(BaseFilter):
    """Check if user has completed registration"""
    async def __call__(self, event: Union[Message, CallbackQuery], user: User) -> bool:
        return bool(user.language and user.full_name)

class IsBlocked(BaseFilter):
    """Check if user is blocked"""
    async def __call__(self, event: Union[Message, CallbackQuery], user: User) -> bool:
        return user.is_blocked

class HasActiveConsultation(BaseFilter):
    """Check if user has active consultation"""
    async def __call__(self, event: Union[Message, CallbackQuery], user: User) -> bool:
        return await cache.exists(f"active_consultation:{user.id}")

class IsWorkingHours(BaseFilter):
    """Check if current time is within working hours"""
    
    def __init__(
        self,
        start_hour: int = 9,
        end_hour: int = 18,
        working_days: set = None
    ):
        self.start_hour = start_hour
        self.end_hour = end_hour
        self.working_days = working_days or {0, 1, 2, 3, 4}  # Mon-Fri
    
    async def __call__(self, event: Union[Message, CallbackQuery]) -> bool:
        now = datetime.now()
        return (
            now.weekday() in self.working_days and
            self.start_hour <= now.hour < self.end_hour
        )

class HasPermission(BaseFilter):
    """Check if user has specific permission"""
    
    def __init__(self, permission: str):
        self.permission = permission
    
    async def __call__(self, event: Union[Message, CallbackQuery], user: User) -> bool:
        user_permissions = await cache.get(f"permissions:{user.id}")
        if not user_permissions:
            return False
        return self.permission in user_permissions

class ContentTypeFilter(BaseFilter):
    """Filter messages by content type"""
    
    def __init__(self, content_types: Union[str, list]):
        self.content_types = (
            [content_types] if isinstance(content_types, str) else content_types
        )
    
    async def __call__(self, message: Message) -> bool:
        return message.content_type in self.content_types

class TextLengthFilter(BaseFilter):
    """Filter messages by text length"""
    
    def __init__(self, min_length: Optional[int] = None, max_length: Optional[int] = None):
        self.min_length = min_length
        self.max_length = max_length
    
    async def __call__(self, message: Message) -> bool:
        if not message.text:
            return False
            
        text_length = len(message.text)
        
        if self.min_length and text_length < self.min_length:
            return False
            
        if self.max_length and text_length > self.max_length:
            return False
            
        return True

class RegexFilter(BaseFilter):
    """Filter messages by regex pattern"""
    
    def __init__(self, pattern: str):
        import re
        self.pattern = re.compile(pattern)
    
    async def __call__(self, message: Message) -> bool:
        if not message.text:
            return False
        return bool(self.pattern.match(message.text))

class LanguageFilter(BaseFilter):
    """Filter messages by user language"""
    
    def __init__(self, languages: Union[str, list]):
        self.languages = [languages] if isinstance(languages, str) else languages
    
    async def __call__(self, event: Union[Message, CallbackQuery], user: User) -> bool:
        return user.language in self.languages

class ChatTypeFilter(BaseFilter):
    """Filter messages by chat type"""
    
    def __init__(self, chat_types: Union[str, list]):
        self.chat_types = [chat_types] if isinstance(chat_types, str) else chat_types
    
    async def __call__(self, message: Message) -> bool:
        return message.chat.type in self.chat_types

class StateFilter(BaseFilter):
    """Filter by current user state"""
    
    def __init__(self, states: Union[str, list]):
        from telegram_bot.bot.states import STATE_MAPPING
        self.states = [states] if isinstance(states, str) else states
        self.state_objects = []
        
        for state in self.states:
            if ':' in state:
                group, state_name = state.split(':')
                if group in STATE_MAPPING:
                    state_obj = getattr(STATE_MAPPING[group], state_name, None)
                    if state_obj:
                        self.state_objects.append(state_obj)
    
    async def __call__(
        self,
        event: Union[Message, CallbackQuery],
        state: Optional[str] = None
    ) -> bool:
        if not state:
            return False
        return state in self.state_objects

# Composite filters
class AdminCommand(BaseFilter):
    """Combined filter for admin commands"""
    async def __call__(
        self,
        message: Message,
        user: User,
        state: Optional[str] = None
    ) -> bool:
        is_admin = await IsAdmin()(message)
        is_command = message.content_type == 'text' and message.text.startswith('/')
        return is_admin and is_command

class ModeratorAction(BaseFilter):
    """Combined filter for moderator actions"""
    async def __call__(
        self,
        event: Union[Message, CallbackQuery],
        user: User
    ) -> bool:
        is_moderator = await IsModerator()(event, user)
        is_working_hours = await IsWorkingHours()(event)
        return is_moderator and is_working_hours

# Export all filters
__all__ = [
    'IsAdmin',
    'IsSupport',
    'IsModerator',
    'HasActiveSubscription',
    'RateLimit',
    'HasCompletedRegistration',
    'IsBlocked',
    'HasActiveConsultation',
    'IsWorkingHours',
    'HasPermission',
    'ContentTypeFilter',
    'TextLengthFilter',
    'RegexFilter',
    'LanguageFilter',
    'ChatTypeFilter',
    'StateFilter',
    'AdminCommand',
    'ModeratorAction',
    'UserActivityFilter',
    'PaymentStatusFilter',
    'ConsultationStatusFilter',
    'QuestionCategoryFilter',
    'NotificationFilter'
]

class UserActivityFilter(BaseFilter):
    """Filter users by activity status"""
    
    def __init__(self, days: int = 7):
        self.days = days
    
    async def __call__(self, event: Union[Message, CallbackQuery], user: User) -> bool:
        if not user.last_active:
            return False
            
        time_diff = datetime.utcnow() - user.last_active
        return time_diff.days <= self.days

class PaymentStatusFilter(BaseFilter):
    """Filter by payment status"""
    
    def __init__(self, statuses: Union[str, list]):
        self.statuses = [statuses] if isinstance(statuses, str) else statuses
    
    async def __call__(self, event: Union[Message, CallbackQuery], payment_status: str) -> bool:
        return payment_status in self.statuses

class ConsultationStatusFilter(BaseFilter):
    """Filter by consultation status"""
    
    def __init__(self, statuses: Union[str, list]):
        self.statuses = [statuses] if isinstance(statuses, str) else statuses
    
    async def __call__(
        self,
        event: Union[Message, CallbackQuery],
        consultation_status: str
    ) -> bool:
        return consultation_status in self.statuses

class QuestionCategoryFilter(BaseFilter):
    """Filter questions by category"""
    
    def __init__(self, categories: Union[str, list]):
        self.categories = [categories] if isinstance(categories, str) else categories
    
    async def __call__(
        self,
        event: Union[Message, CallbackQuery],
        question_category: str
    ) -> bool:
        return question_category in self.categories

class NotificationFilter(BaseFilter):
    """Filter by notification settings"""
    
    def __init__(self, notification_type: str):
        self.notification_type = notification_type
    
    async def __call__(self, event: Union[Message, CallbackQuery], user: User) -> bool:
        user_settings = await cache.get(f"notification_settings:{user.id}")
        if not user_settings:
            return True  # Default to allowing notifications
        return user_settings.get(self.notification_type, True)

class UserRoleFilter(BaseFilter):
    """Filter users by role"""
    
    def __init__(self, roles: Union[str, list]):
        self.roles = [roles] if isinstance(roles, str) else roles
    
    async def __call__(self, event: Union[Message, CallbackQuery], user: User) -> bool:
        return any(role in user.roles for role in self.roles)

class UserSubscriptionFilter(BaseFilter):
    """Filter by subscription level"""
    
    def __init__(self, subscription_types: Union[str, list]):
        self.subscription_types = (
            [subscription_types]
            if isinstance(subscription_types, str)
            else subscription_types
        )
    
    async def __call__(self, event: Union[Message, CallbackQuery], user: User) -> bool:
        subscription = await cache.get(f"subscription:{user.id}")
        if not subscription:
            return False
        return subscription.get('type') in self.subscription_types

class MessageFrequencyFilter(BaseFilter):
    """Filter based on message frequency"""
    
    def __init__(self, max_messages: int, time_window: int):
        self.max_messages = max_messages
        self.time_window = time_window
    
    async def __call__(self, message: Message) -> bool:
        user_id = message.from_user.id
        key = f"message_frequency:{user_id}"
        
        # Get message history
        message_times = await cache.get(key) or []
        current_time = datetime.utcnow()
        
        # Filter out old messages
        message_times = [
            t for t in message_times
            if (current_time - datetime.fromisoformat(t)).total_seconds() <= self.time_window
        ]
        
        # Check frequency
        if len(message_times) >= self.max_messages:
            return False
        
        # Add new message time
        message_times.append(current_time.isoformat())
        await cache.set(key, message_times, expire=self.time_window)
        
        return True

class FileTypeFilter(BaseFilter):
    """Filter file uploads by type"""
    
    def __init__(self, allowed_types: Union[str, list]):
        self.allowed_types = [allowed_types] if isinstance(allowed_types, str) else allowed_types
    
    async def __call__(self, message: Message) -> bool:
        if not message.document:
            return False
            
        file_ext = message.document.file_name.split('.')[-1].lower()
        return file_ext in self.allowed_types

class UserVerificationFilter(BaseFilter):
    """Filter by user verification status"""
    
    async def __call__(self, event: Union[Message, CallbackQuery], user: User) -> bool:
        verified = await cache.get(f"verified:{user.id}")
        return bool(verified)

class ChainFilter(BaseFilter):
    """Combine multiple filters with AND logic"""
    
    def __init__(self, filters: list):
        self.filters = filters
    
    async def __call__(
        self,
        event: Union[Message, CallbackQuery],
        **kwargs
    ) -> bool:
        return all(
            await filter_(event, **kwargs)
            for filter_ in self.filters
        )

class AnyFilter(BaseFilter):
    """Combine multiple filters with OR logic"""
    
    def __init__(self, filters: list):
        self.filters = filters
    
    async def __call__(
        self,
        event: Union[Message, CallbackQuery],
        **kwargs
    ) -> bool:
        return any(
            await filter_(event, **kwargs)
            for filter_ in self.filters
        )

class CustomFilter(BaseFilter):
    """Create custom filter with callable"""
    
    def __init__(self, func: callable):
        self.func = func
    
    async def __call__(
        self,
        event: Union[Message, CallbackQuery],
        **kwargs
    ) -> bool:
        return await self.func(event, **kwargs)

# Helper functions
def create_filter_chain(*filters: BaseFilter) -> ChainFilter:
    """Create chain of filters"""
    return ChainFilter(list(filters))

def create_any_filter(*filters: BaseFilter) -> AnyFilter:
    """Create OR combination of filters"""
    return AnyFilter(list(filters))

def create_custom_filter(func: callable) -> CustomFilter:
    """Create custom filter from callable"""
    return CustomFilter(func)

# Common filter combinations
admin_only = create_filter_chain(IsAdmin(), IsWorkingHours())
support_only = create_filter_chain(IsSupport(), IsWorkingHours())
moderator_only = create_filter_chain(IsModerator(), IsWorkingHours())
active_user = create_filter_chain(
    HasCompletedRegistration(),
    UserActivityFilter(days=30),
    ~IsBlocked()
)
premium_user = create_filter_chain(
    active_user,
    HasActiveSubscription()
)
verified_user = create_filter_chain(
    active_user,
    UserVerificationFilter()
)

# Export additional items
__all__.extend([
    'UserRoleFilter',
    'UserSubscriptionFilter',
    'MessageFrequencyFilter',
    'FileTypeFilter',
    'UserVerificationFilter',
    'ChainFilter',
    'AnyFilter',
    'CustomFilter',
    'create_filter_chain',
    'create_any_filter',
    'create_custom_filter',
    'admin_only',
    'support_only',
    'moderator_only',
    'active_user',
    'premium_user',
    'verified_user'
])
```

# telegram_bot\bot\handlers\__init__.py

```py
from typing import Dict, Any
import logging
from aiogram import Dispatcher

from telegram_bot.bot.handlers.users import register_user_handlers
from telegram_bot.bot.handlers.admin import register_admin_handlers
from telegram_bot.bot.handlers.questions import register_question_handlers
from telegram_bot.bot.handlers.consultations import register_consultation_handlers
from telegram_bot.bot.handlers.payments import register_payment_handlers
from telegram_bot.bot.handlers.faq import register_faq_handlers
from telegram_bot.bot.handlers.support import register_support_handlers
from telegram_bot.bot.handlers.errors import register_error_handlers

logger = logging.getLogger(__name__)

def setup_handlers(dp: Dispatcher) -> None:
    """Setup all bot handlers"""
    handlers = [
        ("users", register_user_handlers),
        ("admin", register_admin_handlers),
        ("questions", register_question_handlers),
        ("consultations", register_consultation_handlers), 
        ("payments", register_payment_handlers),
        ("faq", register_faq_handlers),
        ("support", register_support_handlers),
        ("errors", register_error_handlers)
    ]

    for name, register_func in handlers:
        try:
            register_func(dp)
            logger.info(f"Successfully registered {name} handlers")
        except Exception as e:
            logger.error(f"Failed to register {name} handlers: {e}")
            raise

__all__ = ['setup_handlers']
```

# telegram_bot\bot\handlers\admin.py

```py
# from aiogram import Router, F, Dispatcher
# from aiogram.filters import Command
# from aiogram.types import Message, CallbackQuery
# from aiogram.fsm.context import FSMContext
# import logging
# from datetime import datetime, timedelta
# from sqlalchemy import select
# import asyncio
# from telegram_bot.core.config import settings
# from telegram_bot.models import (
#     User, Question, Consultation,
#     ConsultationStatus, PaymentStatus,FAQ
# )
# from aiogram.types import (
#     InlineKeyboardMarkup,
#     InlineKeyboardButton,
#     ReplyKeyboardMarkup,
#     KeyboardButton,
#     ReplyKeyboardRemove
# )
# from telegram_bot.services.questions import QuestionService
# from telegram_bot.services.consultations import ConsultationService
# from telegram_bot.services.analytics import AnalyticsService
# from telegram_bot.bot.keyboards import (
#     get_admin_menu_keyboard,
#     get_admin_question_keyboard,
#     get_admin_consultation_keyboard,
#     get_admin_user_keyboard,
#     get_admin_broadcast_keyboard,
#     get_cancel_keyboard
# )
# from telegram_bot.bot.states import AdminState
# from telegram_bot.core.constants import TEXTS

# logger = logging.getLogger(__name__)
# router = Router(name='admin')

# @router.message(Command("admin"))
# async def cmd_admin(message: Message, user: User):
#     """Admin panel entry point"""
#     try:
#         if user.telegram_id not in settings.ADMIN_IDS:
#             return
            
#         await message.answer(
#             "👨‍💼 Админ-панель",
#             reply_markup=get_admin_menu_keyboard()
#         )
        
#     except Exception as e:
#         logger.error(f"Error in admin command: {e}", exc_info=True)
#         await message.answer("Произошла ошибка")

# @router.callback_query(F.data == "admin:stats")
# async def show_admin_stats(callback: CallbackQuery, user: User, session):
#     """Show admin statistics"""
#     try:
#         if user.telegram_id not in settings.ADMIN_IDS:
#             return
            
#         analytics = AnalyticsService(session)
#         stats = await analytics.get_dashboard_stats()
        
#         text = "📊 Статистика\n\n"
        
#         # Users stats
#         text += "👥 Пользователи:\n"
#         text += f"Всего: {stats['users']['total']:,}\n"
#         text += f"Активных: {stats['users']['active']:,}\n"
#         text += f"Новых за неделю: {stats['users']['new_week']:,}\n\n"
        
#         # Questions stats
#         text += "❓ Вопросы:\n"
#         text += f"Всего: {stats['questions']['total']:,}\n"
#         text += f"Без ответа: {stats['questions']['unanswered']:,}\n"
#         text += f"Авто-ответы: {stats['questions']['auto_answered']:,}\n\n"
        
#         # Consultations stats
#         text += "📅 Консультации:\n"
#         text += f"Всего: {stats['consultations']['total']:,}\n"
#         text += f"Ожидают: {stats['consultations']['pending']:,}\n"
#         text += f"Доход за месяц: {stats['consultations']['monthly_revenue']:,.0f} сум\n"
        
#         await callback.message.edit_text(
#             text,
#             reply_markup=get_admin_menu_keyboard()
#         )
        
#     except Exception as e:
#         logger.error(f"Error showing admin stats: {e}", exc_info=True)
#         await callback.message.edit_text("Произошла ошибка")

# @router.callback_query(F.data == "admin:questions")
# async def show_admin_questions(callback: CallbackQuery, user: User, session):
#     """Show unanswered questions"""
#     try:
#         if user.telegram_id not in settings.ADMIN_IDS:
#             return
            
#         question_service = QuestionService(session)
#         questions = await question_service.get_unanswered_questions(limit=10)
        
#         if not questions:
#             await callback.message.edit_text(
#                 "Нет неотвеченных вопросов",
#                 reply_markup=get_admin_menu_keyboard()
#             )
#             return
            
#         text = "❓ Неотвеченные вопросы:\n\n"
        
#         for q in questions:
#             text += f"👤 {q.user.full_name}"
#             if q.user.username:
#                 text += f" (@{q.user.username})"
#             text += f"\n📝 {q.question_text}\n"
#             text += f"🕒 {q.created_at.strftime('%d.%m.%Y %H:%M')}\n\n"
            
#         await callback.message.edit_text(
#             text,
#             reply_markup=get_admin_question_keyboard(questions)
#         )
        
#     except Exception as e:
#         logger.error(f"Error showing admin questions: {e}", exc_info=True)
#         await callback.message.edit_text("Произошла ошибка")

# @router.callback_query(F.data.startswith("admin:answer:"))
# async def answer_question(callback: CallbackQuery, state: FSMContext, user: User):
#     """Start answering question"""
#     try:
#         if user.telegram_id not in settings.ADMIN_IDS:
#             return
            
#         question_id = int(callback.data.split(":")[2])
        
#         # Save question ID in state
#         await state.set_state(AdminState.answering_question)
#         await state.update_data(question_id=question_id)
        
#         await callback.message.edit_text(
#             "📝 Введите ответ на вопрос:",
#             reply_markup=get_cancel_keyboard('ru')
#         )
        
#     except Exception as e:
#         logger.error(f"Error starting answer: {e}", exc_info=True)
#         await callback.message.edit_text("Произошла ошибка")

# @router.message(AdminState.answering_question)
# async def process_answer(message: Message, state: FSMContext, user: User, session):
#     """Process answer to question"""
#     try:
#         if user.telegram_id not in settings.ADMIN_IDS:
#             return
            
#         # Get question ID from state
#         data = await state.get_data()
#         question_id = data.get('question_id')
        
#         if not question_id:
#             await message.answer("Произошла ошибка")
#             await state.clear()
#             return
            
#         # Save answer
#         question_service = QuestionService(session)
#         answer = await question_service.create_answer(
#             question_id=question_id,
#             answer_text=message.text,
#             created_by=user.id
#         )
        
#         # Send answer to user
#         question = await question_service.get_question(question_id)
#         if question and question.user:
#             from telegram_bot.bot import bot
#             await bot.send_message(
#                 question.user.telegram_id,
#                 f"✅ Ответ на ваш вопрос:\n\n"
#                 f"❓ {question.question_text}\n\n"
#                 f"📝 {answer.answer_text}"
#             )
        
#         # Clear state
#         await state.clear()
        
#         # Show success message
#         await message.answer(
#             "✅ Ответ отправлен",
#             reply_markup=get_admin_menu_keyboard()
#         )
        
#         # Track answer
#         analytics = AnalyticsService(session)
#         await analytics.track_event(
#             user_id=user.id,
#             event_type="admin_answer",
#             data={"question_id": question_id}
#         )
        
#     except Exception as e:
#         logger.error(f"Error processing answer: {e}", exc_info=True)
#         await message.answer("Произошла ошибка")
#         await state.clear()

# @router.callback_query(F.data == "admin:broadcast")
# async def start_broadcast(callback: CallbackQuery, state: FSMContext, user: User):
#     """Start broadcast message"""
#     try:
#         if user.telegram_id not in settings.ADMIN_IDS:
#             return
            
#         await state.set_state(AdminState.creating_broadcast)
        
#         await callback.message.edit_text(
#             "📢 Введите сообщение для рассылки:",
#             reply_markup=get_cancel_keyboard('ru')
#         )
        
#     except Exception as e:
#         logger.error(f"Error starting broadcast: {e}", exc_info=True)
#         await callback.message.edit_text("Произошла ошибка")

# @router.message(AdminState.creating_broadcast)
# async def process_broadcast_message(message: Message, state: FSMContext, user: User):
#     """Save broadcast message and select target"""
#     try:
#         if user.telegram_id not in settings.ADMIN_IDS:
#             return
            
#         # Save message text
#         await state.update_data(broadcast_text=message.text)
        
#         # Show targeting options
#         await message.answer(
#             "📊 Выберите целевую аудиторию:",
#             reply_markup=get_admin_broadcast_keyboard()
#         )
        
#         await state.set_state(AdminState.selecting_broadcast_target)
        
#     except Exception as e:
#         logger.error(f"Error processing broadcast: {e}", exc_info=True)
#         await message.answer("Произошла ошибка")
#         await state.clear()

# @router.callback_query(F.data.startswith("broadcast:"), AdminState.selecting_broadcast_target)
# async def send_broadcast(callback: CallbackQuery, state: FSMContext, user: User, session):
#     """Send broadcast message"""
#     try:
#         if user.telegram_id not in settings.ADMIN_IDS:
#             return
            
#         target = callback.data.split(":")[1]
        
#         # Get message text
#         data = await state.get_data()
#         text = data.get('broadcast_text')
        
#         if not text:
#             await callback.message.edit_text("Произошла ошибка")
#             await state.clear()
#             return
            
#         # Get target users
#         query = select(User.telegram_id).filter(User.is_blocked == False)
        
#         if target == "active":
#             # Only users active in last 7 days
#             week_ago = datetime.utcnow() - timedelta(days=7)
#             query = query.filter(User.last_active >= week_ago)
#         elif target in ("uz", "ru"):
#             # Users with specific language
#             query = query.filter(User.language == target)
            
#         result = await session.execute(query)
#         user_ids = result.scalars().all()
        
#         # Send messages
#         from telegram_bot.bot import bot
#         success = 0
#         failed = 0
        
#         for uid in user_ids:
#             try:
#                 await bot.send_message(uid, text)
#                 success += 1
#                 await asyncio.sleep(0.05)  # Avoid flood limits
#             except Exception as e:
#                 logger.error(f"Error sending broadcast to {uid}: {e}")
#                 failed += 1
        
#         # Show results
#         await callback.message.edit_text(
#             f"📊 Результаты рассылки:\n\n"
#             f"✅ Успешно: {success}\n"
#             f"❌ Ошибки: {failed}\n"
#             f"📧 Всего: {len(user_ids)}",
#             reply_markup=get_admin_menu_keyboard()
#         )
        
#         # Track broadcast
#         analytics = AnalyticsService(session)
#         await analytics.track_event(
#             user_id=user.id,
#             event_type="broadcast_sent",
#             data={
#                 "target": target,
#                 "success": success,
#                 "failed": failed,
#                 "total": len(user_ids)
#             }
#         )
        
#         # Clear state
#         await state.clear()
        
#     except Exception as e:
#         logger.error(f"Error sending broadcast: {e}", exc_info=True)
#         await callback.message.edit_text("Произошла ошибка")
#         await state.clear()

# @router.callback_query(F.data.startswith("admin:user:"))
# async def show_user_details(callback: CallbackQuery, user: User, session):
#     """Show user details"""
#     try:
#         if user.telegram_id not in settings.ADMIN_IDS:
#             return
            
#         target_id = int(callback.data.split(":")[2])
        
#         # Get user
#         target_user = await session.get(User, target_id)
#         if not target_user:
#             await callback.answer("Пользователь не найден")
#             return
            
#         # Get user statistics
#         analytics = AnalyticsService(session)
#         stats = await analytics.get_user_stats(target_id)
        
#         text = (
#             f"👤 Пользователь: {target_user.full_name}\n"
#             f"🆔 ID: {target_user.telegram_id}\n"
#             f"👤 Username: {f'@{target_user.username}' if target_user.username else '-'}\n"
#             f"🌐 Язык: {target_user.language.upper()}\n"
#             f"📅 Регистрация: {target_user.created_at.strftime('%d.%m.%Y')}\n"
#             f"⏱ Последняя активность: {target_user.last_active.strftime('%d.%m.%Y %H:%M') if target_user.last_active else '-'}\n\n"
#             f"📊 Статистика:\n"
#             f"❓ Вопросов: {stats['questions_count']}\n"
#             f"📅 Консультаций: {stats['consultations_count']}\n"
#             f"💰 Всего оплачено: {stats['total_spent']:,.0f} сум\n"
#             f"⭐️ Средняя оценка: {stats['average_rating']:.1f}/5\n\n"
#             f"🚫 Заблокирован: {'Да' if target_user.is_blocked else 'Нет'}"
#         )
        
#         await callback.message.edit_text(
#             text,
#             reply_markup=get_admin_user_keyboard(target_id)
#         )
        
#     except Exception as e:
#         logger.error(f"Error showing user details: {e}", exc_info=True)
#         await callback.message.edit_text("Произошла ошибка")

# @router.callback_query(F.data.startswith("admin:block:"))
# async def toggle_user_block(callback: CallbackQuery, user: User, session):
#     """Toggle user block status"""
#     try:
#         if user.telegram_id not in settings.ADMIN_IDS:
#             return
            
#         target_id = int(callback.data.split(":")[2])
        
#         # Get user
#         target_user = await session.get(User, target_id)
#         if not target_user:
#             await callback.answer("Пользователь не найден")
#             return
            
#         # Toggle block status
#         target_user.is_blocked = not target_user.is_blocked
#         await session.commit()
        
#         # Send notification to user
#         from telegram_bot.bot import bot
#         try:
#             if target_user.is_blocked:
#                 await bot.send_message(
#                     target_user.telegram_id,
#                     TEXTS[target_user.language]['account_blocked']
#                 )
#             else:
#                 await bot.send_message(
#                     target_user.telegram_id,
#                     TEXTS[target_user.language]['account_unblocked']
#                 )
#         except Exception as e:
#             logger.error(f"Error notifying user about block status: {e}")
        
#         # Show updated user details
#         await show_user_details(callback, user, session)
        
#     except Exception as e:
#         logger.error(f"Error toggling user block: {e}", exc_info=True)
#         await callback.message.edit_text("Произошла ошибка")

# @router.callback_query(F.data == "admin:consultations")
# async def show_admin_consultations(callback: CallbackQuery, user: User, session):
#     """Show pending consultations"""
#     try:
#         if user.telegram_id not in settings.ADMIN_IDS:
#             return
            
#         consultation_service = ConsultationService(session)
#         consultations = await consultation_service.get_pending_consultations()
        
#         if not consultations:
#             await callback.message.edit_text(
#                 "Нет ожидающих консультаций",
#                 reply_markup=get_admin_menu_keyboard()
#             )
#             return
            
#         text = "📅 Ожидающие консультации:\n\n"
        
#         for consultation in consultations:
#             text += f"👤 {consultation.user.full_name}"
#             if consultation.user.username:
#                 text += f" (@{consultation.user.username})"
#             text += f"\n📞 {consultation.phone_number}\n"
#             text += f"💰 {consultation.amount:,.0f} сум\n"
#             text += f"📝 {consultation.description}\n"
#             text += f"🕒 {consultation.created_at.strftime('%d.%m.%Y %H:%M')}\n\n"
            
#         await callback.message.edit_text(
#             text,
#             reply_markup=get_admin_consultation_keyboard(consultations)
#         )
        
#     except Exception as e:
#         logger.error(f"Error showing consultations: {e}", exc_info=True)
#         await callback.message.edit_text("Произошла ошибка")

# @router.callback_query(F.data.startswith("admin:consultation:"))
# async def handle_consultation_action(callback: CallbackQuery, user: User, session):
#     """Handle consultation actions"""
#     try:
#         if user.telegram_id not in settings.ADMIN_IDS:
#             return
            
#         action, consultation_id = callback.data.split(":")[2:]
#         consultation_id = int(consultation_id)
        
#         consultation_service = ConsultationService(session)
#         consultation = await consultation_service.get_consultation(consultation_id)
        
#         if not consultation:
#             await callback.answer("Консультация не найдена")
#             return
            
#         if action == "approve":
#             # Approve consultation
#             await consultation_service.approve_consultation(consultation_id)
            
#             # Notify user
#             from telegram_bot.bot import bot
#             await bot.send_message(
#                 consultation.user.telegram_id,
#                 TEXTS[consultation.user.language]['consultation_approved']
#             )
            
#         elif action == "reject":
#             # Reject consultation
#             await consultation_service.reject_consultation(consultation_id)
            
#             # Notify user
#             from telegram_bot.bot import bot
#             await bot.send_message(
#                 consultation.user.telegram_id,
#                 TEXTS[consultation.user.language]['consultation_rejected']
#             )
        
#         # Show updated consultations list
#         await show_admin_consultations(callback, user, session)
        
#     except Exception as e:
#         logger.error(f"Error handling consultation action: {e}", exc_info=True)
#         await callback.message.edit_text("Произошла ошибка")


# @router.callback_query(F.data == "admin:faq")
# async def show_faq_list(callback: CallbackQuery, user: User, session):
#     """Show FAQ list to admin"""
#     if user.telegram_id not in settings.ADMIN_IDS:
#         return
        
#     # Get FAQ entries
#     result = await session.execute(
#         select(FAQ).order_by(FAQ.order.asc())
#     )
#     faqs = result.scalars().all()
    
#     text = "📋 FAQ List:\n\n"
#     for faq in faqs:
#         text += f"ID: {faq.id}\n"
#         text += f"Q: {faq.question[:50]}...\n"
#         text += f"Language: {faq.language}\n"
#         text += f"Status: {'✅' if faq.is_published else '❌'}\n\n"
        
#     keyboard = [
#         [InlineKeyboardButton(
#             text="➕ Add FAQ",
#             callback_data="admin:faq:add"
#         )],
#         [InlineKeyboardButton(
#             text="◀️ Back",
#             callback_data="admin:menu"
#         )]
#     ]
    
#     await callback.message.edit_text(
#         text,
#         reply_markup=InlineKeyboardMarkup(inline_keyboard=keyboard)
#     )

# @router.callback_query(F.data == "admin:faq:add")
# async def add_faq(callback: CallbackQuery, state: FSMContext, user: User):
#     """Start FAQ creation process"""
#     if user.telegram_id not in settings.ADMIN_IDS:
#         return
        
#     await state.set_state(AdminState.creating_faq)
#     await callback.message.edit_text(
#         "Please enter the question for FAQ:",
#         reply_markup=get_cancel_keyboard()
#     )

# @router.message(AdminState.creating_faq)
# async def process_faq_question(message: Message, state: FSMContext, session):
#     """Process FAQ question"""
#     await state.update_data(question=message.text)
#     await state.set_state(AdminState.creating_faq_answer)
#     await message.answer("Now enter the answer:")

# @router.message(AdminState.creating_faq_answer)
# async def process_faq_answer(message: Message, state: FSMContext, session):
#     """Process FAQ answer"""
#     data = await state.get_data()
    
#     faq = FAQ(
#         question=data['question'],
#         answer=message.text,
#         language='ru'  # Default language
#     )
#     session.add(faq)
#     await session.commit()
    
#     await state.clear()
#     await message.answer(
#         "✅ FAQ created successfully!",
#         reply_markup=get_admin_menu_keyboard()
#     )

# def register_handlers(dp: Dispatcher):
#     """Register admin handlers"""
#     dp.include_router(router)

# # Register message handlers
# router.message.register(cmd_admin, Command("admin"))
# router.message.register(
#     process_answer,
#     AdminState.answering_question
# )
# router.message.register(
#     process_broadcast_message,
#     AdminState.creating_broadcast
# )

# # Register callback handlers
# router.callback_query.register(
#     show_admin_stats,
#     F.data == "admin:stats"
# )
# router.callback_query.register(
#     show_admin_questions,
#     F.data == "admin:questions"
# )
# router.callback_query.register(
#     answer_question,
#     F.data.startswith("admin:answer:")
# )
# router.callback_query.register(
#     start_broadcast,
#     F.data == "admin:broadcast"
# )
# router.callback_query.register(
#     send_broadcast,
#     F.data.startswith("broadcast:"),
#     AdminState.selecting_broadcast_target
# )
# router.callback_query.register(
#     show_user_details,
#     F.data.startswith("admin:user:")
# )

# router.callback_query.register(
#     toggle_user_block,
#     F.data.startswith("admin:block:")
# )
# router.callback_query.register(
#     show_admin_consultations,
#     F.data == "admin:consultations"
# )
# router.callback_query.register(
#     handle_consultation_action,
#     F.data.startswith("admin:consultation:")
# )





from aiogram import Router, F, Dispatcher
from aiogram.filters import Command
from aiogram.types import Message, CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.fsm.context import FSMContext
import logging
from datetime import datetime, timedelta
from sqlalchemy import select, func
import asyncio

from telegram_bot.core.config import settings
from telegram_bot.models import (
    User, Question, Answer, Consultation,
    ConsultationStatus, PaymentStatus
)
from telegram_bot.services.analytics import AnalyticsService
from telegram_bot.services.questions import QuestionService
from telegram_bot.services.consultations import ConsultationService
from telegram_bot.bot.filters import IsAdmin
from telegram_bot.bot.states import AdminState
from telegram_bot.core.constants import TEXTS

logger = logging.getLogger(__name__)
router = Router(name='admin')

# Admin command handlers
@router.message(Command("admin"), IsAdmin())
async def admin_panel(message: Message):
    """Admin panel entry point"""
    keyboard = [
        [
            InlineKeyboardButton(text="📊 Statistics", callback_data="admin:stats"),
            InlineKeyboardButton(text="👥 Users", callback_data="admin:users")
        ],
        [
            InlineKeyboardButton(text="❓ Questions", callback_data="admin:questions"),
            InlineKeyboardButton(text="📅 Consultations", callback_data="admin:consultations")
        ],
        [
            InlineKeyboardButton(text="📢 Broadcast", callback_data="admin:broadcast"),
            InlineKeyboardButton(text="⚙️ Settings", callback_data="admin:settings")
        ]
    ]
    await message.answer(
        "👨‍💼 Welcome to Admin Panel\nSelect an option:",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=keyboard)
    )

@router.callback_query(F.data == "admin:stats", IsAdmin())
async def show_statistics(callback: CallbackQuery, session):
    """Show system statistics"""
    analytics = AnalyticsService(session)
    stats = await analytics.get_dashboard_stats()
    
    text = "📊 System Statistics\n\n"
    text += f"👥 Users: {stats['users']['total']}\n"
    text += f"➕ New today: {stats['users']['new_today']}\n"
    text += f"❓ Questions: {stats['questions']['total']}\n"
    text += f"✅ Answered: {stats['questions']['answered']}\n"
    text += f"📅 Consultations: {stats['consultations']['total']}\n"
    text += f"💰 Revenue: {stats['revenue']['total']:,.0f} sum\n"
    
    back_button = InlineKeyboardButton(text="◀️ Back", callback_data="admin:back")
    await callback.message.edit_text(
        text,
        reply_markup=InlineKeyboardMarkup(inline_keyboard=[[back_button]])
    )

@router.callback_query(F.data == "admin:broadcast", IsAdmin())
async def start_broadcast(callback: CallbackQuery, state: FSMContext):
    """Start broadcast message creation"""
    await state.set_state(AdminState.creating_broadcast)
    
    keyboard = [
        [
            InlineKeyboardButton(text="❌ Cancel", callback_data="admin:cancel")
        ]
    ]
    await callback.message.edit_text(
        "📢 Enter broadcast message text:",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=keyboard)
    )

@router.message(AdminState.creating_broadcast, IsAdmin())
async def process_broadcast_message(message: Message, state: FSMContext, session):
    """Process broadcast message text"""
    broadcast_text = message.text
    
    # Target selection keyboard
    keyboard = [
        [
            InlineKeyboardButton(text="👥 All Users", callback_data="broadcast:all"),
            InlineKeyboardButton(text="✅ Active Users", callback_data="broadcast:active")
        ],
        [
            InlineKeyboardButton(text="🇺🇿 Uzbek", callback_data="broadcast:uz"),
            InlineKeyboardButton(text="🇷🇺 Russian", callback_data="broadcast:ru")
        ],
        [
            InlineKeyboardButton(text="❌ Cancel", callback_data="admin:cancel")
        ]
    ]
    
    await state.update_data(broadcast_text=broadcast_text)
    await message.answer(
        "Select target audience:",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=keyboard)
    )
    await state.set_state(AdminState.selecting_broadcast_target)

@router.callback_query(F.data.startswith("broadcast:"), AdminState.selecting_broadcast_target, IsAdmin())
async def send_broadcast(callback: CallbackQuery, state: FSMContext, session):
    """Send broadcast message to selected audience"""
    target = callback.data.split(":")[1]
    data = await state.get_data()
    text = data['broadcast_text']
    
    # Get target users
    query = select(User.telegram_id).filter(User.is_blocked == False)
    if target == "active":
        week_ago = datetime.utcnow() - timedelta(days=7)
        query = query.filter(User.last_active >= week_ago)
    elif target in ["uz", "ru"]:
        query = query.filter(User.language == target)
        
    result = await session.execute(query)
    user_ids = result.scalars().all()
    
    # Send messages
    from telegram_bot.bot import bot
    sent = 0
    failed = 0
    
    for user_id in user_ids:
        try:
            await bot.send_message(user_id, text)
            sent += 1
            await asyncio.sleep(0.05)  # Rate limiting
        except Exception as e:
            logger.error(f"Failed to send broadcast to {user_id}: {e}")
            failed += 1
            
    # Show results
    await callback.message.edit_text(
        f"📊 Broadcast Results:\n\n"
        f"✅ Successfully sent: {sent}\n"
        f"❌ Failed: {failed}\n"
        f"👥 Total users: {len(user_ids)}"
    )
    await state.clear()

@router.callback_query(F.data == "admin:questions", IsAdmin())
async def show_questions(callback: CallbackQuery, session):
    """Show unanswered questions"""
    question_service = QuestionService(session)
    questions = await question_service.get_unanswered_questions(limit=10)
    
    if not questions:
        await callback.message.edit_text(
            "No unanswered questions",
            reply_markup=InlineKeyboardMarkup(inline_keyboard=[
                [InlineKeyboardButton(text="◀️ Back", callback_data="admin:back")]
            ])
        )
        return
        
    text = "❓ Unanswered Questions:\n\n"
    keyboard = []
    
    for q in questions:
        text += f"👤 {q.user.full_name}"
        if q.user.username:
            text += f" (@{q.user.username})"
        text += f"\n📝 {q.question_text}\n\n"
        
        keyboard.append([
            InlineKeyboardButton(
                text=f"Answer #{q.id}",
                callback_data=f"admin:answer:{q.id}"
            )
        ])
        
    keyboard.append([
        InlineKeyboardButton(text="◀️ Back", callback_data="admin:back")
    ])
    
    await callback.message.edit_text(
        text,
        reply_markup=InlineKeyboardMarkup(inline_keyboard=keyboard)
    )

@router.callback_query(F.data.startswith("admin:answer:"), IsAdmin())
async def start_answer(callback: CallbackQuery, state: FSMContext):
    """Start answering a question"""
    question_id = int(callback.data.split(":")[2])
    await state.set_state(AdminState.answering_question)
    await state.update_data(question_id=question_id)
    
    keyboard = [
        [InlineKeyboardButton(text="❌ Cancel", callback_data="admin:cancel")]
    ]
    await callback.message.edit_text(
        "Enter your answer:",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=keyboard)
    )

@router.message(AdminState.answering_question, IsAdmin())
async def process_answer(message: Message, state: FSMContext, session):
    """Process answer to question"""
    data = await state.get_data()
    question_id = data['question_id']
    
    question_service = QuestionService(session)
    question = await question_service.get_question(question_id)
    
    if not question:
        await message.answer("Question not found")
        await state.clear()
        return
        
    # Create answer
    answer = await question_service.create_answer(
        question_id=question_id,
        answer_text=message.text,
        created_by=message.from_user.id
    )
    
    # Notify user
    from telegram_bot.bot import bot
    await bot.send_message(
        question.user.telegram_id,
        f"✅ Your question has been answered:\n\n"
        f"❓ {question.question_text}\n\n"
        f"📝 {answer.answer_text}"
    )
    
    await message.answer("✅ Answer sent successfully")
    await state.clear()

@router.callback_query(F.data == "admin:users", IsAdmin())
async def show_users(callback: CallbackQuery, session):
    """Show user management panel"""
    total_users = await session.scalar(select(func.count(User.id)))
    active_users = await session.scalar(
        select(func.count(User.id))
        .filter(
            User.is_active == True,
            User.is_blocked == False
        )
    )
    
    text = "👥 User Management\n\n"
    text += f"Total users: {total_users}\n"
    text += f"Active users: {active_users}\n\n"
    text += "Select action:"
    
    keyboard = [
        [
            InlineKeyboardButton(text="📊 Statistics", callback_data="admin:user_stats"),
            InlineKeyboardButton(text="🔍 Search", callback_data="admin:user_search")
        ],
        [
            InlineKeyboardButton(text="⚠️ Blocked", callback_data="admin:blocked_users"),
            InlineKeyboardButton(text="◀️ Back", callback_data="admin:back")
        ]
    ]
    
    await callback.message.edit_text(
        text,
        reply_markup=InlineKeyboardMarkup(inline_keyboard=keyboard)
    )

@router.callback_query(F.data == "admin:settings", IsAdmin())
async def show_settings(callback: CallbackQuery):
    """Show admin settings panel"""
    keyboard = [
        [
            InlineKeyboardButton(text="🌐 Bot Settings", callback_data="admin:bot_settings"),
            InlineKeyboardButton(text="💳 Payment Settings", callback_data="admin:payment_settings")
        ],
        [
            InlineKeyboardButton(text="👥 User Roles", callback_data="admin:user_roles"),
            InlineKeyboardButton(text="⚙️ System Settings", callback_data="admin:system_settings")
        ],
        [
            InlineKeyboardButton(text="◀️ Back", callback_data="admin:back")
        ]
    ]
    
    await callback.message.edit_text(
        "⚙️ Admin Settings\nSelect category:",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=keyboard)
    )

# Register handlers
def register_handlers(dp: Dispatcher):
    """Register admin handlers"""
    dp.include_router(router)

```

# telegram_bot\bot\handlers\common.py

```py
from aiogram import Router, F
from aiogram.filters import Command, CommandStart
from aiogram.types import Message, CallbackQuery
from aiogram.fsm.context import FSMContext
from datetime import datetime
import logging

from telegram_bot.core.config import settings
from telegram_bot.core.constants import TEXTS
from telegram_bot.models import User, Question, Answer
from telegram_bot.services.analytics import AnalyticsService
from telegram_bot.services.questions import QuestionService
from telegram_bot.core.cache import cache_service as cache
from telegram_bot.bot.states import UserState
from telegram_bot.bot.keyboards import (
    get_language_keyboard,
    get_main_menu,
    get_help_keyboard,
    get_settings_keyboard
)

logger = logging.getLogger(__name__)
router = Router(name='common')

@router.message(CommandStart())
async def cmd_start(message: Message, state: FSMContext, user: User, session):
    """Handle /start command"""
    try:
        # Clear state
        await state.clear()
        
        # Track analytics
        analytics = AnalyticsService(session)
        await analytics.track_event(
            user_id=user.id,
            event_type="bot_start",
            data={
                "source": message.get_args() or "direct",
                "platform": message.from_user.language_code
            }
        )
        
        # Show language selection for new users
        if not user.language:
            await message.answer(
                "🌐 Выберите язык / Tilni tanlang",
                reply_markup=get_language_keyboard()
            )
            await state.set_state(UserState.selecting_language)
        else:
            await message.answer(
                TEXTS[user.language]['welcome_back'],
                reply_markup=get_main_menu(user.language)
            )
            
        # Update activity
        user.last_active = datetime.utcnow()
        await session.commit()
        await cache.set(f"user_active:{user.id}", True, expire=86400)
        
    except Exception as e:
        logger.error(f"Error in start command: {e}")
        await message.answer("An error occurred. Please try again.")

@router.message(Command("help"))
async def cmd_help(message: Message, user: User, session):
    """Handle /help command"""
    try:
        # Get FAQ questions
        question_service = QuestionService(session)
        faq = await question_service.get_faq_questions(user.language)
        
        # Format help message
        text = TEXTS[user.language]['help_message'] + "\n\n"
        
        if faq:
            text += "📝 " + TEXTS[user.language]['faq_title'] + "\n\n"
            for q in faq[:5]:
                text += f"❓ {q.question_text}\n"
                if q.answers:
                    text += f"✅ {q.answers[0].answer_text}\n"
                text += "\n"
        
        await message.answer(
            text,
            reply_markup=get_help_keyboard(user.language)
        )
        
        # Track analytics
        analytics = AnalyticsService(session)
        await analytics.track_event(
            user_id=user.id,
            event_type="help_request"
        )
        
    except Exception as e:
        logger.error(f"Error in help command: {e}")
        await message.answer(TEXTS[user.language]['error'])

@router.message(Command("settings"))
async def cmd_settings(message: Message, user: User):
    """Handle /settings command"""
    try:
        await message.answer(
            TEXTS[user.language]['settings_menu'],
            reply_markup=get_settings_keyboard(user.language)
        )
    except Exception as e:
        logger.error(f"Error in settings command: {e}")
        await message.answer(TEXTS[user.language]['error'])

@router.callback_query(F.data.startswith("language:"))
async def change_language(callback: CallbackQuery, user: User, session):
    """Handle language change"""
    try:
        language = callback.data.split(":")[1]
        old_language = user.language
        
        # Update user language
        user.language = language
        await session.commit()
        
        # Clear cache
        await cache.delete(f"user:{user.id}")
        
        # Send confirmation
        await callback.message.edit_text(
            TEXTS[language]['language_changed']
        )
        
        # Show main menu
        await callback.message.answer(
            TEXTS[language]['welcome'],
            reply_markup=get_main_menu(language)
        )
        
        # Track analytics
        analytics = AnalyticsService(session)
        await analytics.track_event(
            user_id=user.id,
            event_type="language_change",
            data={
                "old_language": old_language,
                "new_language": language
            }
        )
        
    except Exception as e:
        logger.error(f"Error changing language: {e}")
        await callback.message.answer(TEXTS[user.language]['error'])

@router.message(Command("cancel"))
async def cmd_cancel(message: Message, state: FSMContext, user: User):
    """Handle /cancel command"""
    try:
        current_state = await state.get_state()
        
        if current_state is None:
            await message.answer(
                TEXTS[user.language]['nothing_to_cancel'],
                reply_markup=get_main_menu(user.language)
            )
            return
            
        # Clear state
        await state.clear()
        
        await message.answer(
            TEXTS[user.language]['cancelled'],
            reply_markup=get_main_menu(user.language)
        )
        
    except Exception as e:
        logger.error(f"Error in cancel command: {e}")
        await message.answer(TEXTS[user.language]['error'])
```

# telegram_bot\bot\handlers\consultations.py

```py
from aiogram import Router, F
from aiogram.filters import Command
from aiogram.types import Message, CallbackQuery
from aiogram.fsm.context import FSMContext
from datetime import datetime, timedelta
import logging
from decimal import Decimal

from telegram_bot.core.constants import TEXTS
from telegram_bot.models import User, ConsultationStatus, PaymentProvider
from telegram_bot.services.consultations import ConsultationService
from telegram_bot.services.payments import PaymentService
from telegram_bot.core.errors import ValidationError
from telegram_bot.bot.keyboards import (
    get_consultation_type_keyboard,
    get_contact_keyboard,
    get_payment_methods_keyboard,
    get_consultation_time_keyboard,
    get_confirm_keyboard,
    get_main_menu_keyboard
)
from telegram_bot.bot.states import ConsultationState
from telegram_bot.utils.validators import validator

logger = logging.getLogger(__name__)
router = Router(name='consultations')

CONSULTATION_PRICES = {
    'online': Decimal('50000.00'),
    'office': Decimal('100000.00')
}

@router.message(Command("book"))
@router.message(F.text.in_([TEXTS['uz']['consultation'], TEXTS['ru']['consultation']]))
async def start_consultation(message: Message, state: FSMContext, user: User):
    """Start consultation booking process"""
    try:
        # Show consultation types
        await message.answer(
            TEXTS[user.language]['select_consultation_type'],
            reply_markup=get_consultation_type_keyboard(user.language)
        )
        await state.set_state(ConsultationState.selecting_type)
        
    except Exception as e:
        logger.error(f"Error starting consultation: {e}")
        await message.answer(TEXTS[user.language]['error'])
        await state.clear()

@router.callback_query(ConsultationState.selecting_type)
async def process_type_selection(callback: CallbackQuery, state: FSMContext, user: User):
    """Process consultation type selection"""
    try:
        consultation_type = callback.data.split(':')[1]
        if consultation_type not in CONSULTATION_PRICES:
            await callback.answer(TEXTS[user.language]['invalid_type'])
            return
            
        # Save type and show contact request
        await state.update_data(
            consultation_type=consultation_type,
            amount=CONSULTATION_PRICES[consultation_type]
        )
        
        await callback.message.edit_text(
            TEXTS[user.language]['enter_phone'],
            reply_markup=get_contact_keyboard(user.language)
        )
        await state.set_state(ConsultationState.entering_phone)
        
    except Exception as e:
        logger.error(f"Error processing consultation type: {e}")
        await callback.message.edit_text(TEXTS[user.language]['error'])
        await state.clear()

@router.message(ConsultationState.entering_phone)
async def process_phone(message: Message, state: FSMContext, user: User):
    """Process phone number input"""
    try:
        # Get phone number from contact or text
        if message.contact:
            phone = message.contact.phone_number
        else:
            phone = message.text
            
        # Validate phone
        try:
            phone = validator.phone_number(phone)
        except ValidationError:
            await message.answer(
                TEXTS[user.language]['invalid_phone'],
                reply_markup=get_contact_keyboard(user.language)
            )
            return
            
        # Save phone and request description
        await state.update_data(phone_number=phone)
        
        await message.answer(
            TEXTS[user.language]['describe_problem'],
            reply_markup=None
        )
        await state.set_state(ConsultationState.entering_description)
        
    except Exception as e:
        logger.error(f"Error processing phone: {e}")
        await message.answer(TEXTS[user.language]['error'])
        await state.clear()

@router.message(ConsultationState.entering_description)
async def process_description(message: Message, state: FSMContext, user: User, session):
    """Process consultation description"""
    try:
        description = message.text.strip()
        
        # Validate description
        try:
            description = validator.text_length(
                description,
                min_length=20,
                max_length=1000
            )
        except ValidationError:
            await message.answer(TEXTS[user.language]['invalid_description'])
            return
            
        # Get consultation data
        data = await state.get_data()
        
        # Create consultation
        consultation_service = ConsultationService(session)
        consultation = await consultation_service.create_consultation(
            user_id=user.id,
            consultation_type=data['consultation_type'],
            amount=data['amount'],
            phone_number=data['phone_number'],
            description=description
        )
        
        # Show payment methods
        await message.answer(
            TEXTS[user.language]['select_payment'].format(
                amount=data['amount']
            ),
            reply_markup=get_payment_methods_keyboard(
                language=user.language,
                consultation_id=consultation.id,
                amount=data['amount']
            )
        )
        
        # Update state
        await state.update_data(consultation_id=consultation.id)
        await state.set_state(ConsultationState.selecting_payment)
        
    except Exception as e:
        logger.error(f"Error processing description: {e}")
        await message.answer(TEXTS[user.language]['error'])
        await state.clear()

@router.callback_query(ConsultationState.selecting_payment)
async def process_payment_selection(callback: CallbackQuery, state: FSMContext, user: User, session):
    """Process payment method selection"""
    try:
        provider = callback.data.split(':')[1]
        if provider not in PaymentProvider.__members__:
            await callback.answer(TEXTS[user.language]['invalid_provider'])
            return
            
        # Get consultation data
        data = await state.get_data()
        
        # Create payment
        payment_service = PaymentService(session)
        payment, payment_url = await payment_service.create_payment(
            provider=PaymentProvider[provider],
            amount=data['amount'],
            consultation_id=data['consultation_id']
        )
        
        # Show payment link
        from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
        
        await callback.message.edit_text(
            TEXTS[user.language]['payment_link'].format(
                amount=data['amount'],
                provider=provider
            ),
            reply_markup=InlineKeyboardMarkup(inline_keyboard=[
                [InlineKeyboardButton(
                    text=TEXTS[user.language]['pay'],
                    url=payment_url
                )],
                [InlineKeyboardButton(
                    text=TEXTS[user.language]['cancel'],
                    callback_data='cancel_payment'
                )]
            ])
        )
        
        # Update state
        await state.update_data(payment_id=payment.id)
        await state.set_state(ConsultationState.awaiting_payment)
        
    except Exception as e:
        logger.error(f"Error processing payment selection: {e}")
        await callback.message.edit_text(TEXTS[user.language]['error'])
        await state.clear()

@router.callback_query(F.data == "cancel_payment", ConsultationState.awaiting_payment)
async def cancel_payment(callback: CallbackQuery, state: FSMContext, user: User, session):
    """Cancel payment"""
    try:
        data = await state.get_data()
        
        # Cancel consultation
        consultation_service = ConsultationService(session)
        await consultation_service.cancel_consultation(
            consultation_id=data['consultation_id']
        )
        
        await callback.message.edit_text(
            TEXTS[user.language]['payment_cancelled'],
            reply_markup=get_main_menu_keyboard(user.language)
        )
        
        await state.clear()
        
    except Exception as e:
        logger.error(f"Error cancelling payment: {e}")
        await callback.message.edit_text(TEXTS[user.language]['error'])
        await state.clear()

@router.callback_query(ConsultationState.selecting_time)
async def process_time_selection(callback: CallbackQuery, state: FSMContext, user: User, session):
    """Process consultation time selection"""
    try:
        selected_time = datetime.fromisoformat(callback.data.split(':')[1])
        
        # Get consultation data
        data = await state.get_data()
        
        # Schedule consultation
        consultation_service = ConsultationService(session)
        await consultation_service.schedule_consultation(
            consultation_id=data['consultation_id'],
            scheduled_time=selected_time
        )
        
        # Show confirmation
        await callback.message.edit_text(
            TEXTS[user.language]['consultation_scheduled'].format(
                time=selected_time.strftime("%d.%m.%Y %H:%M")
            ),
            reply_markup=get_main_menu_keyboard(user.language)
        )
        
        await state.clear()
        
    except Exception as e:
        logger.error(f"Error scheduling consultation: {e}")
        await callback.message.edit_text(TEXTS[user.language]['error'])
        await state.clear()

@router.message(Command("my_consultations"))
async def show_consultations(message: Message, user: User, session):
    """Show user's consultations"""
    try:
        consultation_service = ConsultationService(session)
        consultations = await consultation_service.get_user_consultations(user.id)
        
        if not consultations:
            await message.answer(
                TEXTS[user.language]['no_consultations'],
                reply_markup=get_main_menu_keyboard(user.language)
            )
            return
            
        # Format consultations list
        text = TEXTS[user.language]['your_consultations'] + "\n\n"
        
        for consultation in consultations:
            text += f"📅 {consultation.created_at.strftime('%d.%m.%Y')}\n"
            text += f"💰 {consultation.amount:,.0f} сум\n"
            text += f"📝 {consultation.description[:100]}...\n"
            text += f"✅ {TEXTS[user.language][f'status_{consultation.status.value.lower()}']} \n"
            
            if consultation.scheduled_time:
                text += f"🕒 {consultation.scheduled_time.strftime('%d.%m.%Y %H:%M')}\n"
                
            text += "\n"
            
            if len(text) > 4000:  # Telegram message limit
                await message.answer(text)
                text = ""
                
        if text:
            await message.answer(
                text,
                reply_markup=get_main_menu_keyboard(user.language)
            )
            
    except Exception as e:
        logger.error(f"Error showing consultations: {e}")
        await message.answer(TEXTS[user.language]['error'])

def register_handlers(dp):
    """Register consultation handlers"""
    dp.include_router(router)
```

# telegram_bot\bot\handlers\errors.py

```py
from aiogram import Router, F
from aiogram.types import ErrorEvent, Update
import logging
from datetime import datetime
import traceback
from typing import Any, Awaitable, Callable, Dict, Union
from aiogram import Bot, Dispatcher
from aiogram import BaseMiddleware
from telegram_bot.core.constants import TEXTS
from telegram_bot.services.analytics import AnalyticsService
from telegram_bot.core.config import settings
from telegram_bot.core.errors import (
    ValidationError,
    DatabaseError,
    AuthenticationError,
    PaymentError,
    RateLimitError
)

logger = logging.getLogger(__name__)
router = Router(name='errors')

@router.errors()
async def error_handler(event: ErrorEvent, analytics: AnalyticsService):
    """Global error handler"""
    try:
        # Get update and user info
        update: Update = event.update
        user_id = None
        language = 'ru'
        
        if update.message:
            user_id = update.message.from_user.id
            language = update.message.from_user.language_code
        elif update.callback_query:
            user_id = update.callback_query.from_user.id
            language = update.callback_query.from_user.language_code
            
        # Log error details
        error_data = {
            'user_id': user_id,
            'update_id': update.update_id,
            'error_type': type(event.exception).__name__,
            'error_msg': str(event.exception),
            'traceback': traceback.format_exc(),
            'timestamp': datetime.utcnow().isoformat()
        }
        
        logger.error(
            f"Error handling update {update.update_id}",
            extra={'error_data': error_data},
            exc_info=True
        )
        
        # Track error
        if analytics:
            await analytics.track_event(
                user_id=user_id,
                event_type='bot_error',
                data=error_data
            )
        
        # Prepare user message based on error type
        if isinstance(event.exception, ValidationError):
            error_text = TEXTS[language]['validation_error']
        elif isinstance(event.exception, DatabaseError):
            error_text = TEXTS[language]['database_error']
        elif isinstance(event.exception, AuthenticationError):
            error_text = TEXTS[language]['auth_error']
        elif isinstance(event.exception, PaymentError):
            error_text = TEXTS[language]['payment_error']
        elif isinstance(event.exception, RateLimitError):
            error_text = TEXTS[language]['rate_limit']
        else:
            error_text = TEXTS[language]['error']
        
        # Send error message to user
        if update.message:
            await update.message.answer(error_text)
        elif update.callback_query:
            await update.callback_query.message.answer(error_text)
        
        # Notify admins in production
        if settings.ENVIRONMENT == "production":
            admin_text = (
                f"❌ Error in bot:\n\n"
                f"User ID: {user_id}\n"
                f"Update ID: {update.update_id}\n"
                f"Error type: {type(event.exception).__name__}\n"
                f"Error: {str(event.exception)}\n\n"
                f"Traceback:\n<code>{traceback.format_exc()}</code>"
            )
            
            from telegram_bot.bot import bot
            for admin_id in settings.ADMIN_IDS:
                try:
                    await bot.send_message(
                        admin_id,
                        admin_text,
                        parse_mode="HTML"
                    )
                except Exception as e:
                    logger.error(f"Error notifying admin {admin_id}: {e}")
                    
    except Exception as e:
        logger.error(f"Error in error handler: {e}", exc_info=True)

@router.errors(F.update.message)
async def message_error_handler(event: ErrorEvent):
    """Handle message errors"""
    update: Update = event.update
    try:
        logger.error(
            f"Error handling message: {event.exception}",
            extra={
                'user_id': update.message.from_user.id,
                'message_id': update.message.message_id,
                'chat_id': update.message.chat.id
            },
            exc_info=True
        )
        
        # Send generic error message
        await update.message.answer(
            TEXTS[update.message.from_user.language_code]['error']
        )
        
    except Exception as e:
        logger.error(f"Error in message error handler: {e}", exc_info=True)

@router.errors(F.update.callback_query)
async def callback_error_handler(event: ErrorEvent):
    """Handle callback query errors"""
    update: Update = event.update
    try:
        logger.error(
            f"Error handling callback query: {event.exception}",
            extra={
                'user_id': update.callback_query.from_user.id,
                'callback_data': update.callback_query.data,
                'message_id': update.callback_query.message.message_id
            },
            exc_info=True
        )
        
        # Answer callback query with error
        await update.callback_query.answer(
            TEXTS[update.callback_query.from_user.language_code]['error'],
            show_alert=True
        )
        
    except Exception as e:
        logger.error(f"Error in callback error handler: {e}", exc_info=True)

def register_handlers(dp: Dispatcher):
    """Register error handlers"""
    dp.include_router(router)

# Error handling middleware
class ErrorHandlingMiddleware(BaseMiddleware):
    async def __call__(
        self,
        handler: Callable[[Update, Dict[str, Any]], Awaitable[Any]],
        event: Update,
        data: Dict[str, Any]
    ) -> Any:
        try:
            return await handler(event, data)
        except Exception as e:
            # Get error event
            error_event = ErrorEvent(
                update=event,
                exception=e
            )
            
            # Handle error
            await error_handler(
                error_event,
                data.get('analytics_service')
            )
            
            # Don't propagate error
            return None

# Export error handlers
__all__ = [
    'error_handler',
    'message_error_handler',
    'callback_error_handler',
    'register_handlers',
    'ErrorHandlingMiddleware'
]

```

# telegram_bot\bot\handlers\faq.py

```py
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
```

# telegram_bot\bot\handlers\messages.py

```py
from aiogram import Router, F
from aiogram.types import Message, CallbackQuery
from aiogram.fsm.context import FSMContext
from aiogram.filters import Command
import logging

from telegram_bot.core.constants import TEXTS
from telegram_bot.models import User, Question
from telegram_bot.services.questions import QuestionService
from telegram_bot.bot.states import QuestionState
from telegram_bot.bot.keyboards import (
    get_main_menu,
    get_similar_questions_keyboard,
    get_category_keyboard
)

logger = logging.getLogger(__name__)
router = Router(name='messages')

@router.message(Command("cancel"))
async def cancel_handler(message: Message, state: FSMContext, user: User):
    """Handle cancel command"""
    current_state = await state.get_state()
    if current_state is None:
        return
        
    await state.clear()
    await message.answer(
        TEXTS[user.language]['cancelled'],
        reply_markup=get_main_menu(user.language)
    )

@router.message(QuestionState.waiting_for_question)
async def process_question(message: Message, state: FSMContext, user: User, session):
    """Process user's question"""
    try:
        question_text = message.text.strip()
        
        # Validate question length
        if len(question_text) < 10:
            await message.answer(
                TEXTS[user.language]['question_too_short'],
                reply_markup=get_main_menu(user.language)
            )
            return
            
        if len(question_text) > 1000:
            await message.answer(
                TEXTS[user.language]['question_too_long'],
                reply_markup=get_main_menu(user.language)
            )
            return
        
        # Get question service
        question_service = QuestionService(session)
        
        # Find similar questions
        similar = await question_service.find_similar_questions(
            question_text,
            user.language
        )
        
        if similar:
            # Save question data
            await state.update_data(
                question_text=question_text,
                similar_questions=[(q.id, score) for q, score in similar]
            )
            await state.set_state(QuestionState.viewing_similar)
            
            # Format similar questions text
            text = TEXTS[user.language]['similar_questions_found'] + "\n\n"
            
            for i, (question, score) in enumerate(similar, 1):
                text += f"{i}. ❓ {question.question_text}\n"
                if question.answers:
                    text += f"✅ {question.answers[0].answer_text}\n"
                text += "\n"
            
            text += TEXTS[user.language]['similar_questions_prompt']
            
            await message.answer(
                text,
                reply_markup=get_similar_questions_keyboard(user.language)
            )
            
        else:
            # Create new question
            question = await question_service.create_question(
                user_id=user.id,
                question_text=question_text,
                language=user.language
            )
            
            await message.answer(
                TEXTS[user.language]['question_received'],
                reply_markup=get_main_menu(user.language)
            )
            
            # Clear state
            await state.clear()
            
            # Notify admins
            await notify_admins_new_question(question)
        
    except Exception as e:
        logger.error(f"Error processing question: {e}")
        await message.answer(
            TEXTS[user.language]['error'],
            reply_markup=get_main_menu(user.language)
        )
        await state.clear()

async def notify_admins_new_question(question: Question):
    """Notify admins about new question"""
    from telegram_bot.bot import bot
    from telegram_bot.core.config import settings
    
    text = f"📝 {TEXTS['ru']['new_question']}\n\n"
    text += f"👤 {question.user.full_name}"
    if question.user.username:
        text += f" (@{question.user.username})\n"
    else:
        text += "\n"
    text += f"🌐 {question.language.upper()}\n\n"
    text += f"❓ {question.question_text}"
    
    for admin_id in settings.ADMIN_IDS:
        try:
            await bot.send_message(admin_id, text)
        except Exception as e:
            logger.error(f"Error notifying admin {admin_id}: {e}")

@router.callback_query(F.data == "ask_anyway")
async def ask_anyway(callback: CallbackQuery, state: FSMContext, user: User, session):
    """Handle ask anyway button"""
    try:
        data = await state.get_data()
        question_text = data.get('question_text')
        
        if not question_text:
            await callback.answer(TEXTS[user.language]['error'])
            await state.clear()
            return
        
        # Create question
        question_service = QuestionService(session)
        question = await question_service.create_question(
            user_id=user.id,
            question_text=question_text,
            language=user.language
        )
        
        await callback.message.edit_text(
            TEXTS[user.language]['question_received'],
            reply_markup=get_main_menu(user.language)
        )
        
        # Notify admins
        await notify_admins_new_question(question)
        
        # Clear state
        await state.clear()
        
    except Exception as e:
        logger.error(f"Error asking anyway: {e}")
        await callback.message.edit_text(
            TEXTS[user.language]['error'],
            reply_markup=get_main_menu(user.language)
        )
        await state.clear()
```

# telegram_bot\bot\handlers\payments.py

```py
from aiogram import Router, F, Dispatcher
from aiogram.filters import Command
from aiogram.types import Message, CallbackQuery
from aiogram.fsm.context import FSMContext
import logging
from telegram_bot.core.database import Base, get_session
from sqlalchemy.ext.asyncio import AsyncSession

from decimal import Decimal
from aiogram.types import (
    InlineKeyboardMarkup,
    InlineKeyboardButton,
    ReplyKeyboardMarkup,
    KeyboardButton,
    ReplyKeyboardRemove
)
from telegram_bot.core.constants import TEXTS
from telegram_bot.models import User, Payment, ConsultationStatus, PaymentStatus
from telegram_bot.services.payments import PaymentService
from telegram_bot.services.consultations import ConsultationService
from telegram_bot.services.analytics import AnalyticsService
from telegram_bot.bot.keyboards import (
    get_start_keyboard,
    get_payment_methods_keyboard,
    get_consultation_actions_keyboard
)
from telegram_bot.bot.states import PaymentState
from telegram_bot.utils.validators import validator
from fastapi.responses import JSONResponse
from fastapi import Request,Depends
from datetime import datetime

logger = logging.getLogger(__name__)
router = Router(name='payments')

@router.callback_query(F.data.startswith("pay:"))
async def process_payment_selection(
    callback: CallbackQuery,
    state: FSMContext,
    user: User,
    session
):
    """Process payment method selection"""
    try:
        _, provider, consultation_id, amount = callback.data.split(":")
        consultation_id = int(consultation_id)
        amount = Decimal(amount)
        
        # Validate amount and consultation
        consultation_service = ConsultationService(session)
        consultation = await consultation_service.get_consultation(consultation_id)
        
        if not consultation:
            await callback.answer(TEXTS[user.language]['not_found'])
            return
            
        if consultation.user_id != user.id:
            await callback.answer(TEXTS[user.language]['not_your_consultation'])
            return
            
        if consultation.status != ConsultationStatus.PENDING:
            await callback.answer(TEXTS[user.language]['already_paid'])
            return
            
        # Create payment
        payment_service = PaymentService(session)
        payment_url = await payment_service.create_payment(
            provider=provider,
            amount=amount,
            consultation_id=consultation_id,
            user_id=user.id
        )
        
        # Save payment info to state
        await state.update_data(
            payment_provider=provider,
            consultation_id=consultation_id,
            amount=str(amount)
        )
        await state.set_state(PaymentState.awaiting_payment)
        
        # Send payment link
        await callback.message.edit_text(
            TEXTS[user.language]['payment_link'].format(
                amount=amount,
                provider=provider.upper()
            ),
            reply_markup=InlineKeyboardMarkup(inline_keyboard=[
                [
                    InlineKeyboardButton(
                        text=TEXTS[user.language]['pay'],
                        url=payment_url
                    )
                ],
                [
                    InlineKeyboardButton(
                        text=TEXTS[user.language]['cancel'],
                        callback_data="cancel_payment"
                    )
                ]
            ])
        )
        
        # Track payment initiated
        analytics = AnalyticsService(session)
        await analytics.track_event(
            user_id=user.id,
            event_type='payment_initiated',
            data={
                'consultation_id': consultation_id,
                'amount': float(amount),
                'provider': provider
            }
        )
        
    except Exception as e:
        logger.error(f"Error processing payment selection: {e}", exc_info=True)
        await callback.message.edit_text(TEXTS[user.language]['error'])

@router.callback_query(F.data == "cancel_payment")
async def cancel_payment(callback: CallbackQuery, state: FSMContext, user: User):
    """Cancel payment"""
    try:
        # Get payment data
        data = await state.get_data()
        consultation_id = data.get('consultation_id')
        
        if consultation_id:
            await callback.message.edit_text(
                TEXTS[user.language]['payment_cancelled'],
                reply_markup=get_consultation_actions_keyboard(
                    consultation_id,
                    user.language
                )
            )
        else:
            await callback.message.edit_text(
                TEXTS[user.language]['payment_cancelled'],
                reply_markup=get_start_keyboard(user.language)
            )
            
        # Clear state
        await state.clear()
        
    except Exception as e:
        logger.error(f"Error cancelling payment: {e}", exc_info=True)
        await callback.message.edit_text(TEXTS[user.language]['error'])

async def process_payment_callback(data: dict, session):
    """Process payment callback from payment system"""
    try:
        payment_service = PaymentService(session)
        consultation_service = ConsultationService(session)
        
        # Verify payment
        payment = await payment_service.verify_payment(data)
        if not payment:
            logger.error("Invalid payment callback")
            return False
            
        # Get consultation
        consultation = await consultation_service.get_consultation(
            payment.consultation_id
        )
        if not consultation:
            logger.error(f"Consultation not found: {payment.consultation_id}")
            return False
            
        # Update payment status
        payment.status = PaymentStatus.COMPLETED
        await session.commit()
        
        # Update consultation status
        consultation.status = ConsultationStatus.PAID
        await session.commit()
        
        # Send notification to user
        from telegram_bot.bot import bot
        try:
            await bot.send_message(
                consultation.user.telegram_id,
                TEXTS[consultation.user.language]['payment_success'],
                reply_markup=get_consultation_actions_keyboard(
                    consultation.id,
                    consultation.user.language
                )
            )
        except Exception as e:
            logger.error(f"Error notifying user: {e}")
            
        # Track payment
        analytics = AnalyticsService(session)
        await analytics.track_event(
            user_id=consultation.user_id,
            event_type='payment_completed',
            data={
                'consultation_id': consultation.id,
                'payment_id': payment.id,
                'amount': float(payment.amount)
            }
        )
        
        return True
        
    except Exception as e:
        logger.error(f"Error processing payment callback: {e}", exc_info=True)
        return False

@router.callback_query(F.data.startswith("refund:"))
async def process_refund_request(
    callback: CallbackQuery,
    user: User,
    session
):
    """Process refund request"""
    try:
        consultation_id = int(callback.data.split(":")[1])
        
        # Validate consultation
        consultation_service = ConsultationService(session)
        consultation = await consultation_service.get_consultation(consultation_id)
        
        if not consultation:
            await callback.answer(TEXTS[user.language]['not_found'])
            return
            
        if consultation.user_id != user.id:
            await callback.answer(TEXTS[user.language]['not_your_consultation'])
            return
            
        # Check if refund is possible
        if consultation.status not in [ConsultationStatus.PAID, ConsultationStatus.SCHEDULED]:
            await callback.answer(TEXTS[user.language]['refund_not_available'])
            return
            
        # Create refund
        payment_service = PaymentService(session)
        refund = await payment_service.create_refund(consultation_id)
        
        if refund:
            await callback.message.edit_text(
                TEXTS[user.language]['refund_initiated'],
                reply_markup=get_start_keyboard(user.language)
            )
            
            # Track refund request
            analytics = AnalyticsService(session)
            await analytics.track_event(
                user_id=user.id,
                event_type='refund_requested',
                data={'consultation_id': consultation_id}
            )
        else:
            await callback.message.edit_text(
                TEXTS[user.language]['refund_error'],
                reply_markup=get_start_keyboard(user.language)
            )
            
    except Exception as e:
        logger.error(f"Error processing refund: {e}", exc_info=True)
        await callback.message.edit_text(TEXTS[user.language]['error'])

async def process_refund_callback(data: dict, session):
    """Process refund callback from payment system"""
    try:
        payment_service = PaymentService(session)
        consultation_service = ConsultationService(session)
        
        # Verify refund
        refund = await payment_service.verify_refund(data)
        if not refund:
            logger.error("Invalid refund callback")
            return False
            
        # Get consultation
        consultation = await consultation_service.get_consultation(
            refund.consultation_id
        )
        if not consultation:
            logger.error(f"Consultation not found: {refund.consultation_id}")
            return False
            
        # Update consultation status
        consultation.status = ConsultationStatus.CANCELLED
        await session.commit()
        
        # Send notification to user
        from telegram_bot.bot import bot
        try:
            await bot.send_message(
                consultation.user.telegram_id,
                TEXTS[consultation.user.language]['refund_completed'],
                reply_markup=get_start_keyboard(consultation.user.language)
            )
        except Exception as e:
            logger.error(f"Error notifying user about refund: {e}")
            
        # Track refund
        analytics = AnalyticsService(session)
        await analytics.track_event(
            user_id=consultation.user_id,
            event_type='refund_completed',
            data={
                'consultation_id': consultation.id,
                'refund_id': refund.id,
                'amount': float(refund.amount)
            }
        )
        
        return True
        
    except Exception as e:
        logger.error(f"Error processing refund callback: {e}", exc_info=True)
        return False
    


@router.callback_query(F.data.startswith("pay:"))
async def handle_payment_selection(
    callback: CallbackQuery,
    user: User,
    state: FSMContext,
    session
):
    """Handle payment method selection"""
    try:
        provider, consultation_id = callback.data.split(":")[1:]
        consultation_id = int(consultation_id)
        
        # Get consultation
        consultation_service = ConsultationService(session)
        consultation = await consultation_service.get_consultation(consultation_id)
        
        if not consultation:
            await callback.answer(TEXTS[user.language]['consultation_not_found'])
            return
        
        if consultation.user_id != user.id:
            await callback.answer(TEXTS[user.language]['not_your_consultation'])
            return
            
        # Create payment
        payment_service = PaymentService(session)
        payment_url = await payment_service.create_payment(
            provider=provider,
            amount=consultation.amount,
            consultation_id=consultation_id
        )
        
        if not payment_url:
            await callback.message.edit_text(
                TEXTS[user.language]['payment_error']
            )
            return
            
        # Send payment link
        keyboard = [
            [InlineKeyboardButton(
                text=TEXTS[user.language]['pay'],
                url=payment_url
            )],
            [InlineKeyboardButton(
                text=TEXTS[user.language]['cancel'],
                callback_data=f"cancel_payment:{consultation_id}"
            )]
        ]
        
        await callback.message.edit_text(
            TEXTS[user.language]['payment_instruction'].format(
                amount=consultation.amount,
                provider=provider.upper()
            ),
            reply_markup=InlineKeyboardMarkup(inline_keyboard=keyboard)
        )
        
        # Track payment initiation
        analytics = AnalyticsService(session)
        await analytics.track_event(
            user_id=user.id,
            event_type='payment_initiated',
            data={
                'provider': provider,
                'amount': float(consultation.amount),
                'consultation_id': consultation_id
            }
        )
        
    except Exception as e:
        logger.error(f"Error handling payment selection: {e}")
        await callback.message.edit_text(TEXTS[user.language]['error'])

@router.callback_query(F.data.startswith("cancel_payment:"))
async def handle_payment_cancellation(
    callback: CallbackQuery,
    user: User,
    session
):
    """Handle payment cancellation"""
    try:
        consultation_id = int(callback.data.split(":")[1])
        
        # Get consultation
        consultation_service = ConsultationService(session)
        consultation = await consultation_service.get_consultation(consultation_id)
        
        if not consultation:
            await callback.answer(TEXTS[user.language]['consultation_not_found'])
            return
            
        if consultation.user_id != user.id:
            await callback.answer(TEXTS[user.language]['not_your_consultation'])
            return
            
        # Update consultation status
        consultation.status = ConsultationStatus.CANCELLED
        consultation.cancelled_at = datetime.utcnow()
        await session.commit()
        
        await callback.message.edit_text(
            TEXTS[user.language]['payment_cancelled'],
            reply_markup=get_start_keyboard(user.language)
        )
        
        # Track cancellation
        analytics = AnalyticsService(session)
        await analytics.track_event(
            user_id=user.id,
            event_type='payment_cancelled',
            data={'consultation_id': consultation_id}
        )
        
    except Exception as e:
        logger.error(f"Error handling payment cancellation: {e}")
        await callback.message.edit_text(TEXTS[user.language]['error'])

@router.post("/payment/webhook/{provider}")
async def payment_webhook(
    provider: str,
    request: Request,
    session: AsyncSession = Depends(get_session)
):
    """Handle payment webhook callbacks"""
    try:
        # Verify signature
        payment_service = PaymentService(session)
        signature_valid = await payment_service.verify_signature(
            provider,
            await request.json()
        )
        
        if not signature_valid:
            return JSONResponse(
                status_code=400,
                content={"error": "Invalid signature"}
            )
            
        # Process payment
        payment_data = await request.json()
        success = await payment_service.process_payment(
            provider,
            payment_data
        )
        
        if not success:
            return JSONResponse(
                status_code=400,
                content={"error": "Payment processing failed"}
            )
            
        return {"status": "success"}
        
    except Exception as e:
        logger.error(f"Error processing payment webhook: {e}")
        return JSONResponse(
            status_code=500,
            content={"error": "Internal server error"}
        )

def register_handlers(dp: Dispatcher):
    """Register payment handlers"""
    dp.include_router(router)

# Register callback handlers
router.callback_query.register(
    process_payment_selection,
    F.data.startswith("pay:")
)
router.callback_query.register(
    cancel_payment,
    F.data == "cancel_payment"
)
router.callback_query.register(
    process_refund_request,
    F.data.startswith("refund:")
)

```

# telegram_bot\bot\handlers\questions.py

```py
from aiogram import Router, F
from aiogram.filters import Command
from aiogram.types import Message, CallbackQuery
from aiogram.fsm.context import FSMContext
import logging

from telegram_bot.core.constants import TEXTS
from telegram_bot.models import User
from telegram_bot.services.questions import QuestionService
from telegram_bot.services.auto_answer import AutoAnswerService
from telegram_bot.bot.keyboards import (
    get_main_menu_keyboard,
    get_rating_keyboard
)
from telegram_bot.bot.states import QuestionState

logger = logging.getLogger(__name__)
router = Router(name='questions')

@router.message(F.text.in_([TEXTS['uz']['ask_question'], TEXTS['ru']['ask_question']]))
async def start_question(message: Message, state: FSMContext, user: User):
    """Start question asking flow"""
    try:
        await message.answer(
            TEXTS[user.language]['enter_question'],
            reply_markup=None
        )
        await state.set_state(QuestionState.waiting_for_question)
    except Exception as e:
        logger.error(f"Error starting question: {e}", exc_info=True)
        await message.answer(TEXTS[user.language]['error'])

@router.message(QuestionState.waiting_for_question)
async def process_question(
    message: Message,
    state: FSMContext,
    user: User,
    session
):
    """Process user's question and try to auto-answer"""
    try:
        question_text = message.text.strip()
        
        # Validate question
        if len(question_text) < 10:
            await message.answer(TEXTS[user.language]['question_too_short'])
            return
            
        if len(question_text) > 1000:
            await message.answer(TEXTS[user.language]['question_too_long'])
            return

        # Create question
        question_service = QuestionService(session)
        question = await question_service.create_question(
            user_id=user.id,
            question_text=question_text,
            language=user.language
        )

        # Try auto-answer
        auto_answer_service = AutoAnswerService(session)
        answer = await auto_answer_service.get_answer(
            question_text=question_text,
            language=user.language
        )

        if answer and answer['confidence'] >= 0.85:
            # Create auto-answer
            await question_service.create_answer(
                question_id=question.id,
                answer_text=answer['answer_text'],
                is_auto=True,
                metadata={
                    'confidence': answer['confidence'],
                    'source': answer['source']
                }
            )

            # Send answer with rating request
            await message.answer(
                f"{TEXTS[user.language]['auto_answer']}\n\n{answer['answer_text']}",
                reply_markup=get_rating_keyboard(user.language)
            )
        else:
            # Send confirmation and notify
            # If no auto-answer, send confirmation
            await message.answer(
                TEXTS[user.language]['question_received'],
                reply_markup=get_main_menu_keyboard(user.language)
            )
            
            # Notify admins about new question
            await notify_admins_new_question(question)

        # Clear state
        await state.clear()

    except Exception as e:
        logger.error(f"Error processing question: {e}", exc_info=True)
        await message.answer(TEXTS[user.language]['error'])
        await state.clear()

@router.callback_query(F.data.startswith("rate:"))
async def process_rating(
    callback: CallbackQuery,
    user: User,
    state: FSMContext,
    session
):
    """Process answer rating"""
    try:
        rating = int(callback.data.split(":")[1])
        
        # Get question from state
        data = await state.get_data()
        answer_id = data.get('current_answer_id')
        
        if not answer_id:
            await callback.answer(TEXTS[user.language]['error'])
            return

        # Save rating
        question_service = QuestionService(session)
        await question_service.rate_answer(
            answer_id=answer_id,
            rating=rating
        )

        # Thank user
        await callback.message.edit_text(
            TEXTS[user.language]['rating_saved'],
            reply_markup=get_main_menu_keyboard(user.language)
        )
        
        # Clear state
        await state.clear()

    except Exception as e:
        logger.error(f"Error processing rating: {e}", exc_info=True)
        await callback.message.edit_text(TEXTS[user.language]['error'])

@router.message(Command("my_questions"))
async def show_questions_history(
    message: Message,
    user: User,
    session
):
    """Show user's question history"""
    try:
        question_service = QuestionService(session)
        questions = await question_service.get_user_questions(user.id)

        if not questions:
            await message.answer(
                TEXTS[user.language]['no_questions'],
                reply_markup=get_main_menu_keyboard(user.language)
            )
            return

        # Format questions text
        text = TEXTS[user.language]['your_questions'] + "\n\n"
        
        for q in questions:
            text += f"❓ {q.question_text}\n"
            if q.answers:
                text += f"✅ {q.answers[0].answer_text}\n"
            text += f"📅 {q.created_at.strftime('%d.%m.%Y %H:%M')}\n\n"
            
            if len(text) > 3500:  # Split long messages
                await message.answer(text)
                text = ""

        if text:
            await message.answer(
                text, 
                reply_markup=get_main_menu_keyboard(user.language)
            )

    except Exception as e:
        logger.error(f"Error showing questions: {e}", exc_info=True)
        await message.answer(TEXTS[user.language]['error'])

async def notify_admins_new_question(question: "Question"):
    """Notify admins about new question"""
    try:
        from telegram_bot.bot import bot
        from telegram_bot.core.config import settings

        text = (
            f"📝 {TEXTS['ru']['new_question']}\n\n"
            f"👤 {question.user.full_name}"
            f"{f' (@{question.user.username})' if question.user.username else ''}\n"
            f"🌐 {question.language.upper()}\n\n"
            f"❓ {question.question_text}"
        )

        for admin_id in settings.ADMIN_IDS:
            try:
                await bot.send_message(
                    admin_id,
                    text,
                    reply_markup=get_admin_question_keyboard(question.id)
                )
            except Exception as e:
                logger.error(f"Error notifying admin {admin_id}: {e}")

    except Exception as e:
        logger.error(f"Error in admin notification: {e}", exc_info=True)

def register_handlers(dp):
    """Register question handlers"""
    dp.include_router(router)
```

# telegram_bot\bot\handlers\settings.py

```py
from aiogram import Router, F, Dispatcher
from aiogram.filters import Command
from aiogram.types import Message, CallbackQuery
from aiogram.fsm.context import FSMContext
import logging

from telegram_bot.core.constants import TEXTS
from telegram_bot.models import User
from telegram_bot.services.analytics import AnalyticsService
from telegram_bot.bot.keyboards import (
    get_start_keyboard,
    get_settings_keyboard,
    get_notification_settings_keyboard,
    get_language_keyboard
)
from telegram_bot.bot.states import SettingsState

logger = logging.getLogger(__name__)
router = Router(name='settings')

@router.message(Command("settings"))
@router.message(F.text.in_([TEXTS['uz']['settings'], TEXTS['ru']['settings']]))
async def show_settings(message: Message, user: User):
    """Show settings menu"""
    try:
        await message.answer(
            TEXTS[user.language]['settings_menu'],
            reply_markup=get_settings_keyboard(user.language)
        )
    except Exception as e:
        logger.error(f"Error showing settings: {e}", exc_info=True)
        await message.answer(TEXTS[user.language]['error'])

@router.callback_query(F.data == "settings:language")
async def change_language(callback: CallbackQuery, user: User):
    """Show language selection"""
    try:
        await callback.message.edit_text(
            "🌐 Выберите язык / Tilni tanlang",
            reply_markup=get_language_keyboard()
        )
    except Exception as e:
        logger.error(f"Error changing language: {e}", exc_info=True)
        await callback.message.edit_text(TEXTS[user.language]['error'])

@router.callback_query(F.data == "settings:notifications")
async def notification_settings(callback: CallbackQuery, user: User, session):
    """Show notification settings"""
    try:
        # Get current settings
        settings = user.settings.get('notifications', {})
        
        await callback.message.edit_text(
            TEXTS[user.language]['notification_settings'],
            reply_markup=get_notification_settings_keyboard(
                user.language,
                settings
            )
        )
        
    except Exception as e:
        logger.error(f"Error showing notification settings: {e}", exc_info=True)
        await callback.message.edit_text(TEXTS[user.language]['error'])

@router.callback_query(F.data.startswith("notifications:"))
async def toggle_notification(callback: CallbackQuery, user: User, session):
    """Toggle notification setting"""
    try:
        notification_type = callback.data.split(":")[1]
        
        # Get current settings
        settings = user.settings.get('notifications', {})
        
        # Toggle setting
        current = settings.get(notification_type, True)
        settings[notification_type] = not current
        
        # Update user settings
        if 'notifications' not in user.settings:
            user.settings['notifications'] = {}
        user.settings['notifications'] = settings
        await session.commit()
        
        # Update keyboard
        await callback.message.edit_reply_markup(
            reply_markup=get_notification_settings_keyboard(
                user.language,
                settings
            )
        )
        
        # Track setting change
        analytics = AnalyticsService(session)
        await analytics.track_event(
            user_id=user.id,
            event_type='notification_setting_changed',
            data={
                'type': notification_type,
                'enabled': settings[notification_type]
            }
        )
        
    except Exception as e:
        logger.error(f"Error toggling notification: {e}", exc_info=True)
        await callback.message.edit_text(TEXTS[user.language]['error'])

@router.callback_query(F.data == "settings:profile")
async def show_profile(callback: CallbackQuery, user: User, session):
    """Show user profile"""
    try:
        # Get user statistics
        analytics = AnalyticsService(session)
        stats = await analytics.get_user_stats(user.id)
        
        # Format profile text
        text = TEXTS[user.language]['profile_info'].format(
            full_name=user.full_name,
            username=f"@{user.username}" if user.username else "-",
            language=user.language.upper(),
            join_date=user.created_at.strftime("%d.%m.%Y"),
            questions_count=stats['questions_count'],
            consultations_count=stats['consultations_count']
        )
        
        await callback.message.edit_text(
            text,
            reply_markup=get_settings_keyboard(user.language)
        )
        
        # Track profile viewed
        await analytics.track_event(
            user_id=user.id,
            event_type='profile_viewed'
        )
        
    except Exception as e:
        logger.error(f"Error showing profile: {e}", exc_info=True)
        await callback.message.edit_text(TEXTS[user.language]['error'])

@router.callback_query(F.data == "back_to_menu")
async def back_to_menu(callback: CallbackQuery, user: User):
    """Return to main menu"""
    try:
        await callback.message.edit_text(
            TEXTS[user.language]['main_menu'],
            reply_markup=get_start_keyboard(user.language)
        )
    except Exception as e:
        logger.error(f"Error returning to menu: {e}", exc_info=True)
        await callback.message.edit_text(TEXTS[user.language]['error'])

def register_handlers(dp: Dispatcher):
    """Register settings handlers"""
    dp.include_router(router)

# Register message handlers
router.message.register(
    show_settings,
    Command("settings")
)
router.message.register(
    show_settings,
    F.text.in_([TEXTS['uz']['settings'], TEXTS['ru']['settings']])
)

# Register callback handlers
router.callback_query.register(
    change_language,
    F.data == "settings:language"
)
router.callback_query.register(
    notification_settings,
    F.data == "settings:notifications"
)
router.callback_query.register(
    toggle_notification,
    F.data.startswith("notifications:")
)
router.callback_query.register(
    show_profile,
    F.data == "settings:profile"
)
router.callback_query.register(
    back_to_menu,
    F.data == "back_to_menu"
)

```

# telegram_bot\bot\handlers\support.py

```py
from aiogram import Router, F, Dispatcher
from aiogram.filters import Command
from aiogram.types import Message, CallbackQuery
from aiogram.fsm.context import FSMContext
import logging

from telegram_bot.core.constants import TEXTS
from telegram_bot.models import User
from telegram_bot.services.analytics import AnalyticsService
from telegram_bot.bot.keyboards import (
    get_start_keyboard,
    get_support_keyboard,
    get_contact_keyboard,
    get_cancel_keyboard
)
from aiogram.types import (
    InlineKeyboardMarkup,
    InlineKeyboardButton,
    ReplyKeyboardMarkup,
    KeyboardButton,
    ReplyKeyboardRemove
)
from telegram_bot.bot.states import SupportState
from telegram_bot.core.config import settings

logger = logging.getLogger(__name__)
router = Router(name='support')

@router.message(Command("support"))
@router.message(F.text.in_([TEXTS['uz']['support'], TEXTS['ru']['support']]))
async def show_support(message: Message, user: User):
    """Show support menu"""
    try:
        await message.answer(
            TEXTS[user.language]['support_menu'],
            reply_markup=get_support_keyboard(user.language)
        )
    except Exception as e:
        logger.error(f"Error showing support: {e}", exc_info=True)
        await message.answer(TEXTS[user.language]['error'])

@router.callback_query(F.data == "support:contact")
async def start_support_chat(callback: CallbackQuery, state: FSMContext, user: User):
    """Start support chat"""
    try:
        await callback.message.edit_text(
            TEXTS[user.language]['describe_problem'],
            reply_markup=get_cancel_keyboard(user.language)
        )
        await state.set_state(SupportState.describing_issue)
        
    except Exception as e:
        logger.error(f"Error starting support chat: {e}", exc_info=True)
        await callback.message.edit_text(TEXTS[user.language]['error'])

@router.message(SupportState.describing_issue)
async def process_support_message(
    message: Message,
    state: FSMContext,
    user: User,
    session
):
    """Process support message"""
    try:
        # Save message to database and forward to support
        from telegram_bot.bot import bot
        
        # Forward to support chat/users
        support_text = (
            f"💬 Новое сообщение в поддержку\n\n"
            f"👤 {user.full_name}"
            f"{f' (@{user.username})' if user.username else ''}\n"
            f"🆔 {user.id}\n"
            f"🌐 {user.language.upper()}\n\n"
            f"📝 {message.text}"
        )
        
        # Send to support users
        sent = False
        for admin_id in settings.ADMIN_IDS:
            try:
                await bot.send_message(
                    admin_id,
                    support_text,
                    reply_markup=get_admin_support_keyboard(user.id)
                )
                sent = True
            except Exception as e:
                logger.error(f"Error forwarding to admin {admin_id}: {e}")
        
        if sent:
            await message.answer(
                TEXTS[user.language]['support_message_sent'],
                reply_markup=get_start_keyboard(user.language)
            )
        else:
            await message.answer(
                TEXTS[user.language]['support_unavailable'],
                reply_markup=get_start_keyboard(user.language)
            )
        
        # Track support request
        analytics = AnalyticsService(session)
        await analytics.track_event(
            user_id=user.id,
            event_type='support_message_sent',
            data={'message': message.text}
        )
        
        # Clear state
        await state.clear()
        
    except Exception as e:
        logger.error(f"Error processing support message: {e}", exc_info=True)
        await message.answer(TEXTS[user.language]['error'])
        await state.clear()

@router.callback_query(F.data == "support:faq")
async def show_faq(callback: CallbackQuery, user: User, session):
    """Show FAQ section"""
    try:
        from telegram_bot.services.questions import QuestionService
        
        # Get FAQ questions
        question_service = QuestionService(session)
        faq_questions = await question_service.get_faq_questions(user.language)
        
        if not faq_questions:
            await callback.message.edit_text(
                TEXTS[user.language]['no_faq'],
                reply_markup=get_support_keyboard(user.language)
            )
            return
        
        # Format FAQ text
        text = TEXTS[user.language]['faq_title'] + "\n\n"
        
        for i, question in enumerate(faq_questions, 1):
            text += f"{i}. ❓ {question.question_text}\n"
            if question.answers:
                text += f"✅ {question.answers[0].answer_text}\n"
            text += "\n"
        
        await callback.message.edit_text(
            text,
            reply_markup=get_support_keyboard(user.language)
        )
        
        # Track FAQ viewed
        analytics = AnalyticsService(session)
        await analytics.track_event(
            user_id=user.id,
            event_type='faq_viewed'
        )
        
    except Exception as e:
        logger.error(f"Error showing FAQ: {e}", exc_info=True)
        await callback.message.edit_text(TEXTS[user.language]['error'])

@router.callback_query(F.data == "support:report")
async def start_report(callback: CallbackQuery, state: FSMContext, user: User):
    """Start problem report"""
    try:
        await callback.message.edit_text(
            TEXTS[user.language]['describe_problem'],
            reply_markup=get_cancel_keyboard(user.language)
        )
        await state.set_state(SupportState.reporting_problem)
        
    except Exception as e:
        logger.error(f"Error starting report: {e}", exc_info=True)
        await callback.message.edit_text(TEXTS[user.language]['error'])

@router.message(SupportState.reporting_problem)
async def process_report(
    message: Message,
    state: FSMContext,
    user: User,
    session
):
    """Process problem report"""
    try:
        from telegram_bot.bot import bot
        
        # Format report message
        report_text = (
            f"⚠️ Новый репорт о проблеме\n\n"
            f"👤 {user.full_name}"
            f"{f' (@{user.username})' if user.username else ''}\n"
            f"🆔 {user.id}\n"
            f"🌐 {user.language.upper()}\n\n"
            f"📝 {message.text}"
        )
        
        # Send to admins
        sent = False
        for admin_id in settings.ADMIN_IDS:
            try:
                await bot.send_message(
                    admin_id,
                    report_text,
                    reply_markup=get_admin_report_keyboard(user.id)
                )
                sent = True
            except Exception as e:
                logger.error(f"Error sending report to admin {admin_id}: {e}")
        
        if sent:
            await message.answer(
                TEXTS[user.language]['report_sent'],
                reply_markup=get_start_keyboard(user.language)
            )
        else:
            await message.answer(
                TEXTS[user.language]['report_error'],
                reply_markup=get_start_keyboard(user.language)
            )
        
        # Track report
        analytics = AnalyticsService(session)
        await analytics.track_event(
            user_id=user.id,
            event_type='problem_reported',
            data={'message': message.text}
        )
        
        # Clear state
        await state.clear()
        
    except Exception as e:
        logger.error(f"Error processing report: {e}", exc_info=True)
        await message.answer(TEXTS[user.language]['error'])
        await state.clear()

def get_admin_support_keyboard(user_id: int):
    """Generate keyboard for admin support response"""
    return InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(
                text="✍️ Ответить",
                callback_data=f"admin:reply:{user_id}"
            )
        ],
        [
            InlineKeyboardButton(
                text="❌ Закрыть",
                callback_data=f"admin:close_support:{user_id}"
            )
        ]
    ])

def get_admin_report_keyboard(user_id: int):
    """Generate keyboard for admin report response"""
    return InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(
                text="✅ Принято",
                callback_data=f"admin:accept_report:{user_id}"
            )
        ],
        [
            InlineKeyboardButton(
                text="❌ Отклонить",
                callback_data=f"admin:reject_report:{user_id}"
            )
        ]
    ])

def register_handlers(dp: Dispatcher):
    """Register support handlers"""
    dp.include_router(router)

# Register message handlers
router.message.register(
    show_support,
    Command("support")
)
router.message.register(
    show_support,
    F.text.in_([TEXTS['uz']['support'], TEXTS['ru']['support']])
)
router.message.register(
    process_support_message,
    SupportState.describing_issue
)
router.message.register(
    process_report,
    SupportState.reporting_problem
)

# Register callback handlers
router.callback_query.register(
    start_support_chat,
    F.data == "support:contact"
)
router.callback_query.register(
    show_faq,
    F.data == "support:faq"
)
router.callback_query.register(
    start_report,
    F.data == "support:report"
)

```

# telegram_bot\bot\handlers\users.py

```py
from aiogram import Router, F, Dispatcher
from aiogram.filters import Command, CommandStart
from aiogram.types import Message, CallbackQuery
from aiogram.fsm.context import FSMContext
import logging

from telegram_bot.core.constants import TEXTS
from telegram_bot.models import User
from telegram_bot.services.analytics import AnalyticsService
from telegram_bot.bot.keyboards import (
    get_start_keyboard,
    get_language_keyboard,
    get_settings_keyboard
)
from telegram_bot.bot.states import UserState

logger = logging.getLogger(__name__)
router = Router(name='users')

@router.message(CommandStart())
async def cmd_start(message: Message, user: User, state: FSMContext, session):
    """Handle /start command"""
    try:
        # Clear any existing state
        await state.clear()
        
        # Track analytics
        analytics = AnalyticsService(session)
        await analytics.track_event(
            user_id=user.id,
            event_type='bot_start',
            data={
                'source': message.get_args() or 'direct',
                'platform': message.from_user.language_code
            }
        )
        
        # Check if language is set
        if not user.language:
            await message.answer(
                "🌐 Выберите язык / Tilni tanlang",
                reply_markup=get_language_keyboard()
            )
            await state.set_state(UserState.selecting_language)
        else:
            await message.answer(
                TEXTS[user.language]['welcome_back'],
                reply_markup=get_start_keyboard(user.language)
            )
        
    except Exception as e:
        logger.error(f"Error in start command: {e}", exc_info=True)
        await message.answer("An error occurred. Please try again.")

@router.callback_query(F.data.startswith("language:"))
async def process_language_selection(
    callback: CallbackQuery,
    user: User,
    state: FSMContext,
    session
):
    """Handle language selection"""
    try:
        language = callback.data.split(":")[1]
        
        # Update user language
        user.language = language
        await session.commit()
        
        # Send welcome message
        await callback.message.edit_text(
            TEXTS[language]['welcome'],
            reply_markup=get_start_keyboard(language)
        )
        
        # Clear state
        await state.clear()
        
        # Track language selection
        analytics = AnalyticsService(session)
        await analytics.track_event(
            user_id=user.id,
            event_type='language_selected',
            data={'language': language}
        )
        
    except Exception as e:
        logger.error(f"Error selecting language: {e}", exc_info=True)
        await callback.message.edit_text("An error occurred. Please try again.")

@router.message(Command("help"))
async def cmd_help(message: Message, user: User):
    """Handle /help command"""
    try:
        await message.answer(
            TEXTS[user.language]['help_message'],
            reply_markup=get_start_keyboard(user.language)
        )
    except Exception as e:
        logger.error(f"Error in help command: {e}", exc_info=True)
        await message.answer(TEXTS[user.language]['error'])

@router.message(Command("settings"))
async def cmd_settings(message: Message, user: User):
    """Handle /settings command"""
    try:
        await message.answer(
            TEXTS[user.language]['settings_menu'],
            reply_markup=get_settings_keyboard(user.language)
        )
    except Exception as e:
        logger.error(f"Error in settings command: {e}", exc_info=True)
        await message.answer(TEXTS[user.language]['error'])

@router.message(Command("profile"))
async def cmd_profile(message: Message, user: User, session):
    """Handle /profile command"""
    try:
        # Get user statistics
        analytics = AnalyticsService(session)
        stats = await analytics.get_user_stats(user.id)
        
        # Format profile text
        text = TEXTS[user.language]['profile_info'].format(
            full_name=user.full_name,
            username=f"@{user.username}" if user.username else "-",
            language=user.language.upper(),
            join_date=user.created_at.strftime("%d.%m.%Y"),
            questions_count=stats['questions_count'],
            consultations_count=stats['consultations_count']
        )
        
        await message.answer(
            text,
            reply_markup=get_start_keyboard(user.language)
        )
        
    except Exception as e:
        logger.error(f"Error in profile command: {e}", exc_info=True)
        await message.answer(TEXTS[user.language]['error'])

@router.message(Command("cancel"))
async def cmd_cancel(message: Message, state: FSMContext, user: User):
    """Handle /cancel command"""
    try:
        current_state = await state.get_state()
        if current_state is None:
            await message.answer(
                TEXTS[user.language]['nothing_to_cancel'],
                reply_markup=get_start_keyboard(user.language)
            )
            return
            
        await state.clear()
        await message.answer(
            TEXTS[user.language]['cancelled'],
            reply_markup=get_start_keyboard(user.language)
        )
        
    except Exception as e:
        logger.error(f"Error in cancel command: {e}", exc_info=True)
        await message.answer(TEXTS[user.language]['error'])

def register_handlers(dp: Dispatcher):
    """Register user handlers"""
    dp.include_router(router)

```

# telegram_bot\bot\keyboards.py

```py
from aiogram.types import (
    InlineKeyboardMarkup,
    InlineKeyboardButton,
    ReplyKeyboardMarkup,
    KeyboardButton,
    ReplyKeyboardRemove
)
from typing import List, Optional, Dict
from datetime import datetime
from telegram_bot.models import FAQ
from telegram_bot.core.constants import TEXTS
from telegram_bot.models import Question, Consultation

from aiogram.types import (
    InlineKeyboardMarkup,
    InlineKeyboardButton,
    ReplyKeyboardMarkup,
    KeyboardButton,
    ReplyKeyboardRemove
)
from typing import List, Optional
from telegram_bot.core.constants import TEXTS

def get_language_keyboard() -> InlineKeyboardMarkup:
    """Language selection keyboard"""
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(text="🇺🇿 O'zbek", callback_data="language:uz"),
                InlineKeyboardButton(text="🇷🇺 Русский", callback_data="language:ru")
            ]
        ]
    )

def get_main_menu_keyboard(language: str) -> ReplyKeyboardMarkup:
    """Main menu keyboard"""
    return ReplyKeyboardMarkup(
        keyboard=[
            [
                KeyboardButton(text=TEXTS[language]['ask_question']),
                KeyboardButton(text=TEXTS[language]['consultation'])
            ],
            [
                KeyboardButton(text=TEXTS[language]['my_questions']),
                KeyboardButton(text=TEXTS[language]['faq'])
            ],
            [
                KeyboardButton(text=TEXTS[language]['support']),
                KeyboardButton(text=TEXTS[language]['settings'])
            ]
        ],
        resize_keyboard=True
    )

def get_contact_keyboard(language: str) -> ReplyKeyboardMarkup:
    """Contact sharing keyboard"""
    return ReplyKeyboardMarkup(
        keyboard=[
            [
                KeyboardButton(
                    text=TEXTS[language]['share_contact'],
                    request_contact=True
                )
            ],
            [
                KeyboardButton(text=TEXTS[language]['cancel'])
            ]
        ],
        resize_keyboard=True,
        one_time_keyboard=True
    )

def get_consultation_type_keyboard(language: str) -> InlineKeyboardMarkup:
    """Consultation type selection keyboard"""
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text=TEXTS[language]['online_consultation'],
                    callback_data="consultation_type:online"
                )
            ],
            [
                InlineKeyboardButton(
                    text=TEXTS[language]['office_consultation'],
                    callback_data="consultation_type:office"
                )
            ],
            [
                InlineKeyboardButton(
                    text=TEXTS[language]['cancel'],
                    callback_data="cancel"
                )
            ]
        ]
    )

def get_payment_methods_keyboard(
    language: str,
    amount: float,
    consultation_id: int
) -> InlineKeyboardMarkup:
    """Payment methods keyboard"""
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text="Click",
                    callback_data=f"pay:click:{consultation_id}:{amount}"
                ),
                InlineKeyboardButton(
                    text="Payme",
                    callback_data=f"pay:payme:{consultation_id}:{amount}"
                )
            ],
            [
                InlineKeyboardButton(
                    text="Uzum",
                    callback_data=f"pay:uzum:{consultation_id}:{amount}"
                )
            ],
            [
                InlineKeyboardButton(
                    text=TEXTS[language]['cancel'],
                    callback_data="cancel"
                )
            ]
        ]
    )

def get_faq_keyboard(language: str) -> InlineKeyboardMarkup:
    """FAQ categories keyboard"""
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text=TEXTS[language]['general_questions'],
                    callback_data="faq:general"
                )
            ],
            [
                InlineKeyboardButton(
                    text=TEXTS[language]['consultation_questions'],
                    callback_data="faq:consultation"
                )
            ],
            [
                InlineKeyboardButton(
                    text=TEXTS[language]['payment_questions'],
                    callback_data="faq:payment"
                )
            ],
            [
                InlineKeyboardButton(
                    text=TEXTS[language]['back'],
                    callback_data="back_to_menu"
                )
            ]
        ]
    )

def get_settings_keyboard(language: str) -> InlineKeyboardMarkup:
    """Settings keyboard"""
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text=TEXTS[language]['change_language'],
                    callback_data="settings:language"
                )
            ],
            [
                InlineKeyboardButton(
                    text=TEXTS[language]['notifications'],
                    callback_data="settings:notifications"
                )
            ],
            [
                InlineKeyboardButton(
                    text=TEXTS[language]['profile'],
                    callback_data="settings:profile"
                )
            ],
            [
                InlineKeyboardButton(
                    text=TEXTS[language]['back'],
                    callback_data="back_to_menu"
                )
            ]
        ]
    )

def get_rating_keyboard(language: str) -> InlineKeyboardMarkup:
    """Rating keyboard"""
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(text="⭐", callback_data="rate:1"),
                InlineKeyboardButton(text="⭐⭐", callback_data="rate:2"),
                InlineKeyboardButton(text="⭐⭐⭐", callback_data="rate:3"),
                InlineKeyboardButton(text="⭐⭐⭐⭐", callback_data="rate:4"),
                InlineKeyboardButton(text="⭐⭐⭐⭐⭐", callback_data="rate:5")
            ],
            [
                InlineKeyboardButton(
                    text=TEXTS[language]['skip'],
                    callback_data="rate:skip"
                )
            ]
        ]
    )

def get_support_keyboard(language: str) -> InlineKeyboardMarkup:
    """Support keyboard"""
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text=TEXTS[language]['contact_support'],
                    callback_data="support:contact"
                )
            ],
            [
                InlineKeyboardButton(
                    text=TEXTS[language]['faq'],
                    callback_data="support:faq"
                )
            ],
            [
                InlineKeyboardButton(
                    text=TEXTS[language]['report_problem'],
                    callback_data="support:report"
                )
            ],
            [
                InlineKeyboardButton(
                    text=TEXTS[language]['back'],
                    callback_data="back_to_menu"
                )
            ]
        ]
    )

def get_start_keyboard(language: str) -> ReplyKeyboardMarkup:
    """Main menu keyboard"""
    keyboard = [
        [
            KeyboardButton(text=TEXTS[language]['ask_question']),
            KeyboardButton(text=TEXTS[language]['consultation'])
        ],
        [
            KeyboardButton(text=TEXTS[language]['my_questions']),
            KeyboardButton(text=TEXTS[language]['faq'])
        ],
        [
            KeyboardButton(text=TEXTS[language]['support']),
            KeyboardButton(text=TEXTS[language]['settings'])
        ]
    ]
    return ReplyKeyboardMarkup(
        keyboard=keyboard,
        resize_keyboard=True,
        one_time_keyboard=False
    )

def get_cancel_keyboard(language: str) -> ReplyKeyboardMarkup:
    """Cancel button keyboard"""
    keyboard = [[KeyboardButton(text=TEXTS[language]['cancel'])]]
    return ReplyKeyboardMarkup(
        keyboard=keyboard,
        resize_keyboard=True,
        one_time_keyboard=True
    )

def get_question_category_keyboard(language: str) -> InlineKeyboardMarkup:
    """Question category selection keyboard"""
    categories = [
        ('family', '👨‍👩‍👧‍👦'),
        ('property', '🏠'),
        ('business', '💼'),
        ('criminal', '⚖️'),
        ('other', '❓')
    ]
    
    keyboard = []
    for category, emoji in categories:
        keyboard.append([
            InlineKeyboardButton(
                text=f"{emoji} {TEXTS[language][f'category_{category}']}",
                callback_data=f"category:{category}"
            )
        ])
    
    keyboard.append([
        InlineKeyboardButton(
            text=TEXTS[language]['cancel'],
            callback_data="cancel"
        )
    ])
    
    return InlineKeyboardMarkup(inline_keyboard=keyboard)

def get_similar_questions_keyboard(
    questions: List[Question],
    language: str
) -> InlineKeyboardMarkup:
    """Similar questions keyboard"""
    keyboard = []
    
    # Add question buttons
    for i, question in enumerate(questions, 1):
        keyboard.append([
            InlineKeyboardButton(
                text=f"{i}. {question.question_text[:50]}...",
                callback_data=f"similar:{question.id}"
            )
        ])
    
    # Add action buttons
    keyboard.extend([
        [
            InlineKeyboardButton(
                text=TEXTS[language]['ask_anyway'],
                callback_data="ask_anyway"
            )
        ],
        [
            InlineKeyboardButton(
                text=TEXTS[language]['cancel'],
                callback_data="cancel_question"
            )
        ]
    ])
    
    return InlineKeyboardMarkup(inline_keyboard=keyboard)


def get_consultation_time_keyboard(
    language: str,
    available_times: List[datetime]
) -> InlineKeyboardMarkup:
    """Consultation time selection keyboard"""
    keyboard = []
    
    # Group times by date
    times_by_date = {}
    for time in available_times:
        date_str = time.strftime('%Y-%m-%d')
        if date_str not in times_by_date:
            times_by_date[date_str] = []
        times_by_date[date_str].append(time)
    
    # Create keyboard with dates and times
    for date_str, times in times_by_date.items():
        # Add date header
        keyboard.append([
            InlineKeyboardButton(
                text=datetime.strptime(date_str, '%Y-%m-%d').strftime('%d.%m.%Y'),
                callback_data=f"date_header:{date_str}"
            )
        ])
        
        # Add time slots in rows of 3
        time_row = []
        for time in times:
            time_row.append(
                InlineKeyboardButton(
                    text=time.strftime('%H:%M'),
                    callback_data=f"time:{time.isoformat()}"
                )
            )
            if len(time_row) == 3:
                keyboard.append(time_row)
                time_row = []
        if time_row:
            keyboard.append(time_row)
    
    # Add cancel button
    keyboard.append([
        InlineKeyboardButton(
            text=TEXTS[language]['cancel'],
            callback_data="cancel_consultation"
        )
    ])
    
    return InlineKeyboardMarkup(inline_keyboard=keyboard)

def get_confirm_cancel_keyboard(language: str) -> InlineKeyboardMarkup:
    """Confirm/cancel keyboard"""
    keyboard = [
        [
            InlineKeyboardButton(
                text=TEXTS[language]['confirm'],
                callback_data="confirm"
            ),
            InlineKeyboardButton(
                text=TEXTS[language]['cancel'],
                callback_data="cancel"
            )
        ]
    ]
    return InlineKeyboardMarkup(inline_keyboard=keyboard)


def get_notification_settings_keyboard(
    language: str,
    settings: Dict[str, bool]
) -> InlineKeyboardMarkup:
    """Notification settings keyboard"""
    keyboard = []
    
    # Add notification toggles
    notification_types = [
        ('questions', '❓'),
        ('consultations', '📅'),
        ('news', '📢'),
        ('support', '🆘')
    ]
    
    for type_key, emoji in notification_types:
        status = settings.get(type_key, True)
        keyboard.append([
            InlineKeyboardButton(
                text=f"{emoji} {TEXTS[language][f'notify_{type_key}']} {'✅' if status else '❌'}",
                callback_data=f"notifications:{type_key}"
            )
        ])
    
    # Add back button
    keyboard.append([
        InlineKeyboardButton(
            text=TEXTS[language]['back'],
            callback_data="settings:main"
        )
    ])
    
    return InlineKeyboardMarkup(inline_keyboard=keyboard)

def get_admin_menu_keyboard() -> InlineKeyboardMarkup:
    """Admin main menu keyboard"""
    keyboard = [
        [
            InlineKeyboardButton(
                text="📊 Statistics",
                callback_data="admin:stats"
            )
        ],
        [
            InlineKeyboardButton(
                text="❓ Questions",
                callback_data="admin:questions"
            ),
            InlineKeyboardButton(
                text="📅 Consultations",
                callback_data="admin:consultations"
            )
        ],
        [
            InlineKeyboardButton(
                text="👥 Users",
                callback_data="admin:users"
            ),
            InlineKeyboardButton(
                text="📢 Broadcast",
                callback_data="admin:broadcast"
            )
        ],
        [
            InlineKeyboardButton(
                text="⚙️ Settings",
                callback_data="admin:settings"
            )
        ]
    ]
    return InlineKeyboardMarkup(inline_keyboard=keyboard)

def get_rating_keyboard(language: str) -> InlineKeyboardMarkup:
    """Rating keyboard with stars"""
    keyboard = []
    
    # Add star ratings
    for i in range(1, 6):
        keyboard.append([
            InlineKeyboardButton(
                text="⭐" * i,
                callback_data=f"rate:{i}"
            )
        ])
    
    # Add skip button
    keyboard.append([
        InlineKeyboardButton(
            text=TEXTS[language]['skip'],
            callback_data="rate:skip"
        )
    ])
    
    return InlineKeyboardMarkup(inline_keyboard=keyboard)

def get_consultation_actions_keyboard(
    consultation: Consultation,
    language: str
) -> InlineKeyboardMarkup:
    """Consultation actions keyboard based on status"""
    keyboard = []
    
    if consultation.status == 'PENDING':
        keyboard.extend([
            [
                InlineKeyboardButton(
                    text=TEXTS[language]['pay_now'],
                    callback_data=f"consultation:pay:{consultation.id}"
                )
            ],
            [
                InlineKeyboardButton(
                    text=TEXTS[language]['cancel_consultation'],
                    callback_data=f"consultation:cancel:{consultation.id}"
                )
            ]
        ])
    elif consultation.status == 'PAID':
        keyboard.append([
            InlineKeyboardButton(
                text=TEXTS[language]['choose_time'],
                callback_data=f"consultation:schedule:{consultation.id}"
            )
        ])
    elif consultation.status == 'SCHEDULED':
        keyboard.extend([
            [
                InlineKeyboardButton(
                    text=TEXTS[language]['reschedule'],
                    callback_data=f"consultation:reschedule:{consultation.id}"
                )
            ],
            [
                InlineKeyboardButton(
                    text=TEXTS[language]['cancel_consultation'],
                    callback_data=f"consultation:cancel:{consultation.id}"
                )
            ]
        ])
    elif consultation.status == 'COMPLETED':
        if not consultation.feedback:
            keyboard.append([
                InlineKeyboardButton(
                    text=TEXTS[language]['leave_feedback'],
                    callback_data=f"consultation:feedback:{consultation.id}"
                )
            ])
    
    return InlineKeyboardMarkup(inline_keyboard=keyboard)

def get_admin_question_keyboard(question_id: int) -> InlineKeyboardMarkup:
    """Admin question management keyboard"""
    keyboard = [
        [
            InlineKeyboardButton(
                text="✍️ Answer",
                callback_data=f"admin:answer:{question_id}"
            )
        ],
        [
            InlineKeyboardButton(
                text="🔄 Auto Answer",
                callback_data=f"admin:auto_answer:{question_id}"
            )
        ],
        [
            InlineKeyboardButton(
                text="❌ Delete",
                callback_data=f"admin:delete_question:{question_id}"
            )
        ],
        [
            InlineKeyboardButton(
                text="◀️ Back",
                callback_data="admin:questions"
            )
        ]
    ]
    return InlineKeyboardMarkup(inline_keyboard=keyboard)

def get_admin_user_keyboard(user_id: int) -> InlineKeyboardMarkup:
    """Admin user management keyboard"""
    keyboard = [
        [
            InlineKeyboardButton(
                text="📝 Edit Roles",
                callback_data=f"admin:edit_roles:{user_id}"
            ),
            InlineKeyboardButton(
                text="🚫 Block/Unblock",
                callback_data=f"admin:toggle_block:{user_id}"
            )
        ],
        [
            InlineKeyboardButton(
                text="📨 Send Message",
                callback_data=f"admin:message_user:{user_id}"
            ),
            InlineKeyboardButton(
                text="📊 Statistics",
                callback_data=f"admin:user_stats:{user_id}"
            )
        ],
        [
            InlineKeyboardButton(
                text="◀️ Back",
                callback_data="admin:users"
            )
        ]
    ]
    return InlineKeyboardMarkup(inline_keyboard=keyboard)

def get_admin_consultation_keyboard(consultation_id: int) -> InlineKeyboardMarkup:
    """Admin consultation management keyboard"""
    keyboard = [
        [
            InlineKeyboardButton(
                text="✅ Approve",
                callback_data=f"admin:approve_consultation:{consultation_id}"
            )
        ],
        [
            InlineKeyboardButton(
                text="📅 Schedule",
                callback_data=f"admin:schedule_consultation:{consultation_id}"
            )
        ],
        [
            InlineKeyboardButton(
                text="❌ Reject",
                callback_data=f"admin:reject_consultation:{consultation_id}"
            )
        ],
        [
            InlineKeyboardButton(
                text="💬 Send Message",
                callback_data=f"admin:message_consultation:{consultation_id}"
            )
        ],
        [
            InlineKeyboardButton(
                text="◀️ Back",
                callback_data="admin:consultations"
            )
        ]
    ]
    return InlineKeyboardMarkup(inline_keyboard=keyboard)

def get_admin_broadcast_keyboard() -> InlineKeyboardMarkup:
    """Admin broadcast targeting keyboard"""
    keyboard = [
        [
            InlineKeyboardButton(
                text="👥 All Users",
                callback_data="broadcast:all"
            )
        ],
        [
            InlineKeyboardButton(
                text="✅ Active Users",
                callback_data="broadcast:active"
            )
        ],
        [
            InlineKeyboardButton(
                text="🇺🇿 Uzbek",
                callback_data="broadcast:uz"
            ),
            InlineKeyboardButton(
                text="🇷🇺 Russian",
                callback_data="broadcast:ru"
            )
        ],
        [
            InlineKeyboardButton(
                text="❌ Cancel",
                callback_data="admin:menu"
            )
        ]
    ]
    return InlineKeyboardMarkup(inline_keyboard=keyboard)

def get_support_keyboard(language: str) -> InlineKeyboardMarkup:
    """Support menu keyboard"""
    keyboard = [
        [
            InlineKeyboardButton(
                text=TEXTS[language]['contact_support'],
                callback_data="support:contact"
            )
        ],
        [
            InlineKeyboardButton(
                text=TEXTS[language]['faq'],
                callback_data="support:faq"
            )
        ],
        [
            InlineKeyboardButton(
                text=TEXTS[language]['report_problem'],
                callback_data="support:report"
            )
        ],
        [
            InlineKeyboardButton(
                text=TEXTS[language]['back'],
                callback_data="back_to_menu"
            )
        ]
    ]
    return InlineKeyboardMarkup(inline_keyboard=keyboard)

def get_consultation_calendar_keyboard(
    year: int,
    month: int,
    language: str
) -> InlineKeyboardMarkup:
    """Generate calendar keyboard for consultation scheduling"""
    import calendar
    
    keyboard = []
    
    # Add month and year header
    month_names = {
        'uz': ['Yanvar', 'Fevral', 'Mart', 'Aprel', 'May', 'Iyun', 
               'Iyul', 'Avgust', 'Sentabr', 'Oktabr', 'Noyabr', 'Dekabr'],
        'ru': ['Январь', 'Февраль', 'Март', 'Апрель', 'Май', 'Июнь',
               'Июль', 'Август', 'Сентябрь', 'Октябрь', 'Ноябрь', 'Декабрь']
    }
    
    keyboard.append([
        InlineKeyboardButton(
            text=f"{month_names[language][month-1]} {year}",
            callback_data="ignore"
        )
    ])
    
    # Add weekday headers
    weekdays = {
        'uz': ['Du', 'Se', 'Ch', 'Pa', 'Ju', 'Sh', 'Ya'],
        'ru': ['Пн', 'Вт', 'Ср', 'Чт', 'Пт', 'Сб', 'Вс']
    }
    keyboard.append([
        InlineKeyboardButton(text=day, callback_data="ignore")
        for day in weekdays[language]
    ])
    
    # Add calendar days
    cal = calendar.monthcalendar(year, month)
    for week in cal:
        row = []
        for day in week:
            if day == 0:
                row.append(InlineKeyboardButton(
                    text=" ",
                    callback_data="ignore"
                ))
            else:
                row.append(InlineKeyboardButton(
                    text=str(day),
                    callback_data=f"date:{year}-{month:02d}-{day:02d}"
                ))
        keyboard.append(row)
    
    # Add navigation buttons
    nav_buttons = []
    
    # Previous month
    if month == 1:
        prev_year = year - 1
        prev_month = 12
    else:
        prev_year = year
        prev_month = month - 1
        
    nav_buttons.append(InlineKeyboardButton(
        text="◀️",
        callback_data=f"calendar:{prev_year}:{prev_month}"
    ))
    
    # Next month
    if month == 12:
        next_year = year + 1
        next_month = 1
    else:
        next_year = year
        next_month = month + 1
        
    nav_buttons.append(InlineKeyboardButton(
        text="▶️",
        callback_data=f"calendar:{next_year}:{next_month}"
    ))
    
    keyboard.append(nav_buttons)
    
    # Add cancel button
    keyboard.append([
        InlineKeyboardButton(
            text=TEXTS[language]['cancel'],
            callback_data="cancel"
        )
    ])
    
    return InlineKeyboardMarkup(inline_keyboard=keyboard)

def get_consultation_time_keyboard(
    date: str,
    language: str,
    booked_times: List[str] = None
) -> InlineKeyboardMarkup:
    """Generate time selection keyboard for consultation"""
    keyboard = []
    booked_times = booked_times or []
    
    # Available time slots (9:00 - 18:00)
    time_slots = []
    for hour in range(9, 18):
        for minute in [0, 30]:
            time_slots.append(f"{hour:02d}:{minute:02d}")
    
    # Add time buttons in rows of 3
    row = []
    for time in time_slots:
        if len(row) == 3:
            keyboard.append(row)
            row = []
            
        is_booked = f"{date} {time}" in booked_times
        row.append(InlineKeyboardButton(
            text=f"❌ {time}" if is_booked else time,
            callback_data=f"time:{date}:{time}" if not is_booked else "ignore"
        ))
        
    if row:
        keyboard.append(row)
    
    # Add back and cancel buttons
    keyboard.append([
        InlineKeyboardButton(
            text=TEXTS[language]['back'],
            callback_data=f"calendar_back:{date}"
        ),
        InlineKeyboardButton(
            text=TEXTS[language]['cancel'],
            callback_data="cancel"
        )
    ])
    
    return InlineKeyboardMarkup(inline_keyboard=keyboard)




def get_faq_categories_keyboard(language: str) -> InlineKeyboardMarkup:
    """Generate FAQ categories keyboard"""
    categories = [
        ('general', '📝'),
        ('payment', '💳'),
        ('consultation', '👨‍💼'),
        ('technical', '⚙️')
    ]
    
    keyboard = []
    for category, emoji in categories:
        keyboard.append([
            InlineKeyboardButton(
                text=f"{emoji} {TEXTS[language][f'category_{category}']}",
                callback_data=f"faq_cat:{category}"
            )
        ])
    
    # Add back button
    keyboard.append([
        InlineKeyboardButton(
            text=TEXTS[language]['back'],
            callback_data="start"
        )
    ])
    
    return InlineKeyboardMarkup(inline_keyboard=keyboard)

def get_faq_list_keyboard(
    faqs: List[FAQ],
    language: str
) -> InlineKeyboardMarkup:
    """Generate FAQ list keyboard"""
    keyboard = []
    
    for faq in faqs:
        # Truncate question if too long
        question = faq.question[:50] + "..." if len(faq.question) > 50 else faq.question
        
        keyboard.append([
            InlineKeyboardButton(
                text=question,
                callback_data=f"faq:{faq.id}"
            )
        ])
    
    # Add back button
    keyboard.append([
        InlineKeyboardButton(
            text=TEXTS[language]['back'],
            callback_data="faq_categories"
        )
    ])
    
    return InlineKeyboardMarkup(inline_keyboard=keyboard)

def get_faq_rating_keyboard(faq_id: int) -> InlineKeyboardMarkup:
    """Generate FAQ rating keyboard"""
    keyboard = [
        [
            InlineKeyboardButton(
                text="👍 Helpful",
                callback_data=f"faq_rate:{faq_id}:1"
            ),
            InlineKeyboardButton(
                text="👎 Not helpful",
                callback_data=f"faq_rate:{faq_id}:0"
            )
        ],
        [
            InlineKeyboardButton(
                text="◀️ Back to categories",
                callback_data="faq_categories"
            )
        ]
    ]
    
    return InlineKeyboardMarkup(inline_keyboard=keyboard)


def get_faq_feedback_keyboard(language: str) -> InlineKeyboardMarkup:
    """Generate FAQ feedback keyboard"""
    keyboard = [
        [
            InlineKeyboardButton(
                text=TEXTS[language]['skip_feedback'],
                callback_data="skip_faq_feedback"
            )
        ],
        [
            InlineKeyboardButton(
                text=TEXTS[language]['back_to_categories'],
                callback_data="faq_categories"
            )
        ]
    ]
    return InlineKeyboardMarkup(inline_keyboard=keyboard)

def get_faq_navigation_keyboard(
    language: str,
    category_id: int = None,
    show_helpful: bool = False,
    faq_id: int = None
) -> InlineKeyboardMarkup:
    """Generate FAQ navigation keyboard"""
    keyboard = []
    
    if show_helpful and faq_id:
        # Add helpful/not helpful buttons
        keyboard.append([
            InlineKeyboardButton(
                text=TEXTS[language]['helpful'],
                callback_data=f"faq_helpful:{faq_id}:1"
            ),
            InlineKeyboardButton(
                text=TEXTS[language]['not_helpful'],
                callback_data=f"faq_helpful:{faq_id}:0"
            )
        ])
    
    # Add navigation buttons
    nav_row = []
    
    if category_id:
        nav_row.append(
            InlineKeyboardButton(
                text=TEXTS[language]['back_to_category'],
                callback_data=f"faq_cat:{category_id}"
            )
        )
    
    nav_row.append(
        InlineKeyboardButton(
            text=TEXTS[language]['back_to_categories'],
            callback_data="faq_categories"
        )
    )
    
    keyboard.append(nav_row)
    
    # Add search button
    keyboard.append([
        InlineKeyboardButton(
            text=TEXTS[language]['search_faq'],
            callback_data="faq_search"
        )
    ])
    
    return InlineKeyboardMarkup(inline_keyboard=keyboard)

def get_suggested_faqs_keyboard(
    faqs: List[FAQ],
    language: str,
    category_id: int = None
) -> InlineKeyboardMarkup:
    """Generate keyboard for suggested FAQs"""
    keyboard = []
    
    for faq in faqs:
        keyboard.append([
            InlineKeyboardButton(
                text=f"📌 {faq.question[:50]}...",
                callback_data=f"faq:{faq.id}"
            )
        ])
    
    # Add navigation
    nav_row = []
    
    if category_id:
        nav_row.append(
            InlineKeyboardButton(
                text=TEXTS[language]['back_to_category'],
                callback_data=f"faq_cat:{category_id}"
            )
        )
    
    nav_row.append(
        InlineKeyboardButton(
            text=TEXTS[language]['back_to_categories'],
            callback_data="faq_categories"
        )
    )
    
    keyboard.append(nav_row)
    
    return InlineKeyboardMarkup(inline_keyboard=keyboard)

def get_pagination_keyboard(
    current_page: int,
    total_pages: int,
    callback_prefix: str
) -> List[List[InlineKeyboardButton]]:
    """Generate pagination buttons"""
    keyboard = []
    
    # Add navigation buttons
    nav_buttons = []
    
    if current_page > 1:
        nav_buttons.append(
            InlineKeyboardButton(
                text="◀️",
                callback_data=f"{callback_prefix}:page:{current_page-1}"
            )
        )
    
    nav_buttons.append(
        InlineKeyboardButton(
            text=f"{current_page}/{total_pages}",
            callback_data="pagination_info"
        )
    )
    
    if current_page < total_pages:
        nav_buttons.append(
            InlineKeyboardButton(
                text="▶️",
                callback_data=f"{callback_prefix}:page:{current_page+1}"
            )
        )
    
    keyboard.append(nav_buttons)
    return keyboard

# Helper function to add pagination to any keyboard
def add_pagination(
    keyboard: List[List[InlineKeyboardButton]],
    current_page: int,
    total_pages: int,
    callback_prefix: str
) -> InlineKeyboardMarkup:
    """Add pagination buttons to existing keyboard"""
    if total_pages > 1:
        pagination = get_pagination_keyboard(
            current_page,
            total_pages,
            callback_prefix
        )
        keyboard.extend(pagination)
    return InlineKeyboardMarkup(inline_keyboard=keyboard)

# Export all keyboard functions
__all__ = [
    'get_start_keyboard',
    'get_language_keyboard',
    'get_contact_keyboard',
    'get_cancel_keyboard',
    'get_question_category_keyboard',
    'get_similar_questions_keyboard',
    'get_consultation_type_keyboard',
    'get_payment_methods_keyboard',
    'get_consultation_time_keyboard',
    'get_confirm_cancel_keyboard',
    'get_settings_keyboard',
    'get_notification_settings_keyboard',
    'get_admin_menu_keyboard',
    'get_rating_keyboard',
    'get_consultation_actions_keyboard',
    'get_admin_question_keyboard',
    'get_admin_user_keyboard',
    'get_admin_consultation_keyboard',
    'get_admin_broadcast_keyboard',
    'get_support_keyboard',
    'get_faq_keyboard',
    'get_pagination_keyboard',
    'add_pagination'
]

```

# telegram_bot\bot\middlewares.py

```py
from typing import Any, Awaitable, Callable, Dict, Union
from aiogram import BaseMiddleware
from aiogram.types import Message, CallbackQuery, Update
from sqlalchemy.ext.asyncio import AsyncSession
import logging
from datetime import datetime
import json
import traceback
from telegram_bot.core.constants import TEXTS


from telegram_bot.core.database import get_session
from telegram_bot.models import User
from telegram_bot.services.analytics import AnalyticsService
from telegram_bot.core.monitoring import metrics_manager
from telegram_bot.utils.cache import cache
from telegram_bot.core.errors import (
    ValidationError,
    DatabaseError,
    AuthenticationError
)

logger = logging.getLogger(__name__)

class DatabaseMiddleware(BaseMiddleware):
    """Database session middleware"""
    
    async def __call__(
        self,
        handler: Callable[[Update, Dict[str, Any]], Awaitable[Any]],
        event: Update,
        data: Dict[str, Any]
    ) -> Any:
        async with get_session() as session:
            data['session'] = session
            try:
                return await handler(event, data)
            finally:
                await session.close()

class AuthenticationMiddleware(BaseMiddleware):
    """User authentication middleware"""
    
    async def __call__(
        self,
        handler: Callable[[Update, Dict[str, Any]], Awaitable[Any]],
        event: Update,
        data: Dict[str, Any]
    ) -> Any:
        # Get user info
        if isinstance(event.event, (Message, CallbackQuery)):
            tg_user = event.event.from_user
            session: AsyncSession = data['session']
            
            try:
                # Try to get user from cache
                user_key = f"user:{tg_user.id}"
                user_data = await cache.get(user_key)
                
                if user_data:
                    user = User(**user_data)
                else:
                    # Get or create user
                    from sqlalchemy import select
                    result = await session.execute(
                        select(User).where(User.telegram_id == tg_user.id)
                    )
                    user = result.scalar_one_or_none()
                    
                    if not user:
                        user = User(
                            telegram_id=tg_user.id,
                            username=tg_user.username,
                            full_name=tg_user.full_name
                        )
                        session.add(user)
                        await session.commit()
                        await session.refresh(user)
                    
                    # Cache user data
                    await cache.set(
                        user_key,
                        user.to_dict(),
                        timeout=3600
                    )
                
                # Update user info if needed
                if (
                    user.username != tg_user.username or
                    user.full_name != tg_user.full_name
                ):
                    user.username = tg_user.username
                    user.full_name = tg_user.full_name
                    await session.commit()
                    await cache.delete(user_key)
                
                # Add user to data
                data['user'] = user
                
            except Exception as e:
                logger.error(f"Auth error: {e}", exc_info=True)
                raise AuthenticationError("Failed to authenticate user")
        
        return await handler(event, data)

class LanguageMiddleware(BaseMiddleware):
    """User language middleware"""
    
    async def __call__(
        self,
        handler: Callable[[Update, Dict[str, Any]], Awaitable[Any]],
        event: Update,
        data: Dict[str, Any]
    ) -> Any:
        if isinstance(event.event, (Message, CallbackQuery)):
            user: User = data.get('user')
            if user:
                # Set default language if not set
                if not user.language:
                    user.language = 'uz'  # Default to Uzbek
                    session: AsyncSession = data['session']
                    await session.commit()
                    
                # Add language to data
                data['language'] = user.language
                
        return await handler(event, data)

class UserActivityMiddleware(BaseMiddleware):
    """Track user activity"""
    
    async def __call__(
        self,
        handler: Callable[[Update, Dict[str, Any]], Awaitable[Any]],
        event: Update,
        data: Dict[str, Any]
    ) -> Any:
        if isinstance(event.event, (Message, CallbackQuery)):
            user: User = data.get('user')
            if user:
                try:
                    # Update last active timestamp
                    user.last_active = datetime.utcnow()
                    session: AsyncSession = data['session']
                    await session.commit()
                    
                    # Update cache
                    await cache.set(
                        f"user_active:{user.id}",
                        True,
                        timeout=86400
                    )
                    
                    # Track activity
                    analytics = AnalyticsService(session)
                    await analytics.track_user_activity(
                        user_id=user.id,
                        activity_type='message' if isinstance(event.event, Message) else 'callback',
                        metadata={
                            'content_type': event.event.content_type if isinstance(event.event, Message) else None,
                            'command': event.event.text if isinstance(event.event, Message) and event.event.text.startswith('/') else None
                        }
                    )
                    
                except Exception as e:
                    logger.error(f"Error tracking activity: {e}")
        
        return await handler(event, data)

class RateLimitMiddleware(BaseMiddleware):
    """Rate limiting middleware"""
    
    DEFAULT_RATE = 30  # messages per minute
    INCREASED_RATE = 60  # for admins/special users
    
    async def __call__(
        self,
        handler: Callable[[Update, Dict[str, Any]], Awaitable[Any]],
        event: Update,
        data: Dict[str, Any]
    ) -> Any:
        if isinstance(event.event, (Message, CallbackQuery)):
            user: User = data.get('user')
            if user:
                try:
                    # Get rate limit based on user role
                    rate_limit = self.INCREASED_RATE if user.is_admin else self.DEFAULT_RATE
                    
                    # Check rate limit
                    key = f"rate_limit:{user.id}"
                    count = await cache.increment(key)
                    if count == 1:
                        await cache.expire(key, 60)  # 1 minute window
                        
                    if count > rate_limit:
                        # Rate limit exceeded
                        if isinstance(event.event, Message):
                            await event.event.answer(
                                TEXTS[user.language]['rate_limit_exceeded']
                            )
                        return
                        
                except Exception as e:
                    logger.error(f"Rate limit error: {e}")
        
        return await handler(event, data)

class MetricsMiddleware(BaseMiddleware):
    """Metrics collection middleware"""
    
    async def __call__(
        self,
        handler: Callable[[Update, Dict[str, Any]], Awaitable[Any]],
        event: Update,
        data: Dict[str, Any]
    ) -> Any:
        start_time = datetime.utcnow()
        
        try:
            # Track request
            if isinstance(event.event, Message):
                metrics_manager.track_bot_message(
                    message_type=event.event.content_type
                )
            elif isinstance(event.event, CallbackQuery):
                metrics_manager.track_bot_callback()
            
            # Execute handler
            result = await handler(event, data)
            
            # Calculate duration
            duration = (datetime.utcnow() - start_time).total_seconds()
            
            # Track response time
            metrics_manager.observe(
                'bot_response_time',
                duration,
                labels={
                    'handler_type': 'message' if isinstance(event.event, Message) else 'callback'
                }
            )
            
            return result
            
        except Exception as e:
            # Track error
            metrics_manager.track_bot_error(
                error_type=type(e).__name__
            )
            raise

class LoggingMiddleware(BaseMiddleware):
    """Enhanced logging middleware"""
    
    async def __call__(
        self,
        handler: Callable[[Update, Dict[str, Any]], Awaitable[Any]],
        event: Update,
        data: Dict[str, Any]
    ) -> Any:
        # Prepare log data
        user: User = data.get('user')
        log_data = {
            'user_id': user.id if user else None,
            'telegram_id': user.telegram_id if user else None,
            'update_id': event.update_id,
            'timestamp': datetime.utcnow().isoformat()
        }
        
        if isinstance(event.event, Message):
            log_data.update({
                'event_type': 'message',
                'content_type': event.event.content_type,
                'text': event.event.text if event.event.content_type == 'text' else None
            })
        elif isinstance(event.event, CallbackQuery):
            log_data.update({
                'event_type': 'callback',
                'data': event.event.data
            })
        
        try:
            # Log request
            logger.info(
                f"Incoming {log_data['event_type']}",
                extra={'data': log_data}
            )
            
            # Execute handler
            start_time = datetime.utcnow()
            result = await handler(event, data)
            duration = (datetime.utcnow() - start_time).total_seconds()
            
            # Log response
            log_data['duration'] = duration
            logger.info(
                f"Completed {log_data['event_type']}",
                extra={'data': log_data}
            )
            
            return result
            
        except Exception as e:
            # Log error
            log_data['error'] = str(e)
            log_data['traceback'] = traceback.format_exc()
            logger.error(
                f"Error in {log_data['event_type']}",
                extra={'data': log_data},
                exc_info=True
            )
            raise

class ErrorHandlerMiddleware(BaseMiddleware):
    """Global error handling middleware"""
    
    async def __call__(
        self,
        handler: Callable[[Update, Dict[str, Any]], Awaitable[Any]],
        event: Update,
        data: Dict[str, Any]
    ) -> Any:
        try:
            return await handler(event, data)
            
        except ValidationError as e:
            await self._handle_validation_error(event, e, data)
            
        except DatabaseError as e:
            await self._handle_database_error(event, e, data)
            
        except AuthenticationError as e:
            await self._handle_auth_error(event, e, data)
            
        except Exception as e:
            await self._handle_unknown_error(event, e, data)
    
    async def _handle_validation_error(
        self,
        event: Update,
        error: ValidationError,
        data: Dict
    ):
        """Handle validation errors"""
        user: User = data.get('user')
        if isinstance(event.event, (Message, CallbackQuery)):
            await event.event.answer(
                TEXTS[user.language]['validation_error'] if user else str(error)
            )
    
    async def _handle_database_error(
        self,
        event: Update,
        error: DatabaseError,
        data: Dict
    ):
        """Handle database errors"""
        logger.error(f"Database error: {error}", exc_info=True)
        user: User = data.get('user')
        if isinstance(event.event, (Message, CallbackQuery)):
            await event.event.answer(
                TEXTS[user.language]['error'] if user else "System error"
            )
    
    async def _handle_auth_error(
        self,
        event: Update,
        error: AuthenticationError,
        data: Dict
    ):
        """Handle authentication errors"""
        logger.error(f"Auth error: {error}", exc_info=True)
        if isinstance(event.event, (Message, CallbackQuery)):
            await event.event.answer(
                "Authentication error. Please try again."
            )
    
    async def _handle_unknown_error(
        self,
        event: Update,
        error: Exception,
        data: Dict
    ):
        """Handle unknown errors"""
        logger.error(
            f"Unknown error: {error}",
            exc_info=True,
            extra={'update_id': event.update_id}
        )
        
        user: User = data.get('user')
        if isinstance(event.event, (Message, CallbackQuery)):
            await event.event.answer(
                TEXTS[user.language]['error'] if user else "System error"
            )

# Register all middlewares
def setup_middlewares(dp):
    """Setup all middlewares"""
    middlewares = [
        DatabaseMiddleware(),
        AuthenticationMiddleware(),
        LanguageMiddleware(),
        UserActivityMiddleware(),
        RateLimitMiddleware(),
        MetricsMiddleware(),
        LoggingMiddleware(),
        ErrorHandlerMiddleware()
    ]
    
    for middleware in middlewares:
        dp.message.middleware(middleware)
        dp.callback_query.middleware(middleware)

__all__ = [
    'DatabaseMiddleware',
    'AuthenticationMiddleware',
    'LanguageMiddleware',
    'UserActivityMiddleware',
    'RateLimitMiddleware',
    'MetricsMiddleware',
    'LoggingMiddleware',
    'ErrorHandlerMiddleware',
    'setup_middlewares'
]

```

# telegram_bot\bot\states.py

```py
from aiogram.fsm.state import State, StatesGroup

class BaseState(StatesGroup):
    """Base state group with common functionality"""
    @classmethod
    def get_state_names(cls) -> list[str]:
        return [attr for attr in dir(cls) if isinstance(getattr(cls, attr), State)]
        
    @classmethod
    def get_state(cls, name: str) -> Optional[State]:
        return getattr(cls, name, None) if name in cls.get_state_names() else None

class UserState(BaseState):
    """User interaction states"""
    initial = State()
    selecting_language = State()
    entering_name = State()
    entering_phone = State()
    confirming_profile = State()

class QuestionState(BaseState):
    """Question handling states"""
    entering_question = State()
    selecting_category = State()
    viewing_similar = State()
    awaiting_answer = State()
    rating_answer = State()

class ConsultationState(BaseState): 
    """Consultation flow states"""
    selecting_type = State()
    entering_phone = State()
    entering_description = State()
    selecting_time = State()
    confirming_details = State()
    awaiting_payment = State()
    feedback = State()

class PaymentState(BaseState):
    """Payment flow states"""
    selecting_method = State()
    awaiting_payment = State()
    confirming_payment = State()
    processing_refund = State()

class AdminState(BaseState):
    """Admin panel states"""
    viewing_dashboard = State()
    managing_users = State()
    managing_questions = State()
    managing_consultations = State()
    broadcasting = State()
    viewing_analytics = State()
    
class SupportState(BaseState):
    """Support chat states"""
    describing_issue = State()
    chatting = State()
    viewing_faq = State()
    submitting_feedback = State()

# State manager for tracking state transitions
class StateManager:
    """Manages state transitions and validation"""
    
    def __init__(self):
        self.states = {
            'user': UserState,
            'question': QuestionState,
            'consultation': ConsultationState,
            'payment': PaymentState,
            'admin': AdminState,
            'support': SupportState
        }
        
    def get_state_group(self, group_name: str) -> Optional[Type[BaseState]]:
        """Get state group by name"""
        return self.states.get(group_name)
        
    def get_state(self, group_name: str, state_name: str) -> Optional[State]:
        """Get specific state"""
        group = self.get_state_group(group_name)
        return group.get_state(state_name) if group else None
        
    async def can_transition(
        self,
        from_state: Optional[State],
        to_state: State,
        user: User
    ) -> bool:
        """Check if state transition is allowed"""
        # Always allow transition from None state
        if from_state is None:
            return True
            
        # Get state groups
        from_group = self._get_group_for_state(from_state)
        to_group = self._get_group_for_state(to_state)
        
        # Check if switching between groups
        if from_group != to_group:
            return await self._can_switch_groups(from_group, to_group, user)
            
        # Check specific state transitions
        return await self._check_transition_rules(from_state, to_state, user)
        
    def _get_group_for_state(self, state: State) -> Optional[str]:
        """Get group name for state"""
        for group_name, group_class in self.states.items():
            if state in group_class.get_state_names():
                return group_name
        return None
        
    async def _can_switch_groups(
        self,
        from_group: str,
        to_group: str,
        user: User
    ) -> bool:
        """Check if user can switch between state groups"""
        # Define allowed group transitions
        allowed_transitions = {
            'user': ['question', 'consultation', 'support'],
            'question': ['user', 'consultation'],
            'consultation': ['user', 'payment'],
            'payment': ['consultation'],
            'support': ['user'],
            'admin': ['admin']  # Admin can only transition within admin states
        }
        
        # Check if transition is allowed
        allowed = allowed_transitions.get(from_group, [])
        return to_group in allowed
        
    async def _check_transition_rules(
        self,
        from_state: State,
        to_state: State,
        user: User
    ) -> bool:
        """Check specific state transition rules"""
        # Add custom transition rules here
        return True

# Create state manager instance        
state_manager = StateManager()

__all__ = [
    'UserState',
    'QuestionState', 
    'ConsultationState',
    'PaymentState',
    'AdminState',
    'SupportState',
    'state_manager'
]
```

# telegram_bot\core\__init__.py

```py
from telegram_bot.core.config import settings
from telegram_bot.core.database import get_session, db
from telegram_bot.core.monitoring import metrics_manager
from telegram_bot.core.cache import cache_service
from telegram_bot.core.security import security_manager
from telegram_bot.core.errors import (
    BotError,
    ValidationError,
    DatabaseError,
    AuthenticationError,
    PaymentError
)

__all__ = [
    'settings',
    'get_session',
    'db',
    'metrics_manager',
    'cache_service',
    'security_manager',
    'BotError',
    'ValidationError', 
    'DatabaseError',
    'AuthenticationError',
    'PaymentError'
]
```

# telegram_bot\core\base.py

```py
from datetime import datetime
from typing import Any, Dict, List, Optional, TypeVar, Generic
from sqlalchemy import Column, Integer, DateTime, func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import as_declarative, declared_attr
from sqlalchemy.dialects.postgresql import JSONB
import logging

from telegram_bot.utils.cache import cache
from telegram_bot.core.monitoring import metrics_manager

logger = logging.getLogger(__name__)

ModelType = TypeVar("ModelType")

@as_declarative()
class Base:
    """Base model class"""
    id: Any
    __name__: str
    
    @declared_attr
    def __tablename__(cls) -> str:
        return cls.__name__.lower()
        
    def to_dict(self) -> Dict:
        """Convert model to dictionary"""
        return {
            column.name: getattr(self, column.name)
            for column in self.__table__.columns
        }
    
    @classmethod 
    def from_dict(cls, data: Dict) -> "Base":
        """Create model from dictionary"""
        return cls(**data)

class TimeStampedBase(Base):
    """Base class with timestamp fields"""
    __abstract__ = True
    
    id = Column(Integer, primary_key=True)
    created_at = Column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False
    )
    updated_at = Column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False
    )

class SoftDeleteMixin:
    """Mixin for soft delete"""
    deleted_at = Column(DateTime(timezone=True), nullable=True)
    
    def soft_delete(self) -> None:
        """Mark record as deleted"""
        self.deleted_at = datetime.utcnow()
    
    @property
    def is_deleted(self) -> bool:
        """Check if record is deleted"""
        return self.deleted_at is not None

class MetadataMixin:
    """Mixin for metadata"""
    metadata_ = Column(
        'metadata',
        JSONB,
        nullable=False,
        server_default='{}'
    )
    
    def update_metadata(self, data: Dict) -> None:
        """Update metadata"""
        self.metadata_.update(data)
    
    def get_metadata(self, key: str, default: Any = None) -> Any:
        """Get metadata value"""
        return self.metadata_.get(key, default)

class AuditMixin:
    """Mixin for audit fields"""
    created_by = Column(Integer, nullable=True)
    updated_by = Column(Integer, nullable=True)
    
    def set_created_by(self, user_id: int) -> None:
        """Set created by"""
        self.created_by = user_id
    
    def set_updated_by(self, user_id: int) -> None:
        """Set updated by"""
        self.updated_by = user_id

class BaseService(Generic[ModelType]):
    """Base service with CRUD operations"""
    
    def __init__(
        self,
        model: type[ModelType],
        session: AsyncSession
    ):
        self.model = model
        self.session = session
        
    async def get(self, id: int) -> Optional[ModelType]:
        """Get by ID with caching"""
        # Try cache
        cache_key = f"{self.model.__tablename__}:{id}"
        cached = await cache.get(cache_key)
        if cached:
            metrics_manager.track_cache('get', hit=True)
            return self.model.from_dict(cached)
            
        # Get from database
        start = datetime.utcnow()
        result = await self.session.execute(
            select(self.model).filter_by(id=id)
        )
        metrics_manager.track_db_query(
            (datetime.utcnow() - start).total_seconds()
        )
        
        instance = result.scalar_one_or_none()
        if instance:
            await cache.set(cache_key, instance.to_dict())
            
        metrics_manager.track_cache('get', hit=False)
        return instance
    
    async def create(self, **data) -> ModelType:
        """Create new record"""
        instance = self.model(**data)
        
        # Set audit fields
        if isinstance(instance, AuditMixin):
            instance.created_by = data.get('created_by')
            
        self.session.add(instance)
        
        start = datetime.utcnow()
        await self.session.commit()
        await self.session.refresh(instance)
        metrics_manager.track_db_query(
            (datetime.utcnow() - start).total_seconds()
        )
        
        # Cache new instance
        cache_key = f"{self.model.__tablename__}:{instance.id}"
        await cache.set(cache_key, instance.to_dict())
        
        return instance
    
    async def update(
        self,
        id: int,
        **data
    ) -> Optional[ModelType]:
        """Update record"""
        instance = await self.get(id)
        if not instance:
            return None
            
        # Update fields
        for key, value in data.items():
            setattr(instance, key, value)
            
        # Set audit fields
        if isinstance(instance, AuditMixin):
            instance.updated_by = data.get('updated_by')
            
        start = datetime.utcnow()
        await self.session.commit()
        await self.session.refresh(instance)
        metrics_manager.track_db_query(
            (datetime.utcnow() - start).total_seconds()
        )
        
        # Update cache
        cache_key = f"{self.model.__tablename__}:{id}" 
        await cache.set(cache_key, instance.to_dict())
        
        return instance
    
    async def delete(self, id: int) -> bool:
        """Delete record"""
        instance = await self.get(id)
        if not instance:
            return False
            
        # Soft delete if supported
        if isinstance(instance, SoftDeleteMixin):
            instance.soft_delete()
            await self.session.commit()
        else:
            await self.session.delete(instance)
            await self.session.commit()
            
        # Clear cache
        cache_key = f"{self.model.__tablename__}:{id}"
        await cache.delete(cache_key)
        
        return True
    
    async def list(
        self,
        offset: int = 0,
        limit: int = 100,
        filters: Dict = None,
        order_by: str = None
    ) -> List[ModelType]:
        """Get filtered list"""
        query = select(self.model)
        
        # Apply filters
        if filters:
            for field, value in filters.items():
                if value is not None:
                    query = query.filter(getattr(self.model, field) == value)
                    
        # Apply ordering
        if order_by:
            if order_by.startswith('-'):
                query = query.order_by(getattr(self.model, order_by[1:]).desc())
            else:
                query = query.order_by(getattr(self.model, order_by).asc())
                
        # Apply pagination
        query = query.offset(offset).limit(limit)
        
        start = datetime.utcnow()
        result = await self.session.execute(query)
        metrics_manager.track_db_query(
            (datetime.utcnow() - start).total_seconds()
        )
        
        return list(result.scalars().all())
    
    async def count(self, filters: Dict = None) -> int:
        """Count records"""
        query = select(func.count()).select_from(self.model)
        
        if filters:
            for field, value in filters.items():
                if value is not None:
                    query = query.filter(getattr(self.model, field) == value)
                    
        start = datetime.utcnow()
        result = await self.session.execute(query)
        metrics_manager.track_db_query(
            (datetime.utcnow() - start).total_seconds()
        )
        
        return result.scalar_one()

# Export classes
__all__ = [
    'Base',
    'TimeStampedBase', 
    'SoftDeleteMixin',
    'MetadataMixin',
    'AuditMixin',
    'BaseService'
]
```

# telegram_bot\core\cache.py

```py
from typing import Optional, Any, Dict, List
from datetime import datetime, timedelta
import json
import logging
from redis.asyncio import Redis
from redis.exceptions import RedisError
import hashlib
from functools import wraps
import asyncio
from telegram_bot.core.config import settings
from telegram_bot.core.monitoring import metrics_manager

logger = logging.getLogger(__name__)

class CacheService:
    """Enhanced Redis cache service"""
    
    def __init__(self):
        self.redis = Redis.from_url(
            settings.REDIS_URL,
            encoding='utf-8',
            decode_responses=True,
            socket_timeout=settings.REDIS_SOCKET_TIMEOUT,
            socket_connect_timeout=settings.REDIS_SOCKET_TIMEOUT,
            retry_on_timeout=settings.REDIS_RETRY_ON_TIMEOUT,
            max_connections=settings.REDIS_MAX_CONNECTIONS
        )
        self.default_timeout = 3600  # 1 hour
        
    async def get(self, key: str, default: Any = None) -> Optional[Any]:
        """Get cached value"""
        try:
            value = await self.redis.get(key)
            
            # Track metrics
            metrics_manager.track_cache(
                'get',
                hit=bool(value)
            )
            
            if value is None:
                return default
                
            return json.loads(value)
            
        except RedisError as e:
            logger.error(f"Redis GET error: {e}")
            return default
            
    async def set(
        self,
        key: str,
        value: Any,
        timeout: Optional[int] = None,
        tags: Optional[List[str]] = None
    ) -> bool:
        """Set cached value"""
        try:
            pipe = self.redis.pipeline()
            
            # Set main value
            pipe.set(
                key,
                json.dumps(value),
                ex=timeout or self.default_timeout
            )
            
            # Add tags
            if tags:
                for tag in tags:
                    pipe.sadd(f"tag:{tag}", key)
                    pipe.expire(f"tag:{tag}", timeout or self.default_timeout)
            
            results = await pipe.execute()
            return all(results)
            
        except RedisError as e:
            logger.error(f"Redis SET error: {e}")
            return False
    
    async def delete(self, *keys: str) -> int:
        """Delete cached values"""
        try:
            # Get tags for keys
            pipe = self.redis.pipeline()
            for key in keys:
                pipe.smembers(f"key_tags:{key}")
            tag_results = await pipe.execute()
            
            # Delete keys and tag references
            pipe = self.redis.pipeline()
            
            # Delete main keys
            pipe.delete(*keys)
            
            # Remove keys from tag sets
            all_tags = set()
            for tags in tag_results:
                all_tags.update(tags)
                
            for tag in all_tags:
                pipe.srem(f"tag:{tag}", *keys)
                
            results = await pipe.execute()
            return results[0]  # Number of deleted keys
            
        except RedisError as e:
            logger.error(f"Redis DELETE error: {e}")
            return 0
            
    async def clear_by_tag(self, tag: str) -> int:
        """Clear all keys with given tag"""
        try:
            # Get tagged keys
            keys = await self.redis.smembers(f"tag:{tag}")
            if not keys:
                return 0
                
            # Delete keys and tag
            pipe = self.redis.pipeline()
            pipe.delete(*keys)
            pipe.delete(f"tag:{tag}")
            
            results = await pipe.execute()
            return results[0]
            
        except RedisError as e:
            logger.error(f"Redis tag clear error: {e}")
            return 0
            
    async def get_by_pattern(self, pattern: str) -> Dict[str, Any]:
        """Get all keys matching pattern"""
        try:
            # Get matching keys
            keys = []
            async for key in self.redis.scan_iter(pattern):
                keys.append(key)
                
            if not keys:
                return {}
                
            # Get values
            pipe = self.redis.pipeline()
            for key in keys:
                pipe.get(key)
                
            values = await pipe.execute()
            
            return {
                key: json.loads(value)
                for key, value in zip(keys, values)
                if value is not None
            }
            
        except RedisError as e:
            logger.error(f"Redis pattern get error: {e}")
            return {}
            
    async def increment(
        self,
        key: str,
        amount: int = 1,
        timeout: Optional[int] = None
    ) -> Optional[int]:
        """Increment counter"""
        try:
            pipe = self.redis.pipeline()
            pipe.incr(key, amount)
            
            if timeout:
                pipe.expire(key, timeout)
                
            results = await pipe.execute()
            return results[0]
            
        except RedisError as e:
            logger.error(f"Redis INCREMENT error: {e}")
            return None
            
    async def get_or_set(
        self,
        key: str,
        factory: callable,
        timeout: Optional[int] = None,
        tags: Optional[List[str]] = None
    ) -> Any:
        """Get cached value or generate and cache new one"""
        try:
            # Try get from cache
            value = await self.get(key)
            if value is not None:
                return value
                
            # Generate new value
            value = await factory() if asyncio.iscoroutinefunction(factory) else factory()
            
            # Cache new value
            await self.set(
                key,
                value,
                timeout=timeout,
                tags=tags
            )
            
            return value
            
        except Exception as e:
            logger.error(f"Cache get_or_set error: {e}")
            # Return generated value even if caching fails
            return await factory() if asyncio.iscoroutinefunction(factory) else factory()
            
    async def health_check(self) -> bool:
        """Check Redis connection"""
        try:
            return await self.redis.ping()
        except RedisError:
            return False

def cache_key(*args, **kwargs) -> str:
    """Generate cache key from arguments"""
    key_parts = [str(arg) for arg in args]
    key_parts.extend(
        f"{k}:{v}" for k, v in sorted(kwargs.items())
    )
    return hashlib.md5(":".join(key_parts).encode()).hexdigest()

def cached(
    timeout: Optional[int] = None,
    prefix: Optional[str] = None,
    tags: Optional[List[str]] = None
):
    """Caching decorator"""
    def decorator(func):
        @wraps(func)
        async def wrapper(*args, **kwargs):
            # Generate cache key
            key = cache_key(*args, **kwargs)
            if prefix:
                key = f"{prefix}:{key}"
                
            return await cache_service.get_or_set(
                key,
                lambda: func(*args, **kwargs),
                timeout=timeout,
                tags=tags
            )
        return wrapper
    return decorator

# Create cache service instance
cache_service = CacheService()

__all__ = [
    'CacheService',
    'cache_service',
    'cache_key',
    'cached'
]
```

# telegram_bot\core\config.py

```py
from pydantic_settings import BaseSettings, SettingsConfigDict
from pydantic import SecretStr, Field, validator, DirectoryPath
from typing import List, Dict, Any, Optional
from pathlib import Path
from datetime import timedelta
import json
import os

class Settings(BaseSettings):
    """Application settings"""
    
    # Application
    APP_NAME: str = "Law Consultation Bot"
    VERSION: str = "1.0.0"
    DEBUG: bool = Field(default=False)
    ENVIRONMENT: str = Field(default="development")
    
    # Paths
    BASE_DIR: Path = Field(default=Path(__file__).parent.parent.parent)
    STATIC_DIR: Path = Field(default=None)
    MEDIA_DIR: Path = Field(default=None)
    LOGS_DIR: Path = Field(default=None)
    BACKUP_DIR: Path = Field(default=None)
    
    # Security
    SECRET_KEY: SecretStr
    API_TOKEN_EXPIRE_MINUTES: int = 60
    REFRESH_TOKEN_EXPIRE_DAYS: int = 7
    JWT_ALGORITHM: str = "HS256"
    ALLOWED_HOSTS: List[str] = ["*"]
    CORS_ORIGINS: List[str] = ["*"]
    
    # Bot
    BOT_TOKEN: SecretStr
    ADMIN_IDS: List[int] = []
    BOT_WEBHOOK_SECRET: Optional[SecretStr] = None
    BOT_WEBHOOK_PATH: Optional[str] = None
    BOT_WEBHOOK_URL: Optional[str] = None
    
    # Database
    DB_HOST: str
    DB_PORT: int = 5432
    DB_USER: str
    DB_PASSWORD: SecretStr
    DB_NAME: str
    DB_POOL_SIZE: int = 20
    DB_MAX_OVERFLOW: int = 10
    DB_POOL_TIMEOUT: int = 30
    DB_POOL_RECYCLE: int = 1800
    DB_STATEMENT_TIMEOUT: int = 30000  # 30s
    DB_COMMAND_TIMEOUT: int = 30
    DB_ECHO: bool = False
    DB_SLOW_QUERY_THRESHOLD: float = 1.0  # seconds
    
    # Redis
    REDIS_HOST: str
    REDIS_PORT: int = 6379
    REDIS_PASSWORD: Optional[SecretStr] = None
    REDIS_DB: int = 0
    REDIS_MAX_CONNECTIONS: int = 10
    REDIS_SOCKET_TIMEOUT: int = 5
    REDIS_RETRY_ON_TIMEOUT: bool = True
    
    # Payment Systems
    CLICK_MERCHANT_ID: Optional[SecretStr] = None
    CLICK_SERVICE_ID: Optional[str] = None
    CLICK_SECRET_KEY: Optional[SecretStr] = None
    CLICK_RETURN_URL: Optional[str] = None
    
    PAYME_MERCHANT_ID: Optional[SecretStr] = None
    PAYME_SECRET_KEY: Optional[SecretStr] = None
    PAYME_RETURN_URL: Optional[str] = None
    
    UZUM_MERCHANT_ID: Optional[SecretStr] = None
    UZUM_SECRET_KEY: Optional[SecretStr] = None
    UZUM_RETURN_URL: Optional[str] = None
    
    # Monitoring
    SENTRY_DSN: Optional[SecretStr] = None
    SENTRY_ENVIRONMENT: Optional[str] = None
    SENTRY_TRACES_SAMPLE_RATE: float = 1.0
    
    PROMETHEUS_ENABLED: bool = True
    PROMETHEUS_PORT: int = 9090
    
    GRAYLOG_HOST: Optional[str] = None
    GRAYLOG_PORT: Optional[int] = None
    
    # Logging
    LOG_LEVEL: str = "INFO"
    LOG_FORMAT: str = "json"
    LOG_FILE: Optional[str] = None
    LOG_MAX_SIZE: int = 10 * 1024 * 1024  # 10MB
    LOG_BACKUP_COUNT: int = 5
    
    # Cache
    CACHE_TTL: int = 3600  # 1 hour
    CACHE_PREFIX: str = "law_bot"
    
    # API
    API_V1_PREFIX: str = "/api/v1"
    API_TITLE: str = "Law Bot API"
    API_DESCRIPTION: str = "API for Law Consultation Telegram Bot"
    API_VERSION: str = "1.0.0"
    
    # Admin Panel
    ADMIN_PANEL_URL: str = "/admin"
    ADMIN_PANEL_TITLE: str = "Law Bot Admin"
    
    # Feature Flags
    FEATURES: Dict[str, bool] = {
        "payment_system": True,
        "auto_answers": True,
        "notifications": True,
        "admin_panel": True
    }
    
    # Business Rules
    BUSINESS_RULES: Dict[str, Any] = {
        "min_question_length": 10,
        "max_question_length": 1000,
        "min_consultation_amount": 50000,
        "max_consultation_amount": 1000000,
        "consultation_duration": 60,
        "cancellation_period": 24,
        "working_hours": {
            "start": 9,
            "end": 18
        }
    }

    @validator("STATIC_DIR", "MEDIA_DIR", "LOGS_DIR", "BACKUP_DIR", pre=True)
    def build_paths(cls, v, values):
        if v is None:
            base_dir = values.get("BASE_DIR", Path(__file__).parent.parent.parent)
            if "STATIC_DIR" in values.keys():
                return base_dir / "static"
            elif "MEDIA_DIR" in values.keys():
                return base_dir / "media"
            elif "LOGS_DIR" in values.keys():
                return base_dir / "logs"
            elif "BACKUP_DIR" in values.keys():
                return base_dir / "backups"
        return v

    @property
    def DATABASE_URL(self) -> str:
        """Get SQLAlchemy database URL"""
        return (
            f"postgresql+asyncpg://{self.DB_USER}:"
            f"{self.DB_PASSWORD.get_secret_value()}"
            f"@{self.DB_HOST}:{self.DB_PORT}/{self.DB_NAME}"
        )
    
    @property
    def REDIS_URL(self) -> str:
        """Get Redis URL"""
        if self.REDIS_PASSWORD:
            return (
                f"redis://:{self.REDIS_PASSWORD.get_secret_value()}"
                f"@{self.REDIS_HOST}:{self.REDIS_PORT}/{self.REDIS_DB}"
            )
        return f"redis://{self.REDIS_HOST}:{self.REDIS_PORT}/{self.REDIS_DB}"
    
    @property
    def CLICK_CONFIG(self) -> Dict[str, Any]:
        """Get Click payment system config"""
        if not (self.CLICK_MERCHANT_ID and self.CLICK_SECRET_KEY):
            return {}
            
        return {
            'merchant_id': self.CLICK_MERCHANT_ID.get_secret_value(),
            'service_id': self.CLICK_SERVICE_ID,
            'secret_key': self.CLICK_SECRET_KEY.get_secret_value(),
            'return_url': self.CLICK_RETURN_URL
        }
    
    @property
    def PAYME_CONFIG(self) -> Dict[str, Any]:
        """Get Payme payment system config"""
        if not (self.PAYME_MERCHANT_ID and self.PAYME_SECRET_KEY):
            return {}
            
        return {
            'merchant_id': self.PAYME_MERCHANT_ID.get_secret_value(),
            'secret_key': self.PAYME_SECRET_KEY.get_secret_value(),
            'return_url': self.PAYME_RETURN_URL
        }
    
    @property
    def UZUM_CONFIG(self) -> Dict[str, Any]:
        """Get Uzum payment system config"""
        if not (self.UZUM_MERCHANT_ID and self.UZUM_SECRET_KEY):
            return {}
            
        return {
            'merchant_id': self.UZUM_MERCHANT_ID.get_secret_value(),
            'secret_key': self.UZUM_SECRET_KEY.get_secret_value(),
            'return_url': self.UZUM_RETURN_URL
        }

    def get_feature_flag(self, feature: str) -> bool:
        """Get feature flag value"""
        return self.FEATURES.get(feature, False)
    
    def get_business_rule(self, rule: str) -> Any:
        """Get business rule value"""
        return self.BUSINESS_RULES.get(rule)

    def configure_sentry(self) -> None:
        """Configure Sentry error tracking"""
        if self.SENTRY_DSN:
            import sentry_sdk
            from sentry_sdk.integrations.fastapi import FastApiIntegration
            from sentry_sdk.integrations.sqlalchemy import SqlalchemyIntegration
            from sentry_sdk.integrations.redis import RedisIntegration
            
            sentry_sdk.init(
                dsn=self.SENTRY_DSN.get_secret_value(),
                environment=self.SENTRY_ENVIRONMENT or self.ENVIRONMENT,
                traces_sample_rate=self.SENTRY_TRACES_SAMPLE_RATE,
                integrations=[
                    FastApiIntegration(),
                    SqlalchemyIntegration(),
                    RedisIntegration()
                ]
            )

    def configure_prometheus(self) -> None:
        """Configure Prometheus metrics"""
        if self.PROMETHEUS_ENABLED:
            from prometheus_client import start_http_server
            start_http_server(self.PROMETHEUS_PORT)

    def get_log_config(self) -> Dict[str, Any]:
        """Get logging configuration"""
        return {
            'version': 1,
            'disable_existing_loggers': False,
            'formatters': {
                'json': {
                    '()': 'pythonjsonlogger.jsonlogger.JsonFormatter',
                    'format': '%(asctime)s %(name)s %(levelname)s %(message)s'
                },
                'standard': {
                    'format': '%(asctime)s [%(levelname)s] %(name)s: %(message)s'
                }
            },
            'handlers': {
                'console': {
                    'class': 'logging.StreamHandler',
                    'formatter': 'json' if self.LOG_FORMAT == 'json' else 'standard',
                    'level': self.LOG_LEVEL
                },
                'file': {
                    'class': 'logging.handlers.RotatingFileHandler',
                    'filename': self.LOG_FILE or str(self.LOGS_DIR / 'app.log'),
                    'maxBytes': self.LOG_MAX_SIZE,
                    'backupCount': self.LOG_BACKUP_COUNT,
                    'formatter': 'json' if self.LOG_FORMAT == 'json' else 'standard',
                    'level': self.LOG_LEVEL
                }
            },
            'root': {
                'handlers': ['console', 'file'],
                'level': self.LOG_LEVEL
            }
        }

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=True,
        extra="allow"
    )

# Create settings instance
settings = Settings()

# Create required directories
for path in [settings.STATIC_DIR, settings.MEDIA_DIR, settings.LOGS_DIR, settings.BACKUP_DIR]:
    path.mkdir(parents=True, exist_ok=True)

# Configure monitoring if enabled
if settings.ENVIRONMENT == "production":
    settings.configure_sentry()

if settings.PROMETHEUS_ENABLED:
    settings.configure_prometheus()
```

# telegram_bot\core\constants.py

```py
from typing import Dict, Any
from enum import Enum
from decimal import Decimal
from datetime import timedelta

class UserRole(str, Enum):
    USER = 'USER'
    ADMIN = 'ADMIN'
    SUPPORT = 'SUPPORT'
    MODERATOR = 'MODERATOR'

class ConsultationStatus(str, Enum):
    PENDING = 'PENDING'
    PAID = 'PAID'
    SCHEDULED = 'SCHEDULED'
    COMPLETED = 'COMPLETED'
    CANCELLED = 'CANCELLED'

class PaymentStatus(str, Enum):
    PENDING = 'PENDING'
    PROCESSING = 'PROCESSING'
    COMPLETED = 'COMPLETED'
    FAILED = 'FAILED'
    REFUNDED = 'REFUNDED'

class PaymentProvider(str, Enum):
    CLICK = 'CLICK'
    PAYME = 'PAYME'
    UZUM = 'UZUM'

class Language(str, Enum):
    UZ = 'uz'
    RU = 'ru'

# System Constants
RATE_LIMITS = {
    'default': 30,  # requests per minute
    'payment': 5,   # payment requests per minute
    'questions': 10 # questions per minute
}

CACHE_TIMEOUTS = {
    'user': 3600,           # 1 hour
    'session': 86400,       # 24 hours
    'verification': 300,    # 5 minutes
    'payment': 900,        # 15 minutes
    'analytics': 300       # 5 minutes
}

ERROR_MESSAGES = {
    'validation': {
        'uz': 'Ma\'lumotlar noto\'g\'ri',
        'ru': 'Неверные данные'
    },
    'payment': {
        'uz': 'To\'lov xatosi',
        'ru': 'Ошибка оплаты'
    },
    'server': {
        'uz': 'Server xatosi',
        'ru': 'Ошибка сервера'
    }
}

# Business Rules Constants
CONSULTATION_RULES = {
    'min_amount': Decimal('50000.00'),
    'max_amount': Decimal('1000000.00'),
    'duration': 60,  # minutes
    'cancel_timeout': timedelta(hours=2),
    'reschedule_timeout': timedelta(hours=4),
    'types': {
        'online': {
            'price': Decimal('50000.00'),
            'duration': 30
        },
        'office': {
            'price': Decimal('100000.00'),
            'duration': 60
        }
    }
}

QUESTION_RULES = {
    'min_length': 10,
    'max_length': 1000,
    'max_per_day': 20,
    'similarity_threshold': 0.7
}

WORKING_HOURS = {
    'start': 9,  # 9 AM
    'end': 18,   # 6 PM
    'days': [0, 1, 2, 3, 4, 5]  # Monday to Saturday
}

NOTIFICATION_TYPES = {
    'consultation_reminder': {
        'template': 'consultation_reminder',
        'timeout': timedelta(hours=1)
    },
    'payment_reminder': {
        'template': 'payment_reminder',
        'timeout': timedelta(hours=4)
    },
    'question_answered': {
        'template': 'question_answered',
        'timeout': timedelta(days=1)
    }
}

PAYMENT_CONFIG = {
    'click': {
        'merchant_id': '12345',
        'service_id': '12345',
        'timeout': 900,  # 15 minutes
        'min_amount': Decimal('1000.00'),
        'max_amount': Decimal('10000000.00')
    },
    'payme': {
        'merchant_id': '12345',
        'timeout': 900,
        'min_amount': Decimal('1000.00'),
        'max_amount': Decimal('10000000.00')
    },
    'uzum': {
        'merchant_id': '12345',
        'timeout': 900,
        'min_amount': Decimal('1000.00'),
        'max_amount': Decimal('10000000.00')
    }
}

ANALYTICS_CONFIG = {
    'retention_days': 90,
    'metrics_interval': 300,  # 5 minutes
    'dashboard_cache': 300,
    'export_limit': 10000
}

SYSTEM_LIMITS = {
    'max_connections': 100,
    'request_timeout': 30,
    'file_size_limit': 10 * 1024 * 1024,  # 10MB
    'max_retries': 3,
    'batch_size': 1000
}

# Message Templates
MESSAGES = {
    'uz': {
        'welcome': """
🤖 Yuridik maslahat botiga xush kelibsiz!

Bot orqali siz:
• Savol berishingiz
• Bepul konsultatsiya olishingiz
• Advokat bilan bog'lanishingiz mumkin

Quyidagi tugmalardan birini tanlang:
        """,
        'welcome_back': "Qaytganingizdan xursandmiz! Sizga qanday yordam bera olaman?",
        'contact_support': "Operatorlar bilan bog'lanish",
        'ask_question': "❓ Savol berish",
        'my_questions': "📝 Savollarim",
        'settings': "⚙️ Sozlamalar",
        'help': "🆘 Yordam",
        'language_changed': "✅ Til muvaffaqiyatli o'zgartirildi",
        'consultation_booked': "✅ Konsultatsiya band qilindi",
        'payment_pending': "⏳ To'lov kutilmoqda",
        'payment_success': "✅ To'lov muvaffaqiyatli amalga oshirildi",
        'payment_failed': "❌ To'lov amalga oshmadi"
    },
    'ru': {
        'welcome': """
🤖 Добро пожаловать в бот юридической консультации!

Через бот вы можете:
• Задать вопрос
• Получить бесплатную консультацию
• Связаться с адвокатом

Выберите одну из кнопок ниже:
        """,
        'welcome_back': "Рады видеть вас снова! Как я могу вам помочь?",
        'contact_support': "Связаться с операторами",
        'ask_question': "❓ Задать вопрос",
        'my_questions': "📝 Мои вопросы",
        'settings': "⚙️ Настройки",
        'help': "🆘 Помощь",
        'language_changed': "✅ Язык успешно изменен",
        'consultation_booked': "✅ Консультация забронирована",
        'payment_pending': "⏳ Ожидание оплаты",
        'payment_success': "✅ Оплата успешно выполнена",
        'payment_failed': "❌ Ошибка оплаты"
    }
}


TEXTS = {
    'uz': {
        'welcome': """
🤖 Yuridik maslahat botiga xush kelibsiz!

Bot orqali siz:
• Savol berishingiz
• Bepul konsultatsiya olishingiz
• Advokat bilan bog'lanishingiz mumkin

Quyidagi tugmalardan birini tanlang:
        """,
        'ask_question': '❓ Savol berish',
        'my_questions': '📝 Savollarim',
        'consultation': '📅 Konsultatsiya',
        'support': '🆘 Yordam',
        'settings': '⚙️ Sozlamalar',
        'select_language': '🌐 Tilni tanlang',
        'language_changed': '✅ Til muvaffaqiyatli o\'zgartirildi',
        'select_consultation_type': 'Konsultatsiya turini tanlang:',
        'online_consultation': '🌐 Online konsultatsiya',
        'office_consultation': '🏢 Ofisda konsultatsiya',
        'request_contact': 'Iltimos, telefon raqamingizni yuboring:',
        'invalid_phone': '❌ Noto\'g\'ri telefon raqami formati. Qaytadan urinib ko\'ring.',
        'describe_problem': 'Muammongizni batafsil yozing:',
        'payment_instruction': 'To\'lov miqdori: {amount} so\'m\nTo\'lov tizimi: {provider}\n\nTo\'lovni amalga oshirish uchun quyidagi tugmani bosing:',
        'payment_cancelled': '❌ To\'lov bekor qilindi',
        'payment_success': '✅ To\'lov muvaffaqiyatli amalga oshirildi',
        'consultation_scheduled': '✅ Konsultatsiya {time} ga belgilandi',
        'select_time': 'Qulay vaqtni tanlang:',
        'cancel': '❌ Bekor qilish',
        'back': '◀️ Orqaga',
        'error': '❌ Xatolik yuz berdi. Iltimos, qaytadan urinib ko\'ring.'
    },
    'ru': {
        'welcome': """
🤖 Добро пожаловать в бот юридической консультации!

Через бот вы можете:
• Задать вопрос
• Получить бесплатную консультацию
• Связаться с адвокатом

Выберите одну из кнопок ниже:
        """,
        'ask_question': '❓ Задать вопрос',
        'my_questions': '📝 Мои вопросы',
        'consultation': '📅 Консультация',
        'support': '🆘 Поддержка',
        'settings': '⚙️ Настройки',
        'select_language': '🌐 Выберите язык',
        'language_changed': '✅ Язык успешно изменен',
        'select_consultation_type': 'Выберите тип консультации:',
        'online_consultation': '🌐 Онлайн консультация',
        'office_consultation': '🏢 Консультация в офисе',
        'request_contact': 'Пожалуйста, отправьте ваш номер телефона:',
        'invalid_phone': '❌ Неверный формат номера телефона. Попробуйте еще раз.',
        'describe_problem': 'Опишите подробно вашу проблему:',
        'payment_instruction': 'Сумма к оплате: {amount} сум\nСистема оплаты: {provider}\n\nНажмите кнопку ниже для оплаты:',
        'payment_cancelled': '❌ Оплата отменена',
        'payment_success': '✅ Оплата успешно выполнена',
        'consultation_scheduled': '✅ Консультация назначена на {time}',
        'select_time': 'Выберите удобное время:',
        'cancel': '❌ Отмена',
        'back': '◀️ Назад',
        'error': '❌ Произошла ошибка. Пожалуйста, попробуйте еще раз.'
    }
}

FAQ_TEXTS = {
    'uz': {
        'faq_categories': '📚 Tez-tez so\'raladigan savollar bo\'limlari:',
        'select_faq': 'Savolni tanlang:',
        'no_faqs_in_category': 'Bu bo\'limda hozircha savollar yo\'q.',
        'faq_not_found': 'Savol topilmadi.',
        'enter_faq_search': 'Qidirilayotgan savolni kiriting:',
        'no_faq_results': 'Sizning so\'rovingiz bo\'yicha savollar topilmadi.',
        'search_faq': '🔍 Qidirish',
        'helpful': '👍 Foydali',
        'not_helpful': '👎 Foydali emas',
        'thanks_feedback': 'Fikr-mulohaza uchun rahmat!',
        'back_to_category': '◀️ Bo\'limga qaytish',
        'back_to_categories': '◀️ Bo\'limlarga qaytish'
    },
    'ru': {
        'faq_categories': '📚 Разделы часто задаваемых вопросов:',
        'select_faq': 'Выберите вопрос:',
        'no_faqs_in_category': 'В этом разделе пока нет вопросов.',
        'faq_not_found': 'Вопрос не найден.',
        'enter_faq_search': 'Введите искомый вопрос:',
        'no_faq_results': 'По вашему запросу вопросов не найдено.',
        'search_faq': '🔍 Поиск',
        'helpful': '👍 Полезно',
        'not_helpful': '👎 Не полезно',
        'thanks_feedback': 'Спасибо за отзыв!',
        'back_to_category': '◀️ Назад к разделу',
        'back_to_categories': '◀️ Назад к разделам'
    }
}

# Add FAQ texts to main TEXTS dictionary
for lang in ['uz', 'ru']:
    TEXTS[lang].update(FAQ_TEXTS[lang])

    
# Admin Configuration
ADMIN_CONFIG = {
    'dashboard': {
        'cache_timeout': 300,
        'metrics_interval': 60,
        'max_recent_actions': 100
    },
    'notifications': {
        'error_threshold': 5,
        'warning_threshold': 3
    },
    'export': {
        'formats': ['csv', 'xlsx'],
        'max_records': 10000
    }
}

class SystemMetrics:
    """System metrics configuration"""
    REQUEST_COUNT = 'request_count'
    ERROR_COUNT = 'error_count'
    RESPONSE_TIME = 'response_time'
    ACTIVE_USERS = 'active_users'
    DB_CONNECTIONS = 'db_connections'
    CACHE_HITS = 'cache_hits'
    QUESTIONS_TOTAL = 'questions_total'
    ANSWERS_TOTAL = 'answers_total'
    CONSULTATIONS_TOTAL = 'consultations_total'
    PAYMENTS_TOTAL = 'payments_total'

# Export all constants
__all__ = [
    'UserRole',
    'ConsultationStatus',
    'PaymentStatus',
    'PaymentProvider',
    'Language',
    'RATE_LIMITS',
    'CACHE_TIMEOUTS',
    'ERROR_MESSAGES',
    'CONSULTATION_RULES',
    'QUESTION_RULES',
    'WORKING_HOURS',
    'NOTIFICATION_TYPES',
    'PAYMENT_CONFIG',
    'ANALYTICS_CONFIG',
    'SYSTEM_LIMITS',
    'MESSAGES',
    'ADMIN_CONFIG',
    'SystemMetrics'
]
```

# telegram_bot\core\database.py

```py
from typing import AsyncGenerator, Optional, Dict, Any, List
from sqlalchemy.ext.asyncio import (
    create_async_engine,
    AsyncSession,
    AsyncEngine,
    async_sessionmaker
)
from sqlalchemy.pool import AsyncAdaptedQueuePool
from sqlalchemy import event, text
from sqlalchemy.exc import SQLAlchemyError
from contextlib import asynccontextmanager
import logging
from datetime import datetime
import json

from telegram_bot.core.config import settings
from telegram_bot.core.monitoring import metrics_manager
from telegram_bot.models.base import Base
from telegram_bot.core.errors import DatabaseError

from typing import AsyncGenerator
from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker, AsyncSession
from telegram_bot.core.config import settings
from telegram_bot.models.base import Base
import logging

logger = logging.getLogger(__name__)

# Create async engine
engine = create_async_engine(
    settings.DATABASE_URL,
    echo=settings.DB_ECHO,
    pool_size=settings.DB_POOL_SIZE,
    max_overflow=settings.DB_MAX_OVERFLOW
)

# Create session factory
async_session_maker = async_sessionmaker(
    engine,
    expire_on_commit=False,
    class_=AsyncSession
)

async def init_db():
    """Initialize database"""
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

async def get_session() -> AsyncGenerator[AsyncSession, None]:
    """Get database session"""
    async with async_session_maker() as session:
        try:
            yield session
        finally:
            await session.close()

async def close_db():
    """Close database connections"""
    await engine.dispose()


logger = logging.getLogger(__name__)

class DatabaseManager:
    """Enhanced database manager"""
    
    def __init__(self):
        self._engine: Optional[AsyncEngine] = None
        self._sessionmaker: Optional[async_sessionmaker] = None
        self.Base = Base
        
    async def init(self) -> None:
        """Initialize database connection"""
        if not self._engine:
            # Create engine
            self._engine = create_async_engine(
                settings.DATABASE_URL,
                echo=settings.DB_ECHO,
                pool_size=settings.DB_POOL_SIZE,
                max_overflow=settings.DB_MAX_OVERFLOW,
                poolclass=AsyncAdaptedQueuePool,
                pool_pre_ping=True,
                pool_timeout=settings.DB_POOL_TIMEOUT,
                pool_recycle=settings.DB_POOL_RECYCLE,
                json_serializer=json.dumps,
                json_deserializer=json.loads,
                connect_args={
                    "statement_timeout": settings.DB_STATEMENT_TIMEOUT,
                    "command_timeout": settings.DB_COMMAND_TIMEOUT
                }
            )
            
            # Create session maker
            self._sessionmaker = async_sessionmaker(
                self._engine,
                class_=AsyncSession,
                expire_on_commit=False,
                autoflush=False
            )
            
            # Add event listeners
            event.listen(
                self._engine.sync_engine,
                'before_cursor_execute',
                self._before_cursor_execute
            )
            event.listen(
                self._engine.sync_engine,
                'after_cursor_execute',
                self._after_cursor_execute
            )
            
            logger.info("Database engine initialized")
            
    async def create_all(self) -> None:
        """Create all database tables"""
        if not self._engine:
            await self.init()
            
        async with self._engine.begin() as conn:
            await conn.run_sync(self.Base.metadata.create_all)
            
        logger.info("Database tables created")
        
    async def drop_all(self) -> None:
        """Drop all database tables"""
        if self._engine:
            async with self._engine.begin() as conn:
                await conn.run_sync(self.Base.metadata.drop_all)
                
            logger.info("Database tables dropped")
            
    @asynccontextmanager
    async def session(self) -> AsyncGenerator[AsyncSession, None]:
        """Get database session"""
        if not self._sessionmaker:
            await self.init()
            
        session: AsyncSession = self._sessionmaker()
        try:
            yield session
        except SQLAlchemyError as e:
            logger.error(f"Database session error: {e}")
            await session.rollback()
            raise DatabaseError(str(e))
        finally:
            await session.close()
            
    async def close(self) -> None:
        """Close database connections"""
        if self._engine:
            await self._engine.dispose()
            self._engine = None
            self._sessionmaker = None
            logger.info("Database connections closed")
            
    async def get_stats(self) -> Dict[str, Any]:
        """Get database statistics"""
        try:
            async with self.session() as session:
                # Get general stats
                result = await session.execute(text("""
                    SELECT 
                        pg_database_size(current_database()) as db_size,
                        pg_size_pretty(pg_database_size(current_database())) as db_size_pretty,
                        (SELECT count(*) FROM pg_stat_activity) as connections,
                        (SELECT count(*) FROM pg_stat_activity WHERE state = 'active') as active_connections,
                        age(datfrozenxid) as transaction_age
                    FROM pg_database 
                    WHERE datname = current_database()
                """))
                stats = result.mappings().first()
                
                # Get table stats
                result = await session.execute(text("""
                    SELECT 
                        schemaname,
                        relname,
                        n_live_tup as row_count,
                        pg_size_pretty(pg_total_relation_size(relid)) as total_size
                    FROM pg_stat_user_tables
                    ORDER BY n_live_tup DESC
                """))
                tables = result.mappings().all()
                
                return {
                    "database_size": stats["db_size"],
                    "database_size_pretty": stats["db_size_pretty"],
                    "total_connections": stats["connections"],
                    "active_connections": stats["active_connections"],
                    "transaction_age": stats["transaction_age"],
                    "tables": [dict(t) for t in tables],
                    "timestamp": datetime.utcnow().isoformat()
                }
                
        except Exception as e:
            logger.error(f"Error getting database stats: {e}")
            return {}
            
    async def check_connection(self) -> bool:
        """Check database connection"""
        try:
            async with self.session() as session:
                await session.execute(text("SELECT 1"))
                return True
        except Exception as e:
            logger.error(f"Database connection check failed: {e}")
            return False
            
    async def vacuum(self, table: Optional[str] = None) -> None:
        """Run VACUUM on database or specific table"""
        try:
            async with self.session() as session:
                if table:
                    await session.execute(
                        text(f"VACUUM ANALYZE {table}")
                    )
                else:
                    await session.execute(text("VACUUM ANALYZE"))
                    
            logger.info(f"VACUUM completed for {table or 'all tables'}")
            
        except Exception as e:
            logger.error(f"Error running VACUUM: {e}")
            
    async def backup(self, backup_path: str) -> bool:
        """Create database backup"""
        try:
            import subprocess
            
            # Create backup command
            command = [
                'pg_dump',
                '-h', settings.DB_HOST,
                '-p', str(settings.DB_PORT),
                '-U', settings.DB_USER,
                '-F', 'c',  # Custom format
                '-f', backup_path,
                settings.DB_NAME
            ]
            
            # Set password environment variable
            env = {
                'PGPASSWORD': settings.DB_PASSWORD.get_secret_value()
            }
            
            # Run backup
            process = subprocess.run(
                command,
                env=env,
                capture_output=True,
                text=True
            )
            
            if process.returncode == 0:
                logger.info(f"Database backup created at {backup_path}")
                return True
            else:
                logger.error(f"Backup error: {process.stderr}")
                return False
                
        except Exception as e:
            logger.error(f"Error creating backup: {e}")
            return False
            
    async def restore(self, backup_path: str) -> bool:
        """Restore database from backup"""
        try:
            import subprocess
            
            # Create restore command
            command = [
                'pg_restore',
                '-h', settings.DB_HOST,
                '-p', str(settings.DB_PORT),
                '-U', settings.DB_USER,
                '-d', settings.DB_NAME,
                '-c',  # Clean (drop) database objects before recreating
                backup_path
            ]
            
            # Set password environment variable
            env = {
                'PGPASSWORD': settings.DB_PASSWORD.get_secret_value()
            }
            
            # Run restore
            process = subprocess.run(
                command,
                env=env,
                capture_output=True,
                text=True
            )
            
            if process.returncode == 0:
                logger.info(f"Database restored from {backup_path}")
                return True
            else:
                logger.error(f"Restore error: {process.stderr}")
                return False
                
        except Exception as e:
            logger.error(f"Error restoring backup: {e}")
            return False
            
    def _before_cursor_execute(
        self,
        conn,
        cursor,
        statement,
        parameters,
        context,
        executemany
    ):
        """Handler for before cursor execute event"""
        context._query_start_time = datetime.utcnow()
        metrics_manager.track_db_query(
            operation=statement.split()[0].lower()
        )
        
    def _after_cursor_execute(
        self,
        conn,
        cursor,
        statement,
        parameters,
        context,
        executemany
    ):
        """Handler for after cursor execute event"""
        total_time = (datetime.utcnow() - context._query_start_time).total_seconds()
        
        # Track query duration
        metrics_manager.track_db_query_duration(total_time)
        
        # Log slow queries
        if total_time > settings.DB_SLOW_QUERY_THRESHOLD:
            logger.warning(
                f"Slow query detected: {total_time:.2f}s\n"
                f"Query: {statement}\n"
                f"Parameters: {parameters}"
            )

class DatabaseSession:
    """Database session context manager"""
    
    def __init__(self, session: AsyncSession):
        self.session = session
        
    async def __aenter__(self) -> AsyncSession:
        return self.session
        
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        if exc_type is not None:
            await self.session.rollback()
        await self.session.close()

class QueryBuilder:
    """SQL query builder helper"""
    
    def __init__(self, model):
        self.model = model
        self.query = None
        
    def select(self, *columns):
        """Start SELECT query"""
        from sqlalchemy import select
        self.query = select(*columns or [self.model])
        return self
        
    def where(self, *criteria):
        """Add WHERE clause"""
        if self.query is not None:
            self.query = self.query.where(*criteria)
        return self
        
    def order_by(self, *columns):
        """Add ORDER BY clause"""
        if self.query is not None:
            self.query = self.query.order_by(*columns)
        return self
        
    def limit(self, limit: int):
        """Add LIMIT clause"""
        if self.query is not None:
            self.query = self.query.limit(limit)
        return self
        
    def offset(self, offset: int):
        """Add OFFSET clause"""
        if self.query is not None:
            self.query = self.query.offset(offset)
        return self
        
    def join(self, *props, **kwargs):
        """Add JOIN clause"""
        if self.query is not None:
            self.query = self.query.join(*props, **kwargs)
        return self
        
    def get_query(self):
        """Get built query"""
        return self.query

class BulkOperations:
    """Helper for bulk database operations"""
    
    def __init__(self, session: AsyncSession):
        self.session = session
        
    async def bulk_insert(
        self,
        model,
        items: List[Dict[str, Any]],
        chunk_size: int = 1000
    ) -> int:
        """Bulk insert records"""
        inserted = 0
        
        # Split items into chunks
        for i in range(0, len(items), chunk_size):
            chunk = items[i:i + chunk_size]
            
            # Create model instances
            instances = [model(**item) for item in chunk]
            
            # Add to session
            self.session.add_all(instances)
            
            try:
                await self.session.commit()
                inserted += len(chunk)
            except Exception as e:
                await self.session.rollback()
                logger.error(f"Error in bulk insert: {e}")
                raise
                
        return inserted
        
    async def bulk_update(
        self,
        model,
        items: List[Dict[str, Any]],
        chunk_size: int = 1000
    ) -> int:
        """Bulk update records"""
        from sqlalchemy import update
        updated = 0
        
        # Split items into chunks
        for i in range(0, len(items), chunk_size):
            chunk = items[i:i + chunk_size]
            
            try:
                # Update chunk
                stmt = update(model).where(
                    model.id.in_([item['id'] for item in chunk])
                )
                result = await self.session.execute(stmt)
                updated += result.rowcount
                
                await self.session.commit()
            except Exception as e:
                await self.session.rollback()
                logger.error(f"Error in bulk update: {e}")
                raise
                
        return updated

# Create global instances
db = DatabaseManager()
query_builder = QueryBuilder

async def get_session() -> AsyncGenerator[AsyncSession, None]:
    """Get database session - dependency for FastAPI"""
    async with db.session() as session:
        yield session

__all__ = [
    'db',
    'get_session',
    'DatabaseSession',
    'QueryBuilder',
    'BulkOperations'
]
```

# telegram_bot\core\errors.py

```py
from typing import Optional, Dict, Any
from fastapi import HTTPException, status
import logging
from telegram_bot.core.constants import TEXTS

logger = logging.getLogger(__name__)

class BotError(Exception):
    """Base error class"""
    def __init__(
        self,
        message: str,
        user_message: Optional[Dict[str, str]] = None,
        details: Optional[Dict[str, Any]] = None,
        status_code: int = 500
    ):
        super().__init__(message)
        self.message = message
        self.user_message = user_message or TEXTS
        self.details = details or {}
        self.status_code = status_code
        
    def get_user_message(self, language: str) -> str:
        """Get localized error message"""
        if isinstance(self.user_message, dict):
            return self.user_message.get(language, self.user_message.get('ru', str(self)))
        return str(self)

class ValidationError(BotError):
    """Validation error"""
    def __init__(
        self,
        message: str,
        field: Optional[str] = None,
        details: Optional[Dict] = None
    ):
        super().__init__(
            message=message,
            user_message=TEXTS['validation_error'],
            details={
                'field': field,
                **(details or {})
            },
            status_code=422
        )

class AuthenticationError(BotError):
    """Authentication error"""
    def __init__(self, message: str = "Authentication failed"):
        super().__init__(
            message=message,
            user_message=TEXTS['auth_error'],
            status_code=401
        )

class AuthorizationError(BotError):
    """Authorization error"""
    def __init__(self, message: str = "Permission denied"):
        super().__init__(
            message=message,
            user_message=TEXTS['permission_error'], 
            status_code=403
        )

class PaymentError(BotError):
    """Payment error"""
    def __init__(
        self,
        message: str,
        provider: Optional[str] = None,
        transaction_id: Optional[str] = None
    ):
        super().__init__(
            message=message,
            user_message=TEXTS['payment_error'],
            details={
                'provider': provider,
                'transaction_id': transaction_id
            },
            status_code=402
        )

class NotFoundError(BotError):
    """Not found error"""
    def __init__(self, message: str, resource: Optional[str] = None):
        super().__init__(
            message=message,
            user_message=TEXTS['not_found'],
            details={'resource': resource},
            status_code=404
        )

class RateLimitError(BotError):
    """Rate limit error"""
    def __init__(self, message: str = "Rate limit exceeded"):
        super().__init__(
            message=message,
            user_message=TEXTS['rate_limit'],
            status_code=429
        )

class ServiceUnavailableError(BotError):
    """Service unavailable error"""
    def __init__(self, message: str, service: Optional[str] = None):
        super().__init__(
            message=message,
            user_message=TEXTS['service_unavailable'],
            details={'service': service},
            status_code=503
        )


# Добавляем в файл /telegram_bot/core/errors.py

class DatabaseError(BotError):
    """Database operation error"""
    def __init__(self, message: str = "Database error occurred"):
        super().__init__(
            message=message,
            user_message=TEXTS['database_error'],
            status_code=500
        )

class ConsultationError(BotError):
    """Consultation related error"""
    def __init__(self, message: str = "Consultation error"):
        super().__init__(
            message=message,
            user_message=TEXTS['consultation_error'],
            status_code=400
        )

class PaymentProcessingError(BotError):
    """Payment processing error"""
    def __init__(
        self,
        message: str = "Payment processing failed",
        provider: Optional[str] = None,
        transaction_id: Optional[str] = None
    ):
        super().__init__(
            message=message,
            user_message=TEXTS['payment_error'],
            details={
                'provider': provider,
                'transaction_id': transaction_id
            },
            status_code=402
        )

class QuestionError(BotError):
    """Question related error"""
    def __init__(self, message: str = "Question error"):
        super().__init__(
            message=message,
            user_message=TEXTS['question_error'],
            status_code=400
        )

class AutoAnswerError(BotError):
    """Auto answer generation error"""
    def __init__(self, message: str = "Failed to generate auto answer"):
        super().__init__(
            message=message,
            user_message=TEXTS['auto_answer_error'],
            status_code=500
        )

class ConfigurationError(BotError):
    """Configuration error"""
    def __init__(self, message: str = "Configuration error"):
        super().__init__(
            message=message,
            user_message=TEXTS['system_error'],
            status_code=500
        )

class ServiceUnavailableError(BotError):
    """Service unavailable error"""
    def __init__(self, service: str, message: str = "Service unavailable"):
        super().__init__(
            message=message,
            user_message=TEXTS['service_unavailable'],
            details={'service': service},
            status_code=503
        )

class RateLimitExceededError(BotError):
    """Rate limit exceeded error"""
    def __init__(self, message: str = "Rate limit exceeded"):
        super().__init__(
            message=message,
            user_message=TEXTS['rate_limit'],
            status_code=429
        )

class CacheError(BotError):
    """Cache operation error"""
    def __init__(self, message: str = "Cache error"):
        super().__init__(
            message=message,
            user_message=TEXTS['system_error'],
            status_code=500
        )

class NotificationError(BotError):
    """Notification sending error"""
    def __init__(self, message: str = "Failed to send notification"):
        super().__init__(
            message=message,
            user_message=TEXTS['notification_error'],
            status_code=500
        )



async def error_handler(error: Exception, language: str = 'ru') -> Dict:
    """Global error handler"""
    if isinstance(error, BotError):
        # Log error
        logger.error(
            f"Bot error: {error.message}",
            extra={
                'error_type': type(error).__name__,
                'details': error.details
            }
        )
        
        # Return error response
        return {
            'error': error.message,
            'user_message': error.get_user_message(language),
            'details': error.details,
            'code': error.status_code
        }
        
    # Handle unknown errors
    logger.error(f"Unexpected error: {str(error)}", exc_info=True)
    
    return {
        'error': 'Internal server error',
        'user_message': TEXTS[language]['error'],
        'code': 500
    }

# Export errors and handler
__all__ = [
    'BotError',
    'ValidationError',
    'AuthenticationError', 
    'AuthorizationError',
    'PaymentError',
    'NotFoundError',
    'RateLimitError',
    'ServiceUnavailableError',
    'DatabaseError',
    'ConsultationError',
    'PaymentProcessingError',
    'QuestionError',
    'AutoAnswerError',
    'ConfigurationError',
    'RateLimitExceededError',
    'CacheError',
    'NotificationError',
    'error_handler'
]
```

# telegram_bot\core\logging.py

```py
import logging
import logging.handlers
from datetime import datetime
from pathlib import Path
import json
from pythonjsonlogger import jsonlogger
import sys
from typing import Optional,Dict,Any,Tuple
import graylog
import sentry_sdk

from telegram_bot.core.config import settings

class CustomJsonFormatter(jsonlogger.JsonFormatter):
    """Custom JSON formatter for structured logging"""
    
    def add_fields(self, log_record: Dict[str, Any], record: logging.LogRecord, message_dict: Dict) -> None:
        super().add_fields(log_record, record, message_dict)
        
        # Add basic fields
        log_record['timestamp'] = datetime.utcnow().isoformat()
        log_record['level'] = record.levelname
        log_record['logger'] = record.name
        
        # Add custom fields
        if hasattr(record, 'user_id'):
            log_record['user_id'] = record.user_id
        if hasattr(record, 'request_id'):
            log_record['request_id'] = record.request_id
        if hasattr(record, 'ip_address'):
            log_record['ip_address'] = record.ip_address
            
        # Add error details if present
        if 'exc_info' in message_dict:
            log_record['error'] = {
                'type': record.exc_info[0].__name__ if record.exc_info else None,
                'message': str(record.exc_info[1]) if record.exc_info else None,
                'traceback': self.formatException(record.exc_info) if record.exc_info else None
            }

def setup_logging(
    log_level: str = "INFO",
    log_format: str = "json",
    log_file: Optional[str] = None,
    log_dir: Optional[Path] = None
) -> logging.Logger:
    """Setup application logging with comprehensive configuration"""
    
    # Create logs directory if needed
    if log_dir:
        log_dir.mkdir(parents=True, exist_ok=True)
        if not log_file:
            log_file = log_dir / f"telegram_bot_{datetime.now().strftime('%Y-%m-%d')}.log"
    
    # Configure handlers
    handlers = []
    
    # Console handler
    console_handler = logging.StreamHandler(sys.stdout)
    if log_format == "json":
        formatter = CustomJsonFormatter(
            '%(timestamp)s %(level)s %(name)s %(message)s'
        )
    else:
        formatter = logging.Formatter(
            '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
        )
    console_handler.setFormatter(formatter)
    handlers.append(console_handler)
    
    # File handler
    if log_file:
        file_handler = logging.handlers.RotatingFileHandler(
            log_file,
            maxBytes=10*1024*1024,  # 10MB 
            backupCount=5,
            encoding='utf-8'
        )
        file_handler.setFormatter(formatter)
        handlers.append(file_handler)
    
    # Graylog handler
    if settings.GRAYLOG_HOST:
        graylog_handler = graylog.GELFUDPHandler(
            host=settings.GRAYLOG_HOST,
            port=settings.GRAYLOG_PORT,
            facility=settings.APP_NAME
        )
        handlers.append(graylog_handler)
    
    # Sentry integration
    if settings.SENTRY_DSN:
        sentry_sdk.init(
            dsn=settings.SENTRY_DSN,
            environment=settings.ENVIRONMENT,
            traces_sample_rate=1.0,
            profiles_sample_rate=1.0
        )
    
    # Configure root logger
    logging.basicConfig(
        level=getattr(logging, log_level.upper()),
        handlers=handlers,
        force=True
    )
    
    # Set levels for third-party loggers
    logging.getLogger('aiohttp').setLevel(logging.WARNING)
    logging.getLogger('aiogram').setLevel(logging.INFO)
    logging.getLogger('sqlalchemy').setLevel(logging.WARNING)
    logging.getLogger('urllib3').setLevel(logging.WARNING)
    
    # Create logger
    logger = logging.getLogger('telegram_bot')
    logger.setLevel(getattr(logging, log_level.upper()))
    
    return logger

class LoggerAdapter(logging.LoggerAdapter):
    """Custom logger adapter for adding context"""
    
    def process(self, msg: str, kwargs: Dict[str, Any]) -> Tuple[str, Dict[str, Any]]:
        extra = kwargs.get('extra', {})
        
        # Add context from adapter
        if hasattr(self.extra, 'user_id'):
            extra['user_id'] = self.extra.user_id
        if hasattr(self.extra, 'request_id'):
            extra['request_id'] = self.extra.request_id
            
        kwargs['extra'] = extra
        return msg, kwargs

class AsyncLoggerAdapter(LoggerAdapter):
    """Async logger adapter for coroutines"""
    
    async def alog(
        self,
        level: int,
        msg: str,
        *args,
        **kwargs
    ) -> None:
        """Async logging method"""
        if self.isEnabledFor(level):
            msg, kwargs = self.process(msg, kwargs)
            self.logger._log(level, msg, args, **kwargs)

def get_logger(name: str, **kwargs) -> logging.Logger:
    """Get logger with context"""
    logger = logging.getLogger(name)
    return LoggerAdapter(logger, kwargs)

# Create global logger instance
logger = get_logger(__name__)

__all__ = [
    'setup_logging',
    'get_logger', 
    'logger',
    'LoggerAdapter',
    'AsyncLoggerAdapter'
]
```

# telegram_bot\core\monitoring.py

```py
from prometheus_client import Counter, Histogram, Gauge, Summary
import psutil
from typing import Dict, Any, Optional
import logging
from datetime import datetime, timedelta
from sqlalchemy import select, func
import json
import asyncio
from telegram_bot.core.database import get_session
from telegram_bot.models import User, Question, Consultation, Payment
from telegram_bot.utils.cache import cache

logger = logging.getLogger(__name__)

class MetricsManager:
    """Comprehensive metrics management system"""
    
    def __init__(self):
        # System metrics
        self.cpu_usage = Gauge(
            'system_cpu_usage',
            'System CPU usage percentage'
        )
        self.memory_usage = Gauge(
            'system_memory_usage_bytes',
            'System memory usage in bytes'
        )
        self.disk_usage = Gauge(
            'system_disk_usage_bytes',
            'System disk usage in bytes'
        )
        
        # Application metrics
        self.requests_total = Counter(
            'app_requests_total',
            'Total HTTP requests',
            ['method', 'endpoint']
        )
        self.request_duration = Histogram(
            'app_request_duration_seconds',
            'HTTP request duration in seconds',
            ['method', 'endpoint']
        )
        
        # Bot metrics
        self.bot_messages = Counter(
            'bot_messages_total',
            'Total bot messages',
            ['type']
        )
        self.bot_callbacks = Counter(
            'bot_callbacks_total',
            'Total bot callbacks'
        )
        self.bot_errors = Counter(
            'bot_errors_total',
            'Total bot errors',
            ['type']
        )
        
        # Business metrics
        self.questions_total = Counter(
            'bot_questions_total',
            'Total questions asked',
            ['language']
        )
        self.answers_total = Counter(
            'bot_answers_total',
            'Total answers given',
            ['type']
        )
        self.consultations_total = Counter(
            'bot_consultations_total',
            'Total consultations',
            ['status']
        )
        self.payments_total = Counter(
            'bot_payments_total',
            'Total payments',
            ['status', 'provider']  
        )
        
        # Performance metrics
        self.response_times = Histogram(
            'bot_response_time_seconds',
            'Bot response time in seconds'
        )
        self.db_query_duration = Histogram(
            'bot_db_query_duration_seconds',
            'Database query duration in seconds'
        )
        self.cache_operations = Counter(
            'bot_cache_operations_total',
            'Total cache operations',
            ['operation', 'status']
        )
        
        # Start background collection
        asyncio.create_task(self._collect_metrics())
        
    async def _collect_metrics(self):
        """Periodically collect system metrics"""
        while True:
            try:
                await self.collect_system_metrics()
                await self.collect_business_metrics()
                await asyncio.sleep(60)  # Collect every minute
            except Exception as e:
                logger.error(f"Error collecting metrics: {e}")
                await asyncio.sleep(60)
                
    async def collect_system_metrics(self):
        """Collect system resource metrics"""
        try:
            # CPU metrics
            cpu_percent = psutil.cpu_percent()
            self.cpu_usage.set(cpu_percent)
            
            # Memory metrics
            memory = psutil.virtual_memory()
            self.memory_usage.set(memory.used)
            
            # Disk metrics
            disk = psutil.disk_usage('/')
            self.disk_usage.set(disk.used)
            
        except Exception as e:
            logger.error(f"Error collecting system metrics: {e}")
            
    async def collect_business_metrics(self):
        """Collect business metrics"""
        try:
            async with get_session() as session:
                # Questions metrics
                questions = await session.execute(
                    select(
                        Question.language,
                        func.count(Question.id)
                    ).group_by(Question.language)
                )
                for lang, count in questions:
                    self.questions_total.labels(language=lang).inc(count)
                
                # Consultations metrics
                consultations = await session.execute(
                    select(
                        Consultation.status,
                        func.count(Consultation.id)
                    ).group_by(Consultation.status)
                )
                for status, count in consultations:
                    self.consultations_total.labels(status=status.value).inc(count)
                    
                # Payments metrics
                payments = await session.execute(
                    select(
                        Payment.status,
                        Payment.provider,
                        func.count(Payment.id)
                    ).group_by(Payment.status, Payment.provider)
                )
                for status, provider, count in payments:
                    self.payments_total.labels(
                        status=status.value,
                        provider=provider.value
                    ).inc(count)
                    
        except Exception as e:
            logger.error(f"Error collecting business metrics: {e}")
    
    def track_request(self, method: str, endpoint: str, duration: float):
        """Track HTTP request"""
        self.requests_total.labels(
            method=method,
            endpoint=endpoint
        ).inc()
        
        self.request_duration.labels(
            method=method,
            endpoint=endpoint
        ).observe(duration)
        
    def track_bot_message(self, message_type: str):
        """Track bot message"""
        self.bot_messages.labels(type=message_type).inc()
        
    def track_bot_callback(self):
        """Track bot callback"""
        self.bot_callbacks.inc()
        
    def track_bot_error(self, error_type: str):
        """Track bot error"""
        self.bot_errors.labels(type=error_type).inc()
        
    def track_response_time(self, duration: float):
        """Track bot response time"""
        self.response_times.observe(duration)
        
    def track_db_query(self, duration: float):
        """Track database query duration"""
        self.db_query_duration.observe(duration)
        
    def track_cache(self, operation: str, hit: bool = None):
        """Track cache operation"""
        status = 'hit' if hit else 'miss' if hit is not None else 'unknown'
        self.cache_operations.labels(
            operation=operation,
            status=status
        ).inc()

# Create metrics manager instance
metrics_manager = MetricsManager()

__all__ = ['metrics_manager']
```

# telegram_bot\core\security.py

```py
from datetime import datetime, timedelta
from typing import Optional, Dict, Any, List
from jose import JWTError, jwt
from passlib.context import CryptContext
from fastapi import HTTPException, status, Security
from fastapi.security import OAuth2PasswordBearer
import secrets
import hashlib
import hmac
from telegram_bot.core.config import settings
from telegram_bot.core.constants import CACHE_TIMEOUTS
import jwt
import pyotp
from fastapi.security import HTTPBearer
from telegram_bot.core.cache import cache_service 
from telegram_bot.core.cache import cache_service as cache


# Password hashing
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

# OAuth2 scheme
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="auth/token")




security = HTTPBearer()

class SecurityManager:
    """Enhanced security manager"""
    
    def __init__(self):
        self.cache = cache_service
        self._rate_limits = {
            'default': (100, 60),  # 100 requests per minute
            'auth': (5, 60),       # 5 login attempts per minute
            'payment': (10, 60)    # 10 payment attempts per minute
        }
        
    async def rate_limit(
        self,
        key: str,
        limit_type: str = 'default'
    ) -> bool:
        """Check rate limit"""
        rate_key = f"rate_limit:{limit_type}:{key}"
        
        # Get current count
        count = await self.cache.get(rate_key) or 0
        limit, period = self._rate_limits.get(limit_type, (100, 60))
        
        if count >= limit:
            return False
            
        # Increment counter
        pipe = self.cache.redis.pipeline()
        pipe.incr(rate_key)
        pipe.expire(rate_key, period)
        await pipe.execute()
        
        return True
        
    def create_access_token(
        self,
        data: Dict[str, Any],
        expires_delta: Optional[timedelta] = None
    ) -> str:
        """Create JWT token"""
        to_encode = data.copy()
        expire = datetime.utcnow() + (
            expires_delta if expires_delta
            else timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)
        )
        to_encode.update({"exp": expire})
        
        return jwt.encode(
            to_encode,
            settings.SECRET_KEY.get_secret_value(),
            algorithm=settings.JWT_ALGORITHM
        )
        
    def verify_token(self, token: str) -> Dict[str, Any]:
        """Verify JWT token"""
        try:
            payload = jwt.decode(
                token,
                settings.SECRET_KEY.get_secret_value(),
                algorithms=[settings.JWT_ALGORITHM]
            )
            return payload
        except jwt.PyJWTError:
            raise HTTPException(
                status_code=401,
                detail="Could not validate credentials"
            )
            
    def hash_password(self, password: str) -> str:
        """Hash password"""
        return bcrypt.hashpw(
            password.encode(),
            bcrypt.gensalt()
        ).decode()
        
    def verify_password(
        self,
        plain_password: str,
        hashed_password: str
    ) -> bool:
        """Verify password"""
        return bcrypt.checkpw(
            plain_password.encode(),
            hashed_password.encode()
        )
        
    async def generate_2fa_secret(self, user_id: int) -> str:
        """Generate 2FA secret"""
        secret = pyotp.random_base32()
        await self.cache.set(
            f"2fa_secret:{user_id}",
            secret,
            timeout=300  # 5 minutes
        )
        return secret
        
    def verify_2fa_code(
        self,
        secret: str,
        code: str
    ) -> bool:
        """Verify 2FA code"""
        totp = pyotp.TOTP(secret)
        return totp.verify(code)
        
    async def block_ip(
        self,
        ip: str,
        duration: int = 3600
    ) -> None:
        """Block IP address"""
        await self.cache.set(
            f"blocked_ip:{ip}",
            datetime.utcnow().isoformat(),
            timeout=duration
        )
        
    async def is_ip_blocked(self, ip: str) -> bool:
        """Check if IP is blocked"""
        return await self.cache.exists(f"blocked_ip:{ip}")
        
    def validate_request_signature(
        self,
        signature: str,
        data: Dict[str, Any],
        secret: str
    ) -> bool:
        """Validate request signature"""
        import hmac
        import hashlib
        
        # Create signature
        message = '&'.join(f"{k}={v}" for k, v in sorted(data.items()))
        expected = hmac.new(
            secret.encode(),
            message.encode(),
            hashlib.sha256
        ).hexdigest()
        
        return hmac.compare_digest(signature, expected)

# Create global instance
security_manager = SecurityManager()

async def get_current_user(
    token: str = Security(security)
) -> Dict[str, Any]:
    """Get current user from token"""
    return security_manager.verify_token(token.credentials)

__all__ = [
    'security_manager',
    'get_current_user',
    'OAuth2PasswordBearer'
]

class RoleChecker:
    """Role-based access control checker"""
    
    def __init__(self, required_roles: List[str]):
        self.required_roles = required_roles
    
    async def __call__(self, user: Dict = Security(get_current_user)) -> bool:
        if not user.get('roles'):
            return False
        return any(role in user['roles'] for role in self.required_roles)

class PermissionChecker:
    """Permission-based access control checker"""
    
    def __init__(self, required_permission: str):
        self.required_permission = required_permission
    
    async def __call__(self, user: Dict = Security(get_current_user)) -> bool:
        if not user.get('permissions'):
            return False
        return self.required_permission in user['permissions']

class SecurityUtils:
    """Security utility functions"""
    
    @staticmethod
    def generate_strong_password(length: int = 12) -> str:
        """Generate strong random password"""
        import string
        alphabet = string.ascii_letters + string.digits + string.punctuation
        while True:
            password = ''.join(secrets.choice(alphabet) for _ in range(length))
            if (any(c.islower() for c in password)
                    and any(c.isupper() for c in password)
                    and any(c.isdigit() for c in password)
                    and any(c in string.punctuation for c in password)):
                return password
    
    @staticmethod
    def hash_data(data: str) -> str:
        """Hash data using SHA-256"""
        return hashlib.sha256(data.encode()).hexdigest()
    
    @staticmethod
    def generate_random_token(length: int = 32) -> str:
        """Generate random secure token"""
        return secrets.token_urlsafe(length)
    
    @staticmethod
    def sanitize_input(value: str) -> str:
        """Sanitize input string"""
        import html
        return html.escape(value)

class AdminRequired:
    """Admin role requirement decorator"""
    
    def __init__(self):
        self.checker = RoleChecker(['ADMIN'])
    
    async def __call__(self, user: Dict = Security(get_current_user)) -> bool:
        return await self.checker(user)

class ModeratorRequired:
    """Moderator role requirement decorator"""
    
    def __init__(self):
        self.checker = RoleChecker(['ADMIN', 'MODERATOR'])
    
    async def __call__(self, user: Dict = Security(get_current_user)) -> bool:
        return await self.checker(user)

class RateLimiter:
    """Rate limiting helper"""
    
    def __init__(
        self,
        requests: int,
        window: int
    ):
        self.requests = requests
        self.window = window
    
    async def is_allowed(self, key: str) -> bool:
        """Check if request is allowed"""
        current = await cache.get(f"rate_limit:{key}")
        if not current:
            await cache.set(f"rate_limit:{key}", 1, timeout=self.window)
            return True
        
        if int(current) >= self.requests:
            return False
            
        await cache.increment(f"rate_limit:{key}")
        return True

class IPBanManager:
    """IP ban management"""
    
    @staticmethod
    async def ban_ip(ip: str, reason: str, duration: int = 86400) -> None:
        """Ban IP address"""
        await cache.set(
            f"banned_ip:{ip}",
            {
                'reason': reason,
                'banned_at': datetime.utcnow().isoformat(),
                'duration': duration
            },
            timeout=duration
        )
    
    @staticmethod
    async def unban_ip(ip: str) -> None:
        """Unban IP address"""
        await cache.delete(f"banned_ip:{ip}")
    
    @staticmethod
    async def is_banned(ip: str) -> bool:
        """Check if IP is banned"""
        return await cache.exists(f"banned_ip:{ip}")
    
    @staticmethod
    async def get_ban_info(ip: str) -> Optional[Dict]:
        """Get IP ban information"""
        return await cache.get(f"banned_ip:{ip}")

class TwoFactorAuth:
    """Two-factor authentication helper"""
    
    @staticmethod
    async def generate_code(user_id: int) -> str:
        """Generate 2FA code"""
        code = ''.join(secrets.choice('0123456789') for _ in range(6))
        
        await cache.set(
            f"2fa_code:{user_id}",
            {
                'code': code,
                'attempts': 0,
                'generated_at': datetime.utcnow().isoformat()
            },
            timeout=300  # 5 minutes
        )
        
        return code
    
    @staticmethod
    async def verify_code(user_id: int, code: str) -> bool:
        """Verify 2FA code"""
        stored = await cache.get(f"2fa_code:{user_id}")
        if not stored:
            return False
            
        # Increment attempts
        stored['attempts'] += 1
        await cache.set(f"2fa_code:{user_id}", stored, timeout=300)
        
        # Check attempts
        if stored['attempts'] >= 3:
            await cache.delete(f"2fa_code:{user_id}")
            return False
            
        return stored['code'] == code

# Create utility instances
security_utils = SecurityUtils()
rate_limiter = RateLimiter(100, 60)  # 100 requests per minute
ip_ban_manager = IPBanManager()
two_factor_auth = TwoFactorAuth()

# Additional exports
__all__ += [
    'RoleChecker',
    'PermissionChecker',
    'SecurityUtils',
    'AdminRequired',
    'ModeratorRequired',
    'RateLimiter',
    'IPBanManager',
    'TwoFactorAuth',
    'security_utils',
    'rate_limiter',
    'ip_ban_manager',
    'two_factor_auth'
]
```

# telegram_bot\main.py

```py
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
```

# telegram_bot\models\__init__.py

```py
from telegram_bot.models.base import Base, BaseModel, TimestampMixin
from telegram_bot.models.users import (
    User,
    UserEvent,
    UserNotification,
    UserRole,
    UserStatus
)
from telegram_bot.models.questions import (
    Question,
    Answer, 
    QuestionFeedback,
    AnswerFeedback,
    QuestionCategory,
    QuestionStatus
)
from telegram_bot.models.consultations import (
    Consultation,
    ConsultationFeedback,
    Payment,
    ConsultationType,
    ConsultationStatus,
    PaymentStatus,
    PaymentProvider
)
from telegram_bot.models.faq import (
    FAQ,
    FAQFeedback, 
    FAQCategory
)
from sqlalchemy.orm import relationship
# Configure relationships
Question.user = relationship('User', back_populates='questions')
Answer.question = relationship('Question', back_populates='answers')
Consultation.user = relationship('User', back_populates='consultations')
Payment.consultation = relationship('Consultation', back_populates='payments')
FAQ.category = relationship('FAQCategory', back_populates='faqs')

__all__ = [
    'Base',
    'BaseModel',
    'TimestampMixin',
    'User',
    'UserEvent',
    'UserNotification',
    'UserRole',
    'UserStatus',
    'Question',
    'Answer',
    'QuestionFeedback',
    'AnswerFeedback',
    'QuestionCategory',
    'QuestionStatus',
    'Consultation',
    'ConsultationFeedback',
    'Payment',
    'ConsultationType',
    'ConsultationStatus', 
    'PaymentStatus',
    'PaymentProvider',
    'FAQ',
    'FAQFeedback',
    'FAQCategory'
]
```

# telegram_bot\models\base.py

```py
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
```

# telegram_bot\models\consultations.py

```py
from sqlalchemy import (
    Column, String, Integer, Boolean, ForeignKey, Text, 
    Numeric, DateTime, Enum as SQLEnum, Index, UniqueConstraint,
    CheckConstraint
)
from sqlalchemy.orm import relationship
from sqlalchemy.dialects.postgresql import JSONB
from enum import Enum
from datetime import datetime, timedelta

from telegram_bot.models.base import BaseModel, SoftDeleteMixin, AuditMixin, MetadataMixin

class ConsultationType(str, Enum):
    ONLINE = 'online'
    OFFICE = 'office'

class ConsultationStatus(str, Enum):
    PENDING = 'pending'
    CONFIRMED = 'confirmed'
    PAID = 'paid'
    SCHEDULED = 'scheduled'
    IN_PROGRESS = 'in_progress'
    COMPLETED = 'completed'
    CANCELLED = 'cancelled'
    REFUNDED = 'refunded'

class PaymentStatus(str, Enum):
    PENDING = 'pending'
    PROCESSING = 'processing'
    COMPLETED = 'completed'
    FAILED = 'failed'
    CANCELLED = 'cancelled'
    REFUNDED = 'refunded'

class PaymentProvider(str, Enum):
    CLICK = 'click'
    PAYME = 'payme'
    UZUM = 'uzum'

class Consultation(BaseModel, SoftDeleteMixin, AuditMixin, MetadataMixin):
    """Enhanced consultation model with complete tracking"""
    __tablename__ = 'consultations'

    # Core fields
    user_id = Column(Integer, ForeignKey('users.id', ondelete='CASCADE'), nullable=False)
    type = Column(SQLEnum(ConsultationType), nullable=False)
    status = Column(SQLEnum(ConsultationStatus), default=ConsultationStatus.PENDING)
    category = Column(String)
    language = Column(String(2), nullable=False)

    # Scheduling
    scheduled_time = Column(DateTime(timezone=True))
    duration = Column(Integer, default=60)  # minutes
    timezone = Column(String, default='Asia/Tashkent')
    reschedule_count = Column(Integer, default=0)
    rescheduled_from = Column(DateTime(timezone=True))
    cancellation_deadline = Column(DateTime(timezone=True))

    # Payment
    amount = Column(Numeric(10, 2), nullable=False)
    currency = Column(String, default='UZS', nullable=False)
    is_paid = Column(Boolean, default=False)
    paid_at = Column(DateTime(timezone=True))
    refunded_at = Column(DateTime(timezone=True))
    refund_amount = Column(Numeric(10, 2))
    refund_reason = Column(String)

    # Contact info
    phone_number = Column(String, nullable=False)
    email = Column(String)
    problem_description = Column(Text, nullable=False)
    additional_notes = Column(Text)

    # Meeting details
    meeting_url = Column(String)
    meeting_id = Column(String)
    meeting_password = Column(String)
    office_location = Column(String)
    office_room = Column(String)

    # Consultation details
    lawyer_id = Column(Integer, ForeignKey('users.id', ondelete='SET NULL'))
    lawyer_notes = Column(Text)
    summary = Column(Text)
    recording_url = Column(String)
    documents = Column(JSONB, default=[])

    # Rating and feedback
    rating = Column(Integer)
    client_feedback = Column(Text)
    lawyer_feedback = Column(Text)
    has_feedback = Column(Boolean, default=False)

    # Tracking
    completed_at = Column(DateTime(timezone=True))
    cancelled_at = Column(DateTime(timezone=True))
    cancellation_reason = Column(String)
    last_reminder_sent = Column(DateTime(timezone=True))
    reminder_count = Column(Integer, default=0)

    # Relationships
    user = relationship('User', foreign_keys=[user_id], back_populates='consultations')
    lawyer = relationship('User', foreign_keys=[lawyer_id])
    payments = relationship('Payment', back_populates='consultation', cascade='all, delete-orphan')
    feedback = relationship('ConsultationFeedback', back_populates='consultation', cascade='all, delete-orphan')

    # Constraints and Indexes
    __table_args__ = (
        CheckConstraint('amount >= 0', name='positive_amount'),
        CheckConstraint(
            "status != 'completed' OR (rating IS NOT NULL AND completed_at IS NOT NULL)",
            name='completed_consultation_check'
        ),
        Index('ix_consultations_user_id', user_id),
        Index('ix_consultations_lawyer_id', lawyer_id),
        Index('ix_consultations_status', status),
        Index('ix_consultations_type', type),
        Index('ix_consultations_scheduled_time', scheduled_time),
        Index('ix_consultations_completed_at', completed_at),
    )

    @property
    def can_reschedule(self) -> bool:
        """Check if consultation can be rescheduled"""
        if not self.scheduled_time:
            return False
        return (
            self.status in [ConsultationStatus.SCHEDULED, ConsultationStatus.CONFIRMED] and
            self.reschedule_count < 3 and
            datetime.utcnow() + timedelta(hours=24) < self.scheduled_time
        )

    @property
    def can_cancel(self) -> bool:
        """Check if consultation can be cancelled"""
        if not self.scheduled_time:
            return True
        return (
            self.status not in [ConsultationStatus.COMPLETED, ConsultationStatus.CANCELLED] and
            (not self.cancellation_deadline or datetime.utcnow() < self.cancellation_deadline)
        )

    def mark_paid(self, payment_id: str = None) -> None:
        """Mark consultation as paid"""
        self.is_paid = True
        self.paid_at = datetime.utcnow()
        self.status = ConsultationStatus.PAID
        if payment_id:
            self.metadata['payment_id'] = payment_id

    def schedule(self, scheduled_time: datetime) -> None:
        """Schedule consultation"""
        if self.scheduled_time:
            self.reschedule_count += 1
            self.rescheduled_from = self.scheduled_time
        self.scheduled_time = scheduled_time
        self.status = ConsultationStatus.SCHEDULED
        self.cancellation_deadline = scheduled_time - timedelta(hours=24)

class ConsultationFeedback(BaseModel):
    """Consultation feedback model"""
    __tablename__ = 'consultation_feedback'

    consultation_id = Column(Integer, ForeignKey('consultations.id', ondelete='CASCADE'), nullable=False)
    user_id = Column(Integer, ForeignKey('users.id', ondelete='CASCADE'), nullable=False)
    rating = Column(Integer, nullable=False)
    feedback_text = Column(Text)
    feedback_type = Column(String, default='client')  # client/lawyer
    is_public = Column(Boolean, default=True)
    metadata = Column(JSONB, default={})

    # Specific feedback fields
    professionalism_rating = Column(Integer)
    communication_rating = Column(Integer)
    knowledge_rating = Column(Integer)
    punctuality_rating = Column(Integer)
    value_rating = Column(Integer)

    # Relationships
    consultation = relationship('Consultation', back_populates='feedback')
    user = relationship('User', back_populates='feedback')

    # Indexes
    __table_args__ = (
        CheckConstraint('rating >= 1 AND rating <= 5', name='valid_rating'),
        Index('ix_consultation_feedback_consultation_id', consultation_id),
        Index('ix_consultation_feedback_user_id', user_id),
        UniqueConstraint('consultation_id', 'user_id', 'feedback_type', name='uq_consultation_feedback'),
    )

class Payment(BaseModel, AuditMixin):
    """Enhanced payment model with full transaction tracking"""
    __tablename__ = 'payments'

    # Core fields
    consultation_id = Column(Integer, ForeignKey('consultations.id', ondelete='CASCADE'), nullable=False)
    user_id = Column(Integer, ForeignKey('users.id', ondelete='CASCADE'), nullable=False)
    amount = Column(Numeric(10, 2), nullable=False)
    currency = Column(String, default='UZS', nullable=False)
    provider = Column(SQLEnum(PaymentProvider), nullable=False)
    status = Column(SQLEnum(PaymentStatus), default=PaymentStatus.PENDING)

    # Transaction details
    transaction_id = Column(String)
    provider_transaction_id = Column(String)
    provider_payment_url = Column(String)
    provider_response = Column(JSONB, default={})
    payment_method = Column(String)

    # Refund details
    refund_amount = Column(Numeric(10, 2))
    refund_reason = Column(String)
    refund_transaction_id = Column(String)
    refunded_at = Column(DateTime(timezone=True))

    # Additional info
    error_message = Column(String)
    metadata = Column(JSONB, default={})

    # Relationships
    consultation = relationship('Consultation', back_populates='payments')
    user = relationship('User', back_populates='payments')

    # Indexes and Constraints
    __table_args__ = (
        CheckConstraint('amount > 0', name='positive_payment_amount'),
        Index('ix_payments_consultation_id', consultation_id),
        Index('ix_payments_user_id', user_id),
        Index('ix_payments_status', status),
        Index('ix_payments_transaction_id', transaction_id),
        Index('ix_payments_provider_transaction_id', provider_transaction_id),
        UniqueConstraint('provider_transaction_id', 'provider', name='uq_provider_transaction'),
    )

    @property
    def is_refundable(self) -> bool:
        """Check if payment can be refunded"""
        return (
            self.status == PaymentStatus.COMPLETED and
            not self.refund_amount and
            (datetime.utcnow() - self.created_at).days <= 30
        )

    def process_refund(
        self,
        amount: Numeric,
        reason: str,
        transaction_id: str = None
    ) -> None:
        """Process payment refund"""
        if not self.is_refundable:
            raise ValueError("Payment cannot be refunded")
            
        self.status = PaymentStatus.REFUNDED
        self.refund_amount = amount
        self.refund_reason = reason
        self.refund_transaction_id = transaction_id
        self.refunded_at = datetime.utcnow()
        self.metadata['refund'] = {
            'amount': str(amount),
            'reason': reason,
            'transaction_id': transaction_id,
            'processed_at': datetime.utcnow().isoformat()
        }

# Export models
__all__ = [
    'Consultation',
    'ConsultationFeedback',
    'Payment',
    'ConsultationType',
    'ConsultationStatus',
    'PaymentStatus',
    'PaymentProvider'
]
```

# telegram_bot\models\faq.py

```py
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
```

# telegram_bot\models\notifications.py

```py
from sqlalchemy import Column, String, Integer, Boolean, JSON, ForeignKey, Enum as SQLEnum, DateTime, Text
from sqlalchemy.orm import relationship
from sqlalchemy.dialects.postgresql import JSONB
from enum import Enum as PyEnum
from datetime import datetime

from telegram_bot.models.base import BaseModel, TimestampMixin, MetadataMixin

class NotificationType(str, PyEnum):
    SYSTEM = 'system'
    QUESTION = 'question'
    CONSULTATION = 'consultation'
    PAYMENT = 'payment'
    MARKETING = 'marketing'
    REMINDER = 'reminder'
    SUPPORT = 'support'

class NotificationStatus(str, PyEnum):
    PENDING = 'pending'
    SENT = 'sent'
    DELIVERED = 'delivered'
    READ = 'read'
    FAILED = 'failed'
    CANCELLED = 'cancelled'

class NotificationPriority(str, PyEnum):
    LOW = 'low'
    MEDIUM = 'medium'
    HIGH = 'high'
    URGENT = 'urgent'

class Notification(BaseModel, TimestampMixin, MetadataMixin):
    """User notification model with templating support"""
    __tablename__ = 'notifications'
    
    user_id = Column(Integer, ForeignKey('users.id', ondelete='CASCADE'), nullable=False)
    template_id = Column(Integer, ForeignKey('notification_templates.id'), nullable=True)
    
    type = Column(SQLEnum(NotificationType), nullable=False)
    priority = Column(SQLEnum(NotificationPriority), default=NotificationPriority.MEDIUM)
    status = Column(SQLEnum(NotificationStatus), default=NotificationStatus.PENDING)
    
    title = Column(String, nullable=False)
    message = Column(Text, nullable=False)
    
    scheduled_for = Column(DateTime(timezone=True), nullable=True)
    sent_at = Column(DateTime(timezone=True), nullable=True)
    delivered_at = Column(DateTime(timezone=True), nullable=True)
    read_at = Column(DateTime(timezone=True), nullable=True)
    
    error_message = Column(String, nullable=True)
    retry_count = Column(Integer, default=0)
    
    data = Column(JSONB, default={}, nullable=False)
    
    # Relationships
    user = relationship('User', back_populates='notifications')
    template = relationship('NotificationTemplate', back_populates='notifications')
    
    def mark_sent(self) -> None:
        """Mark notification as sent"""
        self.status = NotificationStatus.SENT
        self.sent_at = datetime.utcnow()
        
    def mark_delivered(self) -> None:
        """Mark notification as delivered"""
        self.status = NotificationStatus.DELIVERED
        self.delivered_at = datetime.utcnow()
        
    def mark_read(self) -> None:
        """Mark notification as read"""
        self.status = NotificationStatus.READ
        self.read_at = datetime.utcnow()
        
    def mark_failed(self, error: str) -> None:
        """Mark notification as failed"""
        self.status = NotificationStatus.FAILED
        self.error_message = error
        self.retry_count += 1

class NotificationTemplate(BaseModel, TimestampMixin):
    """Notification template model with localization support"""
    __tablename__ = 'notification_templates'
    
    name = Column(String, unique=True, nullable=False)
    description = Column(Text)
    
    title_template_uz = Column(Text, nullable=False)
    title_template_ru = Column(Text, nullable=False)
    
    message_template_uz = Column(Text, nullable=False)
    message_template_ru = Column(Text, nullable=False)
    
    type = Column(SQLEnum(NotificationType), nullable=False)
    priority = Column(SQLEnum(NotificationPriority), default=NotificationPriority.MEDIUM)
    
    is_active = Column(Boolean, default=True)
    metadata = Column(JSONB, default={})
    
    # Relationships
    notifications = relationship('Notification', back_populates='template')
    
    def render(self, language: str, data: dict) -> tuple[str, str]:
        """Render notification title and message from template"""
        title_template = getattr(self, f'title_template_{language}')
        message_template = getattr(self, f'message_template_{language}')
        
        try:
            title = title_template.format(**data)
            message = message_template.format(**data)
            return title, message
        except KeyError as e:
            raise ValueError(f"Missing template data key: {e}")

# Export models
__all__ = [
    'Notification',
    'NotificationTemplate',
    'NotificationType',
    'NotificationStatus',
    'NotificationPriority'
]
```

# telegram_bot\models\payments.py

```py
from sqlalchemy import Column, Integer, String, Enum as SQLEnum, Numeric, JSON, ForeignKey, Index
from sqlalchemy.orm import relationship
from enum import Enum as PyEnum
from datetime import datetime

from telegram_bot.models.base import TimeStampedBase, MetadataMixin

class PaymentProvider(str, PyEnum):
    CLICK = 'click'
    PAYME = 'payme'
    UZUM = 'uzum'

class PaymentStatus(str, PyEnum):
    PENDING = 'pending'
    PROCESSING = 'processing'
    COMPLETED = 'completed'
    FAILED = 'failed'
    CANCELLED = 'cancelled'
    REFUNDED = 'refunded'

class PaymentType(str, PyEnum):
    CONSULTATION = 'consultation'
    SUBSCRIPTION = 'subscription'
    OTHER = 'other'

class Payment(TimeStampedBase, MetadataMixin):
    """Enhanced payment model with complete transaction tracking"""
    __tablename__ = 'payments'
    
    # Core fields
    user_id = Column(Integer, ForeignKey('users.id', ondelete='CASCADE'), nullable=False)
    consultation_id = Column(Integer, ForeignKey('consultations.id', ondelete='CASCADE'), nullable=True)
    
    # Payment details
    amount = Column(Numeric(10, 2), nullable=False)
    currency = Column(String, default='UZS', nullable=False)
    provider = Column(SQLEnum(PaymentProvider), nullable=False)
    type = Column(SQLEnum(PaymentType), default=PaymentType.CONSULTATION)
    status = Column(SQLEnum(PaymentStatus), default=PaymentStatus.PENDING)
    
    # Provider details
    provider_transaction_id = Column(String)
    provider_payment_url = Column(String)
    provider_response = Column(JSON, default={})
    
    # Refund details
    refund_amount = Column(Numeric(10, 2))
    refund_reason = Column(String)
    refund_transaction_id = Column(String)
    
    # Relationships
    user = relationship("User", back_populates="payments")
    consultation = relationship("Consultation", back_populates="payments")
    
    # Indexes
    __table_args__ = (
        Index('idx_payment_user', 'user_id'),
        Index('idx_payment_consultation', 'consultation_id'),
        Index('idx_payment_status', 'status'),
        Index('idx_payment_provider', 'provider'),
        Index('idx_payment_transaction', 'provider_transaction_id'),
    )
    
    @property
    def is_refundable(self) -> bool:
        """Check if payment can be refunded"""
        return (
            self.status == PaymentStatus.COMPLETED and
            not self.refund_amount and
            not self.metadata.get('no_refund', False)
        )
        
    def complete(self, transaction_id: str) -> None:
        """Complete payment"""
        self.status = PaymentStatus.COMPLETED
        self.provider_transaction_id = transaction_id
        self.metadata['completed_at'] = datetime.utcnow().isoformat()
        
    def fail(self, error: str = None) -> None:
        """Mark payment as failed"""
        self.status = PaymentStatus.FAILED
        if error:
            self.metadata['error'] = error
        self.metadata['failed_at'] = datetime.utcnow().isoformat()
        
    def cancel(self, reason: str = None) -> None:
        """Cancel payment"""
        self.status = PaymentStatus.CANCELLED
        if reason:
            self.metadata['cancellation_reason'] = reason
        self.metadata['cancelled_at'] = datetime.utcnow().isoformat()
        
    def refund(
        self,
        amount: Numeric,
        reason: str = None,
        transaction_id: str = None
    ) -> None:
        """Refund payment"""
        if not self.is_refundable:
            raise ValueError("Payment cannot be refunded")
            
        self.status = PaymentStatus.REFUNDED
        self.refund_amount = amount
        self.refund_reason = reason
        self.refund_transaction_id = transaction_id
        self.metadata['refunded_at'] = datetime.utcnow().isoformat()
```

# telegram_bot\models\questions.py

```py
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
```

# telegram_bot\models\users.py

```py
from sqlalchemy import (
    Column, String, BigInteger, Boolean, DateTime, 
    Integer, ForeignKey, Enum as SQLEnum, Index,
    Table, UniqueConstraint, Text, Float
)
from sqlalchemy.orm import relationship
from sqlalchemy.dialects.postgresql import ARRAY, JSONB
from enum import Enum
from datetime import datetime

from telegram_bot.models.base import BaseModel, SoftDeleteMixin, AuditMixin, MetadataMixin

class UserRole(str, Enum):
    USER = 'USER'
    ADMIN = 'ADMIN'
    SUPPORT = 'SUPPORT'
    MODERATOR = 'MODERATOR'

class UserStatus(str, Enum):
    ACTIVE = 'ACTIVE'
    BLOCKED = 'BLOCKED'
    SUSPENDED = 'SUSPENDED'
    DELETED = 'DELETED'

class User(BaseModel, SoftDeleteMixin, AuditMixin, MetadataMixin):
    """Enhanced user model with complete profile and security"""
    __tablename__ = 'users'

    # Core fields
    telegram_id = Column(BigInteger, unique=True, nullable=False)
    username = Column(String)
    full_name = Column(String)
    phone_number = Column(String)
    email = Column(String)
    language = Column(String(2), default='uz', nullable=False)
    
    # Security and authentication
    password_hash = Column(String)
    is_active = Column(Boolean, default=True, nullable=False)
    is_verified = Column(Boolean, default=False, nullable=False)
    is_blocked = Column(Boolean, default=False, nullable=False)
    block_reason = Column(String)
    
    # Status and activity
    status = Column(SQLEnum(UserStatus), default=UserStatus.ACTIVE, nullable=False)
    last_active = Column(DateTime(timezone=True))
    last_login = Column(DateTime(timezone=True))
    
    # Roles and permissions
    roles = Column(ARRAY(String), default=['USER'], nullable=False)
    permissions = Column(ARRAY(String), default=[])
    
    # Settings and preferences
    settings = Column(JSONB, default={}, nullable=False)
    notification_preferences = Column(JSONB, default={
        'questions': True,
        'consultations': True,
        'marketing': True,
        'support': True
    }, nullable=False)
    
    # Statistics and metrics
    metrics = Column(JSONB, default={
        'questions_asked': 0,
        'consultations_completed': 0,
        'total_spent': 0,
        'avg_rating': 0
    }, nullable=False)

    # Address and contact info
    region = Column(String)
    city = Column(String)
    address = Column(Text)
    additional_contacts = Column(JSONB, default={})

    # Audit fields
    registration_ip = Column(String)
    registration_device = Column(String)
    last_ip = Column(String)
    last_device = Column(String)
    login_attempts = Column(Integer, default=0)
    
    # Social network links
    social_networks = Column(JSONB, default={})
    
    # Analytics data
    analytics = Column(JSONB, default={
        'visits': [],
        'actions': [],
        'preferences': {}
    })

    # Security settings
    two_factor_enabled = Column(Boolean, default=False)
    two_factor_secret = Column(String)
    backup_codes = Column(ARRAY(String), default=[])

    # Relationships
    questions = relationship('Question', back_populates='user', lazy='dynamic')
    answers = relationship('Answer', back_populates='user', lazy='dynamic')
    consultations = relationship('Consultation', back_populates='user', lazy='dynamic')
    payments = relationship('Payment', back_populates='user', lazy='dynamic')
    notifications = relationship('UserNotification', back_populates='user', lazy='dynamic')
    events = relationship('UserEvent', back_populates='user', lazy='dynamic')
    feedback = relationship('ConsultationFeedback', back_populates='user', lazy='dynamic')
    faq_feedback = relationship('FAQFeedback', back_populates='user', lazy='dynamic')

    # Indexes
    __table_args__ = (
        Index('ix_users_telegram_id', telegram_id),
        Index('ix_users_username', username),
        Index('ix_users_status', status),
        Index('ix_users_language', language),
        Index('ix_users_roles', roles, postgresql_using='gin'),
        Index('ix_users_last_active', last_active),
        Index('ix_users_region', region),
        Index('ix_users_is_blocked', is_blocked),
        UniqueConstraint('telegram_id', name='uq_users_telegram_id'),
    )

    @property
    def is_admin(self) -> bool:
        """Check if user is admin"""
        return 'ADMIN' in self.roles

    @property
    def is_support(self) -> bool:
        """Check if user is support"""
        return 'SUPPORT' in self.roles

    def has_role(self, role: str) -> bool:
        """Check if user has role"""
        return role in self.roles

    def add_role(self, role: str) -> None:
        """Add role to user"""
        if role not in self.roles:
            self.roles = self.roles + [role]

    def remove_role(self, role: str) -> None:
        """Remove role from user"""
        self.roles = [r for r in self.roles if r != role]

    def has_permission(self, permission: str) -> bool:
        """Check if user has permission"""
        return permission in (self.permissions or [])

    def update_last_active(self) -> None:
        """Update last active timestamp"""
        self.last_active = datetime.utcnow()

    def increment_login_attempts(self) -> None:
        """Increment failed login attempts"""
        self.login_attempts = (self.login_attempts or 0) + 1

    def reset_login_attempts(self) -> None:
        """Reset failed login attempts"""
        self.login_attempts = 0

    def update_metrics(self, metric: str, value: float = 1) -> None:
        """Update user metrics"""
        if self.metrics is None:
            self.metrics = {}
        if metric not in self.metrics:
            self.metrics[metric] = 0
        self.metrics[metric] += value

    def get_notification_settings(self, notification_type: str) -> bool:
        """Get notification preference"""
        return self.notification_preferences.get(notification_type, True)

    def update_notification_settings(self, notification_type: str, enabled: bool) -> None:
        """Update notification preference"""
        self.notification_preferences[notification_type] = enabled

    def track_visit(self, ip: str = None, device: str = None) -> None:
        """Track user visit"""
        visit = {
            'timestamp': datetime.utcnow().isoformat(),
            'ip': ip,
            'device': device
        }
        if not self.analytics.get('visits'):
            self.analytics['visits'] = []
        self.analytics['visits'].append(visit)

    def track_action(self, action_type: str, details: dict = None) -> None:
        """Track user action"""
        action = {
            'type': action_type,
            'timestamp': datetime.utcnow().isoformat(),
            'details': details or {}
        }
        if not self.analytics.get('actions'):
            self.analytics['actions'] = []
        self.analytics['actions'].append(action)

    def get_stats(self) -> dict:
        """Get user statistics"""
        return {
            'questions_count': self.metrics.get('questions_asked', 0),
            'consultations_count': self.metrics.get('consultations_completed', 0),
            'total_spent': self.metrics.get('total_spent', 0),
            'avg_rating': self.metrics.get('avg_rating', 0),
            'last_active': self.last_active,
            'member_since': self.created_at
        }

class UserEvent(BaseModel):
    """User activity event tracking"""
    __tablename__ = 'user_events'

    user_id = Column(Integer, ForeignKey('users.id', ondelete='CASCADE'), nullable=False)
    event_type = Column(String, nullable=False)
    event_data = Column(JSONB, default={})
    ip_address = Column(String)
    user_agent = Column(String)
    session_id = Column(String)
    platform = Column(String)
    device_info = Column(JSONB, default={})
    location_data = Column(JSONB, default={})
    event_metadata = Column(JSONB, default={})
    is_processed = Column(Boolean, default=False)
    processed_at = Column(DateTime(timezone=True))
    
    # Analytics fields
    duration = Column(Float)  # For tracking event duration if applicable
    performance_metrics = Column(JSONB, default={})  # For tracking performance data
    error_data = Column(JSONB, default={})  # For tracking any errors during the event

    # Relationships
    user = relationship('User', back_populates='events')

    # Indexes
    __table_args__ = (
        Index('ix_user_events_user_id', user_id),
        Index('ix_user_events_event_type', event_type),
        Index('ix_user_events_created_at', 'created_at'),
        Index('ix_user_events_is_processed', is_processed),
    )

    def mark_processed(self) -> None:
        """Mark event as processed"""
        self.is_processed = True
        self.processed_at = datetime.utcnow()

    def add_performance_metric(self, metric: str, value: float) -> None:
        """Add performance metric"""
        if not self.performance_metrics:
            self.performance_metrics = {}
        self.performance_metrics[metric] = value

    def add_error(self, error: str, details: dict = None) -> None:
        """Add error details"""
        if not self.error_data:
            self.error_data = {}
        self.error_data['error'] = error
        if details:
            self.error_data['details'] = details
        self.error_data['timestamp'] = datetime.utcnow().isoformat()

class UserNotification(BaseModel):
    """User notification model"""
    __tablename__ = 'user_notifications'

    user_id = Column(Integer, ForeignKey('users.id', ondelete='CASCADE'), nullable=False)
    title = Column(String, nullable=False)
    message = Column(Text, nullable=False)
    notification_type = Column(String, nullable=False)
    priority = Column(String, default='normal')
    is_read = Column(Boolean, default=False)
    read_at = Column(DateTime(timezone=True))
    scheduled_for = Column(DateTime(timezone=True))
    sent_at = Column(DateTime(timezone=True))
    metadata = Column(JSONB, default={})
    
    # Additional fields
    category = Column(String)  # For categorizing notifications
    expiry_date = Column(DateTime(timezone=True))  # When notification expires
    action_url = Column(String)  # URL for notification action
    action_data = Column(JSONB, default={})  # Additional action data
    image_url = Column(String)  # URL for notification image
    seen_at = Column(DateTime(timezone=True))  # When notification was seen
    interaction_count = Column(Integer, default=0)  # Number of times user interacted
    is_archived = Column(Boolean, default=False)  # If notification is archived
    archived_at = Column(DateTime(timezone=True))  # When notification was archived
    campaign_id = Column(String)  # For tracking marketing campaigns
    
    # Relationships
    user = relationship('User', back_populates='notifications')

    # Indexes
    __table_args__ = (
        Index('ix_user_notifications_user_id', user_id),
        Index('ix_user_notifications_type', notification_type),
        Index('ix_user_notifications_is_read', is_read),
        Index('ix_user_notifications_scheduled_for', scheduled_for),
        Index('ix_user_notifications_sent_at', sent_at),
        Index('ix_user_notifications_campaign_id', campaign_id),
    )

    def mark_as_read(self) -> None:
        """Mark notification as read"""
        if not self.is_read:
            self.is_read = True
            self.read_at = datetime.utcnow()

    def mark_as_seen(self) -> None:
        """Mark notification as seen"""
        if not self.seen_at:
            self.seen_at = datetime.utcnow()

    def mark_as_sent(self) -> None:
        """Mark notification as sent"""
        self.sent_at = datetime.utcnow()

    def increment_interaction(self) -> None:
        """Increment interaction count"""
        self.interaction_count += 1

    def archive(self) -> None:
        """Archive notification"""
        if not self.is_archived:
            self.is_archived = True
            self.archived_at = datetime.utcnow()

    def is_expired(self) -> bool:
        """Check if notification is expired"""
        if self.expiry_date:
            return datetime.utcnow() > self.expiry_date
        return False

    def should_send(self) -> bool:
        """Check if notification should be sent"""
        return (
            not self.sent_at and
            not self.is_archived and
            not self.is_expired() and
            (not self.scheduled_for or datetime.utcnow() >= self.scheduled_for)
        )
```

# telegram_bot\services\__init__.py

```py
from telegram_bot.services.analytics import AnalyticsService
from telegram_bot.services.questions import QuestionService
from telegram_bot.services.consultations import ConsultationService
from telegram_bot.services.payments import PaymentService

__all__ = [
    'AnalyticsService',
    'QuestionService',
    'ConsultationService',
    'PaymentService'
]

```

# telegram_bot\services\analytics.py

```py
from typing import Dict, Any, List, Optional
from datetime import datetime, timedelta
from sqlalchemy import select, func, case, and_, or_
import logging
import json
from telegram_bot.models import (
    User, Question, Answer, Consultation, Payment,
    ConsultationStatus, PaymentStatus, UserEvent
)
from telegram_bot.core.cache import cache_service as cache

logger = logging.getLogger(__name__)

class AnalyticsService:
    """Enhanced analytics service for comprehensive data analysis"""
    
    def __init__(self, session):
        self.session = session
        self.cache = cache
        
    async def get_dashboard_stats(self) -> Dict[str, Any]:
        """Get comprehensive dashboard statistics"""
        try:
            cache_key = "dashboard_stats"
            cached = await self.cache.get(cache_key)
            if cached:
                return cached
                
            # Get time ranges
            now = datetime.utcnow()
            today = now.replace(hour=0, minute=0, second=0, microsecond=0)
            week_ago = now - timedelta(days=7)
            month_ago = now - timedelta(days=30)
            
            # Get user stats
            users_stats = await self._get_users_stats(week_ago, month_ago)
            
            # Get questions stats
            questions_stats = await self._get_questions_stats(week_ago, month_ago)
            
            # Get consultations stats
            consultations_stats = await self._get_consultations_stats(week_ago, month_ago)
            
            # Get revenue stats
            revenue_stats = await self._get_revenue_stats(today, week_ago, month_ago)
            
            # Get system health metrics
            health_metrics = await self._get_system_health()
            
            stats = {
                'users': users_stats,
                'questions': questions_stats,
                'consultations': consultations_stats,
                'revenue': revenue_stats,
                'system_health': health_metrics,
                'updated_at': now.isoformat()
            }
            
            # Cache for 5 minutes
            await self.cache.set(cache_key, stats, timeout=300)
            
            return stats
            
        except Exception as e:
            logger.error(f"Error getting dashboard stats: {e}")
            return {}

    async def _get_users_stats(
        self,
        week_ago: datetime,
        month_ago: datetime
    ) -> Dict[str, Any]:
        """Get detailed user statistics"""
        try:
            result = await self.session.execute(
                select(
                    func.count(User.id).label('total'),
                    func.count(User.id)
                    .filter(User.created_at >= week_ago)
                    .label('new_week'),
                    func.count(User.id)
                    .filter(User.created_at >= month_ago)
                    .label('new_month'),
                    func.count(User.id)
                    .filter(User.is_blocked == False)
                    .label('active'),
                    func.count(User.id)
                    .filter(User.last_active >= week_ago)
                    .label('active_week'),
                    func.count(User.id)
                    .filter(User.language == 'uz')
                    .label('uz_users'),
                    func.count(User.id)
                    .filter(User.language == 'ru')
                    .label('ru_users')
                )
            )
            stats = result.mappings().first()
            
            # Calculate growth rates
            total = stats['total'] or 0
            new_week = stats['new_week'] or 0
            new_month = stats['new_month'] or 0
            
            week_growth = (new_week / (total - new_week) * 100) if total > new_week else 0
            month_growth = (new_month / (total - new_month) * 100) if total > new_month else 0
            
            return {
                'total_users': total,
                'new_users_week': new_week,
                'new_users_month': new_month,
                'active_users': stats['active'],
                'active_users_week': stats['active_week'],
                'growth_rate_week': round(week_growth, 2),
                'growth_rate_month': round(month_growth, 2),
                'languages': {
                    'uz': stats['uz_users'],
                    'ru': stats['ru_users']
                }
            }
            
        except Exception as e:
            logger.error(f"Error getting user stats: {e}")
            return {}

    async def _get_questions_stats(
        self,
        week_ago: datetime,
        month_ago: datetime
    ) -> Dict[str, Any]:
        """Get detailed question statistics"""
        try:
            result = await self.session.execute(
                select(
                    func.count(Question.id).label('total'),
                    func.count(Question.id)
                    .filter(Question.created_at >= week_ago)
                    .label('new_week'),
                    func.count(Question.id)
                    .filter(~Question.answers.any())
                    .label('unanswered'),
                    func.count(Question.id)
                    .filter(Question.answers.any(Answer.is_auto == True))
                    .label('auto_answered'),
                    func.avg(Answer.rating)
                    .label('avg_rating')
                )
                .outerjoin(Answer)
            )
            stats = result.mappings().first()
            
            # Get category distribution
            categories_result = await self.session.execute(
                select(
                    Question.category,
                    func.count(Question.id).label('count')
                )
                .filter(Question.category.isnot(None))
                .group_by(Question.category)
            )
            categories = {
                row.category: row.count
                for row in categories_result
            }
            
            return {
                'total_questions': stats['total'],
                'new_questions_week': stats['new_week'],
                'unanswered_questions': stats['unanswered'],
                'auto_answered_questions': stats['auto_answered'],
                'average_rating': round(float(stats['avg_rating'] or 0), 2),
                'categories': categories
            }
            
        except Exception as e:
            logger.error(f"Error getting question stats: {e}")
            return {}

    async def _get_consultations_stats(
        self,
        week_ago: datetime,
        month_ago: datetime
    ) -> Dict[str, Any]:
        """Get detailed consultation statistics"""
        try:
            result = await self.session.execute(
                select(
                    func.count(Consultation.id).label('total'),
                    func.count(Consultation.id)
                    .filter(Consultation.created_at >= week_ago)
                    .label('new_week'),
                    func.count(Consultation.id)
                    .filter(Consultation.status == ConsultationStatus.PENDING)
                    .label('pending'),
                    func.count(Consultation.id)
                    .filter(Consultation.status == ConsultationStatus.COMPLETED)
                    .label('completed'),
                    func.avg(Consultation.rating)
                    .filter(Consultation.status == ConsultationStatus.COMPLETED)
                    .label('avg_rating')
                )
            )
            stats = result.mappings().first()
            
            return {
                'total_consultations': stats['total'],
                'new_consultations_week': stats['new_week'],
                'pending_consultations': stats['pending'],
                'completed_consultations': stats['completed'],
                'average_rating': round(float(stats['avg_rating'] or 0), 2),
                'completion_rate': round(stats['completed'] / stats['total'] * 100, 2) if stats['total'] else 0
            }
            
        except Exception as e:
            logger.error(f"Error getting consultation stats: {e}")
            return {}

    async def _get_revenue_stats(
        self,
        today: datetime,
        week_ago: datetime,
        month_ago: datetime
    ) -> Dict[str, Any]:
        """Get detailed revenue statistics"""
        try:
            result = await self.session.execute(
                select(
                    func.sum(Payment.amount)
                    .filter(Payment.status == PaymentStatus.COMPLETED)
                    .label('total'),
                    func.sum(Payment.amount)
                    .filter(
                        Payment.status == PaymentStatus.COMPLETED,
                        Payment.created_at >= today
                    )
                    .label('today'),
                    func.sum(Payment.amount)
                    .filter(
                        Payment.status == PaymentStatus.COMPLETED,
                        Payment.created_at >= week_ago
                    )
                    .label('week'),
                    func.sum(Payment.amount)
                    .filter(
                        Payment.status == PaymentStatus.COMPLETED,
                        Payment.created_at >= month_ago
                    )
                    .label('month')
                )
            )
            totals = result.mappings().first()
            
            # Get provider distribution
            providers_result = await self.session.execute(
                select(
                    Payment.provider,
                    func.count(Payment.id).label('count'),
                    func.sum(Payment.amount).label('amount')
                )
                .filter(Payment.status == PaymentStatus.COMPLETED)
                .group_by(Payment.provider)
            )
            providers = {
                row.provider: {
                    'count': row.count,
                    'amount': float(row.amount or 0)
                }
                for row in providers_result
            }
            
            return {
                'total_revenue': float(totals['total'] or 0),
                'revenue_today': float(totals['today'] or 0),
                'revenue_week': float(totals['week'] or 0),
                'revenue_month': float(totals['month'] or 0),
                'by_provider': providers
            }
            
        except Exception as e:
            logger.error(f"Error getting revenue stats: {e}")
            return {}

    async def _get_system_health(self) -> Dict[str, Any]:
        """Get system health metrics"""
        try:
            import psutil
            
            return {
                'cpu_usage': psutil.cpu_percent(),
                'memory_usage': psutil.virtual_memory().percent,
                'disk_usage': psutil.disk_usage('/').percent,
                'cache_hit_rate': await self.cache.get_hit_rate(),
                'error_rate': await self._get_error_rate()
            }
            
        except Exception as e:
            logger.error(f"Error getting system health: {e}")
            return {}

    async def _get_error_rate(self) -> float:
        """Calculate error rate for last hour"""
        try:
            hour_ago = datetime.utcnow() - timedelta(hours=1)
            
            result = await self.session.execute(
                select(
                    func.count(UserEvent.id).label('total'),
                    func.count(UserEvent.id)
                    .filter(UserEvent.event_type == 'error')
                    .label('errors')
                )
                .filter(UserEvent.created_at >= hour_ago)
            )
            stats = result.mappings().first()
            
            return round(stats['errors'] / stats['total'] * 100, 2) if stats['total'] else 0
            
        except Exception as e:
            logger.error(f"Error calculating error rate: {e}")
            return 0

    async def get_user_activity(
        self,
        user_id: int,
        days: int = 30
    ) -> List[Dict[str, Any]]:
        """Get user activity history"""
        try:
            since = datetime.utcnow() - timedelta(days=days)
            
            result = await self.session.execute(
                select(UserEvent)
                .filter(
                    UserEvent.user_id == user_id,
                    UserEvent.created_at >= since
                )
                .order_by(UserEvent.created_at.desc())
            )
            events = result.scalars().all()
            
            return [
                {
                    'type': event.event_type,
                    'data': event.event_data,
                    'created_at': event.created_at.isoformat()
                }
                for event in events
            ]
            
        except Exception as e:
            logger.error(f"Error getting user activity: {e}")
            return []

    async def track_event(
        self,
        user_id: int,
        event_type: str,
        data: Dict = None
    ) -> None:
        """Track user event"""
        try:
            event = UserEvent(
                user_id=user_id,
                event_type=event_type,
                event_data=data or {}
            )
            self.session.add(event)
            await self.session.commit()
            
        except Exception as e:
            logger.error(f"Error tracking event: {e}")

    async def export_data(
        self,
        start_date: datetime,
        end_date: datetime,
        data_type: str
    ) -> List[Dict[str, Any]]:
        """Export analytics data"""
        try:
            if data_type == 'users':
                data = await self._export_users(start_date, end_date)
            elif data_type == 'questions':
                data = await self._export_questions(start_date, end_date)
            elif data_type == 'consultations':
                data = await self._export_consultations(start_date, end_date)
            elif data_type == 'payments':
                data = await self._export_payments(start_date, end_date)
            else:
                raise ValueError(f"Unknown data type: {data_type}")
                
            return data
            
        except Exception as e:
            logger.error(f"Error exporting data: {e}")
            return []
```

# telegram_bot\services\auto_answer.py

```py
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
```

# telegram_bot\services\background_tasks.py

```py
import asyncio
import logging
from datetime import datetime, timedelta
from typing import Optional, Dict, Any
from sqlalchemy import select, func
from sqlalchemy import event, text
from sqlalchemy.orm import joinedload
from telegram_bot.core.cache import cache_service as cache


from telegram_bot.core.database import get_session
from telegram_bot.models import (
    User, Question, Consultation, ConsultationStatus,
    Payment, PaymentStatus
)
from telegram_bot.services.analytics import AnalyticsService
from telegram_bot.services.auto_answer import AutoAnswerTrainer

logger = logging.getLogger(__name__)

class BackgroundTaskManager:
    """Background task manager for scheduled operations"""
    
    def __init__(self):
        self._running = False
        self._tasks = []
        
    async def start(self):
        """Start background tasks"""
        if self._running:
            return
            
        self._running = True
        
        # Start periodic tasks
        self._tasks.extend([
            asyncio.create_task(self._run_periodic(
                self._train_auto_answer,
                hours=24
            )),
            asyncio.create_task(self._run_periodic(
                self._cleanup_expired_data,
                hours=1
            )),
            asyncio.create_task(self._run_periodic(
                self._update_statistics,
                minutes=5
            )),
            asyncio.create_task(self._run_periodic(
                self._process_scheduled_consultations,
                minutes=1
            )),
            asyncio.create_task(self._run_periodic(
                self._health_check,
                minutes=1
            ))
        ])
        
        logger.info("Background tasks started")
        
    async def stop(self):
        """Stop all background tasks"""
        self._running = False
        
        for task in self._tasks:
            task.cancel()
            
        await asyncio.gather(*self._tasks, return_exceptions=True)
        self._tasks.clear()
        
        logger.info("Background tasks stopped")
        
    async def _run_periodic(
        self,
        func: callable,
        days: int = 0,
        hours: int = 0,
        minutes: int = 0
    ):
        """Run periodic task"""
        interval = timedelta(
            days=days,
            hours=hours,
            minutes=minutes
        ).total_seconds()
        
        while self._running:
            try:
                await func()
            except Exception as e:
                logger.error(f"Error in periodic task {func.__name__}: {e}")
            await asyncio.sleep(interval)
            
    async def _train_auto_answer(self):
        """Train auto-answer models"""
        try:
            async with get_session() as session:
                trainer = AutoAnswerTrainer(session)
                
                # Train for each language
                for language in ['uz', 'ru']:
                    success = await trainer.train_model(language)
                    if success:
                        logger.info(f"Auto-answer model trained for {language}")
                        
                    # Evaluate model
                    metrics = await trainer.evaluate_model(language)
                    await cache.set(
                        f"auto_answer:metrics:{language}",
                        metrics
                    )
                    
        except Exception as e:
            logger.error(f"Error training auto-answer: {e}")
            
    async def _cleanup_expired_data(self):
        """Clean up expired data"""
        try:
            async with get_session() as session:
                # Clean up expired payments
                expired_time = datetime.utcnow() - timedelta(hours=24)
                expired_payments = await session.execute(
                    select(Payment)
                    .filter(
                        Payment.status == PaymentStatus.PENDING,
                        Payment.created_at < expired_time
                    )
                )
                
                for payment in expired_payments.scalars():
                    payment.status = PaymentStatus.EXPIRED

                # Archive old questions
                archive_time = datetime.utcnow() - timedelta(days=90)
                old_questions = await session.execute(
                    select(Question)
                    .filter(
                        Question.created_at < archive_time,
                        Question.is_answered == True
                    )
                )
                
                for question in old_questions.scalars():
                    question.archived = True
                    question.metadata = question.metadata or {}
                    question.metadata["archived_at"] = datetime.utcnow().isoformat()
                    
                # Clean up user sessions
                session_expiry = datetime.utcnow() - timedelta(days=30)
                await session.execute(
                    text("DELETE FROM user_sessions WHERE last_activity < :expiry"),
                    {"expiry": session_expiry}
                )
                
                await session.commit()
                logger.info("Cleanup completed successfully")
                
        except Exception as e:
            logger.error(f"Error in cleanup task: {e}")
            
    async def _update_statistics(self):
        """Update system statistics"""
        try:
            async with get_session() as session:
                analytics = AnalyticsService(session)
                
                # Update user statistics
                user_stats = await analytics.get_users_stats()
                await cache.set("stats:users", user_stats, timeout=300)
                
                # Update question statistics
                question_stats = await analytics.get_question_stats()
                await cache.set("stats:questions", question_stats, timeout=300)
                
                # Update consultation statistics
                consultation_stats = await analytics.get_consultation_stats()
                await cache.set("stats:consultations", consultation_stats, timeout=300)
                
                # Update revenue statistics
                revenue_stats = await analytics.get_revenue_stats()
                await cache.set("stats:revenue", revenue_stats, timeout=300)
                
                logger.info("Statistics updated successfully")
                
        except Exception as e:
            logger.error(f"Error updating statistics: {e}")
            
    async def _process_scheduled_consultations(self):
        """Process scheduled consultations"""
        try:
            async with get_session() as session:
                # Get upcoming consultations
                now = datetime.utcnow()
                upcoming = now + timedelta(minutes=30)
                
                scheduled = await session.execute(
                    select(Consultation)
                    .filter(
                        Consultation.status == ConsultationStatus.SCHEDULED,
                        Consultation.scheduled_time.between(now, upcoming)
                    )
                    .options(joinedload(Consultation.user))
                )
                
                from telegram_bot.bot import bot
                
                for consultation in scheduled.scalars():
                    # Send reminder to user
                    try:
                        await bot.send_message(
                            consultation.user.telegram_id,
                            f"Reminder: Your consultation is scheduled for "
                            f"{consultation.scheduled_time.strftime('%H:%M')} "
                            f"(in {(consultation.scheduled_time - now).minutes} minutes)"
                        )
                        
                        # Update reminder sent flag
                        consultation.metadata = consultation.metadata or {}
                        consultation.metadata["reminder_sent"] = True
                        consultation.metadata["reminder_sent_at"] = now.isoformat()
                        
                    except Exception as e:
                        logger.error(f"Error sending reminder for consultation {consultation.id}: {e}")
                        
                await session.commit()
                
        except Exception as e:
            logger.error(f"Error processing scheduled consultations: {e}")
            
    async def _health_check(self):
        """Perform system health check"""
        try:
            health_data = {
                "timestamp": datetime.utcnow().isoformat(),
                "status": "healthy",
                "components": {}
            }
            
            # Check database
            try:
                async with get_session() as session:
                    await session.execute(text("SELECT 1"))
                health_data["components"]["database"] = {"status": "up"}
            except Exception as e:
                health_data["components"]["database"] = {
                    "status": "down",
                    "error": str(e)
                }
                health_data["status"] = "degraded"
                
            # Check Redis
            try:
                redis_ok = await cache.health_check()
                health_data["components"]["cache"] = {
                    "status": "up" if redis_ok else "down"
                }
                if not redis_ok:
                    health_data["status"] = "degraded"
            except Exception as e:
                health_data["components"]["cache"] = {
                    "status": "down",
                    "error": str(e)
                }
                health_data["status"] = "degraded"
                
            # Check bot
            try:
                from telegram_bot.bot import bot
                me = await bot.get_me()
                health_data["components"]["bot"] = {"status": "up"}
            except Exception as e:
                health_data["components"]["bot"] = {
                    "status": "down",
                    "error": str(e)
                }
                health_data["status"] = "degraded"
                
            # Check system resources
            import psutil
            system_metrics = {
                "cpu_percent": psutil.cpu_percent(),
                "memory_percent": psutil.virtual_memory().percent,
                "disk_percent": psutil.disk_usage('/').percent
            }
            
            # Check if any resource is critical
            for metric, value in system_metrics.items():
                if value > 90:  # Critical threshold
                    health_data["status"] = "degraded"
                    
            health_data["metrics"] = system_metrics
            
            # Save health status
            await cache.set(
                "system:health",
                health_data,
                timeout=60
            )
            
            # Alert if system is unhealthy
            if health_data["status"] != "healthy":
                await self._send_health_alert(health_data)
                
        except Exception as e:
            logger.error(f"Error in health check: {e}")
            
    async def _send_health_alert(self, health_data: Dict[str, Any]):
        """Send health alert to admins"""
        try:
            from telegram_bot.bot import bot
            from telegram_bot.core.config import settings
            
            alert_message = (
                "🚨 System Health Alert 🚨\n\n"
                f"Status: {health_data['status']}\n"
                f"Time: {health_data['timestamp']}\n\n"
                "Component Status:\n"
            )
            
            for component, data in health_data["components"].items():
                status = data["status"]
                error = data.get("error", "")
                alert_message += f"- {component}: {status}\n"
                if error:
                    alert_message += f"  Error: {error}\n"
                    
            alert_message += "\nSystem Metrics:\n"
            metrics = health_data["metrics"]
            alert_message += (
                f"- CPU: {metrics['cpu_percent']}%\n"
                f"- Memory: {metrics['memory_percent']}%\n"
                f"- Disk: {metrics['disk_percent']}%"
            )
            
            # Send to all admins
            for admin_id in settings.ADMIN_IDS:
                try:
                    await bot.send_message(admin_id, alert_message)
                except Exception as e:
                    logger.error(f"Error sending alert to admin {admin_id}: {e}")
                    
        except Exception as e:
            logger.error(f"Error sending health alert: {e}")

# Create global instance
background_tasks = BackgroundTaskManager()

```

# telegram_bot\services\base.py

```py
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
```

# telegram_bot\services\consultations.py

```py
# telegram_bot/services/consultations/service.py

from typing import List, Optional, Dict, Any, Tuple
from datetime import datetime, timedelta
from decimal import Decimal
from sqlalchemy import select, func, or_, and_
import logging

from telegram_bot.models import (
    Consultation, ConsultationStatus, User,
    Payment, PaymentStatus
)
from telegram_bot.services.base import BaseService
from telegram_bot.core.errors import ValidationError
from telegram_bot.core.cache import cache_service as cache
from telegram_bot.core.constants import TEXTS
from telegram_bot.utils.validators import validator

logger = logging.getLogger(__name__)

class ConsultationService(BaseService[Consultation]):
    """Enhanced consultation service"""
    
    WORK_HOURS = {
        'start': 9,  # 9 AM
        'end': 18    # 6 PM
    }
    WORKING_DAYS = [0, 1, 2, 3, 4, 5]  # Monday to Saturday
    SLOT_DURATION = 60  # minutes
    
    def __init__(self, session):
        super().__init__(Consultation, session)
        self.cache = cache
        
    async def create_consultation(
        self,
        user_id: int,
        consultation_type: str,
        amount: Decimal,
        phone_number: str,
        description: str,
        metadata: Dict = None
    ) -> Consultation:
        """Create new consultation request"""
        try:
            # Validate phone number
            phone_number = validator.phone_number(phone_number)
            
            # Validate amount
            if amount < Decimal('50000') or amount > Decimal('1000000'):
                raise ValidationError("Invalid consultation amount")
                
            # Create consultation
            consultation = await self.create(
                user_id=user_id,
                consultation_type=consultation_type,
                amount=amount,
                phone_number=phone_number,
                description=description,
                status=ConsultationStatus.PENDING,
                metadata=metadata or {
                    'created_at': datetime.utcnow().isoformat()
                }
            )
            
            # Notify admins
            await self._notify_admins_new_consultation(consultation)
            
            return consultation
            
        except ValidationError:
            raise
        except Exception as e:
            logger.error(f"Error creating consultation: {e}")
            raise ValidationError("Failed to create consultation")
            
    async def get_available_slots(
        self,
        date: datetime,
        consultation_type: str = None
    ) -> List[datetime]:
        """Get available consultation time slots"""
        if date.date() < datetime.now().date():
            return []
            
        if date.weekday() not in self.WORKING_DAYS:
            return []
            
        # Try cache
        cache_key = f"slots:{date.date()}:{consultation_type or 'all'}"
        cached = await self.cache.get(cache_key)
        if cached:
            return [datetime.fromisoformat(dt) for dt in cached]
            
        # Get booked slots
        booked_slots = await self.session.execute(
            select(Consultation.scheduled_time)
            .filter(
                func.date(Consultation.scheduled_time) == date.date(),
                Consultation.status.in_([
                    ConsultationStatus.SCHEDULED,
                    ConsultationStatus.CONFIRMED
                ])
            )
        )
        booked_times = {slot.scheduled_time for slot in booked_slots.scalars()}
        
        # Generate available slots
        available_slots = []
        current_time = datetime.combine(
            date.date(),
            datetime.min.time().replace(hour=self.WORK_HOURS['start'])
        )
        
        while current_time.hour < self.WORK_HOURS['end']:
            if (current_time > datetime.now() and
                current_time not in booked_times):
                available_slots.append(current_time)
            current_time += timedelta(minutes=self.SLOT_DURATION)
        
        # Cache results
        await self.cache.set(
            cache_key,
            [dt.isoformat() for dt in available_slots],
            timeout=300  # 5 minutes
        )
        
        return available_slots
        
    async def schedule_consultation(
        self,
        consultation_id: int,
        scheduled_time: datetime
    ) -> bool:
        """Schedule confirmed consultation"""
        consultation = await self.get(consultation_id)
        if not consultation:
            return False
            
        if consultation.status != ConsultationStatus.PAID:
            raise ValidationError("Consultation must be paid first")
            
        # Validate time
        if not self._is_valid_time(scheduled_time):
            raise ValidationError("Invalid consultation time")
            
        # Check availability
        if not await self._is_time_available(scheduled_time):
            raise ValidationError("Selected time is not available")
            
        # Update consultation
        consultation.scheduled_time = scheduled_time
        consultation.status = ConsultationStatus.SCHEDULED
        consultation.metadata['scheduled_at'] = datetime.utcnow().isoformat()
        
        await self.session.commit()
        
        # Clear cache
        await self.cache.delete_pattern('slots:*')
        
        # Send notifications
        await self._notify_about_scheduling(consultation)
        
        return True
        
    def _is_valid_time(self, dt: datetime) -> bool:
        """Check if time is valid for consultation"""
        return (
            dt.weekday() in self.WORKING_DAYS and
            self.WORK_HOURS['start'] <= dt.hour < self.WORK_HOURS['end']
        )
        
    async def _is_time_available(
        self,
        dt: datetime,
        exclude_id: Optional[int] = None
    ) -> bool:
        """Check if time slot is available"""
        query = select(Consultation).filter(
            Consultation.scheduled_time == dt,
            Consultation.status.in_([
                ConsultationStatus.SCHEDULED,
                ConsultationStatus.CONFIRMED
            ])
        )
        
        if exclude_id:
            query = query.filter(Consultation.id != exclude_id)
            
        result = await self.session.execute(query)
        return not bool(result.scalar_one_or_none())
        
    async def confirm_payment(
        self,
        consultation_id: int,
        payment_id: str,
        amount: Decimal
    ) -> bool:
        """Confirm consultation payment"""
        consultation = await self.get(consultation_id)
        if not consultation:
            return False
            
        if consultation.status != ConsultationStatus.PENDING:
            raise ValidationError("Invalid consultation status")
            
        if consultation.amount != amount:
            raise ValidationError("Payment amount mismatch")
            
        # Update status
        consultation.status = ConsultationStatus.PAID
        consultation.metadata['payment_id'] = payment_id
        consultation.metadata['paid_at'] = datetime.utcnow().isoformat()
        
        await self.session.commit()
        
        # Notify user
        await self._notify_user(
            consultation,
            'payment_confirmed'
        )
        
        return True
        
    async def cancel_consultation(
        self,
        consultation_id: int,
        reason: Optional[str] = None,
        cancelled_by_user: bool = True
    ) -> bool:
        """Cancel consultation"""
        consultation = await self.get(consultation_id)
        if not consultation:
            return False
            
        # Can only cancel pending or scheduled consultations
        if consultation.status not in [
            ConsultationStatus.PENDING,
            ConsultationStatus.SCHEDULED
        ]:
            raise ValidationError("Cannot cancel this consultation")
            
        # Update status
        consultation.status = ConsultationStatus.CANCELLED
        consultation.metadata['cancelled_at'] = datetime.utcnow().isoformat()
        consultation.metadata['cancelled_by_user'] = cancelled_by_user
        
        if reason:
            consultation.metadata['cancellation_reason'] = reason
            
        await self.session.commit()
        
        # Process refund if needed
        if consultation.status == ConsultationStatus.PAID:
            await self._process_refund(consultation)
            
        # Notify user
        await self._notify_user(
            consultation,
            'consultation_cancelled',
            reason=reason
        )
        
        return True
        
    async def complete_consultation(
        self,
        consultation_id: int,
        notes: Optional[str] = None,
        rating: Optional[int] = None,
        feedback: Optional[str] = None
    ) -> bool:
        """Complete consultation"""
        consultation = await self.get(consultation_id)
        if not consultation:
            return False
            
        if consultation.status != ConsultationStatus.SCHEDULED:
            raise ValidationError("Cannot complete this consultation")
            
        # Update consultation
        consultation.status = ConsultationStatus.COMPLETED
        consultation.metadata['completed_at'] = datetime.utcnow().isoformat()
        
        if notes:
            consultation.metadata['completion_notes'] = notes
            
        if rating:
            consultation.metadata['rating'] = rating
            consultation.metadata['feedback'] = feedback
            
        await self.session.commit()
        
        # Request feedback if not provided
        if not rating:
            await self._request_feedback(consultation)
            
        return True
        
    async def _notify_user(
        self,
        consultation: Consultation,
        message_type: str,
        **kwargs
    ) -> None:
        """Send notification to user"""
        try:
            from telegram_bot.bot import bot
            
            user = await self.session.get(User, consultation.user_id)
            if not user:
                return
                
            text = TEXTS[user.language][message_type]
            
            # Add consultation details
            text += f"\n\n📅 {consultation.created_at.strftime('%d.%m.%Y')}"
            text += f"\n💰 {consultation.amount:,.0f} сум"
            
            if consultation.scheduled_time:
                text += f"\n🕒 {consultation.scheduled_time.strftime('%d.%m.%Y %H:%M')}"
                
            if kwargs.get('reason'):
                text += f"\n\n{TEXTS[user.language]['cancellation_reason']}: {kwargs['reason']}"
                
            await bot.send_message(
                user.telegram_id,
                text
            )
            
        except Exception as e:
            logger.error(f"Error notifying user: {e}")
            
    async def _notify_admins_new_consultation(
        self,
        consultation: Consultation
    ) -> None:
        """Notify admins about new consultation"""
        try:
            from telegram_bot.bot import bot
            from telegram_bot.core.config import settings
            
            user = await self.session.get(User, consultation.user_id)
            if not user:
                return
                
            text = (
                "🆕 New consultation request\n\n"
                f"👤 {user.full_name}"
                f"{f' (@{user.username})' if user.username else ''}\n"
                f"📞 {consultation.phone_number}\n"
                f"💰 {consultation.amount:,.0f} sum\n\n"
                f"📝 {consultation.description}"
            )
            
            for admin_id in settings.ADMIN_IDS:
                try:
                    await bot.send_message(admin_id, text)
                except Exception as e:
                    logger.error(f"Error notifying admin {admin_id}: {e}")
                    
        except Exception as e:
            logger.error(f"Error notifying admins: {e}")
            
    async def _notify_about_scheduling(
        self,
        consultation: Consultation
    ) -> None:
        """Send scheduling notifications"""
        try:
            from telegram_bot.bot import bot
            
            user = await self.session.get(User, consultation.user_id)
            if not user:
                return
                
            # Notify user
            text = TEXTS[user.language]['consultation_scheduled'].format(
                time=consultation.scheduled_time.strftime("%d.%m.%Y %H:%M")
            )
            
            await bot.send_message(
                user.telegram_id,
                text
            )
            
            # Schedule reminders
            reminders = [
                (timedelta(days=1), 'consultation_reminder_24h'),
                (timedelta(hours=2), 'consultation_reminder_2h'),
                (timedelta(minutes=30), 'consultation_reminder_30m')
            ]
            
            for delta, reminder_type in reminders:
                reminder_time = consultation.scheduled_time - delta
                if reminder_time > datetime.utcnow():
                    await self.cache.set(
                        f"reminder:{consultation.id}:{reminder_type}",
                        {
                            'consultation_id': consultation.id,
                            'type': reminder_type,
                            'scheduled_for': reminder_time.isoformat()
                        },
                        timeout=int(delta.total_seconds())
                    )
                    
        except Exception as e:
            logger.error(f"Error sending scheduling notifications: {e}")
            
    async def _process_refund(self, consultation: Consultation) -> bool:
        """Process consultation refund"""
        try:
            if not consultation.metadata.get('payment_id'):
                return False
                
            from telegram_bot.services.payments import payment_service
            
            success = await payment_service.process_refund(
                payment_id=consultation.metadata['payment_id'],
                amount=consultation.amount
            )
            
            if success:
                consultation.metadata['refunded'] = True
                consultation.metadata['refund_time'] = datetime.utcnow().isoformat()
                await self.session.commit()
                
                # Notify user
                await self._notify_user(
                    consultation,
                    'payment_refunded'
                )
                
            return success
            
        except Exception as e:
            logger.error(f"Error processing refund: {e}")
            return False

consultation_service = ConsultationService(None)  # Session will be injected

__all__ = ['ConsultationService', 'consultation_service']
```

# telegram_bot\services\faq.py

```py
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
```

# telegram_bot\services\notifications.py

```py
from typing import Optional, List, Dict, Any
from datetime import datetime, timedelta
import logging
from sqlalchemy import select, func, or_, and_
from sqlalchemy.ext.asyncio import AsyncSession

from telegram_bot.models.notifications import NotificationType, NotificationPriority, NotificationStatus
from telegram_bot.models import User, UserNotification
from telegram_bot.core.cache import cache_service as cache
from telegram_bot.core.errors import ValidationError
from telegram_bot.services.base import BaseService
import asyncio
logger = logging.getLogger(__name__)

class NotificationService(BaseService):
    """Enhanced notification service with queuing and scheduling"""
    
    def __init__(self, session: AsyncSession):
        super().__init__(UserNotification, session)
        self.cache = cache
        
        # Notification templates cache key
        self.TEMPLATES_KEY = "notification:templates"
        
        # Notification rate limits (per user per hour)
        self.RATE_LIMITS = {
            NotificationType.MARKETING: 2,
            NotificationType.SYSTEM_UPDATE: 5,
            NotificationType.SUPPORT: 10
        }
    
    async def create_notification(
        self,
        user_id: int,
        notification_type: NotificationType,
        title: str,
        message: str,
        priority: NotificationPriority = NotificationPriority.MEDIUM,
        schedule_time: Optional[datetime] = None,
        metadata: Dict = None
    ) -> Optional[UserNotification]:
        """Create and optionally schedule notification"""
        try:
            # Check rate limits
            if not await self._check_rate_limit(user_id, notification_type):
                logger.warning(f"Rate limit exceeded for user {user_id} and type {notification_type}")
                return None
            
            # Create notification record
            notification = await self.create(
                user_id=user_id,
                type=notification_type,
                priority=priority,
                title=title,
                message=message,
                status=NotificationStatus.PENDING,
                schedule_time=schedule_time,
                metadata=metadata or {
                    'created_at': datetime.utcnow().isoformat()
                }
            )
            
            # If no schedule time or scheduled for now, send immediately
            if not schedule_time or schedule_time <= datetime.utcnow():
                await self._send_notification(notification)
            else:
                # Schedule notification
                await self._schedule_notification(notification)
            
            return notification
            
        except Exception as e:
            logger.error(f"Error creating notification: {e}")
            return None
    
    async def create_bulk_notifications(
        self,
        user_ids: List[int],
        notification_type: NotificationType,
        title: str,
        message: str,
        priority: NotificationPriority = NotificationPriority.MEDIUM,
        metadata: Dict = None
    ) -> int:
        """Create notifications for multiple users"""
        try:
            sent_count = 0
            
            for user_id in user_ids:
                notification = await self.create_notification(
                    user_id=user_id,
                    notification_type=notification_type,
                    title=title,
                    message=message,
                    priority=priority,
                    metadata=metadata
                )
                if notification:
                    sent_count += 1
                
                # Add small delay to prevent overload
                await asyncio.sleep(0.1)
            
            return sent_count
            
        except Exception as e:
            logger.error(f"Error creating bulk notifications: {e}")
            return 0

    async def _send_notification(self, notification: UserNotification) -> bool:
        """Send notification via appropriate channel"""
        try:
            # Get user
            user = await self.session.get(User, notification.user_id)
            if not user:
                logger.error(f"User not found for notification {notification.id}")
                return False
            
            # Check user preferences
            if not await self._check_user_preferences(user, notification.type):
                logger.info(f"Notification {notification.id} skipped due to user preferences")
                return False
            
            # Send via Telegram
            from telegram_bot.bot import bot
            
            # Format message
            text = f"*{notification.title}*\n\n{notification.message}"
            
            # Add buttons if specified in metadata
            keyboard = None
            if notification.metadata.get('buttons'):
                from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
                keyboard = InlineKeyboardMarkup(inline_keyboard=[
                    [InlineKeyboardButton(
                        text=btn['text'],
                        callback_data=btn['callback_data']
                    ) for btn in notification.metadata['buttons']]
                ])
            
            # Send message
            try:
                await bot.send_message(
                    user.telegram_id,
                    text,
                    parse_mode="Markdown",
                    reply_markup=keyboard
                )
                
                # Update notification status
                notification.status = NotificationStatus.DELIVERED
                notification.metadata['delivered_at'] = datetime.utcnow().isoformat()
                await self.session.commit()
                
                # Update cache
                await self._update_notification_cache(notification)
                
                return True
                
            except Exception as e:
                logger.error(f"Error sending notification {notification.id}: {e}")
                notification.status = NotificationStatus.FAILED
                notification.metadata['error'] = str(e)
                await self.session.commit()
                return False
            
        except Exception as e:
            logger.error(f"Error in _send_notification: {e}")
            return False

    async def _schedule_notification(self, notification: UserNotification) -> bool:
        """Schedule notification for later delivery"""
        try:
            if not notification.schedule_time:
                return False
            
            # Calculate delay
            delay = (notification.schedule_time - datetime.utcnow()).total_seconds()
            if delay <= 0:
                return await self._send_notification(notification)
            
            # Add to schedule queue
            await self.cache.set(
                f"scheduled_notification:{notification.id}",
                notification.to_dict(),
                timeout=int(delay)
            )
            
            return True
            
        except Exception as e:
            logger.error(f"Error scheduling notification: {e}")
            return False

    async def mark_as_read(
        self,
        notification_id: int,
        user_id: int
    ) -> bool:
        """Mark notification as read"""
        try:
            notification = await self.get(notification_id)
            if not notification or notification.user_id != user_id:
                return False
            
            notification.status = NotificationStatus.READ
            notification.metadata['read_at'] = datetime.utcnow().isoformat()
            await self.session.commit()
            
            # Update cache
            await self._update_notification_cache(notification)
            
            return True
            
        except Exception as e:
            logger.error(f"Error marking notification as read: {e}")
            return False

    async def get_user_notifications(
        self,
        user_id: int,
        types: Optional[List[NotificationType]] = None,
        status: Optional[NotificationStatus] = None,
        limit: int = 50,
        offset: int = 0
    ) -> List[UserNotification]:
        """Get user notifications with filtering"""
        try:
            query = select(UserNotification).filter(
                UserNotification.user_id == user_id
            )
            
            if types:
                query = query.filter(UserNotification.type.in_(types))
            
            if status:
                query = query.filter(UserNotification.status == status)
            
            query = query.order_by(
                UserNotification.created_at.desc()
            ).offset(offset).limit(limit)
            
            result = await self.session.execute(query)
            return list(result.scalars().all())
            
        except Exception as e:
            logger.error(f"Error getting user notifications: {e}")
            return []

    async def get_unread_count(self, user_id: int) -> int:
        """Get count of unread notifications"""
        try:
            cache_key = f"unread_notifications:{user_id}"
            
            # Try cache
            cached = await self.cache.get(cache_key)
            if cached is not None:
                return cached
            
            # Get from database
            result = await self.session.execute(
                select(func.count())
                .select_from(UserNotification)
                .filter(
                    UserNotification.user_id == user_id,
                    UserNotification.status.in_([
                        NotificationStatus.PENDING,
                        NotificationStatus.DELIVERED
                    ])
                )
            )
            count = result.scalar() or 0
            
            # Cache result
            await self.cache.set(cache_key, count, timeout=300)
            
            return count
            
        except Exception as e:
            logger.error(f"Error getting unread count: {e}")
            return 0

    async def delete_old_notifications(self, days: int = 30) -> int:
        """Delete old notifications"""
        try:
            cutoff = datetime.utcnow() - timedelta(days=days)
            
            result = await self.session.execute(
                select(UserNotification)
                .filter(
                    UserNotification.created_at < cutoff,
                    UserNotification.status.in_([
                        NotificationStatus.DELIVERED,
                        NotificationStatus.READ,
                        NotificationStatus.FAILED
                    ])
                )
            )
            notifications = result.scalars().all()
            
            for notification in notifications:
                await self.session.delete(notification)
            
            await self.session.commit()
            
            return len(notifications)
            
        except Exception as e:
            logger.error(f"Error deleting old notifications: {e}")
            return 0

    async def _check_rate_limit(
        self,
        user_id: int,
        notification_type: NotificationType
    ) -> bool:
        """Check if user has exceeded rate limit"""
        if notification_type not in self.RATE_LIMITS:
            return True
            
        limit = self.RATE_LIMITS[notification_type]
        cache_key = f"notification_rate:{user_id}:{notification_type}"
        
        count = await self.cache.get(cache_key) or 0
        if count >= limit:
            return False
            
        await self.cache.increment(cache_key)
        if count == 0:
            await self.cache.expire(cache_key, 3600)  # 1 hour
            
        return True

    async def _check_user_preferences(
        self,
        user: User,
        notification_type: NotificationType
    ) -> bool:
        """Check if user has enabled this notification type"""
        preferences = user.notification_preferences or {}
        return preferences.get(notification_type, True)

    async def _update_notification_cache(self, notification: UserNotification):
        """Update notification in cache"""
        # Update unread count
        if notification.status == NotificationStatus.READ:
            cache_key = f"unread_notifications:{notification.user_id}"
            count = await self.cache.get(cache_key)
            if count is not None and count > 0:
                await self.cache.set(cache_key, count - 1)

# Create service instance
notification_service = NotificationService(None)  # Session will be injected

async def setup_notification_scheduler():
    """Setup background task for processing scheduled notifications"""
    while True:
        try:
            # Get all scheduled notifications
            now = datetime.utcnow()
            pattern = "scheduled_notification:*"
            
            scheduled = await cache.get_by_pattern(pattern)
            
            for key, notification_data in scheduled.items():
                notification_id = int(key.split(":")[-1])
                
                # Get notification
                notification = await notification_service.get(notification_id)
                if not notification:
                    await cache.delete(key)
                    continue
                
                # Check if it's time to send
                if notification.schedule_time <= now:
                    await notification_service._send_notification(notification)
                    await cache.delete(key)
            
            # Sleep for a short interval
            await asyncio.sleep(60)  # Check every minute
            
        except Exception as e:
            logger.error(f"Error in notification scheduler: {e}")
            await asyncio.sleep(60)

__all__ = ['NotificationService', 'notification_service', 'setup_notification_scheduler']
```

# telegram_bot\services\payments\providers.py

```py
from typing import Optional, Dict, Any, Tuple
from decimal import Decimal
import logging
from datetime import datetime
import hmac
import hashlib
import aiohttp
import base64
from sqlalchemy import select

from telegram_bot.models import Payment, PaymentStatus, PaymentProvider
from telegram_bot.core.errors import PaymentError
from telegram_bot.core.config import settings
from telegram_bot.core.cache import cache_service
from telegram_bot.services.base import BaseService

logger = logging.getLogger(__name__)

class PaymentProviderBase:
    """Base payment provider implementation"""
    def __init__(self, config: Dict[str, Any]):
        self.config = config
    
    def _generate_signature(self, data: str, key: Optional[str] = None) -> str:
        key = key or self.config.get('secret_key', '')
        return hmac.new(
            key.encode(),
            data.encode(),
            hashlib.sha256
        ).hexdigest()

class ClickProvider(PaymentProviderBase):
    """Click payment provider"""
    async def create_payment_url(
        self,
        amount: Decimal,
        order_id: str,
        return_url: Optional[str] = None
    ) -> Optional[str]:
        try:
            timestamp = int(datetime.utcnow().timestamp())
            sign_string = f"{self.config['merchant_id']}{amount}{order_id}{timestamp}"
            signature = self._generate_signature(sign_string)
            
            params = {
                'merchant_id': self.config['merchant_id'],
                'amount': str(amount),
                'transaction_param': order_id,
                'return_url': return_url or self.config.get('return_url'),
                'sign_time': timestamp,
                'sign_string': signature
            }
            
            query = '&'.join(f"{k}={v}" for k, v in params.items())
            return f"https://my.click.uz/services/pay?{query}"
        except Exception as e:
            logger.error(f"Error creating Click payment: {e}")
            return None

    async def verify_callback(self, data: Dict) -> bool:
        try:
            sign_string = (
                f"{data['click_trans_id']}"
                f"{self.config['secret_key']}"
                f"{data['merchant_trans_id']}"
                f"{data['amount']}"
                f"{data['sign_time']}"
            )
            signature = self._generate_signature(sign_string)
            return signature == data['sign_string']
        except Exception as e:
            logger.error(f"Error verifying Click signature: {e}")
            return False

class PaymeProvider(PaymentProviderBase):
    """Payme payment provider"""
    def _get_auth_token(self) -> str:
        return base64.b64encode(
            f"{self.config['merchant_id']}:{self.config['secret_key']}".encode()
        ).decode()

    async def create_payment_url(
        self,
        amount: Decimal,
        order_id: str,
        return_url: Optional[str] = None
    ) -> Optional[str]:
        try:
            amount_tiyins = int(amount * 100)
            
            data = {
                'method': 'cards.create',
                'params': {
                    'amount': amount_tiyins,
                    'account': {'order_id': order_id},
                    'return_url': return_url or self.config.get('return_url')
                }
            }
            
            headers = {
                'X-Auth': self._get_auth_token(),
                'Content-Type': 'application/json'
            }
            
            async with aiohttp.ClientSession() as session:
                async with session.post(
                    'https://checkout.payme.uz/api',
                    json=data,
                    headers=headers
                ) as response:
                    result = await response.json()
                    
                    if 'error' in result:
                        raise PaymentError(
                            f"Payme error: {result['error']['message']}"
                        )
                    
                    return f"https://checkout.payme.uz/pay/{result['result']['card_token']}"
        except Exception as e:
            logger.error(f"Error creating Payme payment: {e}")
            return None

class UzumProvider(PaymentProviderBase):
    """Uzum payment provider"""
    async def create_payment_url(
        self,
        amount: Decimal,
        order_id: str,
        return_url: Optional[str] = None
    ) -> Optional[str]:
        try:
            data = {
                'merchantId': self.config['merchant_id'],
                'amount': str(amount),
                'orderId': order_id,
                'currency': 'UZS',
                'returnUrl': return_url or self.config.get('return_url'),
                'timestamp': datetime.utcnow().isoformat()
            }
            
            data['signature'] = self._generate_signature(
                ';'.join(f"{k}={v}" for k, v in sorted(data.items()))
            )
            
            async with aiohttp.ClientSession() as session:
                async with session.post(
                    'https://api.uzum.uz/payment/create',
                    json=data
                ) as response:
                    result = await response.json()
                    
                    if not result.get('success'):
                        raise PaymentError(
                            f"Uzum error: {result.get('message')}"
                        )
                    
                    return result['data']['paymentUrl']
        except Exception as e:
            logger.error(f"Error creating Uzum payment: {e}")
            return None

class UnifiedPaymentService(BaseService[Payment]):
    """Unified payment service"""
    
    def __init__(self, session):
        super().__init__(Payment, session)
        self.cache = cache_service
        self.providers = {
            'click': ClickProvider(settings.CLICK_CONFIG),
            'payme': PaymeProvider(settings.PAYME_CONFIG),
            'uzum': UzumProvider(settings.UZUM_CONFIG)
        }
        
        # Payment limits
        self.MIN_AMOUNT = Decimal('1000.00')
        self.MAX_AMOUNT = Decimal('10000000.00')
    
    async def create_payment(
        self,
        amount: Decimal,
        consultation_id: int,
        provider: str,
        user_id: int,
        return_url: Optional[str] = None,
        metadata: Dict = None
    ) -> Tuple[Payment, str]:
        """Create new payment and get payment URL"""
        if amount < self.MIN_AMOUNT or amount > self.MAX_AMOUNT:
            raise PaymentError(
                f"Amount must be between {self.MIN_AMOUNT} and {self.MAX_AMOUNT}"
            )
            
        try:
            provider_instance = self.providers.get(provider)
            if not provider_instance:
                raise PaymentError(f"Unknown payment provider: {provider}")
            
            payment = await self.create(
                amount=amount,
                consultation_id=consultation_id,
                provider=PaymentProvider[provider.upper()],
                status=PaymentStatus.PENDING,
                user_id=user_id,
                metadata=metadata or {
                    'created_at': datetime.utcnow().isoformat(),
                    'return_url': return_url
                }
            )
            
            payment_url = await provider_instance.create_payment_url(
                amount=amount,
                order_id=f"order_{payment.id}",
                return_url=return_url
            )
            
            if not payment_url:
                raise PaymentError("Failed to get payment URL")
            
            payment.metadata['payment_url'] = payment_url
            await self.session.commit()
            
            await self.cache.set(
                f"payment:{payment.id}",
                payment.to_dict(),
                timeout=900
            )
            
            return payment, payment_url
            
        except Exception as e:
            logger.error(f"Error creating payment: {e}")
            raise PaymentError(str(e))

    async def process_callback(
        self,
        provider: str,
        data: Dict
    ) -> bool:
        """Process payment callback"""
        try:
            provider_instance = self.providers.get(provider)
            if not provider_instance:
                raise PaymentError(f"Unknown provider: {provider}")
                
            if not await provider_instance.verify_callback(data):
                raise PaymentError("Invalid callback signature")
                
            # Process payment data
            payment_id = int(data.get('order_id', '').split('_')[1])
            payment = await self.get(payment_id)
            
            if not payment:
                raise PaymentError("Payment not found")
                
            # Update payment status
            old_status = payment.status
            payment.status = PaymentStatus.COMPLETED
            payment.metadata.update({
                'callback_data': data,
                'processed_at': datetime.utcnow().isoformat()
            })
            
            await self.session.commit()
            await self.cache.delete(f"payment:{payment.id}")
            
            # Handle status change
            if old_status != payment.status:
                await self._handle_payment_status_change(payment)
                
            return True
            
        except Exception as e:
            logger.error(f"Error processing callback: {e}")
            return False

    async def _handle_payment_status_change(self, payment: Payment) -> None:
        """Handle payment status change"""
        try:
            if payment.status == PaymentStatus.COMPLETED:
                # Update consultation status
                from telegram_bot.models import Consultation
                consultation = await self.session.get(
                    Consultation,
                    payment.consultation_id
                )
                if consultation:
                    consultation.status = 'PAID'
                    consultation.metadata['payment_completed_at'] = \
                        datetime.utcnow().isoformat()
                    await self.session.commit()
                    
                # Notify user
                await self._notify_user(
                    payment.user_id,
                    'payment_success'
                )
        except Exception as e:
            logger.error(f"Error handling status change: {e}")

    async def _notify_user(
        self,
        user_id: int,
        message_type: str,
        **kwargs
    ) -> None:
        """Send notification to user"""
        try:
            from telegram_bot.bot import bot
            from telegram_bot.models import User
            
            user = await self.session.get(User, user_id)
            if user:
                await bot.send_message(
                    user.telegram_id,
                    self._get_message_text(user.language, message_type, **kwargs)
                )
        except Exception as e:
            logger.error(f"Error notifying user: {e}")

# Create service instance
payment_service = UnifiedPaymentService(None)  # Session will be injected
```

# telegram_bot\services\payments\service.py

```py
# File: telegram_bot/services/payments/service.py

from decimal import Decimal
from typing import Optional, Dict, Any, Tuple
import logging
from datetime import datetime
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from telegram_bot.models import Payment, PaymentStatus, PaymentProvider
from telegram_bot.core.errors import PaymentError
from telegram_bot.services.base import BaseService
from telegram_bot.core.cache import cache_service
from .providers import get_payment_provider

logger = logging.getLogger(__name__)

class PaymentService(BaseService[Payment]):
    """Unified payment processing service"""
    
    def __init__(self, session: AsyncSession):
        super().__init__(Payment, session)
        
        # Payment limits
        self.MIN_AMOUNT = Decimal('1000.00')
        self.MAX_AMOUNT = Decimal('10000000.00')
        
    async def create_payment(
        self,
        amount: Decimal,
        consultation_id: int,
        provider: str,
        user_id: int,
        return_url: Optional[str] = None,
        metadata: Dict = None
    ) -> Tuple[Payment, str]:
        """Create new payment and get payment URL"""
        # Validate amount
        if amount < self.MIN_AMOUNT or amount > self.MAX_AMOUNT:
            raise PaymentError(
                f"Amount must be between {self.MIN_AMOUNT} and {self.MAX_AMOUNT}"
            )
            
        try:
            # Get payment provider
            payment_provider = get_payment_provider(provider)
            
            # Create payment record
            payment = await self.create(
                amount=amount,
                consultation_id=consultation_id,
                provider=PaymentProvider[provider.upper()],
                status=PaymentStatus.PENDING,
                user_id=user_id,
                metadata=metadata or {
                    'created_at': datetime.utcnow().isoformat(),
                    'return_url': return_url
                }
            )
            
            # Get payment URL from provider
            payment_url = await payment_provider.create_payment(
                amount=amount,
                order_id=f"order_{payment.id}",
                return_url=return_url
            )
            
            if not payment_url:
                raise PaymentError("Failed to get payment URL")
                
            # Update payment record
            payment.metadata['payment_url'] = payment_url
            await self.session.commit()
            
            # Cache payment data
            await cache_service.set(
                f"payment:{payment.id}",
                payment.to_dict(),
                timeout=900  # 15 minutes
            )
            
            return payment, payment_url
            
        except Exception as e:
            logger.error(f"Error creating payment: {e}")
            raise PaymentError(f"Payment creation failed: {str(e)}")

    async def process_callback(
        self,
        provider: str,
        data: Dict
    ) -> bool:
        """Process payment callback"""
        try:
            # Get payment provider
            payment_provider = get_payment_provider(provider)
            
            # Verify and parse callback
            payment_data = await payment_provider.process_callback(data)
            if not payment_data:
                logger.error("Failed to parse callback data")
                return False
                
            # Get payment
            payment = await self._get_payment_by_order(payment_data['order_id'])
            if not payment:
                logger.error("Payment not found")
                return False
                
            # Update payment status
            old_status = payment.status
            payment.status = PaymentStatus[payment_data['status']]
            payment.transaction_id = payment_data.get('transaction_id')
            payment.metadata.update({
                'callback_data': data,
                'processed_at': datetime.utcnow().isoformat()
            })
            
            await self.session.commit()
            
            # Clear cache
            await cache_service.delete(f"payment:{payment.id}")
            
            # Handle status change
            if old_status != payment.status:
                await self._handle_payment_status_change(payment)
                
            return True
            
        except Exception as e:
            logger.error(f"Error processing payment callback: {e}")
            return False

    async def process_refund(
        self,
        payment_id: int,
        amount: Optional[Decimal] = None,
        reason: Optional[str] = None
    ) -> bool:
        """Process payment refund"""
        try:
            # Get payment
            payment = await self.get(payment_id)
            if not payment:
                raise PaymentError("Payment not found")
                
            if payment.status != PaymentStatus.COMPLETED:
                raise PaymentError("Only completed payments can be refunded")
                
            # Get payment provider
            payment_provider = get_payment_provider(
                payment.provider.value.lower()
            )
            
            # Process refund
            refund_success = await payment_provider.process_refund(
                payment.transaction_id,
                amount
            )
            
            if refund_success:
                # Update payment status
                payment.status = PaymentStatus.REFUNDED
                payment.metadata['refund'] = {
                    'amount': str(amount) if amount else None,
                    'reason': reason,
                    'refunded_at': datetime.utcnow().isoformat()
                }
                await self.session.commit()
                
                # Clear cache
                await cache_service.delete(f"payment:{payment.id}")
                
                # Notify user
                await self._notify_user_about_refund(payment)
                
            return refund_success
            
        except Exception as e:
            logger.error(f"Error processing refund: {e}")
            return False

    async def verify_payment(self, payment_id: int) -> bool:
        """Verify payment status with provider"""
        try:
            payment = await self.get(payment_id)
            if not payment:
                return False
                
            payment_provider = get_payment_provider(
                payment.provider.value.lower()
            )
            
            return await payment_provider.verify_payment(
                payment.transaction_id
            )
            
        except Exception as e:
            logger.error(f"Error verifying payment: {e}")
            return False

    async def _get_payment_by_order(self, order_id: str) -> Optional[Payment]:
        """Get payment by order ID"""
        if not order_id.startswith('order_'):
            return None
            
        try:
            payment_id = int(order_id.split('_')[1])
            return await self.get(payment_id)
        except (ValueError, IndexError):
            return None

    async def _handle_payment_status_change(self, payment: Payment) -> None:
        """Handle payment status change"""
        try:
            if payment.status == PaymentStatus.COMPLETED:
                # Update consultation status
                from telegram_bot.models import Consultation
                consultation = await self.session.get(
                    Consultation,
                    payment.consultation_id
                )
                if consultation:
                    consultation.status = 'PAID'
                    consultation.metadata['payment_completed_at'] = \
                        datetime.utcnow().isoformat()
                    await self.session.commit()
                    
                # Notify user
                await self._notify_user_about_payment(payment)
                
            # Track payment event
            await self._track_payment_event(payment)
            
        except Exception as e:
            logger.error(f"Error handling payment status change: {e}")

    async def _notify_user_about_payment(self, payment: Payment) -> None:
        """Notify user about payment status"""
        try:
            from telegram_bot.bot import bot
            from telegram_bot.core.constants import TEXTS
            
            user = await self.session.get('User', payment.user_id)
            if user:
                await bot.send_message(
                    user.telegram_id,
                    TEXTS[user.language]['payment_success']
                )
                
        except Exception as e:
            logger.error(f"Error notifying user about payment: {e}")

    async def _notify_user_about_refund(self, payment: Payment) -> None:
        """Notify user about refund"""
        try:
            from telegram_bot.bot import bot
            from telegram_bot.core.constants import TEXTS
            
            user = await self.session.get('User', payment.user_id)
            if user:
                await bot.send_message(
                    user.telegram_id,
                    TEXTS[user.language]['payment_refunded']
                )
                
        except Exception as e:
            logger.error(f"Error notifying user about refund: {e}")

    async def _track_payment_event(self, payment: Payment) -> None:
        """Track payment analytics"""
        try:
            event_data = {
                'payment_id': payment.id,
                'status': payment.status.value,
                'amount': float(payment.amount),
                'provider': payment.provider.value
            }
            
            # Update cache stats
            await cache_service.increment(
                f"stats:payments:{payment.status.value}"
            )
            await cache_service.increment(
                f"stats:payments:{payment.provider.value}",
                float(payment.amount)
            )
            
            # Track user stats
            user_key = f"user:payments:{payment.user_id}"
            user_stats = await cache_service.get(user_key) or {
                'total': 0,
                'amount': 0
            }
            user_stats['total'] += 1
            user_stats['amount'] += float(payment.amount)
            await cache_service.set(user_key, user_stats)
            
        except Exception as e:
            logger.error(f"Error tracking payment event: {e}")
```

# telegram_bot\services\questions.py

```py
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
```

# telegram_bot\services\users.py

```py
from typing import Optional, List, Dict, Any
from datetime import datetime, timedelta
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from telegram_bot.models import User, UserEvent, UserNotification
from telegram_bot.services.base import BaseService
from telegram_bot.core.constants import UserRole
from telegram_bot.core.security import hash_password
from telegram_bot.models import (
    User, Question, Answer, Consultation, ConsultationStatus,
)
from telegram_bot.services.base import update
class UserService(BaseService[User]):
    """User service"""
    
    async def get_by_telegram_id(
        self,
        telegram_id: int
    ) -> Optional[User]:
        """Get user by telegram ID"""
        cache_key = f"user_tg:{telegram_id}"
        
        # Try to get from cache
        cached = await self.cache.get(cache_key)
        if cached:
            return User.from_dict(cached)
        
        # Get from database
        result = await self.session.execute(
            select(User).filter(User.telegram_id == telegram_id)
        )
        user = result.scalar_one_or_none()
        
        # Cache result
        if user:
            await self.cache.set(cache_key, user.to_dict())
        
        return user
    
    async def create_user(
        self,
        telegram_id: int,
        username: Optional[str] = None,
        full_name: Optional[str] = None,
        language: str = 'uz'
    ) -> User:
        """Create new user"""
        user = await self.create(
            telegram_id=telegram_id,
            username=username,
            full_name=full_name,
            language=language
        )
        
        # Cache user
        await self.cache.set(
            f"user_tg:{telegram_id}",
            user.to_dict()
        )
        
        return user
    
    async def update_user_language(
        self,
        user_id: int,
        language: str
    ) -> Optional[User]:
        """Update user language"""
        user = await self.update(
            user_id,
            language=language
        )
        
        if user:
            # Update cache
            await self.cache.delete(f"user_tg:{user.telegram_id}")
        
        return user
    
    async def get_active_users(
        self,
        days: int = 7
    ) -> List[User]:
        """Get active users for last N days"""
        since = datetime.utcnow() - timedelta(days=days)
        
        result = await self.session.execute(
            select(User).filter(
                User.last_active >= since,
                User.is_blocked == False
            )
        )
        return list(result.scalars().all())
    
    async def get_user_stats(
        self,
        user_id: int
    ) -> Dict[str, Any]:
        """Get user statistics"""

        user = await self.get(user_id)
        if not user:
            return {}
    
        # Get questions count
        questions_count = await self.session.scalar(
            select(func.count(Question.id)).filter(
                Question.user_id == user_id
            )
        )
        
        # Get consultations count
        consultations_count = await self.session.scalar(
            select(func.count(Consultation.id)).filter(
                Consultation.user_id == user_id
            )
        )
        
        # Get total spent amount
        total_spent = await self.session.scalar(
            select(func.sum(Consultation.amount)).filter(
                Consultation.user_id == user_id,
                Consultation.status == ConsultationStatus.COMPLETED
            )
        )
        
        return {
            'questions_count': questions_count,
            'consultations_count': consultations_count,
            'total_spent': float(total_spent or 0),
            'last_active': user.last_active,
            'join_date': user.created_at
        }
    
    async def track_user_activity(
        self,
        user_id: int,
        activity_type: str,
        metadata: Dict = None
    ) -> None:
        """Track user activity"""
        # Update last active
        await self.update(
            user_id,
            last_active=datetime.utcnow()
        )
        
        # Create activity event
        event = UserEvent(
            user_id=user_id,
            event_type=activity_type,
            event_data=metadata or {}
        )
        self.session.add(event)
        await self.session.commit()
    
    async def create_notification(
        self,
        user_id: int,
        title: str,
        message: str,
        notification_type: str,
        metadata: Dict = None
    ) -> UserNotification:
        """Create user notification"""
        notification = UserNotification(
            user_id=user_id,
            title=title,
            message=message,
            type=notification_type,
            metadata=metadata or {}
        )
        self.session.add(notification)
        await self.session.commit()
        
        # Invalidate notifications cache
        await self.cache.delete(f"user_notifications:{user_id}")
        
        return notification
    
    async def get_unread_notifications(
        self,
        user_id: int
    ) -> List[UserNotification]:
        """Get unread notifications"""
        cache_key = f"user_notifications:{user_id}"
        
        # Try from cache
        cached = await self.cache.get(cache_key)
        if cached:
            return [UserNotification.from_dict(n) for n in cached]
        
        # Get from database
        result = await self.session.execute(
            select(UserNotification)
            .filter(
                UserNotification.user_id == user_id,
                UserNotification.is_read == False
            )
            .order_by(UserNotification.created_at.desc())
        )
        notifications = list(result.scalars().all())
        
        # Cache result
        await self.cache.set(
            cache_key,
            [n.to_dict() for n in notifications]
        )
        
        return notifications
    
    async def mark_notifications_read(
        self,
        user_id: int,
        notification_ids: List[int] = None
    ) -> None:
        """Mark notifications as read"""
        query = update(UserNotification).where(
            UserNotification.user_id == user_id,
            UserNotification.is_read == False
        )
        
        if notification_ids:
            query = query.where(
                UserNotification.id.in_(notification_ids)
            )
            
        await self.session.execute(
            query.values(is_read=True)
        )
        await self.session.commit()
        
        # Invalidate cache
        await self.cache.delete(f"user_notifications:{user_id}")
    
    async def get_user_roles(
        self,
        user_id: int
    ) -> List[UserRole]:
        """Get user roles"""
        user = await self.get(user_id)
        return user.roles if user else []
    
    async def add_user_role(
        self,
        user_id: int,
        role: UserRole
    ) -> bool:
        """Add role to user"""
        user = await self.get(user_id)
        if not user:
            return False
            
        user.add_role(role)
        await self.session.commit()
        
        # Invalidate cache
        await self.cache.delete(f"user_tg:{user.telegram_id}")
        
        return True
    
    async def remove_user_role(
        self,
        user_id: int,
        role: UserRole
    ) -> bool:
        """Remove role from user"""
        user = await self.get(user_id)
        if not user:
            return False
            
        user.remove_role(role)
        await self.session.commit()
        
        # Invalidate cache
        await self.cache.delete(f"user_tg:{user.telegram_id}")
        
        return True
    
    async def get_admin_users(self) -> List[User]:
        """Get all admin users"""
        result = await self.session.execute(
            select(User).filter(
                User.roles.contains([UserRole.ADMIN])
            )
        )
        return list(result.scalars().all())
    
    async def update_user_settings(
        self,
        user_id: int,
        settings: Dict
    ) -> Optional[User]:
        """Update user settings"""
        user = await self.get(user_id)
        if not user:
            return None
            
        user.update_settings(settings)
        await self.session.commit()
        
        # Invalidate cache
        await self.cache.delete(f"user_tg:{user.telegram_id}")
        
        return user
    
    async def get_user_activity(
        self,
        user_id: int,
        days: int = 30
    ) -> List[Dict]:
        """Get user activity history"""
        since = datetime.utcnow() - timedelta(days=days)
        
        result = await self.session.execute(
            select(UserEvent)
            .filter(
                UserEvent.user_id == user_id,
                UserEvent.created_at >= since
            )
            .order_by(UserEvent.created_at.desc())
        )
        events = result.scalars().all()
        
        return [
            {
                'type': event.event_type,
                'data': event.event_data,
                'created_at': event.created_at.isoformat()
            }
            for event in events
        ]
    
    async def get_user_metrics(
        self,
        user_id: int
    ) -> Dict[str, Any]:
        """Get user metrics"""
        # Get questions metrics
        questions_result = await self.session.execute(
            select(
                func.count(Question.id).label('total'),
                func.count(Question.id)
                .filter(Question.is_answered == True)
                .label('answered')
            )
            .filter(Question.user_id == user_id)
        )
        questions_metrics = questions_result.first()
        
        # Get consultations metrics
        consultations_result = await self.session.execute(
            select(
                func.count(Consultation.id).label('total'),
                func.count(Consultation.id)
                .filter(Consultation.status == ConsultationStatus.COMPLETED)
                .label('completed'),
                func.sum(Consultation.amount)
                .filter(Consultation.status == ConsultationStatus.COMPLETED)
                .label('spent')
            )
            .filter(Consultation.user_id == user_id)
        )
        consultations_metrics = consultations_result.first()
        
        return {
            'questions': {
                'total': questions_metrics.total,
                'answered': questions_metrics.answered,
                'unanswered': questions_metrics.total - questions_metrics.answered
            },
            'consultations': {
                'total': consultations_metrics.total,
                'completed': consultations_metrics.completed,
                'spent': float(consultations_metrics.spent or 0)
            }
        }
```

# telegram_bot\utils\__init__.py

```py
from telegram_bot.utils.text_processor import text_processor
from telegram_bot.utils.validators import validator
from telegram_bot.utils.helpers import (
    format_money,
    format_phone,
    generate_random_string,
    hash_string,
    JSONEncoder
)

__all__ = [
    'text_processor',
    'validator',
    'format_money',
    'format_phone',
    'generate_random_string',
    'hash_string',
    'JSONEncoder'
]

```

# telegram_bot\utils\helpers.py

```py
import json
from typing import Any, Dict, List
from datetime import datetime, date, time
from decimal import Decimal
import hashlib
import secrets
from pathlib import Path

class JSONEncoder(json.JSONEncoder):
    """Custom JSON encoder for complex types"""
    def default(self, obj):
        if isinstance(obj, (datetime, date)):
            return obj.isoformat()
        if isinstance(obj, time):
            return obj.strftime('%H:%M')
        if isinstance(obj, Decimal):
            return str(obj)
        if isinstance(obj, Path):
            return str(obj)
        return super().default(obj)

def generate_random_string(length: int = 32) -> str:
    """Generate random string"""
    return secrets.token_hex(length // 2)

def hash_string(s: str) -> str:
    """Generate hash from string"""
    return hashlib.sha256(s.encode()).hexdigest()

def format_money(amount: Decimal) -> str:
    """Format money amount"""
    return f"{amount:,.2f} сум"

def format_phone(phone: str) -> str:
    """Format phone number"""
    phone = phone.replace('+', '')
    if phone.startswith('998'):
        return f"+{phone[:3]} {phone[3:5]} {phone[5:8]} {phone[8:]}"
    if phone.startswith('7'):
        return f"+{phone[:1]} {phone[1:4]} {phone[4:7]} {phone[7:]}"
    return phone

def group_by(items: List[Dict], key: str) -> Dict[Any, List[Dict]]:
    """Group list of dicts by key"""
    result = {}
    for item in items:
        k = item.get(key)
        if k not in result:
            result[k] = []
        result[k].append(item)
    return result

def chunk_list(lst: List, n: int) -> List[List]:
    """Split list into chunks"""
    return [lst[i:i + n] for i in range(0, len(lst), n)]

def deep_update(d: dict, u: dict) -> dict:
    """Deep update dict"""
    for k, v in u.items():
        if isinstance(v, dict):
            d[k] = deep_update(d.get(k, {}), v)
        else:
            d[k] = v
    return d

def strip_html(text: str) -> str:
    """Remove HTML tags from text"""
    import re
    clean = re.compile('<.*?>')
    return re.sub(clean, '', text)

def truncate(text: str, length: int) -> str:
    """Truncate text to length"""
    return text[:length] + '...' if len(text) > length else text

def parse_bool(value: Any) -> bool:
    """Parse boolean value"""
    if isinstance(value, bool):
        return value
    if isinstance(value, str):
        return value.lower() in ('true', '1', 't', 'y', 'yes')
    return bool(value)
```

# telegram_bot\utils\text_processor.py

```py
import re
from typing import List, Tuple, Set, Optional, Dict
import numpy as np
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity
from nltk.tokenize import word_tokenize, sent_tokenize
from nltk.corpus import stopwords
from nltk.stem import SnowballStemmer
from rapidfuzz import fuzz
import pymorphy2
from functools import lru_cache
import logging
from dataclasses import dataclass

logger = logging.getLogger(__name__)

@dataclass
class TextStats:
    """Text statistics container"""
    char_count: int
    word_count: int
    sentence_count: int
    avg_word_length: float
    unique_words: int
    language: str

class TextProcessor:
    """Enhanced text processor with similarity detection and analysis"""
    
    def __init__(self):
        # Initialize language tools
        self.morph = pymorphy2.MorphAnalyzer()
        self.ru_stemmer = SnowballStemmer('russian')
        self.uz_stemmer = SnowballStemmer('russian')  # Use Russian for Uzbek
        
        # Load stopwords
        self.stopwords = {
            'ru': set(stopwords.words('russian')),
            'uz': set()  # Custom Uzbek stopwords would go here
        }
        
        # Initialize vectorizer
        self.vectorizer = TfidfVectorizer(
            analyzer='word',
            tokenizer=self._tokenize,
            stop_words=None,
            min_df=2,
            max_df=0.95,
            ngram_range=(1, 2)
        )
        
        # Similarity thresholds
        self.SIMILARITY_THRESHOLD = 0.7
        self.FUZZY_THRESHOLD = 80
        
    def _clean_text(self, text: str) -> str:
        """Clean and normalize text"""
        # Convert to lowercase
        text = text.lower()
        
        # Remove special characters but keep sentence structure
        text = re.sub(r'[^\w\s.!?]', ' ', text)
        
        # Normalize whitespace
        text = re.sub(r'\s+', ' ', text)
        
        return text.strip()
        
    @lru_cache(maxsize=1000)
    def _tokenize(self, text: str, language: str = 'ru') -> List[str]:
        """Tokenize text with language-specific processing"""
        # Clean text
        text = self._clean_text(text)
        
        # Tokenize
        tokens = word_tokenize(text)
        
        # Remove stopwords
        tokens = [
            token for token in tokens 
            if token not in self.stopwords.get(language, set())
        ]
        
        # Normalize tokens based on language
        if language == 'ru':
            tokens = [
                self.morph.parse(token)[0].normal_form 
                for token in tokens
            ]
        else:
            tokens = [
                self.uz_stemmer.stem(token)
                for token in tokens
            ]
            
        return tokens
        
    def get_text_similarity(
        self,
        text1: str,
        text2: str,
        language: str = 'ru'
    ) -> float:
        """Get similarity score between two texts"""
        # Get tokens
        tokens1 = set(self._tokenize(text1, language))
        tokens2 = set(self._tokenize(text2, language))
        
        # Calculate Jaccard similarity
        jaccard = len(tokens1 & tokens2) / len(tokens1 | tokens2) if tokens1 or tokens2 else 0
        
        # Calculate TF-IDF cosine similarity
        tfidf = self.vectorizer.fit_transform([text1, text2])
        cosine = cosine_similarity(tfidf[0:1], tfidf[1:2])[0][0]
        
        # Calculate fuzzy ratio
        fuzzy = fuzz.ratio(text1.lower(), text2.lower()) / 100
        
        # Weighted average of different metrics
        similarity = (
            0.4 * cosine +  # TF-IDF similarity
            0.4 * jaccard + # Token overlap
            0.2 * fuzzy     # Fuzzy string matching
        )
        
        return float(similarity)
        
    def find_similar_texts(
        self,
        query: str,
        candidates: List[str],
        language: str = 'ru',
        threshold: float = None,
        top_k: int = 5
    ) -> List[Tuple[int, float]]:
        """Find similar texts with rankings"""
        threshold = threshold or self.SIMILARITY_THRESHOLD
        
        if not candidates:
            return []
            
        # Calculate similarities
        similarities = []
        for idx, candidate in enumerate(candidates):
            score = self.get_text_similarity(query, candidate, language)
            if score >= threshold:
                similarities.append((idx, score))
                
        # Sort by similarity score
        similarities.sort(key=lambda x: x[1], reverse=True)
        
        return similarities[:top_k]
        
    def extract_keywords(
        self,
        text: str,
        language: str = 'ru',
        top_k: int = 5
    ) -> List[Tuple[str, float]]:
        """Extract keywords with importance scores"""
        # Tokenize
        tokens = self._tokenize(text, language)
        
        # Get TF-IDF scores
        tfidf = self.vectorizer.fit_transform([' '.join(tokens)])
        
        # Get feature names and scores
        feature_names = self.vectorizer.get_feature_names_out()
        scores = tfidf.toarray()[0]
        
        # Sort by score
        keywords = list(zip(feature_names, scores))
        keywords.sort(key=lambda x: x[1], reverse=True)
        
        return keywords[:top_k]
        
    def get_text_stats(self, text: str) -> TextStats:
        """Get comprehensive text statistics"""
        # Clean text
        clean_text = self._clean_text(text)
        
        # Get tokens and sentences
        tokens = word_tokenize(clean_text)
        sentences = sent_tokenize(clean_text)
        
        # Calculate stats
        return TextStats(
            char_count=len(text),
            word_count=len(tokens),
            sentence_count=len(sentences),
            avg_word_length=sum(len(t) for t in tokens) / len(tokens) if tokens else 0,
            unique_words=len(set(tokens)),
            language=self.detect_language(text)
        )
        
    def detect_language(self, text: str) -> str:
        """Detect text language (ru/uz)"""
        # Count character frequencies
        ru_chars = len(re.findall(r'[а-яё]', text.lower()))
        uz_chars = len(re.findall(r'[a-z]', text.lower()))
        
        return 'ru' if ru_chars > uz_chars else 'uz'
        
    def summarize_text(
        self,
        text: str,
        max_sentences: int = 3
    ) -> str:
        """Generate text summary"""
        # Get sentences
        sentences = sent_tokenize(text)
        if len(sentences) <= max_sentences:
            return text
            
        # Calculate sentence scores
        scores = []
        for sentence in sentences:
            # Score based on position
            position_score = 1.0
            if sentence == sentences[0]:
                position_score = 1.5
            elif sentence == sentences[-1]:
                position_score = 1.2
                
            # Score based on length
            length_score = min(len(sentence.split()) / 20.0, 1.0)
            
            # Combined score
            scores.append(position_score * length_score)
            
        # Get top sentences
        ranked_sentences = list(zip(sentences, scores))
        ranked_sentences.sort(key=lambda x: x[1], reverse=True)
        
        summary_sentences = [s[0] for s in ranked_sentences[:max_sentences]]
        summary_sentences.sort(key=lambda x: sentences.index(x))
        
        return ' '.join(summary_sentences)

# Create global instance
text_processor = TextProcessor()

```

# telegram_bot\utils\validators.py

```py
import re
from typing import Optional, Union, Any
from datetime import datetime
from decimal import Decimal
import phonenumbers
import logging

logger = logging.getLogger(__name__)

class ValidationError(Exception):
    """Base validation error"""
    pass

class Validator:
    @staticmethod
    def phone_number(
        phone: str,
        country_code: str = 'UZ'
    ) -> Optional[str]:
        """Validate and format phone number"""
        try:
            # Parse phone number
            parsed = phonenumbers.parse(phone, country_code)
            
            # Check if valid
            if not phonenumbers.is_valid_number(parsed):
                raise ValidationError("Invalid phone number")
            
            # Format to international format
            return phonenumbers.format_number(
                parsed,
                phonenumbers.PhoneNumberFormat.E164
            )
        except Exception as e:
            logger.error(f"Phone validation error: {e}")
            raise ValidationError("Invalid phone number format")
    
    @staticmethod
    def amount(
        amount: Union[str, int, float, Decimal],
        min_value: Optional[Decimal] = None,
        max_value: Optional[Decimal] = None
    ) -> Decimal:
        """Validate payment amount"""
        try:
            # Convert to Decimal
            if isinstance(amount, str):
                amount = Decimal(amount.replace(',', '.'))
            else:
                amount = Decimal(str(amount))
            
            # Check range
            if min_value and amount < min_value:
                raise ValidationError(
                    f"Amount must be at least {min_value}"
                )
            if max_value and amount > max_value:
                raise ValidationError(
                    f"Amount must be at most {max_value}"
                )
            
            return amount
            
        except (TypeError, ValueError) as e:
            logger.error(f"Amount validation error: {e}")
            raise ValidationError("Invalid amount format")
    
    @staticmethod
    def text_length(
        text: str,
        min_length: Optional[int] = None,
        max_length: Optional[int] = None
    ) -> str:
        """Validate text length"""
        if min_length and len(text) < min_length:
            raise ValidationError(
                f"Text must be at least {min_length} characters"
            )
        if max_length and len(text) > max_length:
            raise ValidationError(
                f"Text must be at most {max_length} characters"
            )
        return text
    
    @staticmethod
    def datetime(
        dt: Union[str, datetime],
        min_date: Optional[datetime] = None,
        max_date: Optional[datetime] = None,
        format: str = '%Y-%m-%d %H:%M:%S'
    ) -> datetime:
        """Validate datetime"""
        try:
            # Convert string to datetime if needed
            if isinstance(dt, str):
                dt = datetime.strptime(dt, format)
            
            # Check range
            if min_date and dt < min_date:
                raise ValidationError(
                    f"Date must be after {min_date.strftime(format)}"
                )
            if max_date and dt > max_date:
                raise ValidationError(
                    f"Date must be before {max_date.strftime(format)}"
                )
            
            return dt
            
        except ValueError as e:
            logger.error(f"Datetime validation error: {e}")
            raise ValidationError(f"Invalid datetime format, expected {format}")

    @staticmethod
    def email(email: str) -> str:
        """Validate email address"""
        pattern = r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$'
        if not re.match(pattern, email):
            raise ValidationError("Invalid email address")
        return email.lower()

    @staticmethod
    def language(lang: str) -> str:
        """Validate language code"""
        valid_languages = {'uz', 'ru'}
        if lang.lower() not in valid_languages:
            raise ValidationError(
                f"Invalid language code. Must be one of: {', '.join(valid_languages)}"
            )
        return lang.lower()

    @staticmethod
    def boolean(value: Any) -> bool:
        """Validate and convert boolean value"""
        if isinstance(value, bool):
            return value
        if isinstance(value, str):
            value = value.lower()
            if value in ('true', '1', 't', 'y', 'yes'):
                return True
            if value in ('false', '0', 'f', 'n', 'no'):
                return False
        raise ValidationError("Invalid boolean value")

    @staticmethod
    def telegram_username(username: str) -> str:
        """Validate Telegram username"""
        pattern = r'^@?[a-zA-Z0-9_]{5,32}$'
        if not re.match(pattern, username):
            raise ValidationError(
                "Invalid Telegram username. Must be 5-32 characters long and contain only letters, numbers and underscore"
            )
        return username.lstrip('@')

    @staticmethod
    def payment_data(data: dict) -> dict:
        """Validate payment data"""
        required_fields = {'amount', 'provider'}
        missing_fields = required_fields - set(data.keys())
        if missing_fields:
            raise ValidationError(
                f"Missing required payment fields: {', '.join(missing_fields)}"
            )
        
        # Validate amount
        data['amount'] = Validator.amount(
            data['amount'],
            min_value=Decimal('1000.00')
        )
        
        # Validate provider
        valid_providers = {'click', 'payme'}
        if data['provider'].lower() not in valid_providers:
            raise ValidationError(
                f"Invalid payment provider. Must be one of: {', '.join(valid_providers)}"
            )
        
        return data

    @staticmethod 
    def question_data(data: dict) -> dict:
        """Validate question data"""
        required_fields = {'text', 'language'}
        missing_fields = required_fields - set(data.keys())
        if missing_fields:
            raise ValidationError(
                f"Missing required question fields: {', '.join(missing_fields)}"
            )
        
        # Validate text
        data['text'] = Validator.text_length(
            data['text'],
            min_length=10,
            max_length=1000
        )
        
        # Validate language
        data['language'] = Validator.language(data['language'])
        
        return data

    @staticmethod
    def consultation_data(data: dict) -> dict:
        """Validate consultation data"""
        required_fields = {'phone_number', 'problem_description'}
        missing_fields = required_fields - set(data.keys())
        if missing_fields:
            raise ValidationError(
                f"Missing required consultation fields: {', '.join(missing_fields)}"
            )
        
        # Validate phone
        data['phone_number'] = Validator.phone_number(data['phone_number'])
        
        # Validate description
        data['problem_description'] = Validator.text_length(
            data['problem_description'],
            min_length=20,
            max_length=2000
        )
        
        # Validate scheduled time if present
        if 'scheduled_time' in data:
            data['scheduled_time'] = Validator.datetime(
                data['scheduled_time'],
                min_date=datetime.now()
            )
        
        return data

# Helper functions for request validation
def validate_request(validator_func: callable):
    """Decorator for request validation"""
    def decorator(func):
        async def wrapper(*args, **kwargs):
            try:
                # Find request data in args or kwargs
                request_data = None
                for arg in args:
                    if isinstance(arg, dict):
                        request_data = arg
                        break
                if not request_data:
                    request_data = kwargs.get('data')
                
                if request_data:
                    # Validate data
                    validated_data = validator_func(request_data)
                    
                    # Update args or kwargs
                    if 'data' in kwargs:
                        kwargs['data'] = validated_data
                    else:
                        args = list(args)
                        for i, arg in enumerate(args):
                            if isinstance(arg, dict):
                                args[i] = validated_data
                                break
                        args = tuple(args)
                
                return await func(*args, **kwargs)
                
            except ValidationError as e:
                logger.error(f"Validation error: {e}")
                raise
                
        return wrapper
    return decorator

# Create validator instance
validator = Validator()
```


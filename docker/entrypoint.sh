#!/bin/bash
set -e

echo "Waiting for PostgreSQL..."
until PGPASSWORD=$DB_PASSWORD psql -h "$DB_HOST" -U "$DB_USER" -d "$DB_NAME" -c '\q'; do
  echo "PostgreSQL is unavailable - sleeping"
  sleep 1
done

echo "PostgreSQL is up"

echo "Waiting for Redis..."
until redis-cli -h "$REDIS_HOST" -p "$REDIS_PORT" -a "$REDIS_PASSWORD" ping | grep -q "PONG"; do
  echo "Redis is unavailable - sleeping"
  sleep 1
done

echo "Redis is up"

echo "Running database migrations..."
alembic upgrade head

echo "Starting application..."
if [ "$ENVIRONMENT" = "production" ]; then
  echo "Starting in production mode..."
  exec gunicorn telegram_bot.main:app \
    --workers 4 \
    --worker-class uvicorn.workers.UvicornWorker \
    --bind 0.0.0.0:8000 \
    --access-logfile - \
    --error-logfile - \
    --log-level info
else
  echo "Starting in development mode..."
  exec uvicorn telegram_bot.main:app --host 0.0.0.0 --port 8000 --reload
fi
#!/bin/bash
set -e

# Wait for database
echo "Waiting for postgres..."
while ! pg_isready -h postgres -U meeting_user -d meeting_db; do
  sleep 1
done
echo "PostgreSQL started"

# Run migrations
echo "Running alembic migrations..."
alembic upgrade head

# Start application
echo "Starting application..."
exec "$@"

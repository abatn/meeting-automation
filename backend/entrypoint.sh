#!/bin/bash
set -e

# Configuration via environment variables (ISO 27001: controlled schema changes)
DB_HOST="${DB_HOST:-postgres}"
DB_USER="${DB_USER:-meeting_user}"
DB_NAME="${DB_NAME:-meeting_db}"
DB_PASSWORD="${DB_PASSWORD:-}"
RUN_MIGRATIONS="${RUN_MIGRATIONS:-true}"
MIGRATION_TIMEOUT="${MIGRATION_TIMEOUT:-60}"
E2E_TEST="${E2E_TEST:-false}"

if [ "$RUN_MIGRATIONS" = "true" ]; then
    echo "=== Waiting for PostgreSQL at ${DB_HOST} ==="
    for i in $(seq 1 $MIGRATION_TIMEOUT); do
        if pg_isready -h "$DB_HOST" -U "$DB_USER" -d "$DB_NAME" 2>/dev/null; then
            echo "PostgreSQL is ready"
            break
        fi
        if [ $i -eq $MIGRATION_TIMEOUT ]; then
            echo "ERROR: PostgreSQL not ready after ${MIGRATION_TIMEOUT}s"
            exit 1
        fi
        sleep 1
    done

    # Only run Alembic migrations for the main backend container
    if [ "$APP_ROLE" = "backend" ]; then
        # E2E test environment: drop existing tables and types to avoid DuplicateTableError
        # from main.py's create_all() running after Alembic. Safe for E2E (no production data).
        if [ "$E2E_TEST" = "true" ]; then
            echo "=== E2E Mode: Cleaning existing tables and types for fresh Alembic run ==="
            export PGPASSWORD="${DB_PASSWORD}"
            psql -h "$DB_HOST" -U "$DB_USER" -d "$DB_NAME" -c "
                DO \$\$ DECLARE
                    r RECORD;
                BEGIN
                    FOR r IN (SELECT tablename FROM pg_tables WHERE schemaname = 'public') LOOP
                        EXECUTE 'DROP TABLE IF EXISTS ' || quote_ident(r.tablename) || ' CASCADE';
                    END LOOP;
                    FOR r IN (SELECT typname FROM pg_type WHERE typtype = 'e' AND typnamespace = (SELECT oid FROM pg_namespace WHERE nspname = 'public')) LOOP
                        EXECUTE 'DROP TYPE IF EXISTS ' || quote_ident(r.typname) || ' CASCADE';
                    END LOOP;
                END \$\$;
            " 2>/dev/null || true
            unset PGPASSWORD
        fi

        echo "=== Running Alembic Migrations (ISO 27001 compliant) ==="
        export PYTHONPATH=/app
        cd /app
        alembic upgrade heads
        echo "=== Migrations complete ==="
    else
        echo "=== Skipping Alembic migrations (APP_ROLE=$APP_ROLE) ==="
    fi
else
    echo "=== Skipping migrations (RUN_MIGRATIONS=false) ==="
fi

echo "=== Starting Application ==="
exec "$@"

#!/bin/bash

# Default Colima/Local values
DB_HOST=${POSTGRES_SERVER:-localhost}
DB_USER=${POSTGRES_USER:-postgres}
DB_PASS=${POSTGRES_PASSWORD:-postgres}
DB_NAME=${POSTGRES_DB:-postgres}
DB_PORT=${POSTGRES_PORT:-54322}

# Try to load from .env if present
if [ -f "backend/.env" ]; then
    export $(grep -v '^#' backend/.env | xargs)
    # Re-assign if .env has different names or to override defaults
    DB_HOST=${POSTGRES_SERVER:-$DB_HOST}
    DB_USER=${POSTGRES_USER:-$DB_USER}
    DB_PASS=${POSTGRES_PASSWORD:-$DB_PASS}
    DB_NAME=${POSTGRES_DB:-$DB_NAME}
    DB_PORT=${POSTGRES_PORT:-$DB_PORT}
fi

export PGPASSWORD=$DB_PASS

echo "🔍 Verifying Database Schema on $DB_HOST:$DB_PORT/$DB_NAME..."

REQUIRED_TABLES=("organizations" "projects" "documents" "runs" "run_audits" "activities")
MISSING=0

printf "%-20s | %-10s\n" "TABLE" "STATUS"
echo "-----------------------------------"

for table in "${REQUIRED_TABLES[@]}"; do
    EXISTS=$(psql -h $DB_HOST -p $DB_PORT -U $DB_USER -d $DB_NAME -tAc "SELECT EXISTS (SELECT FROM information_schema.tables WHERE table_schema = 'public' AND table_name = '$table');")
    
    if [ "$EXISTS" = "t" ]; then
        printf "%-20s | ✅ OK\n" "$table"
    else
        printf "%-20s | ❌ MISSING\n" "$table"
        MISSING=1
    fi
done

echo "-----------------------------------"

if [ $MISSING -eq 1 ]; then
    echo "⚠️  Missing tables detected."
    exit 1
else
    echo "✅ All core tables are present."
    exit 0
fi

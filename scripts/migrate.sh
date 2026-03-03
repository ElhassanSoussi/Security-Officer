#!/usr/bin/env bash
# Database migration runner
#
# Usage:
#   ./scripts/migrate.sh                        # Apply all migrations in order
#   ./scripts/migrate.sh <migration_name>       # Apply only specific migration
#
# Prerequisites:
#   - SUPABASE_URL and SUPABASE_SERVICE_ROLE_KEY must be set in backend/.env
#   - psql or Supabase CLI must be available (for direct SQL execution)
#
# For Supabase-hosted projects, paste migrations into the SQL Editor at:
#   https://app.supabase.com → your project → SQL Editor

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
MIGRATION_DIR="$SCRIPT_DIR/../backend/scripts"

# Migration files in order
MIGRATIONS=(
    "supabase_schema.sql"
    "enterprise_upgrade_migration.sql"
    "017_source_excerpt.sql"
    "002_project_workspace.sql"
    "003_retrieval_engine.sql"
    "004_multi_run_intelligence.sql"
    "005_expiration_pack_audit.sql"
    "006_rbac.sql"
    "007_productization.sql"
    "audit_events_migration.sql"
    "entitlements_migration.sql"
    "billing_events_schema.sql"
    "stripe_billing_migration.sql"
    "security_rls_migration.sql"
    "008_production_hardening.sql"
    "009_compliance_intelligence.sql"
    "010_institutional_memory_governance.sql"
    "011_evidence_vault.sql"
    "012_billing_usage.sql"
    "013_stripe_billing.sql"
    "014_soc2_readiness.sql"
    "015_sales_engine.sql"
    "016_production_hardening_rls.sql"
)

echo "╔══════════════════════════════════════════════╗"
echo "║  NYC Compliance Architect — Migration Runner ║"
echo "╚══════════════════════════════════════════════╝"
echo ""

FILTER="${1:-}"

for migration in "${MIGRATIONS[@]}"; do
    if [[ -n "$FILTER" && "$migration" != *"$FILTER"* ]]; then
        continue
    fi

    FULL_PATH="$MIGRATION_DIR/$migration"
    if [[ -f "$FULL_PATH" ]]; then
        echo "📄 $migration"
    else
        echo "⚠️  $migration (file not found — skipping)"
    fi
done

echo ""
echo "To apply migrations, paste the SQL files above into the Supabase SQL Editor."
echo "Migration directory: $MIGRATION_DIR"
echo ""
echo "Migration checklist:"
echo "  ✅ Back up the database before applying migrations"
echo "  ✅ Apply migrations in the order listed above"
echo "  ✅ Test with a staging environment first"
echo "  ✅ Verify each migration completes without errors"
echo "  ✅ Run health check after: curl http://localhost:8000/health"

# DEVLOG

## 2026-02-17

- Audit Log confidence formatting: prevents `NaN%` and displays `—` when confidence is missing/invalid.
- RAG failure mode: replaces placeholder “NOT FOUND IN LOCKER” answers with `needs_info` status and a “Missing source context” UX.
- Frontend API client hardening: one-time redirect on 401 to avoid request storms; retries safe GETs on transient 5xx with backoff.
- Backend observability: request tracing middleware adds `X-Request-Id` and logs `request_id/user_id/org_id/status/duration_ms`.
- Added `/api/v1/ready` for readiness checks (backend + Supabase reachability) and improved `/health` diagnostics page.
- Plans & Pricing display updated to Starter $149/mo, Growth $499/mo, Elite $1499/mo (+ “Annual plans available” note).
- Dashboard onboarding checklist added for first-time users.

Database / Supabase scripts:
- `backend/scripts/security_rls_migration.sql` adds membership-scoped RLS across tenant tables (and optional tables if present).
- `backend/scripts/audit_events_migration.sql` adds an `audit_events` table + RLS (best-effort logging hooks in backend).

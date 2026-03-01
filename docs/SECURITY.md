# Security Model & Multi-Tenancy

This document outlines the security architecture for the NYC Compliance Architect.

## Core Principles

1. **Zero Trust Defaults**: No "default" organizations. No fallback IDs. Every request must explicitly state its target Organization ID.
2. **Row Level Security (RLS)**: All data access is mediated by Supabase RLS policies. The application code (FastAPI) provides defense-in-depth, but the database is the source of truth for access control.
3. **Strict UUID Validation**: All IDs are validated as UUIDv4 at the API boundary. Malformed IDs are rejected with 400 Bad Request immediately.

## Multi-Tenancy Implementation

### 1. Data Isolation

All tenant data tables (`documents`, `runs`, `projects`, `exports`, etc.) have a mandatory `org_id` column.

**RLS Policies** enforce that a user can only `SELECT`, `INSERT`, `UPDATE` rows where:

```sql
org_id IN (
    SELECT org_id FROM memberships 
    WHERE user_id = auth.uid()
)
```

This prevents cross-tenant data leaks even if an API endpoint fails to filter correctly.

### 2. Authentication & Context

- **Authentication**: Supabase JWT (Bearer Token).
- **Context Resolution**:
  - Clients must send `org_id` (query param or body).
  - Backend validates `org_id` is a UUID.
  - Backend verifies user is a member of `org_id`.
  - If valid, the request proceeds. If not, `403 Forbidden`.

### 3. Write Operations

For most operations (including ingestion + chunk writes), the backend uses the **caller JWT** so Supabase RLS remains the enforcement layer.

Use a **Service Role** client only for trusted, admin-only operations (e.g., Stripe webhooks, emergency bootstrap), and only after explicit application-level authorization checks.

- **Frontend**: Authenticated User (Subject to RLS)
- **Backend Read**: Authenticated User (Subject to RLS)
- **Backend Write**: Authenticated User (Subject to RLS) by default; Service Role only for tightly-scoped admin actions.

## Onboarding Flow

1. User signs up (Supabase Auth).
2. User lands on `/orgs`.
3. **Auto-Onboarding**: If the user has 0 organizations, the frontend calls `POST /orgs/onboard`.
4. Backend creates a new "My Organization" and makes the user the Owner.
5. Frontend stores the new `org_id` in local storage and redirects to `/projects`.

## Key Files

- `backend/scripts/security_rls_migration.sql`: The source of truth for RLS policies.
- `backend/app/core/org_context.py`: Logic for resolving and verifying organization access.
- `backend/app/core/org_context.py#parse_uuid`: Input validation (UUID strictness).

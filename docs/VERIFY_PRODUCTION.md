# VERIFY_PRODUCTION

Production release verification checklist for Render (backend) + Vercel (frontend).

This document is intentionally direct. It is meant to catch configuration mistakes before customers do.

## Preconditions

- Production domains are finalized.
- Supabase and Stripe production projects are created.
- You have admin access to Render, Vercel, Supabase, Stripe.

## 1) Backend verification (Render)

> **Startup validation is automatic.**
> When the backend starts, `validate_startup_env()` is called at import time.
> In production it raises immediately if critical vars are missing — the process
> will not start and Render will report a failed deploy. In other environments
> it logs warnings and continues. You do not need to call it manually.

### 1.1 Confirm required env vars exist (Render)

Required (always):
- `ENVIRONMENT=production`
- `APP_VERSION` (release tag or commit SHA)
- `RELEASE_TIMESTAMP` (optional; ISO-8601 UTC)
- `FRONTEND_URL` (https://<your-domain>)
- `ALLOWED_ORIGINS` (comma-separated explicit origins; no `*`)
- `SUPABASE_URL`
- `SUPABASE_KEY`
- `SUPABASE_SERVICE_ROLE_KEY` (or `SUPABASE_SECRET_KEY`)
- `SUPABASE_JWT_SECRET`

Required when billing is enabled (`BILLING_ENABLED=true`):
- `STRIPE_SECRET_KEY`
- `STRIPE_WEBHOOK_SECRET`

Required when assistant is enabled (`ASSISTANT_ENABLED=true`):
- `OPENAI_API_KEY`

### 1.2 Run backend smoke checks

From a trusted machine:

- Set `BACKEND_URL` to the backend origin (no `/api/v1`):
  - Example: `https://<service>.onrender.com`

- Run:
  - `python scripts/smoke_production_backend.py`

Expected:
- `PASS: health`
- `PASS/WARNING: readiness`
- `PASS: security_headers`
- `PASS: auth_guard`

### 1.3 Confirm readiness endpoint output

- `GET https://<backend>/api/v1/system/readiness`

Confirm:
- `status` is `ok` or `warning`
- `environment` is `production`
- `version` matches `APP_VERSION`
- `checks[]` contains no secrets

## 2) Frontend verification (Vercel)

### 2.1 Confirm required env vars exist (Vercel)

Required:
- `NEXT_PUBLIC_API_URL` (backend base URL; script auto-appends `/api/v1` when missing)
- `NEXT_PUBLIC_SUPABASE_URL`
- `NEXT_PUBLIC_SUPABASE_ANON_KEY`
- `NEXT_PUBLIC_APP_VERSION` (match backend `APP_VERSION`)

Required when billing is enabled:
- `NEXT_PUBLIC_BILLING_ENABLED=true`
- `NEXT_PUBLIC_STRIPE_PUBLISHABLE_KEY`

### 2.2 Run frontend smoke checks

- Set `FRONTEND_URL` to the frontend origin:
  - Example: `https://<app>.vercel.app`

- Run:
  - `python scripts/smoke_production_frontend.py`

Expected:
- Landing page loads
- Login page loads
- Settings billing route resolves (usually redirects to login when unauthenticated)

## 3) Supabase verification

### 3.1 Auth redirect URLs

In Supabase Dashboard → Authentication → URL Configuration:
- Site URL: `https://<your-frontend-domain>`
- Redirect URLs:
  - `https://<your-frontend-domain>/**`
  - `https://<your-frontend-domain>/login`
  - `https://<your-frontend-domain>/onboarding`

### 3.2 Service role key handling

- Service role key must only exist in Render backend env vars.
- NEVER set service role keys in Vercel.

## 4) Stripe verification

### 4.1 Webhook

In Stripe Dashboard → Developers → Webhooks:
- Endpoint URL: `https://<backend>/api/v1/billing/webhook19`
- Signing secret matches `STRIPE_WEBHOOK_SECRET` in Render.

### 4.2 Portal/Checkout redirects

- Validate that checkout success/cancel redirects go back to `FRONTEND_URL`.

## 5) DNS / domain checks

- `https://<frontend-domain>` resolves and uses TLS.
- `https://<backend-domain>` resolves and uses TLS.
- CORS allows the frontend domain explicitly.

## 6) Rollback checklist

- Vercel: redeploy previous production deployment.
- Render: roll back to the previous successful deploy.
- Confirm `/health` and `/api/v1/system/readiness` return expected status.

# Production Deployment Guide

> **Domain**: `nyccompliancearchitect.com`
> **Frontend**: Vercel (Next.js 14)
> **Backend**: Render (FastAPI / Docker)
> **Database**: Supabase (hosted PostgreSQL + Auth)

---

## Architecture

```text
Browser → nyccompliancearchitect.com (Vercel)
              │
              ├─ Static pages / SSR (Next.js)
              ├─ /api/v1/* proxy → Render backend (BACKEND_INTERNAL_URL)
              │
              └─ Supabase Auth (direct from browser)

Render (nyc-compliance-api)
  ├─ FastAPI on $PORT
  ├─ CORS: nyccompliancearchitect.com only
  ├─ /health/ping → liveness
  └─ Supabase Admin SDK (service_role)
```

---

## 1. Render (Backend)

### One-Time Setup

1. Create a **Web Service** in Render Dashboard.
2. Connect the GitHub repo, set **Root Directory** to `backend`.
3. Set **Dockerfile Path** to `./Dockerfile`.
4. Set **Health Check Path** to `/health/ping`.

### Environment Variables

| Variable | Value |
|---|---|
| `ENVIRONMENT` | `production` |
| `SUPABASE_URL` | `https://<project>.supabase.co` |
| `SUPABASE_KEY` | Supabase anon key |
| `SUPABASE_SERVICE_ROLE_KEY` | Supabase service_role key |
| `SUPABASE_JWT_SECRET` | Supabase JWT secret |
| `OPENAI_API_KEY` | `sk-...` |
| `ALLOWED_ORIGINS` | `https://nyccompliancearchitect.com,https://www.nyccompliancearchitect.com` |
| `FRONTEND_URL` | `https://nyccompliancearchitect.com` |
| `BILLING_ENABLED` | `false` (set `true` when Stripe is ready) |
| `STRIPE_SECRET_KEY` | (when billing enabled) |
| `STRIPE_WEBHOOK_SECRET` | (when billing enabled) |
| `SENTRY_DSN` | (optional) |

> Render auto-injects `$PORT`. The Dockerfile CMD uses `${PORT:-8000}`.

### Custom Domain (Optional)

To use `api.nyccompliancearchitect.com`:

1. In Render → Service → Settings → Custom Domains → Add `api.nyccompliancearchitect.com`.
2. Add a CNAME record: `api` → `<service>.onrender.com`.
3. Render provisions TLS automatically.

---

## 2. Vercel (Frontend)

### One-Time Setup

1. Import the repo in Vercel Dashboard.
2. Set **Root Directory** to `frontend`.
3. Framework preset: **Next.js**.

### Environment Variables

| Variable | Value |
|---|---|
| `NEXT_PUBLIC_SUPABASE_URL` | `https://<project>.supabase.co` |
| `NEXT_PUBLIC_SUPABASE_ANON_KEY` | Supabase anon key |
| `NEXT_PUBLIC_API_URL` | `/api/v1` |
| `BACKEND_INTERNAL_URL` | `https://nyc-compliance-api.onrender.com` (or `https://api.nyccompliancearchitect.com`) |
| `NEXT_PUBLIC_APP_VERSION` | `1.0.0` |
| `NEXT_PUBLIC_SITE_URL` | `https://nyccompliancearchitect.com` |

> **`NEXT_PUBLIC_API_URL`** stays as `/api/v1` — the Next.js API route proxy
> (`app/api/v1/[...path]/route.ts`) forwards requests server-side to
> `BACKEND_INTERNAL_URL`. This avoids CORS issues from the browser.

### Custom Domain

1. In Vercel → Project → Settings → Domains → Add `nyccompliancearchitect.com`.
2. Add DNS records per Vercel's instructions (A record + CNAME for www).
3. Enable "Redirect www to apex" or vice versa.

---

## 3. Supabase

### Auth Settings

1. Go to Authentication → URL Configuration.
2. Set **Site URL** to `https://nyccompliancearchitect.com`.
3. Add to **Redirect URLs**:
   - `https://nyccompliancearchitect.com/**`
   - `https://www.nyccompliancearchitect.com/**`
4. Remove any `localhost` redirect URLs (or keep for development).

### Database Migrations

Apply all migrations in order:

```bash
psql "$DATABASE_URL" -f backend/scripts/001_schema_alignment.sql
psql "$DATABASE_URL" -f backend/scripts/002_project_workspace.sql
# ... through 017_source_excerpt.sql
# Or use: bash scripts/migrate.sh
```

---

## 4. DNS Records (nyccompliancearchitect.com)

| Type | Name | Value | Purpose |
|---|---|---|---|
| A | `@` | `76.76.21.21` | Vercel (check your dashboard for exact IP) |
| CNAME | `www` | `cname.vercel-dns.com` | Vercel www redirect |
| CNAME | `api` | `<service>.onrender.com` | Render backend (optional) |

---

## 5. Pre-Launch Checklist

- [ ] `ENVIRONMENT=production` on Render
- [ ] `ALLOWED_ORIGINS` includes both `https://nyccompliancearchitect.com` and `https://www.nyccompliancearchitect.com`
- [ ] `FRONTEND_URL=https://nyccompliancearchitect.com` on Render
- [ ] `BACKEND_INTERNAL_URL` set on Vercel (points to Render service)
- [ ] Supabase Site URL updated to `https://nyccompliancearchitect.com`
- [ ] Supabase Redirect URLs updated
- [ ] All database migrations applied
- [ ] `/health/ping` returns 200 on Render
- [ ] Frontend loads and auth flow works
- [ ] No `localhost` references in production env vars
- [ ] `BILLING_ENABLED=false` until Stripe webhook is configured
- [ ] Stripe webhook endpoint updated to Render URL (when ready)
- [ ] HTTPS enforced on both domains (automatic on Vercel + Render)

---

## 6. Monitoring

- **Backend health**: `https://api.nyccompliancearchitect.com/health/ping`
- **Deep health**: `https://api.nyccompliancearchitect.com/api/v1/health/full`
- **Sentry**: Set `SENTRY_DSN` on Render for error tracking
- **Render Dashboard**: Auto-restart, deploy logs, metrics
- **Vercel Dashboard**: Function logs, analytics, Web Vitals

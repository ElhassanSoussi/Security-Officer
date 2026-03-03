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
| `STRIPE_SECRET_KEY` | Stripe secret key (server-only; **never** expose to frontend) |
| `STRIPE_WEBHOOK_SECRET` | Webhook signing secret (from Stripe Dashboard → Webhooks) |
| `STRIPE_PRICE_FREE` | Stripe Price ID for Free plan |
| `STRIPE_PRICE_PRO` | Stripe Price ID for Pro plan |
| `STRIPE_PRICE_ENTERPRISE` | Stripe Price ID for Enterprise plan |
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

| Variable | Value | Notes |
|---|---|---|
| `NEXT_PUBLIC_SUPABASE_URL` | `https://<project>.supabase.co` | ⚠️ NOT the Postgres connection string! Find in Supabase → Settings → API → Project URL |
| `NEXT_PUBLIC_SUPABASE_ANON_KEY` | Supabase anon key | Supabase → Settings → API → `anon` `public` |
| `NEXT_PUBLIC_API_URL` | `/api/v1` | Keep as `/api/v1` — the proxy handles the rest |
| `BACKEND_INTERNAL_URL` | `https://security-officer.onrender.com` | ⚠️ **REQUIRED** — without this, API calls return 404. NO `/api/v1` suffix! |
| `NEXT_PUBLIC_APP_VERSION` | `1.0.0` | |
| `NEXT_PUBLIC_SITE_URL` | `https://nyccompliancearchitect.com` | |
| `NEXT_PUBLIC_STRIPE_PUBLISHABLE_KEY` | `pk_live_...` or `pk_test_...` | Stripe publishable key (safe for client-side) |

> ⚠️ **NEVER** set `STRIPE_SECRET_KEY` or `STRIPE_WEBHOOK_SECRET` on Vercel.
> Those belong on the backend (Render) only. The frontend must only have
> `NEXT_PUBLIC_STRIPE_PUBLISHABLE_KEY`.

> **`NEXT_PUBLIC_API_URL`** stays as `/api/v1` — the Next.js API route proxy
> (`app/api/v1/[...path]/route.ts`) forwards requests server-side to
> `BACKEND_INTERNAL_URL`. This avoids CORS issues from the browser.

### Custom Domain

1. In Vercel → Project → Settings → Domains → Add `nyccompliancearchitect.com`.
2. Add DNS records per Vercel's instructions (A record + CNAME for www).
3. Enable "Redirect www to apex" or vice versa.

### ⚠️ Deployment Protection (CRITICAL)

Vercel's **Deployment Protection** can block server-side API proxy calls on
Preview deployments, returning an HTML auth page instead of proxying to the
backend. Symptoms: "Decoding failed", "Failed to load dashboard data",
`401` HTML responses from `/api/v1/*` endpoints.

**Fix — choose one:**

1. **Disable for Preview** (simplest):
   Vercel → Project → Settings → Deployment Protection →
   set "Standard Protection" **or** toggle off "Vercel Authentication" for
   Preview deployments.

2. **Use Production deployments only**:
   Assign the custom domain (`nyccompliancearchitect.com`) so pushes to
   `main` go to the Production environment, which does not have this
   protection by default.

3. **Protection Bypass for Automation** (advanced):
   Vercel → Project → Settings → Deployment Protection →
   "Protection Bypass for Automation" → generate a secret. Then set
   env var `VERCEL_AUTOMATION_BYPASS_SECRET` and send the header
   `x-vercel-protection-bypass: <secret>` on server-side requests.

> **Recommendation:** Once the custom domain is live, deploy to **Production**
> and the issue disappears. For Preview testing, option 1 is fastest.

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

> ⚠️ **Stripe billing migration**: `backend/scripts/013_stripe_billing.sql`
> creates the `subscriptions` and `billing_events` tables required for billing.
> Ensure it has been applied before enabling `BILLING_ENABLED=true`.

---

## 4. Stripe Billing Setup

### Prerequisites

1. A [Stripe account](https://dashboard.stripe.com/register) (Test mode for staging, Live mode for production).
2. Create **Products** and **Prices** in Stripe Dashboard → Products for each plan:
   - Free, Pro, Enterprise (recurring/monthly).
3. Note the **Price IDs** (`price_...`) for each plan.

### Backend Environment Variables (Render)

| Variable | Description |
|---|---|
| `BILLING_ENABLED` | `true` to enable billing endpoints |
| `STRIPE_SECRET_KEY` | `sk_live_...` or `sk_test_...` — **server-side only** |
| `STRIPE_WEBHOOK_SECRET` | `whsec_...` — from Stripe webhook endpoint config |
| `STRIPE_PRICE_FREE` | `price_...` — Stripe Price ID for Free plan |
| `STRIPE_PRICE_PRO` | `price_...` — Stripe Price ID for Pro plan |
| `STRIPE_PRICE_ENTERPRISE` | `price_...` — Stripe Price ID for Enterprise plan |
| `STRIPE_TRIAL_DAYS` | `14` (default) — trial period for new PRO subscriptions |

### Frontend Environment Variables (Vercel)

| Variable | Description |
|---|---|
| `NEXT_PUBLIC_STRIPE_PUBLISHABLE_KEY` | `pk_live_...` or `pk_test_...` — safe for browser |

> ⚠️ **Security rule**: `STRIPE_SECRET_KEY` and `STRIPE_WEBHOOK_SECRET` must
> **never** appear in frontend code, Vercel env vars, or any `NEXT_PUBLIC_*`
> variable. The CI pipeline includes a secret-leak guard that fails the build
> if this rule is violated.

### Webhook Configuration

1. Go to **Stripe Dashboard → Developers → Webhooks → Add endpoint**.
2. Set the endpoint URL to your backend webhook receiver:
   ```
   https://your-backend.onrender.com/api/v1/billing/webhook19
   ```
3. Subscribe to these events:
   - `checkout.session.completed`
   - `customer.subscription.created`
   - `customer.subscription.updated`
   - `customer.subscription.deleted`
   - `invoice.payment_failed`
4. Copy the **Signing secret** (`whsec_...`) and set it as `STRIPE_WEBHOOK_SECRET` on Render.

### Testing Webhooks with Stripe CLI

```bash
# Install Stripe CLI: https://stripe.com/docs/stripe-cli
brew install stripe/stripe-cli/stripe  # macOS

# Login to Stripe
stripe login

# Forward events to your local or deployed backend
stripe listen --forward-to "http://localhost:8000/api/v1/billing/webhook19"
# Or for deployed:
stripe listen --forward-to "https://your-backend.onrender.com/api/v1/billing/webhook19"

# In a separate terminal, trigger test events:
stripe trigger checkout.session.completed
stripe trigger customer.subscription.updated
stripe trigger invoice.payment_failed
```

### Verifying Webhook Processing

After triggering test events, verify:

1. **billing_events table**: Events are logged with `stripe_event_id`, `type`, `raw_payload`.
2. **subscriptions table**: `stripe_customer_id`, `stripe_subscription_id`, `stripe_status`,
   `current_period_end`, and plan limits (`max_runs_per_month`, `max_documents`, `max_memory_entries`)
   are populated correctly.
3. **Checkout flow**: `POST /api/v1/billing/checkout` returns `{ url: "https://checkout.stripe.com/..." }`.
   User is redirected to Stripe, completes payment, and subscription is activated via webhook.
4. **Enforcement**: Protected endpoints (`/ingest`, `/analyze-excel`, `/generate-evidence`) return
   `402 SUBSCRIPTION_INACTIVE` for orgs with `stripe_status` = `canceled` or `past_due`.

### Billing Endpoint Reference

| Endpoint | Method | Purpose |
|---|---|---|
| `/api/v1/billing/checkout` | POST | Create Stripe Checkout Session |
| `/api/v1/billing/webhook19` | POST | Stripe webhook receiver (signature-verified) |
| `/api/v1/billing/status` | GET | Live subscription status for an org |
| `/api/v1/billing/trial` | POST | Start a 14-day PRO trial (admin-granted) |
| `/api/v1/billing/portal` | POST | Create Stripe Billing Portal session |
| `/api/v1/billing/plans` | GET | List available plan tiers |
| `/api/v1/billing/subscription` | GET | Get subscription record for an org |
| `/api/v1/billing/summary` | GET | Plan tier + billing period + usage |

### Behavior When Billing Is Disabled

When `BILLING_ENABLED=false` or Stripe keys are not configured:
- All billing endpoints return structured **503** responses:
  ```json
  { "error": "billing_disabled", "message": "Billing is disabled in this environment" }
  ```
- Core app flows (ingest, analyze, export) continue to work without billing checks.
- No raw tracebacks or 500 errors are returned.

---

## 5. DNS Records (nyccompliancearchitect.com)

| Type | Name | Value | Purpose |
|---|---|---|---|
| A | `@` | `76.76.21.21` | Vercel (check your dashboard for exact IP) |
| CNAME | `www` | `cname.vercel-dns.com` | Vercel www redirect |
| CNAME | `api` | `<service>.onrender.com` | Render backend (optional) |

---

## 6. Pre-Launch Checklist

- [ ] `ENVIRONMENT=production` on Render
- [ ] `ALLOWED_ORIGINS` includes both `https://nyccompliancearchitect.com` and `https://www.nyccompliancearchitect.com`
- [ ] `FRONTEND_URL=https://nyccompliancearchitect.com` on Render
- [ ] `BACKEND_INTERNAL_URL` set on Vercel (points to Render service)
- [ ] Supabase Site URL updated to `https://nyccompliancearchitect.com`
- [ ] Supabase Redirect URLs updated
- [ ] All database migrations applied (including `013_stripe_billing.sql`)
- [ ] `/health/ping` returns 200 on Render
- [ ] Frontend loads and auth flow works
- [ ] No `localhost` references in production env vars
- [ ] **Stripe secrets** — `STRIPE_SECRET_KEY` and `STRIPE_WEBHOOK_SECRET` are set on Render backend only
- [ ] **Stripe publishable key** — `NEXT_PUBLIC_STRIPE_PUBLISHABLE_KEY` is set on Vercel frontend
- [ ] **No secret leaks** — `STRIPE_SECRET_KEY` / `STRIPE_WEBHOOK_SECRET` are NOT in any Vercel / frontend env
- [ ] `BILLING_ENABLED=true` on Render (only after Stripe webhook is configured)
- [ ] `STRIPE_PRICE_FREE`, `STRIPE_PRICE_PRO`, `STRIPE_PRICE_ENTERPRISE` set on Render
- [ ] Stripe webhook endpoint registered in Stripe Dashboard pointing to backend URL
- [ ] Webhook events tested with Stripe CLI and verified in `billing_events` + `subscriptions` tables
- [ ] HTTPS enforced on both domains (automatic on Vercel + Render)

---

## 7. Monitoring

- **Backend health**: `https://api.nyccompliancearchitect.com/health/ping`
- **Deep health**: `https://api.nyccompliancearchitect.com/api/v1/health/full`
- **Sentry**: Set `SENTRY_DSN` on Render for error tracking
- **Render Dashboard**: Auto-restart, deploy logs, metrics
- **Vercel Dashboard**: Function logs, analytics, Web Vitals

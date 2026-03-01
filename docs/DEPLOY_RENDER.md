# Deploying the Backend to Render

Step-by-step guide for deploying the NYC Compliance Architect FastAPI backend to [Render](https://render.com).

---

## Prerequisites

| Item | Details |
|------|---------|
| **GitHub repo** | Push the full monorepo (or at least `backend/`) to a GitHub repository |
| **Render account** | Free tier works for testing; Starter or Standard instance recommended for production |
| **Supabase project** | Running project with anon key, service-role key, and JWT secret |
| **OpenAI API key** | For RAG/embedding functionality |
| **Stripe keys** | Only required if `BILLING_ENABLED=true` |

---

## 1. Create a New Web Service on Render

1. Go to **Render Dashboard → New → Web Service**
2. Connect your GitHub repository
3. Configure the service:

| Setting | Value |
|---------|-------|
| **Name** | `nyc-compliance-api` (or your preference) |
| **Region** | Choose closest to your users (e.g., `Oregon (US West)`) |
| **Branch** | `main` |
| **Root Directory** | `backend` |
| **Runtime** | `Docker` |
| **Instance Type** | `Starter` ($7/mo) or `Standard` ($25/mo) for production |

> **Why Docker?** The repo includes a production-grade `Dockerfile` with multi-stage build, non-root user, and security hardening.

---

## 2. Build & Start Commands

Because we use Docker, Render reads the `Dockerfile` directly. No separate build/start commands are needed in the Render UI — the Dockerfile handles everything.

| Render Field | Value |
|--------------|-------|
| **Build Command** | *(leave blank — Docker handles it)* |
| **Start Command** | *(leave blank — Docker CMD handles it)* |
| **Dockerfile Path** | `./Dockerfile` (auto-detected from Root Directory) |

The Dockerfile CMD is:

```text
uvicorn app.main:app --host 0.0.0.0 --port ${PORT:-8000} --workers 2 --access-log
```

Render injects the `$PORT` environment variable automatically. The CMD respects it.

---

## 3. Health Check

| Render Field | Value |
|--------------|-------|
| **Health Check Path** | `/health/ping` |

The `/health/ping` endpoint:
- **Always returns HTTP 200** with `{ "status": "ok" }`
- No database or external service dependencies
- Ideal for load-balancer liveness probes

Other available health endpoints:

| Endpoint | Purpose | May return 503? |
|----------|---------|-----------------|
| `/health/ping` | Liveness probe (Render health check) | Never |
| `/health` | Basic status + DB check | No (returns 200 with `"degraded"` if DB down) |
| `/health/ready` | Readiness probe (DB + Stripe + OpenAI) | Yes (503 if not ready) |
| `/health/full` | Deep monitoring (DB + Stripe + vector + latency) | Yes (503 if degraded) |

---

## 4. Environment Variables

Set these in **Render Dashboard → Environment → Environment Variables**:

### Required

| Variable | Example | Description |
|----------|---------|-------------|
| `ENVIRONMENT` | `production` | Must be `production` for security hardening |
| `SUPABASE_URL` | `https://xxx.supabase.co` | Supabase project URL |
| `SUPABASE_KEY` | `eyJ...` | Supabase anon/public key |
| `SUPABASE_SERVICE_ROLE_KEY` | `eyJ...` | Supabase service-role key (admin access) |
| `SUPABASE_JWT_SECRET` | `your-jwt-secret` | Supabase JWT secret (Settings → API) |
| `OPENAI_API_KEY` | `sk-...` | OpenAI API key |
| `ALLOWED_ORIGINS` | `https://yourapp.vercel.app,https://yourdomain.com` | Comma-separated allowed CORS origins |

### Optional

| Variable | Default | Description |
|----------|---------|-------------|
| `SUPABASE_SECRET_KEY` | *(empty)* | Alias for `SUPABASE_SERVICE_ROLE_KEY` |
| `BILLING_ENABLED` | `false` | Enable Stripe billing integration |
| `STRIPE_SECRET_KEY` | *(empty)* | Required when `BILLING_ENABLED=true` |
| `STRIPE_WEBHOOK_SECRET` | *(empty)* | Required when `BILLING_ENABLED=true` |
| `STRIPE_PRICE_FREE` | *(empty)* | Stripe Price ID for Free plan |
| `STRIPE_PRICE_PRO` | *(empty)* | Stripe Price ID for Pro plan |
| `STRIPE_PRICE_ENTERPRISE` | *(empty)* | Stripe Price ID for Enterprise plan |
| `SENTRY_DSN` | *(empty)* | Sentry error monitoring DSN |
| `MAX_UPLOAD_SIZE_MB` | `50` | Max file upload size in MB |
| `RATE_LIMIT_ANALYSIS` | `5` | Analysis requests per 60s per user |
| `RATE_LIMIT_EXPORT` | `10` | Export requests per 60s per user |
| `RATE_LIMIT_CONTACT` | `5` | Public contact form per 300s per IP |
| `RATE_LIMIT_AUTH` | `20` | Auth requests per 300s per IP |

> ⚠️ **CRITICAL:** In production (`ENVIRONMENT=production`), `ALLOWED_ORIGINS` **must** be set to explicit origins. Wildcard (`*`) is rejected. Empty value will log a warning.

---

## 5. CORS Configuration

The backend reads `ALLOWED_ORIGINS` as a comma-separated string:

- **Production:** Only explicitly listed origins are allowed. Wildcards are stripped.
- **Development:** `localhost:3000` and `localhost:3001` are added automatically, plus any `ALLOWED_ORIGINS` overrides.

Example for a Vercel frontend + custom domain:

```text
ALLOWED_ORIGINS=https://nyc-compliance.vercel.app,https://app.yourdomain.com
```

---

## 6. Logging

In production (`ENVIRONMENT=production`), all logs are structured JSON:

```json
{
  "timestamp": "2024-01-15T10:30:00.000000+00:00",
  "level": "INFO",
  "logger": "api.requests",
  "message": "request completed",
  "environment": "production",
  "request_id": "a1b2c3d4-...",
  "method": "GET",
  "path": "/api/v1/runs",
  "status_code": 200,
  "duration_ms": 45
}
```

All error responses include a `request_id` for traceability:

```json
{
  "error": "not_found",
  "message": "Run not found",
  "request_id": "a1b2c3d4-..."
}
```

Render captures stdout/stderr automatically — these logs appear in **Render Dashboard → Logs**.

---

## 7. Post-Deploy Verification

After deployment, verify the service is healthy:

```bash
# 1. Liveness check (should return 200)
curl -s https://nyc-compliance-api.onrender.com/health/ping
# → {"status":"ok"}

# 2. Full health check
curl -s https://nyc-compliance-api.onrender.com/health
# → {"status":"ok","version":"1.0.0","environment":"production",...}

# 3. Readiness probe
curl -s https://nyc-compliance-api.onrender.com/health/ready
# → {"status":"ready","checks":{"database":true,...}}

# 4. CORS preflight test
curl -s -X OPTIONS \
  -H "Origin: https://yourapp.vercel.app" \
  -H "Access-Control-Request-Method: GET" \
  https://nyc-compliance-api.onrender.com/api/v1/runs \
  -I
# → Should include: access-control-allow-origin: https://yourapp.vercel.app
```

---

## 8. Render Blueprint (Optional)

For infrastructure-as-code, create a `render.yaml` at the repo root:

```yaml
services:
  - type: web
    name: nyc-compliance-api
    runtime: docker
    rootDir: backend
    dockerfilePath: ./Dockerfile
    region: oregon
    plan: starter
    healthCheckPath: /health/ping
    envVars:
      - key: ENVIRONMENT
        value: production
      - key: SUPABASE_URL
        sync: false
      - key: SUPABASE_KEY
        sync: false
      - key: SUPABASE_SERVICE_ROLE_KEY
        sync: false
      - key: SUPABASE_JWT_SECRET
        sync: false
      - key: OPENAI_API_KEY
        sync: false
      - key: ALLOWED_ORIGINS
        sync: false
      - key: BILLING_ENABLED
        value: "false"
```

> Variables with `sync: false` must be set manually in the Render dashboard (secrets).

---

## 9. Connecting the Frontend

Once deployed, update your **Vercel** (or other frontend host) environment:

```text
NEXT_PUBLIC_API_URL=https://nyc-compliance-api.onrender.com/api/v1
BACKEND_INTERNAL_URL=https://nyc-compliance-api.onrender.com
```

And add the frontend URL to the backend's `ALLOWED_ORIGINS`:

```text
ALLOWED_ORIGINS=https://your-frontend.vercel.app
```

---

## 10. Troubleshooting

| Symptom | Fix |
|---------|-----|
| Health check failing on deploy | Ensure `SUPABASE_URL`, `SUPABASE_KEY`, `SUPABASE_JWT_SECRET` are set. The `/health/ping` endpoint has no dependencies — use it for Render health checks. |
| CORS errors in browser | Check `ALLOWED_ORIGINS` includes the exact frontend origin (with `https://`, no trailing slash) |
| 500 errors with no detail | Check Render logs — structured JSON logs include `request_id` for tracing |
| Slow cold starts | Upgrade from Free to Starter plan (Free tier spins down after inactivity) |
| `PORT` not found | Render injects `$PORT` automatically. The Dockerfile CMD uses `${PORT:-8000}` as fallback. |
| OpenAI timeouts | `OPENAI_TIMEOUT_SECONDS` defaults to 120s. Increase if needed. |

---

## Quick Reference

| Render Setting | Value |
|----------------|-------|
| **Root Directory** | `backend` |
| **Runtime** | `Docker` |
| **Dockerfile Path** | `./Dockerfile` |
| **Health Check Path** | `/health/ping` |
| **Build Command** | *(blank — Docker)* |
| **Start Command** | *(blank — Docker CMD)* |
| **Instance Type** | Starter ($7/mo) or Standard ($25/mo) |

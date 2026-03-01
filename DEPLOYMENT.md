# Deployment Guide: NYC Compliance Architect

## 1. Backend Deployment (Render / Fly.io / AWS)

The backend is a **FastAPI** application requiring Python 3.11+.

For this pinned dependency set, use **Python 3.11-3.13** for local setup.
Python 3.14 can trigger source builds (notably `tiktoken`) and fail without Rust.

### Requirments

- **Outbound Internet Access:** Required to reach OpenAI API and Supabase.
- **Environment Variables:** detailed in `backend/.env.example`.

### Docker Deployment (Recommended)

A `Dockerfile` is provided in the `backend/` directory.

1. **Build:** `docker build -t nyc-compliance-backend ./backend`
2. **Run:** `docker run -p 8000:8000 --env-file backend/.env nyc-compliance-backend`

### One Command Local Run

From the project root, run:

`./scripts/run_all.sh`

This will build + start backend/frontend with Docker Compose and wait for:

- `http://127.0.0.1:8000/health`
- `http://127.0.0.1:3001`

### Local Backend Setup (Mac/Linux)

1. `cd backend`
2. `python3.11 -m venv .venv`
3. `source .venv/bin/activate`
4. `pip install --upgrade pip setuptools wheel`
5. `pip install -r requirements.txt`

### Render.com Setup

1. Connect your GitHub repo using the "Web Service" option.
2. **Root Directory:** `backend`
3. **Runtime:** Docker
4. **Environment Variables:**
    - `OPENAI_API_KEY`: (Securely paste from OpenAI dashboard)
    - `SUPABASE_URL`: (From Supabase settings)
    - `SUPABASE_KEY`: (Service Role Key)
    - `PORT`: `8000`

---

## 2. Frontend Deployment (Vercel)

The frontend is a **Next.js** application.

### Vercel Setup

1. Connect your GitHub repo.
2. **Root Directory:** `frontend`
3. **Framework Preset:** Next.js (Auto-detected).
4. **Environment Variables:**
    - `NEXT_PUBLIC_API_URL`: The URL of your deployed Backend (e.g., `https://nyc-compliance-backend.onrender.com/api/v1`)

---

## 3. Database (Supabase)

Ensure your Supabase project has the vector extension enabled and tables creates as per `schema.sql`.
(If you are using the existing project, no action needed).

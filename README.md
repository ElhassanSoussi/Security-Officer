# NYC Compliance Architect (Security-Officer)

Professional B2B SaaS for NYC construction firms to auto-fill high-stakes government safety/security questionnaires (SCA, MTA, PASSPort) using their own documents as the source of truth.

## Product Positioning

**NYC Compliance Architect** is an enterprise-grade compliance automation platform purpose-built for New York City construction and infrastructure firms. It solves a critical operational bottleneck: completing lengthy government security questionnaires (SCA, MTA, PASSPort) that traditionally require days of manual effort from senior compliance staff.

### How It Works

1. **Upload** — Import your company's safety policies, insurance certificates, and compliance documents.
2. **Analyze** — Upload a vendor security questionnaire (Excel). AI matches each question to relevant passages in your document library and generates draft answers with confidence scores.
3. **Review** — Examine AI-generated answers in an interactive grid. Low-confidence answers are flagged for manual review. Every edit is logged in a tamper-evident audit trail.
4. **Export** — Download a submission-ready Excel file with answers populated in the original cell locations.

### Key Capabilities

| Capability | Description |
|---|---|
| **RAG-Powered Answers** | Retrieval-augmented generation ensures answers cite your actual documents, not hallucinated content. |
| **Confidence Scoring** | Every answer includes a confidence score (HIGH / MEDIUM / LOW) with source document references. |
| **Audit Trail** | Full traceability — every AI answer, manual edit, review decision, and export is logged with user ID and timestamp. |
| **Role-Based Access** | Organization-level isolation with row-level security. Roles: Owner, Admin, Compliance Manager, Reviewer, Viewer. |
| **Source Transparency** | Each answer links back to the exact source document, page number, and excerpt used. |
| **Multi-Project** | Organize questionnaires by project for firms handling multiple contracts simultaneously. |

### Target Users

- **Compliance Officers** managing SCA/MTA/PASSPort questionnaire submissions
- **Safety Directors** maintaining documentation libraries for regulatory audits
- **Project Managers** coordinating multi-project compliance workflows

## Documentation

- `docs/OPERATOR_GUIDE.md`
- `VERIFY.md` (how to run + verify)

---

## Quick Start (Local Dev)

### Prerequisites

- **Node.js 18+** and npm
- **Python 3.11+**
- A **Supabase** project (Postgres + Auth + Storage)
- An **OpenAI API key** (for AI/RAG features)

### Environment Variables

Create the following files (**do not commit secrets**):

```bash
cp backend/.env.example backend/.env        # then fill in real values
cp frontend/.env.example frontend/.env.local # then fill in real values
```

See `backend/.env.example` and `frontend/.env.example` for the full variable list.

**Quick reference — required variables:**

| Variable | Where | Description |
|---|---|---|
| `SUPABASE_URL` | backend | Supabase project URL |
| `SUPABASE_KEY` | backend | Supabase anon/public key |
| `SUPABASE_SERVICE_ROLE_KEY` | backend | Supabase service role key (never in frontend) |
| `SUPABASE_JWT_SECRET` | backend | JWT secret for token verification |
| `OPENAI_API_KEY` | backend | OpenAI API key (GPT-4 access required) |
| `NEXT_PUBLIC_SUPABASE_URL` | frontend | Supabase project URL |
| `NEXT_PUBLIC_SUPABASE_ANON_KEY` | frontend | Supabase anon/public key |
| `NEXT_PUBLIC_API_URL` | frontend | Backend API base URL (default: `/api/v1`) |
| `ALLOWED_ORIGINS` | backend | Comma-separated CORS origins (required in prod) |

### Deployment — Vercel (Frontend)

1. Connect the repo to Vercel, set **Root Directory** to `frontend/`.
2. Set environment variables in Vercel dashboard → Settings → Environment Variables:
   - `NEXT_PUBLIC_SUPABASE_URL`
   - `NEXT_PUBLIC_SUPABASE_ANON_KEY`
   - `NEXT_PUBLIC_API_URL` → your backend URL, e.g. `https://api.yourapp.com/api/v1`
3. Framework Preset: **Next.js** (auto-detected).
4. Deploy. Vercel runs `npm run build` automatically.

### Deployment — Backend Host (Railway / Render / Fly.io)

1. Set all variables from `backend/.env.example` in the host dashboard.
2. **Critical:** Set `ALLOWED_ORIGINS` to your Vercel frontend URL (e.g. `https://yourapp.vercel.app`).
3. **Critical:** Set `ENVIRONMENT=production` to enable strict CORS and disable Swagger docs.
4. Start command: `uvicorn app.main:app --host 0.0.0.0 --port 8000 --workers 2`

### Pre-Push Secrets Scan

Before pushing to GitHub, run the secrets scanner:

```bash
./scripts/scan_secrets.sh
```

This will fail with a non-zero exit code if any secret patterns are detected in tracked files.

### Database Migrations

Run the following SQL scripts in your Supabase SQL Editor **in order**:

1. `backend/supabase_schema.sql` — Base tables: `documents`, `chunks`, `match_chunks` RPC
2. `backend/scripts/enterprise_upgrade_migration.sql` — Review columns: `review_status`, `reviewer_id`, `reviewed_at`, `review_notes`
3. `backend/scripts/017_source_excerpt.sql` — Source transparency: `source_excerpt`, `editor_id`, `edited_at`, `projects.description`

Or use the migration runner to list all migrations in order:

```bash
./scripts/migrate.sh
```

**Migration Checklist:**

- [ ] Back up the database before applying migrations
- [ ] Apply migrations in the order listed
- [ ] Test with a staging environment first
- [ ] Verify each migration completes without errors
- [ ] Run health check after: `curl http://localhost:8000/health`

### Run Everything

```bash
# From repo root (wrapper shims forward to scripts/)
./scripts/start_all.sh

# If ports 8000/3001 are already occupied:
./scripts/start_all.sh --restart
```

Or manually:

```bash
# Backend
cd backend
python3 -m venv .venv        # use .venv (no spaces in name)
source .venv/bin/activate
pip install -r requirements.txt
uvicorn app.main:app --reload --port 8000

# Frontend (separate terminal)
cd frontend
npm install
npm run dev -- -p 3001
```

- **Frontend:** <http://localhost:3001>
- **Backend health:** <http://localhost:8000/health>
- **API docs (Swagger):** <http://localhost:8000/docs>

---

## Quick Start (Docker)

Requires Docker Desktop or Colima. From repo root:

```bash
./scripts/run_all.sh
```

---

## Architecture

| Layer | Technology |
| ----- | ---------- |
| Frontend | Next.js 14 (App Router), TypeScript, Tailwind CSS, shadcn/ui |
| Backend | FastAPI (Python 3.11), Pydantic |
| Database | Supabase Postgres + Row Level Security (RLS) |
| Vector Search | pgvector extension via `match_chunks` RPC |
| AI | OpenAI GPT-4 with RAG (Retrieval-Augmented Generation) |
| Auth | Supabase Auth (JWT-based, passed to FastAPI) |

### Data Flow

```text
Excel Upload → analyze-excel → parse sheets (openpyxl)
  → identify question cells (LLM) → retrieve relevant chunks (pgvector)
  → generate grounded answers with citations (LLM + RAG)
  → store in run_audits → review/approve in UI → export approved answers to Excel
```

---

## Key Features

### Projects & Runs

- **Projects** group related questionnaires and documents
- **Runs** represent a single questionnaire analysis within a project
- Create projects from the Projects page, then start runs from the project detail page

### AI-Powered Questionnaire Analysis

1. Upload an Excel questionnaire (`.xlsx` / `.xlsm`)
2. The system identifies question cells across all visible sheets
3. Each question is answered using RAG against your uploaded documents
4. Answers include **confidence scores** (HIGH / MEDIUM / LOW) and **source citations**

### Review & Approval Workflow

- **Review Grid:** Inline accept/reject for each AI-generated answer
- **Audit Drawer:** Click any row on the Audit page for detailed view with:
  - Full question text
  - Editable answer (with original AI answer shown if overridden)
  - Confidence badge
  - Source document name and excerpt
  - Approve / Reject / Save buttons
- Review actions are **persisted to the backend** (`run_audits.review_status`)
- Each review records `reviewer_id` and `reviewed_at` for audit trail

### Export Behavior

- **Only approved/verified answers** are written to cells in the exported Excel
- Rejected or pending answers are **left blank** in the output
- An audit sheet is appended with all questions, answers, confidence, sources, and review status
- Non-approved rows are marked "(not approved)" in the audit sheet

### Source Transparency

- Each answer stores a `source_excerpt` — the top retrieval chunk used for grounding
- Source excerpts are displayed in the Review Grid and Audit Drawer
- Source document name is linked where available

### Excel Hardening

- Hidden sheets, rows, and columns are automatically **skipped**
- Empty or corrupt sheets are skipped gracefully
- LLM-returned column indexes are **clamped** to actual sheet dimensions
- Per-row error handling prevents a single bad row from crashing the entire analysis

---

## API Endpoints

### Projects

| Method | Path                         | Description           |
| ------ | ---------------------------- | --------------------- |
| GET    | `/api/v1/projects?org_id=`   | List projects for org |
| POST   | `/api/v1/projects`           | Create project        |
| GET    | `/api/v1/projects/{id}`      | Get project detail    |
| PATCH  | `/api/v1/projects/{id}`      | Update project        |

### Runs

| Method | Path                     | Description |
| ------ | ------------------------ | ----------- |
| GET    | `/api/v1/runs?org_id=`   | List runs   |
| POST   | `/api/v1/runs`           | Create run  |
| GET    | `/api/v1/runs/{id}`      | Get run     |
| PATCH  | `/api/v1/runs/{id}`      | Update run  |

### Audits

| Method | Path                                    | Description                    |
| ------ | --------------------------------------- | ------------------------------ |
| GET    | `/api/v1/runs/{id}/audits`              | List audit entries for run     |
| PATCH  | `/api/v1/runs/{id}/audits/{aid}`        | Edit answer (manual override)  |
| PATCH  | `/api/v1/runs/{id}/audits/{aid}/review` | Approve or reject answer       |

### Analysis & Export

| Method | Path                      | Description                    |
| ------ | ------------------------- | ------------------------------ |
| POST   | `/api/v1/analyze-excel`   | Upload & analyze questionnaire |
| POST   | `/api/v1/generate-excel`  | Export filled questionnaire    |

### Documents

| Method | Path                        | Description                |
| ------ | --------------------------- | -------------------------- |
| POST   | `/api/v1/ingest`            | Upload supporting document |
| GET    | `/api/v1/documents?org_id=` | List documents             |

---

## Manual Testing Walkthrough

1. **Login** — Navigate to <http://localhost:3001/login>, sign in with Supabase Auth
2. **Create/Select Org** — On first login, an org is created automatically
3. **Create Project** — Go to Projects page → click "New Project"
4. **Upload Documents** — Navigate to project detail → upload supporting docs (PDF, DOCX)
5. **Run Questionnaire** — Go to Run page → select project → upload Excel → click "Start Analysis"
6. **Review Answers** — In the Review Grid, accept/reject each answer (persisted to backend)
7. **Audit Page** — Click any row to open the detail drawer; edit answers, approve, or reject
8. **Export** — Click "Export Excel" — only approved answers appear in the output file
9. **Verify Export** — Open the downloaded Excel; check that rejected/pending cells are blank; check the appended audit sheet

---

## Verification

```bash
./scripts/verify_local.sh
cd frontend && npm test
```

---

## Project Structure

```text
├── scripts/                         # All shell scripts (dev, CI, smoke tests)
│   ├── doctor.sh                    # Preflight env diagnostics
│   ├── start_all.sh                 # Local dev launcher (backend + frontend)
│   ├── run_all.sh                   # Docker Compose launcher
│   ├── verify_local.sh              # Docker-based backend verification
│   ├── smoke.sh                     # API-level smoke tests
│   ├── smoke_setup.sh               # Smoke test user setup
│   ├── e2e_local_test.sh            # Full E2E test
│   └── run_state_smoke.sh           # Run state machine smoke test
├── backend/
│   ├── app/
│   │   ├── main.py              # FastAPI app, router registration
│   │   ├── api/
│   │   │   ├── routes.py        # analyze-excel, generate-excel endpoints
│   │   │   ├── endpoints/
│   │   │   │   ├── projects.py  # Project CRUD
│   │   │   │   ├── runs.py      # Runs, audits, review endpoints
│   │   │   │   └── audit.py     # Audit log queries
│   │   │   └── deps.py          # UUID validation helpers
│   │   ├── core/
│   │   │   ├── excel_agent.py   # Excel parsing, analysis, export
│   │   │   ├── generation.py    # AI answer generation with RAG
│   │   │   ├── retrieval.py     # Vector search (pgvector)
│   │   │   ├── org_context.py   # Org membership resolution
│   │   │   ├── auth.py          # JWT auth middleware
│   │   │   └── database.py      # Supabase client helpers
│   │   └── models/              # Pydantic schemas
│   ├── scripts/                 # SQL migrations
│   └── requirements.txt
├── frontend/
│   ├── app/                     # Next.js App Router pages
│   │   ├── run/page.tsx         # Questionnaire analysis page
│   │   ├── audit/page.tsx       # Audit review page with drawer
│   │   ├── projects/            # Project list & detail pages
│   │   ├── dashboard/           # Dashboard with stats
│   │   └── settings/            # Org & profile settings
│   ├── components/
│   │   ├── run-wizard.tsx       # Upload → analyze → review → export wizard
│   │   ├── review-grid.tsx      # Inline review grid with backend persistence
│   │   └── ui/                  # shadcn/ui components (sheet, dialog, etc.)
│   ├── lib/api.ts               # API client with auth, retry, error handling
│   ├── types/index.ts           # TypeScript interfaces
│   └── package.json
├── doctor.sh                        # Wrapper → scripts/doctor.sh
├── start_all.sh                     # Wrapper → scripts/start_all.sh
├── run_all.sh                       # Wrapper → scripts/run_all.sh
├── verify_local.sh                  # Wrapper → scripts/verify_local.sh
└── README.md
```

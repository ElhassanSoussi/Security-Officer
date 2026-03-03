# Verification Guide

## Quick Start

```bash

# From project root (pick ONE):

# Option A (recommended): run locally (Python venv + Next dev)

./scripts/start_all.sh

# If ports 8000/3001 are already occupied:

./scripts/start_all.sh --restart

# Option B: run with Docker (requires Docker Desktop or Colima running)

./scripts/run_all.sh
```

## Deterministic Retrieval Engine

### Automated Tests (Deterministic — no DB/API needed)

```bash
cd backend && source venv/bin/activate
python -m pytest tests/test_retrieval_engine.py -v
```

**22 tests covering:**

| #   | Test Class                  | Test                                     | Proves                                                   |
| --- | --------------------------- | ---------------------------------------- | -------------------------------------------------------- |
| 1   | ConfidenceScoring           | `test_high_confidence_direct_quote`      | High similarity + direct quote → HIGH confidence (≥0.7)  |
| 2   | ConfidenceScoring           | `test_low_confidence_no_context`         | No context → LOW confidence (<0.4)                       |
| 3   | ConfidenceScoring           | `test_medium_confidence_inferred`        | Moderate similarity + inferred → MEDIUM (0.3-0.7)        |
| 4   | ConfidenceScoring           | `test_confidence_score_bounded`          | Score always bounded [0.0, 0.1]                          |
| 5   | ConfidenceScoring           | `test_confidence_label_classification`   | Numeric score → categorical label mapping                |
| 6   | DirectQuoteDetection        | `test_exact_substring_detected`          | Verbatim substring → True                                |
| 7   | DirectQuoteDetection        | `test_no_match_detected`                 | No overlap → False                                       |
| 8   | DirectQuoteDetection        | `test_empty_inputs`                      | Empty strings → False (no crash)                         |
| 9   | DirectQuoteDetection        | `test_short_answer_exact_match`          | Short exact match → True                                 |
| 10  | RetrievalResult             | `test_empty_result`                      | Empty result → has_results=False, best_score=0           |
| 11  | RetrievalResult             | `test_with_chunks`                       | Chunks → correct context_text, filenames, best_score     |
| 12  | RetrievalResult             | `test_to_dict_no_debug`                  | No debug → debug_all_scores excluded from dict           |
| 13  | RetrievalResult             | `test_to_dict_with_debug`                | Debug mode → debug_all_scores included in dict           |
| 14  | ErrorResponseStructure      | `test_error_response_has_all_fields`     | Error response includes all retrieval metadata keys      |
| 15  | QuestionItemSchema          | `test_retrieval_fields_present`          | Retrieval fields populated correctly                     |
| 16  | QuestionItemSchema          | `test_retrieval_fields_optional`         | Retrieval fields default to None (backward compat)       |
| 17  | ExcelCellComments           | `test_approved_cell_has_comment`         | Approved cells get comment with confidence + source      |
| 18  | ExcelCellComments           | `test_rejected_cell_has_no_comment`      | Rejected cells get no comment                            |
| 19  | ExpandedAuditSheet          | `test_audit_sheet_has_retrieval_headers` | Audit sheet has Confidence Score, Similarity, Model cols |
| 20  | BackwardCompatibility       | `test_approved_still_writes`             | Approved write behavior preserved                        |
| 21  | BackwardCompatibility       | `test_pending_still_blank`               | Pending blank behavior preserved                         |
| 22  | ConfigSettings              | `test_default_settings`                  | Threshold=0.55, top_k=5, debug=false, strict=false       |

### Database Migration

Run before first use:
```sql
-- In Supabase SQL Editor:
-- backend/scripts/003_retrieval_engine.sql
```

### Configuration (.env)

| Variable                          | Default       | Description                               |
| --------------------------------- | ------------- | ----------------------------------------- |
| `RETRIEVAL_SIMILARITY_THRESHOLD`  | `0.55`        | Min cosine similarity to accept a chunk   |
| `RETRIEVAL_TOP_K`                 | `5`           | Max chunks to retrieve per query          |
| `RETRIEVAL_DEBUG`                 | `false`       | Return top-5 chunks with scores in API    |
| `STRICT_MODE`                     | `false`       | Model must quote from source, no synthesis|
| `LLM_MODEL`                      | `gpt-4-turbo` | Model for answer generation               |
| `LLM_TIMEOUT_SECONDS`            | `60`          | Timeout for LLM API calls                 |

---

## Export Gate: Project Workspace + Knowledge Vault + Review

### Automated Tests (Deterministic — no DB/API needed)

```bash
cd backend && source venv/bin/activate
python -m pytest tests/test_export_gate.py -v
```

**6 tests covering:**

| #   | Test                                        | Proves                                            |
| --- | ------------------------------------------- | ------------------------------------------------- |
| 1   | `test_approved_answer_written_to_cell`      | Approved answers ARE written to Excel cells       |
| 2   | `test_rejected_answer_left_blank`           | Rejected answers leave cells blank                |
| 3   | `test_pending_answer_left_blank`            | Pending (unreviewed) answers leave cells blank    |
| 4   | `test_mixed_review_statuses`                | Mixed batch: only approved fills, others blank    |
| 5   | `test_audit_sheet_records_review_status`    | Audit sheet records Approved/Rejected labels      |
| 6   | `test_not_found_in_locker_has_needs_info_status` | Missing-context answers get `needs_info` status |

### Manual Verification Checklist

- [ ] **Create Project**: POST /api/v1/projects with name → returns project_id
- [ ] **Upload Document**: POST /api/v1/projects/{id}/documents with PDF → 200 + chunks_count
- [ ] **List Documents**: GET /api/v1/projects/{id}/documents → returns uploaded doc
- [ ] **Run Analysis**: POST /api/v1/analyze-excel with project_id → answers grounded in project docs
- [ ] **Review Answers**: PATCH /api/v1/runs/{id}/audits/{id}/review with approved/rejected → persists
- [ ] **Bulk Review**: POST /api/v1/runs/{id}/audits/bulk-review → approves all pending
- [ ] **Export Readiness**: GET /api/v1/runs/{id}/export-readiness → counts approved/pending/rejected
- [ ] **Export Gate**: POST /api/v1/generate-excel with mixed statuses → only approved fill cells
- [ ] **Delete Document**: DELETE /api/v1/projects/{id}/documents/{id} → removes from vault

### Database Migration

Run before first use:
```sql
-- In Supabase SQL Editor:
-- backend/scripts/002_project_workspace.sql
```

### Frontend Flows

- [ ] Projects page → Create project → redirects to detail page
- [ ] Project detail → Knowledge Vault tab → upload PDF/DOCX/TXT → appears in list
- [ ] Project detail → Run Questionnaire tab → upload Excel → analysis runs
- [ ] Review grid → Approve/Reject individual answers → badges update
- [ ] Review grid → "Approve All Pending" bulk action → all turn green
- [ ] Export button shows count of approved answers
- [ ] Export warns when pending answers exist
- [ ] Export button disabled when 0 approved answers
- [ ] Exported Excel has approved cells filled, rejected/pending cells blank

---

## Automated Smoke Test (API-Level, Deterministic)

This repo includes a strict smoke test that exercises:

- public health/readiness
- sample questionnaire download (xlsx validity)
- Supabase password login (requires env)
- authenticated org/settings/plans/audit endpoints
- analyze-excel + generate-excel export (xlsx validity)

```bash

# In a separate shell, while the stack is running:

# Option A (recommended): generate a dedicated smoke user (stores creds in .smoke.env; not printed)

./scripts/smoke_setup.sh
./scripts/smoke.sh

# Run-state and download contract smoke

# (validates 409 export_not_ready, 404 export_missing, and 200 file download)

TOKEN="<access_token>" ORG_ID="<org_uuid>" ./scripts/run_state_smoke.sh

# Full API E2E flow (login -> org/project -> analyze -> export -> download)

# If Docker is not running, the script auto-reuses your currently running local stack.

E2E_USE_RUNNING=1 ./scripts/e2e_local_test.sh

# Option B: use your own account

# export SMOKE_EMAIL="you@example.com"

# export SMOKE_PASSWORD="your-password"

# ./scripts/smoke.sh

```

## What It Tests

| # | Endpoint | Auth | Pass Criteria |
| :--- | :--- | :--- | :--- |
| 1 | `GET /` | No | 200 OK |
| 2 | `GET /api/v1/health` | No | 200 + JSON status |
| 3 | `GET /api/v1/orgs` | Yes | 401/403 (no 500) |
| 4 | `GET /api/v1/projects` | Yes | 401/403 (no 500) |
| 5 | `GET /api/v1/billing/plans` | Yes | 401/403 (no 500) |
| 6 | `GET /api/v1/billing/subscription` | Yes | 401/403 (no 500) |
| 7 | `GET /api/v1/runs/samples/questionnaire` | No | 200 + .xlsx download |
| 8 | Run Questionnaire → Export | Yes | Analysis completes + `.xlsx` downloads |
| 9 | `POST/PATCH /api/v1/runs` | Yes | `queued -> processing -> completed` only |
| 10 | `GET /api/v1/runs/{id}/download` | Yes | 409 before complete, 404 when missing export, 200 when ready |

## Expected Output

```text
Results: 7 PASSED / 0 FAILED out of 7 tests
🎉 ALL TESTS PASSED — Backend is operational!
```

For `scripts/e2e_local_test.sh`:

```text
Health checks passed.
E2E PASS
```

## Prerequisites

- For `./scripts/run_all.sh` / `./scripts/verify_local.sh`:
  - Docker Desktop or Colima running
- For `./scripts/start_all.sh`:
  - Node.js + npm installed
  - Backend Python venv present at `backend/.venv/` (or `backend/venv/`)
- No other service using ports 8000 or 3001

## Environment Variables

- Frontend reads: `frontend/.env.local`
  - `NEXT_PUBLIC_SUPABASE_URL`
  - `NEXT_PUBLIC_SUPABASE_ANON_KEY`

- Backend reads: `backend/.env`
  - `SUPABASE_URL`
  - `SUPABASE_KEY`
  - `SUPABASE_SECRET_KEY` (recommended for admin automation like `smoke_setup`)
  - `SUPABASE_JWT_SECRET` (optional if backend validates via Supabase Auth fallback)
  - `BILLING_ENABLED` (default false; set true only when Stripe + billing tables are ready)

- Smoke test reads (shell env):
  - `SMOKE_EMAIL`
  - `SMOKE_PASSWORD`

If login fails with **"Invalid API key"**, your Supabase URL/key do not match. Copy the **anon public** key from:
Supabase Dashboard → Project Settings → API.

If you see **"Missing required env var: NEXT_PUBLIC_SUPABASE_URL"** in the browser:

1) verify `frontend/.env.local` contains `NEXT_PUBLIC_SUPABASE_URL` and `NEXT_PUBLIC_SUPABASE_ANON_KEY`
2) stop Next.js completely
3) restart with `./scripts/start_all.sh` (or rebuild with `./scripts/run_all.sh`).

For real Supabase connectivity when using Docker verify script, export your keys first (or rely on `backend/.env`):

```bash
export SUPABASE_URL="https://your-project.supabase.co"
export SUPABASE_KEY="your-anon-key"
export OPENAI_API_KEY="sk-your-key"
./scripts/verify_local.sh
```

## UI Auth Pages Checklist

1) Start stack: `./scripts/start_all.sh` (or `./scripts/run_all.sh`)  
2) Sign in via UI.  
3) Open `/plans`, `/audit`, `/settings` in the browser.  
4) In DevTools → Network, every `/api/v1/...` call must include `Authorization: Bearer <access_token>` and return 200/403 (never 500).  
5) Log out and revisit pages; you should be redirected to `/login` (no request storm of 401s).  
6) No backend tracebacks (especially `parse_uuid` TypeError) while browsing those pages.

## Landing + Auth + Settings + Onboarding

### Public routes (no auth)

```bash

# Expect 200 for all public routes

for p in / /login /signup /health; do
  curl -s -o /tmp/page.html -w "$p -> %{http_code}\n" "http://127.0.0.1:3001$p"
done
```

Expected:

- `/` returns `200` and renders the public landing page (hero text includes `NYC Construction Compliance OS`)
- `/login`, `/signup`, `/health` return `200`

### Protected routes (logged out behavior)

```bash

# Expect middleware redirect to /login while logged out

for p in /dashboard /projects /run /plans /audit /settings /onboarding; do
  curl -s -o /tmp/page.html -w "$p -> %{http_code}\n" "http://127.0.0.1:3001$p"
done
```

Expected:

- Protected routes return `307` (redirect to `/login`) when not authenticated

### Authenticated settings round-trip (profile + org)

Use the smoke account (`.smoke.env`) or export `SMOKE_EMAIL` / `SMOKE_PASSWORD`.

```bash
./scripts/smoke.sh
```

What this now proves (must all pass):

- `GET /api/v1/settings/profile -> 200`
- `GET /api/v1/settings/org -> 200`
- `GET /api/v1/audit/log -> 200`
- `GET /api/v1/audit/exports -> 200`
- `GET /api/v1/projects -> 200`
- `POST /api/v1/analyze-excel -> 200`
- `POST /api/v1/generate-excel -> 200` + valid `.xlsx`

Optional direct save verification (safe no-op update of current values):

```bash
set -a; source frontend/.env.local; source .smoke.env; set +a
API=http://127.0.0.1:8000/api/v1
TOKEN=$(curl -sS "$NEXT_PUBLIC_SUPABASE_URL/auth/v1/token?grant_type=password" \
  -H "apikey: $NEXT_PUBLIC_SUPABASE_ANON_KEY" \
  -H "Content-Type: application/json" \
  -d "{\"email\":\"$SMOKE_EMAIL\",\"password\":\"$SMOKE_PASSWORD\"}" | jq -r '.access_token')
ORG_ID=$(curl -sS -H "Authorization: Bearer $TOKEN" "$API/orgs/current" | jq -r '.id')
curl -sS -H "Authorization: Bearer $TOKEN" "$API/settings/profile" | tee /tmp/profile.json >/dev/null
curl -sS -H "Authorization: Bearer $TOKEN" "$API/settings/org?org_id=$ORG_ID" | tee /tmp/org.json >/dev/null
curl -sS -o /tmp/profile_put.json -w "profile_put=%{http_code}\n" \
  -X PUT -H "Authorization: Bearer $TOKEN" -H "Content-Type: application/json" \
  -d "$(jq '{full_name,phone,title}' /tmp/profile.json)" "$API/settings/profile"
curl -sS -o /tmp/org_put.json -w "org_put=%{http_code}\n" \
  -X PUT -H "Authorization: Bearer $TOKEN" -H "Content-Type: application/json" \
  -d "$(jq '{name,trade_type,company_size}' /tmp/org.json)" "$API/settings/org?org_id=$ORG_ID"
```

Expected:

- `profile_put=200`
- `org_put=200`

### Onboarding verification (new user)

For a new user (no memberships yet):

1) Sign up in UI (`/signup`)
2) Login
3) App routes to `/onboarding`
4) Create Organization
5) (Optional) Upload baseline docs
6) Finish -> redirected to `/dashboard`

If testing via API instead of UI, verify the org bootstrap behavior:

- `GET /api/v1/orgs/current` returns `404` before org creation
- `POST /api/v1/orgs` returns `200` and creates owner membership
- `GET /api/v1/orgs/current` returns `200` after creation

## End-to-End Run + Export (Mandatory)

1) Go to `http://localhost:3001/run`  
2) Click **Download Sample** and save the `.xlsx`  
3) Upload the sample `.xlsx` and click **Start Analysis**  
4) Wait for **Analysis Complete**  
5) Click **Export Excel**  
6) Confirm your browser downloads `filled_*.xlsx`  
7) Open the export locally and confirm it contains:
   - a filled workbook
   - an `AI_Verification_Audit` sheet

## Health Page

Open `/health` to quickly validate:

- frontend env present
- backend reachable via proxy
- Supabase auth reachable (detects invalid API key)
- session token works against backend (`/api/v1/orgs`)

## Billing Schema & Deep Health

- Billing is optional. Set `BILLING_ENABLED=false` for local/dev to skip billing checks.
- When `BILLING_ENABLED=false`, read endpoints still return 200 with starter fallback:
  - `GET /api/v1/billing/plans`
  - `GET /api/v1/billing/subscription?org_id=<uuid>`
  - `GET /api/v1/billing/summary?org_id=<uuid>`
- If `BILLING_ENABLED=true`, ensure billing tables exist (notably `billing_events`).
- Apply schema to Supabase (one-time):

  ```bash

  # requires DATABASE_URL (supabase connection string) or run in Supabase SQL editor

  psql "$DATABASE_URL" -f backend/scripts/billing_events_schema.sql
  ```

- Deep health:
  - `/api/v1/health/deep` returns 200 when billing disabled OR schema present.
  - When enabled and schema missing, returns 503 with `billing_schema_missing`.

---

## Multi-Run Intelligence + Institutional Memory Engine

### Automated Tests (Deterministic — no DB/API needed)

```bash
cd backend && source venv/bin/activate
python -m pytest tests/test_multi_run_intelligence.py -v
```

**43 tests covering:**

| #   | Test Class                  | Test                                          | Proves                                                          |
| --- | --------------------------- | --------------------------------------------- | --------------------------------------------------------------- |
| 1   | EmbeddingCache              | `test_put_and_get`                            | Cache stores and retrieves embeddings                           |
| 2   | EmbeddingCache              | `test_cache_miss`                             | Returns None for unknown keys                                   |
| 3   | EmbeddingCache              | `test_case_insensitive`                       | Key lookup is case-insensitive                                  |
| 4   | EmbeddingCache              | `test_whitespace_normalization`               | Whitespace is stripped for key matching                         |
| 5   | EmbeddingCache              | `test_lru_eviction`                           | Oldest entry evicted when cache full                            |
| 6   | EmbeddingCache              | `test_access_refreshes_lru_order`             | Accessing a key prevents its eviction                           |
| 7   | EmbeddingCache              | `test_clear`                                  | Clear empties the cache completely                              |
| 8   | EmbeddingCache              | `test_update_existing_key`                    | Re-putting same key updates value, keeps size=1                 |
| 9   | SimilarityDataclasses       | `test_similarity_match_to_dict`               | SimilarityMatch serializes correctly                            |
| 10  | SimilarityDataclasses       | `test_similarity_result_empty`                | Empty result → action="generate"                                |
| 11  | SimilarityDataclasses       | `test_similarity_result_reusable`             | action="reuse" → has_reusable=True                              |
| 12  | SimilarityDataclasses       | `test_similarity_result_suggestion`           | action="suggest" → has_suggestion=True                          |
| 13  | SimilarityDataclasses       | `test_similarity_result_to_dict`              | SimilarityResult to_dict includes all fields                    |
| 14  | ReuseClassification         | `test_exact_reuse_threshold`                  | 0.90 ≥ REUSE_EXACT_THRESHOLD → reuse                           |
| 15  | ReuseClassification         | `test_suggestion_threshold`                   | 0.80 in suggest range [0.75, 0.90)                              |
| 16  | ReuseClassification         | `test_below_suggestion_threshold`             | 0.70 < 0.75 → normal generation                                |
| 17  | ReuseClassification         | `test_engine_classifies_reuse`                | 0.95 → "reuse" action                                          |
| 18  | ReuseClassification         | `test_engine_classifies_suggest`              | 0.82 → "suggest" action                                        |
| 19  | ReuseClassification         | `test_engine_classifies_generate`             | 0.60 → "generate" action                                       |
| 20  | DeltaTracking               | `test_all_new_questions`                      | No previous → all NEW                                           |
| 21  | DeltaTracking               | `test_all_unchanged`                          | Identical questions → all UNCHANGED                             |
| 22  | DeltaTracking               | `test_modified_question`                      | Same cell, different text → MODIFIED                            |
| 23  | DeltaTracking               | `test_mixed_delta`                            | Mix of NEW + MODIFIED + UNCHANGED                               |
| 24  | DeltaTracking               | `test_case_insensitive_matching`              | "Is Fire Safety OK?" matches "is fire safety ok?"               |
| 25  | DeltaTracking               | `test_empty_current`                          | Empty current → empty delta                                     |
| 26  | DeltaTracking               | `test_normalize_question`                     | Whitespace + case normalization                                 |
| 27  | QuestionItemMultiRun        | `test_multi_run_fields_present`               | answer_origin, reused_from, change_type all set                 |
| 28  | QuestionItemMultiRun        | `test_multi_run_fields_optional`              | All multi-run fields default to None                            |
| 29  | QuestionItemMultiRun        | `test_reused_question_item`                   | Reused item has model_used="reused", tokens=0                   |
| 30  | QuestionItemMultiRun        | `test_suggested_question_item`                | Suggested item has correct origin + score                       |
| 31  | AuditSheetMultiRun          | `test_audit_sheet_has_answer_origin_header`   | Export audit sheet has "Answer Origin" column                   |
| 32  | AuditSheetMultiRun          | `test_audit_sheet_default_origin_is_generated`| Missing origin defaults to "generated"                          |
| 33  | GenerationMultiRunFields    | `test_error_response_has_multi_run_fields`    | Error responses include multi-run keys                          |
| 34  | GenerationMultiRunFields    | `test_not_found_response_has_multi_run_fields`| NOT FOUND responses include multi-run keys                      |
| 35  | ConfigMultiRun              | `test_multi_run_default_settings`             | All 5 multi-run config defaults correct                         |
| 36  | ConfigMultiRun              | `test_thresholds_ordered`                     | SUGGEST < EXACT, both in (0,1]                                  |
| 37  | BackwardCompatibility       | `test_retrieval_question_item_still_works`    | Retrieval fields unchanged                                      |
| 38  | BackwardCompatibility       | `test_approved_answer_still_written`          | Approved → cell gets answer (no regression)                     |
| 39  | BackwardCompatibility       | `test_rejected_answer_not_written`            | Rejected → cell stays blank (no regression)                     |
| 40  | RunComparisonDelta          | `test_comparison_identifies_removed_questions`| Removed questions detected separately                           |
| 41  | RunComparisonDelta          | `test_comparison_all_new`                     | No overlap → all NEW                                            |
| 42  | RunComparisonDelta          | `test_comparison_preserves_whitespace_in_keys`| Original text used as key, norm used for matching               |
| 43  | SimilarityEngineDisabled    | `test_disabled_reuse_returns_generate`        | REUSE_ENABLED=False → always "generate"                         |

### Run All Tests (Phase 2 + 3 + 4)

```bash
python -m pytest tests/test_phase2_export_gate.py tests/test_phase3_retrieval_engine.py tests/test_phase4_multi_run_intelligence.py -v

# Expected: 71 passed

```

### Migration SQL

```bash

# Apply in Supabase SQL Editor or via psql:

psql "$DATABASE_URL" -f backend/scripts/004_multi_run_intelligence.sql
```

Creates:
- `question_embeddings` table (org-scoped, RLS, vector 1536)
- `match_question_embeddings` RPC for similarity search
- `answer_origin`, `reused_from_question_id`, `reuse_similarity_score`, `change_type` columns on `run_audits`
- `previous_run_id` column on `runs`

### New API Endpoints

| Method | Path                                          | Purpose                                     |
| ------ | --------------------------------------------- | ------------------------------------------- |
| GET    | `/api/v1/runs/{run_id}/compare/{prev_run_id}` | Side-by-side run comparison with delta types |
| GET    | `/api/v1/runs/{run_id}/audits/filter`          | Filter audits by change_type / answer_origin |

### Key Behaviors

1. **Reuse Flow**: On approval, Q&A pair is embedded into `question_embeddings`. On future runs, similarity search runs *before* retrieval. ≥0.90 = reuse (skip LLM), 0.75-0.90 = suggestion, <0.75 = normal.
2. **Delta Tracking**: Questions compared between runs by normalized text + cell reference. Each tagged NEW/MODIFIED/UNCHANGED.
3. **Embedding Cache**: LRU cache (default 1000 entries) avoids redundant OpenAI embedding calls on repeated questions.
4. **Batch Embeddings**: `batch_get_embeddings()` sends uncached texts in a single API call.
5. **Schema Drift**: Phase 4 columns gracefully stripped if migration not applied — routes fall back to Phase 3 behavior.
6. **No Excel Regression**: Export still writes only approved answers. Audit sheet gains "Answer Origin" column.

### Files Changed (Phase 4)

| File | Change |
| ---- | ------ |
| `backend/scripts/004_multi_run_intelligence.sql` | NEW — question_embeddings table + RPC + run_audits Phase 4 columns |
| `backend/app/core/similarity.py` | NEW — EmbeddingCache, SimilarityEngine, compute_delta, batch_get_embeddings |
| `backend/app/core/config.py` | MODIFIED — 5 new Phase 4 settings |
| `backend/app/models/schemas.py` | MODIFIED — 4 new Phase 4 fields on QuestionItem |
| `backend/app/core/generation.py` | MODIFIED — similarity search before retrieval, Phase 4 fields in all responses |
| `backend/app/core/excel_agent.py` | MODIFIED — Phase 4 fields passed through, "Answer Origin" audit column |
| `backend/app/api/routes.py` | MODIFIED — Phase 4 columns persisted in run_audits, schema drift handling |
| `backend/app/api/endpoints/runs.py` | MODIFIED — _store_approved_embedding helper, compare endpoint, filter endpoint |
| `backend/tests/test_phase4_multi_run_intelligence.py` | NEW — 43 deterministic tests |
| `VERIFY.md` | MODIFIED — Phase 4 verification section |

---

## Phase 5 Part 1: Role-Based Access Control (RBAC) — Hard Security Layer

### Automated Tests (Deterministic — no DB/API needed)

```bash
cd backend && source venv/bin/activate
python -m pytest tests/test_phase5_rbac.py -v
```

**47 tests covering:**

| #   | Test Class                  | Test                                                    | Proves                                                      |
| --- | --------------------------- | ------------------------------------------------------- | ----------------------------------------------------------- |
| 1   | RoleEnum                    | `test_all_five_roles_defined`                           | Exactly 5 roles: owner, admin, compliance_manager, reviewer, viewer |
| 2   | RoleEnum                    | `test_role_values_are_lowercase`                        | All role values are lowercase strings                       |
| 3   | RoleEnum                    | `test_role_is_string_enum`                              | Role enum extends str for direct comparison                 |
| 4   | NormalizeRole               | `test_valid_roles_pass_through`                         | All 5 roles normalize to themselves                         |
| 5   | NormalizeRole               | `test_case_insensitive`                                 | "OWNER" → "owner", "Admin" → "admin"                       |
| 6   | NormalizeRole               | `test_legacy_manager_alias`                             | "manager" → "compliance_manager" (backward compat)          |
| 7   | NormalizeRole               | `test_whitespace_stripped`                               | "  owner  " → "owner"                                       |
| 8   | NormalizeRole               | `test_none_returns_none`                                | None input → None output                                    |
| 9   | NormalizeRole               | `test_empty_string_returns_none`                        | "" or whitespace → None                                     |
| 10  | NormalizeRole               | `test_unknown_role_returns_none`                        | "superadmin" → None (no silent promotion)                   |
| 11  | PermissionEnum              | `test_all_permissions_defined`                          | All 14 permissions exist                                    |
| 12  | PermissionEnum              | `test_permission_is_string_enum`                        | Permission extends str                                      |
| 13  | PermissionMatrix            | `test_owner_has_all_permissions`                        | Owner = full access                                         |
| 14  | PermissionMatrix            | `test_admin_has_all_permissions`                        | Admin = full access                                         |
| 15  | PermissionMatrix            | `test_compliance_manager_can_upload_and_analyze`        | CM gets upload, analyze, edit, review, export               |
| 16  | PermissionMatrix            | `test_compliance_manager_cannot_manage_org`             | CM denied org_settings + manage_members                     |
| 17  | PermissionMatrix            | `test_reviewer_can_review_and_read`                     | Reviewer gets view + review + export                        |
| 18  | PermissionMatrix            | `test_reviewer_cannot_create_or_upload`                 | Reviewer denied create, upload, edit, run_analysis          |
| 19  | PermissionMatrix            | `test_viewer_read_only`                                 | Viewer gets only view_project, view_document, view_run      |
| 20  | PermissionMatrix            | `test_viewer_cannot_mutate`                             | Viewer denied all write operations                          |
| 21  | PermissionMatrix            | `test_unknown_role_has_no_permissions`                   | Unknown role → zero permissions                              |
| 22  | PermissionMatrix            | `test_none_role_has_no_permissions`                      | None → zero permissions                                      |
| 23  | PermissionMatrix            | `test_empty_role_has_no_permissions`                     | "" → zero permissions                                        |
| 24  | GetRolePermissions          | `test_owner_gets_all`                                   | Owner set = full Permission set                             |
| 25  | GetRolePermissions          | `test_viewer_gets_three`                                | Viewer set = exactly 3 permissions                          |
| 26  | GetRolePermissions          | `test_unknown_role_gets_empty_set`                      | Bad role → empty set                                         |
| 27  | GetRolePermissions          | `test_none_gets_empty_set`                              | None → empty set                                             |
| 28  | ForbiddenResponse           | `test_forbidden_response_structure`                     | 403 JSON has error, message, required_permission, your_role |
| 29  | ForbiddenResponse           | `test_forbidden_response_none_role`                     | None role shows as "none" in response                       |
| 30  | ForbiddenResponse           | `test_forbidden_response_contains_all_keys`             | Exactly 4 keys in response                                  |
| 31  | RequireRoleFactory          | `test_returns_role_checker`                             | Factory returns RoleChecker instance                        |
| 32  | RequireRoleFactory          | `test_checker_stores_permission`                        | Checker retains the permission it was created with          |
| 33  | RoleHierarchy               | `test_owner_superset_of_admin`                          | owner ⊇ admin                                               |
| 34  | RoleHierarchy               | `test_admin_superset_of_compliance_manager`             | admin ⊇ compliance_manager                                   |
| 35  | RoleHierarchy               | `test_compliance_manager_superset_of_reviewer`          | compliance_manager ⊇ reviewer                                |
| 36  | RoleHierarchy               | `test_reviewer_superset_of_viewer`                      | reviewer ⊇ viewer                                            |
| 37  | RoleHierarchy               | `test_strict_escalation_viewer_to_reviewer`             | reviewer ⊃ viewer (strictly more)                            |
| 38  | RoleHierarchy               | `test_strict_escalation_reviewer_to_compliance_manager` | compliance_manager ⊃ reviewer (strictly more)                |
| 39  | BackwardCompatibility       | `test_question_item_schema_unchanged`                   | Phase 4 fields still present on QuestionItem                |
| 40  | BackwardCompatibility       | `test_existing_settings_preserved`                      | Phase 3+4 config settings unaffected                        |
| 41  | BackwardCompatibility       | `test_rbac_import_does_not_break_auth`                  | rbac + auth modules coexist                                  |
| 42  | EndpointPermissionMapping   | `test_ingest_requires_upload_document`                  | Upload: owner/CM ✓, reviewer/viewer ✗                       |
| 43  | EndpointPermissionMapping   | `test_analyze_requires_run_analysis`                    | Analyze: owner/CM ✓, reviewer/viewer ✗                      |
| 44  | EndpointPermissionMapping   | `test_review_requires_review_answer`                    | Review: owner/reviewer ✓, viewer ✗                          |
| 45  | EndpointPermissionMapping   | `test_edit_answer_requires_edit_answer`                 | Edit: owner/CM ✓, reviewer/viewer ✗                         |
| 46  | EndpointPermissionMapping   | `test_create_project_requires_create_project`           | Create project: owner/CM ✓, reviewer/viewer ✗               |
| 47  | EndpointPermissionMapping   | `test_delete_document_requires_delete_document`         | Delete doc: admin/CM ✓, reviewer/viewer ✗                   |

### Run ALL Tests (Phase 2 + 3 + 4 + 5)

```bash
cd backend && source venv/bin/activate
python -m pytest tests/ -v

# Expected: 118 passed, 0 failed

```

### Migration

```bash

# Apply to Supabase via SQL Editor or psql:

cat backend/scripts/006_rbac.sql
```

### Key Behaviors

1. **5 Roles**: owner, admin, compliance_manager, reviewer, viewer — with strict permission matrix.
2. **14 Permissions**: Covering org management, projects, documents, analysis, review, and export.
3. **Role Hierarchy**: owner ⊇ admin ⊇ compliance_manager ⊇ reviewer ⊇ viewer (strict superset at each level).
4. **Structured 403**: Every denial returns `{"error": "forbidden", "message": "...", "required_permission": "...", "your_role": "..."}`.
5. **Backend-Only Enforcement**: All checks happen server-side in FastAPI — frontend is never trusted.
6. **Legacy Alias**: "manager" normalizes to "compliance_manager" for backward compatibility.
7. **Graceful Degradation**: If role lookup fails (e.g., missing migration), RLS still enforces org-level access.

### Endpoints Protected (Phase 5)

| Endpoint | Permission Required | Roles Allowed |
| -------- | ------------------- | ------------- |
| `POST /api/v1/ingest` | `upload_document` | owner, admin, compliance_manager |
| `POST /api/v1/answer` | `run_analysis` | owner, admin, compliance_manager |
| `POST /api/v1/analyze-excel` | `run_analysis` | owner, admin, compliance_manager |
| `POST /api/v1/runs` | `run_analysis` | owner, admin, compliance_manager |
| `POST /api/v1/projects` | `create_project` | owner, admin, compliance_manager |
| `PATCH /api/v1/projects/{id}` | `edit_project` | owner, admin, compliance_manager |
| `POST /api/v1/projects/{id}/documents` | `upload_document` | owner, admin, compliance_manager |
| `DELETE /api/v1/projects/{id}/documents/{id}` | `delete_document` | owner, admin, compliance_manager |
| `PATCH /api/v1/runs/{id}/audits/{id}` | `edit_answer` | owner, admin, compliance_manager |
| `PATCH /api/v1/runs/{id}/audits/{id}/review` | `review_answer` | owner, admin, compliance_manager, reviewer |
| `POST /api/v1/runs/{id}/audits/bulk-review` | `bulk_review` | owner, admin, compliance_manager, reviewer |

### Files Changed (Phase 5 Part 1)

| File | Change |
| ---- | ------ |
| `backend/app/core/rbac.py` | NEW — Role/Permission enums, permission matrix, get_user_role, require_role factory, RoleChecker, structured 403 |
| `backend/scripts/006_rbac.sql` | NEW — Role constraint on memberships, index, default, RLS policy |
| `backend/app/api/routes.py` | MODIFIED — Role checks on ingest, answer, analyze-excel |
| `backend/app/api/endpoints/runs.py` | MODIFIED — Role checks on create_run, update_audit, review_audit, bulk_review |
| `backend/app/api/endpoints/projects.py` | MODIFIED — Role checks on create_project, update_project |
| `backend/app/api/endpoints/documents.py` | MODIFIED — Role checks on upload_document, delete_document |
| `backend/tests/test_phase5_rbac.py` | NEW — 47 deterministic tests |
| `VERIFY.md` | MODIFIED — Phase 5 Part 1 verification section |

---

## Phase 13: Enterprise UI Polish + Trust Layer

### Automated Tests (Frontend)

```bash
cd frontend
npm run test
```

**5 tests covering:**

| #   | Test                                        | Proves                                            |
| --- | ------------------------------------------- | ------------------------------------------------- |
| 1   | `normalizeConfidenceScore: returns null`    | Empty/invalid values return null                  |
| 2   | `normalizeConfidenceScore: accepts 0..1`    | Ratios are correctly normalized                   |
| 3   | `normalizeConfidenceScore: accepts 0..100`  | Percentages are correctly normalized              |
| 4   | `normalizeConfidenceScore: returns null`    | Out-of-range numbers return null                  |
| 5   | `formatConfidencePercent: formats`          | Formats to percent or dash                        |

### Manual Verification Checklist

- [x] **Breadcrumbs**: Verify breadcrumbs are present in deep pages (`projects/[orgId]/[projectId]/page.tsx`, `runs/[id]/page.tsx`, `security/page.tsx`).
- [x] **EmptyState**: Verify `EmptyState` component in Project Details page accepts `title` and `description` props.
- [x] **Sticky Headers**: Verify global `TableHeader` component has sticky headers (`sticky top-0 z-10 bg-background`).
- [x] **CSP**: Verify Content Security Policy allows local WebSocket connections (`ws://127.0.0.1:*` and `ws://localhost:*`).
- [x] **Linting**: Verify `npm run lint` passes with 0 errors.
- [x] **Build**: Verify `npm run build` compiles successfully.
- [x] **E2E Tests**: Verify frontend and backend tests pass successfully.

### Full E2E Test Results (2026-02-27)

```bash
bash scripts/e2e_full_test.sh   # 10/10 passed
```

| Step | Test                          | Result |
|------|-------------------------------|--------|
| 1    | Backend Health                | ✅ PASS |
| 2    | Frontend Proxy Health         | ✅ PASS |
| 3    | Authentication (Supabase)     | ✅ PASS |
| 4    | Organization                  | ✅ PASS |
| 5    | Projects                      | ✅ PASS |
| 6    | Analyze Excel (Direct)        | ✅ PASS — 3 questions |
| 7    | Analyze Excel (Proxy)         | ✅ PASS — 3 questions |
| 8    | Runs List                     | ✅ PASS — 13 runs |
| 9    | Generate Excel Export         | ✅ PASS — 6061B |
| 10   | Audit Log                     | ✅ PASS — 19 entries |

### Key Fixes Applied

- **`next.config.mjs`**: Next.js 14.2.x doesn't support `.ts` config. Restored `.mjs` format.
- **Console Ninja**: VS Code extension was intercepting and killing Next.js. Disabled by renaming extension dir.
- **Proxy route** (`app/api/v1/[...path]/route.ts`): Fixed `content-length` preservation, added `maxDuration=120`.
- **Error handling** (`app/run/page.tsx`, `components/run-wizard.tsx`): Parse backend error body instead of generic "Analysis failed".
- **Schema drift** (`backend/app/api/routes.py`): Progressive column stripping for `run_audits` inserts.

### Test Suite Summary

| Suite              | Count   | Status |
|--------------------|---------|--------|
| Frontend unit      | 5/5     | ✅ All pass |
| Backend unit       | 258/258 | ✅ All pass |
| Frontend lint      | —       | ✅ 0 errors |
| Frontend build     | —       | ✅ Compiles |
| E2E (full stack)   | 10/10   | ✅ All pass |

---

## Phase 14 — Demo-Ready Onboarding + Guided First Run (2026-02-27)

### Overview

Six-part frontend-first feature set: persistent onboarding checklist, multi-step run wizard with stepper, enterprise run details with export gate, improved audit review with filter chips and bulk actions, demo mode, and RBAC permission guards.

### New Files

| File | Purpose |
|---|---|
| `frontend/lib/rbac.ts` | `OrgRole` type, `ROLE_RANK`, `hasRole`, `canReview`, `canEdit`, `canExport`, `canManageProjects`, `canManageMembers`, `roleLabel`, `parseMembershipRole` |
| `frontend/lib/demo-data.ts` | `isDemoMode()`, demo constants, full typed demo data: project, documents, run, audits, stats, activity |
| `frontend/lib/onboarding.ts` | `OnboardingStepId`, `ONBOARDING_STEPS` (6 steps), localStorage helpers, `deriveCompletedSteps()` |
| `frontend/components/OnboardingChecklist.tsx` | Collapsible, dismissible checklist card with progress bar, per-scope localStorage persistence |
| `frontend/components/RunSummaryCards.tsx` | 6 stat cards: Total, High Conf, Medium Conf, Low Conf, Reviewed, Pending |
| `frontend/components/ExportGatePanel.tsx` | Status breakdown, unreviewed-low warning, confirmation checkbox modal, RBAC-gated export button |
| `frontend/components/AuditFilterChips.tsx` | Filter chips (All/High/Medium/Low/Pending/Approved/Rejected) with counts + helper functions |
| `frontend/components/BulkActions.tsx` | Bulk review buttons (Approve all pending, Reject all pending, Approve all HIGH, Flag all LOW) with RBAC gate |
| `frontend/hooks/useRBAC.ts` | React hook fetching membership role from Supabase, exposes all `can*` permission booleans |

### Modified Files

| File | Changes |
|---|---|
| `frontend/app/dashboard/page.tsx` | Demo mode short-circuit, `OnboardingChecklist` replaces Getting Started card, demo banner + "Load Demo Workspace" button |
| `frontend/app/audit/page.tsx` | `useRBAC` hook, `AuditFilterChips`, `BulkActions`, `runIdFilter` URL param sync, `drawerNote` rejection gate, 4 bulk handlers, RBAC-gated action buttons |
| `frontend/app/runs/[id]/page.tsx` | `RunSummaryCards`, `ExportGatePanel`, `useRBAC`, "Open Audit for this Run →" link with `?run_id=` param |
| `frontend/components/run-wizard.tsx` | `WizardStepper` (5-step stepper), `wizardStep` state replacing `step`, stepper wired into JSX, `handleAnalyze` transitions through `"progress"` step |

### Deletions

| File | Reason |
|---|---|
| `frontend/next.config.ts` | Stale duplicate — `next.config.mjs` is the active config file |

### Part Checklist

#### Part 1 — Persistent Onboarding Checklist

- [x] `OnboardingChecklist` component with collapsible card, progress bar, dismissible per-scope
- [x] 6 `ONBOARDING_STEPS`: Invite Members, Upload Documents, Run Questionnaire, Review Audits, Export Report, Invite Reviewer
- [x] `deriveCompletedSteps()` auto-computes progress from live stats
- [x] Dashboard shows checklist with `scopeId={orgId}` and `derivedFrom` live stats
- [x] Checklist hidden after all steps complete or dismissed

#### Part 2 — Multi-Step Run Wizard with Stepper

- [x] `WizardStepper` component with 5 steps: Select Project → Upload Questionnaire → Confirm & Start → Analysis → Review & Export
- [x] `wizardStep: WizardStepId` state drives stepper display
- [x] `handleAnalyze` sets `wizardStep = "progress"` then `"review"` on success, `"upload"` on error
- [x] `handleReset` returns to `"upload"` step
- [x] Stepper rendered above both upload and review cards

#### Part 3 — Enterprise Run Details with ExportGatePanel

- [x] `RunSummaryCards` (6 stats) rendered above legacy 3-card grid on `/runs/[id]`
- [x] `ExportGatePanel` with status breakdown, unreviewed-low warning, confirmation checkbox modal
- [x] `ExportGatePanel` RBAC-gated via `userRole` prop (only `admin`/`owner`/`editor` can export)
- [x] "Open Audit for this Run →" link passes `?run_id=<id>` to filter audit page

#### Part 4 — Improved Audit Review

- [x] `AuditFilterChips` bar with 7 chips and live counts
- [x] `applyAuditChipFilter()` and `computeChipCounts()` pure helper functions
- [x] `BulkActions`: Approve all pending, Reject all pending, Approve all HIGH, Flag all LOW
- [x] Rejection drawer requires non-empty note before submitting
- [x] RBAC-gated action buttons (approve/reject hidden for `viewer` role)
- [x] "Copy citation" button in audit drawer
- [x] Run ID URL param (`?run_id=`) auto-filters table on load

#### Part 5 — Demo Mode

- [x] `isDemoMode()` checks `?demo=1` URL param or `NEXT_PUBLIC_DEMO_MODE=true` env flag
- [x] Full demo dataset: project, 2 documents, 1 run, 5 audits, stats, activity
- [x] Dashboard demo banner (purple) with "Exit Demo" button
- [x] "🧪 Load Demo Workspace" button in dashboard header
- [x] Demo mode populates all dashboard stats/activity/audits from static constants (no API calls)

#### Part 6 — RBAC Permission Guards

- [x] `frontend/lib/rbac.ts` with `OrgRole`, `ROLE_RANK`, all `can*` functions
- [x] `useRBAC(orgId)` hook fetches live role from `memberships` table, falls back to `organizations.owner_id`
- [x] Audit page: action buttons hidden for `viewer` role
- [x] Audit page: bulk actions gated by `canReview`
- [x] Export gate: export button disabled for `viewer` role
- [x] RBAC banner shown on audit page when user is viewer

### Bug Fixes in This Phase

- **`frontend/lib/onboarding.ts`**: `Set` spread (`[...set]`) replaced with `Array.from(set)` to satisfy `tsconfig` target (`es2015` required for Set iteration in Next.js 14)
- **`frontend/components/AuditFilterChips.tsx`**: Removed unused `Badge` import
- **`frontend/components/RunSummaryCards.tsx`**: Removed unused `XCircle` import
- **`frontend/next.config.ts`**: Deleted stale duplicate (was shadowing `next.config.mjs`)

### Test Results (2026-02-27)

```bash

# Frontend build

cd frontend && npm run build

# → ✓ Compiled successfully — 19 routes, 0 type errors

# Frontend unit tests

cd frontend && npm run test

# → 5/5 pass

# Backend unit tests

cd backend && python -m pytest tests/ -q

# → 258/258 pass, 3 warnings

```

| Suite | Count | Status |
|---|---|---|
| Frontend unit | 5/5 | ✅ All pass |
| Backend unit | 258/258 | ✅ All pass |
| Frontend build | 0 errors | ✅ Clean |

---

## Phase 15 — Compliance Intelligence + Institutional Memory

### Backend

#### Part 1 — Institutional Answer Memory

- [x] `backend/scripts/009_compliance_intelligence.sql` — `institutional_answers` table with RLS, unique index on `(org_id, normalized_question_hash)`, `reused_from_memory` column on `run_audits`, `compliance_run_stats` view
- [x] `backend/app/core/institutional_memory.py` — `normalize_question()`, `hash_question()`, `lookup_institutional_answer()`, `store_institutional_answer()`, `confidence_score_to_level()`
- [x] Hash-based lookup before generation in `routes.py` `analyze-excel` endpoint
- [x] `reused_from_memory` flag written to audit row on cache hit
- [x] `"reused_from_memory"` added to `_phase4_cols` stripping set for schema drift safety

#### Part 3 (Backend) — Compliance Health Endpoint

- [x] `GET /runs/compliance-health?org_id=&limit=` endpoint in `endpoints/runs.py`
- [x] Returns: `total_runs`, `total_questions`, `avg_confidence_pct`, `total_approved/rejected/pending`, `total_low/high/medium_conf`, `memory_reuse_count`, `avg_review_turnaround_hours`, `low_conf_trend`
- [x] `_empty_health()` helper prevents 500 on orgs with no run data

### Frontend

#### Part 2 — Question Similarity Detection UI

- [x] "Similar historical answer found" banner in audit drawer (`app/audit/page.tsx`)
- [x] Banner shows when `answer_origin === "reused"` or `reused_from_memory === true`
- [x] Displays `reuse_similarity_score` as a percentage when available
- [x] Purple "Memory" badge in drawer header
- [x] `Brain` icon imported from lucide-react

#### Part 3 — Compliance Health Dashboard

- [x] `frontend/components/ComplianceHealthPanel.tsx` created
- [x] `MetricTile` sub-component (5 tiles: Avg Confidence, Total Approved, Low Confidence, Avg Review Time, Memory Reused)
- [x] `TrendBar` sub-component (green ≤10%, amber 10–20%, red >20%)
- [x] Low-confidence trend chart for last N runs with colour-coded legend
- [x] Loading/error states (silent on error — metrics are enhancement, not critical)
- [x] `ComplianceHealthPanel` wired into `app/dashboard/page.tsx` below Compliance Insights card
- [x] Token stored in dashboard state and passed to panel

#### Part 4 — Risk Highlighting on Run Summary

- [x] `frontend/components/RunRiskPanel.tsx` created
- [x] CRITICAL: >20% low confidence OR >10% rejected (red accent)
- [x] WARNING: >10% low confidence OR any pending (amber accent)
- [x] OK: within all thresholds (green accent)
- [x] Replaces raw amber warning banner on `app/runs/[id]/page.tsx`
- [x] `RunRiskPanel` wired with `total`, `low`, `rejected`, `pending` from `runIntelligence`

#### Part 5 — Run Comparison (Delta Mode)

- [x] `frontend/components/RunComparePanel.tsx` created
- [x] Dropdown lists all other completed runs in the org (excludes current run)
- [x] Calls `GET /api/v1/runs/{id}/compare/{other_id}` via `ApiClient.compareRuns()`
- [x] Summary badges: NEW / MODIFIED / UNCHANGED / REMOVED counts
- [x] Per-row delta display: answer before/after for MODIFIED, NEW/REMOVED labels
- [x] Confidence delta indicators: ↑ improved, ↓ dropped (±5% threshold)
- [x] "Memory" badge when `answer_origin === "reused"`
- [x] `RunComparePanel` wired into `app/runs/[id]/page.tsx` between Export Gate and Audit Trail (COMPLETED/EXPORTED/ANALYZED runs only)

#### API Client

- [x] `ApiClient.getComplianceHealth(orgId, token, limit)` added to `frontend/lib/api.ts`
- [x] `ApiClient.compareRuns(runId, otherId, token)` added to `frontend/lib/api.ts`
- [x] `getComplianceHealth` returns `null` gracefully on non-401 errors

### Tests

#### Backend

- [x] `backend/tests/test_phase15_compliance_intelligence.py` — 57 deterministic tests
- [x] Covers: `normalize_question`, `hash_question`, `confidence_score_to_level`, store/lookup graceful failure, `compute_delta` backward compat, `_empty_health` shape, risk indicator thresholds, run compare summary keys, memory flag logic, confidence boundary coverage, normalization idempotency, hash collision freedom

### Test Results (Phase 15)

```bash

# Backend unit tests

cd backend && python -m pytest tests/ -q

# → 315/315 pass (258 original + 57 Phase 15)

# Frontend build

cd frontend && npm run build

# → ✓ Compiled successfully — 0 type errors

# Frontend unit tests

cd frontend && npm run test

# → 5/5 pass

```

| Suite | Count | Status |
|---|---|---|
| Backend unit | 315/315 | ✅ All pass |
| Frontend unit | 5/5 | ✅ All pass |
| Frontend build | 0 errors | ✅ Clean |

---

## Phase 16: Institutional Memory Governance + Compliance Activity Timeline

### Backend

#### Part 1 — Database Migration

- [x] `backend/scripts/010_institutional_memory_governance.sql` — adds `is_active`, `edited_by`, `edited_at` to `institutional_answers`
- [x] `activity_log` table created with `id`, `org_id`, `user_id`, `action_type`, `entity_type`, `entity_id`, `metadata`, `created_at`
- [x] Indexes: `activity_log_org_idx` on `org_id`, `activity_log_created_idx` on `created_at DESC`
- [x] RLS policy `activity_log_org_member` — org members can read/insert, admin/owner only delete

#### Part 2 — `log_activity_event()` Core Function

- [x] `backend/app/core/audit_events.py` — `log_activity_event()` added alongside `log_audit_event()`
- [x] Writes to `activity_log` table (not `audit_events`) — separate timeline for Phase 16 UI
- [x] No-ops gracefully: returns when `supabase=None`, `org_id=""`, or `action_type=""`
- [x] Handles missing-table error with a one-time warning log (never raises)
- [x] Handles generic DB errors silently (never raises)
- [x] Payload includes: `org_id`, `user_id`, `action_type`, `entity_type`, `entity_id`, `metadata`

#### Part 3 — Institutional Memory CRUD Endpoints

- [x] `GET /runs/institutional-answers?org_id=` — paginated list with `is_active`, `edited_by`, `edited_at` fields
- [x] `PATCH /runs/institutional-answers/{id}` — edits `canonical_answer`, `confidence_level`, `is_active`; sets `edited_by`/`edited_at`; logs to both `audit_events` and `activity_log`
- [x] `DELETE /runs/institutional-answers/{id}` — admin/owner only (RBAC enforced); logs to both tables
- [x] `POST /runs/institutional-answers/promote` — saves edited audit answer as embedding via `_store_approved_embedding`; logs `memory_promoted` to both tables

#### Part 4 — Compliance Activity Timeline Endpoint

- [x] `GET /runs/activity?org_id=&limit=&offset=&filter_type=` — reads from `activity_log`
- [x] Supports filter by `action_type` category
- [x] Returns empty list gracefully if table missing (no 500)

#### Part 5 — Activity Triggers Coverage

- [x] `project_created` — logged on `POST /runs/projects`
- [x] `export_downloaded` — logged on `GET /runs/{id}/export`
- [x] `audit_approved` / `audit_rejected` — logged on `PATCH /{run_id}/audits/{id}/review`
- [x] `bulk_audit_approved` / `bulk_audit_rejected` — logged on `POST /{run_id}/audits/bulk-review`
- [x] `memory_edited` — logged on `PATCH /runs/institutional-answers/{id}`
- [x] `memory_deleted` — logged on `DELETE /runs/institutional-answers/{id}`
- [x] `memory_promoted` — logged on `POST /runs/institutional-answers/promote`

#### Part 6 — Compliance Health Score

- [x] `get_compliance_health` in `runs.py` returns `health_score` (0–100)
- [x] Score: 50 pts approval density + 30 pts avg confidence – low-conf penalty, clamped to [0, 100]
- [x] `_empty_health()` returns `health_score: 0` for empty orgs

### Frontend

#### Part 1 — Institutional Memory Management Panel

- [x] `frontend/components/settings/MemoryGovPanel.tsx` — full CRUD management grid
- [x] Columns: Question/Source, Canonical Answer, Status (Active/Disabled), Actions
- [x] Inline edit with Save/Cancel buttons; PATCH endpoint called on save
- [x] Enable/Disable toggle via `is_active` PATCH
- [x] Delete button — shows confirmation; fails gracefully with toast if insufficient permissions
- [x] Confidence level badge; "Edited" badge when `edited_by` is set
- [x] Wired into `app/settings/page.tsx` under "Inst. Memory" tab

#### Part 2 — Audit Drawer Reuse Transparency

- [x] `app/audit/page.tsx` — purple reuse hint block shown when `answer_origin === "reused"` or `reuse_similarity_score` present
- [x] Shows similarity percentage and institutional answer ID (first 8 chars)
- [x] "Promote to Memory" button in `SheetFooter` — calls `POST /api/v1/runs/institutional-answers/promote`
- [x] Button only shown when answer has been edited (differs from original); requires `canReview` role

#### Part 3 — Compliance Activity Timeline Page

- [x] `frontend/app/activity/page.tsx` — real-time compliance event feed
- [x] Calls `GET /api/v1/runs/activity` (correct path, no broken `ApiClient.baseUrl`)
- [x] Filter dropdown using native `<Select>` component: All / Document / Run / Audit / Memory events
- [x] Per-event: icon, formatted action name, locale date, entity badges, metadata preview
- [x] Empty state and loading spinner
- [x] Uses `PageHeader` with correct `title`/`subtitle`/`actions` props

#### Part 4 — Health Score on Dashboard

- [x] `frontend/components/ComplianceHealthPanel.tsx` — displays `health_score` as 0–100 top-level card
- [x] Score sourced from `GET /runs/compliance-health` response

### Tests

#### Backend — `test_phase16_governance.py` (26 tests)

- [x] Tests 01–10: `log_activity_event` — import, no-op guards, error resilience, payload shape, metadata/entity defaults
- [x] Tests 11–13: Endpoint payload validation — allowed PATCH fields, `MemoryPromotePayload` model, confidence level enum
- [x] Tests 14–19: Migration SQL content — file exists, all columns present, indexes, RLS policy
- [x] Tests 20–24: Health score logic — field presence, 0–100 range, high-approval → high score, rejection penalty, empty org → 0
- [x] Test 25: `MemoryGovPanel.tsx` file exists on disk

#### Phase 15 Regression Fix

- [x] `TestComplianceHealthEmpty::test_empty_health_has_all_keys` — updated to use `<=` subset check; `health_score` added by Phase 16 no longer breaks it

### Test Results (Phase 16)

```bash

# Backend unit tests

cd backend && python -m pytest tests/ -q

# → 341/341 pass (315 Phase 1–15 + 26 Phase 16)

# Frontend TypeScript check

cd frontend && npx tsc --noEmit

# → 0 errors

# Frontend build

cd frontend && npm run build

# → ✓ Compiled successfully — 0 type errors

```

| Suite | Count | Status |
|---|---|---|
| Backend unit | 341/341 | ✅ All pass |
| Frontend TS | 0 errors | ✅ Clean |
| Frontend build | 0 errors | ✅ Clean |

---

## Phase 17: Evidence Vault + Immutable Audit Export

### Automated Tests (Deterministic — no DB/API needed)

```bash
cd backend && python -m pytest tests/test_phase17_evidence_vault.py -v
```

**40 tests covering:**

| #   | Category         | Test                                              | Proves                                                       |
|-----|-----------------|---------------------------------------------------|--------------------------------------------------------------|
| 1   | MigrationSQL    | `file_exists`                                     | SQL file on disk                                             |
| 2   | MigrationSQL    | `is_locked_column`                                | `is_locked boolean` added to `runs`                          |
| 3   | MigrationSQL    | `run_evidence_records_table`                      | Table created                                                |
| 4   | MigrationSQL    | `primary_columns`                                 | `run_id`, `org_id`, `generated_by` present                   |
| 5   | MigrationSQL    | `hash_score_size_columns`                         | `sha256_hash`, `health_score`, `package_size` present        |
| 6   | MigrationSQL    | `created_at_column`                               | `created_at` column defined                                  |
| 7   | MigrationSQL    | `run_idx`                                         | `run_evidence_run_idx` index                                 |
| 8   | MigrationSQL    | `org_idx`                                         | `run_evidence_org_idx` index                                 |
| 9   | MigrationSQL    | `rls_enabled`                                     | RLS enabled on table                                         |
| 10  | MigrationSQL    | `read_policy`                                     | `evidence_read_org_member` SELECT policy                     |
| 11  | MigrationSQL    | `insert_policy`                                   | `evidence_insert_member` INSERT policy                       |
| 12  | MigrationSQL    | `delete_policy`                                   | `evidence_delete_admin` DELETE restricted to admin/owner     |
| 13  | Helpers         | `sha256_bytes_importable`                         | `_sha256_bytes` callable                                     |
| 14  | Helpers         | `sha256_bytes_deterministic`                      | Same input → same output                                     |
| 15  | Helpers         | `sha256_bytes_correct_length`                     | 64-char lowercase hex                                        |
| 16  | Helpers         | `compute_health_score_importable`                 | `_compute_health_score_for_audits` callable                  |
| 17  | HealthScore     | `empty_list`                                      | Empty audits → 0                                             |
| 18  | HealthScore     | `all_approved_high`                               | 10×approved HIGH → score ≥ 70                                |
| 19  | HealthScore     | `all_low_unreviewed`                              | 10×pending LOW → score < 50                                  |
| 20  | HealthScore     | `clamped`                                         | Score always ∈ [0, 100]                                      |
| 21  | HealthScore     | `mixed_intermediate`                              | 5×high + 5×low → valid [0, 100]                              |
| 22  | Endpoints       | `generate_evidence_package_importable`            | Endpoint callable                                            |
| 23  | Endpoints       | `list_evidence_records_importable`                | Per-run list callable                                        |
| 24  | Endpoints       | `list_project_evidence_records_importable`        | Org-wide list callable                                       |
| 25  | Endpoints       | `delete_evidence_record_importable`               | Delete callable                                              |
| 26  | Endpoints       | `unlock_run_importable`                           | Unlock callable                                              |
| 27  | Models          | `run_update_has_is_locked`                        | `RunUpdate.is_locked` field present                          |
| 28  | Models          | `run_has_is_locked`                               | `Run.is_locked` field present                                |
| 29  | ZIPStructure    | `contains_audit_log`                              | `audit_log.json` in ZIP                                      |
| 30  | ZIPStructure    | `contains_summary`                                | `summary.json` in ZIP                                        |
| 31  | ZIPStructure    | `contains_memory_reuse`                           | `memory_reuse.json` in ZIP                                   |
| 32  | ZIPStructure    | `contains_activity`                               | `activity.json` in ZIP                                       |
| 33  | ZIPStructure    | `summary_has_integrity_block`                     | `summary.json` → `integrity.audit_log_sha256` present        |
| 34  | ZIPStructure    | `audit_log_hash_matches_summary`                  | Hash in summary == `sha256(audit_log.json)` — tamper-evident |
| 35  | ApiClient       | `generateEvidence_method_exists`                  | `api.ts` has `generateEvidence`                              |
| 36  | ApiClient       | `listRunEvidenceRecords_method_exists`            | `api.ts` has `listRunEvidenceRecords`                        |
| 37  | ApiClient       | `listOrgEvidenceRecords_method_exists`            | `api.ts` has `listOrgEvidenceRecords`                        |
| 38  | ApiClient       | `deleteEvidenceRecord_method_exists`              | `api.ts` has `deleteEvidenceRecord`                          |
| 39  | ApiClient       | `unlockRun_method_exists`                         | `api.ts` has `unlockRun`                                     |
| 40  | Frontend        | `evidence_page_file_exists`                       | `evidence/page.tsx` on disk                                  |

### Database Migration

Run before first use:
```sql
-- In Supabase SQL Editor:
-- backend/scripts/011_evidence_vault.sql
```

### Backend

#### Part 1 — Evidence Package Generation

- [x] `POST /{run_id}/generate-evidence` — builds ZIP (audit_log.json, memory_reuse.json, activity.json, summary.json, optional export.xlsx)
- [x] SHA-256 hash of `audit_log.json` embedded in `summary.json` integrity block
- [x] Package-level hash = sha256(audit_log_hash + excel_hash) persisted to `run_evidence_records`
- [x] Run locked (`is_locked=True`) on evidence generation
- [x] `X-Evidence-Hash` and `X-Health-Score` response headers
- [x] `evidence_generated` logged to `activity_log`
- [x] `_compute_health_score_for_audits()` reusable helper
- [x] `_sha256_bytes()` helper

#### Part 2 — Evidence Records CRUD

- [x] `GET /{run_id}/evidence-records` — list records for a run
- [x] `GET /evidence-records?org_id=&project_id=` — org-wide list, enriched with run filename data
- [x] `DELETE /evidence-records/{record_id}` — admin/owner only; `evidence_deleted` logged
- [x] `POST /{run_id}/unlock` — admin/owner only; `run_unlocked` logged

#### Part 3 — Model Updates

- [x] `RunUpdate.is_locked: Optional[bool]` added
- [x] `Run.is_locked: Optional[bool] = False` added

### Frontend

#### Part 1 — Evidence Vault Page

- [x] `app/projects/[orgId]/[projectId]/evidence/page.tsx` — full evidence records table
- [x] Columns: Run ID (linked), Generated At, Health score badge, Size, SHA-256 hash (truncated + copy button), Actions
- [x] Summary cards: package count, avg health score, total size
- [x] Admin/Owner delete with confirmation dialog (shows run ID, truncated hash, generated date)
- [x] Refresh button; loading spinner; empty state
- [x] Accessible via "Evidence Vault" tab on project detail page

#### Part 2 — Run Detail Lock Banner

- [x] `app/runs/[id]/page.tsx` — blue lock banner when `run.is_locked === true`
- [x] Banner shows: lock icon, copy of evidence hash (if just generated), admin-only "Unlock Run" button
- [x] Unlock handler calls `ApiClient.unlockRun()` → optimistic state update + toast

#### Part 3 — Generate Evidence Button

- [x] "Generate Evidence" button in PageHeader actions for completed runs
- [x] Triggers `ApiClient.generateEvidence()` → blob download + toast with SHA-256 hash prefix
- [x] Button disabled while generating (spinner) and when run is locked
- [x] `LockOpen` icon used for unlock; `Shield` icon for generate

#### Part 4 — Locked Edit Prevention

- [x] Audit table Edit buttons disabled when `run.is_locked === true`
- [x] Lock icon shown in cell instead of "Edit" text when locked
- [x] Tooltip: "Run is locked — unlock to edit"

#### Part 5 — Project Detail Evidence Tab

- [x] New "Evidence Vault" tab added to `projects/[orgId]/[projectId]/page.tsx`
- [x] Tab shows description + deep link to `/projects/{orgId}/{projectId}/evidence`
- [x] `Lock` icon imported for tab trigger

### Test Results (Phase 17)

```bash

# Backend unit tests

cd backend && python -m pytest tests/ -q

# → 381/381 pass (341 Phase 1–16 + 40 Phase 17)

```

| Suite | Count | Status |
|---|---|---|
| Backend unit | 381/381 | ✅ All pass |
| Frontend TS | 0 errors | ✅ Clean |

---

## Phase 21 — SOC2 Readiness Foundations

### Summary

Phase 21 establishes SOC2 Type II compliance foundations across seven areas:
role-based access audit, immutable activity log protection, data retention
controls, access audit report export, password & auth hardening, vendor
disclosure page, and comprehensive test coverage.

### Backend

#### Part 1 — Role-Based Access Audit (`app/core/rbac.py`)

- [x] Viewer cannot: approve answers, edit answers, run analysis, delete documents, upload documents, unlock runs, manage members
- [x] Reviewer can: review answers, bulk review, export runs
- [x] Reviewer cannot: delete documents, edit answers, manage org settings, manage members
- [x] Compliance Manager: full project lifecycle + review permissions
- [x] Owner and Admin: all permissions (identical sets)
- [x] Unknown roles get empty permission sets
- [x] Legacy `manager` alias normalized to `compliance_manager`

#### Part 2 — Immutable Activity Log Protection

- [x] `AUDIT_IMMUTABLE = True` flag in `audit_events.py`
- [x] Migration SQL: `BEFORE DELETE` trigger on `activity_log` (raises exception)
- [x] Migration SQL: `BEFORE UPDATE` trigger on `activity_log` (raises exception)
- [x] Migration SQL: `BEFORE DELETE` trigger on `audit_events` (raises exception)
- [x] Migration SQL: `BEFORE UPDATE` trigger on `audit_events` (raises exception)
- [x] `created_at SET NOT NULL` on both tables
- [x] No API endpoint exposes PUT/PATCH/DELETE on `activity_log` or `audit_events`
- [x] `log_audit_event()` and `log_activity_event()` are best-effort, never-raise

#### Part 3 — Data Retention Controls (`app/core/retention.py`)

- [x] `DATA_RETENTION_DAYS = 365` config setting (configurable via env var)
- [x] `get_retention_cutoff()` — returns datetime threshold
- [x] `run_retention_job(supabase_admin, org_id, dry_run)` — soft-deletes old runs
- [x] Evidence vault (`evidence_records`) never touched by retention job
- [x] `POST /api/v1/admin/run-retention-job` — admin/owner only endpoint
- [x] Retention events logged to `activity_log`
- [x] Migration adds `retention_deleted_at` and `retained_until` columns to `runs`

#### Part 4 — Access Audit Report Export (`app/api/endpoints/admin.py`)

- [x] `GET /api/v1/orgs/{org_id}/access-report` — JSON format (default)
- [x] `GET /api/v1/orgs/{org_id}/access-report?format=csv` — CSV download
- [x] Report includes: user_id, email, full_name, role, member_since, last_activity, activity_count, evidence_exports
- [x] Admin/owner only access enforcement
- [x] Report generation logged to `activity_log`
- [x] Frontend: "Download CSV" and "Download JSON" buttons in Settings → Security & Compliance tab
- [x] `ApiClient.getAccessReport()`, `ApiClient.downloadAccessReportCSV()`, `ApiClient.triggerRetentionJob()` added to `lib/api.ts`

#### Part 5 — Password & Auth Hardening

- [x] `AUTH_MIN_PASSWORD_LENGTH = 10` config setting (≥ 8 per SOC2)
- [x] `AUTH_REQUIRE_EMAIL_VERIFICATION = True` config setting
- [x] `EmailVerificationBanner` component — shows warning when email unverified
- [x] Banner includes "Resend Email" button
- [x] Banner mounted in `layout.tsx` (global)

#### Part 6 — Vendor Disclosure Page (`frontend/app/security/page.tsx`)

- [x] Vendor disclosure table with: Supabase, OpenAI, Stripe, Sentry, Vercel
- [x] Each vendor includes: service name, purpose, data shared
- [x] RBAC section added to practices grid
- [x] Authentication hardening section added to practices grid
- [x] Trust summary badges: SOC 2 aligned, encryption, zero training, audit trail, tenant isolation, immutable logs, RBAC enforced

### Bug Fixes in This Phase

- **`frontend/components/ComplianceHealthPanel.tsx`**: Fixed double `/api/v1` prefix — URL was `/api/v1/runs/compliance-health` but `ApiClient.fetch()` already prepends `API_BASE` (`/api/v1`). Changed to `/runs/compliance-health`.
- **`backend/app/api/endpoints/runs.py`**: Fixed route shadowing — `GET /{run_id}` catch-all at line 567 was intercepting all static-prefix GET routes declared after it (`/compliance-health`, `/institutional-answers`, `/activity`, `/evidence-records`). Moved all static routes before the `/{run_id}` catch-all. Affected requests returned "Run not found or invalid ID" because FastAPI matched e.g. `run_id="compliance-health"`.

### Migration

```sql
-- Apply Phase 21 migration:
psql $DATABASE_URL < backend/scripts/014_soc2_readiness.sql
```

### Test Results (Phase 21)

```bash

# Phase 21 tests only

cd backend && venv/bin/python -m pytest tests/test_phase21_soc2_readiness.py -v

# → 65/65 pass

# Full suite

cd backend && venv/bin/python -m pytest tests/ -q

# → 602/602 pass (537 Phase 1–20 + 65 Phase 21)

```

| Suite                | Count   | Status        |
|----------------------|---------|---------------|
| Phase 21 SOC2        | 65/65   | ✅ All pass   |
| Backend total        | 602/602 | ✅ All pass   |
| Frontend TS          | 0 errors| ✅ Clean      |

---

## Phase 22 — Sales Engine + Enterprise Demo Workspace

### Overview

Phase 22 adds the complete sales engine infrastructure for enterprise lead generation, trial conversion optimization, and demo workspace management. All components are non-breaking additions — no existing functionality was modified.

### New Files Created

| File | Purpose |
|------|---------|
| `backend/app/api/endpoints/sales.py` | Sales API endpoints (contact, tracking, analytics, demo reset) |
| `backend/scripts/015_sales_engine.sql` | `sales_leads` table + indexes + RLS policies |
| `backend/tests/test_phase22_sales_engine.py` | 76 deterministic tests covering all Phase 22 features |
| `frontend/app/contact/page.tsx` | Public contact/lead capture page |
| `frontend/app/admin/sales/page.tsx` | Admin-only sales analytics dashboard |
| `frontend/components/EnterpriseContactModal.tsx` | Enterprise inquiry modal (replaces mailto: link) |
| `frontend/components/UpgradeNudge.tsx` | In-app upgrade suggestion panel |
| `frontend/components/TrialBanner.tsx` | Trial countdown banner with upgrade CTA |
| `frontend/components/DemoBanner.tsx` | Demo workspace banner with reset button |

### Modified Files

| File | Change |
|------|--------|
| `backend/app/main.py` | Registered `sales_ep.router` with API_V1_STR prefix |
| `frontend/lib/api.ts` | Added 5 methods: `submitContactForm`, `trackEnterpriseInterest`, `trackTrialEvent`, `getSalesAnalytics`, `resetDemoWorkspace` |
| `frontend/lib/demo-data.ts` | Expanded from 5 → 15 audit entries, added evidence records, health score, extended activity timeline |
| `frontend/components/layout/AppShell.tsx` | Added `/contact` to PUBLIC_ROUTES, mounted DemoBanner + TrialBanner |
| `frontend/app/settings/billing/page.tsx` | Replaced Enterprise mailto: with EnterpriseContactModal |

### Part 1 — Enterprise Demo Workspace

- [x] `demo-data.ts` expanded to 15 audit entries with HIGH/MEDIUM/LOW confidence mix
- [x] Mix of `approved`, `pending`, and `rejected` review statuses
- [x] `DEMO_EVIDENCE_RECORDS` — 2 evidence vault entries with hashes
- [x] `DEMO_HEALTH_SCORE` — overall score (82), risk_breakdown (high/medium/low), reuse_stats, export_gate
- [x] `DEMO_ACTIVITY` expanded to 10 entries (reviews, exports, memory reuse, risk flags)
- [x] `DemoBanner` component — shows "Demo Workspace — Data resets automatically"
- [x] "Reset Demo Data" button calls `POST /admin/demo-reset`
- [x] DemoBanner mounted in AppShell (authenticated area only)
- [x] `POST /admin/demo-reset` endpoint — admin-only, idempotent cleanup + reseed

### Part 2 — Lead Capture + Contact Sales Page

- [x] `/contact` page with form: Company Name, Name, Email, Phone, Company Size, Message
- [x] Public route (no auth required) — added to `PUBLIC_ROUTES` in AppShell
- [x] Form validation: required fields, email format
- [x] Calls `POST /api/v1/contact` via `ApiClient.submitContactForm()`
- [x] Success confirmation with "Thank you" message
- [x] Backend stores lead in `sales_leads` table (best-effort, never fails user-facing form)

### Part 3 — Enterprise Inquiry Trigger

- [x] `EnterpriseContactModal` replaces `mailto:` link on billing page
- [x] Modal displays: "Enterprise plan requires custom onboarding"
- [x] Enterprise features list shown in modal
- [x] "Contact Sales" button → navigates to `/contact`
- [x] "Email Sales" button → `mailto:sales@nyccompliancearchitect.com`
- [x] Tracks `ENTERPRISE_INTEREST` event via `trackEnterpriseInterest()` on click
- [x] Backend logs to `activity_log` + stores in `sales_leads`

### Part 4 — In-App Upgrade Nudges

- [x] `UpgradeNudge` component with `resource` prop (runs/documents/memory/evidence)
- [x] Shows current usage vs. limits when provided
- [x] Highlights what Pro plan unlocks per resource type
- [x] Compact variant for inline use
- [x] Only shown to FREE plan users (hidden for PRO/ENTERPRISE)
- [x] Professional tone — "View Pro Plan" CTA, not aggressive marketing
- [x] Links to `/plans` page

### Part 5 — Sales Analytics Panel

- [x] `/admin/sales` page — admin/owner only access
- [x] Calls `GET /api/v1/admin/sales-analytics`
- [x] Displays: total_leads, enterprise_interest_count, conversion_rate, mrr_estimate
- [x] Subscription breakdown: active_subscriptions, trial_count, paid_count
- [x] Quick insights section with contextual recommendations
- [x] 403 error handling for non-admin users
- [x] Refresh button for live data reload

### Part 6 — Trial Conversion Optimization

- [x] `TrialBanner` component — shows "Trial ends in X days" with urgency levels
- [x] Color coding: blue (>7 days), amber (3-7 days), red (≤3 days)
- [x] "Upgrade Now" CTA button → `/plans`
- [x] Dismissible with X button
- [x] Tracks `TRIAL_STARTED` event once per session (sessionStorage dedup)
- [x] Mounted in AppShell between DemoBanner and main content
- [x] Backend `POST /track/trial-event` accepts TRIAL_STARTED, TRIAL_CONVERTED, TRIAL_EXPIRED

### Part 7 — Test Suite + Verification

- [x] `test_phase22_sales_engine.py` — 76 deterministic tests
- [x] Tests cover: endpoints, models, constants, migration, registration, frontend components, demo data, API client, subscriptions
- [x] All tests pass without DB/API/external calls
- [x] No breaking changes to existing 602 tests

### Migration

```sql
-- Apply Phase 22 migration:
psql $DATABASE_URL < backend/scripts/015_sales_engine.sql
```

### Test Results (Phase 22)

```bash
# Phase 22 tests only
cd backend && venv/bin/python -m pytest tests/test_phase22_sales_engine.py -v
# → 76/76 pass

# Full suite
cd backend && venv/bin/python -m pytest tests/ -q
# → 678/678 pass (602 Phase 1–21 + 76 Phase 22)
```

| Suite                | Count   | Status        |
|----------------------|---------|---------------|
| Phase 22 Sales       | 76/76   | ✅ All pass   |
| Backend total        | 678/678 | ✅ All pass   |
| Frontend TS          | 0 errors| ✅ Clean      |

---

## Phase 23: Production Hardening + Security Cleanup

### Part 1 — RLS Security Hardening

- [x] Audited all `USING (true)` policies — all 4 instances are legitimate `service_role` bypass
- [x] Dropped overly-permissive `anon_insert_sales_leads` policy (was `WITH CHECK (true)`)
- [x] Replaced with `anon_insert_sales_leads_restricted` — restricts source values, requires email or company_name
- [x] Added explicit `anon_deny_select_sales_leads` — anonymous cannot read leads
- [x] Added explicit `anon_deny_update_sales_leads` — anonymous cannot modify leads
- [x] Added explicit `anon_deny_delete_sales_leads` — anonymous cannot delete leads
- [x] Documented leaked password protection (Supabase Auth config)
- [x] Documented vector extension schema isolation best practice
- [x] Added `idx_sales_leads_email_created` composite index for rate-limit-friendly queries
- [x] RLS verified: all tenant tables enforce `org_id` membership checks

### Part 2 — Audit 400/404 Logs + Structured Error Codes

- [x] Error handler maps all HTTP statuses to structured `error` codes (400→bad_request, 401→unauthorized, 403→forbidden, 404→not_found, 429→rate_limited, 500→internal_error, 503→service_unavailable)
- [x] All error responses include `error`, `message`, and `request_id` fields
- [x] No billing endpoint returns 400 on valid state
- [x] All /api/v1 endpoints have auth guards (except intentionally public `/contact`)
- [x] All 404s are intentional (no missing route handlers)

### Part 3 — Rate Limiting Production Mode

- [x] `contact_limiter` added — 5 requests per 300s per client IP
- [x] `auth_limiter` added — 20 requests per 300s per client IP
- [x] `get_client_ip()` helper extracts IP from `X-Forwarded-For` or `client.host`
- [x] `RATE_LIMIT_CONTACT` config setting (default: 5)
- [x] `RATE_LIMIT_AUTH` config setting (default: 20)
- [x] `POST /contact` rate-limited via `contact_limiter` by client IP
- [x] Export endpoint protected via existing `export_limiter`
- [x] Rate limit 429 responses include `Retry-After` header

### Part 4 — Dev Mode Banner in Production

- [x] `DevBanner` component checks `config.isProd` and returns `null` in production
- [x] `config.ts` sets `isProd = environment === "production"` based on `NODE_ENV`
- [x] No additional changes needed — already correctly implemented

### Part 5 — Health Monitoring Endpoint

- [x] `GET /health/full` — comprehensive production monitoring endpoint
- [x] Checks: database connectivity (with latency), Stripe status, vector search (pgvector/chunks), queue health
- [x] Returns: `status` (healthy/degraded), `version`, `environment`, `checks`, `latency`, `errors`, `timestamp`
- [x] Returns 503 with degraded status if any check fails
- [x] Existing `/health` and `/health/ready` endpoints preserved

### Part 6 — Test Suite + Verification

- [x] `test_phase23_production_hardening.py` — 60 deterministic tests
- [x] Tests cover: RLS migration, error codes, rate limiting, config, DevBanner, /health/full, VERIFY.md
- [x] All tests pass without DB/API/external calls
- [x] No breaking changes to existing 678 tests

### Security Checklist

- [x] RLS verified — all `USING (true)` are `service_role` only
- [x] Security advisor clean — no public write endpoints without rate limits
- [x] Rate limiting active — contact form, auth, export, analysis endpoints throttled
- [x] No public write endpoints — only `POST /contact` (rate-limited, column-restricted)
- [x] Production banner hidden — `DevBanner` returns null when `NODE_ENV=production`
- [x] Leaked password protection documented (Supabase Auth config)
- [x] Structured error codes on all HTTP status responses

### Migration

```sql
-- Apply Phase 23 migration:
psql $DATABASE_URL < backend/scripts/016_production_hardening_rls.sql
```

### Test Results (Phase 23)

```bash
# Phase 23 tests only
cd backend && venv/bin/python -m pytest tests/test_phase23_production_hardening.py -v
# → 60/60 pass

# Full suite
cd backend && venv/bin/python -m pytest tests/ -q
# → 738/738 pass (678 Phase 1–22 + 60 Phase 23)
```

| Suite                     | Count   | Status        |
|---------------------------|---------|---------------|
| Phase 23 Hardening        | 60/60   | ✅ All pass   |
| Backend total             | 738/738 | ✅ All pass   |
| Frontend TS               | 0 errors| ✅ Clean      |

---

## Phase 24 — Marketing Site Rewrite

### Overview

Complete rewrite of the public marketing homepage (`/`) with 6 structured sections,
modular component architecture, enterprise tone, and no hype language.

### Part 1 — Hero Section

- [x] `HeroSection.tsx` — outcome-driven headline ("Submit compliance questionnaires in hours, not weeks")
- [x] Pain-focused subheadline referencing manual spreadsheet copy-paste workflows
- [x] Dual CTAs: "Request a Demo" (→ `/contact`) + "Start Free Trial" (→ `/signup`)
- [x] Trust signals: no credit card, SOC 2 aligned, audit-ready

### Part 2 — Problem Section

- [x] `ProblemSection.tsx` — four enterprise pain points addressed
- [x] Manual questionnaire chaos — re-keying across Excel tabs
- [x] Version control nonexistent — expired certs and outdated manuals
- [x] Audit exposure — unsourced answers create liability
- [x] Time waste — 30–40 hours per questionnaire cycle

### Part 3 — Solution Section

- [x] `SolutionSection.tsx` — five platform capabilities
- [x] Auto-answer engine — AI maps questions and retrieves evidence
- [x] Confidence scoring — reviewers focus on low-confidence items
- [x] Evidence vault — versioned, searchable document repository
- [x] Full audit trail — source document, page number, reviewer approval
- [x] Export-ready compliance — SCA, MTA, PASSPort formatted Excel files

### Part 4 — Social Proof (Case Study Templates)

- [x] `SocialProofSection.tsx` — three anonymized case study template blocks
- [x] Each block: quote, role, company type, key metric
- [x] Covers SCA, MTA, and PASSPort use cases
- [x] Anonymization disclaimer included

### Part 5 — Pricing Overview

- [x] `PricingSection.tsx` — three tiers with clear differentiation
- [x] Starter ($149/mo) — 3 projects, 50 exports, email support
- [x] Growth ($499/mo) — 15 projects, 250 exports, RBAC, priority support (Most Popular)
- [x] Enterprise (Custom) — unlimited, SSO, audit API, dedicated CSM, custom SLA

### Part 6 — Enterprise CTA + Trust Bar

- [x] `EnterpriseCTASection.tsx` — "Book Compliance Strategy Call" CTA
- [x] Trust bar: end-to-end encryption, SOC 2, no data training, 99.9% uptime SLA

### Architecture

- [x] 6 modular components in `frontend/components/marketing/`
- [x] Barrel export via `index.ts`
- [x] `page.tsx` imports all sections from `@/components/marketing`
- [x] Navigation and footer preserved in `page.tsx`
- [x] Authenticated users still redirect to `/dashboard`
- [x] All components use existing shadcn/ui primitives (Button, Card, Badge)
- [x] Design tokens: HSL CSS variables, Tailwind utility classes

### Design Compliance

- [x] Enterprise tone — compliance, audit, evidence vocabulary
- [x] Minimal style — no excessive exclamation marks (≤ 2 total)
- [x] No hype language — no "revolutionary", "game-changing", "disruptive", etc.
- [x] Serious, restrained copy appropriate for construction/procurement audience

### Test Suite + Verification

- [x] `test_phase24_marketing_site.py` — 60 deterministic tests
- [x] Tests cover: all 6 sections, barrel export, page wiring, tone validation, VERIFY.md
- [x] All tests pass without DB/API/external calls
- [x] No breaking changes to existing 738 tests

### Test Results (Phase 24)

```bash
# Phase 24 tests only
cd backend && venv/bin/python -m pytest tests/test_phase24_marketing_site.py -v
# → 60/60 pass

# Full suite
cd backend && venv/bin/python -m pytest tests/ -q
# → 798/798 pass (738 Phase 1–23 + 60 Phase 24)
```

| Suite                     | Count   | Status        |
|---------------------------|---------|---------------|
| Phase 24 Marketing Site   | 60/60   | ✅ All pass   |
| Backend total             | 798/798 | ✅ All pass   |
| Frontend TS               | 0 errors| ✅ Clean      |

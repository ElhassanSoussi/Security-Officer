# QA Checklist — NYC Compliance Architect

Quick manual test to verify all core flows work before any release.

## Pre-Requisites

- [ ] Backend running on `http://localhost:8000`
- [ ] Frontend running on `http://localhost:3001`
- [ ] `SUPABASE_SERVICE_ROLE_KEY` set in environment
- [ ] `OPENAI_API_KEY` set in environment

## Auth

- [ ] Navigate to `/login` — login form renders
- [ ] Login with valid credentials — redirect to Dashboard
- [ ] Navigate to `/signup` — signup form renders
- [ ] Logout — redirect to `/login`

## Dashboard (`/`)

- [ ] Stat cards show loading skeleton, then real numbers
- [ ] Recent Activity section shows entries or "No recent activity" empty state
- [ ] "Manage Projects" button navigates to `/projects`
- [ ] "Start New Run" button navigates to `/run`

## Organizations (`/orgs`)

- [ ] Orgs list loads correctly
- [ ] "Create Organization" — dialog opens, name validates, org appears in list
- [ ] Selecting an org navigates to `/projects`

## Projects (`/projects`)

- [ ] Projects list loads with skeleton, then cards
- [ ] "New Project" — dialog creates project, card appears
- [ ] Clicking a project navigates to detail page

## Project Detail (`/projects/[orgId]/[projectId]`)

- [ ] **Knowledge Base tab**: shows docs or "No documents found" empty state
- [ ] **Upload Doc**: choose PDF → upload succeeds → document appears in list
- [ ] **Upload Doc (error)**: upload non-PDF → shows error toast
- [ ] **Org Vault**: displays shared documents or empty state
- [ ] **Run Questionnaire tab**: RunWizard loads
- [ ] **Runs History tab**: shows run rows or empty state

## Run Questionnaire (`/run` or project tab)

- [ ] Upload `.xlsx` file — "Analyze" button becomes enabled
- [ ] Click Analyze — spinner shown, results appear in ReviewGrid
- [ ] Edit an answer — "edited" badge appears
- [ ] Click Export — file downloads as `.xlsx`
- [ ] Toast notification on success/failure

## Runs History (`/runs`)

- [ ] Table shows all runs with status badges
- [ ] "Details" button navigates to `/runs/[id]`
- [ ] Download button appears for EXPORTED runs

## Run Details (`/runs/[id]`)

- [ ] Run metadata (status, file, dates) displays
- [ ] Audit trail table shows questions/answers
- [ ] Download button works

## Plans & Billing (`/plans`)

- [ ] Plans page loads with Starter/Growth/Elite cards
- [ ] Current plan badge is visible
- [ ] Export usage counter is accurate

## Error Handling

- [ ] Stop backend → pages show error banner (not blank white screen)
- [ ] Invalid org/project ID in URL → error message, not crash
- [ ] Expired session → redirect to `/login`

## Smoke Test

- [ ] Run `bash backend/scripts/smoke_test.sh` — all checks pass

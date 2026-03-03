# New Customer Onboarding Guide

This app includes a lightweight, modern onboarding guide for **first-time organizations**.
It is **not** a wizard. It uses a compact banner/card that points the user to the next step.

## Data Model

Supabase table: `organizations`

Columns added:
- `onboarding_completed boolean NOT NULL DEFAULT false`
- `onboarding_step integer NOT NULL DEFAULT 1` (bounded to **1..5**)

Migration:
- `backend/scripts/018_org_onboarding.sql`

## Backend API

All endpoints require `Authorization: Bearer <jwt>`.

- `GET /api/v1/org/onboarding`
  - Response: `{ "onboarding_completed": boolean, "onboarding_step": number }`

- `PATCH /api/v1/org/onboarding`
  - Body: `{ "onboarding_completed"?: boolean, "onboarding_step"?: number }`
  - Validation: `onboarding_step` must be 1..5

- `GET /api/v1/org/metrics`
  - Response: `{ documents_count, projects_count, runs_count, reviewed_count, exports_count }`
  - Used only for deterministic step-completion checks.

## Frontend UX

- Dashboard:
  - Shows `OnboardingGuide` when onboarding is incomplete.
  - If user clicks "Skip for now", the guide hides and a subtle "Next step" card persists on Dashboard until onboarding completes.

- Relevant pages:
  - Projects page shows a small banner for step 2.
  - Run page shows small banners for steps 3 and 5.
  - Audit page shows a small banner for step 4.

## Step Definitions (must remain simple + deterministic)

1) Upload compliance documents
   - Completed when `documents_count >= 1`

2) Create a project
   - Completed when `projects_count >= 1`

3) Upload questionnaire (Run)
   - Completed when `runs_count >= 1`

4) Review answers
   - Completed when `reviewed_count >= 1` (any `run_audits.review_status` in `approved|rejected`)

5) Export
   - Completed when `exports_count >= 1`
   - Fallback: if export tracking is unavailable, mark complete when user clicks Export and backend returns success.

## Verification Checklist

1. New org (fresh account + org) -> sees Step 1 on Dashboard.
2. Upload a document -> automatically advances to Step 2.
3. Create a project -> advances to Step 3.
4. Run analysis (upload questionnaire) -> advances to Step 4.
5. Approve or reject at least one answer in Audit -> advances to Step 5.
6. Export -> `onboarding_completed=true` and onboarding UI disappears.
7. Existing orgs with `onboarding_completed=true` never see onboarding guide.
8. No console errors and no API 500s during the flow.

# Audit Review

## What this covers

The platform provides two complementary audit surfaces:

- **Audit Review** (`/audit`) — compliance-focused review of questionnaire runs, document status, and pack exports.
- **Activity Log** (`/activity`) — a unified, filterable timeline of every org action: uploads, deletions, project changes, AI assistant interactions, billing events, and more.

## Viewing the audit review

1. Go to `/audit`.
2. Filter by date range, user, or event type.
3. Each entry shows: timestamp, actor (user), action, and affected resource.

## Viewing the activity log

1. Go to `/activity`.
2. Use the filter bar to narrow by **action type**, **user ID**, **project ID**, or **date range**.
3. Click any row's **chevron** to expand inline JSON metadata.
4. Use **Export CSV** to download up to 5 000 rows matching the current filters.

## What is logged

- Document uploads and deletions
- Questionnaire run starts and completions
- Exports downloaded
- Compliance pack creation
- Project creation
- AI assistant interactions (intent + topics only — no message content)
- User role changes
- Billing events
- Settings changes

## Exporting audit records

- **Audit Review** (`/audit`): use the Export button on that page.
- **Activity Log** (`/activity`): use the **Export CSV** button; the download respects all active filters (max 5 000 rows, metadata sanitized).

## Common questions

- **"Why is an action missing?"** — only actions through the platform are logged. Direct database changes are not captured.
- **"Who can see the audit log?"** — Owner and Admin roles can view the full log. Compliance Managers see run-related events.
- **"Is sensitive data included in exports?"** — No. Keys containing `password`, `token`, `secret`, `api_key`, `credential`, `auth`, `bearer`, or `jwt` are automatically stripped from all metadata before storage and export.

## Relevant pages

- Audit Review: `/audit`
- Activity Log: `/activity`
- Settings: `/settings`

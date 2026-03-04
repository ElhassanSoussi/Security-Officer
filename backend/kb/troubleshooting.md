# Troubleshooting

## Common issues and fixes

### Document upload fails

- **"File too large"** -- maximum file size is 10 MB. Split or compress the file.
- **"Invalid file signature"** -- the file may be corrupt. Re-export from its source application.
- **"Storage limit reached"** -- upgrade your plan at `/settings/billing`.
- **"Insufficient permissions"** -- you need Owner, Admin, or Compliance Manager role to upload.

### Run does not start

- **"No documents found"** -- add at least one document to the project before running.
- **"Run limit reached"** -- monthly run limit exceeded. Check usage at `/settings/billing`. Resets on the 1st.
- **"Questionnaire file format not supported"** -- use `.xlsx` or `.csv`.

### Run completes but answers are low quality

- Ensure your documents contain the relevant policy or control text.
- Rephrase questionnaire questions to be more specific.
- Add more documents with supporting evidence.

### Export fails or is missing

- **"Export limit reached"** -- check `/settings/billing` for your remaining exports.
- **"Run not complete"** -- wait for the run to reach "Completed" status before exporting.

### Login / access issues

- **"Unauthorized"** -- your session may have expired. Sign out and sign back in.
- **"Organization not found"** -- contact your organization owner to ensure you have been added.

### Billing issues

- **"Payment failed"** -- update your payment method in the Stripe portal via `/settings/billing` > Manage Billing.
- **"Subscription inactive"** -- your subscription may have lapsed. Reactivate at `/plans`.

## Relevant pages

- Plans & Billing: `/settings/billing`
- Upgrade plan: `/plans`
- Audit log: `/audit`
- Projects: `/projects`

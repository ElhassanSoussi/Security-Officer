# Runs

## What this covers
A "run" is the process of answering a security questionnaire automatically using your uploaded documents.

## Steps to start a run
1. Go to `/run`.
2. Select the **project** whose documents should be used as the knowledge source.
3. Upload a **questionnaire file** (Excel or CSV with questions).
4. Click **Start Run**. The system processes questions and generates answers with citations.
5. When complete, open the run detail to review answers, confidence scores, and gaps.

## Reading run results
- **Answer** — the AI-generated response drawn from your documents.
- **Confidence** — how strongly the answer is supported by your documents.
- **Source** — the document and section the answer is drawn from.
- **Gap** — flagged when no supporting evidence is found.

## Exporting a run
1. Open a completed run.
2. Click **Export to Excel**.
3. A formatted report downloads with all questions, answers, and citations.

## Common errors
- **"No documents found"** — upload documents to the selected project first.
- **"Run limit reached"** — your plan allows a fixed number of runs per month. See `/settings/billing` to upgrade.
- **"File format not supported"** — use `.xlsx` or `.csv` questionnaire files.

## Relevant pages
- Start a run: `/run`
- All runs: `/runs`
- Plans & Billing: `/settings/billing`

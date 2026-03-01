---
name: nyc_compliance_rag
description: Rules and logic for the NYC Compliance RAG pipeline
---

# NYC Compliance RAG Pipeline

This skill defines the strict grounding rules for the NYC Compliance Architect.

## Core Rules

1. **NO HALLUCINATION**:
    * If evidence is not found in the "Company Locker" or "Project" scope for a **COMPANY_FACT**, return "NOT FOUND IN LOCKER".
    * Do NOT use general knowledge to guess.

2. **CITATIONS REQUIRED**:
    * Every answer must have a citation: `[DocumentName.pdf, pg. X]`.
    * Max 3 citations per answer.

3. **GLOBAL FALLBACK (NYC IAW ONLY)**:
    * Only if the question is classified as `NYC_LAW` (not company specific).
    * Use `[NYC REGULATORY REFERENCE: DocName.pdf, pg. X]`.

4. **Question Classification**:
    * `COMPANY_FACT`: Answer ONLY from Locker/Project.
    * `NYC_LAW`: Check Locker first, then NYC Global Library.
    * `AMBIGUOUS`: Return "AMBIGUOUS: [reason]. Need [missing document]."

## Precedence

1. Company Locker + Project Docs
2. NYC Global Library (only for NYC_LAW)
3. NOT FOUND

---
name: excel_automation
description: Instructions for checking Excel questionnaires
---

# Excel Automation for Questionnaires

This skill handles the reading and writing of Excel files for compliance forms.

## Rules

1. **Parsing**:
    * Detect question cells and adjacent answer cells.
    * Map questions to the internal data model.

2. **Writing**:
    * Fill the answer cell with the generated answer.
    * **Audit Tab**: Create a new tab `AI_Verification_Audit`.
        * Columns: `Cell`, `Question`, `Answer`, `Source Doc`, `Confidence`.

3. **Constraints**:
    * Max 255 chars for standard fields.
    * Truncate/compress if necessary, but preserve meaning.
    * "Detailed Description" fields can exceed the limit.

# Operator Guide: NYC Compliance Architect

**Role:** Compliance Officer / Safety Manager
**Objective:** Auto-fill security questionnaires using company documents.

---

## 🚦 Workflow Rules (Engine Frozen)

**Strict Order:**

1. **Step 1: Upload Documents** (Knowledge Base)
2. **Step 2: Upload Questionnaire** (Excel)
3. **Step 3: Review Answers**
4. **Step 4: Export Signed Excel**

🚫 **DO NOT** try to skip Step 1. The system locks Step 2 until knowledge is loaded.

---

## 📂 Required Files

### 1. Company Documents (Step 1)

- **Formats:** `.pdf`, `.docx`
- **Content:** Safety Manuals, HASP, Corporate Policies, Past Applications.
- **Note:** The more specific the document, the better the answers.

### 2. Questionnaire (Step 2)

- **Formats:** `.xlsx`, `.xlsm` (Macros Preserved)
- **Structure:** Questions in one column, empty cells in the next.
- **Note:** The system detects questions based on keywords (`Describes`, `List`, `?`).

---

## 🧠 Understanding Confidence Labels

| Label | Color | Meaning | Action From You |
| :--- | :--- | :--- | :--- |
| **HIGH** | 🟢 Green | Exact match found in your documents. | Quick glance value. |
| **MEDIUM** | 🟡 Yellow | Logical inference or partial match. | **Read carefully.** Edit if nuances are missed. |
| **LOW** | 🔴 Red | **DANGER.** No good match found. | **MUST REVIEW.** Flagged as **Missing source context** (needs_info). |

### ⚠️ Missing Source Context (needs_info)

If the AI cannot find an answer in your uploaded documents, the UI will show:
- **Status:** Missing source context
- **Action:** “Upload supporting docs”
- **Answer:** left blank (no fake placeholders)

**Action:** You must manually type the answer OR upload a document containing that info and restart.

---

## 🕵️ AI Verification Audit Sheet

Every exported Excel file includes a hidden/visible sheet named `AI_Verification_Audit`.
**Do not delete this.** It serves as the digital chain of custody.

**Columns:**

- **Source Document:** Which file provided the answer.
- **Confidence:** AI's certainty level.
- **Finalized By:** "AI" (if untouched) or "User" (if you edited it).

---

## 🛑 When NOT to Submit

Do **NOT** submit the Excel file if:

1. There are **unreviewed LOW confidence** answers.
2. The Audit Sheet shows "NOT FOUND" for critical regulated questions.
3. Formatting (colors/borders) looks corrupted (Report to Engineering).

---

## 🆘 Troubleshooting

- **System Stuck?** Crl+R to reload.
- **"Analysis Failed"?** Ensure your Excel file is not password protected.
- **Wrong Answers?** Check if `05005_Concrete.docx` (or similar) is actually relevant to the question.

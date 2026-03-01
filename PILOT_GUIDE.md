# Pilot Guide: NYC Compliance Architect

**Welcome to the Pilot!** 🚀
This guide explains how to use the "NYC Compliance Architect" to auto-fill your safety questionnaires.

---

## 🛑 Strict Rules for Pilot Users

1. **Do NOT** upload sensitive employee PII (Social Security Numbers, Medical Records) into the Knowledge Base yet.
2. **Do NOT** submit the Excel file without reviewing the **Low Confidence** answers.
3. **DO** report any "Hallucinations" (AI making things up) immediately.

---

## 🚦 How to Run the Tool

### Step 1: Initialize Knowledge Base (One-Time Setup)

1. Click **"1. Upload Docs"**.
2. Enter your **Organization ID** (e.g., `acme-corp`).
3. Upload your company's **Safety Manuals**, **HASP**, **Insurance Certificates**, and **Past Projects**.
    * *Tip:* The more you upload, the smarter the AI gets.
    * *Supported:* PDF, DOCX.

### Step 2: Auto-Fill Questionnaire

1. Click **"2. Questionnaire"** (This unlocks only after Step 1).
2. Upload the **Excel File** (.xlsx) you need to fill appropriately.
3. Click **"Analyze Questionnaire"**.
4. Wait for the AI to think (approx 30-60 seconds for 50 questions).

### Step 3: Review & Verify

The "Review Grid" will appear.

* 🟢 **GREEN (High Confidence):** The AI found an exact match in your docs.
* 🔴 **RED (Low Confidence):** The AI could **NOT** find the answer in your docs.
  * *Action:* You MUST check these. The UI will flag **Missing source context** and keep the answer blank (no placeholders). Upload supporting docs or type the answer manually.

### Step 4: Export Signed Excel

1. Click **"Export Final Excel"**.
2. Open the downloaded file.
3. **Check the `AI_Verification_Audit` Sheet:**
    * This hidden sheet lists exactly *which document* was used for *which answer*.
    * Use this to double-check the AI's work before you send it to the city.

---

## ❓ FAQ

**Q: The answer says "NOT FOUND IN LOCKER". Why?**
A: That legacy phrase is treated as a sentinel internally. In the UI you should see **Missing source context** instead. Upload a document that contains the missing info (e.g., your Tax ID certificate), then re-run.

**Q: Can I edit the answers?**
A: Yes! You can edit them in the web browser before exporting, OR you can edit the final Excel file directly.

**Q: Is my data safe?**
A: Your documents are stored in a secure cloud database allocated to your Organization ID. They are never shared with other companies.

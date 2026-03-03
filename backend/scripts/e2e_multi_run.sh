#!/bin/bash
set -e

# Configuration
API_URL="http://localhost:8000/api/v1"
COOKIE_FILE="cookies.txt"
ORG_NAME="E2E_Test_Org_$(date +%s)"
PROJECT_NAME="E2E_Project_$(date +%s)"
DOC_FILENAME="test_policy.docx"
XLSX_FILENAME="test_questionnaire.xlsx"

# Colors
GREEN='\033[0;32m'
RED='\033[0;31m'
NC='\033[0m'

echo "🚀 Starting multi-run E2E verification..."

# 1. Create Dummy Files
echo "Files > Creating dummy test files..."
echo "This is a test policy document." > $DOC_FILENAME
# Create a valid empty Excel file using python zipfile (standard lib) to avoid pandas dependency
python3 -c "
import zipfile
import os

with zipfile.ZipFile('$XLSX_FILENAME', 'w') as zf:
    # Minimal [Content_Types].xml
    zf.writestr('[Content_Types].xml', '<?xml version=\"1.0\" encoding=\"UTF-8\" standalone=\"yes\"?><Types xmlns=\"http://schemas.openxmlformats.org/package/2006/content-types\"><Default Extension=\"xml\" ContentType=\"application/xml\"/><Default Extension=\"rels\" ContentType=\"application/vnd.openxmlformats-package.relationships+xml\"/><Override PartName=\"/xl/workbook.xml\" ContentType=\"application/vnd.openxmlformats-officedocument.spreadsheetml.sheet.main+xml\"/><Override PartName=\"/xl/worksheets/sheet1.xml\" ContentType=\"application/vnd.openxmlformats-officedocument.spreadsheetml.worksheet+xml\"/></Types>')
    
    # Minimal _rels/.rels
    zf.writestr('_rels/.rels', '<?xml version=\"1.0\" encoding=\"UTF-8\" standalone=\"yes\"?><Relationships xmlns=\"http://schemas.openxmlformats.org/package/2006/relationships\"><Relationship Id=\"rId1\" Type=\"http://schemas.openxmlformats.org/officeDocument/2006/relationships/officeDocument\" Target=\"xl/workbook.xml\"/></Relationships>')
    
    # Minimal xl/workbook.xml
    zf.writestr('xl/workbook.xml', '<?xml version=\"1.0\" encoding=\"UTF-8\" standalone=\"yes\"?><workbook xmlns=\"http://schemas.openxmlformats.org/spreadsheetml/2006/main\" xmlns:r=\"http://schemas.openxmlformats.org/officeDocument/2006/relationships\"><sheets><sheet name=\"Sheet1\" sheetId=\"1\" r:id=\"rId1\"/></sheets></workbook>')
    
    # Minimal xl/_rels/workbook.xml.rels
    zf.writestr('xl/_rels/workbook.xml.rels', '<?xml version=\"1.0\" encoding=\"UTF-8\" standalone=\"yes\"?><Relationships xmlns=\"http://schemas.openxmlformats.org/package/2006/relationships\"><Relationship Id=\"rId1\" Type=\"http://schemas.openxmlformats.org/officeDocument/2006/relationships/worksheet\" Target=\"worksheets/sheet1.xml\"/></Relationships>')
    
    # Minimal xl/worksheets/sheet1.xml (Empty sheet is fine, or simple data)
    zf.writestr('xl/worksheets/sheet1.xml', '<?xml version=\"1.0\" encoding=\"UTF-8\" standalone=\"yes\"?><worksheet xmlns=\"http://schemas.openxmlformats.org/spreadsheetml/2006/main\"><sheetData><row r=\"1\"><c r=\"A1\" t=\"s\"><v>0</v></c><c r=\"B1\" t=\"s\"><v>1</v></c></row></sheetData></worksheet>')

    # Minimal xl/sharedStrings.xml (needed for t='s')
    zf.writestr('xl/sharedStrings.xml', '<?xml version=\"1.0\" encoding=\"UTF-8\" standalone=\"yes\"?><sst xmlns=\"http://schemas.openxmlformats.org/spreadsheetml/2006/main\" count=\"2\" uniqueCount=\"2\"><si><t>Question</t></si><si><t>Answer</t></si></sst>')
"

# 2. Create Org (Note: No trailing slash!)
echo "API > Creating Organization '$ORG_NAME'..."
RESP=$(curl -s -X POST "$API_URL/orgs" -H "Content-Type: application/json" -d "{\"name\": \"$ORG_NAME\"}")
ORG_ID=$(echo $RESP | python3 -c "import sys, json; print(json.load(sys.stdin)['id'])")
echo "✅ Org Created: $ORG_ID"

# 3. Ingest Document
echo "API > Ingesting Document..."
RESP=$(curl -s -X POST "$API_URL/ingest" \
  -F "file=@$DOC_FILENAME" \
  -F "org_id=$ORG_ID" \
  -F "project_id=$PROJECT_NAME" \
  -F "scope=PROJECT")
DOC_ID=$(echo $RESP | python3 -c "import sys, json; print(json.load(sys.stdin)['data']['document_id'])")
echo "✅ Document Ingested: $DOC_ID"

# 4. Analyze Questionnaire (Creates Run)
echo "API > Analyzing Questionnaire..."
RESP=$(curl -s -X POST "$API_URL/analyze-excel" \
  -F "file=@$XLSX_FILENAME" \
  -F "org_id=$ORG_ID" \
  -F "project_id=$PROJECT_NAME")
# Check HTTP Code if needed, but curl -s hides it. Assuming success if JSON parse works.
RUN_ID=$(echo $RESP | python3 -c "import sys, json; print(json.load(sys.stdin)['run_id'])")
if [ "$RUN_ID" == "None" ] || [ -z "$RUN_ID" ]; then
    echo -e "${RED}❌ Analysis Failed or No Run ID returned${NC}"
    exit 1
fi
echo "✅ Analysis Complete. Run ID: $RUN_ID"

# 5. Verify Run Audits Created (Check specific endpoint or inferred via Stats)
# We'll check via Stats first.

# 6. Generate Export (Updates Run to EXPORTED)
# Needed: answers_json. We can pass empty list mocked?
# The endpoint requires valid JSON.
echo "API > Generating Export..."
ANSWERS_JSON='[{"sheet_name":"Sheet1","cell_coordinate":"B1","question":"Q","final_answer":"A","confidence":"HIGH","is_verified":false,"edited_by_user":false,"sources":[],"ai_answer":"A"}]'
curl -s -X POST "$API_URL/generate-excel" \
  -F "file=@$XLSX_FILENAME" \
  -F "answers_json=$ANSWERS_JSON" \
  -F "org_id=$ORG_ID" \
  -F "run_id=$RUN_ID" \
  -o "exported_result.xlsx"
echo "✅ Export Generated"

# 7. Verify Dashboard Stats
echo "API > Fetching Dashboard Stats..."
RESP=$(curl -s -X GET "$API_URL/runs/stats?org_id=$ORG_ID")
echo "Stats Response: $RESP"

ACTIVE_PROJECTS=$(echo $RESP | python3 -c "import sys, json; print(json.load(sys.stdin)['active_projects'])")
DOCS_INGESTED=$(echo $RESP | python3 -c "import sys, json; print(json.load(sys.stdin)['documents_ingested'])")
RUNS_COMPLETED=$(echo $RESP | python3 -c "import sys, json; print(json.load(sys.stdin)['runs_completed'])")

# Assertions
echo "--------------------------------"
echo "Metrics Verification:"

if [ "$ACTIVE_PROJECTS" -ge 1 ]; then
    echo -e "${GREEN}✅ Active Projects: $ACTIVE_PROJECTS (>=1)${NC}"
else
    echo -e "${RED}❌ Active Projects is 0 (Expected >=1)${NC}"
    exit 1
fi

if [ "$DOCS_INGESTED" -ge 1 ]; then
    echo -e "${GREEN}✅ Documents Ingested: $DOCS_INGESTED (>=1)${NC}"
else
    echo -e "${RED}❌ Documents Ingested is 0 (Expected >=1)${NC}"
    exit 1
fi

if [ "$RUNS_COMPLETED" -ge 1 ]; then
    echo -e "${GREEN}✅ Runs Completed: $RUNS_COMPLETED (>=1)${NC}"
else
    echo -e "${RED}❌ Runs Completed is 0 (Expected >=1)${NC}"
    exit 1
fi

echo "--------------------------------"
echo -e "${GREEN}🏆 MULTI-RUN E2E TEST PASSED${NC}"

# Cleanup
rm $DOC_FILENAME $XLSX_FILENAME exported_result.xlsx

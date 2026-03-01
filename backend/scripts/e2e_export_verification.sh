#!/bin/bash

# Configuration
API_URL="http://localhost:8000/api/v1"
TEST_FILE="backend/tests/fixtures/test_questionnaire.xlsx"
EXPORT_OUTPUT="export_result.xlsx"
PYTHON_CMD="/usr/local/opt/python@3.11/Frameworks/Python.framework/Versions/3.11/bin/python3.11"
# Explicitly add the path where pip installed PyJWT for 3.11 if using 3.14 or mixed env
export PYTHONPATH=$PYTHONPATH:/usr/local/lib/python3.11/site-packages

# Load JWT secret from backend .env (never hardcode secrets)
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
BACKEND_ENV="${SCRIPT_DIR}/../.env"
if [ -f "$BACKEND_ENV" ]; then
  JWT_SECRET=$(grep '^SUPABASE_JWT_SECRET=' "$BACKEND_ENV" | cut -d'=' -f2-)
fi
JWT_SECRET="${JWT_SECRET:?Set SUPABASE_JWT_SECRET in backend/.env or environment}"

echo "🧪 Starting E2E Export Verification..."

# 0. Get Auth Token
echo "   - Generating Auth Token..."
TOKEN=$($PYTHON_CMD -c "import jwt; import time; print(jwt.encode({'aud': 'authenticated', 'exp': int(time.time()) + 3600, 'sub': 'test-user-id-e2e', 'email': 'e2e@example.com', 'role': 'authenticated'}, '$JWT_SECRET', algorithm='HS256'))")

if [[ -z "$TOKEN" ]]; then
    echo "❌ Failed to generate token"
    exit 1
fi
echo "     ✅ Token Generated"
AUTH_HEADER="Authorization: Bearer $TOKEN"

# 1. Setup: Create Org
echo "   - Creating Test Organization..."
echo "     DEBUG: Token starts with ${TOKEN:0:10}..."
curl -v -X POST "${API_URL}/orgs" \
    -H "Content-Type: application/json" \
    -H "$AUTH_HEADER" \
    -d '{"name": "Export Test Org"}' > org_response.txt 2> org_curl.log

ORG_RESP=$(cat org_response.txt)
echo "     DEBUG: Org Response Body: $ORG_RESP"
ORG_ID=$(echo $ORG_RESP | grep -o '"id":"[^"]*"' | cut -d'"' -f4)

if [[ -z "$ORG_ID" ]]; then
    echo "❌ Failed to create organization"
    exit 1
fi
echo "     ✅ Org ID: $ORG_ID"

# 2. Simulate Analysis (to get a valid Run ID and Questions)
echo "   - Simulating Analysis Run..."
# We need to upload a file to analyze-excel
if [[ ! -f "$TEST_FILE" ]]; then
    echo "❌ Test file not found at $TEST_FILE"
    echo "     ⚠️ Warning: Test file missing, skipping actual analysis call simulation if file missing."
    exit 1
fi

ANALYZE_RESP=$(curl -s -X POST "${API_URL}/analyze-excel" \
    -F "file=@$TEST_FILE" \
    -F "org_id=$ORG_ID" \
    -F "project_id=test-project")

# Extract Run ID
RUN_ID=$(echo $ANALYZE_RESP | grep -o '"run_id":"[^"]*"' | cut -d'"' -f4)
if [[ -z "$RUN_ID" ]]; then
   # Fallback: manually parse if grep failed or json structure different
   echo "❌ Analysis failed or Run ID missing"
   echo "Response: $ANALYZE_RESP"
   exit 1
fi
echo "     ✅ Run ID: $RUN_ID"

# 3. Test Export (Happy Path)
echo "   - Testing Export Generation..."

# Construct dummy answers JSON matching the QuestionItem schema
ANSWERS='[{"question":"Q1","answer_format":"text","cell_coordinate":"A1","sheet_name":"Sheet1","ai_answer":"A1","final_answer":"A1","confidence":0.9,"sources":[]}]'

curl -s -X POST "${API_URL}/generate-excel" \
    -F "file=@$TEST_FILE" \
    -F "answers_json=$ANSWERS" \
    -F "org_id=$ORG_ID" \
    -F "project_id=test-project" \
    -F "run_id=$RUN_ID" \
    -o "$EXPORT_OUTPUT" -w "%{http_code}" > http_code.txt

HTTP_CODE=$(cat http_code.txt)
if [[ "$HTTP_CODE" != "200" ]]; then
    echo "❌ Export failed with HTTP $HTTP_CODE"
    exit 1
fi

if [[ ! -f "$EXPORT_OUTPUT" ]]; then
     echo "❌ Export file not downloaded"
     exit 1
fi
echo "     ✅ Export Successful (File downloaded)"

# 4. Verify Database State (Runs Updated?)
# We can't easily check DB directly from shell without psql/supabase-cli.
# We CAN check via GET /runs/{run_id} if implemented?
echo "   - Verifying Run Status..."
RUN_DETAILS=$(curl -s "${API_URL}/runs?org_id=$ORG_ID&limit=1")
# Check if status is "EXPORTED"
if echo "$RUN_DETAILS" | grep -q "EXPORTED"; then
    echo "     ✅ Run status updated to EXPORTED"
else
    echo "❌ Run status check failed or endpoint not returning expected data"
    echo "Response: $RUN_DETAILS"
fi

# 5. Test Error Handling (Invalid Run ID)
echo "   - Testing Error Handling (Invalid UUID)..."
ERR_CODE=$(curl -s -o /dev/null -w "%{http_code}" -X POST "${API_URL}/generate-excel" \
    -F "file=@$TEST_FILE" \
    -F "answers_json=$ANSWERS" \
    -F "org_id=$ORG_ID" \
    -F "run_id=invalid-uuid")

if [[ "$ERR_CODE" == "400" ]]; then
    echo "     ✅ Correctly rejected invalid UUID (400)"
else
    echo "❌ Expected 400 for invalid UUID, got $ERR_CODE"
fi

echo "🎉 E2E Verification Complete!"
rm "$EXPORT_OUTPUT" "http_code.txt"

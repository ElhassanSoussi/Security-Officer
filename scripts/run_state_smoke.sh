#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
API_BASE="${API_BASE:-http://127.0.0.1:8000/api/v1}"
TOKEN="${TOKEN:-}"
ORG_ID="${ORG_ID:-}"

if [[ -z "${TOKEN}" ]]; then
  echo "[FAIL] TOKEN is required (Supabase access token)." >&2
  exit 1
fi

if ! command -v jq >/dev/null 2>&1; then
  echo "[FAIL] jq is required for this smoke script." >&2
  exit 1
fi

AUTH_HEADER=(-H "Authorization: Bearer ${TOKEN}")
JSON_HEADER=(-H "Content-Type: application/json")

pass() { echo "[PASS] $1"; }
fail() { echo "[FAIL] $1" >&2; exit 1; }

if [[ -z "${ORG_ID}" ]]; then
  ORG_ID="$(curl -sS "${AUTH_HEADER[@]}" "${API_BASE}/orgs" | jq -r '.[0].id // empty')"
fi

[[ -n "${ORG_ID}" ]] || fail "Could not resolve ORG_ID from /orgs"
pass "Resolved org ${ORG_ID}"

CREATE_CODE="$(curl -sS -o /tmp/run_create.json -w "%{http_code}" \
  -X POST "${API_BASE}/runs" \
  "${AUTH_HEADER[@]}" "${JSON_HEADER[@]}" \
  -d "{\"org_id\":\"${ORG_ID}\",\"questionnaire_filename\":\"smoke.xlsx\",\"status\":\"queued\",\"progress\":0}")"
[[ "${CREATE_CODE}" == "200" ]] || fail "Run creation failed with HTTP ${CREATE_CODE}: $(cat /tmp/run_create.json)"
RUN_ID="$(jq -r '.id // empty' /tmp/run_create.json)"
[[ -n "${RUN_ID}" ]] || fail "Run ID missing from create response"
pass "Created run ${RUN_ID} in queued state"

RUN_STATUS="$(jq -r '.status // empty' /tmp/run_create.json)"
[[ "${RUN_STATUS}" == "QUEUED" ]] || fail "Expected QUEUED status, got ${RUN_STATUS}"
pass "Initial status QUEUED confirmed"

NOT_READY_CODE="$(curl -sS -o /tmp/run_download_queued.json -w "%{http_code}" \
  "${AUTH_HEADER[@]}" \
  "${API_BASE}/runs/${RUN_ID}/download")"
[[ "${NOT_READY_CODE}" == "409" ]] || fail "Expected 409 before completion, got ${NOT_READY_CODE}: $(cat /tmp/run_download_queued.json)"
[[ "$(jq -r '.error // empty' /tmp/run_download_queued.json)" == "export_not_ready" ]] || fail "Expected export_not_ready while queued"
pass "Download returns 409/export_not_ready while queued"

PROC_CODE="$(curl -sS -o /tmp/run_processing.json -w "%{http_code}" \
  -X PATCH "${API_BASE}/runs/${RUN_ID}" \
  "${AUTH_HEADER[@]}" "${JSON_HEADER[@]}" \
  -d '{"status":"processing","progress":35}')"
[[ "${PROC_CODE}" == "200" ]] || fail "Transition to processing failed with HTTP ${PROC_CODE}: $(cat /tmp/run_processing.json)"
[[ "$(jq -r '.status // empty' /tmp/run_processing.json)" == "PROCESSING" ]] || fail "Run not in PROCESSING state"
pass "Transition queued -> processing confirmed"

NOT_READY_PROC_CODE="$(curl -sS -o /tmp/run_download_processing.json -w "%{http_code}" \
  "${AUTH_HEADER[@]}" \
  "${API_BASE}/runs/${RUN_ID}/download")"
[[ "${NOT_READY_PROC_CODE}" == "409" ]] || fail "Expected 409 while processing, got ${NOT_READY_PROC_CODE}: $(cat /tmp/run_download_processing.json)"
[[ "$(jq -r '.error // empty' /tmp/run_download_processing.json)" == "export_not_ready" ]] || fail "Expected export_not_ready while processing"
pass "Download returns 409/export_not_ready while processing"

DONE_CODE="$(curl -sS -o /tmp/run_completed.json -w "%{http_code}" \
  -X PATCH "${API_BASE}/runs/${RUN_ID}" \
  "${AUTH_HEADER[@]}" "${JSON_HEADER[@]}" \
  -d '{"status":"completed","progress":100}')"
[[ "${DONE_CODE}" == "200" ]] || fail "Transition to completed failed with HTTP ${DONE_CODE}: $(cat /tmp/run_completed.json)"
[[ "$(jq -r '.status // empty' /tmp/run_completed.json)" == "COMPLETED" ]] || fail "Run not in COMPLETED state"
pass "Transition processing -> completed confirmed"

MISSING_EXPORT_CODE="$(curl -sS -o /tmp/run_download_missing.json -w "%{http_code}" \
  "${AUTH_HEADER[@]}" \
  "${API_BASE}/runs/${RUN_ID}/download")"
[[ "${MISSING_EXPORT_CODE}" == "404" ]] || fail "Expected 404 when export missing, got ${MISSING_EXPORT_CODE}: $(cat /tmp/run_download_missing.json)"
[[ "$(jq -r '.error // empty' /tmp/run_download_missing.json)" == "export_missing" ]] || fail "Expected export_missing when run completed without artifact"
pass "Download returns 404/export_missing when export artifact does not exist"

mkdir -p "${ROOT_DIR}/backend/exports"
cp "${ROOT_DIR}/backend/samples/sample_questionnaire.xlsx" "${ROOT_DIR}/backend/exports/${RUN_ID}.xlsx"
pass "Seeded export artifact for ${RUN_ID}"

DOWNLOAD_CODE="$(curl -sS -o "/tmp/${RUN_ID}.xlsx" -w "%{http_code}" \
  "${AUTH_HEADER[@]}" \
  "${API_BASE}/runs/${RUN_ID}/download")"
[[ "${DOWNLOAD_CODE}" == "200" ]] || fail "Download failed with HTTP ${DOWNLOAD_CODE}"
[[ -s "/tmp/${RUN_ID}.xlsx" ]] || fail "Downloaded file is empty"
pass "Download contract OK (200 + non-empty file)"

echo
echo "Run state smoke test passed for run ${RUN_ID}"

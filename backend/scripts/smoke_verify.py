#!/usr/bin/env python3
"""
Local smoke verification (runs inside the backend container).

Goals:
- Prove the stack is up
- Prove the Next.js proxy forwards auth headers correctly
- Prove hardened endpoints do not return 500s
- Prove analyze-excel + generate-excel work without crashing

This intentionally does NOT require a real Supabase user/org; it uses a locally
signed JWT (SUPABASE_JWT_SECRET) to exercise API auth + codepaths.
"""

from __future__ import annotations

import json
import os
import sys
import time
import uuid

import httpx
import jwt


def _ok(msg: str) -> None:
    print(f"PASS: {msg}")


def _fail(msg: str, *, detail: str | None = None) -> "NoReturn":
    print(f"FAIL: {msg}", file=sys.stderr)
    if detail:
        print(detail, file=sys.stderr)
    raise SystemExit(1)


def _make_local_token(secret: str) -> str:
    payload = {
        "aud": "authenticated",
        "exp": int(time.time()) + 3600,
        "sub": str(uuid.uuid4()),
        "role": "authenticated",
        "email": "smoke@example.com",
    }
    return jwt.encode(payload, secret, algorithm="HS256")


def _expect_json_200(client: httpx.Client, url: str, headers: dict[str, str]) -> None:
    r = client.get(url, headers=headers)
    if r.status_code != 200:
        _fail(f"GET {url} expected 200", detail=f"status={r.status_code} body={r.text[:300]}")
    try:
        r.json()
    except Exception:
        _fail(f"GET {url} expected JSON body", detail=f"status=200 body_prefix={r.text[:120]}")


def main() -> None:
    backend_health = os.getenv("BACKEND_HEALTH", "http://127.0.0.1:8000/health").strip()
    proxy_api_base = os.getenv("PROXY_API_BASE", "http://frontend:3000/api/v1").rstrip("/")

    timeout = httpx.Timeout(120.0, connect=10.0)
    client = httpx.Client(timeout=timeout, follow_redirects=False)

    print("== Smoke Verify ==")

    # 1) Backend health
    r = client.get(backend_health)
    if r.status_code != 200:
        _fail("backend /health not reachable", detail=f"status={r.status_code} body={r.text[:200]}")
    _ok("backend /health reachable")

    # 2) Proxy unauth orgs -> 403
    r = client.get(f"{proxy_api_base}/orgs")
    if r.status_code != 403:
        _fail(
            "proxy GET /orgs unauth should return 403",
            detail=f"status={r.status_code} body={r.text[:200]}",
        )
    _ok("proxy GET /orgs unauth returns 403")

    # 3) Authenticated calls via locally signed token
    secret = (os.getenv("SUPABASE_JWT_SECRET") or "").strip()
    if not secret:
        print("SKIP: SUPABASE_JWT_SECRET is missing; cannot run auth smoke.")
        return

    token = _make_local_token(secret)
    headers = {"Authorization": f"Bearer {token}"}
    _ok("local JWT created (not printed)")

    # 4) Hardened endpoints: should never 500
    for path in (
        "/orgs",
        "/projects",
        "/runs/stats",
        "/runs/projects",
        "/runs/activities",
        "/billing/plans",
        "/billing/current",
    ):
        _expect_json_200(client, f"{proxy_api_base}{path}", headers)
        _ok(f"GET {path} returns 200 JSON")

    # Invalid UUID should be a clean 400, never a 500.
    r = client.get(f"{proxy_api_base}/runs/stats?org_id=default-org", headers=headers)
    if r.status_code != 400:
        _fail(
            "invalid org_id should return 400",
            detail=f"status={r.status_code} body={r.text[:200]}",
        )
    _ok("invalid org_id returns 400 (not 500)")

    # 5) Analyze Excel (regression for closed-file bug)
    org_id = str(uuid.uuid4())
    xlsx_path = "/app/test_questionnaire.xlsx"
    try:
        with open(xlsx_path, "rb") as f:
            files = {
                "file": (
                    "test_questionnaire.xlsx",
                    f,
                    "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                )
            }
            data = {"org_id": org_id}
            r = client.post(f"{proxy_api_base}/analyze-excel", headers=headers, files=files, data=data)
    except FileNotFoundError:
        _fail("missing test questionnaire in container", detail=f"expected file at {xlsx_path}")

    if r.status_code != 200:
        _fail("POST /analyze-excel expected 200", detail=f"status={r.status_code} body={r.text[:300]}")
    try:
        body = r.json()
    except Exception:
        _fail("POST /analyze-excel expected JSON", detail=f"body_prefix={r.text[:200]}")
    if body.get("status") != "success":
        _fail("POST /analyze-excel expected status=success", detail=f"body={json.dumps(body)[:300]}")
    _ok("POST /analyze-excel returns 200 and JSON payload")

    # 6) Export stream: generate-excel should return an xlsx attachment.
    answers = [
        {
            "sheet_name": "Sheet1",
            "cell_coordinate": "B2",
            "question": "Smoke test?",
            "ai_answer": "A",
            "final_answer": "A",
            "confidence": "LOW",
            "sources": [],
            "is_verified": False,
            "edited_by_user": False,
        }
    ]
    with open(xlsx_path, "rb") as f:
        files = {
            "file": (
                "test_questionnaire.xlsx",
                f,
                "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            )
        }
        data = {"answers_json": json.dumps(answers), "org_id": org_id}
        r = client.post(f"{proxy_api_base}/generate-excel", headers=headers, files=files, data=data)

    if r.status_code != 200:
        _fail("POST /generate-excel expected 200", detail=f"status={r.status_code} body={r.text[:300]}")

    content_disposition = (r.headers.get("content-disposition") or "").lower()
    if "attachment" not in content_disposition or ".xlsx" not in content_disposition:
        _fail("export missing attachment header", detail=f"content-disposition={r.headers.get('content-disposition')}")

    if not r.content.startswith(b"PK\x03\x04"):
        _fail("export is not a valid xlsx (bad magic)", detail=f"magic={r.content[:8]!r}")

    _ok("POST /generate-excel returns valid xlsx attachment")

    _ok("smoke verification completed")


if __name__ == "__main__":
    main()


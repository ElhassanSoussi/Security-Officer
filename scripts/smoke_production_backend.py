#!/usr/bin/env python3
"""Production smoke test: backend (Render)

Goals:
- Minimal dependencies (requests)
- Clear PASS/FAIL/WARNING output
- No secrets

Usage:
  BACKEND_URL=https://<render-service>.onrender.com python scripts/smoke_production_backend.py

Notes:
- BACKEND_URL should be the backend origin (no /api/v1). The script will probe
  /health and /api/v1/system/readiness.
"""

from __future__ import annotations

import json
import os
import sys
import time
from dataclasses import dataclass
from typing import Any

import requests


@dataclass
class Result:
    status: str  # PASS | FAIL | WARNING
    check: str
    message: str


def _print(res: Result) -> None:
    print(f"{res.status}: {res.check} - {res.message}")


def _get_json(url: str, *, timeout: float = 10.0) -> tuple[int, dict[str, Any] | None, dict[str, str]]:
    resp = requests.get(url, timeout=timeout, headers={"Accept": "application/json"})
    headers = {k: v for k, v in resp.headers.items()}
    if "application/json" in (resp.headers.get("content-type") or ""):
        return resp.status_code, resp.json(), headers
    # Best-effort parse anyway in case of missing content-type
    try:
        return resp.status_code, resp.json(), headers
    except Exception:
        return resp.status_code, None, headers


def main() -> int:
    base = (os.getenv("BACKEND_URL") or os.getenv("RENDER_BACKEND_URL") or "").strip().rstrip("/")
    if not base:
        _print(Result("FAIL", "config", "BACKEND_URL is required"))
        return 2

    results: list[Result] = []

    # 1) /health
    code, data, headers = _get_json(f"{base}/health")
    if code != 200 or not isinstance(data, dict):
        results.append(Result("FAIL", "health", f"GET /health returned {code}"))
    else:
        ver = str(data.get("version") or "")
        env = str(data.get("environment") or "")
        results.append(Result("PASS", "health", f"ok (env={env or 'unknown'} version={ver or 'unknown'})"))

    # 2) readiness endpoint
    code, data, _ = _get_json(f"{base}/api/v1/system/readiness")
    if code != 200 or not isinstance(data, dict):
        results.append(Result("FAIL", "readiness", f"GET /api/v1/system/readiness returned {code}"))
    else:
        status = str(data.get("status") or "unknown")
        if status == "ok":
            results.append(Result("PASS", "readiness", "status=ok"))
        elif status == "warning":
            results.append(Result("WARNING", "readiness", "status=warning"))
        else:
            results.append(Result("FAIL", "readiness", f"status={status}"))

        # No secret leakage (basic heuristic)
        s = json.dumps(data).lower()
        if "secret" in s or "sk_live" in s or "sk_test" in s:
            results.append(Result("FAIL", "readiness_secret_leak", "response appears to contain sensitive values"))
        else:
            results.append(Result("PASS", "readiness_secret_leak", "no obvious secrets found"))

    # 3) security headers
    r = requests.get(f"{base}/health/ping", timeout=10)
    csp = r.headers.get("Content-Security-Policy")
    xcto = r.headers.get("X-Content-Type-Options")
    if not csp or not xcto:
        results.append(Result("WARNING", "security_headers", "missing CSP and/or X-Content-Type-Options"))
    else:
        results.append(Result("PASS", "security_headers", "CSP and basic hardening headers present"))

    # 4) unauthenticated protected route returns auth error (do not require specific code)
    # Use a known protected endpoint that should exist.
    r = requests.get(f"{base}/api/v1/orgs", timeout=10, headers={"Accept": "application/json"})
    if r.status_code in (401, 403):
        results.append(Result("PASS", "auth_guard", f"unauthenticated returns {r.status_code}"))
    else:
        results.append(Result("WARNING", "auth_guard", f"expected 401/403, got {r.status_code}"))

    # 5) rate limiting detection (best-effort, low impact)
    # Hit the critical endpoint a few times; stop early if 429 appears.
    rl_url = f"{base}/api/v1/assistant/message"
    got_429 = False
    for _ in range(4):
        rr = requests.post(
            rl_url,
            timeout=10,
            headers={"Accept": "application/json"},
            json={"message": "smoke", "org_id": "00000000-0000-0000-0000-000000000000"},
        )
        if rr.status_code == 429:
            got_429 = True
            try:
                body = rr.json()
            except Exception:
                body = {}
            if isinstance(body, dict) and body.get("error") == "rate_limited":
                results.append(Result("PASS", "rate_limit", "429 rate_limited shape detected"))
            else:
                results.append(Result("WARNING", "rate_limit", "429 detected but unexpected body"))
            break
        # avoid spamming
        time.sleep(0.2)

    if not got_429:
        results.append(Result("WARNING", "rate_limit", "no 429 observed (may be configured higher)"))

    # Print results and exit code
    exit_code = 0
    for res in results:
        _print(res)
        if res.status == "FAIL":
            exit_code = 2
        elif res.status == "WARNING" and exit_code == 0:
            exit_code = 1

    return exit_code


if __name__ == "__main__":
    sys.exit(main())

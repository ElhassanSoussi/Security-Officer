#!/usr/bin/env python3
"""Production smoke test: frontend (Vercel)

Goals:
- Minimal dependencies (requests)
- Clear PASS/FAIL/WARNING output

Usage:
  FRONTEND_URL=https://<vercel-app>.vercel.app python scripts/smoke_production_frontend.py

Notes:
- This script only validates public GET routes.
- Authenticated flows are checked as "route resolves" only (200/3xx), without credentials.
"""

from __future__ import annotations

import os
import sys
from dataclasses import dataclass

import requests


@dataclass
class Result:
    status: str  # PASS | FAIL | WARNING
    check: str
    message: str


def _print(res: Result) -> None:
    print(f"{res.status}: {res.check} - {res.message}")


def _get(url: str, *, timeout: float = 10.0) -> requests.Response:
    return requests.get(url, timeout=timeout, allow_redirects=False, headers={"User-Agent": "smoke/1.0"})


def main() -> int:
    base = (os.getenv("FRONTEND_URL") or os.getenv("VERCEL_FRONTEND_URL") or "").strip().rstrip("/")
    if not base:
        _print(Result("FAIL", "config", "FRONTEND_URL is required"))
        return 2

    results: list[Result] = []

    # Landing page
    r = _get(f"{base}/")
    if r.status_code in (200, 301, 302, 307, 308):
        results.append(Result("PASS", "landing", f"GET / -> {r.status_code}"))
    else:
        results.append(Result("FAIL", "landing", f"GET / -> {r.status_code}"))

    # Login page
    r = _get(f"{base}/login")
    if r.status_code in (200, 301, 302, 307, 308):
        results.append(Result("PASS", "login", f"GET /login -> {r.status_code}"))
    else:
        results.append(Result("FAIL", "login", f"GET /login -> {r.status_code}"))

    # Billing/settings route should resolve (likely redirects to /login)
    r = _get(f"{base}/settings/billing")
    if r.status_code in (200, 301, 302, 307, 308):
        results.append(Result("PASS", "settings_billing_route", f"GET /settings/billing -> {r.status_code}"))
    else:
        results.append(Result("WARNING", "settings_billing_route", f"GET /settings/billing -> {r.status_code}"))

    # Basic check: deployment is not returning obvious platform error pages
    body_snip = (r.text or "")[:500].lower()
    if "deployment protection" in body_snip or "authentication required" in body_snip:
        results.append(Result("WARNING", "vercel_protection", "Vercel Deployment Protection detected"))

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

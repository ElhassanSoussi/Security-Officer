"""app.api.endpoints.system

Operational endpoints for deployment readiness and configuration verification.

Constraints:
- No secrets in responses
- No business-logic changes
"""

from __future__ import annotations

from fastapi import APIRouter, Request

from app.core.config import get_settings
from app.core.env_readiness import build_readiness_report

router = APIRouter(prefix="/system", tags=["System"])


@router.get("/readiness")
def system_readiness(request: Request):
    settings = get_settings()
    return build_readiness_report(settings, request.app)

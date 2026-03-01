"""
Phase 12 Part 6: Structured logging utility.

Provides logger.info / logger.warn / logger.error with a consistent JSON-like
structured format:  timestamp | level | org_id | user_id | action | result | detail

Usage:
    from app.core.logger import audit_logger
    audit_logger.info(action="run_started", org_id="...", user_id="...", detail="run xyz")
    audit_logger.warn(action="export_failed", org_id="...", user_id="...", result="quota_exceeded")
    audit_logger.error(action="analysis_crash", org_id="...", user_id="...", detail=str(e))
"""
import logging
import json
import os
from datetime import datetime, timezone
from typing import Optional

_ENVIRONMENT = os.getenv("ENVIRONMENT", "local").lower()

# Structured JSON formatter for production; human-readable for local dev
class StructuredFormatter(logging.Formatter):
    """Emits log records as single-line JSON objects."""

    def format(self, record: logging.LogRecord) -> str:
        log_entry = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
        }
        # Merge any extra structured fields
        for key in ("org_id", "user_id", "action", "result", "detail", "request_id"):
            val = getattr(record, key, None)
            if val is not None:
                log_entry[key] = val
        return json.dumps(log_entry, default=str)


class HumanFormatter(logging.Formatter):
    """Human-readable structured log for local development."""

    def format(self, record: logging.LogRecord) -> str:
        ts = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S")
        extras = []
        for key in ("org_id", "user_id", "action", "result", "detail", "request_id"):
            val = getattr(record, key, None)
            if val is not None:
                extras.append(f"{key}={val}")
        extra_str = " ".join(extras)
        msg = record.getMessage()
        return f"{ts} {record.levelname:<7} [{record.name}] {msg} {extra_str}".rstrip()


def _get_formatter() -> logging.Formatter:
    if _ENVIRONMENT in ("production", "staging"):
        return StructuredFormatter()
    return HumanFormatter()


def get_logger(name: str = "app") -> logging.Logger:
    """Get a logger with the correct structured formatter."""
    log = logging.getLogger(name)
    if not log.handlers:
        handler = logging.StreamHandler()
        handler.setFormatter(_get_formatter())
        log.addHandler(handler)
        log.setLevel(logging.DEBUG if _ENVIRONMENT == "local" else logging.INFO)
        log.propagate = False
    return log


class AuditLogger:
    """
    Convenience wrapper for audit-related structured logging.

    All methods accept keyword-only structured fields:
        action, org_id, user_id, result, detail
    """

    def __init__(self):
        self._logger = get_logger("audit")

    def _log(self, level: int, action: str, **kwargs):
        extra = {
            "action": action,
            "org_id": kwargs.get("org_id"),
            "user_id": kwargs.get("user_id"),
            "result": kwargs.get("result"),
            "detail": kwargs.get("detail"),
            "request_id": kwargs.get("request_id"),
        }
        self._logger.log(level, action, extra=extra)

    def info(self, *, action: str, org_id: Optional[str] = None,
             user_id: Optional[str] = None, result: Optional[str] = None,
             detail: Optional[str] = None, request_id: Optional[str] = None):
        self._log(logging.INFO, action, org_id=org_id, user_id=user_id,
                  result=result, detail=detail, request_id=request_id)

    def warn(self, *, action: str, org_id: Optional[str] = None,
             user_id: Optional[str] = None, result: Optional[str] = None,
             detail: Optional[str] = None, request_id: Optional[str] = None):
        self._log(logging.WARNING, action, org_id=org_id, user_id=user_id,
                  result=result, detail=detail, request_id=request_id)

    def error(self, *, action: str, org_id: Optional[str] = None,
              user_id: Optional[str] = None, result: Optional[str] = None,
              detail: Optional[str] = None, request_id: Optional[str] = None):
        self._log(logging.ERROR, action, org_id=org_id, user_id=user_id,
                  result=result, detail=detail, request_id=request_id)


# Singleton instances
audit_logger = AuditLogger()

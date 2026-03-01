"""
Phase 20 Part 7 — Production Safety Guards

Provides:
  • openai_with_timeout(func, *args, **kwargs) — wraps OpenAI calls with configurable timeout
  • retry_vector_search(func, *args, **kwargs) — retries transient vector DB failures
  • structured_error(code, detail, request_id) — canonical error dict
"""

import time
import logging
import functools
from typing import Any, Callable, Optional, TypeVar

logger = logging.getLogger("app.resilience")

T = TypeVar("T")


# ─── OpenAI Timeout Protection ────────────────────────────────────────────────

def openai_with_timeout(func: Callable[..., T], *args: Any, timeout_seconds: Optional[int] = None, **kwargs: Any) -> T:
    """
    Call an OpenAI SDK function with a timeout guard.

    Falls back to OPENAI_TIMEOUT_SECONDS from config if timeout_seconds is not provided.
    Raises TimeoutError if the call exceeds the limit.
    """
    if timeout_seconds is None:
        try:
            from app.core.config import get_settings
            timeout_seconds = get_settings().OPENAI_TIMEOUT_SECONDS
        except Exception:
            timeout_seconds = 120

    import concurrent.futures
    with concurrent.futures.ThreadPoolExecutor(max_workers=1) as executor:
        future = executor.submit(func, *args, **kwargs)
        try:
            return future.result(timeout=timeout_seconds)
        except concurrent.futures.TimeoutError:
            logger.error("OpenAI call timed out after %ds: %s", timeout_seconds, func.__name__)
            raise TimeoutError(f"OpenAI call timed out after {timeout_seconds}s")


# ─── Vector Search Retry Wrapper ──────────────────────────────────────────────

def retry_vector_search(
    func: Callable[..., T],
    *args: Any,
    max_retries: Optional[int] = None,
    backoff_base: float = 0.5,
    **kwargs: Any,
) -> T:
    """
    Retry a vector search function on transient failures.

    Uses exponential backoff: 0.5s, 1s, 2s …
    Falls back to VECTOR_SEARCH_RETRIES from config if max_retries not provided.
    """
    if max_retries is None:
        try:
            from app.core.config import get_settings
            max_retries = get_settings().VECTOR_SEARCH_RETRIES
        except Exception:
            max_retries = 3

    last_exc: Exception = RuntimeError("no attempts made")
    for attempt in range(max_retries):
        try:
            return func(*args, **kwargs)
        except Exception as e:
            last_exc = e
            if attempt < max_retries - 1:
                delay = backoff_base * (2 ** attempt)
                logger.warning(
                    "vector search attempt %d/%d failed: %s — retrying in %.1fs",
                    attempt + 1, max_retries, str(e)[:100], delay,
                )
                time.sleep(delay)
            else:
                logger.error(
                    "vector search failed after %d attempts: %s",
                    max_retries, str(e)[:200],
                )
    raise last_exc


# ─── Structured Error Response Builder ────────────────────────────────────────

def structured_error(
    code: str,
    detail: str,
    request_id: Optional[str] = None,
) -> dict:
    """
    Build a canonical error dict:
    { "code": "...", "detail": "...", "request_id": "..." }
    """
    body: dict = {"code": code, "detail": detail}
    if request_id:
        body["request_id"] = request_id
    return body

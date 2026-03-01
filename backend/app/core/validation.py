"""
Phase 12 Part 3: Request validation utilities.

Centralizes input sanitization and validation helpers used across endpoints.
"""
import re
from typing import Optional


# Maximum upload sizes (bytes)
MAX_UPLOAD_SIZE_BYTES = 10 * 1024 * 1024  # 10 MB
MAX_QUESTIONNAIRE_SIZE_BYTES = 10 * 1024 * 1024  # 10 MB

# Allowed MIME types for uploads
ALLOWED_DOCUMENT_EXTENSIONS = {".pdf", ".docx", ".doc", ".xlsx", ".xlsm"}
ALLOWED_QUESTIONNAIRE_EXTENSIONS = {".xlsx", ".xlsm"}


def sanitize_string(value: Optional[str], max_length: int = 1000) -> Optional[str]:
    """
    Strip dangerous characters and enforce length limits.
    Returns None if input is None or empty after stripping.
    """
    if value is None:
        return None
    cleaned = value.strip()
    if not cleaned:
        return None
    # Remove null bytes
    cleaned = cleaned.replace("\x00", "")
    # Truncate
    return cleaned[:max_length]


def sanitize_filename(filename: Optional[str]) -> Optional[str]:
    """
    Sanitize an uploaded filename: strip path components, remove dangerous chars.
    """
    if not filename:
        return None
    # Remove path traversal
    name = filename.replace("\\", "/").split("/")[-1]
    # Remove null bytes and control chars
    name = re.sub(r"[\x00-\x1f]", "", name)
    return name.strip()[:255] if name.strip() else None


def validate_file_extension(filename: Optional[str], allowed: set[str]) -> str:
    """
    Validate file extension. Returns the lowercase extension.
    Raises ValueError if not in allowed set.
    """
    if not filename:
        raise ValueError("Filename is required")
    ext = ""
    parts = filename.rsplit(".", 1)
    if len(parts) == 2:
        ext = f".{parts[1].lower()}"
    if ext not in allowed:
        raise ValueError(f"File type '{ext or 'unknown'}' not allowed. Accepted: {', '.join(sorted(allowed))}")
    return ext

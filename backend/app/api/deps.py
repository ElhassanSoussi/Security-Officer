from fastapi import HTTPException
from uuid import UUID

def validate_org_id(org_id: str) -> str:
    """
    Validates that the provided org_id is a valid UUID.
    Raises 400 Bad Request if invalid. No fallbacks.
    """
    if not org_id or not str(org_id).strip():
        raise HTTPException(
            status_code=403,
            detail="Organization ID is required."
        )
    try:
        UUID(str(org_id).strip())
        return str(org_id).strip()
    except ValueError:
        raise HTTPException(
            status_code=400,
            detail=f"Invalid Organization ID format: '{org_id}'. Must be a valid UUID."
        )

def validate_uuid(id: str) -> str:
    """Generic UUID validator"""
    try:
        UUID(id)
        return id
    except ValueError:
        raise HTTPException(
            status_code=400,
            detail=f"Invalid ID format: '{id}'. Must be a valid UUID."
        )

"""
Phase 5 Part 2: Expiration Tracking Engine.

Computes document expiration status based on:
  - expiration_date on project_documents
  - reminder_days_before (default 30)

Statuses:
  valid    → expiration_date is in the future beyond the reminder window
  expiring → within the reminder window (0 < days_remaining <= reminder_days_before)
  expired  → expiration_date is in the past (days_remaining <= 0)
  no_expiration → expiration_date is NULL
"""
from datetime import date, datetime
from typing import Any, Dict, List, Optional


def compute_expiration_status(
    expiration_date: Optional[Any],
    reminder_days_before: int = 30,
    reference_date: Optional[date] = None,
) -> Dict[str, Any]:
    """
    Compute the expiration status for a single document.

    Returns dict with keys:
      - status: "valid" | "expiring" | "expired" | "no_expiration"
      - days_remaining: int or None
      - expiration_date: str (ISO) or None
    """
    if expiration_date is None:
        return {
            "status": "no_expiration",
            "days_remaining": None,
            "expiration_date": None,
        }

    # Parse expiration_date to a date object
    exp_date = _parse_date(expiration_date)
    if exp_date is None:
        return {
            "status": "no_expiration",
            "days_remaining": None,
            "expiration_date": None,
        }

    ref = reference_date or date.today()
    delta = (exp_date - ref).days

    if delta <= 0:
        status = "expired"
    elif delta <= max(reminder_days_before, 0):
        status = "expiring"
    else:
        status = "valid"

    return {
        "status": status,
        "days_remaining": delta,
        "expiration_date": exp_date.isoformat(),
    }


def classify_documents(
    documents: List[Dict[str, Any]],
    reminder_days_before: int = 30,
    reference_date: Optional[date] = None,
) -> List[Dict[str, Any]]:
    """
    Add expiration status fields to a list of document dicts.

    Each document dict should optionally have:
      - expiration_date (str ISO date or None)
      - reminder_days_before (int, overrides default if present)

    Returns the same list with added keys: status, days_remaining.
    """
    result = []
    for doc in documents:
        doc_reminder = doc.get("reminder_days_before", reminder_days_before)
        if doc_reminder is None:
            doc_reminder = reminder_days_before
        try:
            doc_reminder = int(doc_reminder)
        except (ValueError, TypeError):
            doc_reminder = reminder_days_before

        exp_info = compute_expiration_status(
            expiration_date=doc.get("expiration_date"),
            reminder_days_before=doc_reminder,
            reference_date=reference_date,
        )
        enriched = {**doc, **exp_info}
        result.append(enriched)
    return result


def summarize_expirations(
    documents: List[Dict[str, Any]],
    reminder_days_before: int = 30,
    reference_date: Optional[date] = None,
) -> Dict[str, Any]:
    """
    Return a summary of expiration statuses across documents.
    """
    classified = classify_documents(documents, reminder_days_before, reference_date)
    counts = {"valid": 0, "expiring": 0, "expired": 0, "no_expiration": 0}
    for doc in classified:
        s = doc.get("status", "no_expiration")
        if s in counts:
            counts[s] += 1
        else:
            counts["no_expiration"] += 1

    return {
        "total": len(classified),
        "counts": counts,
        "documents": classified,
    }


def _parse_date(value: Any) -> Optional[date]:
    """
    Parse a date from various formats. Returns None on failure.
    """
    if isinstance(value, date) and not isinstance(value, datetime):
        return value
    if isinstance(value, datetime):
        return value.date()
    if isinstance(value, str):
        s = value.strip()
        if not s:
            return None
        # Try ISO date (YYYY-MM-DD)
        for fmt in ("%Y-%m-%d", "%Y-%m-%dT%H:%M:%S", "%Y-%m-%dT%H:%M:%S.%f",
                     "%Y-%m-%dT%H:%M:%S%z", "%Y-%m-%dT%H:%M:%S.%f%z"):
            try:
                return datetime.strptime(s[:26].rstrip("Z"), fmt.rstrip("%z")).date()
            except ValueError:
                continue
        # Last resort: try just the date part
        try:
            return datetime.strptime(s[:10], "%Y-%m-%d").date()
        except ValueError:
            return None
    return None

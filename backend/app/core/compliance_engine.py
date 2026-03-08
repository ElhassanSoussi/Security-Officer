"""
compliance_engine.py — Compliance Intelligence Engine

Provides:
  - extract_document_metadata(filename, content_text) → inferred document type,
    expiration date, risk level
  - upsert_document_metadata(admin_sb, org_id, document_id, ...) → DB write
  - generate_compliance_issues(admin_sb, org_id, project_id) → list of issues,
    writes to compliance_issues table
  - calculate_project_score(admin_sb, org_id, project_id) → score 0-100,
    risk_level, writes to compliance_scores table
  - get_project_compliance_summary(admin_sb, org_id, project_id) → dict
  - get_org_compliance_overview(admin_sb, org_id) → dict for dashboard

Scoring model:
  - Start at 100
  - Each HIGH severity open issue: -15 pts
  - Each MEDIUM severity open issue: -8 pts
  - Each LOW severity open issue: -3 pts
  - Minimum score: 0

Risk classification:
  - score >= 75 → low
  - score >= 45 → medium
  - score <  45 → high
"""

from __future__ import annotations

import logging
import re
from datetime import date, datetime, timedelta, timezone
from typing import Any, Dict, List, Optional, Tuple

logger = logging.getLogger("core.compliance_engine")

# ─── Constants ────────────────────────────────────────────────────────────────

EXPIRY_WARNING_DAYS = 60          # issues created when expiry within this window
OUTDATED_SAFETY_DAYS = 365        # safety docs older than this are flagged
SCORE_DEDUCTIONS = {"high": 15, "medium": 8, "low": 3}

DOCUMENT_TYPE_PATTERNS: List[Tuple[str, str]] = [
    (r"fire.?safety|fire.?prevention|sprinkler|extinguisher", "fire_safety"),
    (r"asbestos|hazmat|hazardous.?material", "hazmat"),
    (r"elevator|boiler|pressure.?vessel", "equipment_inspection"),
    (r"electrical|wiring|panel|breaker", "electrical_inspection"),
    (r"egress|exit.?plan|evacuation", "egress_plan"),
    (r"certificate.?of.?occupancy|co.?cert|occupancy.?permit", "occupancy_certificate"),
    (r"insurance|liability|coverage|policy", "insurance"),
    (r"building.?permit|work.?permit|construction.?permit", "permit"),
    (r"inspection.?report|inspector.?report", "inspection_report"),
    (r"license|certification|credential", "license"),
    (r"contract|agreement|lease", "contract"),
]

DATE_PATTERNS = [
    r"expir(?:es?|ation(?:\s+date)?)[:\s]+(\d{4}-\d{2}-\d{2})",
    r"expir(?:es?|ation(?:\s+date)?)[:\s]+(\d{1,2}[\/\-\.]\d{1,2}[\/\-\.]\d{2,4})",
    r"valid(?:\s+through|\s+until|ity)[:\s]+(\d{1,2}[\/\-\.]\d{1,2}[\/\-\.]\d{2,4})",
    r"renew(?:al)?(?:\s+date)?[:\s]+(\d{1,2}[\/\-\.]\d{1,2}[\/\-\.]\d{2,4})",
    r"expires?[:\s]+(\w+ \d{1,2},?\s+\d{4})",
    r"expires[_\-](\d{4}-\d{2}-\d{2})",
    r"(\d{1,2}[\/\-\.]\d{1,2}[\/\-\.]\d{4})",
]


# ─── Document Type Detection ──────────────────────────────────────────────────

def infer_document_type(filename: str, content_text: str = "") -> str:
    """Infer document type from filename and extracted text."""
    combined = f"{filename} {content_text[:2000]}".lower()
    for pattern, doc_type in DOCUMENT_TYPE_PATTERNS:
        if re.search(pattern, combined):
            return doc_type
    return "general"


def infer_risk_level(doc_type: str, expiration_date: Optional[date]) -> str:
    """
    Infer risk level for a document.
    Safety-critical types with imminent expiry are high risk.
    """
    high_risk_types = {"fire_safety", "egress_plan", "hazmat", "equipment_inspection", "electrical_inspection"}
    medium_risk_types = {"occupancy_certificate", "inspection_report", "permit"}

    today = date.today()
    days_remaining = (expiration_date - today).days if expiration_date else None

    if doc_type in high_risk_types:
        if days_remaining is not None and days_remaining <= EXPIRY_WARNING_DAYS:
            return "high"
        return "medium"

    if doc_type in medium_risk_types:
        if days_remaining is not None and days_remaining <= EXPIRY_WARNING_DAYS:
            return "medium"
        return "low"

    return "low"


# ─── Expiration Date Extraction ───────────────────────────────────────────────

def extract_expiration_date(filename: str, content_text: str = "") -> Optional[date]:
    """
    Extract the most likely expiration date from filename and document content.
    Returns None if no date can be reliably extracted.
    """
    combined = f"{filename} {content_text[:5000]}"
    for pattern in DATE_PATTERNS:
        match = re.search(pattern, combined, re.IGNORECASE)
        if match:
            raw = match.group(1).strip()
            parsed = _parse_flexible_date(raw)
            if parsed and parsed > date.today():
                return parsed
    return None


def _parse_flexible_date(raw: str) -> Optional[date]:
    formats = [
        "%Y-%m-%d",
        "%m/%d/%Y", "%m-%d-%Y", "%m.%d.%Y",
        "%m/%d/%y", "%m-%d-%y",
        "%d/%m/%Y", "%d-%m-%Y",
        "%B %d, %Y", "%B %d %Y",
        "%b %d, %Y", "%b %d %Y",
    ]
    for fmt in formats:
        try:
            return datetime.strptime(raw.strip(), fmt).date()
        except ValueError:
            continue
    return None


# ─── Metadata Extraction Entry Point ─────────────────────────────────────────

def extract_document_metadata(
    filename: str,
    content_text: str = "",
) -> Dict[str, Any]:
    """
    Extract compliance metadata from a document.

    Returns dict with:
      - document_type: str
      - expiration_date: date | None
      - risk_level: str (low | medium | high)
    """
    doc_type = infer_document_type(filename, content_text)
    expiration_date = extract_expiration_date(filename, content_text)
    risk_level = infer_risk_level(doc_type, expiration_date)
    return {
        "document_type": doc_type,
        "expiration_date": expiration_date,
        "risk_level": risk_level,
    }


# ─── DB Writes ────────────────────────────────────────────────────────────────

def upsert_document_metadata(
    admin_sb,
    org_id: str,
    document_id: str,
    document_type: str,
    expiration_date: Optional[date],
    risk_level: str,
) -> Optional[Dict[str, Any]]:
    """
    Upsert a document_metadata row. Uses service-role client.
    Silently returns None on failure so callers never crash.
    """
    try:
        payload: Dict[str, Any] = {
            "org_id": org_id,
            "document_id": document_id,
            "document_type": document_type,
            "risk_level": risk_level,
            "last_checked": datetime.now(timezone.utc).isoformat(),
        }
        if expiration_date is not None:
            payload["expiration_date"] = expiration_date.isoformat()

        res = (
            admin_sb.table("document_metadata")
            .upsert(payload, on_conflict="document_id")
            .execute()
        )
        return (res.data or [None])[0]
    except Exception as exc:
        logger.warning("upsert_document_metadata failed for doc %s: %s", document_id, exc)
        return None


# ─── Issue Generation ─────────────────────────────────────────────────────────

def generate_compliance_issues(
    admin_sb,
    org_id: str,
    project_id: str,
) -> List[Dict[str, Any]]:
    """
    Detect compliance issues for a project and persist them.

    Checks:
      1. Documents expiring within EXPIRY_WARNING_DAYS
      2. Safety documents with no expiration date (treated as outdated)
      3. Documents older than OUTDATED_SAFETY_DAYS with no expiry date (high-risk types)

    Existing open issues of the same type are resolved before inserting new ones
    to avoid accumulation of duplicate issues.

    Returns the list of newly-created issue dicts.
    """
    today = date.today()
    issues_to_create: List[Dict[str, Any]] = []

    # Fetch document_metadata for this project via documents join
    try:
        docs_res = (
            admin_sb.table("documents")
            .select("id, filename, created_at")
            .eq("org_id", org_id)
            .eq("project_id", project_id)
            .execute()
        )
        doc_rows = docs_res.data or []
    except Exception as exc:
        logger.warning("generate_compliance_issues: cannot fetch documents: %s", exc)
        return []

    if not doc_rows:
        return []

    doc_ids = [d["id"] for d in doc_rows]

    # Fetch metadata for these documents
    try:
        meta_res = (
            admin_sb.table("document_metadata")
            .select("document_id, document_type, expiration_date, risk_level, last_checked")
            .in_("document_id", doc_ids)
            .execute()
        )
        meta_by_doc = {m["document_id"]: m for m in (meta_res.data or [])}
    except Exception:
        meta_by_doc = {}

    high_risk_types = {"fire_safety", "egress_plan", "hazmat", "equipment_inspection", "electrical_inspection"}

    for doc in doc_rows:
        doc_id = doc["id"]
        meta = meta_by_doc.get(doc_id)
        if not meta:
            continue

        doc_type = meta.get("document_type", "general")
        exp_raw = meta.get("expiration_date")
        exp_date = _parse_flexible_date(exp_raw) if exp_raw else None
        created_raw = doc.get("created_at", "")
        try:
            created_dt = datetime.fromisoformat(created_raw.replace("Z", "+00:00"))
            doc_age_days = (datetime.now(timezone.utc) - created_dt).days
        except Exception:
            doc_age_days = 0

        # Issue: expiring within EXPIRY_WARNING_DAYS
        if exp_date is not None:
            days_remaining = (exp_date - today).days
            if days_remaining < 0:
                issues_to_create.append({
                    "issue_type": "expired_document",
                    "severity": "high",
                    "description": (
                        f"Document '{doc['filename']}' ({doc_type}) expired "
                        f"{abs(days_remaining)} day(s) ago on {exp_date.isoformat()}."
                    ),
                })
            elif days_remaining <= EXPIRY_WARNING_DAYS:
                severity = "high" if days_remaining <= 14 else "medium"
                issues_to_create.append({
                    "issue_type": "expiring_document",
                    "severity": severity,
                    "description": (
                        f"Document '{doc['filename']}' ({doc_type}) expires in "
                        f"{days_remaining} day(s) on {exp_date.isoformat()}."
                    ),
                })
        elif doc_type in high_risk_types and doc_age_days > OUTDATED_SAFETY_DAYS:
            issues_to_create.append({
                "issue_type": "outdated_safety_document",
                "severity": "medium",
                "description": (
                    f"Safety document '{doc['filename']}' ({doc_type}) is "
                    f"{doc_age_days} days old with no expiration date on record. "
                    "Verify it is current."
                ),
            })

    # Check for required document types missing from project
    required_types = {"fire_safety", "egress_plan"}
    present_types = {m.get("document_type") for m in meta_by_doc.values()}
    for req_type in required_types:
        if req_type not in present_types:
            issues_to_create.append({
                "issue_type": "missing_required_document",
                "severity": "high",
                "description": (
                    f"Required document type '{req_type.replace('_', ' ')}' is missing "
                    f"from this project."
                ),
            })

    # Resolve old open issues for this project before inserting fresh ones
    try:
        admin_sb.table("compliance_issues").update({"status": "resolved"}).eq("project_id", project_id).eq("status", "open").execute()
    except Exception as exc:
        logger.warning("generate_compliance_issues: could not resolve old issues: %s", exc)

    created_issues: List[Dict[str, Any]] = []
    for issue in issues_to_create:
        try:
            row = {
                "org_id": org_id,
                "project_id": project_id,
                "issue_type": issue["issue_type"],
                "severity": issue["severity"],
                "description": issue["description"],
                "status": "open",
            }
            res = admin_sb.table("compliance_issues").insert(row).execute()
            if res.data:
                created_issues.append(res.data[0])
        except Exception as exc:
            logger.warning("generate_compliance_issues: insert failed: %s", exc)

    return created_issues


# ─── Score Calculation ────────────────────────────────────────────────────────

def calculate_project_score(
    admin_sb,
    org_id: str,
    project_id: str,
) -> Dict[str, Any]:
    """
    Calculate and persist the compliance score for a project.

    Returns:
      { overall_score: int, risk_level: str, open_issues: int }
    """
    try:
        issues_res = (
            admin_sb.table("compliance_issues")
            .select("id, severity, status")
            .eq("project_id", project_id)
            .eq("status", "open")
            .execute()
        )
        open_issues = issues_res.data or []
    except Exception as exc:
        logger.warning("calculate_project_score: cannot fetch issues: %s", exc)
        open_issues = []

    score = 100
    for issue in open_issues:
        severity = issue.get("severity", "low")
        score -= SCORE_DEDUCTIONS.get(severity, 0)
    score = max(0, score)

    risk_level = (
        "low" if score >= 75
        else "medium" if score >= 45
        else "high"
    )

    # Persist score
    try:
        admin_sb.table("compliance_scores").insert({
            "org_id": org_id,
            "project_id": project_id,
            "overall_score": score,
            "risk_level": risk_level,
        }).execute()
    except Exception as exc:
        logger.warning("calculate_project_score: insert failed: %s", exc)

    return {
        "overall_score": score,
        "risk_level": risk_level,
        "open_issues": len(open_issues),
    }


# ─── Query Helpers ────────────────────────────────────────────────────────────

def get_project_compliance_summary(
    admin_sb,
    org_id: str,
    project_id: str,
) -> Dict[str, Any]:
    """
    Return the latest compliance score and open issue breakdown for a project.
    """
    # Latest score
    try:
        score_res = (
            admin_sb.table("compliance_scores")
            .select("overall_score, risk_level, created_at")
            .eq("project_id", project_id)
            .order("created_at", desc=True)
            .limit(1)
            .execute()
        )
        score_row = (score_res.data or [{}])[0]
    except Exception:
        score_row = {}

    # Open issues grouped by severity
    try:
        issues_res = (
            admin_sb.table("compliance_issues")
            .select("id, severity, issue_type, description, status, created_at")
            .eq("project_id", project_id)
            .eq("status", "open")
            .order("created_at", desc=True)
            .execute()
        )
        issues = issues_res.data or []
    except Exception:
        issues = []

    by_severity: Dict[str, int] = {"high": 0, "medium": 0, "low": 0}
    for issue in issues:
        sev = issue.get("severity", "low")
        by_severity[sev] = by_severity.get(sev, 0) + 1

    return {
        "project_id": project_id,
        "overall_score": score_row.get("overall_score"),
        "risk_level": score_row.get("risk_level"),
        "score_updated_at": score_row.get("created_at"),
        "open_issues": len(issues),
        "issues_by_severity": by_severity,
        "issues": issues,
    }


def get_org_compliance_overview(
    admin_sb,
    org_id: str,
) -> Dict[str, Any]:
    """
    Return org-level compliance overview for the dashboard.

    Includes:
      - avg_score: average of latest scores across all projects
      - overall_risk_level: worst risk level across all projects
      - active_issues: total open issues
      - expiring_documents: count of documents expiring within 60 days
      - top_risks: list of top open issues sorted by severity
    """
    # Fetch all projects in org
    try:
        proj_res = admin_sb.table("projects").select("id").eq("org_id", org_id).execute()
        project_ids = [p["id"] for p in (proj_res.data or [])]
    except Exception:
        project_ids = []

    if not project_ids:
        return _empty_overview()

    # Latest score per project
    scores: List[int] = []
    risk_levels: List[str] = []
    for pid in project_ids:
        try:
            s = (
                admin_sb.table("compliance_scores")
                .select("overall_score, risk_level")
                .eq("project_id", pid)
                .order("created_at", desc=True)
                .limit(1)
                .execute()
            )
            row = (s.data or [None])[0]
            if row:
                scores.append(row["overall_score"])
                risk_levels.append(row["risk_level"])
        except Exception:
            pass

    avg_score = round(sum(scores) / len(scores)) if scores else None
    overall_risk = (
        "high" if "high" in risk_levels
        else "medium" if "medium" in risk_levels
        else "low" if risk_levels
        else None
    )

    # Total open issues
    try:
        issues_res = (
            admin_sb.table("compliance_issues")
            .select("id, severity, issue_type, description, project_id, created_at")
            .eq("org_id", org_id)
            .eq("status", "open")
            .order("created_at", desc=True)
            .execute()
        )
        all_issues = issues_res.data or []
    except Exception:
        all_issues = []

    # Expiring documents count (within EXPIRY_WARNING_DAYS)
    today = date.today()
    cutoff = (today + timedelta(days=EXPIRY_WARNING_DAYS)).isoformat()
    try:
        exp_res = (
            admin_sb.table("document_metadata")
            .select("id")
            .eq("org_id", org_id)
            .not_.is_("expiration_date", "null")
            .lte("expiration_date", cutoff)
            .gte("expiration_date", today.isoformat())
            .execute()
        )
        expiring_count = len(exp_res.data or [])
    except Exception:
        expiring_count = 0

    # Top risks: sort by severity (high first), take up to 5
    severity_order = {"high": 0, "medium": 1, "low": 2}
    top_risks = sorted(
        all_issues,
        key=lambda x: severity_order.get(x.get("severity", "low"), 2),
    )[:5]

    return {
        "avg_score": avg_score,
        "overall_risk_level": overall_risk,
        "active_issues": len(all_issues),
        "expiring_documents": expiring_count,
        "top_risks": top_risks,
        "issues_by_severity": {
            "high": sum(1 for i in all_issues if i.get("severity") == "high"),
            "medium": sum(1 for i in all_issues if i.get("severity") == "medium"),
            "low": sum(1 for i in all_issues if i.get("severity") == "low"),
        },
    }


def _empty_overview() -> Dict[str, Any]:
    return {
        "avg_score": None,
        "overall_risk_level": None,
        "active_issues": 0,
        "expiring_documents": 0,
        "top_risks": [],
        "issues_by_severity": {"high": 0, "medium": 0, "low": 0},
    }

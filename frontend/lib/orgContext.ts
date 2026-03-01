export const ORG_STORAGE_KEY = "nyc_compliance_org_id";

const UUID_RE =
  /^[0-9a-f]{8}-[0-9a-f]{4}-[1-5][0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$/i;

export function isUuid(value: string): boolean {
  return UUID_RE.test((value || "").trim());
}

export function getStoredOrgId(): string | null {
  if (typeof window === "undefined") return null;
  try {
    const v = window.localStorage.getItem(ORG_STORAGE_KEY);
    const trimmed = v && v.trim() ? v.trim() : null;
    if (trimmed && !isUuid(trimmed)) {
      // Auto-heal legacy values like "default-org" that break UUID-backed APIs.
      window.localStorage.removeItem(ORG_STORAGE_KEY);
      return null;
    }
    return trimmed;
  } catch {
    return null;
  }
}

export function setStoredOrgId(orgId: string) {
  if (typeof window === "undefined") return;
  try {
    if (!isUuid(orgId)) {
      window.localStorage.removeItem(ORG_STORAGE_KEY);
      return;
    }
    window.localStorage.setItem(ORG_STORAGE_KEY, orgId.trim());
  } catch {
    // ignore
  }
}

export function clearStoredOrgId() {
  if (typeof window === "undefined") return;
  try {
    window.localStorage.removeItem(ORG_STORAGE_KEY);
  } catch {
    // ignore
  }
}

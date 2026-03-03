/**
 * RBAC helper
 * Roles: viewer < reviewer < compliance_manager < admin < owner
 */

export type OrgRole =
  | "viewer"
  | "reviewer"
  | "compliance_manager"
  | "admin"
  | "owner";

const ROLE_RANK: Record<OrgRole, number> = {
  viewer: 0,
  reviewer: 1,
  compliance_manager: 2,
  admin: 3,
  owner: 4,
};

/** Returns true if the user's role is at least the required minimum. */
export function hasRole(userRole: OrgRole | null | undefined, required: OrgRole): boolean {
  if (!userRole) return false;
  return (ROLE_RANK[userRole] ?? -1) >= ROLE_RANK[required];
}

/** Can approve / reject audit answers. */
export function canReview(role: OrgRole | null | undefined): boolean {
  return hasRole(role, "reviewer");
}

/** Can edit answer text. */
export function canEdit(role: OrgRole | null | undefined): boolean {
  return hasRole(role, "reviewer");
}

/** Can trigger an export. */
export function canExport(role: OrgRole | null | undefined): boolean {
  return hasRole(role, "compliance_manager");
}

/** Can manage projects (create / delete). */
export function canManageProjects(role: OrgRole | null | undefined): boolean {
  return hasRole(role, "compliance_manager");
}

/** Can manage org members. */
export function canManageMembers(role: OrgRole | null | undefined): boolean {
  return hasRole(role, "admin");
}

/** Nice display label for a role. */
export function roleLabel(role: OrgRole | null | undefined): string {
  const map: Record<OrgRole, string> = {
    viewer: "Viewer",
    reviewer: "Reviewer",
    compliance_manager: "Compliance Manager",
    admin: "Admin",
    owner: "Owner",
  };
  return role ? (map[role] ?? role) : "Unknown";
}

/**
 * Hook-free helper: parse the role from a membership record.
 * Supabase memberships table has a `role` column.
 */
export function parseMembershipRole(membership: any): OrgRole | null {
  const raw = String(membership?.role || "").toLowerCase().trim().replace(/ /g, "_");
  if (raw in ROLE_RANK) return raw as OrgRole;
  return null;
}

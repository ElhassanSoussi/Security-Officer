"use client";

/**
 * useRBAC — Phase 14 Part 6
 * Fetches the current user's membership role in the active org and
 * exposes permission helpers derived from lib/rbac.ts.
 */

import { useState, useEffect } from "react";
import { createClient } from "@/utils/supabase/client";
import type { OrgRole } from "@/lib/rbac";
import {
  parseMembershipRole,
  canReview,
  canEdit,
  canExport,
  canManageProjects,
  canManageMembers,
  roleLabel,
} from "@/lib/rbac";

interface RBACState {
  role: OrgRole | null;
  loading: boolean;
  /** Can approve / reject audit answers */
  canReview: boolean;
  /** Can edit answer text */
  canEdit: boolean;
  /** Can trigger an export */
  canExport: boolean;
  /** Can create / archive projects */
  canManageProjects: boolean;
  /** Can invite / remove org members */
  canManageMembers: boolean;
  /** Human-readable role label */
  roleLabel: string;
}

const DEFAULT_STATE: RBACState = {
  role: null,
  loading: true,
  canReview: false,
  canEdit: false,
  canExport: false,
  canManageProjects: false,
  canManageMembers: false,
  roleLabel: "Unknown",
};

/**
 * Hook that resolves the current user's role in `orgId`.
 * Falls back to querying Supabase directly for the memberships table.
 *
 * @param orgId  — The organization UUID to check membership for.
 */
export function useRBAC(orgId: string | null | undefined): RBACState {
  const [state, setState] = useState<RBACState>(DEFAULT_STATE);

  useEffect(() => {
    if (!orgId) {
      setState({ ...DEFAULT_STATE, loading: false });
      return;
    }

    let cancelled = false;

    async function load() {
      setState((prev) => ({ ...prev, loading: true }));
      try {
        const supabase = createClient();
        const {
          data: { user },
        } = await supabase.auth.getUser();

        if (!user) {
          if (!cancelled) setState({ ...DEFAULT_STATE, loading: false });
          return;
        }

        // Query the memberships table directly
        const { data: membership, error } = await supabase
          .from("memberships")
          .select("role")
          .eq("org_id", orgId)
          .eq("user_id", user.id)
          .single();

        if (error || !membership) {
          // If the user owns the org, they won't necessarily have a membership row.
          // Check the orgs table.
          const { data: org } = await supabase
            .from("organizations")
            .select("owner_id")
            .eq("id", orgId)
            .single();

          const role: OrgRole | null =
            org?.owner_id === user.id ? "owner" : null;

          if (!cancelled) {
            setState({
              role,
              loading: false,
              canReview: canReview(role),
              canEdit: canEdit(role),
              canExport: canExport(role),
              canManageProjects: canManageProjects(role),
              canManageMembers: canManageMembers(role),
              roleLabel: roleLabel(role),
            });
          }
          return;
        }

        const role = parseMembershipRole(membership);
        if (!cancelled) {
          setState({
            role,
            loading: false,
            canReview: canReview(role),
            canEdit: canEdit(role),
            canExport: canExport(role),
            canManageProjects: canManageProjects(role),
            canManageMembers: canManageMembers(role),
            roleLabel: roleLabel(role),
          });
        }
      } catch {
        if (!cancelled) {
          // Default to owner-level permissions on error to avoid blocking solo users.
          const role: OrgRole = "owner";
          setState({
            role,
            loading: false,
            canReview: true,
            canEdit: true,
            canExport: true,
            canManageProjects: true,
            canManageMembers: true,
            roleLabel: "Owner",
          });
        }
      }
    }

    load();
    return () => {
      cancelled = true;
    };
  }, [orgId]);

  return state;
}

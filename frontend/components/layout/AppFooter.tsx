"use client";

import { getStoredOrgId } from "@/lib/orgContext";

export function AppFooter() {
    const orgId = getStoredOrgId();
    const env = process.env.NODE_ENV === "production" ? "Production" : "Development";

    return (
        <footer className="border-t border-border bg-muted/50 px-4 py-3 md:px-8 text-[11px] text-muted-foreground flex items-center justify-between gap-4 mt-auto">
            <span>© {new Date().getFullYear()} NYC Compliance Architect · v1.0.0 · {env}</span>
            {orgId && (
                <span className="font-mono truncate max-w-[220px]" title={orgId}>
                    Org: {orgId.slice(0, 12)}…
                </span>
            )}
        </footer>
    );
}

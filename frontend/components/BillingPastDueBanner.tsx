"use client";

/**
 * Phase 19 — Billing Past-Due Banner
 *
 * Fetches the org's Stripe subscription status on mount.
 * Renders a sticky top banner when stripe_status === "past_due".
 * Links to /settings/billing for resolution.
 *
 * Mount inside AppShell (authenticated shell only).
 */

import { useEffect, useState } from "react";
import Link from "next/link";
import { AlertTriangle, X } from "lucide-react";
import { ApiClient } from "@/lib/api";
import { createClient } from "@/utils/supabase/client";

interface BillingStatus {
    stripe_status: string | null;
    org_id: string;
}

export function BillingPastDueBanner() {
    const [isPastDue, setIsPastDue] = useState(false);
    const [dismissed, setDismissed] = useState(false);

    useEffect(() => {
        let cancelled = false;

        async function check() {
            try {
                const supabase = createClient();
                const { data: { session } } = await supabase.auth.getSession();
                if (!session?.access_token) return;

                const orgRes = await ApiClient.getCurrentOrg(session.access_token);
                const orgId: string | undefined = orgRes?.id;
                if (!orgId) return;

                const status: BillingStatus = await ApiClient.getSubscriptionStatus(
                    orgId,
                    session.access_token,
                );
                if (!cancelled && status.stripe_status === "past_due") {
                    setIsPastDue(true);
                }
            } catch {
                // Fail silently — banner is non-critical
            }
        }

        check();
        return () => { cancelled = true; };
    }, []);

    if (!isPastDue || dismissed) return null;

    return (
        <div className="relative flex items-center gap-3 bg-amber-50 border-b border-amber-200 px-4 py-2.5 text-sm text-amber-900">
            <AlertTriangle className="h-4 w-4 shrink-0 text-amber-600" aria-hidden />
            <span className="flex-1">
                Your subscription payment is past due. Some features may be restricted.{" "}
                <Link
                    href="/settings/billing"
                    className="font-semibold underline underline-offset-2 hover:text-amber-800"
                >
                    Update billing →
                </Link>
            </span>
            <button
                onClick={() => setDismissed(true)}
                aria-label="Dismiss billing warning"
                className="rounded p-0.5 hover:bg-amber-100 transition-colors"
            >
                <X className="h-3.5 w-3.5" />
            </button>
        </div>
    );
}

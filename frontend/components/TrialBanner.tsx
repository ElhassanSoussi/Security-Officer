"use client";

/**
 * Trial Conversion Banner
 *
 * Shows a banner when the user is on a trialing subscription.
 * Displays days remaining + upgrade CTA.
 * Tracks TRIAL_STARTED on first render if not already tracked.
 * Mount in AppShell (authenticated area) alongside BillingPastDueBanner.
 */

import { useEffect, useState, useRef } from "react";
import Link from "next/link";
import { Clock, Zap, X } from "lucide-react";
import { Button } from "@/components/ui/button";
import { ApiClient } from "@/lib/api";
import { createClient } from "@/utils/supabase/client";

interface TrialInfo {
    stripe_status: string | null;
    current_period_end: string | null;
    org_id: string;
}

export function TrialBanner() {
    const [daysLeft, setDaysLeft] = useState<number | null>(null);
    const [dismissed, setDismissed] = useState(false);
    const trackedRef = useRef(false);

    useEffect(() => {
        let cancelled = false;

        async function check() {
            try {
                const supabase = createClient();
                const { data: { session } } = await supabase.auth.getSession();
                if (!session?.access_token) return;

                const org = await ApiClient.getCurrentOrg(session.access_token);
                const oid: string | undefined = org?.id;
                if (!oid) return;

                const status: TrialInfo = await ApiClient.getSubscriptionStatus(
                    oid,
                    session.access_token,
                );

                if (cancelled) return;

                if (status.stripe_status === "trialing" && status.current_period_end) {
                    const endDate = new Date(status.current_period_end);
                    const now = new Date();
                    const diffMs = endDate.getTime() - now.getTime();
                    const days = Math.max(0, Math.ceil(diffMs / (1000 * 60 * 60 * 24)));
                    setDaysLeft(days);

                    // Track TRIAL_STARTED once per session
                    if (!trackedRef.current) {
                        trackedRef.current = true;
                        const sessionKey = `nyccompliance:trial_tracked:${oid}`;
                        try {
                            if (!sessionStorage.getItem(sessionKey)) {
                                await ApiClient.trackTrialEvent(oid, "TRIAL_STARTED", session.access_token);
                                sessionStorage.setItem(sessionKey, "1");
                            }
                        } catch {
                            // Best-effort tracking
                        }
                    }
                }
            } catch {
                // Fail silently — banner is non-critical
            }
        }

        check();
        return () => { cancelled = true; };
    }, []);

    if (daysLeft === null || dismissed) return null;

    const urgency = daysLeft <= 3 ? "urgent" : daysLeft <= 7 ? "warning" : "info";
    const colors = {
        urgent: "bg-red-50 border-red-200 text-red-800",
        warning: "bg-amber-50 border-amber-200 text-amber-800",
        info: "bg-blue-50 border-blue-200 text-blue-800",
    };

    return (
        <div className={`flex items-center justify-between gap-3 border-b px-4 py-2 text-sm ${colors[urgency]}`}>
            <div className="flex items-center gap-2">
                <Clock className="h-4 w-4 shrink-0" />
                <span>
                    {daysLeft === 0 ? (
                        <span className="font-semibold">Your trial ends today!</span>
                    ) : daysLeft === 1 ? (
                        <span className="font-semibold">Your trial ends tomorrow!</span>
                    ) : (
                        <>
                            Trial ends in <span className="font-semibold">{daysLeft} days</span>.
                        </>
                    )}{" "}
                    <span className="hidden sm:inline">
                        Upgrade now to keep your compliance workflows running.
                    </span>
                </span>
            </div>
            <div className="flex items-center gap-2 shrink-0">
                <Link href="/plans">
                    <Button
                        size="sm"
                        className="h-7 gap-1.5 text-xs bg-gradient-to-r from-blue-600 to-blue-700 hover:from-blue-700 hover:to-blue-800 text-white"
                    >
                        <Zap className="h-3 w-3" />
                        Upgrade Now
                    </Button>
                </Link>
                <button
                    type="button"
                    onClick={() => setDismissed(true)}
                    className="rounded p-0.5 hover:bg-black/5 transition-colors"
                    aria-label="Dismiss trial banner"
                >
                    <X className="h-3.5 w-3.5" />
                </button>
            </div>
        </div>
    );
}

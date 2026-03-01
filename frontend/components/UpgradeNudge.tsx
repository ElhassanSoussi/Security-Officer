"use client";

/**
 * Phase 22 — Upgrade Nudge Panel
 *
 * A non-intrusive panel that shows current usage vs. plan limits
 * and highlights what the next tier unlocks. Professional tone, no aggressive marketing.
 *
 * Usage:
 *   <UpgradeNudge resource="evidence" currentCount={8} />
 *   <UpgradeNudge resource="runs" />
 */

import Link from "next/link";
import { Zap, TrendingUp, ArrowRight } from "lucide-react";
import { Button } from "@/components/ui/button";

interface UpgradeNudgeProps {
    /** The resource that triggered the nudge: "runs" | "documents" | "memory" | "evidence" */
    resource?: "runs" | "documents" | "memory" | "evidence";
    /** Current usage count (optional — if provided, shown in context) */
    currentCount?: number;
    /** Plan limit (optional) */
    limit?: number;
    /** Current plan name */
    plan?: string;
    /** Optional custom message override */
    message?: string;
    /** Whether to show the component at all */
    show?: boolean;
    /** Compact variant for inline use */
    compact?: boolean;
}

const RESOURCE_NUDGES: Record<string, { label: string; proUnlock: string }> = {
    runs: {
        label: "analysis runs",
        proUnlock: "100 runs/month + priority processing",
    },
    documents: {
        label: "documents",
        proUnlock: "500 documents + batch upload",
    },
    memory: {
        label: "institutional memory entries",
        proUnlock: "2,000 memory entries for smarter answers",
    },
    evidence: {
        label: "evidence exports",
        proUnlock: "Unlimited evidence exports + audit trail",
    },
};

export function UpgradeNudge({
    resource = "evidence",
    currentCount,
    limit,
    plan = "FREE",
    message,
    show = true,
    compact = false,
}: UpgradeNudgeProps) {
    if (!show || plan.toUpperCase() !== "FREE") return null;

    const nudge = RESOURCE_NUDGES[resource] ?? RESOURCE_NUDGES.evidence;

    const displayMessage =
        message ??
        (resource === "evidence"
            ? "Upgrade to Pro for unlimited evidence exports and enhanced compliance features."
            : `You're approaching your ${nudge.label} limit. Upgrade for more capacity.`);

    if (compact) {
        return (
            <div className="flex items-center gap-2 rounded-md border border-blue-100 bg-blue-50/60 px-3 py-2 text-xs text-blue-800">
                <TrendingUp className="h-3.5 w-3.5 shrink-0 text-blue-500" />
                <span>{displayMessage}</span>
                <Link href="/plans" className="ml-auto shrink-0">
                    <Button variant="ghost" size="sm" className="h-6 text-xs text-blue-700 hover:text-blue-900 gap-1 px-2">
                        Upgrade <ArrowRight className="h-3 w-3" />
                    </Button>
                </Link>
            </div>
        );
    }

    return (
        <div className="rounded-lg border border-blue-100 bg-gradient-to-r from-blue-50/80 to-white p-4 space-y-3">
            <div className="flex items-start gap-3">
                <div className="rounded-full bg-blue-100 p-2 shrink-0">
                    <TrendingUp className="h-4 w-4 text-blue-600" />
                </div>
                <div className="space-y-1 flex-1">
                    <p className="text-sm font-medium text-slate-900">{displayMessage}</p>
                    {currentCount != null && limit != null && (
                        <p className="text-xs text-slate-500">
                            Current usage: {currentCount.toLocaleString()} / {limit.toLocaleString()} {nudge.label}
                        </p>
                    )}
                    <p className="text-xs text-blue-700 font-medium">
                        Pro unlocks: {nudge.proUnlock}
                    </p>
                </div>
            </div>
            <div className="flex justify-end">
                <Link href="/plans">
                    <Button
                        size="sm"
                        className="gap-1.5 bg-gradient-to-r from-blue-600 to-blue-700 hover:from-blue-700 hover:to-blue-800 text-white text-xs"
                    >
                        <Zap className="h-3.5 w-3.5" />
                        View Pro Plan
                    </Button>
                </Link>
            </div>
        </div>
    );
}

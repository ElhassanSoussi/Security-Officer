"use client";

/**
 * Usage Panel
 * Displays current-month usage vs plan limits with progress bars.
 * Shows "Upgrade Plan" CTA when at/near limits.
 */

import { useEffect, useState } from "react";
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { ApiClient } from "@/lib/api";
import {
    PlayCircle,
    FileText,
    Brain,
    ShieldCheck,
    TrendingUp,
    AlertTriangle,
    Loader2,
    Zap,
} from "lucide-react";
import Link from "next/link";

interface UsageSummary {
    runs_this_month: number;
    documents_total: number;
    memory_entries_total: number;
    evidence_exports_total: number;
    plan: string;
    limits: {
        plan_name: string;
        max_runs_per_month: number;
        max_documents: number;
        max_memory_entries: number;
    };
}

interface UsagePanelProps {
    orgId: string;
    token?: string;
}

/** Returns a percentage (0–100), capped at 100. */
function pct(current: number, limit: number): number {
    if (limit <= 0) return 0;
    return Math.min(100, Math.round((current / limit) * 100));
}

/** Tailwind width class based on % used (snapped to nearest 5%) */
function barWidthClass(p: number): string {
    const snapped = Math.round(p / 5) * 5;
    const clipped = Math.min(100, Math.max(0, snapped));
    // Map to Tailwind JIT-safe classes
    const map: Record<number, string> = {
        0: "w-0", 5: "w-[5%]", 10: "w-[10%]", 15: "w-[15%]",
        20: "w-[20%]", 25: "w-1/4", 30: "w-[30%]", 35: "w-[35%]",
        40: "w-[40%]", 45: "w-[45%]", 50: "w-1/2", 55: "w-[55%]",
        60: "w-[60%]", 65: "w-[65%]", 70: "w-[70%]", 75: "w-3/4",
        80: "w-[80%]", 85: "w-[85%]", 90: "w-[90%]", 95: "w-[95%]",
        100: "w-full",
    };
    return map[clipped] ?? "w-0";
}

/** Color class based on % used */
function barColor(p: number): string {
    if (p >= 100) return "bg-red-500";
    if (p >= 85) return "bg-amber-500";
    return "bg-blue-500";
}

/** Text color based on % used */
function textColor(p: number): string {
    if (p >= 100) return "text-red-600";
    if (p >= 85) return "text-amber-600";
    return "text-muted-foreground";
}

interface UsageRowProps {
    label: string;
    icon: React.ReactNode;
    current: number;
    limit: number | null;
}

function UsageRow({ label, icon, current, limit }: UsageRowProps) {
    const p = limit != null ? pct(current, limit) : 0;
    const isUnlimited = limit == null || limit >= 1_000_000;
    const isAtLimit = !isUnlimited && p >= 100;
    const isNearLimit = !isUnlimited && p >= 85 && !isAtLimit;

    return (
        <div className="space-y-1.5">
            <div className="flex items-center justify-between text-sm">
                <span className="flex items-center gap-2 font-medium text-foreground">
                    <span className="text-muted-foreground">{icon}</span>
                    {label}
                </span>
                <span className={`text-xs font-semibold ${textColor(p)}`}>
                    {isUnlimited ? (
                        <span className="text-muted-foreground">
                            {current.toLocaleString()} / ∞
                        </span>
                    ) : (
                        <>
                            {current.toLocaleString()}
                            <span className="font-normal text-muted-foreground">
                                {" "}/ {limit!.toLocaleString()}
                            </span>
                        </>
                    )}
                </span>
            </div>

            {!isUnlimited && (
                <div className="h-2 w-full rounded-full bg-muted overflow-hidden">
                    <div
                        className={`h-full rounded-full transition-all duration-500 ${barColor(p)} ${barWidthClass(p)}`}
                    />
                </div>
            )}

            {isAtLimit && (
                <p className="text-xs text-red-600 font-medium flex items-center gap-1">
                    <AlertTriangle className="h-3 w-3" />
                    Limit reached — upgrade to continue
                </p>
            )}
            {isNearLimit && (
                <p className="text-xs text-amber-600 font-medium flex items-center gap-1">
                    <AlertTriangle className="h-3 w-3" />
                    Approaching limit ({p}% used)
                </p>
            )}
        </div>
    );
}

const PLAN_BADGE: Record<string, { label: string; className: string }> = {
    FREE: { label: "Free", className: "border-gray-200 bg-gray-50 text-gray-600" },
    PRO: { label: "Pro", className: "border-blue-200 bg-blue-50 text-blue-700" },
    ENTERPRISE: { label: "Enterprise", className: "border-purple-200 bg-purple-50 text-purple-700" },
};

export function UsagePanel({ orgId, token }: UsagePanelProps) {
    const [usage, setUsage] = useState<UsageSummary | null>(null);
    const [loading, setLoading] = useState(true);

    useEffect(() => {
        if (!orgId) return;
        setLoading(true);
        ApiClient.getUsageSummary(orgId, token)
            .then(setUsage)
            .catch(() => {/* fail silently — panel is non-critical */})
            .finally(() => setLoading(false));
    }, [orgId, token]);

    if (loading) {
        return (
            <Card>
                <CardContent className="flex items-center justify-center py-8">
                    <Loader2 className="h-5 w-5 animate-spin text-muted-foreground" />
                </CardContent>
            </Card>
        );
    }

    if (!usage) return null;

    const { limits, plan } = usage;
    const planBadge = PLAN_BADGE[plan] ?? PLAN_BADGE["FREE"];

    // Determine whether CTA should be shown: any metric at/near limit
    const runPct = pct(usage.runs_this_month, limits.max_runs_per_month);
    const docPct = pct(usage.documents_total, limits.max_documents);
    const memPct = pct(usage.memory_entries_total, limits.max_memory_entries);
    const showCTA = plan !== "ENTERPRISE" && Math.max(runPct, docPct, memPct) >= 75;

    return (
        <Card className="border-border">
            <CardHeader className="pb-3">
                <div className="flex items-center justify-between flex-wrap gap-2">
                    <div>
                        <CardTitle className="flex items-center gap-2 text-base">
                            <TrendingUp className="h-4 w-4 text-blue-600" />
                            Plan Usage
                        </CardTitle>
                        <CardDescription className="mt-1">
                            Current billing period usage and limits.
                        </CardDescription>
                    </div>
                    <div className="flex items-center gap-2">
                        <Badge
                            variant="outline"
                            className={`text-xs font-semibold ${planBadge.className}`}
                        >
                            <Zap className="h-3 w-3 mr-1" />
                            {planBadge.label} Plan
                        </Badge>
                        {showCTA && plan === "FREE" && (
                            <Link href="/plans">
                                <Button size="sm" className="h-7 text-xs gap-1 bg-gradient-to-r from-blue-600 to-blue-700 hover:from-blue-700 hover:to-blue-800 text-white">
                                    <Zap className="h-3 w-3" /> Upgrade Plan
                                </Button>
                            </Link>
                        )}
                        {showCTA && plan === "PRO" && (
                            <Link href="/plans">
                                <Button size="sm" variant="outline" className="h-7 text-xs gap-1 border-purple-300 text-purple-700 hover:bg-purple-50">
                                    <Zap className="h-3 w-3" /> Go Enterprise
                                </Button>
                            </Link>
                        )}
                    </div>
                </div>
            </CardHeader>

            <CardContent className="space-y-4">
                <UsageRow
                    label="Runs this month"
                    icon={<PlayCircle className="h-4 w-4" />}
                    current={usage.runs_this_month}
                    limit={limits.max_runs_per_month}
                />
                <UsageRow
                    label="Documents stored"
                    icon={<FileText className="h-4 w-4" />}
                    current={usage.documents_total}
                    limit={limits.max_documents}
                />
                <UsageRow
                    label="Memory entries"
                    icon={<Brain className="h-4 w-4" />}
                    current={usage.memory_entries_total}
                    limit={limits.max_memory_entries}
                />
                <UsageRow
                    label="Evidence exports"
                    icon={<ShieldCheck className="h-4 w-4" />}
                    current={usage.evidence_exports_total}
                    limit={null}
                />
            </CardContent>
        </Card>
    );
}

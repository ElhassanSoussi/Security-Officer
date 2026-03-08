"use client";

/**
 * /settings/usage — Usage Dashboard
 *
 * Shows:
 * 1. Current plan card + upgrade button
 * 2. Usage meters for Projects, Documents, Runs
 * 3. Upgrade recommendation (next plan features)
 */

import { useCallback, useEffect, useState } from "react";
import { Zap, BarChart3, ArrowUpRight, RefreshCw, Loader2, CheckCircle2, ExternalLink } from "lucide-react";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { UsageMeter } from "@/components/ui/UsageMeter";
import { ApiClient } from "@/lib/api";
import { createClient } from "@/utils/supabase/client";
import Link from "next/link";

// ── Plan metadata ─────────────────────────────────────────────────────────────

const PLAN_DISPLAY: Record<string, { label: string; description: string; badgeClass: string }> = {
    starter: {
        label: "Starter",
        description: "Perfect for small teams getting started with compliance.",
        badgeClass: "bg-slate-100 text-slate-700 border-slate-200",
    },
    growth: {
        label: "Growth",
        description: "For growing teams that need more headroom and AI runs.",
        badgeClass: "bg-blue-100 text-blue-800 border-blue-200",
    },
    elite: {
        label: "Elite",
        description: "Unlimited scale for enterprise compliance programs.",
        badgeClass: "bg-violet-100 text-violet-800 border-violet-200",
    },
};

const PLAN_NEXT_FEATURES: Record<string, { label: string; features: string[] }> = {
    growth: {
        label: "Growth",
        features: [
            "25 projects (5× more)",
            "500 documents (20× more)",
            "100 analysis runs / month (10× more)",
            "Priority support",
        ],
    },
    elite: {
        label: "Elite",
        features: [
            "Unlimited projects",
            "Unlimited documents",
            "Unlimited analysis runs",
            "Dedicated account manager",
        ],
    },
};

// ── Types ─────────────────────────────────────────────────────────────────────

interface UsageData {
    plan: string;
    limits: { projects: number; documents: number; runs: number };
    usage: { projects: number; documents: number; runs: number };
    percent: { projects: number; documents: number; runs: number };
    next_plan: string | null;
}

// ── Sub-components ────────────────────────────────────────────────────────────

function PlanCard({
    plan,
    nextPlan,
    onManageBilling,
    portalLoading,
}: {
    plan: string;
    nextPlan: string | null;
    onManageBilling: () => void;
    portalLoading: boolean;
}) {
    const display = PLAN_DISPLAY[plan] ?? PLAN_DISPLAY.starter;
    const isElite = plan === "elite";

    return (
        <Card>
            <CardHeader className="pb-3">
                <div className="flex items-start justify-between gap-4">
                    <div className="space-y-1">
                        <CardTitle className="flex items-center gap-2 text-base">
                            <Zap className="h-4 w-4 text-muted-foreground" />
                            Current Plan
                        </CardTitle>
                        <CardDescription>{display.description}</CardDescription>
                    </div>
                    <Badge variant="outline" className={`shrink-0 gap-1 text-xs font-semibold ${display.badgeClass}`}>
                        <Zap className="h-3 w-3" />
                        {display.label}
                    </Badge>
                </div>
            </CardHeader>
            <CardContent className="flex flex-wrap gap-3">
                {!isElite && (
                    <Button asChild size="sm" className="gap-1.5">
                        <Link href="/plans">
                            <ArrowUpRight className="h-3.5 w-3.5" />
                            Upgrade to {nextPlan ? (PLAN_DISPLAY[nextPlan]?.label ?? nextPlan) : "next tier"}
                        </Link>
                    </Button>
                )}
                <Button
                    variant="outline"
                    size="sm"
                    className="gap-1.5"
                    onClick={onManageBilling}
                    disabled={portalLoading}
                >
                    {portalLoading ? (
                        <Loader2 className="h-3.5 w-3.5 animate-spin" />
                    ) : (
                        <ExternalLink className="h-3.5 w-3.5" />
                    )}
                    Manage Billing
                </Button>
            </CardContent>
        </Card>
    );
}

function UsageMetersCard({ data }: { data: UsageData }) {
    const maxPct = Math.max(data.percent.projects, data.percent.documents, data.percent.runs);
    const hasWarning = maxPct >= 70;

    return (
        <Card>
            <CardHeader className="pb-3">
                <CardTitle className="flex items-center gap-2 text-base">
                    <BarChart3 className="h-4 w-4 text-muted-foreground" />
                    Resource Usage
                </CardTitle>
                <CardDescription>
                    Current consumption against your {PLAN_DISPLAY[data.plan]?.label ?? data.plan} plan limits.
                    Runs reset monthly.
                </CardDescription>
            </CardHeader>
            <CardContent className="space-y-5">
                <UsageMeter
                    label="Projects"
                    used={data.usage.projects}
                    limit={data.limits.projects}
                    percent={data.percent.projects}
                />
                <UsageMeter
                    label="Documents"
                    used={data.usage.documents}
                    limit={data.limits.documents}
                    percent={data.percent.documents}
                />
                <UsageMeter
                    label="Analysis Runs"
                    used={data.usage.runs}
                    limit={data.limits.runs}
                    percent={data.percent.runs}
                    sublabel="this month"
                />

                {hasWarning && data.next_plan && (
                    <div className="rounded-lg border border-amber-200 bg-amber-50 px-4 py-3 text-sm text-amber-800 dark:border-amber-800 dark:bg-amber-950 dark:text-amber-300">
                        You&apos;re approaching your plan limits.{" "}
                        <Link href="/plans" className="font-semibold underline underline-offset-2 hover:opacity-80">
                            Upgrade now
                        </Link>{" "}
                        to keep things running smoothly.
                    </div>
                )}
            </CardContent>
        </Card>
    );
}

function UpgradeRecommendationCard({ nextPlan }: { nextPlan: string }) {
    const next = PLAN_NEXT_FEATURES[nextPlan];
    if (!next) return null;

    return (
        <Card className="border-primary/20 bg-primary/5">
            <CardHeader className="pb-3">
                <CardTitle className="flex items-center gap-2 text-base">
                    <Zap className="h-4 w-4 text-primary" />
                    Upgrade to {next.label}
                </CardTitle>
                <CardDescription>
                    Unlock higher limits and more capacity for your compliance work.
                </CardDescription>
            </CardHeader>
            <CardContent className="space-y-4">
                <ul className="space-y-2">
                    {next.features.map((f) => (
                        <li key={f} className="flex items-center gap-2 text-sm">
                            <CheckCircle2 className="h-4 w-4 shrink-0 text-primary" />
                            <span>{f}</span>
                        </li>
                    ))}
                </ul>
                <Button asChild size="sm" className="gap-1.5">
                    <Link href="/plans">
                        <ArrowUpRight className="h-3.5 w-3.5" />
                        See all {next.label} features
                    </Link>
                </Button>
            </CardContent>
        </Card>
    );
}

// ── Page ──────────────────────────────────────────────────────────────────────

export default function UsagePage() {
    const [data, setData] = useState<UsageData | null>(null);
    const [loading, setLoading] = useState(true);
    const [error, setError] = useState<string | null>(null);
    const [portalLoading, setPortalLoading] = useState(false);
    const [orgId, setOrgId] = useState<string | undefined>(undefined);

    const load = useCallback(async () => {
        setLoading(true);
        setError(null);
        try {
            const supabase = createClient();
            const { data: { session } } = await supabase.auth.getSession();
            const token = session?.access_token;

            // Resolve org_id from user's orgs
            let oid: string | undefined;
            try {
                const orgs = await ApiClient.fetch<{ id: string }[]>("/orgs", {}, token);
                oid = Array.isArray(orgs) && orgs.length > 0 ? orgs[0].id : undefined;
            } catch {
                oid = undefined;
            }
            setOrgId(oid);

            const usage = await ApiClient.getAccountUsage(oid, token);
            setData(usage);
        } catch (e: any) {
            setError(e?.message ?? "Failed to load usage data");
        } finally {
            setLoading(false);
        }
    }, []);

    useEffect(() => { load(); }, [load]);

    const handleManageBilling = async () => {
        if (!orgId) return;
        setPortalLoading(true);
        try {
            const result = await ApiClient.createPortalSessionV2(orgId);
            if (result.url) window.location.href = result.url;
        } catch (e: any) {
            setError(e?.message ?? "Could not open billing portal.");
        } finally {
            setPortalLoading(false);
        }
    };

    return (
        <div className="max-w-2xl space-y-6">
            {/* Header */}
            <div className="flex items-center justify-between">
                <div>
                    <h2 className="text-lg font-semibold text-foreground">Usage</h2>
                    <p className="text-sm text-muted-foreground mt-0.5">
                        Track your plan usage and limits in real time.
                    </p>
                </div>
                <Button
                    variant="ghost"
                    size="sm"
                    onClick={load}
                    disabled={loading}
                    className="gap-1.5 text-xs"
                >
                    <RefreshCw className={`h-3.5 w-3.5 ${loading ? "animate-spin" : ""}`} />
                    Refresh
                </Button>
            </div>

            {/* Error */}
            {error && (
                <div className="rounded-lg border border-red-200 bg-red-50 px-4 py-3 text-sm text-red-800">
                    {error}
                </div>
            )}

            {/* Loading skeleton */}
            {loading && (
                <div className="space-y-4">
                    {[1, 2, 3].map((i) => (
                        <Card key={i}>
                            <CardContent className="pt-6 pb-5 space-y-3 animate-pulse">
                                <div className="h-4 w-1/3 rounded bg-muted" />
                                <div className="h-2 w-full rounded-full bg-muted" />
                                <div className="h-2 w-full rounded-full bg-muted" />
                                <div className="h-2 w-3/4 rounded-full bg-muted" />
                            </CardContent>
                        </Card>
                    ))}
                </div>
            )}

            {/* Content */}
            {!loading && data && (
                <>
                    <PlanCard
                        plan={data.plan}
                        nextPlan={data.next_plan}
                        onManageBilling={handleManageBilling}
                        portalLoading={portalLoading}
                    />
                    <UsageMetersCard data={data} />
                    {data.next_plan && <UpgradeRecommendationCard nextPlan={data.next_plan} />}
                </>
            )}
        </div>
    );
}

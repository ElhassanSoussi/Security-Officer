"use client";

/**
 * ComplianceHealthPanel — Phase 15 Part 3
 * Org-level compliance metrics + low-confidence trend bar chart.
 * Fetches from GET /api/v1/runs/compliance-health?org_id=...
 * (via ApiClient.fetch which prepends API_BASE automatically)
 */

import { useEffect, useState } from "react";
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { ApiClient } from "@/lib/api";
import {
    BarChart3, CheckCircle2, Clock, AlertTriangle,
    TrendingDown, Brain, Loader2, Activity
} from "lucide-react";

interface HealthData {
    health_score?: number;
    total_runs: number;
    total_questions: number;
    avg_confidence_pct: number;
    total_approved: number;
    total_rejected: number;
    total_pending: number;
    total_low_conf: number;
    total_high_conf: number;
    total_medium_conf: number;
    memory_reuse_count: number;
    avg_review_turnaround_hours: number | null;
    low_conf_trend: Array<{
        run_id: string;
        label: string;
        total: number;
        low_conf: number;
        low_conf_pct: number;
    }>;
}

interface Props {
    orgId: string;
    token?: string;
    className?: string;
}

function MetricTile({
    label, value, sub, icon, color,
}: {
    label: string;
    value: string | number;
    sub?: string;
    icon: React.ReactNode;
    color: string;
}) {
    return (
        <div className="flex flex-col gap-1 rounded-lg border bg-card p-3">
            <div className={`flex items-center gap-1.5 text-xs font-medium ${color}`}>
                {icon}
                {label}
            </div>
            <p className="text-2xl font-bold text-foreground leading-none">{value}</p>
            {sub && <p className="text-[10px] text-muted-foreground">{sub}</p>}
        </div>
    );
}

function TrendBar({ pct, total, label }: { pct: number; total: number; label: string }) {
    const color =
        pct > 20 ? "bg-red-500" :
        pct > 10 ? "bg-amber-400" :
        "bg-green-500";
    // Use Tailwind width classes for common values; fall back to a data-attribute
    // driven approach so we never need inline styles.
    const clampedPct = Math.min(Math.round(pct), 100);
    // Map to nearest 5% Tailwind width class (w-0 → w-full).
    const widthClass = (() => {
        if (clampedPct === 0) return "w-0";
        if (clampedPct <= 5) return "w-[5%]";
        if (clampedPct <= 10) return "w-[10%]";
        if (clampedPct <= 15) return "w-[15%]";
        if (clampedPct <= 20) return "w-[20%]";
        if (clampedPct <= 25) return "w-1/4";
        if (clampedPct <= 30) return "w-[30%]";
        if (clampedPct <= 40) return "w-2/5";
        if (clampedPct <= 50) return "w-1/2";
        if (clampedPct <= 60) return "w-[60%]";
        if (clampedPct <= 75) return "w-3/4";
        if (clampedPct <= 90) return "w-[90%]";
        return "w-full";
    })();
    return (
        <div className="flex items-center gap-2 group">
            <span className="w-24 truncate text-[10px] text-muted-foreground text-right shrink-0" title={label}>
                {label}
            </span>
            <div className="flex-1 h-4 rounded-sm bg-muted overflow-hidden relative">
                <div className={`h-full rounded-sm transition-all ${color} ${widthClass}`} />
                {total === 0 && (
                    <span className="absolute inset-0 flex items-center justify-center text-[9px] text-muted-foreground">
                        no data
                    </span>
                )}
            </div>
            <span className="w-9 text-right text-[10px] font-medium text-muted-foreground shrink-0">
                {pct}%
            </span>
        </div>
    );
}

export function ComplianceHealthPanel({ orgId, token, className = "" }: Props) {
    const [healthData, setHealthData] = useState<HealthData | null>(null);
    const [loading, setLoading] = useState(true);
    const [error, setError] = useState("");

    useEffect(() => {
        if (!orgId) return;
        async function fetchHealth() {
            setLoading(true);
            try {
                const url = `/runs/compliance-health${orgId ? `?org_id=${orgId}` : ""}`;
                ApiClient.fetch<HealthData>(url, {}, token)
                    .then((d) => { setHealthData(d); setError(""); })
                    .catch((e: any) => setError(e?.message || "Failed to load health data"))
                    .finally(() => setLoading(false));
            } catch (e: any) {
                setError(e?.message || "Failed to load health data");
                setLoading(false);
            }
        }
        fetchHealth();
    }, [orgId, token]);

    if (loading) {
        return (
            <Card className={className}>
                <CardContent className="flex items-center justify-center py-12">
                    <Loader2 className="h-6 w-6 animate-spin text-muted-foreground" />
                </CardContent>
            </Card>
        );
    }

    if (error) {
        return (
            <Card className={`border-red-200 bg-red-50/50 ${className}`}>
                <CardContent className="pt-6 text-sm text-red-600 flex items-center gap-2">
                    <AlertTriangle className="h-4 w-4" />
                    Failed to load compliance health: {error}
                </CardContent>
            </Card>
        );
    }

    if (!healthData) return null;

    const turnaround = healthData.avg_review_turnaround_hours
        ? `${healthData.avg_review_turnaround_hours.toFixed(1)}h`
        : "—";

    return (
        <Card className={className}>
            <CardHeader className="pb-3">
                <div className="flex items-center gap-2">
                    <BarChart3 className="h-4 w-4 text-blue-600" />
                    <CardTitle className="text-base">Compliance Health</CardTitle>
                    <Badge variant="outline" className="text-[10px] ml-auto border-blue-200 text-blue-700 bg-blue-50">
                        Last {healthData.total_runs} run{healthData.total_runs !== 1 ? "s" : ""}
                    </Badge>
                </div>
                <CardDescription>Org-level metrics across recent questionnaire runs.</CardDescription>
            </CardHeader>

            <CardContent>
                <div className="grid grid-cols-1 gap-6 lg:grid-cols-4">

                    {/* Stats Grid */}
                    <div className="lg:col-span-3 grid grid-cols-2 sm:grid-cols-3 xl:grid-cols-5 gap-3">
                        {healthData.health_score !== undefined && (
                            <MetricTile
                                label="Health Score"
                                value={healthData.health_score}
                                sub="0-100 Aggregate"
                                color={healthData.health_score > 80 ? "text-green-600" : healthData.health_score > 60 ? "text-amber-600" : "text-red-600"}
                                icon={<Activity className="h-4 w-4" />}
                            />
                        )}
                        <MetricTile
                            label="Avg Confidence"
                            value={`${healthData.avg_confidence_pct}%`}
                            sub={`Across ${healthData.total_questions} questions`}
                            color="text-primary"
                            icon={<BarChart3 className="h-3 w-3" />}
                        />
                        <MetricTile
                            label="Total Approved"
                            value={healthData.total_approved}
                            sub={`of ${healthData.total_questions} answers`}
                            icon={<CheckCircle2 className="h-3 w-3" />}
                            color="text-green-700"
                        />
                        <MetricTile
                            label="Low Confidence"
                            value={healthData.total_low_conf}
                            sub="answers flagged"
                            icon={<AlertTriangle className="h-3 w-3" />}
                            color="text-red-700"
                        />
                        <MetricTile
                            label="Avg Review Time"
                            value={turnaround}
                            sub="from audit to review"
                            icon={<Clock className="h-3 w-3" />}
                            color="text-blue-700"
                        />
                        <MetricTile
                            label="Memory Reused"
                            value={healthData.memory_reuse_count}
                            sub="answers from memory"
                            icon={<Brain className="h-3 w-3" />}
                            color="text-purple-700"
                        />
                    </div>

                    {/* Low-confidence trend */}
                    {healthData.low_conf_trend.length > 0 && (
                        <div>
                            <div className="flex items-center gap-1.5 mb-2">
                                <TrendingDown className="h-3.5 w-3.5 text-muted-foreground" />
                                <p className="text-xs font-medium text-muted-foreground">
                                    Low-Confidence Rate by Run (last {healthData.low_conf_trend.length})
                                </p>
                            </div>
                            <div className="space-y-1.5">
                                {healthData.low_conf_trend.map((r) => (
                                    <TrendBar
                                        key={r.run_id}
                                        label={r.label}
                                        pct={r.low_conf_pct}
                                        total={r.total}
                                    />
                                ))}
                            </div>
                            <div className="flex items-center gap-3 mt-2 text-[10px] text-muted-foreground">
                                <span className="flex items-center gap-1"><span className="h-2 w-2 rounded-sm bg-green-500 inline-block" /> ≤10% good</span>
                                <span className="flex items-center gap-1"><span className="h-2 w-2 rounded-sm bg-amber-400 inline-block" /> 10–20% review</span>
                                <span className="flex items-center gap-1"><span className="h-2 w-2 rounded-sm bg-red-500 inline-block" /> &gt;20% risk</span>
                            </div>
                        </div>
                    )}
                </div>
            </CardContent>
        </Card>
    );
}

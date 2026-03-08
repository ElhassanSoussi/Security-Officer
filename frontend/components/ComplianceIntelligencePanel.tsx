"use client";

import { useEffect, useState } from "react";
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { ApiClient } from "@/lib/api";
import {
    ShieldCheck, AlertTriangle, Clock, CheckCircle2, Loader2, RefreshCw,
} from "lucide-react";
import Link from "next/link";

interface ComplianceOverview {
    avg_score: number | null;
    overall_risk_level: string | null;
    active_issues: number;
    expiring_documents: number;
    issues_by_severity: { high: number; medium: number; low: number };
    top_risks: Array<{
        id: string;
        issue_type: string;
        severity: string;
        description: string;
        project_id: string;
        created_at: string;
    }>;
}

interface Props {
    orgId: string;
    token?: string;
}

const RISK_COLORS: Record<string, string> = {
    low: "text-green-700 bg-green-50 border-green-200",
    medium: "text-amber-700 bg-amber-50 border-amber-200",
    high: "text-red-700 bg-red-50 border-red-200",
};

const SEVERITY_BADGE: Record<string, string> = {
    high: "bg-red-100 text-red-700 border-red-200",
    medium: "bg-amber-100 text-amber-700 border-amber-200",
    low: "bg-blue-50 text-blue-700 border-blue-200",
};

function ScoreRing({ score }: { score: number }) {
    const radius = 28;
    const circumference = 2 * Math.PI * radius;
    const filled = (score / 100) * circumference;
    const color = score >= 75 ? "#22c55e" : score >= 45 ? "#f59e0b" : "#ef4444";
    return (
        <div className="relative flex items-center justify-center w-20 h-20">
            <svg width="80" height="80" viewBox="0 0 80 80" className="-rotate-90">
                <circle cx="40" cy="40" r={radius} fill="none" stroke="hsl(var(--muted))" strokeWidth="8" />
                <circle
                    cx="40" cy="40" r={radius} fill="none"
                    stroke={color} strokeWidth="8"
                    strokeDasharray={`${filled} ${circumference}`}
                    strokeLinecap="round"
                />
            </svg>
            <div className="absolute inset-0 flex flex-col items-center justify-center">
                <span className="text-lg font-bold leading-none">{score}</span>
                <span className="text-[9px] text-muted-foreground font-medium">/ 100</span>
            </div>
        </div>
    );
}

export function ComplianceIntelligencePanel({ orgId, token }: Props) {
    const [data, setData] = useState<ComplianceOverview | null>(null);
    const [loading, setLoading] = useState(true);
    const [error, setError] = useState("");

    async function load() {
        setLoading(true);
        setError("");
        try {
            const result = await ApiClient.getComplianceOverview(orgId, token);
            setData(result);
        } catch (e: any) {
            setError("Failed to load compliance data.");
        } finally {
            setLoading(false);
        }
    }

    useEffect(() => { if (orgId) load(); }, [orgId, token]);

    if (loading) {
        return (
            <Card>
                <CardContent className="flex items-center justify-center py-10">
                    <Loader2 className="h-6 w-6 animate-spin text-muted-foreground" />
                </CardContent>
            </Card>
        );
    }

    if (error || !data) {
        return (
            <Card className="border-red-200 bg-red-50/40">
                <CardContent className="pt-5 text-sm text-red-700 flex items-center gap-2">
                    <AlertTriangle className="h-4 w-4 shrink-0" />
                    {error || "Compliance data unavailable."}
                </CardContent>
            </Card>
        );
    }

    const riskLevel = data.overall_risk_level || "low";
    const score = data.avg_score;
    const noData = score === null && data.active_issues === 0 && data.expiring_documents === 0;

    if (noData) {
        return (
            <Card>
                <CardHeader className="pb-3">
                    <CardTitle className="flex items-center gap-2 text-base">
                        <ShieldCheck className="h-4 w-4 text-blue-600" /> Compliance Intelligence
                    </CardTitle>
                    <CardDescription>No compliance scans have been run yet.</CardDescription>
                </CardHeader>
                <CardContent className="text-sm text-muted-foreground pb-5">
                    Upload documents and run a scan on any project to generate compliance insights.
                </CardContent>
            </Card>
        );
    }

    return (
        <Card>
            <CardHeader className="pb-3">
                <div className="flex items-center justify-between flex-wrap gap-2">
                    <div className="flex items-center gap-2">
                        <ShieldCheck className="h-4 w-4 text-blue-600" />
                        <CardTitle className="text-base">Compliance Intelligence</CardTitle>
                    </div>
                    <div className="flex items-center gap-2">
                        {riskLevel && (
                            <span className={`text-[11px] font-medium px-2 py-0.5 rounded-full border ${RISK_COLORS[riskLevel] || RISK_COLORS.low}`}>
                                {riskLevel.charAt(0).toUpperCase() + riskLevel.slice(1)} Risk
                            </span>
                        )}
                        <Button variant="ghost" size="icon" className="h-7 w-7" onClick={load} title="Refresh">
                            <RefreshCw className="h-3.5 w-3.5" />
                        </Button>
                    </div>
                </div>
                <CardDescription>Org-level compliance posture from document analysis.</CardDescription>
            </CardHeader>

            <CardContent className="space-y-5">
                {/* Score + Summary Stats */}
                <div className="flex items-center gap-6 flex-wrap">
                    {score !== null && <ScoreRing score={score} />}
                    <div className="grid grid-cols-2 sm:grid-cols-3 gap-3 flex-1 min-w-0">
                        <div className="rounded-lg border bg-muted/30 p-3 text-center">
                            <p className="text-2xl font-bold">{data.active_issues}</p>
                            <p className="text-xs text-muted-foreground font-medium">Open Issues</p>
                        </div>
                        <div className={`rounded-lg border p-3 text-center ${data.expiring_documents > 0 ? "border-amber-200 bg-amber-50/60 text-amber-800" : "bg-muted/30"}`}>
                            <p className="text-2xl font-bold">{data.expiring_documents}</p>
                            <p className="text-xs font-medium text-muted-foreground">Expiring (60d)</p>
                        </div>
                        <div className="rounded-lg border bg-muted/30 p-3 text-center">
                            <p className="text-2xl font-bold text-red-600">{data.issues_by_severity.high}</p>
                            <p className="text-xs text-muted-foreground font-medium">High Severity</p>
                        </div>
                    </div>
                </div>

                {/* Severity breakdown bar */}
                {data.active_issues > 0 && (
                    <div>
                        <p className="text-xs font-medium text-muted-foreground mb-1.5">Issues by Severity</p>
                        <div className="flex gap-1 h-2 rounded-full overflow-hidden">
                            {data.issues_by_severity.high > 0 && (
                                <div
                                    className="bg-red-500 transition-all"
                                    style={{ flex: data.issues_by_severity.high }}
                                    title={`${data.issues_by_severity.high} high`}
                                />
                            )}
                            {data.issues_by_severity.medium > 0 && (
                                <div
                                    className="bg-amber-400 transition-all"
                                    style={{ flex: data.issues_by_severity.medium }}
                                    title={`${data.issues_by_severity.medium} medium`}
                                />
                            )}
                            {data.issues_by_severity.low > 0 && (
                                <div
                                    className="bg-blue-400 transition-all"
                                    style={{ flex: data.issues_by_severity.low }}
                                    title={`${data.issues_by_severity.low} low`}
                                />
                            )}
                        </div>
                        <div className="flex gap-4 mt-1.5 text-[10px] text-muted-foreground">
                            <span className="flex items-center gap-1"><span className="h-2 w-2 rounded-sm bg-red-500 inline-block" /> {data.issues_by_severity.high} High</span>
                            <span className="flex items-center gap-1"><span className="h-2 w-2 rounded-sm bg-amber-400 inline-block" /> {data.issues_by_severity.medium} Medium</span>
                            <span className="flex items-center gap-1"><span className="h-2 w-2 rounded-sm bg-blue-400 inline-block" /> {data.issues_by_severity.low} Low</span>
                        </div>
                    </div>
                )}

                {/* Top Risks */}
                {data.top_risks.length > 0 && (
                    <div>
                        <p className="text-xs font-medium text-muted-foreground mb-2">Top Risks</p>
                        <div className="space-y-2">
                            {data.top_risks.map((risk) => (
                                <div
                                    key={risk.id}
                                    className="flex items-start gap-2.5 rounded-md border px-3 py-2.5 text-sm"
                                >
                                    <AlertTriangle className="h-3.5 w-3.5 mt-0.5 shrink-0 text-amber-500" />
                                    <p className="flex-1 text-xs text-muted-foreground leading-relaxed line-clamp-2">
                                        {risk.description}
                                    </p>
                                    <Badge
                                        variant="outline"
                                        className={`text-[10px] px-1.5 py-0 shrink-0 ${SEVERITY_BADGE[risk.severity] || ""}`}
                                    >
                                        {risk.severity}
                                    </Badge>
                                </div>
                            ))}
                        </div>
                    </div>
                )}

                {data.active_issues === 0 && (
                    <div className="flex items-center gap-2 text-sm text-green-700 bg-green-50 border border-green-200 rounded-md px-3 py-2.5">
                        <CheckCircle2 className="h-4 w-4 shrink-0" />
                        No open compliance issues. Compliance posture is strong.
                    </div>
                )}

                <div className="flex justify-end">
                    <Link href="/intelligence">
                        <Button size="sm" variant="outline" className="h-7 text-xs">
                            View Full Report
                        </Button>
                    </Link>
                </div>
            </CardContent>
        </Card>
    );
}

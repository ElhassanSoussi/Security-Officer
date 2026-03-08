"use client";

import { useEffect, useState, useMemo } from "react";
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from "@/components/ui/card";
import { FolderKanban, FileText, PlayCircle, Clock, BarChart3, AlertTriangle, TrendingUp } from "lucide-react";
import Link from "next/link";
import { Button } from "@/components/ui/button";
import { ApiClient } from "@/lib/api";
import { DashboardStats } from "@/types";
import { createClient } from "@/utils/supabase/client";
import { useRouter } from "next/navigation";
import { getStoredOrgId, setStoredOrgId } from "@/lib/orgContext";
import PageHeader from "@/components/ui/PageHeader";
import { EmptyState } from "@/components/ui/EmptyState";
import { StatCard } from "@/components/ui/StatCard";
import { TrustBar } from "@/components/ui/TrustBar";
import { ActivityTimeline } from "@/components/ui/ActivityTimeline";
import { ConfidenceBar, MiniBarChart } from "@/components/ui/ConfidenceBar";
import { normalizeConfidenceScore } from "@/lib/confidence";
import { Badge } from "@/components/ui/badge";
import { OnboardingChecklist } from "@/components/OnboardingChecklist";
import { ComplianceHealthPanel } from "@/components/ComplianceHealthPanel";
import { ComplianceIntelligencePanel } from "@/components/ComplianceIntelligencePanel";
import { UsagePanel } from "@/components/UsagePanel";
import { isDemoMode, DEMO_STATS, DEMO_ACTIVITY, DEMO_AUDITS, DEMO_ORG_ID } from "@/lib/demo-data";

export default function Dashboard() {
    const [stats, setStats] = useState<DashboardStats | null>(null);
    const [activity, setActivity] = useState<any[]>([]);
    const [auditData, setAuditData] = useState<any[]>([]);
    const [loading, setLoading] = useState(true);
    const [error, setError] = useState("");
    const [orgId, setOrgId] = useState<string | null>(null);
    const [token, setToken] = useState<string | undefined>(undefined);
    const [demoActive, setDemoActive] = useState(false);
    const router = useRouter();

    // ── Compliance Insights (derived from audit data) ──
    const insights = useMemo(() => {
        if (!auditData.length) return null;
        let high = 0, medium = 0, low = 0, overridden = 0, noSource = 0;
        for (const a of auditData) {
            const ratio = normalizeConfidenceScore(a.confidence_score);
            if (ratio !== null) {
                if (ratio >= 0.8) high++;
                else if (ratio >= 0.5) medium++;
                else low++;
            }
            if (a.is_overridden) overridden++;
            if (!a.source_document) noSource++;
        }
        const total = auditData.length;
        const avgConf = total > 0 ? (high * 0.9 + medium * 0.65 + low * 0.3) / total : 0;
        return {
            avgConfidence: Math.round(avgConf * 100),
            lowCount: low,
            highRisk: avgConf < 0.5,
            noSource,
            overridden,
            distribution: { high, medium, low },
        };
    }, [auditData]);

    // ── Monthly trends (derived from activity timestamps) ──
    const monthlyTrends = useMemo(() => {
        const now = new Date();
        const months: { label: string; value: number }[] = [];
        for (let i = 5; i >= 0; i--) {
            const d = new Date(now.getFullYear(), now.getMonth() - i, 1);
            const label = d.toLocaleString("default", { month: "short" });
            const count = activity.filter((a: any) => {
                const ad = new Date(a.created_at);
                return ad.getMonth() === d.getMonth() && ad.getFullYear() === d.getFullYear();
            }).length;
            months.push({ label, value: count });
        }
        return months;
    }, [activity]);

    useEffect(() => {
        const loadData = async () => {
            try {
                setError("");

                if (isDemoMode()) {
                    setStats(DEMO_STATS);
                    setActivity(DEMO_ACTIVITY);
                    setAuditData(DEMO_AUDITS);
                    setOrgId(DEMO_ORG_ID);
                    setDemoActive(true);
                    setLoading(false);
                    return;
                }

                const supabase = createClient();
                const { data: { session } } = await supabase.auth.getSession();
                const token = session?.access_token;
                if (!token) {
                    router.push("/login");
                    return;
                }
                setToken(token);

                const orgs = await ApiClient.getMyOrgs(token);

                if (orgs && orgs.length > 0) {
                    const stored = getStoredOrgId() || "";
                    const selected = orgs.find((o: any) => o.id === stored) || orgs[0];
                    const orgId = selected.id;
                    setStoredOrgId(orgId);
                    setOrgId(orgId);

                    const [s, acts, audits] = await Promise.all([
                        ApiClient.getStats(orgId, token),
                        ApiClient.getActivities(orgId, 5, token),
                        ApiClient.getAuditLog(orgId, {}, token).catch(() => []),
                    ]);
                    setStats(s);
                    setActivity(acts);
                    setAuditData(Array.isArray(audits) ? audits : []);
                } else {
                    router.push("/onboarding");
                }
            } catch (e: any) {
                console.error("Failed to load dashboard data:", e);
                if (String(e?.message || "").toLowerCase().includes("unauthorized")) {
                    router.push("/login");
                    return;
                }
                setError("Failed to load dashboard data.");
                setStats({ active_projects: 0, documents_ingested: 0, runs_completed: 0 });
                setActivity([]);
            } finally {
                setLoading(false);
            }
        };
        loadData();
    }, [router]);

    const STAT_CARDS = [
        { label: "Active Projects", value: stats?.active_projects ?? "-", icon: FolderKanban, color: "text-blue-600 bg-blue-50" },
        { label: "Documents Ingested", value: stats?.documents_ingested ?? "-", icon: FileText, color: "text-purple-600 bg-purple-50" },
        { label: "Runs Completed", value: stats?.runs_completed ?? "-", icon: PlayCircle, color: "text-green-600 bg-green-50" },
    ];

    return (
        <div className="space-y-6">
            <PageHeader
                title="Dashboard"
                subtitle="Overview of your compliance automation activity."
                actions={
                    <div className="flex gap-2">
                        {!demoActive && (
                            <Button
                                variant="outline"
                                size="sm"
                                onClick={() => {
                                    window.location.href = "?demo=1";
                                }}
                            >
                                🧪 Demo
                            </Button>
                        )}
                        <Link href="/projects">
                            <Button variant="outline" size="sm">
                                <FolderKanban className="mr-2 h-4 w-4" /> Projects
                            </Button>
                        </Link>
                        <Link href="/run">
                            <Button size="sm">
                                <PlayCircle className="mr-2 h-4 w-4" /> Run Analysis
                            </Button>
                        </Link>
                    </div>
                }
            />

            {/* Demo Mode Banner */}
            {demoActive && (
                <div className="rounded-lg border border-purple-200 bg-purple-50/60 px-4 py-2.5 flex items-center gap-3">
                    <span className="text-base">🧪</span>
                    <div className="flex-1 min-w-0">
                        <p className="text-sm font-medium text-purple-800">
                            Demo Mode — <span className="font-normal text-purple-700">viewing pre-seeded data, nothing is modified.</span>
                        </p>
                    </div>
                    <Button
                        size="sm"
                        variant="outline"
                        className="shrink-0 h-7 text-xs border-purple-300 text-purple-700 hover:bg-purple-100"
                        onClick={() => {
                            window.location.href = window.location.pathname;
                        }}
                    >
                        Exit Demo
                    </Button>
                </div>
            )}

            {error && (
                <div className="rounded-lg border border-red-200 bg-red-50 px-4 py-3 text-sm text-red-700">
                    {error}
                </div>
            )}

            {/* Stats Row */}
            <div className="grid gap-4 sm:grid-cols-3">
                {STAT_CARDS.map((stat) => (
                    <StatCard
                        key={stat.label}
                        label={stat.label}
                        value={stat.value}
                        icon={<stat.icon className="h-5 w-5" />}
                        iconClassName={stat.color}
                        loading={loading}
                    />
                ))}
            </div>

            {/* Trust Bar */}
            <TrustBar />

            {/* Two-column layout: Getting Started + Recent Activity */}
            <div className="grid gap-6 lg:grid-cols-2">
                {/* Onboarding Checklist */}
                <OnboardingChecklist
                    scopeId={orgId || "global"}
                    derivedFrom={{
                        hasProject: (stats?.active_projects || 0) > 0,
                        hasDocuments: (stats?.documents_ingested || 0) > 0,
                        hasRun: (stats?.runs_completed || 0) > 0,
                        hasReviewActivity: activity.some((a) =>
                            String(a.event_type || "").includes("review")
                        ),
                        hasExport: activity.some((a) =>
                            String(a.event_type || "").includes("export")
                        ),
                    }}
                    title="Getting Started"
                />

                {/* Recent Activity */}
                <Card>
                    <CardHeader className="pb-3">
                        <CardTitle className="text-base">Recent Activity</CardTitle>
                        <CardDescription>Latest actions across all projects.</CardDescription>
                    </CardHeader>
                    <CardContent>
                        {loading && <ActivityTimeline activities={[]} loading={true} />}

                        {!loading && activity.length === 0 && (
                            <EmptyState
                                icon={<Clock className="h-10 w-10" />}
                                title="No recent activity"
                                description="Start by creating a project or running a questionnaire."
                                action={<Link href="/projects"><Button size="sm" variant="outline">Get Started</Button></Link>}
                            />
                        )}

                        {!loading && activity.length > 0 && (
                            <ActivityTimeline
                                activities={activity}
                                maxItems={5}
                                showUserAttribution={true}
                            />
                        )}
                    </CardContent>
                </Card>
            </div>

            {/* Compliance Insights */}
            {!loading && insights && (
                <Card>
                    <CardHeader className="pb-3">
                        <div className="flex items-center justify-between">
                            <div>
                                <CardTitle className="flex items-center gap-2 text-base">
                                    <BarChart3 className="h-4 w-4 text-blue-600" /> Compliance Insights
                                </CardTitle>
                                <CardDescription>Confidence overview and risk indicators across all runs.</CardDescription>
                            </div>
                            <Link href="/intelligence">
                                <Button size="sm" variant="outline" className="h-7 text-xs gap-1">
                                    <TrendingUp className="h-3 w-3" /> Full Report
                                </Button>
                            </Link>
                        </div>
                    </CardHeader>
                    <CardContent className="space-y-5">
                        {/* Confidence Overview */}
                        <div className="grid gap-4 sm:grid-cols-3">
                            <div className="rounded-lg border bg-muted/30 p-3 text-center">
                                <p className="text-2xl font-bold">{insights.avgConfidence}%</p>
                                <p className="text-xs text-muted-foreground font-medium">Avg Confidence</p>
                            </div>
                            <div className="rounded-lg border border-amber-200 bg-amber-50/60 p-3 text-center text-amber-700">
                                <p className="text-2xl font-bold">{insights.lowCount}</p>
                                <p className="text-xs font-medium">Low Confidence</p>
                            </div>
                            <div className={`rounded-lg border p-3 text-center ${insights.highRisk ? "border-red-200 bg-red-50/60 text-red-700" : "border-green-200 bg-green-50/60 text-green-700"}`}>
                                <p className="text-2xl font-bold">{insights.highRisk ? "⚠" : "✓"}</p>
                                <p className="text-xs font-medium">{insights.highRisk ? "High Risk" : "Low Risk"}</p>
                            </div>
                        </div>

                        <ConfidenceBar
                            segments={[
                                { label: "High", value: insights.distribution.high, color: "bg-green-500" },
                                { label: "Medium", value: insights.distribution.medium, color: "bg-amber-400" },
                                { label: "Low", value: insights.distribution.low, color: "bg-red-400" },
                            ]}
                        />

                        {/* Risk Indicators */}
                        <div className="grid gap-3 sm:grid-cols-3">
                            <div className="flex items-center gap-2 rounded-md border px-3 py-2">
                                <AlertTriangle className="h-4 w-4 text-amber-500 shrink-0" />
                                <div className="text-xs">
                                    <span className="font-semibold text-foreground">{insights.lowCount}</span>
                                    <span className="text-muted-foreground"> below 0.6 confidence</span>
                                </div>
                            </div>
                            <div className="flex items-center gap-2 rounded-md border px-3 py-2">
                                <FileText className="h-4 w-4 text-muted-foreground shrink-0" />
                                <div className="text-xs">
                                    <span className="font-semibold text-foreground">{insights.noSource}</span>
                                    <span className="text-muted-foreground"> missing doc references</span>
                                </div>
                            </div>
                            <div className="flex items-center gap-2 rounded-md border px-3 py-2">
                                <Badge variant="outline" className="text-[10px] px-1.5 py-0 border-purple-200 text-purple-700 bg-purple-50">Edited</Badge>
                                <div className="text-xs">
                                    <span className="font-semibold text-foreground">{insights.overridden}</span>
                                    <span className="text-muted-foreground"> manually overridden</span>
                                </div>
                            </div>
                        </div>

                        {/* Activity Trends */}
                        <div>
                            <p className="text-xs font-medium text-muted-foreground mb-2">Activity Trend (last 6 months)</p>
                            <MiniBarChart data={monthlyTrends} barColor="bg-primary" maxHeight={48} />
                        </div>
                    </CardContent>
                </Card>
            )}

            {/* Compliance Health Panel */}
            {!loading && !demoActive && orgId && (
                <ComplianceHealthPanel orgId={orgId} token={token} />
            )}

            {/* Compliance Intelligence Panel */}
            {!loading && !demoActive && orgId && (
                <ComplianceIntelligencePanel orgId={orgId} token={token} />
            )}

            {/* Usage Panel */}
            {!loading && !demoActive && orgId && (
                <UsagePanel orgId={orgId} token={token} />
            )}
        </div>
    );
}

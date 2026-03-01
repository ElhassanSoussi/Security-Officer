"use client";

/**
 * Phase 22 — Sales Analytics Admin Page (/admin/sales)
 *
 * Admin-only dashboard displaying sales metrics from GET /admin/sales-analytics.
 * Shows: total_leads, enterprise_interest_count, conversion_rate,
 *        active_subscriptions, trial_count, paid_count, mrr_estimate.
 */

import { useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import Link from "next/link";
import {
    BarChart3,
    Users,
    Building2,
    TrendingUp,
    DollarSign,
    Clock,
    CheckCircle2,
    Loader2,
    AlertTriangle,
    RefreshCw,
    ArrowLeft,
} from "lucide-react";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { ApiClient } from "@/lib/api";
import { createClient } from "@/utils/supabase/client";
import PageHeader from "@/components/ui/PageHeader";

interface SalesAnalytics {
    total_leads: number;
    enterprise_interest_count: number;
    active_subscriptions: number;
    trial_count: number;
    paid_count: number;
    conversion_rate: number;
    mrr_estimate: number;
}

function MetricCard({
    title,
    value,
    icon: Icon,
    subtitle,
    accent = "text-slate-900",
}: {
    title: string;
    value: string | number;
    icon: React.ElementType;
    subtitle?: string;
    accent?: string;
}) {
    return (
        <Card>
            <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
                <CardTitle className="text-sm font-medium text-slate-600">{title}</CardTitle>
                <Icon className="h-4 w-4 text-slate-400" />
            </CardHeader>
            <CardContent>
                <div className={`text-2xl font-bold ${accent}`}>{value}</div>
                {subtitle && (
                    <p className="text-xs text-muted-foreground mt-1">{subtitle}</p>
                )}
            </CardContent>
        </Card>
    );
}

export default function SalesAnalyticsPage() {
    const [data, setData] = useState<SalesAnalytics | null>(null);
    const [loading, setLoading] = useState(true);
    const [error, setError] = useState<string | null>(null);
    const router = useRouter();

    async function loadAnalytics() {
        setLoading(true);
        setError(null);
        try {
            const supabase = createClient();
            const { data: { session } } = await supabase.auth.getSession();
            if (!session?.access_token) {
                router.push("/login");
                return;
            }
            const analytics = await ApiClient.getSalesAnalytics(session.access_token);
            setData(analytics);
        } catch (e: any) {
            const msg = e?.message ?? "Failed to load analytics";
            if (msg.toLowerCase().includes("403") || msg.toLowerCase().includes("admin")) {
                setError("Admin access required. You must be an org owner or admin to view this page.");
            } else if (msg.toLowerCase().includes("unauthorized")) {
                router.push("/login");
                return;
            } else {
                setError(msg);
            }
        } finally {
            setLoading(false);
        }
    }

    useEffect(() => {
        loadAnalytics();
        // eslint-disable-next-line react-hooks/exhaustive-deps
    }, []);

    if (loading) {
        return (
            <div className="flex items-center justify-center h-96">
                <Loader2 className="animate-spin h-8 w-8 text-muted-foreground" />
            </div>
        );
    }

    return (
        <div className="p-8 max-w-7xl mx-auto space-y-8">
            {/* Back link */}
            <Link href="/admin" className="inline-flex items-center gap-1.5 text-sm text-slate-500 hover:text-slate-700">
                <ArrowLeft className="h-3.5 w-3.5" />
                Back to Operator Center
            </Link>

            <PageHeader
                title="Sales Analytics"
                subtitle="Lead generation, trial conversions, and revenue metrics."
                actions={
                    <div className="flex items-center gap-2">
                        <Badge variant="outline" className="text-xs">Admin Only</Badge>
                        <Button
                            variant="outline"
                            size="sm"
                            onClick={loadAnalytics}
                            disabled={loading}
                            className="gap-1.5"
                        >
                            <RefreshCw className={`h-3.5 w-3.5 ${loading ? "animate-spin" : ""}`} />
                            Refresh
                        </Button>
                    </div>
                }
            />

            {error && (
                <div className="flex items-center gap-2.5 rounded-lg border border-red-200 bg-red-50 px-4 py-3 text-sm text-red-800">
                    <AlertTriangle className="h-4 w-4 shrink-0" />
                    {error}
                </div>
            )}

            {data && (
                <>
                    {/* ── Metrics grid ── */}
                    <div className="grid gap-4 md:grid-cols-2 lg:grid-cols-4">
                        <MetricCard
                            title="Total Leads"
                            value={data.total_leads}
                            icon={Users}
                            subtitle="From contact form + enterprise interest"
                        />
                        <MetricCard
                            title="Enterprise Interest"
                            value={data.enterprise_interest_count}
                            icon={Building2}
                            subtitle="Enterprise plan CTA clicks"
                            accent="text-violet-700"
                        />
                        <MetricCard
                            title="Conversion Rate"
                            value={`${data.conversion_rate}%`}
                            icon={TrendingUp}
                            subtitle="Trial → Paid conversion"
                            accent={data.conversion_rate >= 20 ? "text-emerald-700" : "text-amber-700"}
                        />
                        <MetricCard
                            title="MRR Estimate"
                            value={`$${data.mrr_estimate.toLocaleString()}`}
                            icon={DollarSign}
                            subtitle="Monthly recurring revenue"
                            accent="text-emerald-700"
                        />
                    </div>

                    {/* ── Subscription breakdown ── */}
                    <Card>
                        <CardHeader>
                            <CardTitle className="text-base flex items-center gap-2">
                                <BarChart3 className="h-4 w-4 text-slate-500" />
                                Subscription Breakdown
                            </CardTitle>
                        </CardHeader>
                        <CardContent>
                            <div className="grid gap-6 sm:grid-cols-3">
                                <div className="text-center p-4 rounded-lg bg-slate-50 border">
                                    <div className="text-3xl font-bold text-slate-900">{data.active_subscriptions}</div>
                                    <div className="text-sm text-slate-600 mt-1 flex items-center justify-center gap-1.5">
                                        <CheckCircle2 className="h-3.5 w-3.5 text-emerald-500" />
                                        Active Subscriptions
                                    </div>
                                </div>
                                <div className="text-center p-4 rounded-lg bg-blue-50/50 border border-blue-100">
                                    <div className="text-3xl font-bold text-blue-700">{data.trial_count}</div>
                                    <div className="text-sm text-slate-600 mt-1 flex items-center justify-center gap-1.5">
                                        <Clock className="h-3.5 w-3.5 text-blue-500" />
                                        Active Trials
                                    </div>
                                </div>
                                <div className="text-center p-4 rounded-lg bg-emerald-50/50 border border-emerald-100">
                                    <div className="text-3xl font-bold text-emerald-700">{data.paid_count}</div>
                                    <div className="text-sm text-slate-600 mt-1 flex items-center justify-center gap-1.5">
                                        <DollarSign className="h-3.5 w-3.5 text-emerald-500" />
                                        Paid Customers
                                    </div>
                                </div>
                            </div>
                        </CardContent>
                    </Card>

                    {/* ── Quick insights ── */}
                    <Card>
                        <CardHeader>
                            <CardTitle className="text-base">Quick Insights</CardTitle>
                        </CardHeader>
                        <CardContent className="space-y-3">
                            {data.total_leads > 0 && (
                                <div className="flex items-center gap-2 text-sm">
                                    <Badge variant="outline" className="text-xs bg-blue-50 text-blue-700 border-blue-200">Leads</Badge>
                                    <span className="text-slate-700">
                                        {data.total_leads} total lead{data.total_leads !== 1 ? "s" : ""} captured
                                        {data.enterprise_interest_count > 0 && (
                                            <>, including {data.enterprise_interest_count} enterprise interest signal{data.enterprise_interest_count !== 1 ? "s" : ""}</>
                                        )}
                                    </span>
                                </div>
                            )}
                            {data.trial_count > 0 && (
                                <div className="flex items-center gap-2 text-sm">
                                    <Badge variant="outline" className="text-xs bg-amber-50 text-amber-700 border-amber-200">Trials</Badge>
                                    <span className="text-slate-700">
                                        {data.trial_count} active trial{data.trial_count !== 1 ? "s" : ""} — consider targeted follow-up emails.
                                    </span>
                                </div>
                            )}
                            {data.conversion_rate > 0 && (
                                <div className="flex items-center gap-2 text-sm">
                                    <Badge variant="outline" className="text-xs bg-emerald-50 text-emerald-700 border-emerald-200">Growth</Badge>
                                    <span className="text-slate-700">
                                        {data.conversion_rate}% trial-to-paid conversion rate
                                        {data.conversion_rate >= 20 ? " — strong performance." : " — consider improving onboarding flow."}
                                    </span>
                                </div>
                            )}
                            {data.total_leads === 0 && data.trial_count === 0 && (
                                <p className="text-sm text-slate-500">No leads or trial data yet. Metrics will populate as users interact with the platform.</p>
                            )}
                        </CardContent>
                    </Card>
                </>
            )}
        </div>
    );
}

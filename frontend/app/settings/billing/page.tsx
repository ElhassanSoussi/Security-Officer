"use client";

/*
 * Plans & Billing — /settings/billing
 *
 * Tabs:
 *   Overview   — Current Plan, Usage, Plan Comparison, Manage Billing
 *   Analytics  — Upgrade funnel: Limit Hits, Modal Opens, Clicks, Conversions + resource bar chart
 */

import { useEffect, useRef, useState, useCallback } from "react";
import { useSearchParams } from "next/navigation";
import Link from "next/link";
import {
    CreditCard,
    CheckCircle2,
    XCircle,
    Clock,
    Zap,
    AlertTriangle,
    BarChart2,
    RefreshCw,
    ExternalLink,
    ArrowUpRight,
    Table2,
    TrendingUp,
    MousePointerClick,
    Eye,
    Award,
} from "lucide-react";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from "@/components/ui/card";
import { ApiClient } from "@/lib/api";
import { createClient } from "@/utils/supabase/client";

// ─── Types ─────────────────────────────────────────────────────────────────

interface AnalyticsData {
    limit_hits: number;
    modal_shown: number;
    upgrade_clicks: number;
    conversions: number;
    top_resource: string | null;
    resource_hits: Record<string, number>;
}

interface BillingSummary {
    plan: string;
    subscription_status: string;
    stripe_price_id: string | null;
    current_period_end: string | null;
    billing_configured: boolean;
    has_stripe: boolean;
    usage: {
        documents_used: number;
        documents_limit: number | null;
        projects_used: number;
        projects_limit: number | null;
        runs_used: number;
        runs_limit: number | null;
    };
}

// ─── Tier display config ────────────────────────────────────────────────────

const TIER_DISPLAY: Record<string, { label: string; color: string }> = {
    starter: { label: "Starter", color: "bg-slate-100 text-slate-700 border-slate-200" },
    growth:  { label: "Growth",  color: "bg-blue-100 text-blue-800 border-blue-200" },
    elite:   { label: "Elite",   color: "bg-violet-100 text-violet-800 border-violet-200" },
};

const STATUS_DISPLAY: Record<string, { label: string; color: string; icon: React.ReactNode }> = {
    active:      { label: "Active",      color: "bg-emerald-100 text-emerald-800 border-emerald-200", icon: <CheckCircle2 className="h-3 w-3" /> },
    trialing:    { label: "Trialing",    color: "bg-blue-100 text-blue-800 border-blue-200",          icon: <Clock className="h-3 w-3" /> },
    past_due:    { label: "Past Due",    color: "bg-amber-100 text-amber-800 border-amber-200",       icon: <AlertTriangle className="h-3 w-3" /> },
    canceled:    { label: "Canceled",    color: "bg-red-100 text-red-800 border-red-200",             icon: <XCircle className="h-3 w-3" /> },
    unpaid:      { label: "Unpaid",      color: "bg-red-100 text-red-800 border-red-200",             icon: <XCircle className="h-3 w-3" /> },
    incomplete:  { label: "Incomplete",  color: "bg-slate-100 text-slate-700 border-slate-200",       icon: <AlertTriangle className="h-3 w-3" /> },
};

// ─── Components ──────────────────────────────────────────────────────────────

function PlanBadge({ plan }: { plan: string }) {
    const tier = TIER_DISPLAY[plan.toLowerCase()] ?? TIER_DISPLAY.starter;
    return (
        <Badge variant="outline" className={`gap-1 text-xs font-semibold ${tier.color}`}>
            <Zap className="h-3 w-3" />
            {tier.label}
        </Badge>
    );
}

function StatusBadge({ status }: { status: string }) {
    const s = STATUS_DISPLAY[status] ?? { label: status, color: "bg-slate-100 text-slate-700 border-slate-200", icon: null };
    return (
        <Badge variant="outline" className={`gap-1 ${s.color}`}>
            {s.icon}
            {s.label}
        </Badge>
    );
}

function UsageBar({ label, used, limit }: { label: string; used: number; limit: number | null }) {
    const isUnlimited = limit === null;
    const pct = isUnlimited ? 0 : limit > 0 ? Math.min(100, Math.round((used / limit) * 100)) : 0;
    const atLimit = !isUnlimited && limit > 0 && used >= limit;
    const nearLimit = !isUnlimited && limit > 0 && pct >= 85;
    const barColor = atLimit ? "bg-red-500" : nearLimit ? "bg-amber-400" : "bg-primary";
    const barRef = useRef<HTMLDivElement>(null);

    // Set width imperatively to avoid inline style JSX prop
    useEffect(() => {
        if (barRef.current) {
            barRef.current.style.width = isUnlimited ? "2%" : `${Math.max(pct, 2)}%`;
        }
    }, [isUnlimited, pct]);

    return (
        <div className="space-y-1.5">
            <div className="flex justify-between text-sm">
                <span className="text-muted-foreground">{label}</span>
                <span className={`font-medium ${atLimit ? "text-red-600" : "text-foreground"}`}>
                    {used.toLocaleString()}
                    {isUnlimited ? (
                        <span className="text-muted-foreground font-normal"> / Unlimited</span>
                    ) : (
                        <span className="text-muted-foreground font-normal"> / {limit!.toLocaleString()}</span>
                    )}
                </span>
            </div>
            <div className="h-2 rounded-full bg-muted overflow-hidden">
                <div
                    ref={barRef}
                    className={`h-full rounded-full transition-all duration-500 ${barColor}`}
                />
            </div>
            {atLimit && (
                <p className="text-xs text-red-600 flex items-center gap-1">
                    <AlertTriangle className="h-3 w-3" />
                    Limit reached — upgrade to continue
                </p>
            )}
        </div>
    );
}

// ─── Analytics Tab Components ────────────────────────────────────────────────

const RESOURCE_LABELS: Record<string, string> = {
    projects: "Projects",
    documents: "Documents",
    runs: "Analysis Runs",
};

function MetricCard({
    label,
    value,
    icon,
    sub,
    accent,
}: {
    label: string;
    value: number | string;
    icon: React.ReactNode;
    sub?: string;
    accent?: string;
}) {
    return (
        <Card>
            <CardContent className="pt-5 pb-4">
                <div className="flex items-start justify-between gap-3">
                    <div className="space-y-1">
                        <p className="text-xs text-muted-foreground uppercase tracking-wider font-medium">{label}</p>
                        <p className={`text-3xl font-bold tabular-nums ${accent ?? "text-foreground"}`}>{value}</p>
                        {sub && <p className="text-xs text-muted-foreground">{sub}</p>}
                    </div>
                    <div className="rounded-lg bg-muted p-2 shrink-0">{icon}</div>
                </div>
            </CardContent>
        </Card>
    );
}

function ResourceBar({ label, count, max }: { label: string; count: number; max: number }) {
    const pct = max > 0 ? Math.round((count / max) * 100) : 0;
    const barRef = useRef<HTMLDivElement>(null);
    useEffect(() => {
        if (barRef.current) barRef.current.style.width = `${Math.max(pct, 2)}%`;
    }, [pct]);
    return (
        <div className="space-y-1">
            <div className="flex justify-between text-sm">
                <span className="text-muted-foreground">{RESOURCE_LABELS[label] ?? label}</span>
                <span className="font-semibold tabular-nums">{count.toLocaleString()}</span>
            </div>
            <div className="h-3 rounded-full bg-muted overflow-hidden">
                <div ref={barRef} className="h-full rounded-full bg-primary transition-all duration-500" />
            </div>
        </div>
    );
}

function AnalyticsTab({ data, loading }: { data: AnalyticsData | null; loading: boolean }) {
    const conversionRate =
        data && data.modal_shown > 0
            ? ((data.conversions / data.modal_shown) * 100).toFixed(1)
            : "0.0";

    const maxHits = data
        ? Math.max(...Object.values(data.resource_hits), 1)
        : 1;

    if (loading) {
        return (
            <div className="space-y-4 animate-pulse">
                <div className="grid grid-cols-2 gap-4">
                    {[0, 1, 2, 3].map((i) => (
                        <div key={i} className="h-28 rounded-xl bg-muted" />
                    ))}
                </div>
                <div className="h-40 rounded-xl bg-muted" />
            </div>
        );
    }

    return (
        <div className="space-y-6">
            {/* Metric Cards */}
            <div className="grid grid-cols-2 gap-4">
                <MetricCard
                    label="Limit Hits"
                    value={data?.limit_hits ?? 0}
                    icon={<AlertTriangle className="h-5 w-5 text-amber-500" />}
                    sub="Last 30 days"
                    accent="text-amber-600"
                />
                <MetricCard
                    label="Modal Opens"
                    value={data?.modal_shown ?? 0}
                    icon={<Eye className="h-5 w-5 text-blue-500" />}
                    sub="Upgrade prompts shown"
                />
                <MetricCard
                    label="Upgrade Clicks"
                    value={data?.upgrade_clicks ?? 0}
                    icon={<MousePointerClick className="h-5 w-5 text-violet-500" />}
                    sub="Portal redirects initiated"
                />
                <MetricCard
                    label="Conversion Rate"
                    value={`${conversionRate}%`}
                    icon={<Award className="h-5 w-5 text-emerald-500" />}
                    sub={`${data?.conversions ?? 0} plan upgrade${(data?.conversions ?? 0) !== 1 ? "s" : ""}`}
                    accent={(data?.conversions ?? 0) > 0 ? "text-emerald-600" : undefined}
                />
            </div>

            {/* Resource Hit Frequency */}
            <Card>
                <CardHeader>
                    <CardTitle className="text-base flex items-center gap-2">
                        <TrendingUp className="h-4 w-4 text-muted-foreground" />
                        Resource Hit Frequency
                    </CardTitle>
                    <CardDescription>
                        Which limits triggered the most upgrade prompts in the last 30 days.
                    </CardDescription>
                </CardHeader>
                <CardContent className="space-y-4">
                    {data && Object.keys(data.resource_hits).length > 0 ? (
                        Object.entries(data.resource_hits)
                            .sort(([, a], [, b]) => b - a)
                            .map(([resource, count]) => (
                                <ResourceBar
                                    key={resource}
                                    label={resource}
                                    count={count}
                                    max={maxHits}
                                />
                            ))
                    ) : (
                        <div className="flex flex-col items-center justify-center py-10 text-center text-muted-foreground">
                            <BarChart2 className="h-10 w-10 mb-3 opacity-30" />
                            <p className="text-sm font-medium">No limit events in the last 30 days</p>
                            <p className="text-xs mt-1">Data appears here when users hit plan limits.</p>
                        </div>
                    )}
                </CardContent>
            </Card>

            {/* Funnel Summary */}
            {data && (data.limit_hits > 0 || data.modal_shown > 0) && (
                <Card>
                    <CardHeader>
                        <CardTitle className="text-base flex items-center gap-2">
                            <Zap className="h-4 w-4 text-muted-foreground" />
                            Funnel Overview
                        </CardTitle>
                    </CardHeader>
                    <CardContent>
                        <div className="flex items-center gap-2 text-sm flex-wrap">
                            {[
                                { label: "Limit Hit", val: data.limit_hits, color: "bg-amber-100 text-amber-700 border-amber-200" },
                                { label: "→ Modal Shown", val: data.modal_shown, color: "bg-blue-100 text-blue-700 border-blue-200" },
                                { label: "→ Clicked Upgrade", val: data.upgrade_clicks, color: "bg-violet-100 text-violet-700 border-violet-200" },
                                { label: "→ Converted", val: data.conversions, color: "bg-emerald-100 text-emerald-700 border-emerald-200" },
                            ].map(({ label, val, color }) => (
                                <div key={label} className={`flex items-center gap-1.5 rounded-full border px-3 py-1 font-medium ${color}`}>
                                    <span className="text-xs">{label}</span>
                                    <span className="tabular-nums font-bold">{val}</span>
                                </div>
                            ))}
                        </div>
                    </CardContent>
                </Card>
            )}
        </div>
    );
}

// ─── Plan Comparison Table ───────────────────────────────────────────────────

interface PlanCol {
    id: string;
    label: string;
    price: string;
    projects: string;
    documents: string;
    runs: string;
    color: string;
    recommended?: boolean;
}

const PLAN_COLS: PlanCol[] = [
    {
        id: "starter",
        label: "Starter",
        price: "$149/mo",
        projects: "5",
        documents: "25",
        runs: "10 / month",
        color: "border-slate-200",
    },
    {
        id: "growth",
        label: "Growth",
        price: "$499/mo",
        projects: "25",
        documents: "500",
        runs: "100 / month",
        color: "border-blue-300",
    },
    {
        id: "elite",
        label: "Elite",
        price: "$1,499/mo",
        projects: "10,000",
        documents: "100,000",
        runs: "10,000 / month",
        color: "border-violet-300",
    },
];

const PLAN_HEADER_CLASS: Record<string, string> = {
    starter: "bg-slate-50 text-slate-700",
    growth:  "bg-blue-50 text-blue-800",
    elite:   "bg-violet-50 text-violet-800",
};

const PLAN_CURRENT_RING: Record<string, string> = {
    starter: "ring-2 ring-slate-400",
    growth:  "ring-2 ring-blue-500",
    elite:   "ring-2 ring-violet-500",
};

function PlanComparisonTable({ currentPlan, nextPlan }: { currentPlan: string; nextPlan: string | null }) {
    const rows = [
        { label: "Projects",           key: "projects" as keyof PlanCol },
        { label: "Documents",          key: "documents" as keyof PlanCol },
        { label: "Analysis Runs",      key: "runs" as keyof PlanCol },
        { label: "Price",              key: "price" as keyof PlanCol },
    ];

    return (
        <Card>
            <CardHeader>
                <CardTitle className="text-base flex items-center gap-2">
                    <Table2 className="h-4 w-4 text-muted-foreground" />
                    Plan Comparison
                </CardTitle>
                <CardDescription>
                    Limits across all tiers — your current plan is highlighted.
                </CardDescription>
            </CardHeader>
            <CardContent className="overflow-x-auto">
                <table className="w-full text-sm border-separate border-spacing-0">
                    <thead>
                        <tr>
                            <th className="text-left py-2 pr-4 text-xs text-muted-foreground font-medium w-28" />
                            {PLAN_COLS.map((col) => {
                                const isCurrent = col.id === currentPlan;
                                const isNext    = col.id === nextPlan;
                                return (
                                    <th
                                        key={col.id}
                                        className={`
                                            text-center py-2 px-4 rounded-t-lg font-semibold text-xs uppercase tracking-wide
                                            ${PLAN_HEADER_CLASS[col.id]}
                                            ${isCurrent ? PLAN_CURRENT_RING[col.id] : ""}
                                        `}
                                    >
                                        <div className="flex flex-col items-center gap-1">
                                            {col.label}
                                            {isCurrent && (
                                                <span className="text-[10px] font-medium px-1.5 py-0.5 rounded-full bg-white/70 border border-current opacity-80">
                                                    Current
                                                </span>
                                            )}
                                            {isNext && !isCurrent && (
                                                <span className="text-[10px] font-medium px-1.5 py-0.5 rounded-full bg-white/70 border border-blue-400 text-blue-700">
                                                    Recommended
                                                </span>
                                            )}
                                        </div>
                                    </th>
                                );
                            })}
                        </tr>
                    </thead>
                    <tbody>
                        {rows.map(({ label, key }, rowIdx) => (
                            <tr key={key} className={rowIdx % 2 === 0 ? "bg-muted/30" : ""}>
                                <td className="py-2.5 pr-4 text-muted-foreground font-medium text-xs">{label}</td>
                                {PLAN_COLS.map((col) => {
                                    const isCurrent = col.id === currentPlan;
                                    return (
                                        <td
                                            key={col.id}
                                            className={`
                                                text-center py-2.5 px-4 font-medium
                                                ${isCurrent ? "text-foreground" : "text-muted-foreground"}
                                            `}
                                        >
                                            {col[key]}
                                        </td>
                                    );
                                })}
                            </tr>
                        ))}
                    </tbody>
                </table>
            </CardContent>
        </Card>
    );
}

// ─── Page ────────────────────────────────────────────────────────────────────

export default function BillingPage() {
    const searchParams = useSearchParams();
    const checkoutResult = searchParams.get("checkout");
    const stripeReturn   = searchParams.get("stripe_return") === "1";

    const [activeTab, setActiveTab] = useState<"overview" | "analytics">("overview");
    const [loading, setLoading] = useState(true);
    const [analyticsLoading, setAnalyticsLoading] = useState(false);
    const [portalLoading, setPortalLoading] = useState(false);
    const [error, setError] = useState<string | null>(null);
    const [data, setData] = useState<BillingSummary | null>(null);
    const [analytics, setAnalytics] = useState<AnalyticsData | null>(null);
    const [orgId, setOrgId] = useState<string | null>(null);
    const [stripeReturnToast, setStripeReturnToast] = useState<"upgraded" | "unchanged" | null>(null);

    const load = useCallback(async () => {
        setLoading(true);
        setError(null);
        try {
            const supabase = createClient();
            const { data: { session } } = await supabase.auth.getSession();
            const tok = session?.access_token;
            const org = await ApiClient.getCurrentOrg(tok);
            const oid: string = org?.id;
            setOrgId(oid);
            const summary = await ApiClient.getBillingSummary(oid, tok);
            setData(summary);
            return { oid, tok, summary };
        } catch (e: any) {
            setError(e?.message ?? "Failed to load billing data");
            return null;
        } finally {
            setLoading(false);
        }
    }, []);

    const loadAnalytics = useCallback(async (oid: string, tok?: string) => {
        setAnalyticsLoading(true);
        try {
            const result = await ApiClient.getUpgradeAnalytics(oid, tok);
            setAnalytics(result);
        } catch {
            // non-fatal
        } finally {
            setAnalyticsLoading(false);
        }
    }, []);

    // On mount: load billing; also handle Stripe portal return
    useEffect(() => {
        load().then(async (ctx) => {
            if (!ctx) return;
            const { oid, tok, summary } = ctx;

            // Always pre-load analytics in background
            loadAnalytics(oid, tok);

            if (stripeReturn) {
                // Log stripe_portal_returned
                try {
                    await ApiClient.logUpgradeEvent("stripe_portal_returned", oid, tok, {
                        plan: summary.plan,
                    });
                } catch { /* best-effort */ }

                // Detect plan change: if plan is no longer starter show "upgraded" toast
                const prevPlan = sessionStorage.getItem("nyccompliance:billing:plan_before_portal");
                if (prevPlan && prevPlan !== summary.plan) {
                    setStripeReturnToast("upgraded");
                } else {
                    setStripeReturnToast("unchanged");
                }
                sessionStorage.removeItem("nyccompliance:billing:plan_before_portal");
            }
        });
    // eslint-disable-next-line react-hooks/exhaustive-deps
    }, []);

    // When the user clicks Manage Billing, save current plan before redirect
    const handleManageBilling = async () => {
        if (!orgId) return;
        if (data?.plan) {
            try { sessionStorage.setItem("nyccompliance:billing:plan_before_portal", data.plan); } catch { /* ignore */ }
        }
        setPortalLoading(true);
        try {
            const result = await ApiClient.createPortalSessionV2(orgId);
            if (result.url) window.location.href = result.url;
        } catch (e: any) {
            setError(e?.message ?? "Could not open billing portal. You may need to subscribe to a plan first.");
        } finally {
            setPortalLoading(false);
        }
    };

    const handleTabChange = (tab: "overview" | "analytics") => {
        setActiveTab(tab);
        if (tab === "analytics" && orgId && !analytics) {
            createClient().auth.getSession().then(
                (r: { data: { session: { access_token: string } | null }}) =>
                    loadAnalytics(orgId, r.data.session?.access_token)
            );
        }
    };

    const plan = data?.plan?.toLowerCase() ?? "starter";
    const isElite = plan === "elite";
    const nextPlan = plan === "starter" ? "growth" : plan === "growth" ? "elite" : null;
    const renewalDate = data?.current_period_end
        ? new Date(data.current_period_end).toLocaleDateString("en-US", {
            year: "numeric", month: "long", day: "numeric",
          })
        : null;

    return (
        <div className="max-w-3xl space-y-6">
            {/* Stripe return toasts */}
            {stripeReturnToast === "upgraded" && (
                <div className="flex items-center gap-2.5 rounded-lg border border-emerald-200 bg-emerald-50 px-4 py-3 text-sm text-emerald-800">
                    <CheckCircle2 className="h-4 w-4 shrink-0" />
                    Plan upgraded successfully. Your new limits are now active.
                    <Button variant="ghost" size="sm" className="ml-auto text-xs" onClick={() => setStripeReturnToast(null)}>✕</Button>
                </div>
            )}
            {stripeReturnToast === "unchanged" && (
                <div className="flex items-center gap-2.5 rounded-lg border border-slate-200 bg-slate-50 px-4 py-3 text-sm text-slate-700">
                    <RefreshCw className="h-4 w-4 shrink-0" />
                    You&apos;ve returned from the billing portal. No plan change detected.
                    <Button variant="ghost" size="sm" className="ml-auto text-xs" onClick={() => setStripeReturnToast(null)}>✕</Button>
                </div>
            )}

            {/* Checkout result banners */}
            {checkoutResult === "success" && (
                <div className="flex items-center gap-2.5 rounded-lg border border-emerald-200 bg-emerald-50 px-4 py-3 text-sm text-emerald-800">
                    <CheckCircle2 className="h-4 w-4 shrink-0" />
                    Subscription activated! Your plan has been updated.
                </div>
            )}
            {checkoutResult === "canceled" && (
                <div className="flex items-center gap-2.5 rounded-lg border border-amber-200 bg-amber-50 px-4 py-3 text-sm text-amber-800">
                    <AlertTriangle className="h-4 w-4 shrink-0" />
                    Checkout was canceled. Your plan has not changed.
                </div>
            )}

            {/* Error */}
            {error && (
                <div className="flex items-center gap-2.5 rounded-lg border border-red-200 bg-red-50 px-4 py-3 text-sm text-red-800">
                    <AlertTriangle className="h-4 w-4 shrink-0" />
                    {error}
                    <Button variant="ghost" size="sm" className="ml-auto text-xs" onClick={() => setError(null)}>
                        Dismiss
                    </Button>
                </div>
            )}

            {/* Tab Bar */}
            <div className="flex gap-1 border-b border-border pb-0">
                {(["overview", "analytics"] as const).map((tab) => (
                    <button
                        key={tab}
                        onClick={() => handleTabChange(tab)}
                        className={`
                            px-4 py-2 text-sm font-medium rounded-t-lg border-b-2 transition-colors capitalize
                            ${activeTab === tab
                                ? "border-primary text-primary"
                                : "border-transparent text-muted-foreground hover:text-foreground"}
                        `}
                    >
                        {tab === "analytics" ? "Analytics" : "Overview"}
                    </button>
                ))}
                <div className="ml-auto flex items-center pb-1">
                    <Button variant="ghost" size="sm" onClick={() => load()} disabled={loading} className="gap-1 text-xs">
                        <RefreshCw className={`h-3.5 w-3.5 ${loading ? "animate-spin" : ""}`} />
                        Refresh
                    </Button>
                </div>
            </div>

            {/* ── Overview Tab ─────────────────────────────────────────── */}
            {activeTab === "overview" && (
                <>
                    {/* 1. Current Plan Card */}
                    <Card>
                        <CardHeader className="flex flex-row items-start justify-between space-y-0">
                            <div className="space-y-1">
                                <CardTitle className="text-base flex items-center gap-2">
                                    <CreditCard className="h-4 w-4 text-muted-foreground" />
                                    Current Plan
                                </CardTitle>
                                <CardDescription>Your organization&apos;s active subscription</CardDescription>
                            </div>
                        </CardHeader>
                        <CardContent>
                            {loading ? (
                                <div className="space-y-3 animate-pulse">
                                    <div className="h-5 w-28 rounded bg-muted" />
                                    <div className="h-4 w-44 rounded bg-muted" />
                                </div>
                            ) : data ? (
                                <div className="flex flex-wrap items-start gap-x-8 gap-y-4">
                                    <div className="space-y-1">
                                        <p className="text-xs text-muted-foreground uppercase tracking-wider font-medium">Plan</p>
                                        <PlanBadge plan={data.plan} />
                                    </div>
                                    <div className="space-y-1">
                                        <p className="text-xs text-muted-foreground uppercase tracking-wider font-medium">Status</p>
                                        <StatusBadge status={data.subscription_status} />
                                    </div>
                                    {renewalDate && (
                                        <div className="space-y-1">
                                            <p className="text-xs text-muted-foreground uppercase tracking-wider font-medium">Renews</p>
                                            <p className="text-sm font-medium text-foreground">{renewalDate}</p>
                                        </div>
                                    )}
                                    {!isElite && (
                                        <div className="ml-auto">
                                            <Button asChild size="sm" className="gap-1.5">
                                                <Link href="/plans">
                                                    <ArrowUpRight className="h-3.5 w-3.5" />
                                                    Upgrade Plan
                                                </Link>
                                            </Button>
                                        </div>
                                    )}
                                </div>
                            ) : null}
                        </CardContent>
                    </Card>

                    {/* 2. Usage Section */}
                    {data && !loading && (
                        <Card>
                            <CardHeader>
                                <CardTitle className="text-base flex items-center gap-2">
                                    <BarChart2 className="h-4 w-4 text-muted-foreground" />
                                    Usage
                                </CardTitle>
                                <CardDescription>
                                    Resource consumption against your plan limits. Runs reset monthly.
                                </CardDescription>
                            </CardHeader>
                            <CardContent className="space-y-5">
                                <UsageBar
                                    label="Documents"
                                    used={data.usage.documents_used}
                                    limit={data.usage.documents_limit}
                                />
                                <UsageBar
                                    label="Projects"
                                    used={data.usage.projects_used}
                                    limit={data.usage.projects_limit}
                                />
                                <UsageBar
                                    label="Analysis Runs (this month)"
                                    used={data.usage.runs_used}
                                    limit={data.usage.runs_limit}
                                />
                            </CardContent>
                        </Card>
                    )}

                    {/* 3. Plan Comparison */}
                    {data && !loading && (
                        <PlanComparisonTable currentPlan={plan} nextPlan={nextPlan} />
                    )}

                    {/* 4. Manage Billing */}
                    {data && !loading && (
                        <Card>
                            <CardHeader>
                                <CardTitle className="text-base flex items-center gap-2">
                                    <ExternalLink className="h-4 w-4 text-muted-foreground" />
                                    Manage Billing
                                </CardTitle>
                                <CardDescription>
                                    Update payment method, view invoices, or cancel your subscription via the Stripe billing portal.
                                </CardDescription>
                            </CardHeader>
                            <CardContent>
                                {data.has_stripe && data.billing_configured ? (
                                    <Button
                                        variant="outline"
                                        size="sm"
                                        className="gap-1.5"
                                        onClick={handleManageBilling}
                                        disabled={portalLoading}
                                    >
                                        {portalLoading ? (
                                            <>
                                                <RefreshCw className="h-3.5 w-3.5 animate-spin" />
                                                Opening…
                                            </>
                                        ) : (
                                            <>
                                                <ExternalLink className="h-3.5 w-3.5" />
                                                Manage Billing
                                            </>
                                        )}
                                    </Button>
                                ) : (
                                    <p className="text-sm text-muted-foreground">
                                        No active Stripe subscription.{" "}
                                        <Link href="/plans" className="text-primary underline underline-offset-2 hover:text-primary/80">
                                            Subscribe to a plan
                                        </Link>{" "}
                                        to enable billing management.
                                    </p>
                                )}
                            </CardContent>
                        </Card>
                    )}
                </>
            )}

            {/* ── Analytics Tab ─────────────────────────────────────────── */}
            {activeTab === "analytics" && (
                <AnalyticsTab data={analytics} loading={analyticsLoading} />
            )}
        </div>
    );
}

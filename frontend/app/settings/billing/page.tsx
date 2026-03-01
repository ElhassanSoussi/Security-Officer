"use client";

/**
 * Phase 19 — Billing Settings Page  (/settings/billing)
 *
 * Sections:
 *  1. Current subscription card — plan badge, Stripe status badge, renewal date
 *  2. Usage this month — from getUsageSummary (reuses Phase-18 data)
 *  3. Plans comparison table — FREE / PRO / ENTERPRISE
 *  4. Upgrade CTA → createStripeCheckout
 */

import { useEffect, useState, useCallback } from "react";
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
} from "lucide-react";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { ApiClient } from "@/lib/api";
import { createClient } from "@/utils/supabase/client";
import { EnterpriseContactModal } from "@/components/EnterpriseContactModal";

// ─── Types ─────────────────────────────────────────────────────────────────

interface SubStatus {
    org_id: string;
    plan_name: string;
    stripe_status: string | null;
    stripe_customer_id: string | null;
    stripe_subscription_id: string | null;
    current_period_end: string | null;
    is_active: boolean;
}

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

// ─── Plan data ──────────────────────────────────────────────────────────────

const PLANS = [
    {
        key: "FREE" as const,
        label: "Free",
        price: "$0",
        interval: "forever",
        features: [
            "10 analysis runs / month",
            "25 documents",
            "100 memory entries",
            "Evidence exports (unmetered)",
        ],
        highlight: false,
    },
    {
        key: "PRO" as const,
        label: "Pro",
        price: "$149",
        interval: "/ month",
        features: [
            "100 analysis runs / month",
            "500 documents",
            "2,000 memory entries",
            "Evidence exports (unmetered)",
            "14-day free trial",
            "Priority support",
        ],
        highlight: true,
    },
    {
        key: "ENTERPRISE" as const,
        label: "Enterprise",
        price: "Custom",
        interval: "",
        features: [
            "10,000 analysis runs / month",
            "100,000 documents",
            "1M memory entries",
            "Evidence exports (unmetered)",
            "Dedicated support",
            "Custom integrations",
        ],
        highlight: false,
    },
];

// ─── Status badge helper ─────────────────────────────────────────────────────

function StripeStatusBadge({ status }: { status: string | null }) {
    if (!status || status === "") {
        return <Badge variant="secondary">Free tier</Badge>;
    }
    const map: Record<string, { label: string; className: string; icon: React.ReactNode }> = {
        active:    { label: "Active",    className: "bg-emerald-100 text-emerald-800 border-emerald-200", icon: <CheckCircle2 className="h-3 w-3" /> },
        trialing:  { label: "Trialing",  className: "bg-blue-100 text-blue-800 border-blue-200",         icon: <Clock className="h-3 w-3" /> },
        past_due:  { label: "Past Due",  className: "bg-amber-100 text-amber-800 border-amber-200",      icon: <AlertTriangle className="h-3 w-3" /> },
        canceled:  { label: "Canceled",  className: "bg-red-100 text-red-800 border-red-200",            icon: <XCircle className="h-3 w-3" /> },
        unpaid:    { label: "Unpaid",    className: "bg-red-100 text-red-800 border-red-200",            icon: <XCircle className="h-3 w-3" /> },
        incomplete:{ label: "Incomplete",className: "bg-slate-100 text-slate-700 border-slate-200",      icon: <AlertTriangle className="h-3 w-3" /> },
    };
    const def = map[status] ?? { label: status, className: "bg-slate-100 text-slate-700 border-slate-200", icon: null };
    return (
        <Badge variant="outline" className={`gap-1 ${def.className}`}>
            {def.icon}
            {def.label}
        </Badge>
    );
}

function PlanBadge({ plan }: { plan: string }) {
    const colors: Record<string, string> = {
        FREE:       "bg-slate-100 text-slate-700",
        PRO:        "bg-blue-100 text-blue-800",
        ENTERPRISE: "bg-violet-100 text-violet-800",
    };
    const cl = colors[plan.toUpperCase()] ?? "bg-slate-100 text-slate-700";
    return (
        <span className={`inline-flex items-center gap-1 rounded-full px-2.5 py-0.5 text-xs font-semibold ${cl}`}>
            <Zap className="h-3 w-3" />
            {plan}
        </span>
    );
}

// ─── Progress bar ────────────────────────────────────────────────────────────

function UsageBar({ label, value, max }: { label: string; value: number; max: number }) {
    const pct = max > 0 ? Math.min(100, Math.round((value / max) * 100)) : 0;
    const color = pct >= 100 ? "bg-red-500" : pct >= 85 ? "bg-amber-400" : "bg-blue-500";
    const barRef = useCallback((node: HTMLDivElement | null) => {
        if (node) node.style.width = `${pct}%`;
    }, [pct]);
    return (
        <div className="space-y-1">
            <div className="flex justify-between text-xs text-slate-600">
                <span>{label}</span>
                <span>{value.toLocaleString()} / {max.toLocaleString()}</span>
            </div>
            <div className="h-1.5 rounded-full bg-slate-100 overflow-hidden">
                <div ref={barRef} className={`h-full rounded-full transition-all ${color}`} />
            </div>
        </div>
    );
}

// ─── Page ────────────────────────────────────────────────────────────────────

export default function BillingPage() {
    const searchParams = useSearchParams();
    const checkoutResult = searchParams.get("checkout"); // "success" | "canceled"

    const [loading, setLoading] = useState(true);
    const [upgrading, setUpgrading] = useState<string | null>(null);
    const [enterpriseModalOpen, setEnterpriseModalOpen] = useState(false);
    const [error, setError] = useState<string | null>(null);
    const [sub, setSub] = useState<SubStatus | null>(null);
    const [usage, setUsage] = useState<UsageSummary | null>(null);
    const [token, setToken] = useState<string | undefined>(undefined);
    const [orgId, setOrgId] = useState<string | undefined>(undefined);

    const load = useCallback(async () => {
        setLoading(true);
        setError(null);
        try {
            const supabase = createClient();
            const { data: { session } } = await supabase.auth.getSession();
            const tok = session?.access_token;
            setToken(tok);

            const org = await ApiClient.getCurrentOrg(tok);
            const oid: string = org?.id;
            setOrgId(oid);

            const [subData, usageData] = await Promise.all([
                ApiClient.getSubscriptionStatus(oid, tok),
                ApiClient.getUsageSummary(oid, tok),
            ]);
            setSub(subData);
            setUsage(usageData);
        } catch (e: any) {
            setError(e?.message ?? "Failed to load billing data");
        } finally {
            setLoading(false);
        }
    }, []);

    useEffect(() => { load(); }, [load]);

    async function handleUpgrade(planKey: "FREE" | "PRO" | "ENTERPRISE") {
        if (!orgId) return;
        setUpgrading(planKey);
        try {
            const result = await ApiClient.createStripeCheckout(orgId, planKey, token);
            if (result.url) window.location.href = result.url;
        } catch (e: any) {
            setError(e?.message ?? "Checkout failed. Please try again.");
        } finally {
            setUpgrading(null);
        }
    }

    const renewalDate = sub?.current_period_end
        ? new Date(sub.current_period_end).toLocaleDateString("en-US", {
            year: "numeric", month: "long", day: "numeric",
          })
        : null;

    const currentPlan = (sub?.plan_name ?? usage?.plan ?? "FREE").toUpperCase();

    return (
        <div className="max-w-4xl mx-auto space-y-8 py-2">
            {/* ── Page header ── */}
            <div>
                <h1 className="text-2xl font-semibold text-slate-900">Billing &amp; Subscription</h1>
                <p className="mt-1 text-sm text-slate-500">
                    Manage your plan, payment method, and usage.
                </p>
            </div>

            {/* ── Checkout result banner ── */}
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

            {/* ── Error ── */}
            {error && (
                <div className="flex items-center gap-2.5 rounded-lg border border-red-200 bg-red-50 px-4 py-3 text-sm text-red-800">
                    <AlertTriangle className="h-4 w-4 shrink-0" />
                    {error}
                </div>
            )}

            {/* ── Current plan card ── */}
            <Card>
                <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
                    <CardTitle className="text-base flex items-center gap-2">
                        <CreditCard className="h-4 w-4 text-slate-500" />
                        Current Subscription
                    </CardTitle>
                    <Button
                        variant="ghost"
                        size="sm"
                        onClick={load}
                        disabled={loading}
                        className="gap-1 text-xs"
                    >
                        <RefreshCw className={`h-3.5 w-3.5 ${loading ? "animate-spin" : ""}`} />
                        Refresh
                    </Button>
                </CardHeader>
                <CardContent>
                    {loading ? (
                        <div className="space-y-2 animate-pulse">
                            <div className="h-4 w-32 rounded bg-slate-200" />
                            <div className="h-4 w-48 rounded bg-slate-200" />
                        </div>
                    ) : (
                        <div className="flex flex-wrap items-center gap-4">
                            <div className="space-y-1">
                                <div className="text-xs text-slate-500 uppercase tracking-wide">Plan</div>
                                <PlanBadge plan={currentPlan} />
                            </div>
                            <div className="space-y-1">
                                <div className="text-xs text-slate-500 uppercase tracking-wide">Status</div>
                                <StripeStatusBadge status={sub?.stripe_status ?? null} />
                            </div>
                            {renewalDate && (
                                <div className="space-y-1">
                                    <div className="text-xs text-slate-500 uppercase tracking-wide">Renews</div>
                                    <div className="text-sm font-medium text-slate-800">{renewalDate}</div>
                                </div>
                            )}
                        </div>
                    )}
                </CardContent>
            </Card>

            {/* ── Usage this month ── */}
            {usage && (
                <Card>
                    <CardHeader className="pb-2">
                        <CardTitle className="text-base flex items-center gap-2">
                            <BarChart2 className="h-4 w-4 text-slate-500" />
                            Usage This Month
                        </CardTitle>
                    </CardHeader>
                    <CardContent className="space-y-4">
                        <UsageBar
                            label="Analysis runs"
                            value={usage.runs_this_month}
                            max={usage.limits.max_runs_per_month}
                        />
                        <UsageBar
                            label="Documents stored"
                            value={usage.documents_total}
                            max={usage.limits.max_documents}
                        />
                        <UsageBar
                            label="Memory entries"
                            value={usage.memory_entries_total}
                            max={usage.limits.max_memory_entries}
                        />
                        <div className="flex justify-between text-xs text-slate-500 pt-1 border-t">
                            <span>Evidence exports</span>
                            <span className="font-medium text-slate-700">
                                {usage.evidence_exports_total.toLocaleString()} (unmetered)
                            </span>
                        </div>
                    </CardContent>
                </Card>
            )}

            {/* ── Plans comparison ── */}
            <div>
                <h2 className="text-base font-semibold text-slate-800 mb-4">Available Plans</h2>
                <div className="grid grid-cols-1 sm:grid-cols-3 gap-4">
                    {PLANS.map((plan) => {
                        const isCurrent = currentPlan === plan.key;
                        return (
                            <div
                                key={plan.key}
                                className={`relative rounded-xl border p-5 flex flex-col gap-4 ${
                                    plan.highlight
                                        ? "border-blue-400 shadow-md bg-blue-50/40"
                                        : "border-slate-200 bg-white"
                                } ${isCurrent ? "ring-2 ring-blue-500 ring-offset-1" : ""}`}
                            >
                                {plan.highlight && (
                                    <div className="absolute -top-3 left-1/2 -translate-x-1/2">
                                        <span className="rounded-full bg-blue-600 px-3 py-0.5 text-xs font-semibold text-white shadow">
                                            Most Popular
                                        </span>
                                    </div>
                                )}

                                <div>
                                    <div className="flex items-center justify-between">
                                        <span className="font-semibold text-slate-900">{plan.label}</span>
                                        {isCurrent && (
                                            <Badge variant="outline" className="text-xs border-blue-300 text-blue-700 bg-blue-50">
                                                Current
                                            </Badge>
                                        )}
                                    </div>
                                    <div className="mt-1 flex items-baseline gap-1">
                                        <span className="text-2xl font-bold text-slate-900">{plan.price}</span>
                                        {plan.interval && (
                                            <span className="text-sm text-slate-500">{plan.interval}</span>
                                        )}
                                    </div>
                                </div>

                                <ul className="flex-1 space-y-2">
                                    {plan.features.map((f) => (
                                        <li key={f} className="flex items-start gap-2 text-sm text-slate-700">
                                            <CheckCircle2 className="mt-0.5 h-3.5 w-3.5 shrink-0 text-emerald-500" />
                                            {f}
                                        </li>
                                    ))}
                                </ul>

                                {isCurrent ? (
                                    <Button variant="outline" size="sm" disabled className="w-full">
                                        Current Plan
                                    </Button>
                                ) : plan.key === "ENTERPRISE" ? (
                                    <Button
                                        variant="outline"
                                        size="sm"
                                        className="w-full"
                                        onClick={() => setEnterpriseModalOpen(true)}
                                    >
                                        Contact Sales
                                    </Button>
                                ) : (
                                    <Button
                                        size="sm"
                                        className={`w-full gap-1.5 ${
                                            plan.highlight
                                                ? "bg-gradient-to-r from-blue-600 to-blue-700 hover:from-blue-700 hover:to-blue-800 text-white"
                                                : ""
                                        }`}
                                        variant={plan.highlight ? "default" : "outline"}
                                        onClick={() => handleUpgrade(plan.key)}
                                        disabled={upgrading !== null}
                                    >
                                        {upgrading === plan.key ? (
                                            <>
                                                <RefreshCw className="h-3.5 w-3.5 animate-spin" />
                                                Redirecting…
                                            </>
                                        ) : (
                                            <>
                                                <Zap className="h-3.5 w-3.5" />
                                                {plan.key === "FREE" ? "Downgrade" : "Upgrade"}
                                            </>
                                        )}
                                    </Button>
                                )}
                            </div>
                        );
                    })}
                </div>

                <p className="mt-4 text-xs text-center text-slate-400">
                    Upgrades take effect immediately. Cancel anytime. Questions?{" "}
                    <a href="mailto:support@nyccompliancearchitect.com" className="underline">
                        Contact support
                    </a>
                    .
                </p>
            </div>

            {/* ── Back link ── */}
            <div className="pt-2 border-t">
                <Link href="/settings" className="text-sm text-slate-500 hover:text-slate-700 underline underline-offset-2">
                    ← Back to Settings
                </Link>
            </div>

            {/* ── Enterprise Contact Modal (Phase 22) ── */}
            <EnterpriseContactModal
                open={enterpriseModalOpen}
                onOpenChange={setEnterpriseModalOpen}
                orgId={orgId}
                token={token}
            />
        </div>
    );
}

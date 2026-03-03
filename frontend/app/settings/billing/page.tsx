"use client";

/*
 * Plans & Billing — /settings/billing
 *
 * Sections:
 *   1. Current Plan Card   (plan badge, status badge, renewal, upgrade CTA)
 *   2. Usage               (progress bars for documents / projects / runs)
 *   3. Manage Billing      (Stripe portal redirect)
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
    ExternalLink,
    ArrowUpRight,
} from "lucide-react";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from "@/components/ui/card";
import { ApiClient } from "@/lib/api";
import { createClient } from "@/utils/supabase/client";

// ─── Types ─────────────────────────────────────────────────────────────────

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
                    className={`h-full rounded-full transition-all duration-500 ${barColor}`}
                    style={{ width: isUnlimited ? "2%" : `${Math.max(pct, 2)}%` }}
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

// ─── Page ────────────────────────────────────────────────────────────────────

export default function BillingPage() {
    const searchParams = useSearchParams();
    const checkoutResult = searchParams.get("checkout");

    const [loading, setLoading] = useState(true);
    const [portalLoading, setPortalLoading] = useState(false);
    const [error, setError] = useState<string | null>(null);
    const [data, setData] = useState<BillingSummary | null>(null);
    const [orgId, setOrgId] = useState<string | null>(null);

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
        } catch (e: any) {
            setError(e?.message ?? "Failed to load billing data");
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
            setError(e?.message ?? "Could not open billing portal. You may need to subscribe to a plan first.");
        } finally {
            setPortalLoading(false);
        }
    };

    const plan = data?.plan?.toLowerCase() ?? "starter";
    const isElite = plan === "elite";
    const renewalDate = data?.current_period_end
        ? new Date(data.current_period_end).toLocaleDateString("en-US", {
            year: "numeric", month: "long", day: "numeric",
          })
        : null;

    return (
        <div className="max-w-3xl space-y-6">
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
                    <Button variant="ghost" size="sm" onClick={load} disabled={loading} className="gap-1 text-xs">
                        <RefreshCw className={`h-3.5 w-3.5 ${loading ? "animate-spin" : ""}`} />
                        Refresh
                    </Button>
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

            {/* 3. Manage Billing */}
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
        </div>
    );
}

"use client";

import React, { Suspense, useEffect, useState } from "react";
import { Card, CardContent, CardHeader, CardTitle, CardDescription, CardFooter } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Check, Shield, Zap, Crown, Info, ArrowRight, ExternalLink, Loader2 } from "lucide-react";
import { ApiClient } from "@/lib/api";
import { createClient } from "@/utils/supabase/client";
import { useRouter, useSearchParams } from "next/navigation";
import { getStoredOrgId, setStoredOrgId } from "@/lib/orgContext";
import PageHeader from "@/components/ui/PageHeader";
import { InfoBanner } from "@/components/ui/InfoBanner";

interface UsageMetric {
    used: number;
    limit: number;
    remaining: number;
}

interface StorageMetric {
    used_mb: number;
    limit_mb: number;
    remaining_mb: number;
}

interface BillingSummary {
    plan: string;
    period_start: string;
    period_end: string;
    entitlements: {
        questionnaires: UsageMetric;
        exports: UsageMetric;
        storage_mb: StorageMetric;
    };
}

function UsageBar({ label, used, limit, unit }: { label: string; used: number; limit: number; unit?: string }) {
    const pct = limit > 0 ? Math.min(100, (used / limit) * 100) : 0;
    const color =
        pct >= 90 ? "bg-red-500" :
            pct >= 70 ? "bg-amber-500" :
                "bg-primary";

    const barRef = React.useRef<HTMLDivElement>(null);
    React.useEffect(() => {
        if (barRef.current) barRef.current.style.width = `${pct}%`;
    }, [pct]);

    return (
        <div className="space-y-1.5">
            <div className="flex justify-between text-sm">
                <span className="text-muted-foreground font-medium">{label}</span>
                <span className="text-foreground font-semibold tabular-nums">
                    {used} / {limit} {unit || ""}
                </span>
            </div>
            <div className="h-2 rounded-full bg-muted overflow-hidden">
                <div
                    ref={barRef}
                    className={`h-full rounded-full transition-all duration-700 ease-out ${color}`}
                />
            </div>
            <p className="text-xs text-muted-foreground text-right">
                {limit - used} remaining
            </p>
        </div>
    );
}

const PLAN_META: Record<string, { icon: React.ReactNode; desc: string; badge: string }> = {
    starter: { icon: <Shield className="h-5 w-5 text-blue-500" />, desc: "For single-project teams.", badge: "bg-blue-100 text-blue-800" },
    growth: { icon: <Zap className="h-5 w-5 text-emerald-500" />, desc: "For teams handling multiple bids.", badge: "bg-emerald-100 text-emerald-800" },
    elite: { icon: <Crown className="h-5 w-5 text-purple-500" />, desc: "For heavy compliance volume.", badge: "bg-purple-100 text-purple-800" },
};

const STATUS_BADGES: Record<string, { label: string; className: string }> = {
    active: { label: "Active", className: "bg-green-100 text-green-800" },
    trialing: { label: "Trial", className: "bg-blue-100 text-blue-800" },
    past_due: { label: "Past Due", className: "bg-red-100 text-red-800" },
    canceled: { label: "Canceled", className: "bg-slate-100 text-slate-600" },
};

export default function PlansPage() {
    return (
        <Suspense fallback={<div className="p-8 text-slate-500">Loading billing...</div>}>
            <PlansPageInner />
        </Suspense>
    );
}

function PlansPageInner() {
    const [loading, setLoading] = useState(true);
    const [error, setError] = useState("");
    const [plans, setPlans] = useState<any[]>([]);
    const [summary, setSummary] = useState<BillingSummary | null>(null);
    const [subscription, setSubscription] = useState<any>(null);
    const [upgradingPlan, setUpgradingPlan] = useState<string | null>(null);
    const [billingConfigured, setBillingConfigured] = useState<boolean>(true);
    const [orgId, setOrgId] = useState<string>("");
    const [token, setToken] = useState<string>("");
    const [checkoutSuccess, setCheckoutSuccess] = useState(false);
    const router = useRouter();
    const searchParams = useSearchParams();

    const fallbackSummaryFromPlans = (availablePlans: any[]): BillingSummary => {
        const starter = (availablePlans || []).find((p: any) => p?.id === "starter") || {};
        const qLimit = Number(starter?.questionnaires_limit || 10);
        const eLimit = Number(starter?.exports_limit || 10);
        const sLimit = Number(starter?.knowledge_storage_mb || 500);
        const now = new Date();
        const periodStart = new Date(Date.UTC(now.getUTCFullYear(), now.getUTCMonth(), 1)).toISOString();
        const periodEnd = new Date(Date.UTC(now.getUTCFullYear(), now.getUTCMonth() + 1, 0, 23, 59, 59)).toISOString();

        return {
            plan: "starter",
            period_start: periodStart,
            period_end: periodEnd,
            entitlements: {
                questionnaires: { used: 0, limit: qLimit, remaining: qLimit },
                exports: { used: 0, limit: eLimit, remaining: eLimit },
                storage_mb: { used_mb: 0, limit_mb: sLimit, remaining_mb: sLimit },
            },
        };
    };

    useEffect(() => {
        // Check for checkout success redirect
        if (searchParams.get("checkout") === "success") {
            setCheckoutSuccess(true);
            // Clean up URL
            window.history.replaceState({}, "", "/plans");
        }
    }, [searchParams]);

    useEffect(() => {
        async function loadBilling() {
            setLoading(true);
            setError("");
            try {
                const supabase = createClient();
                const { data: { session } } = await supabase.auth.getSession();
                const tkn = session?.access_token;
                if (!tkn) {
                    router.push("/login");
                    return;
                }
                setToken(tkn);

                const orgs = await ApiClient.getMyOrgs(tkn);
                if (!orgs || orgs.length === 0) {
                    router.push("/onboarding");
                    return;
                }

                const stored = getStoredOrgId() || "";
                const selected = orgs.find((o: any) => o.id === stored) || orgs[0];
                const oid = selected.id;
                setStoredOrgId(oid);
                setOrgId(oid);

                const p = await ApiClient.getPlans(tkn);
                setPlans(p || []);
                const plansBillingEnabled = (p || []).some((plan: any) => plan?.billing_enabled !== false);

                if (!plansBillingEnabled) {
                    setBillingConfigured(false);
                    setSummary(fallbackSummaryFromPlans(p || []));
                    setSubscription({
                        plan: "starter",
                        subscription_status: "trialing",
                        billing_configured: false,
                        has_stripe: false,
                    });
                    return;
                }

                const [s, sub] = await Promise.all([
                    ApiClient.getBillingSummary(oid, tkn),
                    ApiClient.getSubscription(oid, tkn),
                ]);

                setSummary(s || null);
                setSubscription(sub || null);
                const configured = (sub?.billing_configured ?? s?.billing_configured ?? true);
                setBillingConfigured(Boolean(configured));
            } catch (e: any) {
                console.error(e);
                if (String(e?.message || "").toLowerCase().includes("unauthorized")) {
                    router.push("/login");
                    return;
                }
                if (e?.code === "billing_disabled" || e?.code === "billing_not_configured") {
                    setBillingConfigured(false);
                    setSummary((prev) => prev ?? fallbackSummaryFromPlans(plans));
                    setSubscription((prev: any) => prev ?? {
                        plan: "starter",
                        subscription_status: "trialing",
                        billing_configured: false,
                        has_stripe: false,
                    });
                } else {
                    setError(e?.message || "Failed to load billing data.");
                }
            } finally {
                setLoading(false);
            }
        }

        loadBilling();
        // eslint-disable-next-line react-hooks/exhaustive-deps
    }, [router, checkoutSuccess]);

    const handleUpgrade = async (planId: string) => {
        if (!orgId || !token) return;
        if (!billingConfigured) {
            setError("Self-service billing coming soon. Contact support@nyccompliancearchitect.com to upgrade.");
            return;
        }
        setUpgradingPlan(planId);
        setError("");

        try {
            const res = await ApiClient.createCheckoutSession(orgId, planId, token);
            if (res?.url) {
                window.location.href = res.url;
            } else {
                setError("Failed to create checkout session.");
            }
        } catch (e: any) {
            console.error(e);
            setError(e?.message || "Failed to start checkout.");
        } finally {
            setUpgradingPlan(null);
        }
    };

    const handleManageBilling = async () => {
        if (!orgId || !token) return;
        try {
            const res = await ApiClient.createPortalSession(orgId, token);
            if (res?.url) {
                window.location.href = res.url;
            }
        } catch (e: any) {
            setError(e?.message || "Failed to open billing portal.");
        }
    };

    const fmtPrice = (cents?: number) => {
        if (typeof cents !== "number") return "—";
        return `$${(cents / 100).toLocaleString()}`;
    };

    const fmtDate = (iso?: string) => {
        if (!iso) return "—";
        return new Date(iso).toLocaleDateString("en-US", { month: "short", day: "numeric", year: "numeric" });
    };

    const currentPlan = summary?.plan || subscription?.plan || "starter";
    const subStatus = subscription?.subscription_status || subscription?.status || "trialing";
    const statusBadge = STATUS_BADGES[subStatus] || STATUS_BADGES.trialing;
    const hasStripe = subscription?.has_stripe;

    return (
        <div className="space-y-8 max-w-5xl mx-auto">
            <PageHeader title="Plans & Billing" subtitle="Compare plans, track usage, and manage your subscription." />

            {checkoutSuccess && (
                <div className="rounded-md border border-green-200 bg-green-50 px-4 py-3 text-sm text-green-700 flex items-center gap-2">
                    <Check className="h-4 w-4" />
                    <span><strong>Plan upgraded successfully!</strong> Your new limits are now active.</span>
                </div>
            )}

            {error && (
                <div className="rounded-md border border-red-200 bg-red-50 px-4 py-3 text-sm text-red-700">
                    {error}
                </div>
            )}

            {!billingConfigured && (
                <InfoBanner variant="info" title="Self-service billing is coming soon.">
                    Plan upgrades will be available shortly. In the meantime, contact <strong>support@nyccompliancearchitect.com</strong> to upgrade your plan.
                </InfoBanner>
            )}

            {/* ── Usage Summary Card ── */}
            <Card>
                <CardHeader className="pb-3">
                    <div className="flex items-center justify-between">
                        <div className="flex items-center gap-3">
                            {PLAN_META[currentPlan]?.icon || <Shield className="h-5 w-5 text-slate-400" />}
                            <div>
                                <CardTitle className="text-lg">
                                    {loading ? (
                                        <span className="inline-block h-5 w-24 bg-slate-200 rounded animate-pulse" />
                                    ) : (
                                        <>
                                            {currentPlan.toUpperCase()} Plan
                                            <span className={`ml-2 text-xs px-2 py-0.5 rounded font-medium ${statusBadge.className}`}>
                                                {statusBadge.label}
                                            </span>
                                        </>
                                    )}
                                </CardTitle>
                                <CardDescription className="mt-0.5">
                                    {loading ? (
                                        <span className="inline-block h-3.5 w-48 bg-slate-100 rounded animate-pulse" />
                                    ) : (
                                        <>Billing period: {fmtDate(summary?.period_start)} — {fmtDate(summary?.period_end)}</>
                                    )}
                                </CardDescription>
                            </div>
                        </div>
                        {hasStripe && !loading && (
                            <Button variant="outline" size="sm" onClick={handleManageBilling} className="gap-1.5">
                                <ExternalLink className="h-3.5 w-3.5" />
                                Manage Billing
                            </Button>
                        )}
                    </div>
                </CardHeader>
                <CardContent className="space-y-5">
                    {loading ? (
                        <div className="space-y-4">
                            {[1, 2, 3].map(i => (
                                <div key={i} className="space-y-2">
                                    <div className="h-4 w-40 bg-slate-100 rounded animate-pulse" />
                                    <div className="h-2.5 w-full bg-slate-100 rounded-full animate-pulse" />
                                </div>
                            ))}
                        </div>
                    ) : summary ? (
                        <>
                            <UsageBar
                                label="Questionnaires"
                                used={summary.entitlements.questionnaires.used}
                                limit={summary.entitlements.questionnaires.limit}
                            />
                            <UsageBar
                                label="Exports"
                                used={summary.entitlements.exports.used}
                                limit={summary.entitlements.exports.limit}
                            />
                            <UsageBar
                                label="Knowledge Vault Storage"
                                used={Math.round(summary.entitlements.storage_mb.used_mb)}
                                limit={summary.entitlements.storage_mb.limit_mb}
                                unit="MB"
                            />
                        </>
                    ) : (
                        <p className="text-sm text-slate-500">No usage data available.</p>
                    )}
                </CardContent>
            </Card>

            {/* ── Plan Cards ── */}
            <div className="grid md:grid-cols-3 gap-6">
                {(plans || []).map((plan) => {
                    const isCurrent = currentPlan === plan.id;
                    const meta = PLAN_META[plan.id] || PLAN_META.starter;
                    const isUpgrading = upgradingPlan === plan.id;

                    return (
                        <Card key={plan.id} className={`transition-shadow hover:shadow-md ${isCurrent ? "border-primary shadow-md ring-2 ring-primary/10" : ""}`}>
                            <CardHeader>
                                <CardTitle className="flex justify-between items-center">
                                    <span className="flex items-center gap-2">
                                        {meta.icon}
                                        {plan.name || plan.id}
                                    </span>
                                    {isCurrent && (
                                        <span className={`text-xs px-2 py-1 rounded font-medium ${meta.badge}`}>Current</span>
                                    )}
                                </CardTitle>
                                <CardDescription>{meta.desc}</CardDescription>
                            </CardHeader>
                            <CardContent className="space-y-4">
                                <div className="text-3xl font-bold tracking-tight">
                                    {fmtPrice(plan.price_cents)}{" "}
                                    <span className="text-sm text-muted-foreground font-normal">/ {plan.billing_interval || "month"}</span>
                                </div>
                                <ul className="space-y-2.5 text-sm text-muted-foreground">
                                    <li className="flex items-center">
                                        <Check className="h-4 w-4 mr-2 text-green-500 flex-shrink-0" /> {plan.questionnaires_limit ?? "—"} questionnaires / month
                                    </li>
                                    <li className="flex items-center" title="Knowledge Vault is your org and project documents used for RAG answers.">
                                        <Check className="h-4 w-4 mr-2 text-green-500 flex-shrink-0" /> {plan.knowledge_storage_mb ?? "—"} MB Knowledge Vault
                                    </li>
                                    <li className="flex items-center" title="Exports are final filled Excel downloads.">
                                        <Check className="h-4 w-4 mr-2 text-green-500 flex-shrink-0" /> {plan.exports_limit ?? "—"} exports / month
                                    </li>
                                </ul>
                            </CardContent>
                            <CardFooter>
                                {isCurrent ? (
                                    <Button className="w-full" variant="outline" disabled>
                                        Current Plan
                                    </Button>
                                ) : (
                                    <Button
                                        className={`w-full gap-2 ${billingConfigured
                                            ? "bg-gradient-to-r from-slate-800 to-slate-700 text-white hover:from-slate-700 hover:to-slate-600"
                                            : "bg-slate-100 text-slate-400 cursor-not-allowed"
                                        }`}
                                        onClick={() => handleUpgrade(plan.id)}
                                        disabled={isUpgrading || loading || !billingConfigured}
                                    >
                                        {isUpgrading ? (
                                            <>
                                                <Loader2 className="h-4 w-4 animate-spin" />
                                                Redirecting to Stripe…
                                            </>
                                        ) : billingConfigured ? (
                                            <>
                                                Upgrade <ArrowRight className="h-4 w-4" />
                                            </>
                                        ) : (
                                            <>
                                                Coming soon <ArrowRight className="h-4 w-4" />
                                            </>
                                        )}
                                    </Button>
                                )}
                            </CardFooter>
                        </Card>
                    );
                })}
            </div>

            <div className="text-center text-xs text-muted-foreground flex items-center justify-center gap-2">
                <Info className="h-3 w-3" />
                Usage resets at the start of each billing period. All limits are enforced server-side.
            </div>
        </div>
    );
}

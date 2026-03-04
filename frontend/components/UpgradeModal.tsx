"use client";

/**
 * UpgradeModal — Context-aware upgrade prompt.
 *
 * Listens for the global "plan:limit_exceeded" CustomEvent fired by
 * ApiClient.fetch() whenever the backend returns HTTP 403 plan_limit_exceeded.
 * Mount once in AppShell so it catches limit errors across the entire app.
 *
 * Shows:
 *   - Which resource hit its limit and current usage/limit
 *   - What the next plan unlocks
 *   - Price of the next plan
 *   - "Upgrade Now" CTA → Stripe portal redirect
 */

import { useCallback, useEffect, useState } from "react";
import {
    Dialog,
    DialogContent,
    DialogHeader,
    DialogTitle,
    DialogDescription,
    DialogFooter,
} from "@/components/ui/dialog";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import {
    AlertTriangle,
    ArrowRight,
    CheckCircle2,
    Zap,
} from "lucide-react";
import { ApiClient } from "@/lib/api";
import { createClient } from "@/utils/supabase/client";

// ─── Types ──────────────────────────────────────────────────────────────────

export interface PlanLimitExceededDetail {
    error?: string;
    message?: string;
    resource?: string;
    current_plan?: string;
    used?: number;
    limit?: number;
    next_plan?: string | null;
    // legacy aliases
    plan?: string;
    current_count?: number;
}

// ─── Static config ──────────────────────────────────────────────────────────

const RESOURCE_LABELS: Record<string, string> = {
    projects:  "projects",
    documents: "documents",
    runs:      "analysis runs",
};

const PLAN_LABELS: Record<string, string> = {
    starter: "Starter",
    growth:  "Growth",
    elite:   "Elite",
};

const PLAN_PRICES: Record<string, string> = {
    starter: "$149/mo",
    growth:  "$499/mo",
    elite:   "$1,499/mo",
};

const PLAN_UNLOCKS: Record<string, Record<string, string[]>> = {
    // what upgrading FROM starter TO growth unlocks
    starter: {
        projects:  ["25 projects (was 5)", "500 documents", "100 runs/month"],
        documents: ["500 documents (was 25)", "25 projects", "100 runs/month"],
        runs:      ["100 runs/month (was 10)", "25 projects", "500 documents"],
    },
    // what upgrading FROM growth TO elite unlocks
    growth: {
        projects:  ["10,000 projects (was 25)", "100K documents", "10K runs/month"],
        documents: ["100K documents (was 500)", "10,000 projects", "10K runs/month"],
        runs:      ["10K runs/month (was 100)", "10,000 projects", "100K documents"],
    },
};

const PLAN_BADGE_CLASS: Record<string, string> = {
    starter: "bg-slate-100 text-slate-700 border-slate-200",
    growth:  "bg-blue-100 text-blue-800 border-blue-200",
    elite:   "bg-violet-100 text-violet-800 border-violet-200",
};

// ─── Component ───────────────────────────────────────────────────────────────

export function UpgradeModal() {
    const [open, setOpen]       = useState(false);
    const [loading, setLoading] = useState(false);
    const [detail, setDetail]   = useState<PlanLimitExceededDetail>({});

    /** Best-effort funnel logger — never throws */
    const logEvent = useCallback(async (
        eventType: string,
        eventDetail: PlanLimitExceededDetail = {},
    ) => {
        try {
            const supabase = createClient();
            const { data: { session } } = await supabase.auth.getSession();
            const tok = session?.access_token;
            const org = await ApiClient.getCurrentOrg(tok);
            if (org?.id) {
                await ApiClient.logUpgradeEvent(eventType, org.id, tok, {
                    resource:      eventDetail.resource,
                    current_plan:  eventDetail.current_plan ?? eventDetail.plan,
                    used:          eventDetail.used ?? eventDetail.current_count,
                    limit:         eventDetail.limit,
                    next_plan:     eventDetail.next_plan,
                } as Record<string, unknown>);
            }
        } catch {
            // best-effort
        }
    }, []);

    useEffect(() => {
        const handler = (e: Event) => {
            const custom = e as CustomEvent<PlanLimitExceededDetail>;
            setDetail(custom.detail ?? {});
            setOpen(true);
            setLoading(false);
            // Track: modal shown
            logEvent("upgrade_modal_shown", custom.detail ?? {});
        };
        window.addEventListener("plan:limit_exceeded", handler);
        return () => window.removeEventListener("plan:limit_exceeded", handler);
    }, [logEvent]);

    const handleUpgrade = useCallback(async () => {
        setLoading(true);
        // Track: upgrade clicked
        logEvent("upgrade_clicked", detail);
        try {
            const supabase = createClient();
            const { data: { session } } = await supabase.auth.getSession();
            const tok = session?.access_token;
            const org = await ApiClient.getCurrentOrg(tok);
            const result = await ApiClient.createPortalSessionV2(org?.id, tok);
            if (result?.url) {
                setOpen(false);
                window.location.href = result.url;
            }
        } catch {
            // fallback: navigate to plans page
            setOpen(false);
            window.location.href = "/plans";
        } finally {
            setLoading(false);
        }
    }, [detail, logEvent]);

    const currentPlan  = (detail.current_plan ?? detail.plan ?? "starter").toLowerCase();
    const nextPlan     = (detail.next_plan ?? "").toLowerCase() || null;
    const resource     = (detail.resource ?? "").toLowerCase();
    const used         = detail.used ?? detail.current_count ?? 0;
    const limit        = detail.limit ?? 0;
    const resourceLabel = RESOURCE_LABELS[resource] ?? resource;
    const currentLabel = PLAN_LABELS[currentPlan] ?? currentPlan;
    const nextLabel    = nextPlan ? (PLAN_LABELS[nextPlan] ?? nextPlan) : null;
    const nextPrice    = nextPlan ? (PLAN_PRICES[nextPlan] ?? "") : "";
    const unlocks: string[] = (nextPlan && PLAN_UNLOCKS[currentPlan]?.[resource]) ? PLAN_UNLOCKS[currentPlan][resource] : [];

    return (
        <Dialog open={open} onOpenChange={setOpen}>
            <DialogContent className="sm:max-w-md">
                <DialogHeader>
                    <div className="flex items-center gap-3 mb-2">
                        <div className="rounded-full bg-amber-100 p-2.5 shrink-0">
                            <AlertTriangle className="h-5 w-5 text-amber-600" />
                        </div>
                        <div>
                            <DialogTitle className="text-base leading-snug">
                                You&apos;ve reached your {resourceLabel} limit
                            </DialogTitle>
                            <DialogDescription className="mt-0.5 text-xs text-muted-foreground">
                                on the{" "}
                                <Badge
                                    variant="outline"
                                    className={`text-xs font-semibold ${PLAN_BADGE_CLASS[currentPlan] ?? ""}`}
                                >
                                    {currentLabel}
                                </Badge>{" "}
                                plan
                            </DialogDescription>
                        </div>
                    </div>
                </DialogHeader>

                {/* Usage meter */}
                <div className="rounded-lg border bg-muted/40 px-4 py-3 space-y-2">
                    <div className="flex justify-between text-sm">
                        <span className="text-muted-foreground capitalize">{resourceLabel} used</span>
                        <span className="font-semibold text-red-600">
                            {used.toLocaleString()} / {limit.toLocaleString()}
                        </span>
                    </div>
                    <div className="h-2 rounded-full bg-muted overflow-hidden">
                        <div className="h-full rounded-full bg-red-500 w-full" />
                    </div>
                </div>

                {/* What upgrading unlocks */}
                {nextLabel && unlocks.length > 0 && (
                    <div className="space-y-2">
                        <p className="text-xs font-medium text-muted-foreground uppercase tracking-wide">
                            Upgrade to{" "}
                            <Badge
                                variant="outline"
                                className={`text-xs font-semibold ${PLAN_BADGE_CLASS[nextPlan ?? ""] ?? ""}`}
                            >
                                {nextLabel}
                            </Badge>{" "}
                            {nextPrice && `· ${nextPrice}`}
                        </p>
                        <ul className="space-y-1.5">
                            {unlocks.map((item) => (
                                <li key={item} className="flex items-start gap-2 text-sm text-foreground">
                                    <CheckCircle2 className="h-4 w-4 text-emerald-500 mt-0.5 shrink-0" />
                                    {item}
                                </li>
                            ))}
                        </ul>
                    </div>
                )}

                {!nextLabel && (
                    <p className="text-sm text-muted-foreground">
                        Contact support to discuss custom limits for your organization.
                    </p>
                )}

                <DialogFooter className="flex-col-reverse sm:flex-row gap-2 sm:gap-0">
                    <Button variant="ghost" size="sm" onClick={() => setOpen(false)}>
                        Not now
                    </Button>
                    {nextLabel ? (
                        <Button
                            size="sm"
                            className="w-full sm:w-auto gap-1.5 bg-gradient-to-r from-blue-600 to-blue-700 hover:from-blue-700 hover:to-blue-800 text-white"
                            onClick={handleUpgrade}
                            disabled={loading}
                        >
                            {loading ? (
                                <span className="animate-pulse">Opening portal…</span>
                            ) : (
                                <>
                                    <Zap className="h-3.5 w-3.5" />
                                    Upgrade to {nextLabel}
                                    <ArrowRight className="h-3.5 w-3.5" />
                                </>
                            )}
                        </Button>
                    ) : (
                        <Button
                            size="sm"
                            variant="outline"
                            className="w-full sm:w-auto gap-1.5"
                            onClick={() => { setOpen(false); window.location.href = "/plans"; }}
                        >
                            View Plans
                        </Button>
                    )}
                </DialogFooter>
            </DialogContent>
        </Dialog>
    );
}

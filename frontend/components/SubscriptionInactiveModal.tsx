"use client";

/*
 * Subscription Inactive Blocking Modal
 *
 * Listens for the global "subscription:inactive" CustomEvent dispatched by
 * ApiClient.fetch() whenever the backend returns HTTP 402 SUBSCRIPTION_INACTIVE.
 *
 * Shown when the org's Stripe subscription is past_due / canceled / unpaid.
 * Blocks the user with an "Update Billing" CTA → /settings/billing.
 *
 * Mount once in the root layout alongside PlanLimitModal.
 */

import { useEffect, useState } from "react";
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
import { CreditCard, AlertOctagon } from "lucide-react";
import Link from "next/link";

interface InactiveDetail {
    error?: string;
    detail?: string;
    stripe_status?: string;
}

const STATUS_LABELS: Record<string, string> = {
    past_due: "Past Due",
    canceled: "Canceled",
    unpaid: "Unpaid",
    incomplete: "Incomplete",
};

export function SubscriptionInactiveModal() {
    const [open, setOpen] = useState(false);
    const [detail, setDetail] = useState<InactiveDetail>({});

    useEffect(() => {
        const handler = (e: Event) => {
            const custom = e as CustomEvent<InactiveDetail>;
            setDetail(custom.detail ?? {});
            setOpen(true);
        };
        window.addEventListener("subscription:inactive", handler);
        return () => window.removeEventListener("subscription:inactive", handler);
    }, []);

    const stripeStatus = detail.stripe_status ?? "";
    const statusLabel = STATUS_LABELS[stripeStatus] ?? "Inactive";

    return (
        <Dialog open={open} onOpenChange={setOpen}>
            <DialogContent
                className="sm:max-w-md [&>div.fixed]:pointer-events-none"
            >
                <DialogHeader>
                    <div className="flex items-center gap-3 mb-1">
                        <div className="rounded-full bg-red-100 p-2">
                            <AlertOctagon className="h-5 w-5 text-red-600" />
                        </div>
                        <DialogTitle className="text-base">Subscription Inactive</DialogTitle>
                    </div>
                    <DialogDescription className="text-sm leading-relaxed">
                        Your subscription is currently{" "}
                        <Badge variant="destructive" className="text-xs font-semibold">
                            {statusLabel}
                        </Badge>
                        . Access to analysis, document ingestion, and evidence
                        generation has been paused until billing is resolved.
                    </DialogDescription>
                </DialogHeader>

                <div className="rounded-lg border border-red-100 bg-red-50/60 px-4 py-3 text-sm text-red-800">
                    Please update your payment method or renew your subscription to
                    restore full access to your compliance workspace.
                </div>

                <DialogFooter className="flex-col-reverse sm:flex-row gap-2 sm:gap-0">
                    <Button
                        variant="ghost"
                        size="sm"
                        onClick={() => setOpen(false)}
                    >
                        Dismiss
                    </Button>
                    <Link href="/settings/billing" onClick={() => setOpen(false)}>
                        <Button
                            size="sm"
                            className="w-full sm:w-auto gap-1.5 bg-gradient-to-r from-red-600 to-rose-600 hover:from-red-700 hover:to-rose-700 text-white"
                        >
                            <CreditCard className="h-3.5 w-3.5" />
                            Update Billing
                        </Button>
                    </Link>
                </DialogFooter>
            </DialogContent>
        </Dialog>
    );
}

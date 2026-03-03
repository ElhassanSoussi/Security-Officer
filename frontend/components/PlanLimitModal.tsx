"use client";

/**
 * Plan Limit Modal
 *
 * Listens for the global "plan:limit_reached" CustomEvent dispatched by
 * ApiClient.fetch() whenever the backend returns HTTP 402 PLAN_LIMIT_REACHED.
 *
 * Mount this once in the root layout so it intercepts any 402 across the app.
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
import { Zap, AlertTriangle } from "lucide-react";
import Link from "next/link";

interface PlanLimitDetail {
    error?: string;
    detail?: string;
    current_count?: number;
    limit?: number;
    plan?: string;
    resource?: string;
}

const RESOURCE_LABELS: Record<string, string> = {
    runs: "analysis runs",
    documents: "uploaded documents",
    memory: "institutional memory entries",
    evidence: "evidence exports",
};

export function PlanLimitModal() {
    const [open, setOpen] = useState(false);
    const [detail, setDetail] = useState<PlanLimitDetail>({});

    useEffect(() => {
        const handler = (e: Event) => {
            const custom = e as CustomEvent<PlanLimitDetail>;
            setDetail(custom.detail ?? {});
            setOpen(true);
        };
        window.addEventListener("plan:limit_reached", handler);
        return () => window.removeEventListener("plan:limit_reached", handler);
    }, []);

    const resource = detail.resource ?? "";
    const resourceLabel = RESOURCE_LABELS[resource] ?? resource;
    const plan = detail.plan ?? "FREE";
    const limit = detail.limit;
    const count = detail.current_count;

    return (
        <Dialog open={open} onOpenChange={setOpen}>
            <DialogContent className="sm:max-w-md">
                <DialogHeader>
                    <div className="flex items-center gap-3 mb-1">
                        <div className="rounded-full bg-amber-100 p-2">
                            <AlertTriangle className="h-5 w-5 text-amber-600" />
                        </div>
                        <DialogTitle className="text-base">Plan Limit Reached</DialogTitle>
                    </div>
                    <DialogDescription className="text-sm leading-relaxed">
                        You&apos;ve reached your{" "}
                        <Badge variant="outline" className="text-xs font-semibold border-gray-200">
                            {plan}
                        </Badge>{" "}
                        plan limit for{" "}
                        <span className="font-semibold text-foreground">{resourceLabel}</span>.
                        {count != null && limit != null && (
                            <span className="block mt-1 text-muted-foreground">
                                Current usage: {count.toLocaleString()} / {limit.toLocaleString()}
                            </span>
                        )}
                    </DialogDescription>
                </DialogHeader>

                <div className="rounded-lg border border-blue-100 bg-blue-50/60 px-4 py-3 text-sm text-blue-800">
                    Upgrade your plan to unlock higher limits and continue without interruption.
                </div>

                <DialogFooter className="flex-col-reverse sm:flex-row gap-2 sm:gap-0">
                    <Button variant="ghost" size="sm" onClick={() => setOpen(false)}>
                        Dismiss
                    </Button>
                    <Link href="/plans" onClick={() => setOpen(false)}>
                        <Button size="sm" className="w-full sm:w-auto gap-1.5 bg-gradient-to-r from-blue-600 to-blue-700 hover:from-blue-700 hover:to-blue-800 text-white">
                            <Zap className="h-3.5 w-3.5" />
                            Upgrade Plan
                        </Button>
                    </Link>
                </DialogFooter>
            </DialogContent>
        </Dialog>
    );
}

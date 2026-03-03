"use client";

/**
 * Enterprise Contact Modal
 *
 * Shown instead of Stripe checkout when user clicks "Enterprise" plan.
 * Tracks enterprise interest event and provides options to contact sales
 * or go to the /contact page.
 */

import { useState } from "react";
import Link from "next/link";
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
import { Building2, ArrowRight, Mail, CheckCircle2 } from "lucide-react";
import { ApiClient } from "@/lib/api";

interface EnterpriseContactModalProps {
    open: boolean;
    onOpenChange: (open: boolean) => void;
    orgId?: string;
    token?: string;
}

const ENTERPRISE_FEATURES = [
    "10,000 analysis runs / month",
    "100,000 document uploads",
    "1M institutional memory entries",
    "Dedicated customer success manager",
    "Custom integrations & SSO",
    "Priority support SLA",
];

export function EnterpriseContactModal({
    open,
    onOpenChange,
    orgId,
    token,
}: EnterpriseContactModalProps) {
    const [tracked, setTracked] = useState(false);

    async function handleTrackAndNavigate() {
        if (!tracked) {
            try {
                await ApiClient.trackEnterpriseInterest(orgId, "billing_page", token);
            } catch {
                // Best-effort tracking — don't block navigation
            }
            setTracked(true);
        }
    }

    return (
        <Dialog open={open} onOpenChange={onOpenChange}>
            <DialogContent className="sm:max-w-lg">
                <DialogHeader>
                    <div className="flex items-center gap-3 mb-1">
                        <div className="rounded-full bg-violet-100 p-2.5">
                            <Building2 className="h-5 w-5 text-violet-600" />
                        </div>
                        <div>
                            <DialogTitle className="text-base">Enterprise Plan</DialogTitle>
                            <Badge variant="outline" className="mt-0.5 text-xs border-violet-200 text-violet-700 bg-violet-50">
                                Custom Pricing
                            </Badge>
                        </div>
                    </div>
                    <DialogDescription className="text-sm leading-relaxed pt-2">
                        The Enterprise plan requires custom onboarding tailored to your
                        organization&apos;s compliance requirements. Our team will work with you to
                        configure the perfect setup.
                    </DialogDescription>
                </DialogHeader>

                {/* Features list */}
                <div className="rounded-lg border border-violet-100 bg-violet-50/40 p-4 space-y-2">
                    <p className="text-xs font-semibold uppercase tracking-wider text-violet-600 mb-2">
                        What&apos;s Included
                    </p>
                    {ENTERPRISE_FEATURES.map((f) => (
                        <div key={f} className="flex items-start gap-2 text-sm text-slate-700">
                            <CheckCircle2 className="mt-0.5 h-3.5 w-3.5 shrink-0 text-violet-500" />
                            {f}
                        </div>
                    ))}
                </div>

                <DialogFooter className="flex-col-reverse sm:flex-row gap-2 sm:gap-0 pt-2">
                    <Button
                        variant="ghost"
                        size="sm"
                        onClick={() => onOpenChange(false)}
                    >
                        Maybe Later
                    </Button>
                    <div className="flex gap-2">
                        <a href="mailto:sales@nyccompliancearchitect.com">
                            <Button
                                variant="outline"
                                size="sm"
                                className="gap-1.5"
                                onClick={handleTrackAndNavigate}
                            >
                                <Mail className="h-3.5 w-3.5" />
                                Email Sales
                            </Button>
                        </a>
                        <Link href="/contact" onClick={handleTrackAndNavigate}>
                            <Button
                                size="sm"
                                className="gap-1.5 bg-gradient-to-r from-violet-600 to-violet-700 hover:from-violet-700 hover:to-violet-800 text-white"
                            >
                                Contact Sales
                                <ArrowRight className="h-3.5 w-3.5" />
                            </Button>
                        </Link>
                    </div>
                </DialogFooter>
            </DialogContent>
        </Dialog>
    );
}

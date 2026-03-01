"use client";

/**
 * RunRiskPanel — Phase 15 Part 4
 * Displays a risk indicator banner on the run detail page.
 * CRITICAL  → >20% low confidence OR >10% rejected
 * WARNING   → >10% low confidence OR any pending
 * OK        → everything looks good
 */

import { AlertTriangle, ShieldCheck, AlertOctagon } from "lucide-react";

interface Props {
    total: number;
    low: number;
    rejected: number;
    pending: number;
}

type RiskLevel = "CRITICAL" | "WARNING" | "OK";

function computeRisk(total: number, low: number, rejected: number, pending: number): {
    level: RiskLevel;
    reasons: string[];
} {
    if (total === 0) return { level: "OK", reasons: [] };

    const lowPct = (low / total) * 100;
    const rejectedPct = (rejected / total) * 100;
    const reasons: string[] = [];

    if (lowPct > 20) reasons.push(`${Math.round(lowPct)}% of answers have low confidence (>${20}% threshold)`);
    if (rejectedPct > 10) reasons.push(`${Math.round(rejectedPct)}% of answers rejected (>${10}% threshold)`);

    if (reasons.length > 0) return { level: "CRITICAL", reasons };

    if (lowPct > 10) reasons.push(`${Math.round(lowPct)}% of answers have low confidence`);
    if (pending > 0) reasons.push(`${pending} answer${pending !== 1 ? "s" : ""} still pending review`);

    if (reasons.length > 0) return { level: "WARNING", reasons };

    return { level: "OK", reasons: [] };
}

export function RunRiskPanel({ total, low, rejected, pending }: Props) {
    const { level, reasons } = computeRisk(total, low, rejected, pending);

    if (level === "OK") {
        return (
            <div className="flex items-center gap-2.5 rounded-lg border border-green-200 bg-green-50/60 px-4 py-3">
                <ShieldCheck className="h-5 w-5 text-green-600 shrink-0" />
                <div>
                    <p className="text-sm font-semibold text-green-800">Risk Assessment: Low</p>
                    <p className="text-xs text-green-700 mt-0.5">
                        Confidence distribution and review rates are within acceptable thresholds.
                    </p>
                </div>
                <span className="ml-auto rounded-full bg-green-100 px-2.5 py-0.5 text-xs font-semibold text-green-800 border border-green-200">
                    OK
                </span>
            </div>
        );
    }

    if (level === "WARNING") {
        return (
            <div className="flex items-start gap-2.5 rounded-lg border border-amber-200 bg-amber-50/60 px-4 py-3">
                <AlertTriangle className="h-5 w-5 text-amber-600 shrink-0 mt-0.5" />
                <div className="flex-1 min-w-0">
                    <p className="text-sm font-semibold text-amber-800">Risk Assessment: Warning</p>
                    <ul className="mt-1 space-y-0.5">
                        {reasons.map((r, i) => (
                            <li key={i} className="text-xs text-amber-700 leading-snug">• {r}</li>
                        ))}
                    </ul>
                </div>
                <span className="ml-auto rounded-full bg-amber-100 px-2.5 py-0.5 text-xs font-semibold text-amber-800 border border-amber-200 shrink-0">
                    WARNING
                </span>
            </div>
        );
    }

    // CRITICAL
    return (
        <div className="flex items-start gap-2.5 rounded-lg border border-red-200 bg-red-50/60 px-4 py-3">
            <AlertOctagon className="h-5 w-5 text-red-600 shrink-0 mt-0.5" />
            <div className="flex-1 min-w-0">
                <p className="text-sm font-semibold text-red-800">Risk Assessment: Critical</p>
                <ul className="mt-1 space-y-0.5">
                    {reasons.map((r, i) => (
                        <li key={i} className="text-xs text-red-700 leading-snug">• {r}</li>
                    ))}
                </ul>
                <p className="text-xs text-red-600 mt-1.5 font-medium">
                    Manual review is strongly recommended before exporting.
                </p>
            </div>
            <span className="ml-auto rounded-full bg-red-100 px-2.5 py-0.5 text-xs font-semibold text-red-800 border border-red-200 shrink-0">
                CRITICAL
            </span>
        </div>
    );
}

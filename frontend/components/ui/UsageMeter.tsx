"use client";

/**
 * UsageMeter
 * Compact horizontal progress bar showing used / limit with colour coding.
 *
 * Color bands:
 *   0–69%  → neutral (primary)
 *   70–89% → warning (amber)
 *   90–100%→ danger  (red)
 */

import { useEffect, useRef } from "react";
import { AlertTriangle } from "lucide-react";

export interface UsageMeterProps {
    label: string;
    used: number;
    limit: number;
    percent: number;
    /** Optional suffix for the "used" value (e.g. "this month") */
    sublabel?: string;
}

function barColor(pct: number): string {
    if (pct >= 90) return "bg-red-500";
    if (pct >= 70) return "bg-amber-400";
    return "bg-primary";
}

function textAccent(pct: number): string {
    if (pct >= 90) return "text-red-600";
    if (pct >= 70) return "text-amber-600";
    return "text-foreground";
}

export function UsageMeter({ label, used, limit, percent, sublabel }: UsageMeterProps) {
    const barRef = useRef<HTMLDivElement>(null);
    const pct = Math.min(100, Math.max(0, percent));

    useEffect(() => {
        if (barRef.current) {
            barRef.current.style.width = `${Math.max(pct, 2)}%`;
        }
    }, [pct]);

    const isDanger = pct >= 90;
    const isWarning = pct >= 70 && pct < 90;

    return (
        <div className="space-y-1.5">
            <div className="flex items-baseline justify-between gap-2 text-sm">
                <span className="font-medium text-foreground">
                    {label}
                    {sublabel && (
                        <span className="ml-1 text-xs font-normal text-muted-foreground">
                            ({sublabel})
                        </span>
                    )}
                </span>
                <span className={`tabular-nums text-xs font-semibold ${textAccent(pct)}`}>
                    {used.toLocaleString()}
                    <span className="font-normal text-muted-foreground">
                        {" "}/ {limit.toLocaleString()}
                    </span>
                    <span className="ml-1 text-muted-foreground">({pct}%)</span>
                </span>
            </div>

            <div className="h-2 w-full overflow-hidden rounded-full bg-muted">
                <div
                    ref={barRef}
                    className={`h-full rounded-full transition-all duration-500 ${barColor(pct)}`}
                />
            </div>

            {isDanger && (
                <p className="flex items-center gap-1 text-xs font-medium text-red-600">
                    <AlertTriangle className="h-3 w-3" />
                    Limit nearly reached — upgrade to avoid interruption
                </p>
            )}
            {isWarning && (
                <p className="flex items-center gap-1 text-xs font-medium text-amber-600">
                    <AlertTriangle className="h-3 w-3" />
                    Approaching limit
                </p>
            )}
        </div>
    );
}

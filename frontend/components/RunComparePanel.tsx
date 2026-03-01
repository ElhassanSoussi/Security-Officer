"use client";

/**
 * RunComparePanel — Phase 15 Part 5
 * Dropdown to select a "compare to" run, then shows delta indicators:
 *   NEW / REMOVED / MODIFIED (answer changed) / UNCHANGED
 *   ↑ confidence improved  ↓ confidence dropped
 */

import { useEffect, useState } from "react";
import { ApiClient } from "@/lib/api";
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import {
    GitCompare, Loader2, ArrowUp, ArrowDown, Minus,
    PlusCircle, MinusCircle, RefreshCw,
} from "lucide-react";
import { normalizeConfidenceScore } from "@/lib/confidence";

interface RunStub {
    id: string;
    created_at: string;
    status: string;
    input_filename?: string;
}

interface Comparison {
    change_type: "NEW" | "MODIFIED" | "UNCHANGED" | "REMOVED";
    current: {
        audit_id: string;
        question_text: string;
        answer_text: string;
        confidence_score: number | string | null;
        review_status: string;
        answer_origin?: string;
    } | null;
    previous: {
        audit_id: string;
        question_text: string;
        answer_text: string;
        confidence_score: number | string | null;
        review_status: string;
        answer_origin?: string;
    } | null;
}

interface CompareResult {
    comparisons: Comparison[];
    summary: { new: number; modified: number; unchanged: number; removed: number };
}

interface Props {
    runId: string;
    orgId: string;
    token?: string;
}

function confDelta(current: number | string | null, previous: number | string | null): "up" | "down" | "same" | null {
    const c = normalizeConfidenceScore(current);
    const p = normalizeConfidenceScore(previous);
    if (c === null || p === null) return null;
    if (c > p + 0.05) return "up";
    if (c < p - 0.05) return "down";
    return "same";
}

function ChangeTypeBadge({ type }: { type: string }) {
    switch (type) {
        case "NEW":
            return <Badge className="bg-blue-100 text-blue-800 border-blue-200 gap-1 text-[10px]"><PlusCircle className="h-2.5 w-2.5" /> NEW</Badge>;
        case "REMOVED":
            return <Badge className="bg-slate-100 text-slate-700 border-slate-200 gap-1 text-[10px]"><MinusCircle className="h-2.5 w-2.5" /> REMOVED</Badge>;
        case "MODIFIED":
            return <Badge className="bg-amber-100 text-amber-800 border-amber-200 gap-1 text-[10px]"><RefreshCw className="h-2.5 w-2.5" /> MODIFIED</Badge>;
        default:
            return <Badge className="bg-muted text-muted-foreground gap-1 text-[10px]"><Minus className="h-2.5 w-2.5" /> UNCHANGED</Badge>;
    }
}

export function RunComparePanel({ runId, orgId, token }: Props) {
    const [runs, setRuns] = useState<RunStub[]>([]);
    const [selectedOtherId, setSelectedOtherId] = useState<string>("");
    const [result, setResult] = useState<CompareResult | null>(null);
    const [loading, setLoading] = useState(false);
    const [fetchingRuns, setFetchingRuns] = useState(true);
    const [error, setError] = useState("");

    // Load available runs for selection
    useEffect(() => {
        if (!orgId) return;
        setFetchingRuns(true);
        ApiClient.getRuns(orgId, undefined, 20, token)
            .then((rs) => {
                // Exclude current run
                setRuns(rs.filter((r) => r.id !== runId));
            })
            .catch(() => setRuns([]))
            .finally(() => setFetchingRuns(false));
    }, [orgId, runId, token]);

    const handleCompare = async () => {
        if (!selectedOtherId) return;
        setLoading(true);
        setError("");
        setResult(null);
        try {
            const data = await ApiClient.compareRuns(runId, selectedOtherId, token);
            setResult(data);
        } catch (e: any) {
            setError(e?.message || "Comparison failed");
        } finally {
            setLoading(false);
        }
    };

    return (
        <Card>
            <CardHeader className="pb-3">
                <CardTitle className="flex items-center gap-2 text-base">
                    <GitCompare className="h-5 w-5 text-blue-600" />
                    Run Comparison (Delta Mode)
                </CardTitle>
                <CardDescription>
                    Compare this run&apos;s answers against a previous run to see what changed.
                </CardDescription>
            </CardHeader>
            <CardContent className="space-y-4">
                {/* Run selector */}
                <div className="flex gap-2 items-end">
                    <div className="flex-1">
                        <label className="text-xs font-medium text-muted-foreground mb-1 block">Compare to run:</label>
                        {fetchingRuns ? (
                            <div className="h-9 rounded-md border bg-muted animate-pulse" />
                        ) : (
                            <select
                                className="w-full rounded-md border bg-background px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-ring"
                                value={selectedOtherId}
                                onChange={(e) => {
                                    setSelectedOtherId(e.target.value);
                                    setResult(null);
                                }}
                                aria-label="Select run to compare"
                            >
                                <option value="">— select a run —</option>
                                {runs.map((r) => (
                                    <option key={r.id} value={r.id}>
                                        {r.id.slice(0, 8)} · {new Date(r.created_at).toLocaleDateString()} · {r.status}
                                        {r.input_filename ? ` · ${r.input_filename}` : ""}
                                    </option>
                                ))}
                            </select>
                        )}
                    </div>
                    <Button
                        size="sm"
                        disabled={!selectedOtherId || loading}
                        onClick={handleCompare}
                        className="gap-1.5 shrink-0"
                    >
                        {loading ? <Loader2 className="h-4 w-4 animate-spin" /> : <GitCompare className="h-4 w-4" />}
                        Compare
                    </Button>
                </div>

                {runs.length === 0 && !fetchingRuns && (
                    <p className="text-xs text-muted-foreground">No other completed runs found for this organisation.</p>
                )}

                {error && (
                    <div className="rounded-md border border-red-200 bg-red-50 px-3 py-2 text-xs text-red-700">{error}</div>
                )}

                {/* Summary badges */}
                {result && (
                    <div className="space-y-4">
                        <div className="flex flex-wrap gap-2">
                            <Badge className="bg-blue-100 text-blue-800 border-blue-200">
                                <PlusCircle className="h-3 w-3 mr-1" /> {result.summary.new} New
                            </Badge>
                            <Badge className="bg-amber-100 text-amber-800 border-amber-200">
                                <RefreshCw className="h-3 w-3 mr-1" /> {result.summary.modified} Modified
                            </Badge>
                            <Badge className="bg-muted text-muted-foreground">
                                <Minus className="h-3 w-3 mr-1" /> {result.summary.unchanged} Unchanged
                            </Badge>
                            <Badge className="bg-slate-100 text-slate-700 border-slate-200">
                                <MinusCircle className="h-3 w-3 mr-1" /> {result.summary.removed} Removed
                            </Badge>
                        </div>

                        {/* Comparison rows — show only non-unchanged by default, up to 30 */}
                        <div className="max-h-[400px] overflow-auto rounded-md border divide-y text-xs">
                            {result.comparisons
                                .filter((c) => c.change_type !== "UNCHANGED")
                                .slice(0, 30)
                                .map((c, i) => {
                                    const delta = c.current && c.previous
                                        ? confDelta(c.current.confidence_score, c.previous.confidence_score)
                                        : null;

                                    return (
                                        <div key={i} className="px-3 py-2.5 space-y-1">
                                            <div className="flex items-center gap-2 flex-wrap">
                                                <ChangeTypeBadge type={c.change_type} />
                                                {delta === "up" && (
                                                    <span className="flex items-center gap-0.5 text-green-700 font-medium">
                                                        <ArrowUp className="h-3 w-3" /> conf ↑
                                                    </span>
                                                )}
                                                {delta === "down" && (
                                                    <span className="flex items-center gap-0.5 text-red-700 font-medium">
                                                        <ArrowDown className="h-3 w-3" /> conf ↓
                                                    </span>
                                                )}
                                                {(c.current?.answer_origin === "reused") && (
                                                    <Badge variant="outline" className="text-[9px] px-1.5 py-0 h-4 border-purple-200 text-purple-700 bg-purple-50">
                                                        Memory
                                                    </Badge>
                                                )}
                                                <span className="font-medium text-foreground truncate max-w-xs" title={c.current?.question_text || c.previous?.question_text || ""}>
                                                    {c.current?.question_text || c.previous?.question_text || "—"}
                                                </span>
                                            </div>

                                            {c.change_type === "NEW" && (
                                                <div className="pl-1 text-muted-foreground">
                                                    <span className="text-foreground/80">{c.current?.answer_text || "—"}</span>
                                                </div>
                                            )}

                                            {c.change_type === "REMOVED" && (
                                                <div className="pl-1 line-through text-muted-foreground/70">
                                                    {c.previous?.answer_text || "—"}
                                                </div>
                                            )}

                                            {c.change_type === "MODIFIED" && (
                                                <div className="pl-1 space-y-0.5">
                                                    <div className="flex gap-1.5">
                                                        <span className="text-muted-foreground shrink-0 w-12 text-right">before:</span>
                                                        <span className="line-through text-muted-foreground/70 truncate">{c.previous?.answer_text || "—"}</span>
                                                    </div>
                                                    <div className="flex gap-1.5">
                                                        <span className="text-muted-foreground shrink-0 w-12 text-right">after:</span>
                                                        <span className="text-foreground/90 truncate">{c.current?.answer_text || "—"}</span>
                                                    </div>
                                                </div>
                                            )}
                                        </div>
                                    );
                                })}

                            {result.comparisons.filter((c) => c.change_type !== "UNCHANGED").length === 0 && (
                                <div className="px-3 py-6 text-center text-muted-foreground">
                                    No differences found — runs are identical.
                                </div>
                            )}
                        </div>

                        {result.summary.unchanged > 0 && (
                            <p className="text-[11px] text-muted-foreground">
                                {result.summary.unchanged} unchanged answer{result.summary.unchanged !== 1 ? "s" : ""} hidden.
                            </p>
                        )}
                    </div>
                )}
            </CardContent>
        </Card>
    );
}

"use client";

import { useEffect, useState, useMemo } from "react";
import { useParams } from "next/navigation";
import { ApiClient, Run } from "@/lib/api";
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { Loader2, Download, ArrowLeft, FileText, Verified, AlertTriangle, Activity, FolderOpen, ShieldCheck, Lock, LockOpen, BarChart3, Clock, Pencil, Sparkles, Eye, Shield, Hash } from "lucide-react";
import Link from "next/link";
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table";
import { TableEmptyState } from "@/components/ui/EmptyState";
import { Dialog, DialogContent, DialogDescription, DialogFooter, DialogHeader, DialogTitle, DialogTrigger } from "@/components/ui/dialog";
import { createClient } from "@/utils/supabase/client";
import { useRouter } from "next/navigation";
import { normalizeConfidenceScore } from "@/lib/confidence";
import PageHeader from "@/components/ui/PageHeader";
import { Label } from "@/components/ui/label";
import { StepHeader } from "@/components/ui/StepHeader";
import { ConfidenceBar, ScoreGauge } from "@/components/ui/ConfidenceBar";
import { RunSummaryCards } from "@/components/RunSummaryCards";
import { ExportGatePanel } from "@/components/ExportGatePanel";
import { RunRiskPanel } from "@/components/RunRiskPanel";
import { RunComparePanel } from "@/components/RunComparePanel";
import { useRBAC } from "@/hooks/useRBAC";
import { getStoredOrgId } from "@/lib/orgContext";
import { useToast } from "@/components/ui/toaster";

export default function RunDetailPage() {
    const params = useParams();
    const runId = params.id as string;

    const [run, setRun] = useState<Run | null>(null);
    const [audits, setAudits] = useState<any[]>([]);
    const [loading, setLoading] = useState(true);
    const [error, setError] = useState("");
    const [token, setToken] = useState<string | undefined>(undefined);
    const [orgId, setOrgId] = useState<string | null>(getStoredOrgId());
    const router = useRouter();

    // Phase 14: RBAC
    const rbac = useRBAC(orgId);

    // Phase 17: Evidence Vault state
    const [evidenceGenerating, setEvidenceGenerating] = useState(false);
    const [evidenceHash, setEvidenceHash] = useState<string | null>(null);
    const [unlocking, setUnlocking] = useState(false);

    const { toast } = useToast();

    /* ── Run Intelligence (Phase 11) ── */
    const runIntelligence = useMemo(() => {
        if (!audits || audits.length === 0) return null;
        const total = audits.length;
        let high = 0, medium = 0, low = 0;
        let autoCount = 0, editedCount = 0, flaggedCount = 0, pendingReview = 0;
        audits.forEach((a: any) => {
            const label = (() => {
                const raw = String(a.confidence_score || "").trim().toUpperCase();
                if (raw === "HIGH" || raw === "MEDIUM" || raw === "LOW") return raw;
                const ratio = normalizeConfidenceScore(a.confidence_score);
                if (ratio === null) return "MEDIUM";
                if (ratio >= 0.8) return "HIGH";
                if (ratio >= 0.5) return "MEDIUM";
                return "LOW";
            })();
            if (label === "HIGH") high++;
            else if (label === "MEDIUM") medium++;
            else low++;
            if (a.is_overridden) editedCount++;
            else autoCount++;
            if (label === "LOW" && !a.verified_by_user) flaggedCount++;
            if (!a.review_status || a.review_status === "pending") pendingReview++;
        });
        const approved = audits.filter((a: any) => a.review_status === "approved").length;
        const readiness = total > 0 ? Math.round(((approved) / total) * 100) : 0;
        const autoPct = total > 0 ? Math.round((autoCount / total) * 100) : 0;
        const editedPct = total > 0 ? Math.round((editedCount / total) * 100) : 0;
        const createdAt = run ? new Date(run.created_at || "").getTime() : 0;
        const completedAt = run ? Date.now() : 0;
        const elapsed = createdAt > 0 ? completedAt - createdAt : null;
        return {
            distribution: { high, medium, low },
            autoPct,
            editedPct,
            readiness,
            total,
            flaggedCount,
            pendingReview,
            elapsed,
        };
    }, [audits, run]);

    const confidenceLabel = (value: any): "HIGH" | "MEDIUM" | "LOW" | "—" => {
        const raw = String(value || "").trim().toUpperCase();
        if (raw === "HIGH" || raw === "MEDIUM" || raw === "LOW") return raw as any;
        const ratio = normalizeConfidenceScore(value);
        if (ratio === null) return "—";
        if (ratio >= 0.8) return "HIGH";
        if (ratio >= 0.5) return "MEDIUM";
        return "LOW";
    };

    const confidenceBadgeVariant = (label: string) => {
        if (label === "HIGH") return "default";
        if (label === "MEDIUM") return "secondary";
        if (label === "LOW") return "destructive";
        return "outline";
    };

    // Phase 17: Generate evidence package handler
    async function handleGenerateEvidence() {
        if (!run) return;
        setEvidenceGenerating(true);
        try {
            const { blob, hash, filename } = await ApiClient.generateEvidence(run.id, token);
            // Trigger download
            const url = URL.createObjectURL(blob);
            const a = document.createElement("a");
            a.href = url;
            a.download = filename;
            document.body.appendChild(a);
            a.click();
            a.remove();
            URL.revokeObjectURL(url);
            // Update local run state to show it's now locked
            setRun((prev) => prev ? { ...prev, is_locked: true } as any : prev);
            setEvidenceHash(hash);
            toast({
                title: "Evidence package generated",
                description: `SHA-256: ${hash.slice(0, 16)}… — Run is now locked.`,
                variant: "success",
            });
        } catch (e: any) {
            toast({ title: "Evidence generation failed", description: e?.message, variant: "destructive" });
        } finally {
            setEvidenceGenerating(false);
        }
    }

    // Phase 17: Unlock run handler (admin/owner only)
    async function handleUnlockRun() {
        if (!run) return;
        setUnlocking(true);
        try {
            await ApiClient.unlockRun(run.id, token);
            setRun((prev) => prev ? { ...prev, is_locked: false } as any : prev);
            toast({ title: "Run unlocked", description: "You can now edit audit answers.", variant: "success" });
        } catch (e: any) {
            toast({ title: "Unlock failed", description: e?.message, variant: "destructive" });
        } finally {
            setUnlocking(false);
        }
    }

    useEffect(() => {
        async function loadData() {
            try {
                const supabase = createClient();
                const { data: { session } } = await supabase.auth.getSession();
                const accessToken = session?.access_token;
                setToken(accessToken);
                if (!accessToken) {
                    router.push("/login");
                    return;
                }

                const [runData, auditData] = await Promise.all([
                    ApiClient.getRun(runId, accessToken),
                    ApiClient.getRunAudits(runId, accessToken)
                ]);
                setRun(runData);
                setAudits(auditData);
                if (runData?.org_id) setOrgId(runData.org_id);
            } catch (err) {
                console.error(err);
                const e: any = err;
                const requestId = e?.requestId ? ` (Request ${e.requestId})` : "";
                const msg = String(e?.message || "Unknown error").replace(/^API Error:\s*/i, "");
                setError(`Failed to load run details${requestId}: ${msg}`);
            } finally {
                setLoading(false);
            }
        }
        if (runId) loadData();
    }, [runId, router]);

    if (loading) return <div className="flex h-screen items-center justify-center"><Loader2 className="h-8 w-8 animate-spin text-muted-foreground" /></div>;
    if (error || !run) return <div className="p-8 text-destructive">{error || "Run not found"}</div>;

    const statusColor =
        run.status === "COMPLETED" || run.status === "EXPORTED" || run.status === "ANALYZED"
            ? "bg-green-100 text-green-800 border-green-200"
            : run.status === "FAILED"
                ? "bg-red-100 text-red-800 border-red-200"
                : "bg-blue-100 text-blue-800 border-blue-200";

    /* ── Pipeline progress ── */
    const PIPELINE_STEPS = [
        { id: "QUEUED", label: "Queued" },
        { id: "PROCESSING", label: "Analysis" },
        { id: "COMPLETED", label: "Review" },
        { id: "EXPORTED", label: "Exported" },
    ];
    const statusOrder: Record<string, number> = { QUEUED: 0, PROCESSING: 1, COMPLETED: 2, ANALYZED: 2, EXPORTED: 3, FAILED: -1 };
    const currentStepIdx = statusOrder[run.status] ?? -1;
    const pipelineStepId = PIPELINE_STEPS[currentStepIdx]?.id || PIPELINE_STEPS[0].id;

    return (
        <div className="space-y-6">
            {/* Header */}
            <PageHeader
                breadcrumbs={
                    <Link
                        href="/runs"
                        className="inline-flex items-center gap-1.5 text-sm text-muted-foreground hover:text-primary transition-colors"
                    >
                        <ArrowLeft className="h-4 w-4" /> Back to Runs
                    </Link>
                }
                title={
                    <span className="flex items-center gap-3">
                        Run Details
                        <Badge variant="outline" className="font-mono text-xs">{run.id.slice(0, 8)}</Badge>
                    </span>
                }
                subtitle={
                    <>
                        Project: <span className="font-medium text-foreground">{run.project_id || "Unassigned"}</span>
                        {" · "}
                        Completed: {new Date(run.created_at || "").toLocaleString()}
                        {(run as any).created_by_name && (
                            <>
                                {" · "}
                                Generated by <span className="font-medium text-foreground">{(run as any).created_by_name}</span>
                            </>
                        )}
                    </>
                }
                actions={
                    (['COMPLETED','EXPORTED','ANALYZED'] as string[]).includes(run.status) && (
                        <div className="flex items-center gap-2">
                            {/* Phase 17: Generate Evidence */}
                            <Button
                                variant="outline"
                                className="gap-2"
                                onClick={handleGenerateEvidence}
                                disabled={evidenceGenerating || !!(run as any).is_locked}
                                title={(run as any).is_locked ? "Run is locked — unlock to regenerate" : "Generate tamper-evident evidence package"}
                            >
                                {evidenceGenerating
                                    ? <Loader2 className="h-4 w-4 animate-spin" />
                                    : <Shield className="h-4 w-4 text-blue-600" />
                                }
                                {evidenceGenerating ? "Generating…" : "Generate Evidence"}
                            </Button>
                            <Dialog>
                                <DialogTrigger asChild>
                                    <Button className="gap-2">
                                        <Download className="h-4 w-4" /> Download Excel
                                    </Button>
                                </DialogTrigger>
                            <DialogContent className="sm:max-w-md">
                                <DialogHeader>
                                    <DialogTitle className="flex items-center gap-2">
                                        <Lock className="h-4 w-4 text-slate-500" /> Export Summary
                                    </DialogTitle>
                                    <DialogDescription>
                                        Review the compliance audit results before downloading.
                                    </DialogDescription>
                                </DialogHeader>
                                <div className="space-y-4 py-4">
                                    {/* Stat grid */}
                                    <div className="grid grid-cols-2 gap-3">
                                        <div className="rounded-lg border bg-muted/50 p-3 text-center">
                                            <div className="text-2xl font-bold">{audits.length}</div>
                                            <div className="text-xs text-muted-foreground font-medium uppercase tracking-wide">Questions</div>
                                        </div>
                                        <div className="rounded-lg border border-amber-200 bg-amber-50/60 p-3 text-center text-amber-700">
                                            <div className="text-2xl font-bold">{run.counts_low_confidence || 0}</div>
                                            <div className="text-xs font-medium uppercase tracking-wide">Low Confidence</div>
                                        </div>
                                    </div>

                                    {/* Detail rows */}
                                    <div className="rounded-lg border bg-muted/30 p-4 text-sm space-y-2">
                                        <div className="flex justify-between">
                                            <span className="text-muted-foreground">Answered:</span>
                                            <span className="font-semibold">{run.counts_answered || 0}</span>
                                        </div>
                                        <div className="flex justify-between">
                                            <span className="text-muted-foreground">High Confidence:</span>
                                            <span className="font-semibold">{audits.filter(a => confidenceLabel(a.confidence_score) === 'HIGH').length}</span>
                                        </div>
                                        <div className="flex justify-between">
                                            <span className="text-muted-foreground">Medium Confidence:</span>
                                            <span className="font-semibold">{audits.filter(a => confidenceLabel(a.confidence_score) === 'MEDIUM').length}</span>
                                        </div>
                                        <div className="flex justify-between">
                                            <span className="text-muted-foreground">Low Confidence:</span>
                                            <span className="font-semibold text-amber-700">{audits.filter(a => confidenceLabel(a.confidence_score) === 'LOW').length}</span>
                                        </div>
                                    </div>

                                    {/* Export metadata */}
                                    <div className="rounded-lg border bg-muted/30 p-4 text-xs space-y-1.5 text-muted-foreground">
                                        <div className="flex justify-between">
                                            <span>Export timestamp:</span>
                                            <span className="font-mono">{new Date().toISOString().slice(0, 19)}</span>
                                        </div>
                                        {(run as any).created_by_name && (
                                            <div className="flex justify-between">
                                                <span>Generated by:</span>
                                                <span className="font-medium text-foreground">{(run as any).created_by_name}</span>
                                            </div>
                                        )}
                                        <div className="flex justify-between">
                                            <span>Run ID:</span>
                                            <span className="font-mono">{run.id.slice(0, 12)}…</span>
                                        </div>
                                    </div>

                                    {/* Low-confidence warning */}
                                    {(run.counts_low_confidence || 0) > 0 && (
                                        <div className="rounded-lg border border-amber-200 bg-amber-50/60 px-3 py-2 flex items-start gap-2 text-amber-800">
                                            <AlertTriangle className="h-4 w-4 mt-0.5 shrink-0" />
                                            <p className="text-xs leading-snug">
                                                {run.counts_low_confidence} answers have low confidence. Please review them before exporting.
                                            </p>
                                        </div>
                                    )}

                                    {/* Confirmation checkbox */}
                                    <div className="flex items-start gap-2.5 rounded-lg border bg-background p-3">
                                        <input
                                            type="checkbox"
                                            id="confirm-review"
                                            aria-label="Confirm review of generated answers"
                                            className="mt-0.5 h-4 w-4 rounded border-input"
                                        />
                                        <Label htmlFor="confirm-review" className="text-xs leading-snug font-medium cursor-pointer">
                                            I confirm that I have reviewed the generated answers, especially those with low confidence.
                                        </Label>
                                    </div>
                                </div>
                                <DialogFooter>
                                    <Button
                                        className="w-full sm:w-auto gap-2"
                                        onClick={async () => {
                                            const confirmed = (document.getElementById('confirm-review') as HTMLInputElement)?.checked;
                                            if (!confirmed && (run.counts_low_confidence || 0) > 0) {
                                                alert("Please confirm that you have reviewed the answers.");
                                                return;
                                            }
                                            try {
                                                await ApiClient.downloadRun(run.id, run.output_filename || "export.xlsx", token);
                                            } catch (err: any) {
                                                const msg = err?.message || "Download failed";
                                                setError(msg);
                                            }
                                        }}
                                    >
                                        <Download className="h-4 w-4" /> Confirm & Download
                                    </Button>
                                </DialogFooter>                                </DialogContent>
                            </Dialog>
                        </div>
                    )
                }
            />

            {/* Pipeline Progress Indicator */}
            {run.status !== "FAILED" && (
                <StepHeader steps={PIPELINE_STEPS} currentStepId={pipelineStepId} />
            )}

            {/* Phase 17: Lock Banner */}
            {(run as any).is_locked && (
                <div className="rounded-lg border border-blue-200 bg-blue-50 px-4 py-3 flex items-center justify-between gap-4">
                    <div className="flex items-center gap-3 text-blue-800">
                        <Lock className="h-5 w-5 shrink-0" />
                        <div>
                            <p className="text-sm font-semibold">Run is locked — Evidence package generated</p>
                            <p className="text-xs text-blue-700 mt-0.5">
                                Audit answers cannot be edited while this run is locked. An admin can unlock to allow changes.
                            </p>
                            {evidenceHash && (
                                <p className="text-xs font-mono text-blue-600 mt-1 flex items-center gap-1">
                                    <Hash className="h-3 w-3" /> {evidenceHash.slice(0, 32)}…
                                </p>
                            )}
                        </div>
                    </div>
                    {(rbac.role === "owner" || rbac.role === "admin") && (
                        <Button
                            variant="outline"
                            size="sm"
                            className="shrink-0 gap-1.5 border-blue-300 text-blue-700 hover:bg-blue-100"
                            onClick={handleUnlockRun}
                            disabled={unlocking}
                        >
                            {unlocking
                                ? <Loader2 className="h-3.5 w-3.5 animate-spin" />
                                : <LockOpen className="h-3.5 w-3.5" />
                            }
                            Unlock Run
                        </Button>
                    )}
                </div>
            )}

            {/* Phase 14: Run Summary Cards */}
            {runIntelligence && (
                <RunSummaryCards
                    total={runIntelligence.total}
                    high={runIntelligence.distribution.high}
                    medium={runIntelligence.distribution.medium}
                    low={runIntelligence.distribution.low}
                    reviewed={audits.filter((a) => a.review_status === "approved" || a.review_status === "rejected").length}
                    pending={runIntelligence.pendingReview}
                />
            )}

            {/* Legacy 3-card status/files/QA row */}
            <div className="grid gap-4 md:grid-cols-3">
                <Card>
                    <CardHeader className="pb-2">
                        <CardTitle className="text-sm font-medium flex items-center gap-2 text-muted-foreground">
                            <Activity className="h-4 w-4" /> Status
                        </CardTitle>
                    </CardHeader>
                    <CardContent>
                        <Badge className={`text-sm px-2.5 py-0.5 ${statusColor}`}>
                            {run.status}
                        </Badge>
                    </CardContent>
                </Card>
                <Card>
                    <CardHeader className="pb-2">
                        <CardTitle className="text-sm font-medium flex items-center gap-2 text-muted-foreground">
                            <FolderOpen className="h-4 w-4" /> Files
                        </CardTitle>
                    </CardHeader>
                    <CardContent className="space-y-1">
                        <div className="text-sm truncate">
                            <span className="text-muted-foreground">In:</span>{" "}
                            <span className="font-medium">{run.input_filename || "N/A"}</span>
                        </div>
                        <div className="text-sm truncate">
                            <span className="text-muted-foreground">Out:</span>{" "}
                            <span className="font-medium">{run.output_filename || "N/A"}</span>
                        </div>
                    </CardContent>
                </Card>
                <Card>
                    <CardHeader className="pb-2">
                        <CardTitle className="text-sm font-medium flex items-center gap-2 text-muted-foreground">
                            <Verified className="h-4 w-4" /> QA Summary
                        </CardTitle>
                    </CardHeader>
                    <CardContent>
                        <div className="flex gap-4">
                            <div className="flex items-center text-sm text-green-600 font-medium">
                                <Verified className="h-4 w-4 mr-1" /> {run.counts_answered || 0} Answered
                            </div>
                            {((run.counts_low_confidence || 0) > 0) && (
                                <div className="flex items-center text-sm text-amber-600 font-medium">
                                    <AlertTriangle className="h-4 w-4 mr-1" /> {run.counts_low_confidence} Low Conf
                                </div>
                            )}
                        </div>
                    </CardContent>
                </Card>
            </div>

            {/* Phase 15: Risk Panel */}
            {runIntelligence && (
                <RunRiskPanel
                    total={runIntelligence.total}
                    low={runIntelligence.distribution.low}
                    rejected={audits.filter((a: any) => a.review_status === "rejected").length}
                    pending={runIntelligence.pendingReview}
                />
            )}

            {/* ── Run Intelligence Card (Phase 11) ── */}
            {runIntelligence && (
                <Card>
                    <CardHeader>
                        <CardTitle className="flex items-center gap-2 text-base">
                            <BarChart3 className="h-5 w-5 text-blue-600" /> Run Intelligence
                        </CardTitle>
                        <CardDescription>AI-generated insights for this compliance run.</CardDescription>
                    </CardHeader>
                    <CardContent>
                        <div className="grid gap-6 md:grid-cols-2">
                            {/* Left: Confidence Distribution + Stats */}
                            <div className="space-y-4">
                                <div>
                                    <p className="text-xs font-medium text-muted-foreground mb-2 uppercase tracking-wide">Confidence Distribution</p>
                                    <ConfidenceBar
                                        segments={[
                                            { label: "High", value: runIntelligence.distribution.high, color: "bg-green-500" },
                                            { label: "Medium", value: runIntelligence.distribution.medium, color: "bg-amber-400" },
                                            { label: "Low", value: runIntelligence.distribution.low, color: "bg-red-400" },
                                        ]}
                                        height="h-4"
                                    />
                                </div>
                                <div className="grid grid-cols-2 gap-3">
                                    <div className="rounded-lg border bg-muted/30 p-3">
                                        <div className="flex items-center gap-1.5 text-xs text-muted-foreground mb-1">
                                            <Sparkles className="h-3.5 w-3.5" /> Auto-generated
                                        </div>
                                        <p className="text-xl font-bold">{runIntelligence.autoPct}%</p>
                                    </div>
                                    <div className="rounded-lg border bg-muted/30 p-3">
                                        <div className="flex items-center gap-1.5 text-xs text-muted-foreground mb-1">
                                            <Pencil className="h-3.5 w-3.5" /> Manually Edited
                                        </div>
                                        <p className="text-xl font-bold">{runIntelligence.editedPct}%</p>
                                    </div>
                                </div>
                                {runIntelligence.elapsed && runIntelligence.elapsed > 0 && (
                                    <div className="flex items-center gap-2 text-sm text-muted-foreground">
                                        <Clock className="h-4 w-4" />
                                        <span>Time since creation:{" "}
                                            <span className="font-medium text-foreground">
                                                {runIntelligence.elapsed < 60000
                                                    ? `${Math.round(runIntelligence.elapsed / 1000)}s`
                                                    : runIntelligence.elapsed < 3600000
                                                        ? `${Math.round(runIntelligence.elapsed / 60000)}m`
                                                        : `${Math.round(runIntelligence.elapsed / 3600000)}h`}
                                            </span>
                                        </span>
                                    </div>
                                )}
                            </div>
                            {/* Right: Export Readiness Gauge */}
                            <div className="flex flex-col items-center justify-center">
                                <ScoreGauge score={runIntelligence.readiness} label="Export Readiness" size="md" />
                                <div className="mt-3 flex flex-wrap gap-2 justify-center">
                                    {runIntelligence.flaggedCount > 0 && (
                                        <Badge variant="outline" className="text-xs bg-red-50 text-red-700 border-red-200">
                                            {runIntelligence.flaggedCount} flagged
                                        </Badge>
                                    )}
                                    {runIntelligence.pendingReview > 0 && (
                                        <Badge variant="outline" className="text-xs bg-amber-50 text-amber-700 border-amber-200">
                                            {runIntelligence.pendingReview} unreviewed
                                        </Badge>
                                    )}
                                </div>
                            </div>
                        </div>
                    </CardContent>
                </Card>
            )}

            {/* Phase 14: Export Gate Panel + Review Link */}
            {(['COMPLETED', 'EXPORTED', 'ANALYZED'] as string[]).includes(run.status) && (
                <div className="grid gap-4 md:grid-cols-2">
                    <ExportGatePanel
                        total={audits.length}
                        unreviewedLow={audits.filter((a) => {
                            const lbl = confidenceLabel(a.confidence_score);
                            return lbl === "LOW" && (!a.review_status || a.review_status === "pending");
                        }).length}
                        approved={audits.filter((a) => a.review_status === "approved").length}
                        rejected={audits.filter((a) => a.review_status === "rejected").length}
                        pending={runIntelligence?.pendingReview ?? 0}
                        userRole={rbac.role}
                        outputFilename={run.output_filename || undefined}
                        onExport={async () => {
                            try {
                                await ApiClient.downloadRun(run.id, run.output_filename || "export.xlsx", token);
                            } catch (err: any) {
                                setError(err?.message || "Download failed");
                            }
                        }}
                    />
                    <div className="rounded-lg border bg-card p-4 flex flex-col justify-between">
                        <div>
                            <h3 className="text-sm font-semibold mb-1">Review Audit Answers</h3>
                            <p className="text-xs text-muted-foreground leading-snug">
                                Open the Audit tab pre-filtered to this run to approve, reject, or edit individual answers before export.
                            </p>
                        </div>
                        <Link href={`/audit?run_id=${run.id}`} className="mt-4">
                            <button className="inline-flex items-center gap-2 rounded-md border bg-background px-3 py-2 text-sm font-medium hover:bg-muted transition-colors w-full justify-center">
                                <Eye className="h-4 w-4 text-blue-600" />
                                Open Audit for this Run →
                            </button>
                        </Link>
                    </div>
                </div>
            )}

            {/* Phase 15: Run Comparison (Delta Mode) */}
            {(['COMPLETED', 'EXPORTED', 'ANALYZED'] as string[]).includes(run.status) && orgId && (
                <RunComparePanel runId={run.id} orgId={orgId} token={token} />
            )}

            {/* Audit Trail */}
            <Card>
                <CardHeader className="flex flex-row items-center justify-between space-y-0">
                    <div>
                        <CardTitle className="flex items-center gap-2">
                            <ShieldCheck className="h-5 w-5 text-blue-600" /> Audit Trail
                        </CardTitle>
                        <CardDescription>
                            Detailed log of every answer generated and reviewed.
                        </CardDescription>
                    </div>
                    <Badge variant="secondary" className="text-xs">
                        {audits.length} {audits.length === 1 ? "record" : "records"}
                    </Badge>
                </CardHeader>
                <CardContent>
                    <div className="max-h-[70vh] overflow-auto rounded-md border">
                        <Table>
                            <TableHeader>
                                <TableRow>
                                    <TableHead className="w-[80px]">Cell</TableHead>
                                    <TableHead className="max-w-[300px]">Question</TableHead>
                                    <TableHead className="max-w-[300px]">Final Answer</TableHead>
                                    <TableHead>Source</TableHead>
                                    <TableHead>Conf</TableHead>
                                    <TableHead className="w-[70px]"></TableHead>
                                </TableRow>
                            </TableHeader>
                            <TableBody>
                                {audits.length === 0 ? (
                                    <TableEmptyState
                                        cols={6}
                                        icon={<FileText className="h-10 w-10" />}
                                        title="No audit records yet"
                                        description="Audit records are generated during the export step."
                                    />
                                ) : (
                                    audits.map((audit) => (
                                        <TableRow key={audit.id}>
                                            <TableCell className="font-mono bg-muted/50 font-medium text-xs">
                                                {audit.cell_reference || "?"}
                                            </TableCell>
                                            <TableCell className="truncate max-w-[300px]" title={audit.question_text}>
                                                {audit.question_text}
                                            </TableCell>
                                            <TableCell className="max-w-[300px]">
                                                <div className="flex flex-col gap-1">
                                                    <div className="truncate" title={audit.answer_text}>
                                                        {audit.answer_text}
                                                    </div>
                                                    {audit.is_overridden && (
                                                        <Badge variant="outline" className="w-fit text-[10px] px-1 py-0 h-4 border-amber-500 text-amber-600">
                                                            Edited
                                                        </Badge>
                                                    )}
                                                </div>
                                            </TableCell>
                                            <TableCell className="text-xs">
                                                <div className="font-medium">{audit.source_document}</div>
                                                <div className="text-muted-foreground">{audit.page_number}</div>
                                            </TableCell>
                                            <TableCell>
                                                <Badge variant={confidenceBadgeVariant(confidenceLabel(audit.confidence_score))}>
                                                    {confidenceLabel(audit.confidence_score)}
                                                </Badge>
                                            </TableCell>
                                            <TableCell>
                                                <Button
                                                    variant="ghost"
                                                    size="sm"
                                                    className="text-xs"
                                                    disabled={!!(run as any).is_locked}
                                                    title={(run as any).is_locked ? "Run is locked — unlock to edit" : "Edit answer"}
                                                    onClick={() => {
                                                        if ((run as any).is_locked) return;
                                                        const newAns = prompt("Edit Answer:", audit.answer_text);
                                                        if (newAns !== null && newAns !== audit.answer_text) {
                                                            import("@/utils/supabase/client").then(({ createClient }) => {
                                                                const supabase = createClient();
                                                                supabase.auth.getSession().then(({ data: { session } }) => {
                                                                    ApiClient.updateAudit(run.id, audit.id, newAns, session?.access_token).then(() => {
                                                                        window.location.reload();
                                                                    });
                                                                });
                                                            });
                                                        }
                                                    }}>
                                                    {(run as any).is_locked ? <Lock className="h-3 w-3 text-muted-foreground" /> : "Edit"}
                                                </Button>
                                            </TableCell>
                                        </TableRow>
                                    ))
                                )}
                            </TableBody>
                        </Table>
                    </div>
                </CardContent>
            </Card>
        </div>
    );
}

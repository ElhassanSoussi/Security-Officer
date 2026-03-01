"use client";

import { useState, useEffect, useMemo } from "react";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Loader2, FileSpreadsheet, PlayCircle, Download, CheckCheck, XCircle, ShieldCheck, AlertTriangle, CheckCircle2 } from "lucide-react";
import { ApiClient } from "@/lib/api";
import { config } from "@/lib/config";
import { ReviewGrid } from "@/components/review-grid";
import { Run, QuestionItem } from "@/types";
import { useToast } from "@/components/ui/toaster";
import { createClient } from "@/utils/supabase/client";
import { normalizeConfidenceScore } from "@/lib/confidence";
import { Badge } from "@/components/ui/badge";
import { ExportReadinessGate, ExportWarning } from "@/components/ui/ExportReadinessGate";
import { deriveAnswerStatus } from "@/components/ui/AnswerStatusBadge";

// ── Wizard step definitions ───────────────────────
const WIZARD_STEPS = [
    { id: "select",   label: "Select Project" },
    { id: "upload",   label: "Upload Questionnaire" },
    { id: "confirm",  label: "Confirm & Start" },
    { id: "progress", label: "Analysis" },
    { id: "review",   label: "Review & Export" },
] as const;
type WizardStepId = (typeof WIZARD_STEPS)[number]["id"];

function WizardStepper({ current }: { current: WizardStepId }) {
    const idx = WIZARD_STEPS.findIndex((s) => s.id === current);
    return (
        <nav aria-label="Wizard steps" className="flex items-center gap-0 mb-6">
            {WIZARD_STEPS.map((step, i) => {
                const done = i < idx;
                const active = i === idx;
                return (
                    <div key={step.id} className="flex items-center flex-1 last:flex-none">
                        <div className="flex flex-col items-center">
                            <div className={`flex h-7 w-7 items-center justify-center rounded-full border-2 text-xs font-bold transition-colors ${
                                done   ? "bg-green-600 border-green-600 text-white" :
                                active ? "bg-primary border-primary text-primary-foreground" :
                                         "bg-muted border-border text-muted-foreground"
                            }`}>
                                {done ? <CheckCircle2 className="h-4 w-4" /> : i + 1}
                            </div>
                            <span className={`mt-1 text-[10px] font-medium whitespace-nowrap ${active ? "text-foreground" : "text-muted-foreground"}`}>
                                {step.label}
                            </span>
                        </div>
                        {i < WIZARD_STEPS.length - 1 && (
                            <div className={`flex-1 h-0.5 mx-1 mb-4 transition-colors ${done ? "bg-green-400" : "bg-border"}`} />
                        )}
                    </div>
                );
            })}
        </nav>
    );
}

interface RunWizardProps {
    orgId: string;
    projectId?: string;
}

export function RunWizard({ orgId, projectId }: RunWizardProps) {
    const { toast } = useToast();
    const [file, setFile] = useState<File | null>(null);
    const [analyzing, setAnalyzing] = useState(false);
    const [runData, setRunData] = useState<Run | null>(null);
    const [questions, setQuestions] = useState<QuestionItem[]>([]);
    const [wizardStep, setWizardStep] = useState<WizardStepId>("upload");
    const [error, setError] = useState("");
    const [exporting, setExporting] = useState(false);
    const [token, setToken] = useState<string | undefined>(undefined);
    const [bulkActioning, setBulkActioning] = useState(false);
    const [exportGateOpen, setExportGateOpen] = useState(false);

    // Map wizard steps to legacy binary step for card rendering
    const step = (wizardStep === "review") ? "review" : "upload";

    // Review stats derived from questions state
    const reviewStats = useMemo(() => {
        const total = questions.length;
        const approved = questions.filter(q => q.review_status === "approved").length;
        const rejected = questions.filter(q => q.review_status === "rejected").length;
        const pending = total - approved - rejected;
        return {
            total,
            approved,
            rejected,
            pending,
            allReviewed: pending === 0 && total > 0,
            readyForExport: approved > 0 && pending === 0,
        };
    }, [questions]);

    // Phase 11: Export readiness warnings
    const exportWarnings = useMemo<ExportWarning[]>(() => {
        const flagged = questions.filter(q => deriveAnswerStatus(q) === "flagged").length;
        const lowConf = questions.filter(q => q.confidence === "LOW").length;
        const unreviewed = questions.filter(q => !q.review_status || q.review_status === "pending").length;
        return [
            { type: "flagged" as const, count: flagged, label: `${flagged} answer(s) flagged for issues` },
            { type: "low_confidence" as const, count: lowConf, label: `${lowConf} answer(s) with low confidence` },
            { type: "unreviewed" as const, count: unreviewed, label: `${unreviewed} answer(s) not yet reviewed` },
        ];
    }, [questions]);

    // Phase 4.3: Load latest run on mount
    useEffect(() => {
        const supabase = createClient();

        async function loadLatestRun() {
            const { data: { session } } = await supabase.auth.getSession();
            const accessToken = session?.access_token;
            setToken(accessToken);

            try {
                const runs = await ApiClient.getRuns(orgId, projectId, 1, accessToken);
                if (runs && runs.length > 0) {
                    const latestRun = runs[0];
                    if (["COMPLETED", "ANALYZED", "EXPORTED"].includes(latestRun.status)) {
                        setRunData(latestRun);

                        const audits = await ApiClient.getRunAudits(latestRun.id, accessToken);
                        if (audits && audits.length > 0) {
                            const items: QuestionItem[] = audits.map((a: any) => ({
                                audit_id: a.id,
                                sheet_name: a.sheet_name || "Sheet1",
                                cell_coordinate: a.cell_reference || "A1",
                                question: a.question_text,
                                ai_answer: a.original_answer || a.answer_text,
                                final_answer: a.answer_text,
                                confidence: (() => {
                                    const raw = String(a.confidence_score || "").trim().toUpperCase();
                                    if (raw === "HIGH" || raw === "MEDIUM" || raw === "LOW") return raw as any;
                                    const ratio = normalizeConfidenceScore(a.confidence_score);
                                    if (ratio === null) return "MEDIUM";
                                    if (ratio >= 0.8) return "HIGH";
                                    if (ratio >= 0.5) return "MEDIUM";
                                    return "LOW";
                                })(),
                                sources: a.source_document ? [a.source_document] : [],
                                source_excerpt: a.source_excerpt || undefined,
                                is_verified: a.verified_by_user || a.review_status === "approved" || false,
                                edited_by_user: a.is_overridden || false,
                                review_status: a.review_status || "pending",
                            }));
                            setQuestions(items);
                            setWizardStep("review");
                        }
                    }
                }
            } catch (e) {
                console.error("Failed to load existing run:", e);
            }
        }
        if (orgId && projectId) {
            loadLatestRun();
        }
    }, [orgId, projectId]);

    const handleBulkAction = async (action: "approved" | "rejected") => {
        if (!runData?.id) return;
        setBulkActioning(true);
        try {
            let t = token;
            if (!t) {
                const supabase = createClient();
                const { data: { session } } = await supabase.auth.getSession();
                t = session?.access_token || undefined;
                setToken(t);
            }

            await ApiClient.bulkReviewAudits(runData.id, action, "", t);

            // Update local state
            const newItems = questions.map(q => ({
                ...q,
                review_status: q.review_status === "pending" ? action : q.review_status,
                is_verified: q.review_status === "pending" ? true : q.is_verified,
            }));
            setQuestions(newItems as QuestionItem[]);

            toast({
                title: action === "approved" ? "All Approved" : "All Rejected",
                description: `Pending answers ${action === "approved" ? "approved" : "rejected"}.`,
                variant: action === "approved" ? "success" : "default",
            });
        } catch (e: any) {
            toast({ title: "Bulk Action Failed", description: e?.message || "Failed", variant: "destructive" });
        } finally {
            setBulkActioning(false);
        }
    };

    const handleExport = async () => {
        if (!file) {
            toast({
                title: "Template Missing",
                description: "The original Excel file is missing. Please re-upload the template to export.",
                variant: "destructive"
            });
            return;
        }

        if (!runData) return;

        // Phase 11: Check if there are warnings that should trigger the gate
        const hasIssues = exportWarnings.some(w => w.count > 0);
        if (hasIssues && !exportGateOpen) {
            setExportGateOpen(true);
            return;
        }

        await performExport();
    };

    const performExport = async () => {
        if (!file || !runData) return;
        setExportGateOpen(false);

        setExporting(true);
        try {
            let t = token;
            if (!t) {
                const supabase = createClient();
                const { data: { session } } = await supabase.auth.getSession();
                t = session?.access_token || undefined;
                setToken(t);
            }
            await ApiClient.generateExport(file, questions, orgId, projectId, runData.id, t);
            toast({
                title: "Export Success",
                description: `Excel generated. ${reviewStats.approved} approved answer(s) written; ${reviewStats.rejected + reviewStats.pending} left blank.`,
            });
        } catch (e: any) {
            console.error(e);
            toast({
                title: "Export Failed",
                description: e.message || "Could not generate export.",
                variant: "destructive"
            });
        } finally {
            setExporting(false);
        }
    };

    const handleFileChange = (e: React.ChangeEvent<HTMLInputElement>) => {
        if (e.target.files && e.target.files[0]) {
            setFile(e.target.files[0]);
            setError("");
        }
    };

    const handleAnalyze = async () => {
        if (!file) return;

        setAnalyzing(true);
        setError("");
        setWizardStep("progress");

        try {
            const formData = new FormData();
            formData.append("file", file);
            formData.append("org_id", orgId);
            if (projectId) formData.append("project_id", projectId);

            const headers: HeadersInit = {};
            let t = token;
            if (!t) {
                const supabase = createClient();
                const { data: { session } } = await supabase.auth.getSession();
                t = session?.access_token || undefined;
                setToken(t);
            }
            if (t) headers["Authorization"] = `Bearer ${t}`;

            const res = await fetch(`${config.apiUrl}/analyze-excel`, {
                method: "POST",
                body: formData,
                headers
            });

            if (!res.ok) {
                let detail = `Server returned ${res.status}`;
                try {
                    const errBody = await res.json();
                    detail = errBody?.detail
                        ? (typeof errBody.detail === "string" ? errBody.detail : JSON.stringify(errBody.detail))
                        : detail;
                } catch { /* body not JSON */ }
                throw new Error(detail);
            }

            const data = await res.json();

            setRunData({
                id: data.run_id,
                status: "COMPLETED",
                org_id: orgId,
                project_id: projectId,
                questionnaire_filename: file.name,
                created_at: new Date().toISOString()
            });
            setQuestions(data.data || []);
            setWizardStep("review");
            toast({ title: "Analysis Complete", description: `Found ${(data.data || []).length} questions.`, variant: "success" });

        } catch (e: any) {
            console.error(e);
            const msg = "Analysis failed: " + e.message;
            setError(msg);
            setWizardStep("upload");
            toast({ title: "Analysis Failed", description: e.message || "Could not analyze questionnaire.", variant: "destructive" });
        } finally {
            setAnalyzing(false);
        }
    };

    const handleDownloadSample = async () => {
        try {
            await ApiClient.downloadSampleQuestionnaire();
        } catch (e) {
            console.error(e);
            setError("Failed to download sample.");
        }
    };

    const handleReset = () => {
        setFile(null);
        setRunData(null);
        setQuestions([]);
        setWizardStep("upload");
        setError("");
        setExporting(false);
    };

    return (
        <div className="space-y-8">
            <WizardStepper current={wizardStep} />

            {step === "upload" && (
                <Card>
                    <CardHeader>
                        <CardTitle>Run New Questionnaire</CardTitle>
                        <CardDescription>
                            Upload an Excel file to start a new analysis run for this project.
                            {projectId && " AI answers will be grounded using documents in the Knowledge Vault."}
                        </CardDescription>
                    </CardHeader>
                    <CardContent className="space-y-6">
                        <div className="grid w-full max-w-sm items-center gap-1.5">
                            <Label htmlFor="questionnaire">Excel File</Label>
                            <Input id="questionnaire" type="file" accept=".xlsx,.xlsm" onChange={handleFileChange} disabled={analyzing} />
                        </div>

                        {error && (
                            <div className="p-3 bg-red-50 text-red-600 text-sm rounded-md flex items-center">
                                <span className="font-bold mr-2">Error:</span> {error}
                            </div>
                        )}

                        <div className="flex items-center gap-4">
                            <Button onClick={handleAnalyze} disabled={!file || analyzing}>
                                {analyzing ? (
                                    <>
                                        <Loader2 className="mr-2 h-4 w-4 animate-spin" /> Analyzing...
                                    </>
                                ) : (
                                    <>
                                        <PlayCircle className="mr-2 h-4 w-4" /> Start Analysis
                                    </>
                                )}
                            </Button>

                            <Button variant="outline" onClick={handleDownloadSample}>
                                <FileSpreadsheet className="mr-2 h-4 w-4" /> Download Sample
                            </Button>
                        </div>
                    </CardContent>
                </Card>
            )}

            {step === "review" && runData && (
                <div className="space-y-6">
                    {/* Review Stats + Export Gate Banner */}
                    <Card className={reviewStats.readyForExport ? "bg-green-50/50 border-green-200" : "bg-amber-50/50 border-amber-200"}>
                        <CardHeader>
                            <div className="flex items-center justify-between flex-wrap gap-4">
                                <div>
                                    <CardTitle className={reviewStats.readyForExport ? "text-green-700" : "text-amber-700"}>
                                        {reviewStats.readyForExport ? (
                                            <span className="flex items-center gap-2">
                                                <ShieldCheck className="h-5 w-5" /> Ready for Export
                                            </span>
                                        ) : (
                                            <span className="flex items-center gap-2">
                                                <AlertTriangle className="h-5 w-5" /> Review Required
                                            </span>
                                        )}
                                    </CardTitle>
                                    <CardDescription className="mt-1">
                                        {questions.length} question{questions.length !== 1 ? "s" : ""} found.
                                        {" "}Review each answer, then export. Only <strong>approved</strong> answers are written to the Excel.
                                    </CardDescription>
                                </div>
                                <div className="flex gap-2 flex-wrap">
                                    <Button variant="outline" onClick={handleReset} size="sm">
                                        Start Over
                                    </Button>
                                    <Button
                                        onClick={handleExport}
                                        disabled={exporting || questions.length === 0 || reviewStats.approved === 0}
                                        size="sm"
                                        className={reviewStats.readyForExport ? "bg-green-600 hover:bg-green-700" : ""}
                                    >
                                        {exporting ? <Loader2 className="mr-2 h-4 w-4 animate-spin" /> : <Download className="mr-2 h-4 w-4" />}
                                        Export Excel ({reviewStats.approved} approved)
                                    </Button>
                                </div>
                            </div>

                            {/* Review Stats Bar */}
                            <div className="flex flex-wrap gap-3 mt-4">
                                <Badge variant="outline" className="bg-yellow-50 text-yellow-700 border-yellow-200">
                                    Pending: {reviewStats.pending}
                                </Badge>
                                <Badge variant="outline" className="bg-green-50 text-green-700 border-green-200">
                                    Approved: {reviewStats.approved}
                                </Badge>
                                <Badge variant="outline" className="bg-red-50 text-red-700 border-red-200">
                                    Rejected: {reviewStats.rejected}
                                </Badge>

                                {/* Bulk Actions */}
                                {reviewStats.pending > 0 && (
                                    <div className="flex gap-2 ml-auto">
                                        <Button
                                            variant="outline"
                                            size="sm"
                                            className="h-7 text-xs text-green-700 border-green-200 hover:bg-green-50"
                                            onClick={() => handleBulkAction("approved")}
                                            disabled={bulkActioning}
                                        >
                                            {bulkActioning ? <Loader2 className="h-3 w-3 animate-spin mr-1" /> : <CheckCheck className="h-3 w-3 mr-1" />}
                                            Approve All Pending
                                        </Button>
                                        <Button
                                            variant="outline"
                                            size="sm"
                                            className="h-7 text-xs text-red-700 border-red-200 hover:bg-red-50"
                                            onClick={() => handleBulkAction("rejected")}
                                            disabled={bulkActioning}
                                        >
                                            <XCircle className="h-3 w-3 mr-1" />
                                            Reject All Pending
                                        </Button>
                                    </div>
                                )}
                            </div>
                        </CardHeader>
                    </Card>

                    <ReviewGrid
                        items={questions}
                        onItemsChange={setQuestions}
                        uploadDocsHref={projectId ? `/projects/${orgId}/${projectId}` : `/projects?orgId=${orgId}`}
                        runId={runData?.id}
                        token={token}
                    />

                    {/* Phase 11: Export Readiness Gate */}
                    <ExportReadinessGate
                        open={exportGateOpen}
                        onOpenChange={setExportGateOpen}
                        warnings={exportWarnings}
                        totalQuestions={reviewStats.total}
                        approvedCount={reviewStats.approved}
                        isAdmin={true}
                        onForceExport={performExport}
                        onReturnToReview={() => setExportGateOpen(false)}
                        exporting={exporting}
                    />
                </div>
            )}
        </div>
    );
}

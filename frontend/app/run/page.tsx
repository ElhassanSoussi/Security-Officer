"use client";

import { useState, useEffect } from "react";
import { Button } from "@/components/ui/button";
import { CardContent, CardHeader, CardTitle, CardDescription } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Loader2, FileSpreadsheet, PlayCircle, Download, FolderKanban, CheckCircle2, Upload, AlertTriangle, Search } from "lucide-react";
import { createClient } from "@/utils/supabase/client";
import { ApiClient } from "@/lib/api";
import { config } from "@/lib/config";
import { ReviewGrid } from "@/components/review-grid";
import { useRouter } from "next/navigation";
import { getStoredOrgId, setStoredOrgId } from "@/lib/orgContext";
import { Project } from "@/types";
import PageHeader from "@/components/ui/PageHeader";
import SectionCard from "@/components/ui/SectionCard";
import { StepHeader } from "@/components/ui/StepHeader";
import { Select } from "@/components/ui/select";

export interface Run {
    id: string;
    org_id: string;
    project_id?: string;
    questionnaire_filename: string;
    status: "QUEUED" | "PROCESSING" | "COMPLETED" | "ANALYZED" | "EXPORTED" | "FAILED";
    created_at: string;
    export_filename?: string;
    output_filename?: string;
    input_filename?: string;
    counts_answered?: number;
    counts_low_confidence?: number;
    error_message?: string;
}

export interface QuestionItem {
    sheet_name: string;
    cell_coordinate: string;
    question: string;
    ai_answer: string;
    final_answer: string;
    confidence: "HIGH" | "LOW" | "MEDIUM";
    sources: string[];
    is_verified: boolean;
    edited_by_user: boolean;
}

export default function RunPage() {
    const router = useRouter();

    const [currentOrgId, setCurrentOrgId] = useState<string | null>(null);
    const [projects, setProjects] = useState<Project[]>([]);
    const [selectedProjectId, setSelectedProjectId] = useState<string | null>(null);
    const [file, setFile] = useState<File | null>(null);
    const [analyzing, setAnalyzing] = useState(false);
    const [exporting, setExporting] = useState(false);
    const [runData, setRunData] = useState<Run | null>(null);
    const [questions, setQuestions] = useState<QuestionItem[]>([]);
    const [step, setStep] = useState<"select" | "upload" | "analyze" | "review">("select");
    const [error, setError] = useState("");
    const [_token, setToken] = useState<string | undefined>(undefined);

    const getFreshToken = async (): Promise<string | undefined> => {
        const supabase = createClient();
        const { data: { session } } = await supabase.auth.getSession();
        if (!session?.access_token) return undefined;

        const expiresAtMs = (session.expires_at || 0) * 1000;
        if (expiresAtMs && expiresAtMs < Date.now() + 30_000) {
            const { data, error } = await supabase.auth.refreshSession();
            if (!error && data.session?.access_token) {
                return data.session.access_token;
            }
        }
        return session.access_token;
    };

    // Load Org ID
    useEffect(() => {
        async function init() {
            const freshToken = await getFreshToken();
            if (!freshToken) {
                router.push("/login");
                return;
            }
            setToken(freshToken);

            ApiClient.getMyOrgs(freshToken).then(orgs => {
                if (orgs && orgs.length > 0) {
                    const stored = getStoredOrgId() || "";
                    const selected = orgs.find((o: any) => o.id === stored) || orgs[0];
                    setCurrentOrgId(selected.id);
                    setStoredOrgId(selected.id);

                    // Load projects for the org
                    ApiClient.getProjects(selected.id, freshToken).then(projs => {
                        setProjects(projs || []);
                    }).catch(err => {
                        console.error("Failed to load projects:", err);
                    });
                } else {
                    router.push("/onboarding");
                }
            }).catch(err => {
                console.error(err);
                if (String(err?.message || "").toLowerCase().includes("unauthorized")) {
                    router.push("/login");
                    return;
                }
                setError("Failed to load organization.");
            });
        }

        init();
    }, [router]);

    const handleFileChange = (e: React.ChangeEvent<HTMLInputElement>) => {
        if (e.target.files && e.target.files[0]) {
            setFile(e.target.files[0]);
            setError("");
        }
    };

    const handleAnalyze = async () => {
        if (!file || !currentOrgId) {
            setError("Missing file or organization context.");
            return;
        }

        setStep("analyze");
        setAnalyzing(true);
        setError("");

        try {
            const freshToken = await getFreshToken();
            if (!freshToken) {
                router.push("/login");
                return;
            }
            setToken(freshToken);

            const formData = new FormData();
            formData.append("file", file);
            formData.append("org_id", currentOrgId);
            if (selectedProjectId) formData.append("project_id", selectedProjectId);

            const headers: HeadersInit = {};
            headers["Authorization"] = `Bearer ${freshToken}`;

            const res = await fetch(`${config.apiUrl}/analyze-excel`, {
                method: "POST",
                body: formData,
                headers
            });

            if (res.status === 401) {
                router.push("/login");
                return;
            }
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
                org_id: currentOrgId,
                project_id: selectedProjectId || undefined,
                questionnaire_filename: file.name,
                created_at: new Date().toISOString()
            });
            setQuestions(data.data || []); // API changed to return {data: items}
            setStep("review");

        } catch (e: any) {
            console.error(e);
            setError("Analysis failed: " + e.message);
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

    const handleExport = async () => {
        if (!file || !currentOrgId) return;
        setExporting(true);
        try {
            const freshToken = await getFreshToken();
            if (!freshToken) {
                router.push("/login");
                return;
            }
            setToken(freshToken);
            await ApiClient.generateExport(file, questions, currentOrgId, selectedProjectId || undefined, runData?.id, freshToken);
        } catch (e: any) {
            console.error(e);
            if (String(e?.message || "").toLowerCase().includes("unauthorized")) {
                router.push("/login");
                return;
            }
            setError(e.message);
        } finally {
            setExporting(false);
        }
    };

    if (!currentOrgId && !error) return <div className="p-8 text-center text-muted-foreground">Loading organization context…</div>;

    /* ── Step indicator data ── */
    const STEPS = [
        { id: "select", label: "Select Project", icon: FolderKanban },
        { id: "upload", label: "Upload Questionnaire", icon: Upload },
        { id: "analyze", label: "Run Analysis", icon: Search },
        { id: "review", label: "Review & Export", icon: CheckCircle2 },
    ];

    return (
        <div className="space-y-6 max-w-5xl mx-auto pb-12">
            <PageHeader
                title="Run Questionnaire"
                subtitle="Upload a vendor security questionnaire and generate AI-powered answers."
            />

            {/* ── Step indicator ── */}
            <StepHeader steps={STEPS} currentStepId={step} />

            {step === "select" && (
                <SectionCard>
                    <CardHeader>
                        <CardTitle>Select Project</CardTitle>
                        <CardDescription>
                            Choose the compliance project this questionnaire belongs to, or proceed at the organization level.
                        </CardDescription>
                    </CardHeader>
                    <CardContent className="space-y-6">
                        <div className="grid w-full max-w-sm items-center gap-1.5">
                            <Label htmlFor="project-select">
                                <FolderKanban className="inline mr-1 h-4 w-4" /> Project
                            </Label>
                            <Select
                                id="project-select"
                                value={selectedProjectId || ""}
                                onChange={(e) => setSelectedProjectId(e.target.value || null)}
                                aria-label="Select project"
                            >
                                <option value="">— No project (org-level) —</option>
                                {projects.map((p) => (
                                    <option key={p.project_id} value={p.project_id}>
                                        {p.project_name || p.project_id}
                                    </option>
                                ))}
                            </Select>
                            {projects.length === 0 && currentOrgId && (
                                <p className="text-xs text-slate-400">
                                    No projects yet.{" "}
                                    <a href="/projects" className="text-blue-600 hover:underline">Create one</a> to organize your runs.
                                </p>
                            )}
                        </div>

                        <Button onClick={() => setStep("upload")} size="lg">
                            Continue to Upload →
                        </Button>
                    </CardContent>
                </SectionCard>
            )}

            {step === "upload" && (
                <SectionCard>
                    <CardHeader>
                        <CardTitle>Upload Questionnaire</CardTitle>
                        <CardDescription>
                            Upload the <code className="font-mono text-xs bg-slate-100 px-1 rounded">.xlsx</code> file you received from the client.
                        </CardDescription>
                    </CardHeader>
                    <CardContent className="space-y-6">
                        <div className="grid w-full max-w-sm items-center gap-1.5">
                            <Label htmlFor="questionnaire">Excel File (.xlsx)</Label>
                            <Input id="questionnaire" type="file" accept=".xlsx,.xlsm" onChange={handleFileChange} disabled={analyzing} />
                            {file && (
                                <p className="text-xs text-slate-500 flex items-center gap-1">
                                    <FileSpreadsheet className="h-3 w-3" /> {file.name}
                                </p>
                            )}
                        </div>

                        {error && (
                            <div className="p-3 bg-red-50 text-red-600 text-sm rounded-md border border-red-100">
                                <span className="font-semibold">Error: </span>{error}
                            </div>
                        )}

                        <div className="flex items-center gap-3 pt-1">
                            <Button variant="outline" onClick={() => setStep("select")}>
                                ← Back
                            </Button>
                            <Button onClick={handleAnalyze} disabled={!file || analyzing || !currentOrgId} size="lg">
                                <PlayCircle className="mr-2 h-4 w-4" /> Run Analysis
                            </Button>
                            <Button variant="ghost" onClick={handleDownloadSample}>
                                <FileSpreadsheet className="mr-2 h-4 w-4" /> Download Sample
                            </Button>
                        </div>
                        <p className="text-xs text-muted-foreground leading-relaxed">
                            Your file will be processed by AI against your organization&apos;s Knowledge Vault.
                            Answers include confidence scores and source citations. No data leaves your workspace.
                        </p>
                    </CardContent>
                </SectionCard>
            )}

            {step === "analyze" && (
                <SectionCard>
                    <CardHeader>
                        <CardTitle>Running Analysis</CardTitle>
                        <CardDescription>
                            AI is processing your questionnaire against your organization&apos;s document library.
                        </CardDescription>
                    </CardHeader>
                    <CardContent className="py-12 text-center space-y-4">
                        <Loader2 className="h-10 w-10 animate-spin text-primary mx-auto" />
                        <p className="text-sm text-slate-500">
                            Analyzing <span className="font-medium text-slate-700">{file?.name}</span>…
                        </p>
                        <p className="text-xs text-slate-400">This may take a minute for large questionnaires.</p>
                        {error && (
                            <div className="p-3 bg-red-50 text-red-600 text-sm rounded-md border border-red-100 max-w-md mx-auto text-left">
                                <span className="font-semibold">Error: </span>{error}
                                <div className="mt-2">
                                    <Button size="sm" variant="outline" onClick={() => { setStep("upload"); setAnalyzing(false); }}>
                                        ← Back to Upload
                                    </Button>
                                </div>
                            </div>
                        )}
                    </CardContent>
                </SectionCard>
            )}

            {step === "review" && runData && currentOrgId && (
                <div className="space-y-6">
                    <SectionCard>
                        <CardHeader className="bg-green-50/60 border-b border-green-100">
                            <div className="flex items-start justify-between gap-4">
                                <div className="flex items-start gap-3">
                                    <CheckCircle2 className="h-5 w-5 text-green-600 mt-0.5 shrink-0" />
                                    <div>
                                        <CardTitle className="text-green-800">Analysis Complete</CardTitle>
                                        <CardDescription className="text-green-700/80 mt-0.5">
                                            {questions.length} question{questions.length !== 1 ? "s" : ""} answered.
                                            {questions.filter(q => q.confidence === "LOW").length > 0 && (
                                                <span className="text-amber-700 font-medium ml-1">
                                                    ({questions.filter(q => q.confidence === "LOW").length} low confidence — review recommended)
                                                </span>
                                            )}
                                        </CardDescription>
                                    </div>
                                </div>
                                <Button onClick={handleExport} disabled={exporting} className="shrink-0">
                                    {exporting
                                        ? <><Loader2 className="mr-2 h-4 w-4 animate-spin" /> Exporting…</>
                                        : <><Download className="mr-2 h-4 w-4" /> Export Excel</>}
                                </Button>
                            </div>
                        </CardHeader>
                    </SectionCard>

                    {/* Review summary stats */}
                    <div className="grid grid-cols-3 gap-3">
                        <div className="rounded-lg border bg-muted/30 p-3 text-center">
                            <div className="text-xl font-bold text-slate-900">{questions.length}</div>
                            <div className="text-[11px] text-muted-foreground font-medium uppercase tracking-wide">Total Questions</div>
                        </div>
                        <div className="rounded-lg border bg-green-50/60 border-green-100 p-3 text-center text-green-800">
                            <div className="text-xl font-bold">{questions.filter(q => q.confidence === "HIGH").length}</div>
                            <div className="text-[11px] font-medium uppercase tracking-wide">High Confidence</div>
                        </div>
                        <div className="rounded-lg border bg-amber-50/60 border-amber-100 p-3 text-center text-amber-800">
                            <div className="text-xl font-bold">{questions.filter(q => q.confidence === "LOW").length}</div>
                            <div className="text-[11px] font-medium uppercase tracking-wide">Low Confidence</div>
                        </div>
                    </div>

                    {questions.filter(q => q.confidence === "LOW").length > 0 && (
                        <div className="rounded-lg border border-amber-200 bg-amber-50/60 p-3 flex items-start gap-2 text-amber-800 text-sm">
                            <AlertTriangle className="h-4 w-4 mt-0.5 shrink-0" />
                            <p className="text-xs leading-snug">
                                <strong>{questions.filter(q => q.confidence === "LOW").length} answers</strong> have low confidence.
                                Review and edit them in the grid below before exporting.
                            </p>
                        </div>
                    )}

                    <ReviewGrid items={questions} onItemsChange={setQuestions} uploadDocsHref="/projects" />
                </div>
            )}
        </div>
    );
}

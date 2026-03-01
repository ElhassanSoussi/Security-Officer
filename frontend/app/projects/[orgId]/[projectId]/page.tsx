"use client";

import { useParams, useRouter } from "next/navigation";
import { useState, useEffect, useCallback } from "react";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import {
    FileText, PlayCircle, Shield, Upload, Eye, Database, ListChecks,
    Trash2, Loader2, FolderOpen, AlertCircle, CheckCircle,
    Package, Activity, ChevronRight, CircleDot, ArrowRight, Lock
} from "lucide-react";
import { ApiClient } from "@/lib/api";
import { RunWizard } from "@/components/run-wizard";
import Link from "next/link";
import { Badge } from "@/components/ui/badge";
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table";
import { createClient } from "@/utils/supabase/client";
import { useToast } from "@/components/ui/toaster";
import { ProjectDocument, ProjectOverview, OnboardingState } from "@/types";
import PageHeader from "@/components/ui/PageHeader";
import SectionCard from "@/components/ui/SectionCard";

const UUID_RE = /^[0-9a-f]{8}-[0-9a-f]{4}-[1-5][0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$/i;

export default function ProjectDetail() {
    const params = useParams();
    const _router = useRouter();
    const { toast: _toast } = useToast();
    const rawOrgId = String(params.orgId || "");
    const rawProjectId = String(params.projectId || "");
    const [resolvedOrgId, setResolvedOrgId] = useState<string | null>(null);
    const [resolvedProjectId, setResolvedProjectId] = useState<string | undefined>(undefined);
    const [projectName, setProjectName] = useState<string>(rawProjectId);
    const [token, setToken] = useState<string | undefined>(undefined);
    const [resolving, setResolving] = useState(true);
    const [contextWarning, setContextWarning] = useState("");
    const [overview, setOverview] = useState<ProjectOverview | null>(null);
    const [overviewLoading, setOverviewLoading] = useState(false);

    useEffect(() => {
        async function resolveContext() {
            const warnings: string[] = [];
            const supabase = createClient();
            const { data: { session } } = await supabase.auth.getSession();
            const accessToken = session?.access_token;
            setToken(accessToken);

            let nextOrgId: string | null = UUID_RE.test(rawOrgId) ? rawOrgId : null;
            const nextProjectId = UUID_RE.test(rawProjectId) ? rawProjectId : undefined;

            if (!nextOrgId && accessToken) {
                try {
                    const orgs = await ApiClient.getMyOrgs(accessToken);
                    if (orgs && orgs.length > 0) {
                        nextOrgId = orgs[0].id;
                        warnings.push("Legacy org slug detected; switched to your primary organization context.");
                    }
                } catch (e) {
                    console.error("Failed to resolve org context:", e);
                }
            } else if (!nextOrgId) {
                warnings.push("Missing valid organization ID in route.");
            }

            if (!nextProjectId) {
                warnings.push("Legacy project slug detected; running in organization-level mode.");
            }

            setResolvedOrgId(nextOrgId);
            setResolvedProjectId(nextProjectId);
            setContextWarning(warnings.join(" "));

            // Fetch overview if we have a project UUID
            if (nextProjectId && accessToken) {
                setOverviewLoading(true);
                try {
                    const ov = await ApiClient.getProjectOverview(nextProjectId, accessToken);
                    setOverview(ov);
                    if (ov?.project?.name) {
                        setProjectName(ov.project.name);
                    }
                } catch (e) {
                    console.error("Failed to fetch project overview:", e);
                    // Fallback to simple project fetch
                    try {
                        const project = await ApiClient.getProject(nextProjectId, accessToken);
                        if (project?.project_name) {
                            setProjectName(project.project_name);
                        }
                    } catch { /* ignore */ }
                } finally {
                    setOverviewLoading(false);
                }
            }

            setResolving(false);
        }

        resolveContext();
    }, [rawOrgId, rawProjectId]);

    if (resolving) {
        return (
            <div className="flex h-64 items-center justify-center">
                <Loader2 className="h-8 w-8 animate-spin text-slate-400" />
            </div>
        );
    }

    if (!resolvedOrgId) {
        return (
            <div className="p-8">
                <div className="rounded-md border border-red-200 bg-red-50 px-4 py-3 text-sm text-red-700">
                    Could not resolve a valid organization context from this URL.
                </div>
            </div>
        );
    }

    const hasProjectUuid = Boolean(resolvedProjectId);

    return (
        <div className="space-y-8 p-8">
            <div>
                <PageHeader
                    breadcrumbs={
                        <div className="flex items-center gap-2 text-sm text-slate-400">
                            <Link href="/projects" className="hover:underline">Projects</Link>
                            <span>/</span>
                            <span className="text-slate-600 font-medium">{projectName}</span>
                        </div>
                    }
                    title={projectName}
                    subtitle={
                        <>
                            {overview?.org?.name ? `${overview.org.name} · ` : ""}
                            Project Workspace &amp; Knowledge Vault
                        </>
                    }
                    actions={overview?.role && overview.role !== "none" ? <Badge variant="outline" className="text-xs capitalize">{overview.role}</Badge> : undefined}
                />
            </div>
         
            {contextWarning && (
                <div className="rounded-md border border-amber-200 bg-amber-50 px-4 py-3 text-sm text-amber-800">
                    {contextWarning}
                </div>
            )}

            {/* Phase 6: Onboarding Checklist */}
            {overview?.onboarding && !overview.onboarding.all_complete && (
                <SectionCard>
                    <div className="p-6">
                        <OnboardingChecklist
                            onboarding={overview.onboarding}
                            projectId={resolvedProjectId!}
                            token={token}
                        />
                    </div>
                </SectionCard>
            )}

            {/* Phase 6: KPI Dashboard Cards */}
            {overview && !overviewLoading && (
                <div className="grid gap-4 md:grid-cols-4">
                    <KpiCard
                        icon={<FileText className="h-5 w-5 text-blue-600" />}
                        title="Documents"
                        value={overview.docs.total}
                        subtitle={
                            overview.docs.expired_count > 0
                                ? `${overview.docs.expired_count} expired`
                                : overview.docs.expiring_count > 0
                                    ? `${overview.docs.expiring_count} expiring soon`
                                    : "All current"
                        }
                        subtitleClass={overview.docs.expired_count > 0 ? "text-red-500" : overview.docs.expiring_count > 0 ? "text-amber-500" : "text-green-500"}
                    />
                    <KpiCard
                        icon={<PlayCircle className="h-5 w-5 text-indigo-600" />}
                        title="Analysis Runs"
                        value={overview.runs.total}
                        subtitle={
                            overview.runs.last_run_at
                                ? `Last: ${new Date(overview.runs.last_run_at).toLocaleDateString()}`
                                : "No runs yet"
                        }
                    />
                    <KpiCard
                        icon={<Package className="h-5 w-5 text-emerald-600" />}
                        title="Exports"
                        value={overview.runs.last_export_at ? "Ready" : "—"}
                        subtitle={
                            overview.runs.last_export_at
                                ? `Last: ${new Date(overview.runs.last_export_at).toLocaleDateString()}`
                                : "No exports yet"
                        }
                    />
                    <KpiCard
                        icon={<Activity className="h-5 w-5 text-purple-600" />}
                        title="Audit Events"
                        value={overview.audit_preview.length}
                        subtitle={
                            overview.audit_preview.length > 0
                                ? `Latest: ${overview.audit_preview[0].event_type.replace(/_/g, " ")}`
                                : "No activity"
                        }
                    />
                </div>
            )}

            {overviewLoading && (
                <div className="grid gap-4 md:grid-cols-4">
                    {[1, 2, 3, 4].map((i) => (
                        <Card key={i} className="animate-pulse">
                            <CardContent className="pt-6">
                                <div className="h-4 w-24 bg-slate-200 rounded mb-2" />
                                <div className="h-8 w-16 bg-slate-200 rounded mb-1" />
                                <div className="h-3 w-32 bg-slate-100 rounded" />
                            </CardContent>
                        </Card>
                    ))}
                </div>
            )}

            <Tabs defaultValue="knowledge" className="space-y-6">
                <TabsList className="bg-slate-100 p-1">
                    <TabsTrigger value="knowledge" className="px-6 data-[state=active]:bg-white data-[state=active]:shadow-sm">
                        <Database className="mr-2 h-4 w-4" /> Knowledge Vault
                    </TabsTrigger>
                    <TabsTrigger value="questionnaire" className="px-6 data-[state=active]:bg-white data-[state=active]:shadow-sm">
                        <PlayCircle className="mr-2 h-4 w-4" /> Run Questionnaire
                    </TabsTrigger>
                    <TabsTrigger value="runs" className="px-6 data-[state=active]:bg-white data-[state=active]:shadow-sm">
                        <ListChecks className="mr-2 h-4 w-4" /> Runs History
                    </TabsTrigger>
                    <TabsTrigger value="audit" className="px-6 data-[state=active]:bg-white data-[state=active]:shadow-sm">
                        <Shield className="mr-2 h-4 w-4" /> Audit Trail
                    </TabsTrigger>
                    <TabsTrigger value="evidence" className="px-6 data-[state=active]:bg-white data-[state=active]:shadow-sm">
                        <Lock className="mr-2 h-4 w-4" /> Evidence Vault
                    </TabsTrigger>
                </TabsList>

                {/* TAB 1: KNOWLEDGE VAULT */}
                <TabsContent value="knowledge" className="space-y-6">
                    <div className="grid gap-6 md:grid-cols-2">
                        <SectionCard>
                            <CardHeader>
                                <div className="flex justify-between items-center">
                                    <div>
                                        <CardTitle className="flex items-center gap-2">
                                            <Shield className="h-5 w-5 text-blue-600" />
                                            Project Documents
                                        </CardTitle>
                                        <CardDescription>
                                            Upload supporting docs (PDF, DOCX, TXT) to ground AI answers.
                                        </CardDescription>
                                    </div>
                                </div>
                            </CardHeader>
                            <CardContent>
                                {hasProjectUuid ? (
                                    <ProjectDocumentsList
                                        projectId={resolvedProjectId!}
                                        orgId={resolvedOrgId}
                                        token={token}
                                    />
                                ) : (
                                    <EmptyState
                                        icon={<FolderOpen className="h-10 w-10" />}
                                        title="Project UUID Required"
                                        description="A valid project UUID is needed to manage documents."
                                    />
                                )}
                            </CardContent>
                        </SectionCard>
                    
                        <Card className="bg-slate-50/50">
                             <CardHeader>
                                 <CardTitle>Organization Vault</CardTitle>
                                 <CardDescription>Inherited global documents (read-only).</CardDescription>
                             </CardHeader>
                             <CardContent>
                                 <DocList orgId={resolvedOrgId} projectId={null} token={token} />
                             </CardContent>
                         </Card>
                     </div>
                 </TabsContent>

                {/* TAB 2: QUESTIONNAIRE WIZARD */}
                <TabsContent value="questionnaire">
                    <RunWizard orgId={resolvedOrgId} projectId={resolvedProjectId} />
                </TabsContent>

                {/* TAB 3: RUNS HISTORY */}
                <TabsContent value="runs">
                    <Card>
                        <CardHeader>
                            <CardTitle>Run History</CardTitle>
                            <CardDescription>Past analysis and export logs for this project.</CardDescription>
                        </CardHeader>
                        <CardContent>
                            {hasProjectUuid ? (
                                <ProjectRunsList orgId={resolvedOrgId} projectId={resolvedProjectId as string} token={token} />
                            ) : (
                                <EmptyState
                                    icon={<PlayCircle className="h-10 w-10" />}
                                    title="No Project Context"
                                    description="No project UUID available for this route."
                                />
                            )}
                        </CardContent>
                    </Card>
                </TabsContent>

                {/* TAB 4: AUDIT TRAIL (Phase 6) */}
                <TabsContent value="audit">
                    <Card>
                        <CardHeader>
                            <CardTitle>Audit Trail</CardTitle>
                            <CardDescription>Recent audit events for this project&apos;s organization.</CardDescription>
                        </CardHeader>
                        <CardContent>
                            {overview && overview.audit_preview.length > 0 ? (
                                <Table>
                                    <TableHeader>
                                        <TableRow>
                                            <TableHead>Event</TableHead>
                                            <TableHead>Time</TableHead>
                                            <TableHead>User</TableHead>
                                        </TableRow>
                                    </TableHeader>
                                    <TableBody>
                                        {overview.audit_preview.map((ev) => (
                                            <TableRow key={ev.id}>
                                                <TableCell>
                                                    <Badge variant="outline" className="text-xs">
                                                        {ev.event_type.replace(/_/g, " ")}
                                                    </Badge>
                                                </TableCell>
                                                <TableCell className="text-xs text-slate-500">
                                                    {new Date(ev.created_at).toLocaleString()}
                                                </TableCell>
                                                <TableCell className="text-xs text-slate-500 font-mono">
                                                    {ev.user_id?.slice(0, 8) || "—"}
                                                </TableCell>
                                            </TableRow>
                                        ))}
                                    </TableBody>
                                </Table>
                            ) : (
                                <EmptyState
                                    icon={<Shield className="h-10 w-10" />}
                                    title="No Audit Events Yet"
                                    description="Audit events will appear here as your team uploads documents, runs analyses, and reviews answers."
                                    action={{ label: "Run an Analysis", tab: "questionnaire" }}
                                />
                            )}
                        </CardContent>
                    </Card>
                </TabsContent>

                {/* TAB 5: EVIDENCE VAULT (Phase 17) */}
                <TabsContent value="evidence">
                    <Card>
                        <CardHeader>
                            <CardTitle className="flex items-center gap-2">
                                <Lock className="h-5 w-5 text-blue-600" /> Evidence Vault
                            </CardTitle>
                            <CardDescription>
                                Tamper-evident compliance evidence packages generated for runs in this project.
                                Each package is SHA-256 hashed and the run is locked upon generation.
                            </CardDescription>
                        </CardHeader>
                        <CardContent>
                            <Link
                                href={`/projects/${resolvedOrgId}/${resolvedProjectId}/evidence`}
                                className="inline-flex items-center gap-2 rounded-md border bg-background px-4 py-2.5 text-sm font-medium hover:bg-muted transition-colors"
                            >
                                <Lock className="h-4 w-4 text-blue-600" />
                                Open Evidence Vault →
                            </Link>
                        </CardContent>
                    </Card>
                </TabsContent>
            </Tabs>
        </div>
    );
}


// ─── Phase 6: KPI Card ────────────────────────────────────────────────────────
function KpiCard({
    icon,
    title,
    value,
    subtitle,
    subtitleClass,
}: {
    icon: React.ReactNode;
    title: string;
    value: number | string;
    subtitle: string;
    subtitleClass?: string;
}) {
    return (
        <Card className="hover:shadow-md transition-shadow">
            <CardContent className="pt-6">
                <div className="flex items-center gap-2 mb-2">
                    {icon}
                    <span className="text-sm font-medium text-slate-500">{title}</span>
                </div>
                <div className="text-2xl font-bold text-slate-900">{value}</div>
                <p className={`text-xs mt-1 ${subtitleClass || "text-slate-400"}`}>{subtitle}</p>
            </CardContent>
        </Card>
    );
}


// ─── Phase 6: Onboarding Checklist ────────────────────────────────────────────
function OnboardingChecklist({
    onboarding,
    projectId: _projectId,
    token: _token,
}: {
    onboarding: OnboardingState;
    projectId: string;
    token?: string;
}) {
    const stepOrder = ["connect_org", "upload_docs", "run_analysis", "review_answers", "export_pack"];
    const progress = (onboarding.completed_count / onboarding.total_steps) * 100;

    // Map progress to a set of discrete width classes to avoid inline styles
    const pctClass = progress >= 100 ? 'w-full' : progress >= 75 ? 'w-3/4' : progress >= 50 ? 'w-1/2' : progress >= 25 ? 'w-1/4' : 'w-0';

    return (
        <Card className="border-blue-200 bg-gradient-to-r from-blue-50/50 to-indigo-50/30">
            <CardHeader className="pb-3">
                <div className="flex items-center justify-between">
                    <div>
                        <CardTitle className="text-lg flex items-center gap-2">
                            <ListChecks className="h-5 w-5 text-blue-600" />
                            Getting Started
                        </CardTitle>
                        <CardDescription>
                            Complete these steps to set up your compliance project
                        </CardDescription>
                    </div>
                    <Badge variant="outline" className="text-sm">
                        {onboarding.completed_count}/{onboarding.total_steps}
                    </Badge>
                </div>
                {/* Progress bar (uses discrete width classes for lint compatibility) */}
                <div className="w-full bg-blue-100 rounded-full h-2 mt-3">
                    <div className={`bg-blue-600 h-2 rounded-full transition-all duration-500 ${pctClass}`} />
                </div>
            </CardHeader>
            <CardContent>
                <div className="space-y-2">
                    {stepOrder.map((key) => {
                        const step = onboarding.steps[key];
                        if (!step) return null;
                        return (
                            <div
                                key={key}
                                className={`flex items-center gap-3 rounded-lg px-3 py-2 transition-colors ${
                                    step.completed
                                        ? "bg-green-50/50 text-green-700"
                                        : "bg-white text-slate-600 hover:bg-slate-50"
                                }`}
                            >
                                {step.completed ? (
                                    <CheckCircle className="h-5 w-5 text-green-500 shrink-0" />
                                ) : (
                                    <CircleDot className="h-5 w-5 text-slate-300 shrink-0" />
                                )}
                                <span className={`text-sm font-medium flex-1 ${step.completed ? "line-through opacity-60" : ""}`}>
                                    {step.label}
                                </span>
                                {!step.completed && (
                                    <ArrowRight className="h-4 w-4 text-slate-300" />
                                )}
                            </div>
                        );
                    })}
                </div>
            </CardContent>
        </Card>
    );
}


// ─── Phase 6: Reusable Empty State ────────────────────────────────────────────
function EmptyState({
    icon,
    title,
    description,
    action,
}: {
    icon: React.ReactNode;
    title: string;
    description: string;
    action?: { label: string; href?: string; tab?: string; onClick?: () => void };
}) {
    return (
        <div className="text-center py-12 border-2 border-dashed rounded-lg bg-white/50">
            <div className="mx-auto mb-3 opacity-20 text-slate-400">{icon}</div>
            <p className="text-sm font-medium text-slate-500">{title}</p>
            <p className="text-xs text-slate-400 mt-1 max-w-sm mx-auto">{description}</p>
            {action && (
                action.onClick ? (
                    <Button variant="outline" size="sm" className="mt-4" onClick={action.onClick}>
                        {action.label} <ChevronRight className="ml-1 h-3 w-3" />
                    </Button>
                ) : action.href ? (
                    <Link href={action.href}>
                        <Button variant="outline" size="sm" className="mt-4">
                            {action.label} <ChevronRight className="ml-1 h-3 w-3" />
                        </Button>
                    </Link>
                ) : null
            )}
        </div>
    );
}


// ─── Project Documents with Upload + Delete ───────────────────────────────────
function ProjectDocumentsList({ projectId, orgId, token }: { projectId: string; orgId: string; token?: string }) {
    // ...existing code for ProjectDocumentsList...
    const [docs, setDocs] = useState<ProjectDocument[]>([]);
    const [loading, setLoading] = useState(true);
    const [error, setError] = useState("");
    const [uploading, setUploading] = useState(false);
    const [deleting, setDeleting] = useState<string | null>(null);
    const { toast } = useToast();

    const loadDocs = useCallback(async () => {
        try {
            setError("");
            let data: any[];
            try {
                data = await ApiClient.getProjectDocuments(projectId, token);
            } catch {
                data = await ApiClient.getDocuments(orgId, projectId, token);
            }
            setDocs(data || []);
        } catch (err: any) {
            setError(err?.message || "Failed to load documents");
        } finally {
            setLoading(false);
        }
    }, [projectId, orgId, token]);

    useEffect(() => {
        loadDocs();
    }, [loadDocs]);

    const handleUpload = async (e: React.ChangeEvent<HTMLInputElement>) => {
        const file = e.target.files?.[0];
        if (!file) return;

        setUploading(true);
        try {
            await ApiClient.uploadProjectDocument(projectId, file, token);
            toast({ title: "Upload Complete", description: `${file.name} added to Knowledge Vault.`, variant: "success" });
            await loadDocs();
        } catch (err: any) {
            toast({ title: "Upload Failed", description: err?.message || "Upload failed", variant: "destructive" });
        } finally {
            setUploading(false);
            e.target.value = "";
        }
    };

    const handleDelete = async (docId: string, filename: string) => {
        if (!confirm(`Delete "${filename}" from the Knowledge Vault? This cannot be undone.`)) return;
        setDeleting(docId);
        try {
            await ApiClient.deleteProjectDocument(projectId, docId, token);
            toast({ title: "Deleted", description: `${filename} removed.` });
            await loadDocs();
        } catch (err: any) {
            toast({ title: "Delete Failed", description: err?.message || "Delete failed", variant: "destructive" });
        } finally {
            setDeleting(null);
        }
    };

    const formatFileSize = (bytes?: number) => {
        if (!bytes) return "—";
        if (bytes < 1024) return `${bytes} B`;
        if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`;
        return `${(bytes / (1024 * 1024)).toFixed(1)} MB`;
    };

    return (
        <div className="space-y-4">
            {/* Upload Area */}
            <div className="relative">
                <label
                    htmlFor="vault-upload"
                    className={`flex items-center justify-center gap-2 border-2 border-dashed rounded-lg p-4 cursor-pointer transition-colors
                        ${uploading ? "border-blue-300 bg-blue-50/50" : "border-slate-200 hover:border-blue-400 hover:bg-blue-50/30"}`}
                >
                    {uploading ? (
                        <Loader2 className="h-5 w-5 animate-spin text-blue-500" />
                    ) : (
                        <Upload className="h-5 w-5 text-slate-400" />
                    )}
                    <span className="text-sm text-slate-600">
                        {uploading ? "Uploading & processing..." : "Click to upload PDF, DOCX, or TXT"}
                    </span>
                </label>
                <input
                    id="vault-upload"
                    type="file"
                    accept=".pdf,.docx,.txt"
                    className="hidden"
                    onChange={handleUpload}
                    disabled={uploading}
                />
            </div>

            {loading && (
                <div className="text-center py-8 text-slate-400">
                    <Loader2 className="mx-auto h-6 w-6 animate-spin mb-2" />
                    Loading documents...
                </div>
            )}

            {error && (
                <div className="rounded-md border border-red-200 bg-red-50 px-4 py-3 text-sm text-red-700 flex items-center gap-2">
                    <AlertCircle className="h-4 w-4 shrink-0" />
                    <div>
                        <p className="font-medium">Unable to load documents</p>
                        <p className="text-xs mt-0.5">{error}</p>
                    </div>
                </div>
            )}

            {!loading && !error && docs.length === 0 && (
                <EmptyState
                    icon={<FolderOpen className="h-10 w-10" />}
                    title="Knowledge Vault is empty"
                    description="Upload project documents so the AI can ground its answers with citations. Supports PDF, DOCX, and TXT files."
                />
            )}

            {docs.length > 0 && (
                <div className="rounded-md border">
                    <Table>
                        <TableHeader>
                            <TableRow>
                                <TableHead>Document</TableHead>
                                <TableHead>Type</TableHead>
                                <TableHead>Size</TableHead>
                                <TableHead>Uploaded</TableHead>
                                <TableHead className="w-[60px]"></TableHead>
                            </TableRow>
                        </TableHeader>
                        <TableBody>
                            {docs.map((doc) => (
                                <TableRow key={doc.id}>
                                    <TableCell className="font-medium flex items-center gap-2">
                                        <FileText className="h-4 w-4 text-blue-500 shrink-0" />
                                        <span className="truncate max-w-[200px]">{doc.filename}</span>
                                    </TableCell>
                                    <TableCell>
                                        <Badge variant="outline" className="text-xs uppercase">
                                            {doc.file_type || "—"}
                                        </Badge>
                                    </TableCell>
                                    <TableCell className="text-xs text-slate-500">
                                        {formatFileSize(doc.file_size_bytes)}
                                    </TableCell>
                                    <TableCell className="text-xs text-slate-500">
                                        {new Date(doc.created_at).toLocaleDateString()}
                                    </TableCell>
                                    <TableCell>
                                        <Button
                                            variant="ghost"
                                            size="sm"
                                            className="h-7 w-7 p-0 text-slate-400 hover:text-red-600"
                                            onClick={() => handleDelete(doc.id, doc.filename)}
                                            disabled={deleting === doc.id}
                                        >
                                            {deleting === doc.id ? (
                                                <Loader2 className="h-3.5 w-3.5 animate-spin" />
                                            ) : (
                                                <Trash2 className="h-3.5 w-3.5" />
                                            )}
                                        </Button>
                                    </TableCell>
                                </TableRow>
                            ))}
                        </TableBody>
                    </Table>
                </div>
            )}

            {docs.length > 0 && (
                <div className="flex items-center gap-2 text-xs text-slate-400">
                    <CheckCircle className="h-3.5 w-3.5 text-green-500" />
                    {docs.length} document{docs.length !== 1 ? "s" : ""} in vault — AI will use these for grounded answers
                </div>
            )}
        </div>
    );
}

// ─── Legacy Org-level Docs (read-only) ────────────────────────────────────────
function DocList({ orgId, projectId, token }: { orgId: string; projectId: string | null; token?: string }) {
    const [docs, setDocs] = useState<any[]>([]);
    const [loading, setLoading] = useState(true);
    const [error, setError] = useState("");

    useEffect(() => {
        const fetchDocs = async () => {
            try {
                setError("");
                const data = await ApiClient.getDocuments(orgId, projectId, token);
                setDocs(data || []);
            } catch (err: any) {
                console.error("Failed to load docs:", err);
                setError(err?.message || "Failed to load documents");
            } finally {
                setLoading(false);
            }
        };
        fetchDocs();
    }, [orgId, projectId, token]);

    if (loading) return <div className="text-center py-8 text-slate-400"><Loader2 className="mx-auto h-6 w-6 animate-spin mb-2" />Loading documents...</div>;

    if (error) {
        return (
            <div className="rounded-md border border-red-200 bg-red-50 px-4 py-3 text-sm text-red-700 flex items-center gap-2">
                <AlertCircle className="h-4 w-4 shrink-0" />
                <div>
                    <p className="font-medium">Unable to load org documents</p>
                    <p className="text-xs mt-0.5">{error}</p>
                </div>
            </div>
        );
    }

    if (docs.length === 0) {
        return (
            <EmptyState
                icon={<FileText className="h-10 w-10" />}
                title="No organization-level documents"
                description="Organization documents added to the global vault will appear here and be available across all projects."
            />
        );
    }

    return (
        <Table>
            <TableHeader>
                <TableRow>
                    <TableHead>Filename</TableHead>
                    <TableHead>Uploaded</TableHead>
                </TableRow>
            </TableHeader>
            <TableBody>
                {docs.map((doc: any) => (
                    <TableRow key={doc.id}>
                        <TableCell className="font-medium flex items-center gap-2">
                            <FileText className="h-4 w-4 text-slate-400" />
                            {doc.filename}
                        </TableCell>
                        <TableCell className="text-xs text-slate-500">
                            {new Date(doc.created_at).toLocaleDateString()}
                        </TableCell>
                    </TableRow>
                ))}
            </TableBody>
        </Table>
    );
}

// ─── Project Runs History ─────────────────────────────────────────────────────
function ProjectRunsList({ orgId, projectId, token }: { orgId: string; projectId: string; token?: string }) {
    const [runs, setRuns] = useState<any[]>([]);
    const [loading, setLoading] = useState(true);
    const [error, setError] = useState("");

    useEffect(() => {
        setError("");
        ApiClient.getRuns(orgId, projectId, 50, token)
            .then(setRuns)
            .catch((err: any) => {
                console.error("Failed to load runs:", err);
                setError(err?.message || "Failed to load run history");
            })
            .finally(() => setLoading(false));
    }, [orgId, projectId, token]);

    if (loading) return <div className="text-center py-8 text-slate-400"><Loader2 className="mx-auto h-6 w-6 animate-spin mb-2" />Loading runs...</div>;

    if (error) {
        return (
            <div className="rounded-md border border-red-200 bg-red-50 px-4 py-3 text-sm text-red-700 flex items-center gap-2">
                <AlertCircle className="h-4 w-4 shrink-0" />
                <div>
                    <p className="font-medium">Unable to load run history</p>
                    <p className="text-xs mt-0.5">{error}</p>
                </div>
            </div>
        );
    }

    if (runs.length === 0) {
        return (
            <EmptyState
                icon={<PlayCircle className="h-10 w-10" />}
                title="No Analysis Runs Yet"
                description="Run your first questionnaire analysis to see results here. Upload your compliance questionnaire and let the AI answer questions using your knowledge vault."
            />
        );
    }

    const statusColor = (s: string) => {
        switch (s) {
            case "COMPLETED": return "bg-green-50 text-green-700 border-green-200";
            case "PROCESSING": return "bg-blue-50 text-blue-700 border-blue-200";
            case "FAILED": return "bg-red-50 text-red-700 border-red-200";
            default: return "bg-slate-50 text-slate-700 border-slate-200";
        }
    };

    return (
        <Table>
            <TableHeader>
                <TableRow>
                    <TableHead>Run</TableHead>
                    <TableHead>Questionnaire</TableHead>
                    <TableHead>Status</TableHead>
                    <TableHead>Date</TableHead>
                    <TableHead className="text-right">Actions</TableHead>
                </TableRow>
            </TableHeader>
            <TableBody>
                {runs.map(run => (
                    <TableRow key={run.id}>
                        <TableCell className="font-mono text-xs">{run.id.slice(0, 8)}</TableCell>
                        <TableCell className="text-sm truncate max-w-[200px]">
                            {run.questionnaire_filename || "—"}
                        </TableCell>
                        <TableCell>
                            <Badge variant="outline" className={statusColor(run.status)}>
                                {run.status}
                            </Badge>
                        </TableCell>
                        <TableCell className="text-muted-foreground text-sm">
                            {run.created_at ? new Date(run.created_at).toLocaleString() : "—"}
                        </TableCell>
                        <TableCell className="text-right">
                            <Link href={`/runs/${run.id}`}>
                                <Button variant="ghost" size="sm">
                                    <Eye className="h-4 w-4 mr-1" /> Review
                                </Button>
                            </Link>
                        </TableCell>
                    </TableRow>
                ))}
            </TableBody>
        </Table>
    );
}

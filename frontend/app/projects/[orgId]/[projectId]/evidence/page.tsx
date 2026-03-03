"use client";

/**
 * Evidence Vault page
 * Route: /projects/[orgId]/[projectId]/evidence
 *
 * Shows all evidence packages generated for a project.
 * Admin/Owner can delete records.
 */

import { useEffect, useState, useCallback } from "react";
import { useParams } from "next/navigation";
import Link from "next/link";
import { ArrowLeft, Shield, Download, Trash2, Loader2, RefreshCw, Hash, ClipboardCopy, CheckCircle2 } from "lucide-react";
import { createClient } from "@/utils/supabase/client";
import { ApiClient } from "@/lib/api";
import { useRBAC } from "@/hooks/useRBAC";
import { useToast } from "@/components/ui/toaster";
import PageHeader from "@/components/ui/PageHeader";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from "@/components/ui/card";
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table";
import { TableEmptyState } from "@/components/ui/EmptyState";
import {
    Dialog,
    DialogContent,
    DialogDescription,
    DialogFooter,
    DialogHeader,
    DialogTitle,
} from "@/components/ui/dialog";

interface EvidenceRecord {
    id: string;
    run_id: string;
    org_id: string;
    generated_by: string;
    sha256_hash: string;
    health_score: number;
    package_size: number;
    created_at: string;
    questionnaire_filename?: string;
    output_filename?: string;
    run_project_id?: string;
}

function formatBytes(bytes: number): string {
    if (bytes < 1024) return `${bytes} B`;
    if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`;
    return `${(bytes / (1024 * 1024)).toFixed(2)} MB`;
}

function HealthBadge({ score }: { score: number }) {
    if (score >= 80) return <Badge className="bg-green-100 text-green-800 border-green-200">{score}</Badge>;
    if (score >= 60) return <Badge className="bg-amber-100 text-amber-800 border-amber-200">{score}</Badge>;
    return <Badge className="bg-red-100 text-red-800 border-red-200">{score}</Badge>;
}

export default function EvidenceVaultPage() {
    const params = useParams();
    const orgId = params.orgId as string;
    const projectId = params.projectId as string;

    const [records, setRecords] = useState<EvidenceRecord[]>([]);
    const [loading, setLoading] = useState(true);
    const [token, setToken] = useState<string | undefined>(undefined);
    const [deleteTarget, setDeleteTarget] = useState<EvidenceRecord | null>(null);
    const [deleting, setDeleting] = useState(false);
    const [copiedHash, setCopiedHash] = useState<string | null>(null);

    const rbac = useRBAC(orgId);
    const { toast } = useToast();

    const loadRecords = useCallback(async (tok?: string) => {
        setLoading(true);
        try {
            const data = await ApiClient.listOrgEvidenceRecords(orgId, projectId, tok ?? token);
            setRecords(data);
        } catch (e: any) {
            toast({ title: "Failed to load evidence records", description: e?.message, variant: "destructive" });
        } finally {
            setLoading(false);
        }
    }, [orgId, projectId, token, toast]);

    useEffect(() => {
        async function init() {
            const supabase = createClient();
            const { data: { session } } = await supabase.auth.getSession();
            const tok = session?.access_token;
            setToken(tok);
            await loadRecords(tok);
        }
        init();
    }, [orgId, projectId]); // eslint-disable-line react-hooks/exhaustive-deps

    async function handleDelete() {
        if (!deleteTarget) return;
        setDeleting(true);
        try {
            await ApiClient.deleteEvidenceRecord(deleteTarget.id, token);
            toast({ title: "Evidence record deleted", variant: "success" });
            setDeleteTarget(null);
            await loadRecords();
        } catch (e: any) {
            toast({ title: "Delete failed", description: e?.message, variant: "destructive" });
        } finally {
            setDeleting(false);
        }
    }

    async function copyHash(hash: string) {
        try {
            await navigator.clipboard.writeText(hash);
            setCopiedHash(hash);
            setTimeout(() => setCopiedHash(null), 2000);
        } catch {
            // ignore
        }
    }

    const canDelete = rbac.role === "owner" || rbac.role === "admin";

    return (
        <div className="space-y-6">
            <PageHeader
                breadcrumbs={
                    <Link
                        href={`/projects/${orgId}/${projectId}`}
                        className="inline-flex items-center gap-1.5 text-sm text-muted-foreground hover:text-primary transition-colors"
                    >
                        <ArrowLeft className="h-4 w-4" /> Back to Project
                    </Link>
                }
                title={
                    <span className="flex items-center gap-2">
                        <Shield className="h-6 w-6 text-blue-600" />
                        Evidence Vault
                    </span>
                }
                subtitle="Tamper-evident compliance evidence packages. Each record contains a SHA-256 hash of its audit log and export artifacts."
                actions={
                    <Button variant="outline" size="sm" onClick={() => loadRecords()} disabled={loading}>
                        <RefreshCw className={`h-4 w-4 mr-1.5 ${loading ? "animate-spin" : ""}`} />
                        Refresh
                    </Button>
                }
            />

            {/* Summary cards */}
            <div className="grid gap-4 md:grid-cols-3">
                <Card>
                    <CardContent className="pt-6">
                        <div className="text-3xl font-bold">{records.length}</div>
                        <p className="text-sm text-muted-foreground mt-1">Evidence Packages</p>
                    </CardContent>
                </Card>
                <Card>
                    <CardContent className="pt-6">
                        <div className="text-3xl font-bold">
                            {records.length > 0
                                ? Math.round(records.reduce((s, r) => s + r.health_score, 0) / records.length)
                                : "—"}
                        </div>
                        <p className="text-sm text-muted-foreground mt-1">Avg Health Score</p>
                    </CardContent>
                </Card>
                <Card>
                    <CardContent className="pt-6">
                        <div className="text-3xl font-bold">
                            {records.length > 0 ? formatBytes(records.reduce((s, r) => s + (r.package_size || 0), 0)) : "—"}
                        </div>
                        <p className="text-sm text-muted-foreground mt-1">Total Package Size</p>
                    </CardContent>
                </Card>
            </div>

            {/* Records table */}
            <Card>
                <CardHeader>
                    <CardTitle className="flex items-center gap-2 text-base">
                        <Shield className="h-5 w-5 text-blue-600" />
                        Evidence Records
                    </CardTitle>
                    <CardDescription>
                        One row per generated evidence package. Hash is SHA-256 of the full audit log + export artifact bundle.
                    </CardDescription>
                </CardHeader>
                <CardContent>
                    {loading ? (
                        <div className="flex justify-center py-12">
                            <Loader2 className="h-6 w-6 animate-spin text-muted-foreground" />
                        </div>
                    ) : (
                        <div className="rounded-md border overflow-auto">
                            <Table>
                                <TableHeader>
                                    <TableRow>
                                        <TableHead>Run</TableHead>
                                        <TableHead>Generated At</TableHead>
                                        <TableHead className="text-center">Health</TableHead>
                                        <TableHead>Size</TableHead>
                                        <TableHead>SHA-256 Hash</TableHead>
                                        <TableHead className="w-[120px]">Actions</TableHead>
                                    </TableRow>
                                </TableHeader>
                                <TableBody>
                                    {records.length === 0 ? (
                                        <TableEmptyState
                                            cols={6}
                                            icon={<Shield className="h-10 w-10 text-muted-foreground/40" />}
                                            title="No evidence packages yet"
                                            description="Generate evidence packages from individual run detail pages for completed runs."
                                        />
                                    ) : (
                                        records.map((rec) => (
                                            <TableRow key={rec.id}>
                                                <TableCell>
                                                    <Link
                                                        href={`/runs/${rec.run_id}`}
                                                        className="font-medium font-mono text-xs hover:underline text-blue-600"
                                                    >
                                                        {rec.run_id.slice(0, 8)}…
                                                    </Link>
                                                    {rec.questionnaire_filename && (
                                                        <div className="text-xs text-muted-foreground truncate max-w-[160px]" title={rec.questionnaire_filename}>
                                                            {rec.questionnaire_filename}
                                                        </div>
                                                    )}
                                                </TableCell>
                                                <TableCell className="text-sm text-muted-foreground">
                                                    {new Date(rec.created_at).toLocaleString()}
                                                </TableCell>
                                                <TableCell className="text-center">
                                                    <HealthBadge score={rec.health_score} />
                                                </TableCell>
                                                <TableCell className="text-sm text-muted-foreground">
                                                    {formatBytes(rec.package_size || 0)}
                                                </TableCell>
                                                <TableCell>
                                                    <div className="flex items-center gap-1.5">
                                                        <Hash className="h-3 w-3 text-muted-foreground shrink-0" />
                                                        <span className="font-mono text-xs text-muted-foreground truncate max-w-[120px]" title={rec.sha256_hash}>
                                                            {rec.sha256_hash.slice(0, 16)}…
                                                        </span>
                                                        <button
                                                            onClick={() => copyHash(rec.sha256_hash)}
                                                            className="shrink-0 p-1 rounded hover:bg-muted transition-colors"
                                                            title="Copy full hash"
                                                        >
                                                            {copiedHash === rec.sha256_hash
                                                                ? <CheckCircle2 className="h-3 w-3 text-green-600" />
                                                                : <ClipboardCopy className="h-3 w-3 text-muted-foreground" />
                                                            }
                                                        </button>
                                                    </div>
                                                </TableCell>
                                                <TableCell>
                                                    <div className="flex items-center gap-1">
                                                        <Link href={`/runs/${rec.run_id}`}>
                                                            <Button variant="ghost" size="sm" className="h-7 px-2 text-xs gap-1">
                                                                <Download className="h-3 w-3" /> View Run
                                                            </Button>
                                                        </Link>
                                                        {canDelete && (
                                                            <Button
                                                                variant="ghost"
                                                                size="sm"
                                                                className="h-7 px-2 text-xs text-destructive hover:text-destructive hover:bg-destructive/10"
                                                                onClick={() => setDeleteTarget(rec)}
                                                            >
                                                                <Trash2 className="h-3 w-3" />
                                                            </Button>
                                                        )}
                                                    </div>
                                                </TableCell>
                                            </TableRow>
                                        ))
                                    )}
                                </TableBody>
                            </Table>
                        </div>
                    )}
                </CardContent>
            </Card>

            {/* Delete Confirmation Dialog */}
            <Dialog open={!!deleteTarget} onOpenChange={(open) => { if (!open) setDeleteTarget(null); }}>
                <DialogContent>
                    <DialogHeader>
                        <DialogTitle className="flex items-center gap-2 text-destructive">
                            <Trash2 className="h-5 w-5" /> Delete Evidence Record
                        </DialogTitle>
                        <DialogDescription>
                            This will permanently delete the evidence record for run{" "}
                            <span className="font-mono font-semibold">{deleteTarget?.run_id.slice(0, 8)}</span>.
                            The original ZIP artifact is not stored server-side, so only the metadata record is removed.
                            This action cannot be undone.
                        </DialogDescription>
                    </DialogHeader>
                    {deleteTarget && (
                        <div className="rounded-lg border bg-muted/30 p-3 text-xs space-y-1 font-mono">
                            <div><span className="text-muted-foreground">Run ID:</span> {deleteTarget.run_id}</div>
                            <div><span className="text-muted-foreground">Hash:</span> {deleteTarget.sha256_hash.slice(0, 32)}…</div>
                            <div><span className="text-muted-foreground">Generated:</span> {new Date(deleteTarget.created_at).toLocaleString()}</div>
                        </div>
                    )}
                    <DialogFooter>
                        <Button variant="outline" onClick={() => setDeleteTarget(null)} disabled={deleting}>
                            Cancel
                        </Button>
                        <Button variant="destructive" onClick={handleDelete} disabled={deleting}>
                            {deleting ? <Loader2 className="h-4 w-4 animate-spin mr-2" /> : <Trash2 className="h-4 w-4 mr-2" />}
                            Delete Record
                        </Button>
                    </DialogFooter>
                </DialogContent>
            </Dialog>
        </div>
    );
}

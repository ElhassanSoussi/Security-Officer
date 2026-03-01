"use client";

import { useEffect, useState } from "react";
import { ApiClient, Run } from "@/lib/api";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Eye, Download, PlayCircle } from "lucide-react";
import Link from "next/link";
import { createClient } from "@/utils/supabase/client";
import { useRouter } from "next/navigation";
import PageHeader from "@/components/ui/PageHeader";
import { EmptyState } from "@/components/ui/EmptyState";

export default function RunsPage() {
    const [runs, setRuns] = useState<Run[]>([]);
    const [loading, setLoading] = useState(true);
    const [error, setError] = useState("");
    const [token, setToken] = useState<string | undefined>(undefined);
    const router = useRouter();

    useEffect(() => {
        async function loadRuns() {
            try {
                setError("");
                const supabase = createClient();
                const { data: { session } } = await supabase.auth.getSession();
                const accessToken = session?.access_token;
                setToken(accessToken);

                if (!accessToken) {
                    router.push("/login");
                    return;
                }

                const orgs = await ApiClient.getMyOrgs(accessToken);
                if (!orgs || orgs.length === 0) {
                    setRuns([]);
                    setError("No organization found. Create one first.");
                    return;
                }

                const orgId = orgs[0].id;
                const data = await ApiClient.getRuns(orgId, undefined, 50, accessToken);
                setRuns(data);
            } catch (err: any) {
                console.error("Failed to load runs", err);
                if (String(err?.message || "").toLowerCase().includes("unauthorized")) {
                    router.push("/login");
                    return;
                }
                const requestId = err?.requestId ? ` (Request ${err.requestId})` : "";
                const msg = String(err?.message || "Unknown error").replace(/^API Error:\s*/i, "");
                setError(`Failed to load runs${requestId}: ${msg}`);
            } finally {
                setLoading(false);
            }
        }
        loadRuns();
    }, [router]);

    const getStatusColor = (status: string) => {
        switch (status) {
            case "COMPLETED":
            case "EXPORTED":
            case "ANALYZED":
                return "default";
            case "QUEUED": return "outline";
            case "PROCESSING": return "secondary";
            case "FAILED": return "destructive";
            default: return "secondary";
        }
    };

    return (
        <div className="space-y-6">
            <PageHeader
                title="Runs History"
                subtitle="Track all questionnaire processing activity across your organization."
                actions={
                    <Link href="/run">
                        <Button><PlayCircle className="mr-2 h-4 w-4" /> Run Analysis</Button>
                    </Link>
                }
            />

            <Card>
                <CardHeader>
                    <CardTitle>All Runs</CardTitle>
                </CardHeader>
                <CardContent>
                    {error && (
                        <div className="mb-4 rounded-md border border-red-200 bg-red-50 px-4 py-3 text-sm text-red-700">
                            {error}
                        </div>
                    )}
                    {loading ? (
                        <div className="space-y-3">
                            {[1, 2, 3, 4].map((i) => (
                                <div key={i} className="flex items-center gap-4 animate-pulse">
                                    <div className="h-4 w-20 bg-muted rounded" />
                                    <div className="h-4 w-28 bg-muted rounded" />
                                    <div className="h-5 w-16 bg-muted rounded-full" />
                                    <div className="h-4 w-32 bg-muted/60 rounded flex-1" />
                                    <div className="h-4 w-24 bg-muted/60 rounded" />
                                    <div className="h-8 w-20 bg-muted rounded" />
                                </div>
                            ))}
                        </div>
                    ) : runs.length === 0 ? (
                        <div className="space-y-4">
                            <EmptyState
                                title="No runs yet"
                                description="Questionnaire runs appear here after you upload and process an Excel file."
                                icon={<PlayCircle className="h-10 w-10" />}
                                action={
                                    <Link href="/run">
                                        <Button><PlayCircle className="mr-2 h-4 w-4" /> Run Your First Analysis</Button>
                                    </Link>
                                }
                            />
                            <div className="max-w-md mx-auto rounded-lg border bg-muted/30 p-4 space-y-2">
                                <h4 className="text-xs font-semibold text-foreground uppercase tracking-wider">What happens in a run?</h4>
                                <ul className="space-y-1.5 text-xs text-muted-foreground">
                                    <li>• Your Excel questionnaire is parsed (including merged cells &amp; multi-sheet layouts)</li>
                                    <li>• AI generates answers using your uploaded source documents</li>
                                    <li>• Each answer gets a confidence score and source citation</li>
                                    <li>• Review, approve, and export the submission-ready file</li>
                                </ul>
                            </div>
                        </div>
                    ) : (
                        <div className="max-h-[70vh] overflow-auto rounded-md border">
                        <Table>
                            <TableHeader>
                                <TableRow>
                                    <TableHead>Run ID</TableHead>
                                    <TableHead>Project</TableHead>
                                    <TableHead>Status</TableHead>
                                    <TableHead>Input File</TableHead>
                                    <TableHead>Created</TableHead>
                                    <TableHead className="text-right">Actions</TableHead>
                                </TableRow>
                            </TableHeader>
                            <TableBody>
                                {runs.map((run) => (
                                    <TableRow key={run.id}>
                                        <TableCell className="font-mono text-xs text-muted-foreground">
                                            {run.id.slice(0, 8)}...
                                        </TableCell>
                                        <TableCell>
                                            {run.project_id || "Unassigned"}
                                        </TableCell>
                                        <TableCell>
                                            <Badge variant={getStatusColor(run.status) as any}>
                                                {run.status}
                                            </Badge>
                                        </TableCell>
                                        <TableCell className="max-w-[200px] truncate" title={run.input_filename || "N/A"}>
                                            {run.input_filename || "—"}
                                        </TableCell>
                                        <TableCell className="text-muted-foreground">
                                            {run.created_at ? new Date(run.created_at).toLocaleString() : "—"}
                                        </TableCell>
                                        <TableCell className="text-right">
                                            <div className="flex justify-end gap-2">
                                                <Link href={`/runs/${run.id}`}>
                                                    <Button variant="ghost" size="sm">
                                                        <Eye className="h-4 w-4 mr-2" />
                                                        Details
                                                    </Button>
                                                </Link>
                                                {["COMPLETED", "EXPORTED", "ANALYZED"].includes(run.status) && (
                                                    <Button
                                                        variant="outline"
                                                        size="sm"
                                                        onClick={async () => {
                                                            try {
                                                                await ApiClient.downloadRun(run.id, run.output_filename || `run_${run.id}.xlsx`, token);
                                                            } catch (err: any) {
                                                                const msg = err?.message || "Download failed";
                                                                setError(msg);
                                                            }
                                                        }}
                                                    >
                                                        <Download className="h-4 w-4" />
                                                    </Button>
                                                )}
                                            </div>
                                        </TableCell>
                                    </TableRow>
                                ))}
                            </TableBody>
                        </Table>
                        </div>
                    )}
                </CardContent>
            </Card>
        </div>
    );
}

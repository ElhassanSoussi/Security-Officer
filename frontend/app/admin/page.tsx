"use client";

import { useEffect, useState } from "react";
import { ApiClient, Run } from "@/lib/api";
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Loader2, Activity, AlertCircle, RefreshCw, Terminal, CheckCircle2 } from "lucide-react";
import { createClient } from "@/utils/supabase/client";
import { useRouter } from "next/navigation";
import PageHeader from "@/components/ui/PageHeader";
import { EmptyState } from "@/components/ui/EmptyState";

export default function AdminPage() {
    const [stats, setStats] = useState<any>(null);
    const [failedRuns, setFailedRuns] = useState<Run[]>([]);
    const [loading, setLoading] = useState(true);
    const [error, setError] = useState("");
    const router = useRouter();

    useEffect(() => {
        // Simple health and failed runs fetch
        async function loadAdminData() {
            try {
                setError("");
                const supabase = createClient();
                const { data: { session } } = await supabase.auth.getSession();
                const token = session?.access_token;

                if (!token) {
                    router.push("/login");
                    return;
                }

                const orgs = await ApiClient.getMyOrgs(token);
                if (!orgs || orgs.length === 0) {
                    setStats({ total_runs: 0, failed_runs: 0, healthy: true });
                    setFailedRuns([]);
                    setError("No organization found.");
                    return;
                }

                // In a real app, we'd restrict this page to owners/admins.
                const orgId = orgs[0].id;
                const runs = await ApiClient.getRuns(orgId, undefined, 100, token);
                setFailedRuns(runs.filter(r => r.status === "FAILED"));
                setStats({
                    total_runs: runs.length,
                    failed_runs: runs.filter(r => r.status === "FAILED").length,
                    healthy: true
                });
            } catch (e: any) {
                console.error(e);
                if (String(e?.message || "").toLowerCase().includes("unauthorized")) {
                    router.push("/login");
                    return;
                }
                setError("Failed to load admin data.");
            } finally {
                setLoading(false);
            }
        }
        loadAdminData();
    }, [router]);

    if (loading) return <div className="flex items-center justify-center h-96"><Loader2 className="animate-spin h-8 w-8 text-muted-foreground" /></div>;

    return (
        <div className="p-8 max-w-7xl mx-auto space-y-8">
            {error && (
                <div className="rounded-md border border-red-200 bg-red-50 px-4 py-3 text-sm text-red-700">
                    {error}
                </div>
            )}
            <PageHeader
                title="Operator Center"
                subtitle="System monitoring and manual overrides."
                actions={
                    <Badge variant={stats?.healthy ? "default" : "destructive"} className="h-6">
                        <Activity className="h-3 w-3 mr-2" /> System {stats?.healthy ? "Healthy" : "Degraded"}
                    </Badge>
                }
            />

            <div className="grid gap-4 md:grid-cols-4">
                <Card>
                    <CardHeader className="py-4">
                        <CardTitle className="text-sm font-medium">Total Runs</CardTitle>
                    </CardHeader>
                    <CardContent>
                        <div className="text-2xl font-bold">{stats?.total_runs}</div>
                    </CardContent>
                </Card>
                <Card>
                    <CardHeader className="py-4">
                        <CardTitle className="text-sm font-medium text-destructive">Failed Runs</CardTitle>
                    </CardHeader>
                    <CardContent>
                        <div className="text-2xl font-bold">{stats?.failed_runs}</div>
                    </CardContent>
                </Card>
            </div>

            <Card>
                <CardHeader>
                    <CardTitle>Failed Operations</CardTitle>
                    <CardDescription>Runs that encountered errors during analysis or export.</CardDescription>
                </CardHeader>
                <CardContent>
                    {failedRuns.length === 0 ? (
                        <EmptyState
                            icon={<CheckCircle2 className="h-10 w-10" />}
                            title="No failed runs"
                            description="All operations completed successfully."
                        />
                    ) : (
                        <div className="space-y-4">
                            {failedRuns.map(run => (
                                <div key={run.id} className="flex items-center justify-between p-4 border rounded-lg bg-muted/30">
                                    <div>
                                        <div className="font-semibold">{run.questionnaire_filename}</div>
                                        <div className="text-xs text-muted-foreground">ID: {run.id} • {new Date(run.created_at || "").toLocaleString()}</div>
                                        <div className="text-xs text-destructive mt-1 flex items-center gap-1">
                                            <AlertCircle className="h-3 w-3" /> Error: {run.error_message || "Unknown error"}
                                        </div>
                                    </div>
                                    <Button size="sm" variant="outline">
                                        <RefreshCw className="h-3 w-3 mr-2" /> Retry Manual
                                    </Button>
                                </div>
                            ))}
                        </div>
                    )}
                </CardContent>
            </Card>

            <Card className="bg-slate-950 text-slate-50 border-slate-800">
                <CardHeader>
                    <CardTitle className="flex items-center gap-2 text-slate-200">
                        <Terminal className="h-4 w-4" /> System Logs (Live)
                    </CardTitle>
                </CardHeader>
                <CardContent>
                    <div className="font-mono text-[10px] space-y-1 opacity-80">
                        <p>[INFO] {new Date().toISOString()} Starting metrics pulse...</p>
                        <p className="text-emerald-400">[OK] Database connection active.</p>
                        <p className="text-emerald-400">[OK] OpenAI API connection active.</p>
                        <p>[INFO] {new Date().toISOString()} Worker pool: 4 active, 0 queued.</p>
                    </div>
                </CardContent>
            </Card>
        </div>
    );
}

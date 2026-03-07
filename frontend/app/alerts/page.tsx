"use client";

/*
 * Document Expiry & Re-run Alerts — /alerts
 *
 * Shows:
 *   - Expired documents (need immediate attention)
 *   - Expiring documents (approaching deadline)
 *   - Re-run candidates (stale analysis)
 *   - Trigger email notification button
 */

import { useEffect, useState, useCallback } from "react";
import Link from "next/link";
import {
    AlertTriangle,
    Clock,
    FileWarning,
    RefreshCw,
    Bell,
    CheckCircle2,
    FileText,
    ArrowRight,
    ShieldAlert,
    RotateCcw,
    Loader2,
} from "lucide-react";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from "@/components/ui/card";
import { ApiClient } from "@/lib/api";
import { createClient } from "@/utils/supabase/client";

// ─── Types ─────────────────────────────────────────────────────────────────

interface ExpiryDoc {
    id: string;
    filename: string;
    project_id: string;
    project_name: string;
    expiration_date: string;
    status: string;
    days_remaining: number | null;
}

interface RerunDoc {
    id: string;
    filename: string;
    project_id: string;
    project_name: string;
    last_run_at: string | null;
    days_since_run: number | null;
}

interface AlertSummary {
    expiring_count: number;
    expired_count: number;
    rerun_needed_count: number;
    total_alerts: number;
    expiring_docs: ExpiryDoc[];
    expired_docs: ExpiryDoc[];
    rerun_docs: RerunDoc[];
}

// ─── Helpers ────────────────────────────────────────────────────────────────

function StatusBadge({ status, days }: { status: string; days: number | null }) {
    if (status === "expired") {
        return (
            <Badge variant="outline" className="gap-1 bg-red-100 text-red-700 border-red-200">
                <AlertTriangle className="h-3 w-3" />
                Expired
            </Badge>
        );
    }
    return (
        <Badge variant="outline" className="gap-1 bg-amber-100 text-amber-700 border-amber-200">
            <Clock className="h-3 w-3" />
            {days !== null ? `${days}d left` : "Expiring"}
        </Badge>
    );
}

function AlertStatCard({
    label,
    count,
    icon,
    color,
}: {
    label: string;
    count: number;
    icon: React.ReactNode;
    color: string;
}) {
    return (
        <Card>
            <CardContent className="pt-5 pb-4">
                <div className="flex items-center gap-3">
                    <div className={`rounded-lg p-2 ${color}`}>{icon}</div>
                    <div>
                        <p className="text-2xl font-bold tabular-nums">{count}</p>
                        <p className="text-xs text-muted-foreground">{label}</p>
                    </div>
                </div>
            </CardContent>
        </Card>
    );
}

// ─── Page ────────────────────────────────────────────────────────────────────

export default function AlertsPage() {
    const [loading, setLoading] = useState(true);
    const [notifying, setNotifying] = useState(false);
    const [notifyResult, setNotifyResult] = useState<string | null>(null);
    const [data, setData] = useState<AlertSummary | null>(null);
    const [orgId, setOrgId] = useState<string | null>(null);

    const load = useCallback(async () => {
        setLoading(true);
        try {
            const supabase = createClient();
            const { data: { session } } = await supabase.auth.getSession();
            const tok = session?.access_token;
            const org = await ApiClient.getCurrentOrg(tok);
            const oid = org?.id;
            setOrgId(oid);
            if (oid) {
                const alerts = await ApiClient.getDocumentExpiryAlerts(oid, 30, tok);
                setData(alerts);
            }
        } catch {
            // non-fatal
        } finally {
            setLoading(false);
        }
    }, []);

    useEffect(() => {
        load();
    // eslint-disable-next-line react-hooks/exhaustive-deps
    }, []);

    const handleNotify = async () => {
        if (!orgId) return;
        setNotifying(true);
        setNotifyResult(null);
        try {
            const supabase = createClient();
            const { data: { session } } = await supabase.auth.getSession();
            const tok = session?.access_token;
            const result = await ApiClient.checkAndNotifyExpiry(orgId, tok);
            setNotifyResult(
                result.notifications_sent
                    ? `Email sent! ${result.alerts_found} alert(s) found.`
                    : result.alerts_found > 0
                    ? `${result.alerts_found} alert(s) found. Email not sent (email not configured).`
                    : "No alerts found — all documents are up to date!"
            );
        } catch {
            setNotifyResult("Failed to send notifications.");
        } finally {
            setNotifying(false);
        }
    };

    const totalAlerts = data?.total_alerts ?? 0;

    return (
        <div className="max-w-4xl mx-auto space-y-6 p-6">
            {/* Header */}
            <div className="flex items-center justify-between">
                <div>
                    <h1 className="text-2xl font-bold flex items-center gap-2">
                        <ShieldAlert className="h-6 w-6 text-amber-500" />
                        Document Alerts
                    </h1>
                    <p className="text-sm text-muted-foreground mt-1">
                        Monitor document expirations and compliance re-run requirements.
                    </p>
                </div>
                <div className="flex gap-2">
                    <Button variant="outline" size="sm" onClick={load} disabled={loading} className="gap-1.5">
                        <RefreshCw className={`h-3.5 w-3.5 ${loading ? "animate-spin" : ""}`} />
                        Refresh
                    </Button>
                    <Button size="sm" onClick={handleNotify} disabled={notifying || !orgId} className="gap-1.5">
                        {notifying ? (
                            <>
                                <Loader2 className="h-3.5 w-3.5 animate-spin" />
                                Sending…
                            </>
                        ) : (
                            <>
                                <Bell className="h-3.5 w-3.5" />
                                Send Alert Emails
                            </>
                        )}
                    </Button>
                </div>
            </div>

            {/* Notification result */}
            {notifyResult && (
                <div className="flex items-center gap-2 rounded-lg border border-blue-200 bg-blue-50 px-4 py-3 text-sm text-blue-800">
                    <CheckCircle2 className="h-4 w-4 shrink-0" />
                    {notifyResult}
                    <Button variant="ghost" size="sm" className="ml-auto text-xs" onClick={() => setNotifyResult(null)}>✕</Button>
                </div>
            )}

            {/* Loading state */}
            {loading && (
                <div className="space-y-4 animate-pulse">
                    <div className="grid grid-cols-3 gap-4">
                        {[0, 1, 2].map((i) => <div key={i} className="h-24 rounded-xl bg-muted" />)}
                    </div>
                    <div className="h-40 rounded-xl bg-muted" />
                </div>
            )}

            {/* Summary Cards */}
            {!loading && data && (
                <>
                    <div className="grid grid-cols-1 sm:grid-cols-3 gap-4">
                        <AlertStatCard
                            label="Expired Documents"
                            count={data.expired_count}
                            icon={<AlertTriangle className="h-5 w-5 text-red-600" />}
                            color="bg-red-50"
                        />
                        <AlertStatCard
                            label="Expiring Soon"
                            count={data.expiring_count}
                            icon={<Clock className="h-5 w-5 text-amber-600" />}
                            color="bg-amber-50"
                        />
                        <AlertStatCard
                            label="Re-run Needed"
                            count={data.rerun_needed_count}
                            icon={<RotateCcw className="h-5 w-5 text-blue-600" />}
                            color="bg-blue-50"
                        />
                    </div>

                    {/* All clear */}
                    {totalAlerts === 0 && (
                        <Card>
                            <CardContent className="flex flex-col items-center justify-center py-16 text-center">
                                <CheckCircle2 className="h-12 w-12 text-emerald-400 mb-4" />
                                <p className="text-lg font-medium text-foreground">All Clear</p>
                                <p className="text-sm text-muted-foreground mt-1">
                                    No document expirations or stale analysis runs detected.
                                </p>
                            </CardContent>
                        </Card>
                    )}

                    {/* Expired Documents */}
                    {data.expired_docs.length > 0 && (
                        <Card>
                            <CardHeader>
                                <CardTitle className="text-base flex items-center gap-2 text-red-700">
                                    <AlertTriangle className="h-4 w-4" />
                                    Expired Documents
                                </CardTitle>
                                <CardDescription>
                                    These documents have passed their expiration date and require immediate attention.
                                </CardDescription>
                            </CardHeader>
                            <CardContent>
                                <div className="space-y-3">
                                    {data.expired_docs.map((doc) => (
                                        <div key={doc.id} className="flex items-center gap-3 rounded-lg border border-red-100 bg-red-50/50 px-4 py-3">
                                            <FileWarning className="h-5 w-5 text-red-500 shrink-0" />
                                            <div className="flex-1 min-w-0">
                                                <p className="text-sm font-medium truncate">{doc.filename}</p>
                                                <p className="text-xs text-muted-foreground">
                                                    {doc.project_name} · Expired {doc.expiration_date}
                                                </p>
                                            </div>
                                            <StatusBadge status={doc.status} days={doc.days_remaining} />
                                            <Link href={`/projects/${doc.project_id}`}>
                                                <Button variant="ghost" size="sm" className="gap-1 text-xs">
                                                    View <ArrowRight className="h-3 w-3" />
                                                </Button>
                                            </Link>
                                        </div>
                                    ))}
                                </div>
                            </CardContent>
                        </Card>
                    )}

                    {/* Expiring Soon */}
                    {data.expiring_docs.length > 0 && (
                        <Card>
                            <CardHeader>
                                <CardTitle className="text-base flex items-center gap-2 text-amber-700">
                                    <Clock className="h-4 w-4" />
                                    Expiring Soon
                                </CardTitle>
                                <CardDescription>
                                    These documents will expire within the next 30 days.
                                </CardDescription>
                            </CardHeader>
                            <CardContent>
                                <div className="space-y-3">
                                    {data.expiring_docs.map((doc) => (
                                        <div key={doc.id} className="flex items-center gap-3 rounded-lg border border-amber-100 bg-amber-50/50 px-4 py-3">
                                            <FileText className="h-5 w-5 text-amber-500 shrink-0" />
                                            <div className="flex-1 min-w-0">
                                                <p className="text-sm font-medium truncate">{doc.filename}</p>
                                                <p className="text-xs text-muted-foreground">
                                                    {doc.project_name} · Expires {doc.expiration_date}
                                                </p>
                                            </div>
                                            <StatusBadge status={doc.status} days={doc.days_remaining} />
                                            <Link href={`/projects/${doc.project_id}`}>
                                                <Button variant="ghost" size="sm" className="gap-1 text-xs">
                                                    View <ArrowRight className="h-3 w-3" />
                                                </Button>
                                            </Link>
                                        </div>
                                    ))}
                                </div>
                            </CardContent>
                        </Card>
                    )}

                    {/* Re-run Candidates */}
                    {data.rerun_docs.length > 0 && (
                        <Card>
                            <CardHeader>
                                <CardTitle className="text-base flex items-center gap-2 text-blue-700">
                                    <RotateCcw className="h-4 w-4" />
                                    Re-run Recommended
                                </CardTitle>
                                <CardDescription>
                                    These documents haven&apos;t been analyzed in over 90 days and may benefit from a fresh compliance run.
                                </CardDescription>
                            </CardHeader>
                            <CardContent>
                                <div className="space-y-3">
                                    {data.rerun_docs.map((doc) => (
                                        <div key={doc.id} className="flex items-center gap-3 rounded-lg border px-4 py-3">
                                            <RotateCcw className="h-5 w-5 text-blue-500 shrink-0" />
                                            <div className="flex-1 min-w-0">
                                                <p className="text-sm font-medium truncate">{doc.filename}</p>
                                                <p className="text-xs text-muted-foreground">
                                                    {doc.project_name}
                                                    {doc.days_since_run !== null
                                                        ? ` · Last run ${doc.days_since_run} days ago`
                                                        : " · Never analyzed"}
                                                </p>
                                            </div>
                                            <Badge variant="outline" className="gap-1 bg-blue-100 text-blue-700 border-blue-200">
                                                <RotateCcw className="h-3 w-3" />
                                                Stale
                                            </Badge>
                                            <Link href={`/projects/${doc.project_id}`}>
                                                <Button variant="ghost" size="sm" className="gap-1 text-xs">
                                                    Re-run <ArrowRight className="h-3 w-3" />
                                                </Button>
                                            </Link>
                                        </div>
                                    ))}
                                </div>
                            </CardContent>
                        </Card>
                    )}
                </>
            )}
        </div>
    );
}

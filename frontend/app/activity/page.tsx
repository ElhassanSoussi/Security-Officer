"use client";

import { useEffect, useState, useCallback, useRef } from "react";
import { ApiClient } from "@/lib/api";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table";
import { useToast } from "@/components/ui/toaster";
import { createClient } from "@/utils/supabase/client";
import { getStoredOrgId } from "@/lib/orgContext";
import {
    ChevronLeft, ChevronRight, Download, Filter,
    RefreshCw, ChevronDown, ChevronUp, ClipboardList,
} from "lucide-react";
import PageHeader from "@/components/ui/PageHeader";

// ── Types ──────────────────────────────────────────────────────────────────────

interface AuditEvent {
    id: string;
    timestamp: string;
    user_id: string;
    user_email: string | null;
    action_type: string;
    entity_type: string;
    entity_id: string;
    metadata: Record<string, unknown>;
}

// ── Constants ──────────────────────────────────────────────────────────────────

const ACTION_LABELS: Record<string, string> = {
    document_uploaded:       "Document Uploaded",
    document_deleted:        "Document Deleted",
    project_created:         "Project Created",
    run_created:             "Run Created",
    run_completed:           "Run Completed",
    run_failed:              "Run Failed",
    memory_edited:           "Memory Edited",
    memory_deleted:          "Memory Deleted",
    memory_promoted:         "Memory Promoted",
    compliance_pack_created: "Compliance Pack Created",
    export_generated:        "Export Generated",
    plan_changed:            "Plan Changed",
    assistant_interaction:   "AI Assistant",
};

const ACTION_COLORS: Record<string, string> = {
    document_uploaded:       "bg-blue-50 text-blue-700",
    document_deleted:        "bg-red-50 text-red-700",
    project_created:         "bg-green-50 text-green-700",
    run_created:             "bg-indigo-50 text-indigo-700",
    run_completed:           "bg-green-50 text-green-700",
    run_failed:              "bg-red-50 text-red-700",
    memory_edited:           "bg-amber-50 text-amber-700",
    memory_deleted:          "bg-red-50 text-red-700",
    memory_promoted:         "bg-purple-50 text-purple-700",
    compliance_pack_created: "bg-teal-50 text-teal-700",
    export_generated:        "bg-sky-50 text-sky-700",
    plan_changed:            "bg-orange-50 text-orange-700",
    assistant_interaction:   "bg-slate-100 text-slate-600",
};

// ── Sub-components ─────────────────────────────────────────────────────────────

function formatTs(ts: string) {
    try {
        return new Date(ts).toLocaleString(undefined, {
            dateStyle: "medium",
            timeStyle: "short",
        });
    } catch {
        return ts;
    }
}

function ActionBadge({ action }: { action: string }) {
    const label = ACTION_LABELS[action] ?? action.replace(/_/g, " ");
    const cls = ACTION_COLORS[action] ?? "bg-slate-100 text-slate-600";
    return (
        <Badge className={`text-xs font-medium px-2 py-0.5 rounded-full border-0 ${cls}`}>
            {label}
        </Badge>
    );
}

function SkeletonRows({ cols }: { cols: number }) {
    return (
        <>
            {[1, 2, 3, 4, 5].map((i) => (
                <TableRow key={i}>
                    {Array.from({ length: cols }).map((_, j) => (
                        <TableCell key={j}>
                            <div className="h-4 bg-muted rounded animate-pulse" />
                        </TableCell>
                    ))}
                </TableRow>
            ))}
        </>
    );
}

function MetaViewer({ meta }: { meta: Record<string, unknown> }) {
    const [open, setOpen] = useState(false);
    const keys = Object.keys(meta);
    if (keys.length === 0) return <span className="text-xs text-muted-foreground">—</span>;
    const preview = keys.slice(0, 2).map((k) => `${k}: ${JSON.stringify(meta[k])}`).join(", ");

    return (
        <div className="text-xs">
            <button
                onClick={() => setOpen((v) => !v)}
                className="flex items-center gap-1 text-slate-500 hover:text-slate-800 transition-colors"
            >
                <span className="truncate max-w-[200px]">{open ? "Hide details" : preview}</span>
                {open ? <ChevronUp className="h-3 w-3 shrink-0" /> : <ChevronDown className="h-3 w-3 shrink-0" />}
            </button>
            {open && (
                <pre className="mt-1.5 rounded bg-slate-50 border border-slate-200 p-2 text-[11px] leading-relaxed overflow-auto max-h-48 max-w-xs text-slate-700">
                    {JSON.stringify(meta, null, 2)}
                </pre>
            )}
        </div>
    );
}

// ── Page ───────────────────────────────────────────────────────────────────────

const PAGE_SIZE = 25;

export default function ActivityPage() {
    const [events, setEvents]   = useState<AuditEvent[]>([]);
    const [total, setTotal]     = useState(0);
    const [page, setPage]       = useState(1);
    const [loading, setLoading] = useState(true);
    const [exporting, setExporting] = useState(false);

    // Committed filter state (triggers fetch)
    const [filterUser, setFilterUser]       = useState("");
    const [filterAction, setFilterAction]   = useState("");
    const [filterProject, setFilterProject] = useState("");
    const [filterFrom, setFilterFrom]       = useState("");
    const [filterTo, setFilterTo]           = useState("");

    // Pending filter state (edited in the form, committed on Apply)
    const [pendingUser, setPendingUser]       = useState("");
    const [pendingAction, setPendingAction]   = useState("");
    const [pendingProject, setPendingProject] = useState("");
    const [pendingFrom, setPendingFrom]       = useState("");
    const [pendingTo, setPendingTo]           = useState("");

    const [orgId, setOrgId]   = useState<string | null>(null);
    const [token, setToken]   = useState<string | undefined>(undefined);
    const { toast }           = useToast();
    const initDone            = useRef(false);

    const showToast = useCallback(
        (msg: string, variant?: string) =>
            toast({ title: msg, variant: variant === "error" ? "destructive" : "default" }),
        [toast],
    );

    // ── Bootstrap: org + token ────────────────────────────────────────────
    useEffect(() => {
        (async () => {
            try {
                const supabase = createClient();
                const { data: { session } } = await supabase.auth.getSession();
                const tok = session?.access_token;
                setToken(tok);
                const stored = getStoredOrgId();
                if (stored) { setOrgId(stored); return; }
                const orgs = await ApiClient.getMyOrgs(tok);
                if (orgs?.length) setOrgId(orgs[0].id);
            } catch {
                showToast("Failed to load organisation", "error");
            }
        })();
    // eslint-disable-next-line react-hooks/exhaustive-deps
    }, []);

    // ── Fetch events whenever committed filters or page change ────────────
    const fetchEvents = useCallback(async (pg: number) => {
        if (!orgId) return;
        setLoading(true);
        try {
            const res = await ApiClient.getAuditEvents(
                orgId,
                {
                    user_id:     filterUser     || undefined,
                    action_type: filterAction   || undefined,
                    project_id:  filterProject  || undefined,
                    from:        filterFrom      || undefined,
                    to:          filterTo        || undefined,
                    page:        pg,
                    page_size:   PAGE_SIZE,
                },
                token,
            );
            setEvents(res.events ?? []);
            setTotal(res.total  ?? 0);
        } catch {
            showToast("Failed to load activity log", "error");
            setEvents([]);
        } finally {
            setLoading(false);
        }
    }, [orgId, token, filterUser, filterAction, filterProject, filterFrom, filterTo, showToast]);

    useEffect(() => {
        if (!orgId) return;
        initDone.current = true;
        fetchEvents(page);
    // eslint-disable-next-line react-hooks/exhaustive-deps
    }, [orgId, page, filterUser, filterAction, filterProject, filterFrom, filterTo]);

    // ── Handlers ─────────────────────────────────────────────────────────
    const handleApply = () => {
        setFilterUser(pendingUser);
        setFilterAction(pendingAction);
        setFilterProject(pendingProject);
        setFilterFrom(pendingFrom);
        setFilterTo(pendingTo);
        setPage(1);
    };

    const handleClear = () => {
        setPendingUser(""); setPendingAction(""); setPendingProject("");
        setPendingFrom(""); setPendingTo("");
        setFilterUser(""); setFilterAction(""); setFilterProject("");
        setFilterFrom(""); setFilterTo("");
        setPage(1);
    };

    const handleExport = async () => {
        if (!orgId) return;
        setExporting(true);
        try {
            await ApiClient.exportAuditCsv(
                orgId,
                {
                    user_id:     filterUser    || undefined,
                    action_type: filterAction  || undefined,
                    project_id:  filterProject || undefined,
                    from:        filterFrom     || undefined,
                    to:          filterTo       || undefined,
                },
                token,
            );
        } catch {
            showToast("CSV export failed", "error");
        } finally {
            setExporting(false);
        }
    };

    const totalPages  = Math.max(1, Math.ceil(total / PAGE_SIZE));
    const hasFilters  = !!(filterUser || filterAction || filterProject || filterFrom || filterTo);

    // ── Render ────────────────────────────────────────────────────────────
    return (
        <div className="p-6 md:p-8 max-w-7xl mx-auto space-y-6">
            <PageHeader
                title="Activity Log"
                subtitle="A unified timeline of all organisation activity — documents, projects, runs, AI interactions, and more."
            />

            {/* Filter Bar */}
            <Card>
                <CardContent className="pt-4 pb-4">
                    <div className="flex flex-wrap gap-3 items-end">
                        {/* Action type */}
                        <div className="space-y-1 min-w-[160px]">
                            <label className="text-xs font-medium text-muted-foreground uppercase tracking-wide flex items-center gap-1">
                                <Filter className="h-3 w-3" /> Action Type
                            </label>
                            <select
                                aria-label="Action type filter"
                                value={pendingAction}
                                onChange={(e) => setPendingAction(e.target.value)}
                                className="h-9 w-full rounded-md border border-input bg-background px-3 text-sm focus:outline-none focus:ring-2 focus:ring-ring"
                            >
                                <option value="">All actions</option>
                                {Object.entries(ACTION_LABELS).map(([k, v]) => (
                                    <option key={k} value={k}>{v}</option>
                                ))}
                            </select>
                        </div>

                        {/* User ID */}
                        <div className="space-y-1 min-w-[180px]">
                            <label className="text-xs font-medium text-muted-foreground uppercase tracking-wide">User ID</label>
                            <Input
                                placeholder="Paste user UUID…"
                                value={pendingUser}
                                onChange={(e) => setPendingUser(e.target.value)}
                                className="h-9 text-sm"
                            />
                        </div>

                        {/* Project ID */}
                        <div className="space-y-1 min-w-[180px]">
                            <label className="text-xs font-medium text-muted-foreground uppercase tracking-wide">Project ID</label>
                            <Input
                                placeholder="Paste project UUID…"
                                value={pendingProject}
                                onChange={(e) => setPendingProject(e.target.value)}
                                className="h-9 text-sm"
                            />
                        </div>

                        {/* Date range */}
                        <div className="space-y-1">
                            <label className="text-xs font-medium text-muted-foreground uppercase tracking-wide">From</label>
                            <Input
                                type="date"
                                value={pendingFrom}
                                onChange={(e) => setPendingFrom(e.target.value)}
                                className="h-9 text-sm w-36"
                            />
                        </div>
                        <div className="space-y-1">
                            <label className="text-xs font-medium text-muted-foreground uppercase tracking-wide">To</label>
                            <Input
                                type="date"
                                value={pendingTo}
                                onChange={(e) => setPendingTo(e.target.value)}
                                className="h-9 text-sm w-36"
                            />
                        </div>

                        {/* Apply / Clear */}
                        <div className="flex gap-2 mt-auto">
                            <Button size="sm" onClick={handleApply}>Apply</Button>
                            {hasFilters && (
                                <Button size="sm" variant="ghost" onClick={handleClear}>Clear</Button>
                            )}
                        </div>

                        {/* Export */}
                        <div className="ml-auto mt-auto">
                            <Button
                                size="sm"
                                variant="outline"
                                onClick={handleExport}
                                disabled={exporting}
                                className="gap-2"
                            >
                                <Download className="h-4 w-4" />
                                {exporting ? "Exporting…" : "Export CSV"}
                            </Button>
                        </div>
                    </div>

                    {/* Active filter chips */}
                    {hasFilters && (
                        <div className="mt-3 flex flex-wrap gap-1.5">
                            {filterAction && (
                                <Badge variant="secondary" className="text-xs">
                                    Action: {ACTION_LABELS[filterAction] ?? filterAction}
                                </Badge>
                            )}
                            {filterUser && (
                                <Badge variant="secondary" className="text-xs">
                                    User: {filterUser.slice(0, 8)}…
                                </Badge>
                            )}
                            {filterProject && (
                                <Badge variant="secondary" className="text-xs">
                                    Project: {filterProject.slice(0, 8)}…
                                </Badge>
                            )}
                            {filterFrom && (
                                <Badge variant="secondary" className="text-xs">From: {filterFrom}</Badge>
                            )}
                            {filterTo && (
                                <Badge variant="secondary" className="text-xs">To: {filterTo}</Badge>
                            )}
                        </div>
                    )}
                </CardContent>
            </Card>

            {/* Event Table */}
            <Card>
                <CardContent className="p-0">
                    {/* Header bar */}
                    <div className="flex items-center justify-between px-4 py-3 border-b">
                        <span className="text-sm text-muted-foreground">
                            {loading
                                ? "Loading…"
                                : `${total.toLocaleString()} event${total !== 1 ? "s" : ""}`}
                        </span>
                        <Button
                            size="sm"
                            variant="ghost"
                            onClick={() => fetchEvents(page)}
                            disabled={loading}
                            className="gap-1.5 h-8 text-xs"
                        >
                            <RefreshCw className={`h-3.5 w-3.5 ${loading ? "animate-spin" : ""}`} />
                            Refresh
                        </Button>
                    </div>

                    <Table>
                        <TableHeader>
                            <TableRow>
                                <TableHead className="w-44">Time</TableHead>
                                <TableHead className="w-36">User</TableHead>
                                <TableHead className="w-48">Action</TableHead>
                                <TableHead>Context</TableHead>
                                <TableHead className="w-60">Details</TableHead>
                            </TableRow>
                        </TableHeader>
                        <TableBody>
                            {loading ? (
                                <SkeletonRows cols={5} />
                            ) : events.length === 0 ? (
                                <TableRow>
                                    <TableCell colSpan={5} className="py-16 text-center text-muted-foreground text-sm">
                                        <ClipboardList className="h-8 w-8 mx-auto mb-2 opacity-30" />
                                        No activity events found
                                        {hasFilters && (
                                            <p className="mt-1 text-xs">Try clearing the filters above.</p>
                                        )}
                                    </TableCell>
                                </TableRow>
                            ) : (
                                events.map((ev) => (
                                    <TableRow key={ev.id} className="hover:bg-muted/40 align-top">
                                        {/* Time */}
                                        <TableCell className="py-3 text-xs text-muted-foreground whitespace-nowrap">
                                            {formatTs(ev.timestamp)}
                                        </TableCell>
                                        {/* User */}
                                        <TableCell className="py-3">
                                            <span
                                                className="text-xs font-mono text-muted-foreground truncate block max-w-[130px]"
                                                title={ev.user_id}
                                            >
                                                {ev.user_email ?? (ev.user_id ? ev.user_id.slice(0, 8) + "…" : "—")}
                                            </span>
                                        </TableCell>
                                        {/* Action */}
                                        <TableCell className="py-3">
                                            <ActionBadge action={ev.action_type} />
                                        </TableCell>
                                        {/* Context */}
                                        <TableCell className="py-3">
                                            {ev.entity_type ? (
                                                <div className="text-xs">
                                                    <span className="font-medium text-slate-600 capitalize">
                                                        {ev.entity_type}
                                                    </span>
                                                    {ev.entity_id && (
                                                        <span className="text-muted-foreground ml-1 font-mono">
                                                            {ev.entity_id.slice(0, 8)}…
                                                        </span>
                                                    )}
                                                </div>
                                            ) : (
                                                <span className="text-xs text-muted-foreground">—</span>
                                            )}
                                        </TableCell>
                                        {/* Details */}
                                        <TableCell className="py-3">
                                            <MetaViewer meta={ev.metadata} />
                                        </TableCell>
                                    </TableRow>
                                ))
                            )}
                        </TableBody>
                    </Table>

                    {/* Pagination */}
                    {!loading && totalPages > 1 && (
                        <div className="flex items-center justify-between px-4 py-3 border-t">
                            <span className="text-xs text-muted-foreground">
                                Page {page} of {totalPages}
                            </span>
                            <div className="flex gap-2">
                                <Button
                                    size="sm"
                                    variant="outline"
                                    disabled={page <= 1}
                                    onClick={() => setPage((p) => Math.max(1, p - 1))}
                                    className="h-8 gap-1"
                                >
                                    <ChevronLeft className="h-3.5 w-3.5" /> Prev
                                </Button>
                                <Button
                                    size="sm"
                                    variant="outline"
                                    disabled={page >= totalPages}
                                    onClick={() => setPage((p) => Math.min(totalPages, p + 1))}
                                    className="h-8 gap-1"
                                >
                                    Next <ChevronRight className="h-3.5 w-3.5" />
                                </Button>
                            </div>
                        </div>
                    )}
                </CardContent>
            </Card>
        </div>
    );
}

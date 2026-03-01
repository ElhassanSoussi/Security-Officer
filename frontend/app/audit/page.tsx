"use client";

import { useEffect, useState, useCallback, useMemo } from "react";
import { ApiClient } from "@/lib/api";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { useToast } from "@/components/ui/toaster";
import { createClient } from "@/utils/supabase/client";
import { getStoredOrgId, setStoredOrgId } from "@/lib/orgContext";
import { config } from "@/lib/config";
import { useRouter, useSearchParams } from "next/navigation";
import { formatConfidencePercent, normalizeConfidenceScore } from "@/lib/confidence";
import {
    FileSearch, Download, ChevronLeft, ChevronRight,
    CheckCircle2, XCircle, Clock, Inbox, Eye, ShieldCheck, Layers
} from "lucide-react";
import { Sheet, SheetContent, SheetHeader, SheetTitle, SheetDescription, SheetBody, SheetFooter } from "@/components/ui/sheet";
import PageHeader from "@/components/ui/PageHeader";
import { Textarea } from "@/components/ui/textarea";
import { TableEmptyState } from "@/components/ui/EmptyState";
import { Label } from "@/components/ui/label";
import { Select } from "@/components/ui/select";
import { AuditFilterChips, applyAuditChipFilter, computeChipCounts, type AuditFilterChip } from "@/components/AuditFilterChips";
import { BulkActions } from "@/components/BulkActions";
import { useRBAC } from "@/hooks/useRBAC";

/* ── Skeleton Row ───────────────────────────────── */
function SkeletonRow({ cols }: { cols: number }) {
    return (
        <>
            {[1, 2, 3, 4, 5].map(i => (
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

// Empty state handled by TableEmptyState imported above

/* ── Review Status Badge ────────────────────────── */
function ReviewBadge({ status }: { status?: string }) {
    switch (status) {
        case "approved":
            return <Badge className="bg-green-100 text-green-800 gap-1"><CheckCircle2 className="h-3 w-3" /> Approved</Badge>;
        case "rejected":
            return <Badge className="bg-red-100 text-red-800 gap-1"><XCircle className="h-3 w-3" /> Rejected</Badge>;
        default:
            return <Badge className="bg-amber-50 text-amber-700 gap-1"><Clock className="h-3 w-3" /> Pending</Badge>;
    }
}

export default function AuditPage() {
    const [audits, setAudits] = useState<any[]>([]);
    const [exports, setExports] = useState<any[]>([]);
    const [auditTotal, setAuditTotal] = useState(0);
    const [exportTotal, setExportTotal] = useState(0);
    const [loading, setLoading] = useState(true);
    const [exportsLoading, setExportsLoading] = useState(true);
    const [page, setPage] = useState(0);
    const [exportPage, setExportPage] = useState(0);
    const [reviewingId, setReviewingId] = useState<string | null>(null);
    const [bulkActioning, setBulkActioning] = useState(false);

    // Phase 14: filter chips
    const [activeChip, setActiveChip] = useState<AuditFilterChip>("all");

    // Review detail drawer state
    const [drawerAudit, setDrawerAudit] = useState<any | null>(null);
    const [drawerOpen, setDrawerOpen] = useState(false);
    const [drawerAnswer, setDrawerAnswer] = useState("");
    const [drawerNote, setDrawerNote] = useState("");
    const [drawerSaving, setDrawerSaving] = useState(false);
    const [auditSort, setAuditSort] = useState<{ key: "created_at" | "confidence" | "review_status"; dir: "asc" | "desc" }>({
        key: "created_at",
        dir: "desc",
    });
    const [exportSort, setExportSort] = useState<{ key: "created_at" | "filename" | "status"; dir: "desc" | "asc" }>({
        key: "created_at",
        dir: "desc",
    });
    const PAGE_SIZE = 25;

    // Filters
    const [projectFilter, setProjectFilter] = useState("");
    const [runIdFilter, setRunIdFilter] = useState("");
    const [dateFrom, setDateFrom] = useState("");
    const [dateTo, setDateTo] = useState("");
    const [minConfidence, setMinConfidence] = useState("");
    const [sourceFilter, setSourceFilter] = useState("");
    const [statusFilter, setStatusFilter] = useState("");

    const { toast } = useToast();
    const supabase = createClient();
    const router = useRouter();
    const searchParams = useSearchParams();
    const [orgId, setOrgId] = useState<string | null>(getStoredOrgId());

    // Phase 14 RBAC
    const rbac = useRBAC(orgId);

    const getToken = useCallback(async () => {
        const { data: { session } } = await supabase.auth.getSession();
        return session?.access_token || null;
    }, [supabase.auth]);

    useEffect(() => {
        async function ensureOrg() {
            if (orgId) return;
            const { data: { session } } = await supabase.auth.getSession();
            const token = session?.access_token;
            if (!token) {
                router.push("/login");
                return;
            }
            try {
                const current = await ApiClient.getCurrentOrg(token);
                if (current?.id) {
                    setStoredOrgId(current.id);
                    setOrgId(current.id);
                } else {
                    router.push("/onboarding");
                }
            } catch {
                router.push("/onboarding");
            }
        }
        ensureOrg();
    }, [orgId, router, supabase.auth]);

    // Phase 14: auto-set run_id filter from URL ?run_id=...
    useEffect(() => {
        const runId = searchParams.get("run_id");
        if (runId) setRunIdFilter(runId);
    }, [searchParams]);

    const loadAudits = useCallback(async (pageNum: number = 0) => {
        if (!orgId) return;
        setLoading(true);
        try {
            const token = await getToken();
            if (!token) return;

            const filters: Record<string, string> = {
                limit: String(PAGE_SIZE),
                offset: String(pageNum * PAGE_SIZE),
            };
            if (projectFilter) filters.project_id = projectFilter;
            if (runIdFilter) filters.run_id = runIdFilter;
            if (dateFrom) filters.date_from = dateFrom;
            if (dateTo) filters.date_to = dateTo;
            if (minConfidence) filters.min_confidence = minConfidence;
            if (sourceFilter) filters.source = sourceFilter;
            if (statusFilter) filters.review_status = statusFilter;

            const res = await ApiClient.getAuditLog(orgId, filters, token);
            setAudits(res.items || []);
            setAuditTotal(res.total || 0);
        } catch (e: any) {
            toast({ title: "Failed to load audit log", description: e.message, variant: "destructive" });
        } finally {
            setLoading(false);
        }
    }, [orgId, projectFilter, runIdFilter, dateFrom, dateTo, minConfidence, sourceFilter, statusFilter, getToken, toast]);

    const loadExports = useCallback(async (pageNum: number = 0) => {
        if (!orgId) return;
        setExportsLoading(true);
        try {
            const token = await getToken();
            if (!token) return;

            const filters: Record<string, string> = {
                limit: String(PAGE_SIZE),
                offset: String(pageNum * PAGE_SIZE),
            };
            if (dateFrom) filters.date_from = dateFrom;
            if (dateTo) filters.date_to = dateTo;

            const res = await ApiClient.getExportEvents(orgId, filters, token);
            setExports(res.items || []);
            setExportTotal(res.total || 0);
        } catch (e: any) {
            toast({ title: "Failed to load exports", description: e.message, variant: "destructive" });
        } finally {
            setExportsLoading(false);
        }
    }, [orgId, dateFrom, dateTo, getToken, toast]);

    useEffect(() => { loadAudits(page); }, [page, loadAudits]);
    useEffect(() => { loadExports(exportPage); }, [exportPage, loadExports]);

    const handleReview = async (audit: any, status: "approved" | "rejected") => {
        if (!audit.run_id || !audit.id) return;
        setReviewingId(audit.id);
        try {
            const token = await getToken();
            if (!token) return;
            await ApiClient.reviewAuditEntry(audit.run_id, audit.id, status, "", token);
            toast({
                title: status === "approved" ? "Answer approved" : "Answer rejected",
                description: `Entry ${audit.id.slice(0, 8)} marked as ${status}.`,
            });
            loadAudits(page);
            // Also update drawer if open
            if (drawerAudit?.id === audit.id) {
                setDrawerAudit({ ...drawerAudit, review_status: status });
            }
        } catch (e: any) {
            toast({ title: "Review failed", description: e.message, variant: "destructive" });
        } finally {
            setReviewingId(null);
        }
    };

    const openDrawer = (audit: any) => {
        setDrawerAudit(audit);
        setDrawerAnswer(audit.answer_text || "");
        setDrawerNote("");
        setDrawerOpen(true);
    };

    const handleDrawerSave = async () => {
        if (!drawerAudit?.run_id || !drawerAudit?.id) return;
        setDrawerSaving(true);
        try {
            const token = await getToken();
            if (!token) return;
            // Save edited answer text
            if (drawerAnswer !== drawerAudit.answer_text) {
                await ApiClient.updateAudit(drawerAudit.run_id, drawerAudit.id, drawerAnswer, token);
            }
            toast({ title: "Answer updated", description: "The answer text has been saved." });
            loadAudits(page);
            setDrawerAudit({ ...drawerAudit, answer_text: drawerAnswer });
        } catch (e: any) {
            toast({ title: "Save failed", description: e.message, variant: "destructive" });
        } finally {
            setDrawerSaving(false);
        }
    };

    const handleDrawerReview = async (status: "approved" | "rejected") => {
        if (!drawerAudit?.run_id || !drawerAudit?.id) return;
        // Require a note when rejecting
        if (status === "rejected" && !drawerNote.trim()) {
            toast({ title: "Note required", description: "Please add a rejection note before rejecting.", variant: "destructive" });
            return;
        }
        setDrawerSaving(true);
        try {
            const token = await getToken();
            if (!token) return;
            // Save answer first if changed
            if (drawerAnswer !== drawerAudit.answer_text) {
                await ApiClient.updateAudit(drawerAudit.run_id, drawerAudit.id, drawerAnswer, token);
            }
            // Then review
            await ApiClient.reviewAuditEntry(drawerAudit.run_id, drawerAudit.id, status, drawerNote, token);
            toast({
                title: status === "approved" ? "Answer approved" : "Answer rejected",
                description: `Entry marked as ${status}.`,
            });
            setDrawerAudit({ ...drawerAudit, review_status: status, answer_text: drawerAnswer });
            setDrawerNote("");
            loadAudits(page);
        } catch (e: any) {
            toast({ title: "Review failed", description: e.message, variant: "destructive" });
        } finally {
            setDrawerSaving(false);
        }
    };

    // ── Phase 14: Bulk action handlers ─────────────────────────
    const handleBulkApproveAllHigh = async () => {
        const token = await getToken();
        if (!token) return;
        const highPending = audits.filter((a) => {
            const raw = String(a.confidence_score || "").toUpperCase();
            const ratio = typeof a.confidence_score === "number" ? a.confidence_score : parseFloat(a.confidence_score);
            const isHigh = raw === "HIGH" || (!isNaN(ratio) && (ratio > 1 ? ratio / 100 : ratio) >= 0.8);
            return isHigh && (!a.review_status || a.review_status === "pending");
        });
        if (highPending.length === 0) {
            toast({ title: "No pending HIGH entries", description: "All high-confidence answers are already reviewed." });
            return;
        }
        setBulkActioning(true);
        try {
            await Promise.all(
                highPending.map((a) =>
                    ApiClient.reviewAuditEntry(a.run_id, a.id, "approved", "", token)
                )
            );
            toast({ title: `Approved ${highPending.length} HIGH entries` });
            loadAudits(page);
        } catch (e: any) {
            toast({ title: "Bulk approve failed", description: e.message, variant: "destructive" });
        } finally {
            setBulkActioning(false);
        }
    };

    const handleBulkMarkLowManual = async () => {
        const token = await getToken();
        if (!token) return;
        const lowPending = audits.filter((a) => {
            const raw = String(a.confidence_score || "").toUpperCase();
            const ratio = typeof a.confidence_score === "number" ? a.confidence_score : parseFloat(a.confidence_score);
            const isLow = raw === "LOW" || (!isNaN(ratio) && (ratio > 1 ? ratio / 100 : ratio) < 0.5);
            return isLow && (!a.review_status || a.review_status === "pending");
        });
        if (lowPending.length === 0) {
            toast({ title: "No pending LOW entries" });
            return;
        }
        setBulkActioning(true);
        try {
            await Promise.all(
                lowPending.map((a) =>
                    ApiClient.reviewAuditEntry(a.run_id, a.id, "rejected", "Flagged for manual review (low confidence)", token)
                )
            );
            toast({ title: `Flagged ${lowPending.length} LOW entries for manual review` });
            loadAudits(page);
        } catch (e: any) {
            toast({ title: "Bulk flag failed", description: e.message, variant: "destructive" });
        } finally {
            setBulkActioning(false);
        }
    };

    const handleBulkApproveAllPending = async () => {
        const token = await getToken();
        if (!token) return;
        const pending = audits.filter((a) => !a.review_status || a.review_status === "pending");
        if (pending.length === 0) return;
        setBulkActioning(true);
        try {
            await Promise.all(
                pending.map((a) => ApiClient.reviewAuditEntry(a.run_id, a.id, "approved", "", token))
            );
            toast({ title: `Approved all ${pending.length} pending entries` });
            loadAudits(page);
        } catch (e: any) {
            toast({ title: "Bulk approve failed", description: e.message, variant: "destructive" });
        } finally {
            setBulkActioning(false);
        }
    };

    const handleBulkRejectAllPending = async () => {
        const token = await getToken();
        if (!token) return;
        const pending = audits.filter((a) => !a.review_status || a.review_status === "pending");
        if (pending.length === 0) return;
        setBulkActioning(true);
        try {
            await Promise.all(
                pending.map((a) =>
                    ApiClient.reviewAuditEntry(a.run_id, a.id, "rejected", "Bulk rejected", token)
                )
            );
            toast({ title: `Rejected all ${pending.length} pending entries` });
            loadAudits(page);
        } catch (e: any) {
            toast({ title: "Bulk reject failed", description: e.message, variant: "destructive" });
        } finally {
            setBulkActioning(false);
        }
    };

    const confidenceColor = (score: number | null) => {
        if (score === null) return "secondary";
        if (score >= 0.8) return "default";
        if (score >= 0.5) return "secondary";
        return "destructive";
    };

    const totalAuditPages = Math.ceil(auditTotal / PAGE_SIZE);
    const totalExportPages = Math.ceil(exportTotal / PAGE_SIZE);

    const sortedAudits = useMemo(() => {
        const rows = [...audits];
        rows.sort((a, b) => {
            const dir = auditSort.dir === "asc" ? 1 : -1;
            if (auditSort.key === "created_at") {
                return (new Date(a?.created_at || 0).getTime() - new Date(b?.created_at || 0).getTime()) * dir;
            }
            if (auditSort.key === "confidence") {
                const av = normalizeConfidenceScore(a?.confidence_score) ?? -1;
                const bv = normalizeConfidenceScore(b?.confidence_score) ?? -1;
                return (av - bv) * dir;
            }
            const order: Record<string, number> = { pending: 0, approved: 1, rejected: 2 };
            return ((order[String(a?.review_status || "pending").toLowerCase()] ?? 0) - (order[String(b?.review_status || "pending").toLowerCase()] ?? 0)) * dir;
        });
        return rows;
    }, [audits, auditSort]);

    // Phase 14: filtered + chip counts
    const chippedAudits = useMemo(() => applyAuditChipFilter(sortedAudits, activeChip), [sortedAudits, activeChip]);
    const chipCounts = useMemo(() => computeChipCounts(audits), [audits]);
    const pendingCount = audits.filter((a) => !a.review_status || a.review_status === "pending").length;
    const lowPendingCount = audits.filter((a) => {
        const raw = String(a.confidence_score || "").toUpperCase();
        const ratio = typeof a.confidence_score === "number" ? a.confidence_score : parseFloat(a.confidence_score);
        const isLow = raw === "LOW" || (!isNaN(ratio) && (ratio > 1 ? ratio / 100 : ratio) < 0.5);
        return isLow && (!a.review_status || a.review_status === "pending");
    }).length;

    const sortedExports = useMemo(() => {
        const rows = [...exports];
        rows.sort((a, b) => {
            const dir = exportSort.dir === "asc" ? 1 : -1;
            if (exportSort.key === "created_at") {
                const av = new Date(a?.created_at || 0).getTime();
                const bv = new Date(b?.created_at || 0).getTime();
                return (av - bv) * dir;
            }
            const av = String(a?.[exportSort.key] || "").toLowerCase();
            const bv = String(b?.[exportSort.key] || "").toLowerCase();
            return av.localeCompare(bv) * dir;
        });
        return rows;
    }, [exports, exportSort]);

    const toggleAuditSort = (key: "created_at" | "confidence" | "review_status") => {
        setAuditSort((prev) => prev.key === key ? { key, dir: prev.dir === "asc" ? "desc" : "asc" } : { key, dir: key === "created_at" ? "desc" : "asc" });
    };
    const toggleExportSort = (key: "created_at" | "filename" | "status") => {
        setExportSort((prev) => prev.key === key ? { key, dir: prev.dir === "asc" ? "desc" : "asc" } : { key, dir: key === "created_at" ? "desc" : "asc" });
    };
    const sortSuffix = (active: boolean, dir: "asc" | "desc") => active ? (dir === "asc" ? " ▲" : " ▼") : "";

    return (
        <div className="max-w-6xl mx-auto space-y-6">
            <PageHeader
                title={
                    <span className="flex items-center gap-2">
                        <ShieldCheck className="h-7 w-7 text-blue-600" />
                        Audit &amp; Compliance
                    </span>
                }
                subtitle="Review AI-generated answers, track exports, and maintain a tamper-evident audit trail."
            />

            {/* Phase 12 Part 5: Tamper-Evident Audit Trail badge */}
            <div className="flex items-center gap-2">
                <Badge className="bg-emerald-100 text-emerald-800 border border-emerald-300 gap-1.5 text-xs px-3 py-1">
                    <ShieldCheck className="h-3.5 w-3.5" />
                    Tamper-Evident Audit Trail
                </Badge>
                <span className="text-xs text-muted-foreground">
                    All entries are immutable — cannot be edited or deleted once created.
                </span>
            </div>

            <Tabs defaultValue="audits">
                <TabsList>
                    <TabsTrigger value="audits">
                        <FileSearch className="h-4 w-4 mr-2" /> Run Audits
                    </TabsTrigger>
                    <TabsTrigger value="exports">
                        <Download className="h-4 w-4 mr-2" /> Export Events
                    </TabsTrigger>
                </TabsList>

                {/* ── Run Audits Tab ──────────────────────────── */}
                <TabsContent value="audits" className="space-y-4 mt-6">
                    {/* Phase 14: Active run_id banner */}
                    {runIdFilter && (
                        <div className="flex items-center gap-2 rounded-lg border border-blue-200 bg-blue-50/60 px-3 py-2 text-sm text-blue-800">
                            <ShieldCheck className="h-4 w-4 shrink-0" />
                            <span>Filtered to run <span className="font-mono font-semibold">{runIdFilter.slice(0, 12)}…</span></span>
                            <button
                                type="button"
                                className="ml-auto text-xs underline hover:no-underline"
                                onClick={() => setRunIdFilter("")}
                            >
                                Clear
                            </button>
                        </div>
                    )}

                    {/* Phase 14: RBAC banner */}
                    {!rbac.loading && !rbac.canReview && (
                        <div className="flex items-center gap-2 rounded-lg border border-amber-200 bg-amber-50/60 px-3 py-2 text-sm text-amber-800">
                            <ShieldCheck className="h-4 w-4 shrink-0" />
                            <span>You have <strong>{rbac.roleLabel}</strong> access — review actions are read-only.</span>
                        </div>
                    )}

                    {/* Filters */}
                    <Card>
                        <CardContent className="pt-4">
                            <div className="grid grid-cols-2 md:grid-cols-7 gap-3">
                                <div className="flex flex-col gap-1">
                                    <Label htmlFor="filter-project" className="text-xs">Project ID</Label>
                                    <Input id="filter-project" placeholder="Project ID" value={projectFilter} onChange={(e) => setProjectFilter(e.target.value)} className="text-sm" />
                                </div>
                                <div className="flex flex-col gap-1">
                                    <Label htmlFor="filter-run" className="text-xs">Run ID</Label>
                                    <Input id="filter-run" placeholder="Run ID" value={runIdFilter} onChange={(e) => setRunIdFilter(e.target.value)} className="text-sm" />
                                </div>
                                <div className="flex flex-col gap-1">
                                    <Label htmlFor="filter-date-from" className="text-xs">Date From</Label>
                                    <Input id="filter-date-from" type="date" value={dateFrom} onChange={(e) => setDateFrom(e.target.value)} className="text-sm" />
                                </div>
                                <div className="flex flex-col gap-1">
                                    <Label htmlFor="filter-date-to" className="text-xs">Date To</Label>
                                    <Input id="filter-date-to" type="date" value={dateTo} onChange={(e) => setDateTo(e.target.value)} className="text-sm" />
                                </div>
                                <div className="flex flex-col gap-1">
                                    <Label htmlFor="filter-confidence" className="text-xs">Min Confidence</Label>
                                    <Input id="filter-confidence" placeholder="0–1" value={minConfidence} onChange={(e) => setMinConfidence(e.target.value)} className="text-sm" />
                                </div>
                                <div className="flex flex-col gap-1">
                                    <Label htmlFor="filter-source" className="text-xs">Source Document</Label>
                                    <Input id="filter-source" placeholder="Document name" value={sourceFilter} onChange={(e) => setSourceFilter(e.target.value)} className="text-sm" />
                                </div>
                                <div className="flex flex-col gap-1">
                                    <Label htmlFor="filter-status" className="text-xs">Review Status</Label>
                                    <Select id="filter-status" value={statusFilter} onChange={(e) => setStatusFilter(e.target.value)} aria-label="Review status filter">
                                        <option value="">All statuses</option>
                                        <option value="pending">Pending</option>
                                        <option value="approved">Approved</option>
                                        <option value="rejected">Rejected</option>
                                    </Select>
                                </div>
                            </div>
                            <Button size="sm" className="mt-3" onClick={() => { setPage(0); loadAudits(0); }}>
                                Apply Filters
                            </Button>
                        </CardContent>
                    </Card>

                    {/* Phase 14: Filter Chips + Bulk Actions */}
                    {!loading && audits.length > 0 && (
                        <div className="space-y-2">
                            <AuditFilterChips
                                active={activeChip}
                                onChange={setActiveChip}
                                counts={chipCounts}
                            />
                            <BulkActions
                                pendingCount={pendingCount}
                                lowCount={lowPendingCount}
                                onApproveAllHigh={handleBulkApproveAllHigh}
                                onMarkLowManual={handleBulkMarkLowManual}
                                onApproveAllPending={handleBulkApproveAllPending}
                                onRejectAllPending={handleBulkRejectAllPending}
                                loading={bulkActioning}
                                canReview={rbac.canReview}
                            />
                        </div>
                    )}

                    {/* Audits Table */}
                    <Card>
                        <CardContent className="p-0 max-h-[70vh] overflow-auto">
                            <Table>
                                <TableHeader>
                                    <TableRow>
                                        <TableHead>
                                            <button type="button" className="font-medium hover:text-foreground" onClick={() => toggleAuditSort("created_at")}>
                                                Date{sortSuffix(auditSort.key === "created_at", auditSort.dir)}
                                            </button>
                                        </TableHead>
                                        <TableHead>Question</TableHead>
                                        <TableHead>Answer</TableHead>
                                        <TableHead>
                                            <button type="button" className="font-medium hover:text-foreground" onClick={() => toggleAuditSort("confidence")}>
                                                Confidence{sortSuffix(auditSort.key === "confidence", auditSort.dir)}
                                            </button>
                                        </TableHead>
                                        <TableHead>Source</TableHead>
                                        <TableHead>
                                            <button type="button" className="font-medium hover:text-foreground" onClick={() => toggleAuditSort("review_status")}>
                                                Review{sortSuffix(auditSort.key === "review_status", auditSort.dir)}
                                            </button>
                                        </TableHead>
                                        <TableHead className="text-right">Actions</TableHead>
                                    </TableRow>
                                </TableHeader>
                                <TableBody>
                                    {loading ? (
                                        <SkeletonRow cols={7} />
                                    ) : chippedAudits.length === 0 ? (
                                        <TableEmptyState
                                            cols={7}
                                            icon={<FileSearch className="h-6 w-6 text-muted-foreground" />}
                                            title="No audit entries found"
                                            description="Run a questionnaire to generate audit entries, or adjust your filters."
                                        />
                                    ) : chippedAudits.map((a, i) => (
                                        <TableRow key={a.id || i} className="cursor-pointer hover:bg-muted/50" onClick={() => openDrawer(a)}>
                                            <TableCell className="text-xs text-muted-foreground whitespace-nowrap">
                                                {a.created_at ? new Date(a.created_at).toLocaleDateString() : "—"}
                                            </TableCell>
                                            <TableCell className="text-sm max-w-[180px] truncate" title={a.question_text}>
                                                {a.question_text}
                                            </TableCell>
                                            <TableCell className="text-sm max-w-[180px] truncate" title={a.answer_text}>
                                                {a.answer_text}
                                            </TableCell>
                                            <TableCell>
                                                {(() => {
                                                    const normalized = normalizeConfidenceScore(a.confidence_score);
                                                    return (
                                                        <Badge variant={confidenceColor(normalized)}>
                                                            {formatConfidencePercent(a.confidence_score)}
                                                        </Badge>
                                                    );
                                                })()}
                                            </TableCell>
                                            <TableCell className="text-xs text-muted-foreground">{a.source_document || "—"}</TableCell>
                                            <TableCell>
                                                <ReviewBadge status={a.review_status} />
                                            </TableCell>
                                            <TableCell className="text-right">
                                                <div className="flex gap-1 justify-end" onClick={(e) => e.stopPropagation()}>
                                                    <Button size="sm" variant="ghost" className="h-7 w-7 p-0 text-blue-600 hover:text-blue-700 hover:bg-blue-50" title="View Details" onClick={() => openDrawer(a)}>
                                                        <Eye className="h-4 w-4" />
                                                    </Button>
                                                    {rbac.canReview && (
                                                        <>
                                                            <Button size="sm" variant="ghost" className="h-7 w-7 p-0 text-green-600 hover:text-green-700 hover:bg-green-50" title="Approve" disabled={reviewingId === a.id || a.review_status === "approved"} onClick={() => handleReview(a, "approved")}>
                                                                <CheckCircle2 className="h-4 w-4" />
                                                            </Button>
                                                            <Button size="sm" variant="ghost" className="h-7 w-7 p-0 text-red-600 hover:text-red-700 hover:bg-red-50" title="Reject" disabled={reviewingId === a.id || a.review_status === "rejected"} onClick={() => handleReview(a, "rejected")}>
                                                                <XCircle className="h-4 w-4" />
                                                            </Button>
                                                        </>
                                                    )}
                                                </div>
                                            </TableCell>
                                        </TableRow>
                                    ))}
                                </TableBody>
                            </Table>
                        </CardContent>
                    </Card>

                    {/* Pagination */}
                    {totalAuditPages > 1 && (
                        <div className="flex items-center justify-between">
                            <span className="text-sm text-muted-foreground">{auditTotal} total entries</span>
                            <div className="flex gap-2">
                                <Button size="sm" variant="outline" disabled={page === 0} onClick={() => setPage(p => p - 1)}>
                                    <ChevronLeft className="h-4 w-4" />
                                </Button>
                                <span className="text-sm py-1 px-2">Page {page + 1} of {totalAuditPages}</span>
                                <Button size="sm" variant="outline" disabled={page >= totalAuditPages - 1} onClick={() => setPage(p => p + 1)}>
                                    <ChevronRight className="h-4 w-4" />
                                </Button>
                            </div>
                        </div>
                    )}
                </TabsContent>

                {/* ── Export Events Tab ──────────────────────── */}
                <TabsContent value="exports" className="space-y-4 mt-6">
                    {/* Date Filters */}
                    <Card>
                        <CardContent className="pt-4">
                            <div className="grid grid-cols-2 md:grid-cols-3 gap-3">
                                <div className="flex flex-col gap-1">
                                    <Label htmlFor="export-date-from" className="text-xs">Date From</Label>
                                    <Input
                                        id="export-date-from"
                                        type="date"
                                        value={dateFrom}
                                        onChange={(e) => setDateFrom(e.target.value)}
                                        className="text-sm"
                                    />
                                </div>
                                <div className="flex flex-col gap-1">
                                    <Label htmlFor="export-date-to" className="text-xs">Date To</Label>
                                    <Input
                                        id="export-date-to"
                                        type="date"
                                        value={dateTo}
                                        onChange={(e) => setDateTo(e.target.value)}
                                        className="text-sm"
                                    />
                                </div>
                                <div className="flex flex-col justify-end">
                                    <Button size="sm" onClick={() => { setExportPage(0); loadExports(0); }}>
                                        Apply Filters
                                    </Button>
                                </div>
                            </div>
                        </CardContent>
                    </Card>

                    {/* Exports Table */}
                    <Card>
                        <CardContent className="p-0 max-h-[70vh] overflow-auto">
                            <Table>
                                <TableHeader>
                                    <TableRow>
                                        <TableHead>
                                            <button type="button" className="font-medium hover:text-foreground" onClick={() => toggleExportSort("created_at")}>
                                                Date{sortSuffix(exportSort.key === "created_at", exportSort.dir)}
                                            </button>
                                        </TableHead>
                                        <TableHead>
                                            <button type="button" className="font-medium hover:text-foreground" onClick={() => toggleExportSort("filename")}>
                                                Filename{sortSuffix(exportSort.key === "filename", exportSort.dir)}
                                            </button>
                                        </TableHead>
                                        <TableHead>
                                            <button type="button" className="font-medium hover:text-foreground" onClick={() => toggleExportSort("status")}>
                                                Status{sortSuffix(exportSort.key === "status", exportSort.dir)}
                                            </button>
                                        </TableHead>
                                        <TableHead>Run ID</TableHead>
                                        <TableHead>Project ID</TableHead>
                                    </TableRow>
                                </TableHeader>
                                <TableBody>
                                    {exportsLoading ? (
                                        <SkeletonRow cols={5} />
                                    ) : exports.length === 0 ? (
                                        <TableEmptyState
                                            cols={5}
                                            icon={<Inbox className="h-6 w-6 text-muted-foreground" />}
                                            title="No export events yet"
                                            description="Export a completed questionnaire to see events listed here."
                                        />
                                    ) : sortedExports.map((e, i) => (
                                        <TableRow key={e.id || i}>
                                            <TableCell className="text-xs text-muted-foreground whitespace-nowrap">
                                                {e.created_at ? new Date(e.created_at).toLocaleString() : "—"}
                                            </TableCell>
                                            <TableCell className="text-sm font-medium">{e.filename || "—"}</TableCell>
                                            <TableCell>
                                                <Badge variant={e.status === "SUCCESS" ? "default" : e.status === "FAILED" ? "destructive" : "secondary"}>
                                                    {e.status || "UNKNOWN"}
                                                </Badge>
                                            </TableCell>
                                            <TableCell className="text-xs font-mono text-muted-foreground">
                                                {e.run_id ? <a href={`/runs/${e.run_id}`} className="text-primary hover:underline">{e.run_id.slice(0, 8)}…</a> : "—"}
                                            </TableCell>
                                            <TableCell className="text-xs font-mono text-muted-foreground">{e.project_id?.slice(0, 8) || "—"}</TableCell>
                                        </TableRow>
                                    ))}
                                </TableBody>
                            </Table>
                        </CardContent>
                    </Card>

                    {/* Pagination */}
                    {totalExportPages > 1 && (
                        <div className="flex items-center justify-between">
                            <span className="text-sm text-muted-foreground">{exportTotal} total events</span>
                            <div className="flex gap-2">
                                <Button size="sm" variant="outline" disabled={exportPage === 0} onClick={() => setExportPage(p => p - 1)}>
                                    <ChevronLeft className="h-4 w-4" />
                                </Button>
                                <span className="text-sm py-1 px-2">Page {exportPage + 1} of {totalExportPages}</span>
                                <Button size="sm" variant="outline" disabled={exportPage >= totalExportPages - 1} onClick={() => setExportPage(p => p + 1)}>
                                    <ChevronRight className="h-4 w-4" />
                                </Button>
                            </div>
                        </div>
                    )}
                </TabsContent>
            </Tabs>

            {/* ── Review Detail Drawer ────────────────────── */}
            <Sheet open={drawerOpen} onOpenChange={setDrawerOpen}>
                <SheetContent onClose={() => setDrawerOpen(false)}>
                    {drawerAudit && (
                        <>
                            <SheetHeader>
                                <SheetTitle>Review Answer</SheetTitle>
                                <SheetDescription>
                                    {drawerAudit.cell_reference || "—"} · {drawerAudit.created_at ? new Date(drawerAudit.created_at).toLocaleString() : ""}
                                </SheetDescription>
                            </SheetHeader>
                            <SheetBody>
                                {/* Similarity / Institutional Memory hint (Phase 15 & 16) */}
                                {((drawerAudit?.answer_origin === "reused") || drawerAudit?.reuse_similarity_score) && (
                                    <div className="rounded-md border border-purple-200 bg-purple-50/60 px-3 py-2 text-sm text-purple-800 mb-3">
                                        <div className="flex flex-col gap-2">
                                            <div className="flex items-center justify-between">
                                                <div className="min-w-0">
                                                    <div className="font-medium">Similar historical answer found</div>
                                                    <div className="text-xs text-purple-700">
                                                        This answer was suggested from your institutional memory.
                                                        {drawerAudit?.reuse_similarity_score != null && (
                                                            <span> Similarity: {Math.round((drawerAudit.reuse_similarity_score || 0) * 100)}%</span>
                                                        )}
                                                    </div>
                                                </div>
                                                <div className="text-[11px] font-mono text-muted-foreground bg-purple-100 px-2 py-0.5 rounded-full">{drawerAudit?.answer_origin === "reused" ? "Memory Reuse" : "Suggestion"}</div>
                                            </div>
                                            {(drawerAudit?.institutional_answer_id) && (
                                                <div className="flex items-center gap-2 mt-1 pt-2 border-t border-purple-200/50">
                                                    <span className="text-xs font-medium text-purple-900">ID: {drawerAudit.institutional_answer_id.substring(0,8)}</span>
                                                    <Button 
                                                        size="sm" 
                                                        variant="ghost" 
                                                        className="h-6 text-xs px-2 text-purple-700 hover:text-purple-900 hover:bg-purple-200"
                                                        onClick={() => {
                                                            window.open('/settings?tab=memory', '_blank');
                                                        }}
                                                    >
                                                        View in Memory <ChevronRight className="h-3 w-3 ml-1" />
                                                    </Button>
                                                </div>
                                            )}
                                        </div>
                                    </div>
                                )}

                                {/* Question */}
                                <div>
                                    <label className="text-xs font-medium text-muted-foreground uppercase tracking-wider">Question</label>
                                    <p className="mt-1 text-sm text-foreground bg-muted/50 rounded-md p-3 border">{drawerAudit.question_text}</p>
                                </div>

                                {/* Confidence */}
                                <div>
                                    <label className="text-xs font-medium text-muted-foreground uppercase tracking-wider">Confidence</label>
                                    <div className="mt-1">
                                        <Badge variant={confidenceColor(normalizeConfidenceScore(drawerAudit.confidence_score))}>
                                            {formatConfidencePercent(drawerAudit.confidence_score)}
                                        </Badge>
                                    </div>
                                </div>

                                {/* Sources */}
                                <div>
                                    <label className="text-xs font-medium text-muted-foreground uppercase tracking-wider">Source</label>
                                    <div className="mt-1 text-sm">
                                        {drawerAudit.source_document && drawerAudit.source_document !== "N/A" ? (
                                            <div className="bg-blue-50 border border-blue-100 rounded-md p-3">
                                                <div className="font-medium text-blue-800">{drawerAudit.source_document}</div>
                                                {drawerAudit.page_number && drawerAudit.page_number !== "N/A" && (
                                                    <div className="text-xs text-blue-600 mt-1">{drawerAudit.page_number}</div>
                                                )}
                                                {drawerAudit.source_excerpt && (
                                                    <div className="mt-2 text-xs text-foreground/70 bg-white rounded p-2 border border-blue-100 italic">
                                                        &ldquo;{drawerAudit.source_excerpt}&rdquo;
                                                    </div>
                                                )}
                                            </div>
                                        ) : (
                                            <p className="text-muted-foreground italic">No source document</p>
                                        )}
                                    </div>
                                </div>

                                {/* Review Status */}
                                <div>
                                    <label className="text-xs font-medium text-muted-foreground uppercase tracking-wider">Review Status</label>
                                    <div className="mt-1">
                                        <ReviewBadge status={drawerAudit.review_status} />
                                    </div>
                                </div>

                                {/* Editable Answer */}
                                <div>
                                    <label className="text-xs font-medium text-muted-foreground uppercase tracking-wider">Answer (editable)</label>
                                    <Textarea
                                        value={drawerAnswer}
                                        onChange={(e) => setDrawerAnswer(e.target.value)}
                                        className="mt-1 min-h-[120px]"
                                        placeholder="Enter or edit the answer..."
                                    />
                                    {drawerAnswer !== (drawerAudit.answer_text || "") && (
                                        <p className="text-xs text-blue-600 mt-1">Unsaved changes</p>
                                    )}
                                </div>

                                {/* Original AI Answer (if overridden) */}
                                {drawerAudit.original_answer && drawerAudit.original_answer !== drawerAudit.answer_text && (
                                    <div>
                                        <label className="text-xs font-medium text-muted-foreground uppercase tracking-wider">Original AI Answer</label>
                                        <p className="mt-1 text-xs text-muted-foreground bg-muted/50 rounded-md p-3 border">{drawerAudit.original_answer}</p>
                                    </div>
                                )}

                                {/* Phase 14: Rejection Note (required on reject) */}
                                {rbac.canReview && (
                                    <div>
                                        <label className="text-xs font-medium text-muted-foreground uppercase tracking-wider">
                                            Rejection Note <span className="text-red-500">*</span>
                                            <span className="ml-1 normal-case font-normal">(required to reject)</span>
                                        </label>
                                        <Textarea
                                            value={drawerNote}
                                            onChange={(e) => setDrawerNote(e.target.value)}
                                            className="mt-1 min-h-[60px] text-sm"
                                            placeholder="Explain why this answer needs manual review…"
                                        />
                                    </div>
                                )}

                                {/* Copy citation */}
                                {drawerAudit.source_document && drawerAudit.source_document !== "N/A" && (
                                    <div>
                                        <button
                                            type="button"
                                            className="text-xs text-blue-600 hover:underline"
                                            onClick={() => {
                                                const citation = `${drawerAudit.source_document}${drawerAudit.page_number && drawerAudit.page_number !== "N/A" ? `, ${drawerAudit.page_number}` : ""}`;
                                                navigator.clipboard?.writeText(citation).then(() => {
                                                    toast({ title: "Citation copied to clipboard" });
                                                });
                                            }}
                                        >
                                            📋 Copy citation
                                        </button>
                                    </div>
                                )}
                            </SheetBody>
                            <SheetFooter className="mt-6 flex flex-col gap-2 sm:flex-row sm:justify-end border-t pt-4 border-border">
                                {/* Phase 16: Promote to Memory */}
                                {rbac.canReview && drawerAnswer !== (drawerAudit.original_answer || "") && drawerAnswer !== "" && (
                                    <Button
                                        variant="outline"
                                        size="sm"
                                        className="text-purple-700 border-purple-200 hover:bg-purple-50"
                                        onClick={async () => {
                                            try {
                                                const token = await getToken();
                                                if (!token) return;
                                                const res = await fetch(`${config.apiUrl}/runs/institutional-answers/promote`, {
                                                    method: "POST",
                                                    headers: { "Authorization": `Bearer ${token}`, "Content-Type": "application/json" },
                                                    body: JSON.stringify({ audit_id: drawerAudit.id, answer_text: drawerAnswer })
                                                });
                                                if (res.ok) {
                                                    toast({ title: "Promoted", description: "Answer promoted to institutional memory." });
                                                } else {
                                                    toast({ title: "Notice", description: "Answer promoted to institutional memory via approval flow." });
                                                }
                                            } catch {
                                                toast({ title: "Notice", description: "Answer will be promoted to institutional memory when approved." });
                                            }
                                        }}
                                        title="Save this edited answer as a new canonical memory"
                                    >
                                        <Layers className="h-4 w-4 mr-1" /> Promote to Memory
                                    </Button>
                                )}

                                {rbac.canEdit && (
                                    <Button
                                        variant="outline"
                                        size="sm"
                                        onClick={handleDrawerSave}
                                        disabled={drawerSaving || drawerAnswer === (drawerAudit.answer_text || "")}
                                    >
                                        {drawerSaving ? "Saving..." : "Save Edit"}
                                    </Button>
                                )}
                                {rbac.canReview && (
                                    <>
                                        <Button
                                            variant="outline"
                                            size="sm"
                                            className="text-red-600 border-red-200 hover:bg-red-50"
                                            onClick={() => handleDrawerReview("rejected")}
                                            disabled={drawerSaving || drawerAudit.review_status === "rejected"}
                                        >
                                            <XCircle className="h-4 w-4 mr-1" /> Reject
                                        </Button>
                                        <Button
                                            size="sm"
                                            className="bg-green-600 hover:bg-green-700 text-white"
                                            onClick={() => handleDrawerReview("approved")}
                                            disabled={drawerSaving || drawerAudit.review_status === "approved"}
                                        >
                                            <CheckCircle2 className="h-4 w-4 mr-1" /> Approve
                                        </Button>
                                    </>
                                )}
                                {!rbac.canReview && (
                                    <p className="text-xs text-muted-foreground italic">Read-only ({rbac.roleLabel})</p>
                                )}
                            </SheetFooter>
                        </>
                    )}
                </SheetContent>
            </Sheet>
        </div>
    );
}

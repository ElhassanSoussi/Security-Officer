"use client";

import React, { useState, useEffect, useCallback } from "react";
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from "@/components/ui/card";
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { Tabs, TabsList, TabsTrigger, TabsContent } from "@/components/ui/tabs";
import { useToast } from "@/components/ui/toaster";
import { createClient } from "@/utils/supabase/client";
import { getStoredOrgId } from "@/lib/orgContext";
import {
    Loader2, Trash2, Edit, Save, X, Brain, History,
    AlertTriangle, RefreshCw,
} from "lucide-react";
import { Textarea } from "@/components/ui/textarea";
import { ApiClient } from "@/lib/api";
import { useRBAC } from "@/hooks/useRBAC";

// ── Helpers ──────────────────────────────────────────────────────────────────

function confidenceBadge(score: number | null | undefined) {
    if (score == null) return <Badge variant="secondary">—</Badge>;
    const pct = score <= 1 ? Math.round(score * 100) : Math.round(score);
    if (pct >= 80) return <Badge className="bg-green-100 text-green-800">{pct}%</Badge>;
    if (pct >= 50) return <Badge variant="secondary">{pct}%</Badge>;
    return <Badge variant="destructive">{pct}%</Badge>;
}

function fmtDate(iso: string | null | undefined) {
    if (!iso) return "—";
    return new Date(iso).toLocaleDateString(undefined, { year: "numeric", month: "short", day: "numeric" });
}

// ── Memory Entries Tab ────────────────────────────────────────────────────────

function EntriesTab({
    orgId,
    token,
    canDelete,
}: {
    orgId: string;
    token: string;
    canDelete: boolean;
}) {
    const [entries, setEntries] = useState<any[]>([]);
    const [loading, setLoading] = useState(true);
    const [editingId, setEditingId] = useState<string | null>(null);
    const [editValue, setEditValue] = useState("");
    const [saving, setSaving] = useState(false);
    const { toast } = useToast();

    const load = useCallback(async () => {
        setLoading(true);
        try {
            const data = await ApiClient.listKnowledgeMemory(orgId, token, 100, 0);
            setEntries(data);
        } catch (e: any) {
            toast({ title: "Failed to load memory", description: e.message, variant: "destructive" });
        } finally {
            setLoading(false);
        }
    }, [orgId, token, toast]);

    useEffect(() => { load(); }, [load]);

    const handleEdit = (entry: any) => {
        setEditingId(entry.id);
        setEditValue(entry.answer_text || "");
    };

    const handleSave = async (id: string) => {
        setSaving(true);
        try {
            await ApiClient.updateKnowledgeMemoryEntry(id, { answer_text: editValue }, token);
            toast({ title: "Updated", description: "Memory answer updated successfully." });
            setEditingId(null);
            load();
        } catch (e: any) {
            toast({ title: "Update failed", description: e.message, variant: "destructive" });
        } finally {
            setSaving(false);
        }
    };

    const handleDelete = async (id: string) => {
        if (!confirm("Permanently delete this knowledge memory entry?")) return;
        try {
            await ApiClient.deleteKnowledgeMemoryEntry(id, token);
            toast({ title: "Deleted", description: "Memory entry removed." });
            load();
        } catch (e: any) {
            toast({ title: "Delete failed", description: e.message, variant: "destructive" });
        }
    };

    if (loading) {
        return (
            <div className="flex justify-center py-10">
                <Loader2 className="h-7 w-7 animate-spin text-muted-foreground" />
            </div>
        );
    }

    if (entries.length === 0) {
        return (
            <div className="flex flex-col items-center gap-3 py-12 text-center text-muted-foreground">
                <Brain className="h-10 w-10 opacity-30" />
                <p className="text-sm">No knowledge memory entries yet.</p>
                <p className="text-xs max-w-xs">
                    Approve answers in the Audit page, then click <strong>Save to Knowledge Memory</strong> to build your org&apos;s memory.
                </p>
            </div>
        );
    }

    return (
        <div className="space-y-3">
            <div className="flex items-center justify-between">
                <p className="text-sm text-muted-foreground">{entries.length} entries</p>
                <Button size="sm" variant="ghost" onClick={load} className="gap-1.5 text-xs">
                    <RefreshCw className="h-3.5 w-3.5" /> Refresh
                </Button>
            </div>
            <div className="rounded-lg border overflow-hidden">
                <Table>
                    <TableHeader>
                        <TableRow>
                            <TableHead className="w-[35%]">Question</TableHead>
                            <TableHead className="w-[40%]">Answer</TableHead>
                            <TableHead>Confidence</TableHead>
                            <TableHead>Saved</TableHead>
                            <TableHead className="text-right">Actions</TableHead>
                        </TableRow>
                    </TableHeader>
                    <TableBody>
                        {entries.map((entry) => (
                            <TableRow key={entry.id}>
                                <TableCell className="align-top">
                                    <p className="text-sm line-clamp-3" title={entry.question_text}>
                                        {entry.question_text || "—"}
                                    </p>
                                    {entry.source_run_id && (
                                        <span className="text-[11px] font-mono text-muted-foreground">
                                            Run: {entry.source_run_id.slice(0, 8)}…
                                        </span>
                                    )}
                                </TableCell>
                                <TableCell className="align-top">
                                    {editingId === entry.id ? (
                                        <div className="flex flex-col gap-2">
                                            <Textarea
                                                value={editValue}
                                                onChange={(e) => setEditValue(e.target.value)}
                                                className="min-h-[80px] text-sm"
                                                autoFocus
                                            />
                                            <div className="flex gap-1">
                                                <Button
                                                    size="sm"
                                                    onClick={() => handleSave(entry.id)}
                                                    disabled={saving}
                                                    className="h-7 text-xs"
                                                >
                                                    <Save className="h-3.5 w-3.5 mr-1" />
                                                    {saving ? "Saving…" : "Save"}
                                                </Button>
                                                <Button
                                                    size="sm"
                                                    variant="ghost"
                                                    onClick={() => setEditingId(null)}
                                                    className="h-7 text-xs"
                                                >
                                                    <X className="h-3.5 w-3.5 mr-1" /> Cancel
                                                </Button>
                                            </div>
                                        </div>
                                    ) : (
                                        <p className="text-sm line-clamp-3" title={entry.answer_text}>
                                            {entry.answer_text || "—"}
                                        </p>
                                    )}
                                </TableCell>
                                <TableCell className="align-top">
                                    {confidenceBadge(entry.confidence)}
                                </TableCell>
                                <TableCell className="align-top text-xs text-muted-foreground">
                                    {fmtDate(entry.created_at)}
                                </TableCell>
                                <TableCell className="align-top text-right">
                                    <div className="flex justify-end gap-1">
                                        {editingId !== entry.id && (
                                            <Button
                                                size="icon"
                                                variant="ghost"
                                                className="h-7 w-7"
                                                title="Edit answer"
                                                onClick={() => handleEdit(entry)}
                                            >
                                                <Edit className="h-3.5 w-3.5" />
                                            </Button>
                                        )}
                                        {canDelete && (
                                            <Button
                                                size="icon"
                                                variant="ghost"
                                                className="h-7 w-7 text-destructive hover:text-destructive"
                                                title="Delete (admin only)"
                                                onClick={() => handleDelete(entry.id)}
                                            >
                                                <Trash2 className="h-3.5 w-3.5" />
                                            </Button>
                                        )}
                                    </div>
                                </TableCell>
                            </TableRow>
                        ))}
                    </TableBody>
                </Table>
            </div>
        </div>
    );
}

// ── Usage Matches Tab ─────────────────────────────────────────────────────────

function MatchesTab({ orgId, token }: { orgId: string; token: string }) {
    const [matches, setMatches] = useState<any[]>([]);
    const [loading, setLoading] = useState(true);
    const { toast } = useToast();

    const load = useCallback(async () => {
        setLoading(true);
        try {
            const data = await ApiClient.listMemoryMatches(orgId, token);
            setMatches(data);
        } catch (e: any) {
            toast({ title: "Failed to load matches", description: e.message, variant: "destructive" });
        } finally {
            setLoading(false);
        }
    }, [orgId, token, toast]);

    useEffect(() => { load(); }, [load]);

    if (loading) {
        return (
            <div className="flex justify-center py-10">
                <Loader2 className="h-7 w-7 animate-spin text-muted-foreground" />
            </div>
        );
    }

    if (matches.length === 0) {
        return (
            <div className="flex flex-col items-center gap-3 py-12 text-center text-muted-foreground">
                <History className="h-10 w-10 opacity-30" />
                <p className="text-sm">No memory matches recorded yet.</p>
                <p className="text-xs max-w-xs">
                    Matches are logged automatically when the pipeline reuses a knowledge memory answer in a run.
                </p>
            </div>
        );
    }

    return (
        <div className="space-y-3">
            <div className="flex items-center justify-between">
                <p className="text-sm text-muted-foreground">{matches.length} usage records</p>
                <Button size="sm" variant="ghost" onClick={load} className="gap-1.5 text-xs">
                    <RefreshCw className="h-3.5 w-3.5" /> Refresh
                </Button>
            </div>
            <div className="rounded-lg border overflow-hidden">
                <Table>
                    <TableHeader>
                        <TableRow>
                            <TableHead>Question matched</TableHead>
                            <TableHead>Similarity</TableHead>
                            <TableHead>Used in run</TableHead>
                            <TableHead>Date</TableHead>
                        </TableRow>
                    </TableHeader>
                    <TableBody>
                        {matches.map((m) => (
                            <TableRow key={m.id}>
                                <TableCell className="text-sm max-w-xs truncate" title={m.question_text}>
                                    {m.question_text || "—"}
                                </TableCell>
                                <TableCell>
                                    <Badge variant="secondary">
                                        {m.similarity_score != null
                                            ? `${Math.round(m.similarity_score * 100)}%`
                                            : "—"}
                                    </Badge>
                                </TableCell>
                                <TableCell className="text-xs font-mono text-muted-foreground">
                                    {m.used_in_run ? m.used_in_run.slice(0, 8) + "…" : "—"}
                                </TableCell>
                                <TableCell className="text-xs text-muted-foreground">
                                    {fmtDate(m.created_at)}
                                </TableCell>
                            </TableRow>
                        ))}
                    </TableBody>
                </Table>
            </div>
        </div>
    );
}

// ── Main Panel ────────────────────────────────────────────────────────────────

export function MemoryGovPanel() {
    const [orgId] = useState<string | null>(getStoredOrgId());
    const [token, setToken] = useState<string | null>(null);
    const [tokenLoading, setTokenLoading] = useState(true);
    const supabase = createClient();
    const rbac = useRBAC(orgId);

    useEffect(() => {
        (async () => {
            try {
                const { data: { session } } = await supabase.auth.getSession();
                setToken(session?.access_token ?? null);
            } finally {
                setTokenLoading(false);
            }
        })();
    // eslint-disable-next-line react-hooks/exhaustive-deps
    }, []);

    if (tokenLoading) {
        return (
            <div className="flex justify-center p-8">
                <Loader2 className="h-8 w-8 animate-spin text-muted-foreground" />
            </div>
        );
    }

    if (!orgId || !token) {
        return (
            <div className="flex items-center gap-2 rounded-lg border border-amber-200 bg-amber-50 px-4 py-3 text-sm text-amber-800">
                <AlertTriangle className="h-4 w-4 shrink-0" />
                Could not load your organization. Please refresh.
            </div>
        );
    }

    const canDelete = rbac.role === "owner" || rbac.role === "admin";

    return (
        <Card>
            <CardHeader>
                <CardTitle className="flex items-center gap-2">
                    <Brain className="h-5 w-5 text-purple-600" />
                    Knowledge Memory
                </CardTitle>
                <CardDescription>
                    Vector-indexed answers reused across questionnaires. Entries are saved from approved audit answers and searched automatically during every run (≥ 85% similarity).
                </CardDescription>
            </CardHeader>
            <CardContent>
                <Tabs defaultValue="entries">
                    <TabsList className="mb-4">
                        <TabsTrigger value="entries">Memory Entries</TabsTrigger>
                        <TabsTrigger value="matches">Usage Matches</TabsTrigger>
                    </TabsList>
                    <TabsContent value="entries">
                        <EntriesTab orgId={orgId} token={token} canDelete={canDelete} />
                    </TabsContent>
                    <TabsContent value="matches">
                        <MatchesTab orgId={orgId} token={token} />
                    </TabsContent>
                </Tabs>
            </CardContent>
        </Card>
    );
}

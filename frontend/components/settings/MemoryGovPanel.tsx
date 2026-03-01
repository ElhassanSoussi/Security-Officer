import React, { useState, useEffect } from "react";
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from "@/components/ui/card";
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { useToast } from "@/components/ui/toaster";
import { createClient } from "@/utils/supabase/client";
import { getStoredOrgId } from "@/lib/orgContext";
import { Loader2, Trash2, Edit, Save, X, Ban, CheckCircle2 } from "lucide-react";
import { Input } from "@/components/ui/input";
import { config } from "@/lib/config";

const API_BASE = config.apiUrl;

export function MemoryGovPanel() {
    const [answers, setAnswers] = useState<any[]>([]);
    const [loading, setLoading] = useState(true);
    const [orgId] = useState<string | null>(getStoredOrgId());
    const [editingId, setEditingId] = useState<string | null>(null);
    const [editValue, setEditValue] = useState("");
    const { toast } = useToast();
    const supabase = createClient();

    const loadData = React.useCallback(async () => {
        if (!orgId) return;
        setLoading(true);
        try {
            const { data: { session } } = await supabase.auth.getSession();
            if (!session) return;
            const t = session.access_token;
            const res = await fetch(`${API_BASE}/runs/institutional-answers?org_id=${orgId}`, {
                headers: { "Authorization": `Bearer ${t}` }
            });
            if (res.ok) {
                const data = await res.json();
                setAnswers(data);
            }
        } catch (e) {
            console.error("Failed to load memory:", e);
        } finally {
            setLoading(false);
        }
    }, [orgId, supabase.auth]);

    useEffect(() => {
        loadData();
    }, [loadData]);

    async function handleDelete(id: string) {
        if (!confirm("Are you sure you want to delete this canonical answer?")) return;
        try {
            const { data: { session } } = await supabase.auth.getSession();
            if (!session) return;
            const t = session.access_token;
            const res = await fetch(`${API_BASE}/runs/institutional-answers/${id}`, {
                method: "DELETE",
                headers: { "Authorization": `Bearer ${t}` }
            });
            if (res.ok) {
                toast({ title: "Deleted", description: "Memory entry removed." });
                loadData();
            } else {
                toast({ title: "Error", description: "Failed to delete entry or insufficient permissions.", variant: "destructive" });
            }
        } catch {
            toast({ title: "Error", description: "Could not connect to server.", variant: "destructive" });
        }
    }

    async function toggleActive(id: string, currentActive: boolean) {
        try {
            const { data: { session } } = await supabase.auth.getSession();
            if (!session) return;
            const t = session.access_token;
            const res = await fetch(`${API_BASE}/runs/institutional-answers/${id}`, {
                method: "PATCH",
                headers: { "Authorization": `Bearer ${t}`, "Content-Type": "application/json" },
                body: JSON.stringify({ is_active: !currentActive })
            });
            if (res.ok) {
                toast({ title: "Updated", description: `Memory entry ${!currentActive ? 'enabled' : 'disabled'}.` });
                loadData();
            } else {
                toast({ title: "Error", description: "Failed to update entry.", variant: "destructive" });
            }
        } catch {
            toast({ title: "Error", description: "Could not connect to server.", variant: "destructive" });
        }
    }

    async function saveEdit(id: string) {
        try {
            const { data: { session } } = await supabase.auth.getSession();
            if (!session) return;
            const t = session.access_token;
            const res = await fetch(`${API_BASE}/runs/institutional-answers/${id}`, {
                method: "PATCH",
                headers: { "Authorization": `Bearer ${t}`, "Content-Type": "application/json" },
                body: JSON.stringify({ canonical_answer: editValue })
            });
            if (res.ok) {
                toast({ title: "Saved", description: "Memory answer updated successfully." });
                setEditingId(null);
                loadData();
            } else {
                toast({ title: "Error", description: "Failed to update answer.", variant: "destructive" });
            }
        } catch {
            toast({ title: "Error", description: "Could not connect to server.", variant: "destructive" });
        }
    }

    if (loading) {
        return (
            <div className="flex justify-center p-8">
                <Loader2 className="h-8 w-8 animate-spin text-muted-foreground" />
            </div>
        );
    }

    return (
        <Card>
            <CardHeader>
                <CardTitle>Institutional Memory</CardTitle>
                <CardDescription>
                    Manage canonical answers, view source references, and control what is active for reuse.
                </CardDescription>
            </CardHeader>
            <CardContent>
                {answers.length === 0 ? (
                    <div className="text-center py-8 text-muted-foreground">
                        No canonical answers found in institutional memory.
                    </div>
                ) : (
                    <Table>
                        <TableHeader>
                            <TableRow>
                                <TableHead className="w-[30%]">Question / Source</TableHead>
                                <TableHead className="w-[40%]">Canonical Answer</TableHead>
                                <TableHead>Status</TableHead>
                                <TableHead className="text-right">Actions</TableHead>
                            </TableRow>
                        </TableHeader>
                        <TableBody>
                            {answers.map(ans => (
                                <TableRow key={ans.id}>
                                    <TableCell className="align-top">
                                        <div className="font-medium text-sm line-clamp-2" title={ans.original_question || "Unknown Question"}>
                                            {ans.original_question || "Unknown Question"}
                                        </div>
                                        <div className="text-xs text-muted-foreground mt-1 truncate max-w-xs" title={ans.source_doc_name || "Unknown Document"}>
                                            Doc: {ans.source_doc_name || "Unknown Document"}
                                        </div>
                                    </TableCell>
                                    <TableCell className="align-top">
                                        {editingId === ans.id ? (
                                            <div className="flex gap-2">
                                                <Input 
                                                    value={editValue} 
                                                    onChange={e => setEditValue(e.target.value)} 
                                                    className="w-full h-auto text-sm py-2"
                                                />
                                                <div className="flex flex-col gap-1">
                                                    <Button size="icon" variant="ghost" onClick={() => saveEdit(ans.id)} title="Save">
                                                        <Save className="h-4 w-4 text-green-600" />
                                                    </Button>
                                                    <Button size="icon" variant="ghost" onClick={() => setEditingId(null)} title="Cancel">
                                                        <X className="h-4 w-4" />
                                                    </Button>
                                                </div>
                                            </div>
                                        ) : (
                                            <div className="text-sm">
                                                <p className="line-clamp-3" title={ans.canonical_answer}>{ans.canonical_answer}</p>
                                                <div className="flex items-center gap-2 mt-2">
                                                    <Badge variant="outline" className="text-xs">Conf: {ans.confidence_level || 0}%</Badge>
                                                    {ans.edited_by && <Badge variant="secondary" className="text-xs">Edited</Badge>}
                                                </div>
                                            </div>
                                        )}
                                    </TableCell>
                                    <TableCell className="align-top">
                                        {ans.is_active !== false ? (
                                            <Badge variant="default" className="bg-green-600">Active</Badge>
                                        ) : (
                                            <Badge variant="secondary">Disabled</Badge>
                                        )}
                                    </TableCell>
                                    <TableCell className="text-right align-top">
                                        <div className="flex justify-end gap-1">
                                            {editingId !== ans.id && (
                                                <Button size="icon" variant="ghost" onClick={() => {
                                                    setEditingId(ans.id);
                                                    setEditValue(ans.canonical_answer);
                                                }} title="Edit Answer">
                                                    <Edit className="h-4 w-4" />
                                                </Button>
                                            )}
                                            <Button size="icon" variant="ghost" onClick={() => toggleActive(ans.id, ans.is_active !== false)} title={ans.is_active !== false ? "Disable" : "Enable"}>
                                                {ans.is_active !== false ? <Ban className="h-4 w-4 text-orange-500" /> : <CheckCircle2 className="h-4 w-4 text-green-500" />}
                                            </Button>
                                            <Button size="icon" variant="ghost" onClick={() => handleDelete(ans.id)} title="Delete (Admin Only)">
                                                <Trash2 className="h-4 w-4 text-destructive" />
                                            </Button>
                                        </div>
                                    </TableCell>
                                </TableRow>
                            ))}
                        </TableBody>
                    </Table>
                )}
            </CardContent>
        </Card>
    );
}

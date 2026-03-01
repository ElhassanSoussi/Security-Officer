"use client";

import React, { useEffect, useState, useCallback } from "react";
import PageHeader from "@/components/ui/PageHeader";
import { Card, CardContent } from "@/components/ui/card";
import { createClient } from "@/utils/supabase/client";
import { getStoredOrgId } from "@/lib/orgContext";
import { Loader2, Calendar, Filter, Activity, Shield, Layers, FileText } from "lucide-react";
import { Select } from "@/components/ui/select";
import { Badge } from "@/components/ui/badge";
import { config } from "@/lib/config";

export default function ActivityPage() {
    const [activities, setActivities] = useState<any[]>([]);
    const [loading, setLoading] = useState(true);
    const [orgId] = useState<string | null>(getStoredOrgId());
    const [filter, setFilter] = useState<string>("all");
    const supabase = createClient();

    const loadData = useCallback(async () => {
        if (!orgId) return;
        setLoading(true);
        try {
            const { data: { session } } = await supabase.auth.getSession();
            if (!session) return;
            const t = session.access_token;
            let url = `${config.apiUrl}/runs/activity?org_id=${orgId}&limit=100`;
            if (filter !== "all") {
                url += `&filter_type=${encodeURIComponent(filter)}`;
            }
            const res = await fetch(url, { headers: { "Authorization": `Bearer ${t}` } });
            if (res.ok) {
                const data = await res.json();
                setActivities(data);
            }
        } catch (e) {
            console.error("Failed to load activity:", e);
        } finally {
            setLoading(false);
        }
    }, [orgId, filter, supabase.auth]);

    useEffect(() => {
        loadData();
    }, [loadData]);

    function formatDate(iso: string | null | undefined): string {
        if (!iso) return "Unknown date";
        try {
            return new Date(iso).toLocaleString(undefined, {
                year: "numeric", month: "short", day: "numeric",
                hour: "numeric", minute: "2-digit",
            });
        } catch {
            return iso;
        }
    }

    function formatAction(action: string) {
        return action.replace(/_/g, " ").replace(/\b\w/g, l => l.toUpperCase());
    }

    function getIconForAction(action: string) {
        if (action.includes("run") || action.includes("process")) return <Activity className="h-4 w-4" />;
        if (action.includes("memory") || action.includes("answer")) return <Layers className="h-4 w-4" />;
        if (action.includes("export") || action.includes("document")) return <FileText className="h-4 w-4" />;
        return <Shield className="h-4 w-4" />;
    }

    const filterControl = (
        <div className="flex items-center gap-2">
            <Filter className="h-4 w-4 text-muted-foreground hidden md:block" />
            <Select
                value={filter}
                onChange={e => setFilter(e.target.value)}
                className="w-[180px]"
            >
                <option value="all">All Events</option>
                <option value="document_uploaded">Document Added</option>
                <option value="process_completed">Run Completed</option>
                <option value="audit_approved">Audit Approved</option>
                <option value="audit_rejected">Audit Rejected</option>
                <option value="memory_edited">Memory Edited</option>
                <option value="memory_deleted">Memory Deleted</option>
                <option value="memory_promoted">Memory Promoted</option>
                <option value="export_downloaded">Export Downloaded</option>
                <option value="project_created">Project Created</option>
            </Select>
        </div>
    );

    return (
        <div className="flex flex-col h-full bg-background min-h-screen pb-12">
            <PageHeader
                title="Activity Timeline"
                subtitle="Compliance and system events organization-wide"
                actions={filterControl}
            />

            <div className="px-4 md:px-8 mt-2 max-w-5xl mx-auto w-full">
                <Card>
                    <CardContent className="p-0">
                        {loading ? (
                            <div className="p-12 flex justify-center py-20">
                                <Loader2 className="h-8 w-8 animate-spin text-muted-foreground" />
                            </div>
                        ) : activities.length === 0 ? (
                            <div className="p-12 text-center text-muted-foreground">
                                No activity recorded yet.
                            </div>
                        ) : (
                            <div className="divide-y divide-border">
                                {activities.map((act) => (
                                    <div key={act.id} className="p-4 sm:p-6 hover:bg-muted/50 transition-colors flex items-start gap-4">
                                        <div className="mt-1 bg-primary/10 text-primary p-2 rounded-full shrink-0">
                                            {getIconForAction(act.action_type || "")}
                                        </div>
                                        <div className="flex-1 min-w-0">
                                            <div className="flex flex-col sm:flex-row justify-between sm:items-center gap-1 mb-1">
                                                <h4 className="font-semibold text-foreground truncate">
                                                    {formatAction(act.action_type || "Unknown Activity")}
                                                </h4>
                                                <span className="text-xs text-muted-foreground whitespace-nowrap flex items-center gap-1 shrink-0">
                                                    <Calendar className="h-3 w-3" />
                                                    {formatDate(act.created_at)}
                                                </span>
                                            </div>
                                            <p className="text-sm text-muted-foreground mb-2">
                                                {act.description
                                                    || act.metadata?.description
                                                    || `Action on ${act.entity_type || "entity"}${act.entity_id ? ` ${(act.entity_id as string).substring(0, 8)}` : ""}`}
                                            </p>

                                            {act.metadata && Object.keys(act.metadata).length > 0 && !act.metadata.description && (
                                                <div className="mt-2 text-xs bg-muted/50 p-2 rounded border border-border inline-block break-all max-w-full overflow-hidden">
                                                    <code>{JSON.stringify(act.metadata).slice(0, 120)}{JSON.stringify(act.metadata).length > 120 ? "…" : ""}</code>
                                                </div>
                                            )}

                                            <div className="mt-2 flex flex-wrap gap-2">
                                                {act.entity_type && (
                                                    <Badge variant="outline" className="text-[10px] uppercase tracking-wide">
                                                        {act.entity_type}
                                                    </Badge>
                                                )}
                                                {act.user_id && (
                                                    <Badge variant="secondary" className="text-[10px]">
                                                        User: {(act.user_id as string).substring(0, 8)}…
                                                    </Badge>
                                                )}
                                            </div>
                                        </div>
                                    </div>
                                ))}
                            </div>
                        )}
                    </CardContent>
                </Card>
            </div>
        </div>
    );
}

"use client";

import * as React from "react";
import Link from "next/link";
import { CheckCircle, AlertCircle, PlayCircle, Clock, Download, FileText, Edit3, Shield } from "lucide-react";
import { cn } from "@/lib/utils";

export interface ActivityItem {
    id: string;
    event_type: string;
    description: string;
    created_at: string;
    user_name?: string;
    user_id?: string;
    project_name?: string;
    project_id?: string;
    org_id?: string;
    run_id?: string;
    metadata?: Record<string, any>;
}

function getEventIcon(eventType: string) {
    if (eventType.includes("fail") || eventType.includes("error"))
        return { icon: AlertCircle, bg: "bg-red-100", fg: "text-red-600" };
    if (eventType.includes("complete") || eventType.includes("approved"))
        return { icon: CheckCircle, bg: "bg-green-100", fg: "text-green-600" };
    if (eventType.includes("export") || eventType.includes("download"))
        return { icon: Download, bg: "bg-emerald-100", fg: "text-emerald-600" };
    if (eventType.includes("review") || eventType.includes("override"))
        return { icon: Shield, bg: "bg-purple-100", fg: "text-purple-600" };
    if (eventType.includes("edit"))
        return { icon: Edit3, bg: "bg-amber-100", fg: "text-amber-600" };
    if (eventType.includes("upload") || eventType.includes("document"))
        return { icon: FileText, bg: "bg-indigo-100", fg: "text-indigo-600" };
    return { icon: PlayCircle, bg: "bg-blue-100", fg: "text-blue-600" };
}

function formatRelativeTime(dateStr: string): string {
    const now = new Date();
    const date = new Date(dateStr);
    const diffMs = now.getTime() - date.getTime();
    const diffMin = Math.floor(diffMs / 60000);
    if (diffMin < 1) return "Just now";
    if (diffMin < 60) return `${diffMin}m ago`;
    const diffHr = Math.floor(diffMin / 60);
    if (diffHr < 24) return `${diffHr}h ago`;
    const diffDays = Math.floor(diffHr / 24);
    if (diffDays < 7) return `${diffDays}d ago`;
    return date.toLocaleDateString();
}

export interface ActivityTimelineProps {
    activities: ActivityItem[];
    loading?: boolean;
    maxItems?: number;
    showUserAttribution?: boolean;
    className?: string;
}

export function ActivityTimeline({
    activities,
    loading = false,
    maxItems,
    showUserAttribution = true,
    className,
}: ActivityTimelineProps) {
    const items = maxItems ? activities.slice(0, maxItems) : activities;

    if (loading) {
        return (
            <div className={cn("space-y-3", className)}>
                {[1, 2, 3].map((i) => (
                    <div key={i} className="flex items-start gap-3 animate-pulse">
                        <div className="h-8 w-8 rounded-full bg-muted shrink-0" />
                        <div className="flex-1 space-y-1.5">
                            <div className="h-4 w-3/4 bg-muted rounded" />
                            <div className="h-3 w-1/2 bg-muted/60 rounded" />
                        </div>
                    </div>
                ))}
            </div>
        );
    }

    if (items.length === 0) return null;

    return (
        <div className={cn("relative", className)}>
            {/* Vertical line */}
            <div className="absolute left-[15px] top-4 bottom-4 w-px bg-border" />
            <div className="space-y-4">
                {items.map((act) => {
                    const { icon: Icon, bg, fg } = getEventIcon(act.event_type);
                    let linkTarget: string | null = null;
                    if (act.run_id) linkTarget = `/runs/${act.run_id}`;
                    else if (act.project_name && act.org_id)
                        linkTarget = `/projects/${act.org_id}/${act.project_name}`;

                    return (
                        <div key={act.id} className="relative flex items-start gap-3 pl-0">
                            <div className={`relative z-10 flex h-8 w-8 shrink-0 items-center justify-center rounded-full ${bg}`}>
                                <Icon className={`h-3.5 w-3.5 ${fg}`} />
                            </div>
                            <div className="flex-1 min-w-0 pt-0.5">
                                <div className="flex items-start justify-between gap-2">
                                    <div className="min-w-0">
                                        {linkTarget ? (
                                            <Link
                                                href={linkTarget}
                                                className="text-sm font-medium text-foreground hover:text-primary hover:underline truncate block"
                                            >
                                                {act.description || act.event_type}
                                            </Link>
                                        ) : (
                                            <p className="text-sm font-medium text-foreground truncate">
                                                {act.description || act.event_type}
                                            </p>
                                        )}
                                        <div className="flex items-center gap-2 mt-0.5">
                                            {showUserAttribution && act.user_name && (
                                                <span className="text-xs text-muted-foreground">
                                                    by {act.user_name}
                                                </span>
                                            )}
                                            {act.project_name && (
                                                <span className="text-xs text-muted-foreground">
                                                    {showUserAttribution && act.user_name ? "· " : ""}
                                                    {act.project_name}
                                                </span>
                                            )}
                                        </div>
                                    </div>
                                    <span className="flex shrink-0 items-center gap-1 text-xs text-muted-foreground whitespace-nowrap">
                                        <Clock className="h-3 w-3" />
                                        {formatRelativeTime(act.created_at)}
                                    </span>
                                </div>
                            </div>
                        </div>
                    );
                })}
            </div>
        </div>
    );
}

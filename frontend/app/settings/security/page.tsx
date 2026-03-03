"use client";

import { useEffect, useState } from "react";
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { useToast } from "@/components/ui/toaster";
import { createClient } from "@/utils/supabase/client";
import { getStoredOrgId } from "@/lib/orgContext";
import { ApiClient } from "@/lib/api";
import { ShieldCheck, Shield, Lock, Info, ExternalLink, Download } from "lucide-react";
import Link from "next/link";

export default function SecurityPage() {
    const [orgId] = useState<string | null>(getStoredOrgId());
    const [canManageOrg, setCanManageOrg] = useState(false);
    const { toast } = useToast();
    const supabase = createClient();

    useEffect(() => {
        async function checkRole() {
            if (!orgId) return;
            try {
                const { data: { session } } = await supabase.auth.getSession();
                if (!session) return;
                const org = await ApiClient.getOrgSettings(orgId, session.access_token);
                const role = String(org?.my_role || "").toLowerCase();
                setCanManageOrg(["owner", "admin"].includes(role));
            } catch {
                // Fail silently — non-admins won't see audit report
            }
        }
        checkRole();
        // eslint-disable-next-line react-hooks/exhaustive-deps
    }, [orgId]);

    return (
        <div className="space-y-6 max-w-3xl">
            <Card>
                <CardHeader>
                    <CardTitle className="flex items-center gap-2 text-base">
                        <ShieldCheck className="h-4 w-4 text-primary" /> Security &amp; Compliance
                    </CardTitle>
                    <CardDescription>
                        How NYC Compliance Architect protects your data and maintains regulatory alignment.
                    </CardDescription>
                </CardHeader>
                <CardContent className="space-y-5">
                    <div className="grid gap-4 md:grid-cols-2">
                        <div className="rounded-lg border bg-muted/30 p-4 space-y-1.5">
                            <div className="flex items-center gap-2">
                                <Lock className="h-4 w-4 text-muted-foreground" />
                                <h4 className="text-sm font-semibold text-foreground">Data Encryption</h4>
                            </div>
                            <p className="text-xs text-muted-foreground leading-relaxed">
                                All data is encrypted in transit (TLS 1.2+) and at rest via Supabase-managed AES-256 encryption.
                            </p>
                        </div>
                        <div className="rounded-lg border bg-muted/30 p-4 space-y-1.5">
                            <div className="flex items-center gap-2">
                                <Shield className="h-4 w-4 text-muted-foreground" />
                                <h4 className="text-sm font-semibold text-foreground">Role-Based Access</h4>
                            </div>
                            <p className="text-xs text-muted-foreground leading-relaxed">
                                Row-level security policies enforce organization boundaries. Members can only access their own org data.
                            </p>
                        </div>
                        <div className="rounded-lg border bg-muted/30 p-4 space-y-1.5">
                            <div className="flex items-center gap-2">
                                <ShieldCheck className="h-4 w-4 text-muted-foreground" />
                                <h4 className="text-sm font-semibold text-foreground">Audit Trail</h4>
                            </div>
                            <p className="text-xs text-muted-foreground leading-relaxed">
                                Every AI-generated answer, manual edit, review decision, and export is logged with timestamps and user IDs.
                            </p>
                        </div>
                        <div className="rounded-lg border bg-muted/30 p-4 space-y-1.5">
                            <div className="flex items-center gap-2">
                                <Info className="h-4 w-4 text-muted-foreground" />
                                <h4 className="text-sm font-semibold text-foreground">Source Transparency</h4>
                            </div>
                            <p className="text-xs text-muted-foreground leading-relaxed">
                                Each answer includes the source document, page reference, and confidence score for full traceability.
                            </p>
                        </div>
                    </div>
                    <div className="rounded-lg border border-blue-100 bg-blue-50/50 p-4 text-xs text-blue-800 leading-relaxed">
                        <strong>Compliance note:</strong> NYC Compliance Architect is designed to align with SOC 2 Type II controls
                        for data handling, access management, and audit logging. Contact your administrator for your organization&apos;s
                        specific compliance documentation.
                    </div>
                    <div className="pt-1">
                        <Link href="/security" className="inline-flex items-center gap-1.5 text-sm font-medium text-primary hover:underline">
                            <ExternalLink className="h-3.5 w-3.5" /> View full Security &amp; Data Practices →
                        </Link>
                    </div>
                </CardContent>
            </Card>

            {/* Access Audit Report */}
            {canManageOrg && orgId && (
                <Card>
                    <CardHeader>
                        <CardTitle className="flex items-center gap-2 text-base">
                            <Download className="h-4 w-4 text-primary" /> Access Audit Report
                        </CardTitle>
                        <CardDescription>
                            Download a SOC2-ready report of all users, roles, and activity for this organization.
                        </CardDescription>
                    </CardHeader>
                    <CardContent className="space-y-3">
                        <div className="flex flex-wrap gap-3">
                            <Button
                                size="sm"
                                variant="outline"
                                className="gap-2"
                                onClick={async () => {
                                    try {
                                        const { data: { session } } = await supabase.auth.getSession();
                                        await ApiClient.downloadAccessReportCSV(orgId!, session?.access_token);
                                        toast({ title: "Access report downloaded", variant: "success" });
                                    } catch (e: any) {
                                        toast({ title: "Download failed", description: e.message, variant: "destructive" });
                                    }
                                }}
                            >
                                <Download className="h-4 w-4" /> Download CSV
                            </Button>
                            <Button
                                size="sm"
                                variant="outline"
                                className="gap-2"
                                onClick={async () => {
                                    try {
                                        const { data: { session } } = await supabase.auth.getSession();
                                        const report = await ApiClient.getAccessReport(orgId!, session?.access_token);
                                        const blob = new Blob([JSON.stringify(report, null, 2)], { type: "application/json" });
                                        const url = window.URL.createObjectURL(blob);
                                        const a = document.createElement("a");
                                        a.href = url;
                                        a.download = `access_report_${orgId!.slice(0, 8)}.json`;
                                        document.body.appendChild(a);
                                        a.click();
                                        window.URL.revokeObjectURL(url);
                                        document.body.removeChild(a);
                                        toast({ title: "Access report downloaded", variant: "success" });
                                    } catch (e: any) {
                                        toast({ title: "Download failed", description: e.message, variant: "destructive" });
                                    }
                                }}
                            >
                                <Download className="h-4 w-4" /> Download JSON
                            </Button>
                        </div>
                        <p className="text-xs text-muted-foreground">
                            Includes: user roles, member-since dates, last activity timestamps, activity counts, and evidence export counts.
                        </p>
                    </CardContent>
                </Card>
            )}

            {/* About */}
            <Card>
                <CardHeader>
                    <CardTitle className="flex items-center gap-2 text-base">
                        <Info className="h-4 w-4 text-muted-foreground" /> About
                    </CardTitle>
                </CardHeader>
                <CardContent className="space-y-3 text-sm">
                    <div className="flex justify-between">
                        <span className="text-muted-foreground">Product</span>
                        <span className="font-medium">NYC Compliance Architect</span>
                    </div>
                    <div className="flex justify-between">
                        <span className="text-muted-foreground">Version</span>
                        <span className="font-mono text-xs">1.0.0</span>
                    </div>
                    <div className="flex justify-between">
                        <span className="text-muted-foreground">Environment</span>
                        <span className="font-mono text-xs">{process.env.NODE_ENV === "production" ? "Production" : "Development"}</span>
                    </div>
                    {orgId && (
                        <div className="flex justify-between">
                            <span className="text-muted-foreground">Organization ID</span>
                            <span className="font-mono text-xs">{orgId.slice(0, 12)}…</span>
                        </div>
                    )}
                    <p className="text-xs text-muted-foreground pt-2 border-t">
                        AI-powered security questionnaire automation for NYC construction compliance.
                        Built for SCA, MTA, and PASSPort submissions.
                    </p>
                </CardContent>
            </Card>
        </div>
    );
}

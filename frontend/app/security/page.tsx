"use client";

import { Card, CardContent, CardHeader, CardTitle, CardDescription } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import {
    ShieldCheck, Lock, Eye, FileCheck2, Server, Clock, Brain, ArrowLeft, CheckCircle2, ExternalLink,
    KeyRound, Users,
} from "lucide-react";
import Link from "next/link";
import PageHeader from "@/components/ui/PageHeader";

const PRACTICES = [
    {
        icon: Server,
        title: "Tenant Data Isolation",
        description:
            "Every organization's data is logically isolated using Supabase Row-Level Security (RLS) policies. API requests are scoped to authenticated sessions and verified against org membership before any data is returned.",
        details: [
            "RLS enforced at the database layer — not just application code",
            "Cross-org data access is impossible by design",
            "All API calls require a valid JWT scoped to the user's session",
        ],
    },
    {
        icon: Eye,
        title: "Comprehensive Audit Logging",
        description:
            "Every significant action — AI-generated answers, manual edits, reviewer approvals, exports, and role changes — is recorded with a timestamp, user ID, and contextual metadata.",
        details: [
            "Immutable audit trail for compliance reviews",
            "Events include: run_started, answer_generated, review_approved, export_downloaded",
            "Accessible via the Audit Log page and API",
            "DB-level triggers prevent deletion or modification of log entries",
        ],
    },
    {
        icon: FileCheck2,
        title: "Export Validation & Integrity",
        description:
            "Before any questionnaire export is finalized, the system validates answer completeness, flags low-confidence responses, and requires explicit user confirmation.",
        details: [
            "Pre-export readiness check with approval/rejection counts",
            "Low-confidence answers are surfaced for manual review",
            "Downloaded files include metadata headers for traceability",
        ],
    },
    {
        icon: Brain,
        title: "No Training on Customer Data",
        description:
            "Your documents and questionnaire answers are never used to train AI models. All AI inference uses your data as context only within the scope of your request.",
        details: [
            "Documents are processed for retrieval-augmented generation (RAG) only",
            "No fine-tuning or model training on uploaded content",
            "Data is not shared across organizations or used for product improvement",
        ],
    },
    {
        icon: Lock,
        title: "Encryption & Transport Security",
        description:
            "All data is encrypted in transit using TLS 1.2+ and at rest via Supabase-managed AES-256 encryption. Authentication tokens use short-lived JWTs.",
        details: [
            "TLS 1.2+ enforced for all API and frontend connections",
            "AES-256 encryption at rest via Supabase storage layer",
            "JWT tokens with configurable expiration windows",
        ],
    },
    {
        icon: Clock,
        title: "Data Retention & Deletion",
        description:
            "Organizations retain full control over their data lifecycle. Configurable retention policies automatically soft-delete old runs while preserving the evidence vault.",
        details: [
            "Configurable DATA_RETENTION_DAYS policy (default: 365 days)",
            "Admin-only retention job endpoint for controlled cleanup",
            "Evidence vault records are never auto-purged",
            "Self-service deletion for projects, documents, and runs",
        ],
    },
    {
        icon: Users,
        title: "Role-Based Access Control",
        description:
            "Five-tier RBAC (Owner, Admin, Compliance Manager, Reviewer, Viewer) enforces least-privilege access. Every API endpoint checks permissions before executing.",
        details: [
            "Viewer: read-only access to projects, documents, and runs",
            "Reviewer: can approve/reject answers, bulk review, and export",
            "Compliance Manager: full project lifecycle + review",
            "Admin/Owner: all permissions including member management",
            "Access audit reports exportable as JSON or CSV",
        ],
    },
    {
        icon: KeyRound,
        title: "Authentication Hardening",
        description:
            "SOC2-aligned authentication controls including minimum password requirements, email verification enforcement, and inactive user blocking.",
        details: [
            "Minimum 10-character passwords with complexity requirements",
            "Email verification required for full platform access",
            "Inactive/banned user detection and blocking",
            "Session management via Supabase Auth with JWT rotation",
        ],
    },
];

export default function SecurityPage() {
    return (
        <div className="space-y-6">
            <PageHeader
                breadcrumbs={
                    <Link
                        href="/settings"
                        className="inline-flex items-center gap-1.5 text-sm text-muted-foreground hover:text-primary transition-colors"
                    >
                        <ArrowLeft className="h-4 w-4" /> Back to Settings
                    </Link>
                }
                title={
                    <span className="flex items-center gap-2">
                        <ShieldCheck className="h-6 w-6 text-primary" />
                        Security &amp; Data Practices
                    </span>
                }
                subtitle="How NYC Compliance Architect protects your organization's data and maintains regulatory alignment."
            />

            {/* Trust summary banner */}
            <Card className="border-primary/20 bg-gradient-to-br from-primary/5 to-background">
                <CardContent className="py-5">
                    <div className="flex flex-wrap items-center gap-x-6 gap-y-2 text-sm">
                        {[
                            "SOC 2 aligned controls",
                            "End-to-end encryption",
                            "Zero data training",
                            "Full audit trail",
                            "Tenant isolation",
                            "Immutable logs",
                            "RBAC enforced",
                        ].map((item) => (
                            <span key={item} className="inline-flex items-center gap-1.5 text-foreground">
                                <CheckCircle2 className="h-4 w-4 text-green-600 shrink-0" />
                                {item}
                            </span>
                        ))}
                    </div>
                </CardContent>
            </Card>

            {/* Practices grid */}
            <div className="grid gap-5 md:grid-cols-2">
                {PRACTICES.map((practice) => {
                    const Icon = practice.icon;
                    return (
                        <Card key={practice.title} className="flex flex-col">
                            <CardHeader className="pb-3">
                                <div className="flex items-center gap-2.5">
                                    <div className="flex h-9 w-9 items-center justify-center rounded-lg bg-primary/10">
                                        <Icon className="h-4.5 w-4.5 text-primary" />
                                    </div>
                                    <CardTitle className="text-base">{practice.title}</CardTitle>
                                </div>
                                <CardDescription className="mt-2 text-sm leading-relaxed">
                                    {practice.description}
                                </CardDescription>
                            </CardHeader>
                            <CardContent className="flex-1">
                                <ul className="space-y-1.5">
                                    {practice.details.map((detail) => (
                                        <li key={detail} className="flex items-start gap-2 text-xs text-muted-foreground leading-relaxed">
                                            <CheckCircle2 className="h-3.5 w-3.5 text-green-600 mt-0.5 shrink-0" />
                                            {detail}
                                        </li>
                                    ))}
                                </ul>
                            </CardContent>
                        </Card>
                    );
                })}
            </div>

            {/* Phase 21: Vendor & Third-Party Disclosure */}
            <Card>
                <CardHeader>
                    <CardTitle className="text-base">Vendor &amp; Third-Party Disclosures</CardTitle>
                    <CardDescription>
                        Transparency about external services used by NYC Compliance Architect.
                    </CardDescription>
                </CardHeader>
                <CardContent>
                    <div className="overflow-auto">
                        <table className="w-full text-sm">
                            <thead>
                                <tr className="border-b text-left">
                                    <th className="pb-2 pr-4 font-medium text-muted-foreground">Service</th>
                                    <th className="pb-2 pr-4 font-medium text-muted-foreground">Purpose</th>
                                    <th className="pb-2 font-medium text-muted-foreground">Data Shared</th>
                                </tr>
                            </thead>
                            <tbody className="divide-y">
                                <tr>
                                    <td className="py-2.5 pr-4 font-medium">Supabase</td>
                                    <td className="py-2.5 pr-4 text-muted-foreground">Database, Auth, Storage (RLS-enforced)</td>
                                    <td className="py-2.5 text-muted-foreground">All application data (encrypted at rest, AES-256)</td>
                                </tr>
                                <tr>
                                    <td className="py-2.5 pr-4 font-medium">OpenAI</td>
                                    <td className="py-2.5 pr-4 text-muted-foreground">AI answer generation &amp; embeddings</td>
                                    <td className="py-2.5 text-muted-foreground">Document chunks &amp; questions (not used for training)</td>
                                </tr>
                                <tr>
                                    <td className="py-2.5 pr-4 font-medium">Stripe</td>
                                    <td className="py-2.5 pr-4 text-muted-foreground">Subscription billing &amp; payments</td>
                                    <td className="py-2.5 text-muted-foreground">Org ID, plan tier, payment method (PCI-DSS compliant)</td>
                                </tr>
                                <tr>
                                    <td className="py-2.5 pr-4 font-medium">Sentry</td>
                                    <td className="py-2.5 pr-4 text-muted-foreground">Error monitoring &amp; performance</td>
                                    <td className="py-2.5 text-muted-foreground">Error traces, no PII (send_default_pii=False)</td>
                                </tr>
                                <tr>
                                    <td className="py-2.5 pr-4 font-medium">Vercel</td>
                                    <td className="py-2.5 pr-4 text-muted-foreground">Frontend hosting &amp; CDN</td>
                                    <td className="py-2.5 text-muted-foreground">Static assets &amp; server-side rendering only</td>
                                </tr>
                            </tbody>
                        </table>
                    </div>
                </CardContent>
            </Card>

            {/* Compliance note */}
            <Card>
                <CardContent className="py-5 space-y-3">
                    <div className="rounded-lg border border-blue-100 bg-blue-50/50 p-4 text-sm text-blue-800 leading-relaxed">
                        <strong>Compliance alignment:</strong> NYC Compliance Architect is designed to align with SOC 2 Type II
                        controls for data handling, access management, and audit logging. For your organization&apos;s specific
                        compliance documentation or a Data Processing Agreement (DPA), contact your account administrator.
                    </div>
                    <div className="flex flex-wrap gap-3">
                        <a href="mailto:security@nyccompliance.ai">
                            <Button variant="outline" size="sm" className="gap-2">
                                <ExternalLink className="h-3.5 w-3.5" /> Contact Security Team
                            </Button>
                        </a>
                        <a href="mailto:compliance@nyccompliance.ai">
                            <Button variant="outline" size="sm" className="gap-2">
                                <FileCheck2 className="h-3.5 w-3.5" /> Request DPA
                            </Button>
                        </a>
                    </div>
                </CardContent>
            </Card>
        </div>
    );
}

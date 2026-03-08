import {
    LayoutDashboard,
    ClipboardList,
    BarChart3,
    MessageSquare,
} from "lucide-react";

const SCREENS = [
    {
        icon: LayoutDashboard,
        title: "Project Dashboard",
        description:
            "Central view of all active compliance projects. Status, last-run date, confidence summary, and pending review items in one place.",
        badge: "Overview",
        accent: "from-blue-50 to-slate-50 border-blue-100",
        iconClass: "text-blue-600 bg-blue-100",
        preview: [
            { label: "SCA — Bid Package 12B", status: "In Review", pct: 87 },
            { label: "MTA Capital Q2 Submission", status: "Draft", pct: 62 },
            { label: "PASSPort Vendor Renewal", status: "Complete", pct: 100 },
        ],
    },
    {
        icon: ClipboardList,
        title: "Answer Review",
        description:
            "Each answer is scored by confidence. Reviewers see the source document excerpt alongside the AI-drafted answer. Approvals are logged with timestamp and user.",
        badge: "Review & Audit",
        accent: "from-emerald-50 to-slate-50 border-emerald-100",
        iconClass: "text-emerald-600 bg-emerald-100",
        preview: [
            { label: "Does the contractor maintain a written safety plan?", confidence: 96, source: "Safety Manual v3.2 · p.4" },
            { label: "Provide current Workers' Comp certificate.", confidence: 91, source: "WC Certificate 2026.pdf" },
            { label: "OSHA 30-hour training — all supervisors?", confidence: 74, source: "Training Records Q1 · p.12" },
        ],
    },
    {
        icon: BarChart3,
        title: "Usage & Limits",
        description:
            "Real-time view of questionnaire runs, document count, and storage consumption against your plan limits. No surprise overages.",
        badge: "Usage Dashboard",
        accent: "from-amber-50 to-slate-50 border-amber-100",
        iconClass: "text-amber-600 bg-amber-100",
        preview: [
            { label: "Projects", used: 3, limit: 5 },
            { label: "Documents", used: 18, limit: 25 },
            { label: "Runs this month", used: 6, limit: 10 },
        ],
    },
    {
        icon: MessageSquare,
        title: "Compliance Assistant",
        description:
            "Ask questions against your document vault. Get grounded answers with inline citations. Designed for fast lookups during bid prep, not open-ended chat.",
        badge: "Assistant",
        accent: "from-violet-50 to-slate-50 border-violet-100",
        iconClass: "text-violet-600 bg-violet-100",
        preview: [
            { q: "What does our safety manual say about confined space entry?", a: "Per Section 8.3 of Safety Manual v3.2, all confined space entries require…" },
        ],
    },
];

function ProgressBar({ pct }: { pct: number }) {
    const color = pct >= 90 ? "bg-red-400" : pct >= 70 ? "bg-amber-400" : "bg-emerald-500";
    return (
        <div className="h-1.5 w-full rounded-full bg-slate-200/80 overflow-hidden">
            <div className={`h-full rounded-full ${color}`} style={{ width: `${pct}%` }} />
        </div>
    );
}

function ConfidenceBadge({ pct }: { pct: number }) {
    const color = pct >= 90 ? "text-emerald-700 bg-emerald-50" : pct >= 75 ? "text-amber-700 bg-amber-50" : "text-red-700 bg-red-50";
    return (
        <span className={`inline-block rounded px-1.5 py-0.5 text-[10px] font-bold tabular-nums ${color}`}>
            {pct}%
        </span>
    );
}

export function ProductProofSection() {
    return (
        <section
            id="product"
            className="border-t border-border/50 bg-muted/20"
            data-testid="marketing-product-proof"
        >
            <div className="max-w-6xl mx-auto px-6 py-16 md:py-20">
                <div className="max-w-2xl mx-auto text-center mb-12">
                    <p className="text-sm font-semibold uppercase tracking-wider text-muted-foreground mb-3">
                        Inside the platform
                    </p>
                    <h2 className="text-3xl font-bold tracking-tight text-foreground">
                        Built for compliance operations, not generic document Q&amp;A
                    </h2>
                    <p className="mt-3 text-muted-foreground leading-relaxed">
                        Every screen is designed around the workflow compliance officers
                        actually run — from document ingestion through approved submission.
                    </p>
                </div>

                <div className="grid gap-6 md:grid-cols-2">
                    {SCREENS.map((screen) => {
                        const Icon = screen.icon;
                        return (
                            <div
                                key={screen.title}
                                className={`rounded-xl border bg-gradient-to-br ${screen.accent} overflow-hidden`}
                            >
                                {/* Card header */}
                                <div className="flex items-center gap-3 px-5 py-4 border-b border-current/10 bg-white/60">
                                    <div className={`flex h-8 w-8 items-center justify-center rounded-lg ${screen.iconClass}`}>
                                        <Icon className="h-4 w-4" />
                                    </div>
                                    <div>
                                        <p className="text-sm font-semibold text-foreground">{screen.title}</p>
                                        <span className="text-[10px] font-semibold uppercase tracking-wider text-muted-foreground">
                                            {screen.badge}
                                        </span>
                                    </div>
                                </div>

                                {/* Description */}
                                <div className="px-5 pt-3 pb-2">
                                    <p className="text-sm text-muted-foreground leading-relaxed">
                                        {screen.description}
                                    </p>
                                </div>

                                {/* Preview rows */}
                                <div className="px-5 pb-5 mt-2 space-y-2">
                                    {/* Project dashboard preview */}
                                    {"status" in (screen.preview[0] ?? {}) && screen.preview.map((row: any) => (
                                        <div
                                            key={row.label}
                                            className="flex items-center justify-between gap-3 rounded-lg border border-white/70 bg-white/80 px-3 py-2"
                                        >
                                            <span className="text-xs font-medium text-foreground truncate max-w-[60%]">
                                                {row.label}
                                            </span>
                                            <div className="flex items-center gap-2 shrink-0">
                                                <ProgressBar pct={row.pct} />
                                                <span className={`text-[10px] font-semibold px-1.5 py-0.5 rounded ${
                                                    row.status === "Complete" ? "bg-emerald-100 text-emerald-700"
                                                    : row.status === "In Review" ? "bg-amber-100 text-amber-700"
                                                    : "bg-slate-100 text-slate-600"
                                                }`}>
                                                    {row.status}
                                                </span>
                                            </div>
                                        </div>
                                    ))}

                                    {/* Review preview */}
                                    {"confidence" in (screen.preview[0] ?? {}) && screen.preview.map((row: any) => (
                                        <div
                                            key={row.label}
                                            className="rounded-lg border border-white/70 bg-white/80 px-3 py-2"
                                        >
                                            <div className="flex items-start justify-between gap-2">
                                                <p className="text-xs text-foreground leading-snug flex-1">{row.label}</p>
                                                <ConfidenceBadge pct={row.confidence} />
                                            </div>
                                            <p className="mt-1 text-[10px] text-muted-foreground">
                                                Source: {row.source}
                                            </p>
                                        </div>
                                    ))}

                                    {/* Usage preview */}
                                    {"limit" in (screen.preview[0] ?? {}) && (screen.preview as any[]).map((row) => (
                                        <div
                                            key={row.label}
                                            className="rounded-lg border border-white/70 bg-white/80 px-3 py-2 space-y-1"
                                        >
                                            <div className="flex justify-between text-xs">
                                                <span className="font-medium text-foreground">{row.label}</span>
                                                <span className="tabular-nums text-muted-foreground">
                                                    {row.used} / {row.limit}
                                                </span>
                                            </div>
                                            <ProgressBar pct={Math.round((row.used / row.limit) * 100)} />
                                        </div>
                                    ))}

                                    {/* Assistant preview */}
                                    {"q" in (screen.preview[0] ?? {}) && (screen.preview as any[]).map((row) => (
                                        <div key={row.q} className="space-y-1.5">
                                            <div className="rounded-lg border border-white/70 bg-white/80 px-3 py-2">
                                                <p className="text-[10px] font-semibold text-muted-foreground uppercase tracking-wider mb-1">
                                                    You asked
                                                </p>
                                                <p className="text-xs text-foreground">{row.q}</p>
                                            </div>
                                            <div className="rounded-lg border border-primary/20 bg-primary/5 px-3 py-2">
                                                <p className="text-[10px] font-semibold text-primary uppercase tracking-wider mb-1">
                                                    Answer
                                                </p>
                                                <p className="text-xs text-muted-foreground">{row.a}</p>
                                            </div>
                                        </div>
                                    ))}
                                </div>
                            </div>
                        );
                    })}
                </div>
            </div>
        </section>
    );
}

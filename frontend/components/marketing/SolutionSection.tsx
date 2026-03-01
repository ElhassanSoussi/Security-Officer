import {
    FileSearch,
    ShieldCheck,
    BarChart3,
    Archive,
    ClipboardCheck,
} from "lucide-react";

const CAPABILITIES = [
    {
        icon: FileSearch,
        title: "Auto-answer engine",
        description:
            "Upload a questionnaire. The AI maps every question, retrieves relevant evidence from your document vault, and generates grounded answers — no manual lookup.",
    },
    {
        icon: BarChart3,
        title: "Confidence scoring",
        description:
            "Every answer carries a confidence score. Reviewers focus on low-confidence items instead of re-reading the entire submission.",
    },
    {
        icon: Archive,
        title: "Evidence vault",
        description:
            "Safety manuals, insurance certificates, and prior submissions live in one versioned repository. Always current, always searchable.",
    },
    {
        icon: ClipboardCheck,
        title: "Full audit trail",
        description:
            "Every answer includes the source document, page number, and reviewer approval — traceable from submission back to original evidence.",
    },
    {
        icon: ShieldCheck,
        title: "Export-ready compliance",
        description:
            "Download submission-ready Excel files formatted to SCA, MTA, and PASSPort requirements. No reformatting, no guesswork.",
    },
];

export function SolutionSection() {
    return (
        <section
            className="border-t border-border/50"
            data-testid="marketing-solution"
        >
            <div className="max-w-6xl mx-auto px-6 py-16 md:py-20">
                <div className="max-w-2xl mx-auto text-center mb-12">
                    <p className="text-sm font-semibold uppercase tracking-wider text-primary mb-3">
                        The solution
                    </p>
                    <h2 className="text-3xl font-bold tracking-tight text-foreground">
                        One platform from document ingestion to auditable export
                    </h2>
                    <p className="mt-3 text-muted-foreground leading-relaxed">
                        NYC Compliance Architect replaces spreadsheets, email chains, and
                        tribal knowledge with a structured, evidence-backed workflow.
                    </p>
                </div>

                <div className="grid gap-5 md:grid-cols-2 lg:grid-cols-3">
                    {CAPABILITIES.map((cap) => {
                        const Icon = cap.icon;
                        return (
                            <div
                                key={cap.title}
                                className="rounded-xl border border-border/60 bg-background p-5 hover:border-primary/30 transition-colors"
                            >
                                <div className="flex h-10 w-10 items-center justify-center rounded-lg bg-primary/10 mb-3">
                                    <Icon className="h-5 w-5 text-primary" />
                                </div>
                                <h3 className="text-sm font-semibold text-foreground mb-1">
                                    {cap.title}
                                </h3>
                                <p className="text-sm text-muted-foreground leading-relaxed">
                                    {cap.description}
                                </p>
                            </div>
                        );
                    })}
                </div>
            </div>
        </section>
    );
}

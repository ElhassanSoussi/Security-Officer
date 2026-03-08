import { Upload, FileQuestion, CheckSquare, FileDown } from "lucide-react";

const STEPS = [
    {
        number: "01",
        icon: Upload,
        title: "Upload your documents",
        description:
            "Add safety manuals, insurance certificates, prior submissions, and operational policies to your evidence vault. Documents are indexed and version-tracked.",
    },
    {
        number: "02",
        icon: FileQuestion,
        title: "Upload the questionnaire",
        description:
            "Import an SCA, MTA, or PASSPort questionnaire. The platform maps every question to relevant evidence in your vault and drafts answers with source citations.",
    },
    {
        number: "03",
        icon: CheckSquare,
        title: "Review answers",
        description:
            "Your team reviews AI-drafted answers flagged by confidence score. Low-confidence items are highlighted. Approve, edit, or escalate — all actions are logged.",
    },
    {
        number: "04",
        icon: FileDown,
        title: "Export the final submission",
        description:
            "Download a submission-ready file formatted to agency requirements. Every answer includes its source document, page number, and reviewer sign-off.",
    },
];

export function HowItWorksSection() {
    return (
        <section
            id="how-it-works"
            className="border-t border-border/50"
            data-testid="marketing-how-it-works"
        >
            <div className="max-w-6xl mx-auto px-6 py-16 md:py-20">
                <div className="max-w-2xl mx-auto text-center mb-12">
                    <p className="text-sm font-semibold uppercase tracking-wider text-muted-foreground mb-3">
                        How it works
                    </p>
                    <h2 className="text-3xl font-bold tracking-tight text-foreground">
                        From raw documents to auditable submission in four steps
                    </h2>
                    <p className="mt-3 text-muted-foreground leading-relaxed">
                        No custom implementation required. Most teams are processing
                        their first questionnaire within the same day they sign up.
                    </p>
                </div>

                <div className="relative">
                    {/* Connector line — desktop only */}
                    <div
                        className="hidden lg:block absolute top-10 left-0 right-0 h-px bg-border/60 z-0"
                        style={{ marginLeft: "10%", marginRight: "10%" }}
                        aria-hidden="true"
                    />

                    <div className="relative z-10 grid gap-6 sm:grid-cols-2 lg:grid-cols-4">
                        {STEPS.map((step) => {
                            const Icon = step.icon;
                            return (
                                <div key={step.number} className="flex flex-col gap-3">
                                    {/* Step icon + number */}
                                    <div className="flex items-center gap-3 lg:flex-col lg:items-start">
                                        <div className="flex h-10 w-10 shrink-0 items-center justify-center rounded-full border-2 border-primary/30 bg-primary/10">
                                            <Icon className="h-4.5 w-4.5 text-primary" />
                                        </div>
                                        <span className="text-xs font-bold tabular-nums text-muted-foreground/60 tracking-widest">
                                            {step.number}
                                        </span>
                                    </div>

                                    <div className="rounded-xl border border-border/60 bg-background p-4">
                                        <h3 className="text-sm font-semibold text-foreground mb-1.5">
                                            {step.title}
                                        </h3>
                                        <p className="text-sm text-muted-foreground leading-relaxed">
                                            {step.description}
                                        </p>
                                    </div>
                                </div>
                            );
                        })}
                    </div>
                </div>
            </div>
        </section>
    );
}

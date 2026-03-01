import { Clock, AlertTriangle, FileWarning, ShieldAlert } from "lucide-react";

const PAIN_POINTS = [
    {
        icon: FileWarning,
        title: "Manual questionnaire chaos",
        description:
            "Teams re-key answers from prior submissions, copy-pasting across dozens of Excel tabs with no single source of truth.",
    },
    {
        icon: AlertTriangle,
        title: "Version control is nonexistent",
        description:
            "Which safety manual is current? Which insurance cert expired last month? Nobody knows until the audit finds out.",
    },
    {
        icon: ShieldAlert,
        title: "Audit exposure",
        description:
            "Unsourced answers and missing evidence create real liability. One bad submission can disqualify your firm.",
    },
    {
        icon: Clock,
        title: "Weeks lost on every bid",
        description:
            "Compliance officers spend 30–40 hours per questionnaire cycle on work that adds zero competitive advantage.",
    },
];

export function ProblemSection() {
    return (
        <section
            className="border-t border-border/50 bg-muted/30"
            data-testid="marketing-problem"
        >
            <div className="max-w-6xl mx-auto px-6 py-16 md:py-20">
                <div className="max-w-2xl mx-auto text-center mb-12">
                    <p className="text-sm font-semibold uppercase tracking-wider text-muted-foreground mb-3">
                        The problem
                    </p>
                    <h2 className="text-3xl font-bold tracking-tight text-foreground">
                        Compliance questionnaires are a liability, not a formality
                    </h2>
                    <p className="mt-3 text-muted-foreground leading-relaxed">
                        Every NYC construction bid demands detailed safety, insurance, and
                        operational documentation. Most teams still handle it the hard way.
                    </p>
                </div>

                <div className="grid sm:grid-cols-2 gap-6">
                    {PAIN_POINTS.map((point) => {
                        const Icon = point.icon;
                        return (
                            <div
                                key={point.title}
                                className="flex gap-4 rounded-xl border border-border/60 bg-background p-5"
                            >
                                <div className="flex h-10 w-10 shrink-0 items-center justify-center rounded-lg bg-destructive/10">
                                    <Icon className="h-5 w-5 text-destructive" />
                                </div>
                                <div>
                                    <h3 className="text-sm font-semibold text-foreground mb-1">
                                        {point.title}
                                    </h3>
                                    <p className="text-sm text-muted-foreground leading-relaxed">
                                        {point.description}
                                    </p>
                                </div>
                            </div>
                        );
                    })}
                </div>
            </div>
        </section>
    );
}

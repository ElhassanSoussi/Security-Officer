import {
    BookOpen,
    ShieldCheck,
    Users,
    FileSearch,
    Download,
} from "lucide-react";

const SIGNALS = [
    { icon: BookOpen,    text: "Audit Trail" },
    { icon: FileSearch,  text: "Source Citations" },
    { icon: Users,       text: "Role-Based Access" },
    { icon: ShieldCheck, text: "Evidence-Backed Answers" },
    { icon: Download,    text: "Export-Ready Outputs" },
];

export function TrustBar() {
    return (
        <div className="border-y border-border/50 bg-muted/20">
            <div className="max-w-6xl mx-auto px-6 py-4">
                <div className="flex flex-wrap items-center justify-center gap-x-8 gap-y-3">
                    {SIGNALS.map(({ icon: Icon, text }) => (
                        <span
                            key={text}
                            className="inline-flex items-center gap-2 text-sm font-medium text-muted-foreground"
                        >
                            <Icon className="h-4 w-4 text-primary/70 shrink-0" />
                            {text}
                        </span>
                    ))}
                </div>
            </div>
        </div>
    );
}

import Link from "next/link";
import {
    ShieldCheck,
    Upload,
    FileQuestion,
    CheckSquare,
    FileDown,
    ArrowRight,
    Calendar,
    BookOpen,
    Eye,
    Lock,
} from "lucide-react";
import { Button } from "@/components/ui/button";
import { Card, CardContent } from "@/components/ui/card";

const DEMO_INCLUDES = [
    {
        icon: Upload,
        title: "Sample evidence vault",
        description:
            "A pre-loaded set of representative documents — safety manual, insurance certificate, training records — so you can see how the vault is structured without uploading your own files.",
    },
    {
        icon: FileQuestion,
        title: "Example questionnaire run",
        description:
            "A completed SCA-style questionnaire showing how questions are mapped to source documents, confidence scores assigned, and low-confidence items flagged for human review.",
    },
    {
        icon: CheckSquare,
        title: "Review & audit trail",
        description:
            "See what a reviewer sees: the AI-drafted answer, the source excerpt with page citation, the confidence score, and the approval log entry.",
    },
    {
        icon: FileDown,
        title: "Export preview",
        description:
            "A sample export file showing submission-ready output — formatted to agency requirements with answers, sources, and reviewer sign-offs included.",
    },
];

const WHAT_YOU_CANNOT_DO = [
    "Upload your own documents (read-only workspace)",
    "Submit or save changes",
    "Access billing or account settings",
];

export default function DemoPage() {
    return (
        <div className="min-h-screen bg-background">
            {/* ── Navigation ────────────────────────────────────── */}
            <nav className="border-b border-border/50 bg-background/80 backdrop-blur-sm sticky top-0 z-50">
                <div className="max-w-6xl mx-auto px-6 h-16 flex items-center justify-between">
                    <Link href="/" className="flex items-center gap-2.5">
                        <div className="flex h-8 w-8 items-center justify-center rounded-lg bg-primary/10">
                            <ShieldCheck className="h-4.5 w-4.5 text-primary" />
                        </div>
                        <span className="font-semibold text-[15px] tracking-tight text-foreground">
                            NYC Compliance
                        </span>
                    </Link>
                    <div className="flex items-center gap-3">
                        <Link href="/login">
                            <Button variant="ghost" size="sm">Sign In</Button>
                        </Link>
                        <Link href="/signup">
                            <Button size="sm">Start Free Trial</Button>
                        </Link>
                    </div>
                </div>
            </nav>

            {/* ── Hero ──────────────────────────────────────────── */}
            <section className="relative overflow-hidden border-b border-border/50">
                <div className="absolute inset-0 bg-gradient-to-br from-primary/5 via-background to-background" />
                <div className="relative max-w-6xl mx-auto px-6 py-16 md:py-24">
                    <div className="max-w-2xl">
                        <div className="inline-flex items-center gap-2 rounded-full border border-primary/20 bg-primary/5 text-primary px-3.5 py-1.5 text-xs font-semibold tracking-wide uppercase mb-6">
                            <Eye className="h-3.5 w-3.5" />
                            Product Demo
                        </div>
                        <h1 className="text-4xl sm:text-5xl font-bold tracking-tight text-foreground leading-tight">
                            See the compliance workflow before you commit.
                        </h1>
                        <p className="mt-5 text-lg text-muted-foreground leading-relaxed">
                            This is a guided, read-only look at a real workspace. You will
                            see the document vault, a completed questionnaire run with
                            confidence scoring, the reviewer interface, and a sample export
                            — using representative data, not your own.
                        </p>
                        <div className="mt-8 flex flex-wrap items-center gap-3">
                            <Link href="/signup">
                                <Button size="lg" className="gap-2 text-base px-6 h-12">
                                    Start Free Trial — no demo needed
                                    <ArrowRight className="h-4 w-4" />
                                </Button>
                            </Link>
                            <Link href="/contact">
                                <Button size="lg" variant="outline" className="gap-2 text-base px-6 h-12">
                                    <Calendar className="h-4 w-4" />
                                    Book a live walkthrough
                                </Button>
                            </Link>
                        </div>
                    </div>
                </div>
            </section>

            {/* ── What the demo includes ─────────────────────────── */}
            <section className="max-w-6xl mx-auto px-6 py-16">
                <div className="mb-10">
                    <p className="text-sm font-semibold uppercase tracking-wider text-muted-foreground mb-2">
                        What is included
                    </p>
                    <h2 className="text-2xl font-bold tracking-tight text-foreground">
                        A complete compliance run from start to export
                    </h2>
                    <p className="mt-2 text-muted-foreground max-w-xl leading-relaxed">
                        The demo workspace is pre-populated with sample documents and a
                        completed questionnaire so you can explore every step without
                        setting anything up.
                    </p>
                </div>

                <div className="grid gap-5 sm:grid-cols-2">
                    {DEMO_INCLUDES.map((item) => {
                        const Icon = item.icon;
                        return (
                            <Card key={item.title} className="border-border/60">
                                <CardContent className="pt-5 flex gap-4">
                                    <div className="flex h-10 w-10 shrink-0 items-center justify-center rounded-lg bg-primary/10">
                                        <Icon className="h-5 w-5 text-primary" />
                                    </div>
                                    <div>
                                        <h3 className="text-sm font-semibold text-foreground mb-1">
                                            {item.title}
                                        </h3>
                                        <p className="text-sm text-muted-foreground leading-relaxed">
                                            {item.description}
                                        </p>
                                    </div>
                                </CardContent>
                            </Card>
                        );
                    })}
                </div>
            </section>

            {/* ── Scope / limitations ───────────────────────────── */}
            <section className="border-t border-border/50 bg-muted/30">
                <div className="max-w-6xl mx-auto px-6 py-12">
                    <div className="max-w-xl mx-auto">
                        <div className="flex items-start gap-3 mb-5">
                            <div className="flex h-9 w-9 shrink-0 items-center justify-center rounded-lg bg-muted border border-border">
                                <Lock className="h-4 w-4 text-muted-foreground" />
                            </div>
                            <div>
                                <h3 className="text-sm font-semibold text-foreground">
                                    Demo workspace is read-only
                                </h3>
                                <p className="text-sm text-muted-foreground mt-0.5">
                                    To protect data integrity, the following are not available in
                                    the demo:
                                </p>
                            </div>
                        </div>
                        <ul className="space-y-2 pl-12">
                            {WHAT_YOU_CANNOT_DO.map((item) => (
                                <li
                                    key={item}
                                    className="flex items-center gap-2 text-sm text-muted-foreground"
                                >
                                    <span className="h-1.5 w-1.5 rounded-full bg-muted-foreground/40 shrink-0" />
                                    {item}
                                </li>
                            ))}
                        </ul>
                        <p className="mt-5 pl-12 text-sm text-muted-foreground">
                            Need to test with your own documents?{" "}
                            <Link
                                href="/signup"
                                className="font-medium text-foreground underline underline-offset-2 hover:no-underline"
                            >
                                Start the free trial
                            </Link>{" "}
                            — no credit card required.
                        </p>
                    </div>
                </div>
            </section>

            {/* ── Live walkthrough option ────────────────────────── */}
            <section className="border-t border-border/50">
                <div className="max-w-6xl mx-auto px-6 py-14 md:py-16">
                    <div className="max-w-2xl mx-auto text-center">
                        <BookOpen className="h-8 w-8 text-muted-foreground/50 mx-auto mb-4" />
                        <h2 className="text-2xl font-bold tracking-tight text-foreground">
                            Prefer a live walkthrough?
                        </h2>
                        <p className="mt-3 text-muted-foreground leading-relaxed">
                            Schedule a 30-minute call with our team. We will walk through
                            your specific questionnaire type, show you how your own documents
                            would be processed, and answer any workflow questions directly.
                        </p>
                        <div className="mt-7 flex flex-wrap items-center justify-center gap-3">
                            <Link href="/contact">
                                <Button size="lg" className="gap-2 text-base px-6 h-12">
                                    <Calendar className="h-4 w-4" />
                                    Schedule a Live Demo
                                </Button>
                            </Link>
                            <Link href="/signup">
                                <Button size="lg" variant="outline" className="text-base px-6 h-12">
                                    Start Free Trial
                                </Button>
                            </Link>
                        </div>
                    </div>
                </div>
            </section>

            {/* ── Footer ────────────────────────────────────────── */}
            <footer className="border-t border-border">
                <div className="max-w-6xl mx-auto px-6 py-8 flex flex-wrap items-center justify-between gap-4 text-sm text-muted-foreground">
                    <Link href="/" className="flex items-center gap-2 hover:text-foreground transition-colors">
                        <ShieldCheck className="h-4 w-4 text-primary" />
                        <span className="font-medium">NYC Compliance Architect</span>
                    </Link>
                    <div className="flex flex-wrap gap-4 text-xs">
                        <Link href="/" className="hover:text-foreground transition-colors">Home</Link>
                        <a href="#pricing" className="hover:text-foreground transition-colors">Pricing</a>
                        <Link href="/contact" className="hover:text-foreground transition-colors">Contact</Link>
                        <Link href="/login" className="hover:text-foreground transition-colors">Sign In</Link>
                    </div>
                </div>
            </footer>
        </div>
    );
}

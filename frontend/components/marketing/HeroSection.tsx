import Link from "next/link";
import { ArrowRight, ShieldCheck, CheckCircle2, PlayCircle } from "lucide-react";
import { Button } from "@/components/ui/button";

const TRUST_SIGNALS = [
    "No credit card required",
    "SOC 2 aligned controls",
    "Audit-ready from day one",
];

export function HeroSection() {
    return (
        <section id="hero" className="relative overflow-hidden" data-testid="marketing-hero">
            <div className="absolute inset-0 bg-gradient-to-br from-primary/5 via-background to-background" />
            <div className="relative max-w-6xl mx-auto px-6 pt-20 pb-16 md:pt-28 md:pb-24">
                <div className="max-w-3xl">
                    <div className="inline-flex items-center gap-2 rounded-full border border-primary/20 bg-primary/5 text-primary px-3.5 py-1.5 text-xs font-semibold tracking-wide uppercase mb-6">
                        <ShieldCheck className="h-3.5 w-3.5" />
                        NYC Construction Compliance
                    </div>

                    <h1 className="text-4xl sm:text-5xl md:text-[3.5rem] font-bold tracking-tight text-foreground leading-[1.08]">
                        Complete high-stakes compliance questionnaires{" "}
                        <span className="text-primary">faster with evidence-backed answers.</span>
                    </h1>

                    <p className="mt-6 text-lg text-muted-foreground max-w-2xl leading-relaxed">
                        Built for NYC contractors and compliance-heavy vendors. Your own
                        documents become the source of truth — every answer is cited,
                        traceable, and reviewer-approved before export.
                    </p>

                    <div className="mt-8 flex flex-wrap items-center gap-3">
                        <Link href="/signup">
                            <Button size="lg" className="gap-2 text-base px-6 h-12">
                                Start Free Trial <ArrowRight className="h-4 w-4" />
                            </Button>
                        </Link>
                        <Link href="/contact">
                            <Button size="lg" variant="outline" className="text-base px-6 h-12">
                                Book Demo
                            </Button>
                        </Link>
                        <Link href="/demo">
                            <Button size="lg" variant="ghost" className="gap-2 text-base px-4 h-12 text-muted-foreground hover:text-foreground">
                                <PlayCircle className="h-4 w-4" />
                                View Product Demo
                            </Button>
                        </Link>
                    </div>

                    <div className="mt-8 flex flex-wrap items-center gap-x-6 gap-y-2 text-sm text-muted-foreground">
                        {TRUST_SIGNALS.map((item) => (
                            <span key={item} className="inline-flex items-center gap-1.5">
                                <CheckCircle2 className="h-4 w-4 text-green-600" />
                                {item}
                            </span>
                        ))}
                    </div>
                </div>
            </div>
        </section>
    );
}

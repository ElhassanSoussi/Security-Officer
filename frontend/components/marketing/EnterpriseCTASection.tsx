import Link from "next/link";
import { ArrowRight, ShieldCheck, Lock, Zap, Clock } from "lucide-react";
import { Button } from "@/components/ui/button";

const TRUST_BAR = [
    { icon: Lock, text: "End-to-end encryption" },
    { icon: ShieldCheck, text: "SOC 2 aligned controls" },
    { icon: Zap, text: "No training on your data" },
    { icon: Clock, text: "99.9% uptime SLA" },
];

export function EnterpriseCTASection() {
    return (
        <section data-testid="marketing-enterprise-cta">
            {/* ── Enterprise CTA ───────────────────────────────── */}
            <div className="border-t border-border/50 bg-muted/30">
                <div className="max-w-6xl mx-auto px-6 py-16 md:py-20">
                    <div className="max-w-2xl mx-auto text-center">
                        <h2 className="text-3xl font-bold tracking-tight text-foreground">
                            Ready to eliminate compliance bottlenecks?
                        </h2>
                        <p className="mt-3 text-muted-foreground leading-relaxed">
                            Book a 30-minute compliance strategy call. We will walk through
                            your current workflow and show you exactly where the platform
                            saves time.
                        </p>
                        <div className="mt-8 flex flex-wrap items-center justify-center gap-3">
                            <Link href="/contact">
                                <Button size="lg" className="gap-2 text-base px-6 h-12">
                                    Book Compliance Strategy Call
                                    <ArrowRight className="h-4 w-4" />
                                </Button>
                            </Link>
                            <Link href="/signup">
                                <Button
                                    size="lg"
                                    variant="outline"
                                    className="text-base px-6 h-12"
                                >
                                    Start Free Trial
                                </Button>
                            </Link>
                        </div>
                    </div>
                </div>
            </div>

            {/* ── Trust Bar ────────────────────────────────────── */}
            <div className="border-t border-border/50">
                <div className="max-w-6xl mx-auto px-6 py-10">
                    <div className="flex flex-wrap items-center justify-center gap-x-8 gap-y-3 text-sm text-muted-foreground">
                        {TRUST_BAR.map(({ icon: Icon, text }) => (
                            <span
                                key={text}
                                className="inline-flex items-center gap-2"
                            >
                                <Icon className="h-4 w-4 text-muted-foreground/70" />
                                {text}
                            </span>
                        ))}
                    </div>
                </div>
            </div>
        </section>
    );
}

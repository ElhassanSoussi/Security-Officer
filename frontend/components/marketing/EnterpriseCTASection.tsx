import Link from "next/link";
import { ArrowRight, ShieldCheck, Lock, Zap, Clock, PlayCircle, Calendar, Mail } from "lucide-react";
import { Button } from "@/components/ui/button";

const TRUST_BAR = [
    { icon: Lock, text: "End-to-end encryption" },
    { icon: ShieldCheck, text: "SOC 2 aligned controls" },
    { icon: Zap, text: "No training on your data" },
    { icon: Clock, text: "99.9% uptime SLA" },
];

export function EnterpriseCTASection() {
    return (
        <section id="contact" data-testid="marketing-enterprise-cta">
            {/* ── CTA ──────────────────────────────────────────── */}
            <div className="border-t border-border/50 bg-gradient-to-br from-slate-900 to-slate-800 text-white">
                <div className="max-w-6xl mx-auto px-6 py-16 md:py-20">
                    <div className="max-w-2xl mx-auto text-center">
                        <h2 className="text-3xl font-bold tracking-tight text-white">
                            Ready to eliminate compliance bottlenecks?
                        </h2>
                        <p className="mt-3 text-white/70 leading-relaxed">
                            Start a free trial, schedule a 30-minute walkthrough of your
                            specific workflow, or contact our team for enterprise pricing.
                        </p>
                        <div className="mt-8 flex flex-wrap items-center justify-center gap-3">
                            <Link href="/signup">
                                <Button
                                    size="lg"
                                    className="gap-2 text-base px-6 h-12 bg-white text-slate-900 hover:bg-white/90"
                                >
                                    Start Free Trial
                                    <ArrowRight className="h-4 w-4" />
                                </Button>
                            </Link>
                            <Link href="/contact">
                                <Button
                                    size="lg"
                                    variant="outline"
                                    className="gap-2 text-base px-6 h-12 border-white/30 text-white hover:bg-white/10"
                                >
                                    <Calendar className="h-4 w-4" />
                                    Schedule Demo
                                </Button>
                            </Link>
                            <Link href="/demo">
                                <Button
                                    size="lg"
                                    variant="ghost"
                                    className="gap-2 text-base px-5 h-12 text-white/70 hover:text-white hover:bg-white/10"
                                >
                                    <PlayCircle className="h-4 w-4" />
                                    View Demo
                                </Button>
                            </Link>
                        </div>
                        <p className="mt-6 text-sm text-white/40">
                            Enterprise or agency-specific pricing?{" "}
                            <a
                                href="mailto:hello@nyccompliance.ai"
                                className="underline underline-offset-2 text-white/60 hover:text-white transition-colors"
                            >
                                Contact sales <Mail className="inline h-3 w-3 ml-0.5" />
                            </a>
                        </p>
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

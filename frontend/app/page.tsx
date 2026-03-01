import Link from "next/link";
import { redirect } from "next/navigation";
import { ShieldCheck } from "lucide-react";
import { Button } from "@/components/ui/button";
import { createClient } from "@/utils/supabase/server";

import {
    HeroSection,
    ProblemSection,
    SolutionSection,
    SocialProofSection,
    PricingSection,
    EnterpriseCTASection,
} from "@/components/marketing";

export default async function LandingPage() {
    try {
        const supabase = createClient();
        const { data: { user } } = await supabase.auth.getUser();
        if (user) {
            redirect("/dashboard");
        }
    } catch {
        // If env is missing, RootLayout already renders a dedicated config error.
    }

    return (
        <div className="min-h-screen bg-background">
            {/* ── Navigation ────────────────────────────────────── */}
            <nav className="border-b border-border/50 bg-background/80 backdrop-blur-sm sticky top-0 z-50">
                <div className="max-w-6xl mx-auto px-6 h-16 flex items-center justify-between">
                    <div className="flex items-center gap-2.5">
                        <div className="flex h-8 w-8 items-center justify-center rounded-lg bg-primary/10">
                            <ShieldCheck className="h-4.5 w-4.5 text-primary" />
                        </div>
                        <span className="font-semibold text-[15px] tracking-tight text-foreground">
                            NYC Compliance
                        </span>
                    </div>
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

            {/* ── 1. Hero ───────────────────────────────────────── */}
            <HeroSection />

            {/* ── 2. Problem ────────────────────────────────────── */}
            <ProblemSection />

            {/* ── 3. Solution ───────────────────────────────────── */}
            <SolutionSection />

            {/* ── 4. Social Proof ───────────────────────────────── */}
            <SocialProofSection />

            {/* ── 5. Pricing ────────────────────────────────────── */}
            <PricingSection />

            {/* ── 6. Enterprise CTA + Trust Bar ─────────────────── */}
            <EnterpriseCTASection />

            {/* ── Footer ────────────────────────────────────────── */}
            <footer className="border-t border-border">
                <div className="max-w-6xl mx-auto px-6 py-10">
                    <div className="grid sm:grid-cols-4 gap-8">
                        <div className="sm:col-span-2">
                            <div className="flex items-center gap-2 mb-3">
                                <div className="flex h-7 w-7 items-center justify-center rounded-lg bg-primary/10">
                                    <ShieldCheck className="h-4 w-4 text-primary" />
                                </div>
                                <span className="font-semibold text-sm text-foreground">
                                    NYC Compliance Architect
                                </span>
                            </div>
                            <p className="text-sm text-muted-foreground max-w-sm leading-relaxed">
                                AI-powered security questionnaire automation for NYC
                                construction compliance. Built for SCA, MTA, and PASSPort
                                submissions.
                            </p>
                        </div>
                        <div>
                            <h4 className="text-sm font-semibold text-foreground mb-3">
                                Product
                            </h4>
                            <ul className="space-y-2 text-sm text-muted-foreground">
                                <li>
                                    <Link href="/signup" className="hover:text-foreground transition-colors">
                                        Sign Up
                                    </Link>
                                </li>
                                <li>
                                    <Link href="/login" className="hover:text-foreground transition-colors">
                                        Sign In
                                    </Link>
                                </li>
                                <li>
                                    <Link href="/contact" className="hover:text-foreground transition-colors">
                                        Request Demo
                                    </Link>
                                </li>
                                <li>
                                    <Link href="/plans" className="hover:text-foreground transition-colors">
                                        Pricing
                                    </Link>
                                </li>
                            </ul>
                        </div>
                        <div>
                            <h4 className="text-sm font-semibold text-foreground mb-3">
                                Legal
                            </h4>
                            <ul className="space-y-2 text-sm text-muted-foreground">
                                <li>
                                    <a href="mailto:legal@nyccompliance.ai" className="hover:text-foreground transition-colors">
                                        Terms of Service
                                    </a>
                                </li>
                                <li>
                                    <a href="mailto:privacy@nyccompliance.ai" className="hover:text-foreground transition-colors">
                                        Privacy Policy
                                    </a>
                                </li>
                                <li>
                                    <a href="mailto:security@nyccompliance.ai" className="hover:text-foreground transition-colors">
                                        Security
                                    </a>
                                </li>
                                <li>
                                    <a href="mailto:hello@nyccompliance.ai" className="hover:text-foreground transition-colors">
                                        Contact
                                    </a>
                                </li>
                            </ul>
                        </div>
                    </div>
                    <div className="border-t border-border mt-8 pt-6 flex flex-wrap items-center justify-between gap-2 text-xs text-muted-foreground">
                        <span>
                            © {new Date().getFullYear()} NYC Compliance Architect. All
                            rights reserved.
                        </span>
                        <span>
                            v1.0.0 · Security-first architecture with auditable actions
                        </span>
                    </div>
                </div>
            </footer>
        </div>
    );
}

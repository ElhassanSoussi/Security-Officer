import Link from "next/link";
import { redirect } from "next/navigation";
import { ShieldCheck } from "lucide-react";
import { Button } from "@/components/ui/button";
import { createClient } from "@/utils/supabase/server";

import {
    HeroSection,
    TrustBar,
    ProblemSection,
    HowItWorksSection,
    SolutionSection,
    ProductProofSection,
    SocialProofSection,
    PricingSection,
    EnterpriseCTASection,
} from "@/components/marketing";

export default async function LandingPage() {
    try {
        const supabase = createClient();
        if (supabase) {
            const { data: { user } } = await supabase.auth.getUser();
            if (user) {
                redirect("/dashboard");
            }
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

                    {/* Desktop nav links */}
                    <div className="hidden md:flex items-center gap-1 text-sm text-muted-foreground">
                        <a
                            href="#features"
                            className="px-3 py-1.5 rounded-md hover:text-foreground hover:bg-muted/50 transition-colors"
                        >
                            Features
                        </a>
                        <a
                            href="#how-it-works"
                            className="px-3 py-1.5 rounded-md hover:text-foreground hover:bg-muted/50 transition-colors"
                        >
                            How It Works
                        </a>
                        <a
                            href="#pricing"
                            className="px-3 py-1.5 rounded-md hover:text-foreground hover:bg-muted/50 transition-colors"
                        >
                            Pricing
                        </a>
                        <Link
                            href="/demo"
                            className="px-3 py-1.5 rounded-md hover:text-foreground hover:bg-muted/50 transition-colors"
                        >
                            Demo
                        </Link>
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

            {/* ── 2. Trust Bar ──────────────────────────────────── */}
            <TrustBar />

            {/* ── 3. Problem ────────────────────────────────────── */}
            <ProblemSection />

            {/* ── 4. How It Works ───────────────────────────────── */}
            <HowItWorksSection />

            {/* ── 5. Solution / Capabilities ────────────────────── */}
            <SolutionSection />

            {/* ── 6. Product Proof / Screens ────────────────────── */}
            <ProductProofSection />

            {/* ── 7. Social Proof ───────────────────────────────── */}
            <SocialProofSection />

            {/* ── 8. Pricing ────────────────────────────────────── */}
            <PricingSection />

            {/* ── 9. Final CTA + Trust Bar ──────────────────────── */}
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
                                Evidence-backed compliance questionnaire automation for NYC
                                construction. Built for SCA, MTA, and PASSPort submissions.
                            </p>
                        </div>

                        <div>
                            <h4 className="text-sm font-semibold text-foreground mb-3">
                                Product
                            </h4>
                            <ul className="space-y-2 text-sm text-muted-foreground">
                                <li>
                                    <Link href="/demo" className="hover:text-foreground transition-colors">
                                        Demo
                                    </Link>
                                </li>
                                <li>
                                    <a href="#pricing" className="hover:text-foreground transition-colors">
                                        Pricing
                                    </a>
                                </li>
                                <li>
                                    <Link href="/signup" className="hover:text-foreground transition-colors">
                                        Start Free Trial
                                    </Link>
                                </li>
                                <li>
                                    <Link href="/contact" className="hover:text-foreground transition-colors">
                                        Schedule Demo
                                    </Link>
                                </li>
                                <li>
                                    <Link href="/login" className="hover:text-foreground transition-colors">
                                        Sign In
                                    </Link>
                                </li>
                            </ul>
                        </div>

                        <div>
                            <h4 className="text-sm font-semibold text-foreground mb-3">
                                Legal &amp; Contact
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
                            Security-first architecture · Auditable actions · SOC 2 aligned
                        </span>
                    </div>
                </div>
            </footer>
        </div>
    );
}

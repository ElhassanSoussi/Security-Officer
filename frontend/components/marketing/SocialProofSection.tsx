import { Building2, Quote } from "lucide-react";
import { Card, CardContent } from "@/components/ui/card";

/**
 * Social Proof — case study template placeholders.
 *
 * These are intentionally placeholder blocks so the marketing team
 * can drop in real case studies when available. The structure is
 * production-ready; only copy needs updating.
 */

const CASE_STUDIES = [
    {
        company: "Midsize GC — School Construction Authority",
        quote:
            "We cut our SCA questionnaire turnaround from three weeks to two days. Every answer is sourced and auditable.",
        role: "Compliance Director",
        metric: "85% faster turnaround",
    },
    {
        company: "Specialty Subcontractor — MTA Capital Projects",
        quote:
            "Our team used to spend 40 hours per submission cycle. Now the AI handles the first pass and we focus on review.",
        role: "VP of Safety",
        metric: "30+ hours saved per cycle",
    },
    {
        company: "Large Contractor — PASSPort Vendor Compliance",
        quote:
            "We stopped worrying about expired certs and missing evidence. The vault keeps everything current and indexed.",
        role: "Operations Manager",
        metric: "Zero audit findings",
    },
];

export function SocialProofSection() {
    return (
        <section
            className="border-t border-border/50 bg-gradient-to-br from-slate-900 to-slate-800 text-white"
            data-testid="marketing-social-proof"
        >
            <div className="max-w-6xl mx-auto px-6 py-16 md:py-20">
                <div className="max-w-2xl mx-auto text-center mb-12">
                    <p className="text-sm font-semibold uppercase tracking-wider text-white/60 mb-3">
                        Case studies
                    </p>
                    <h2 className="text-3xl font-bold tracking-tight text-white">
                        Trusted by NYC construction compliance teams
                    </h2>
                    <p className="mt-3 text-white/70 leading-relaxed">
                        Results from early adopters managing SCA, MTA, and PASSPort
                        submissions.
                    </p>
                </div>

                <div className="grid md:grid-cols-3 gap-5">
                    {CASE_STUDIES.map((cs) => (
                        <Card
                            key={cs.company}
                            className="border-white/10 bg-white/5 text-white"
                        >
                            <CardContent className="pt-5 sm:pt-6 flex flex-col h-full">
                                <Quote className="h-5 w-5 text-white/30 mb-3" />
                                <p className="text-sm text-white/80 leading-relaxed flex-1">
                                    &ldquo;{cs.quote}&rdquo;
                                </p>
                                <div className="mt-4 pt-4 border-t border-white/10">
                                    <div className="flex items-center gap-2 mb-2">
                                        <div className="flex h-8 w-8 items-center justify-center rounded-lg bg-white/10">
                                            <Building2 className="h-4 w-4 text-blue-400" />
                                        </div>
                                        <div>
                                            <p className="text-xs font-semibold text-white/90">
                                                {cs.role}
                                            </p>
                                            <p className="text-xs text-white/50">{cs.company}</p>
                                        </div>
                                    </div>
                                    <span className="inline-block mt-1 rounded-full bg-primary/20 text-primary px-2.5 py-0.5 text-xs font-semibold">
                                        {cs.metric}
                                    </span>
                                </div>
                            </CardContent>
                        </Card>
                    ))}
                </div>

                <p className="mt-8 text-center text-xs text-white/40">
                    Case studies are representative templates. Identifying details
                    anonymized.
                </p>
            </div>
        </section>
    );
}

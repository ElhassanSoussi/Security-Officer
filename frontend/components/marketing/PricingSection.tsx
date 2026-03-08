import Link from "next/link";
import { CheckCircle2, Star } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from "@/components/ui/card";

interface Plan {
    name: string;
    price: string;
    period: string;
    description: string;
    features: string[];
    popular?: boolean;
    cta: string;
    href: string;
}

const PLANS: Plan[] = [
    {
        name: "Starter",
        price: "$149",
        period: "/month",
        description:
            "For small teams managing a focused pipeline of bids with basic compliance needs.",
        features: [
            "3 active projects",
            "50 exports per month",
            "Document vault — 5 GB",
            "Email support",
        ],
        cta: "Start Free Trial",
        href: "/signup",
    },
    {
        name: "Growth",
        price: "$499",
        period: "/month",
        description:
            "For multi-project operations that need review workflows, role-based access, and analytics.",
        features: [
            "15 active projects",
            "250 exports per month",
            "Document vault — 25 GB",
            "Review and approval workflows",
            "Role-based access control",
            "Priority support",
        ],
        popular: true,
        cta: "Start Free Trial",
        href: "/signup",
    },
    {
        name: "Elite",
        price: "Custom",
        period: "",
        description:
            "For large contractors requiring SSO, dedicated support, and API access at scale.",
        features: [
            "Unlimited projects",
            "Unlimited exports",
            "Document vault — unlimited",
            "SSO and SAML integration",
            "Audit log API access",
            "Dedicated customer success manager",
            "Custom SLA",
        ],
        cta: "Contact Sales",
        href: "/contact",
    },
];

export function PricingSection() {
    return (
        <section
            id="pricing"
            className="border-t border-border/50"
            data-testid="marketing-pricing"
        >
            <div className="max-w-6xl mx-auto px-6 py-16 md:py-20">
                <div className="max-w-2xl mx-auto text-center mb-12">
                    <p className="text-sm font-semibold uppercase tracking-wider text-muted-foreground mb-3">
                        Pricing
                    </p>
                    <h2 className="text-3xl font-bold tracking-tight text-foreground">
                        Transparent pricing, no hidden fees
                    </h2>
                    <p className="mt-3 text-muted-foreground leading-relaxed">
                        Start with a free trial. Upgrade when your team is ready.
                    </p>
                </div>

                <div className="grid md:grid-cols-3 gap-5">
                    {PLANS.map((plan) => (
                        <Card
                            key={plan.name}
                            className={`relative flex flex-col ${
                                plan.popular
                                    ? "border-primary shadow-md ring-1 ring-primary/20"
                                    : "border-border/60"
                            }`}
                        >
                            {plan.popular && (
                                <div className="absolute -top-3 left-1/2 -translate-x-1/2">
                                    <span className="inline-flex items-center gap-1 rounded-full bg-primary text-primary-foreground px-3 py-0.5 text-xs font-semibold">
                                        <Star className="h-3 w-3" /> Most Popular
                                    </span>
                                </div>
                            )}
                            <CardHeader>
                                <CardTitle>{plan.name}</CardTitle>
                                <CardDescription>
                                    <span className="text-2xl font-bold text-foreground">
                                        {plan.price}
                                    </span>
                                    {plan.period && (
                                        <span className="text-muted-foreground">
                                            {plan.period}
                                        </span>
                                    )}
                                </CardDescription>
                            </CardHeader>
                            <CardContent className="flex-1 space-y-4">
                                <p className="text-sm text-muted-foreground">
                                    {plan.description}
                                </p>
                                <ul className="space-y-2">
                                    {plan.features.map((f) => (
                                        <li
                                            key={f}
                                            className="flex items-start gap-2 text-sm"
                                        >
                                            <CheckCircle2 className="h-4 w-4 text-green-600 shrink-0 mt-0.5" />
                                            {f}
                                        </li>
                                    ))}
                                </ul>
                                <Link href={plan.href} className="block pt-2">
                                    <Button
                                        variant={plan.popular ? "default" : "outline"}
                                        className="w-full"
                                    >
                                        {plan.cta}
                                    </Button>
                                </Link>
                            </CardContent>
                        </Card>
                    ))}
                </div>
            </div>
        </section>
    );
}

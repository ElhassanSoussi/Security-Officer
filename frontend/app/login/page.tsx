"use client";

import { useState } from "react";
import { createClient } from "@/utils/supabase/client";
import { useRouter } from "next/navigation";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Card, CardContent } from "@/components/ui/card";
import Link from "next/link";
import { useToast } from "@/components/ui/toaster";
import { ApiClient } from "@/lib/api";
import { setStoredOrgId, getStoredOrgId } from "@/lib/orgContext";
import { ShieldCheck, CheckCircle2, Loader2 } from "lucide-react";

const FEATURES = [
    "AI-powered NYC compliance questionnaire processing",
    "Multi-run intelligence & audit trail",
    "Role-based access control & export gates",
    "Enterprise-grade security & SOC 2 ready",
];

export default function LoginPage() {
    const [email, setEmail] = useState("");
    const [password, setPassword] = useState("");
    const [loading, setLoading] = useState(false);
    const router = useRouter();
    const { toast } = useToast();

    let supabase: ReturnType<typeof createClient> | null = null;
    let initError = "";
    try {
        supabase = createClient();
    } catch (err: any) {
        initError = String(err?.message || "Supabase client is not configured.");
    }

    const mapAuthError = (err: any): string => {
        const msg = String(err?.message || "Login failed");
        const status = typeof err?.status === "number" ? err.status : undefined;
        if (status === 401 && /invalid api key/i.test(msg)) {
            return "Supabase credentials mismatch (URL/key). Check NEXT_PUBLIC_SUPABASE_URL + NEXT_PUBLIC_SUPABASE_ANON_KEY, then restart the dev server.";
        }
        if (/invalid login credentials/i.test(msg)) {
            return "Invalid email or password.";
        }
        return msg;
    };

    const handleLogin = async (e: React.FormEvent) => {
        e.preventDefault();
        if (!supabase) {
            toast({ title: "Configuration Error", description: initError, variant: "destructive" });
            return;
        }
        setLoading(true);

        const { error } = await supabase.auth.signInWithPassword({ email, password });

        if (error) {
            toast({ title: "Login Failed", description: mapAuthError(error), variant: "destructive" });
            setLoading(false);
        } else {
            try {
                const { data: { session } } = await supabase.auth.getSession();
                const token = session?.access_token;
                if (token) {
                    const preferred = getStoredOrgId() || undefined;
                    try {
                        const current = await ApiClient.getCurrentOrg(token, preferred);
                        if (current?.id) {
                            setStoredOrgId(current.id);
                            toast({ title: "Welcome back!", variant: "success" });
                            router.push("/dashboard");
                            router.refresh();
                            return;
                        }
                    } catch {
                        router.push("/onboarding");
                        router.refresh();
                        return;
                    }
                }
            } catch {
                // Non-fatal
            }
            toast({ title: "Welcome back!", variant: "success" });
            router.push("/dashboard");
            router.refresh();
        }
    };

    if (!supabase) {
        return (
            <div className="flex items-center justify-center min-h-screen bg-background p-6">
                <Card className="w-full max-w-md border-destructive/30">
                    <CardContent className="pt-6 space-y-3">
                        <p className="font-semibold text-destructive">Configuration Error</p>
                        <p className="text-sm text-muted-foreground">{initError}</p>
                        <p className="text-xs text-muted-foreground">
                            Set <code className="font-mono bg-muted px-1 rounded">NEXT_PUBLIC_SUPABASE_URL</code> and{" "}
                            <code className="font-mono bg-muted px-1 rounded">NEXT_PUBLIC_SUPABASE_ANON_KEY</code>, then restart Next.js.
                        </p>
                    </CardContent>
                </Card>
            </div>
        );
    }

    return (
        <div className="flex min-h-screen">
            {/* ── Left brand panel ── */}
            <div className="hidden lg:flex lg:w-[45%] flex-col justify-between bg-primary text-primary-foreground p-12">
                <div className="flex items-center gap-3">
                    <div className="flex h-9 w-9 items-center justify-center rounded-lg bg-primary-foreground/10 ring-1 ring-primary-foreground/20">
                        <ShieldCheck className="h-5 w-5" />
                    </div>
                    <span className="text-lg font-semibold tracking-tight">NYC Compliance Architect</span>
                </div>

                <div className="space-y-8">
                    <div className="space-y-3">
                        <h1 className="text-3xl font-bold leading-tight">
                            Compliance at the<br />speed of AI
                        </h1>
                        <p className="text-primary-foreground/70 text-base leading-relaxed max-w-sm">
                            Process NYC regulatory questionnaires in minutes, not days. Trusted by compliance teams across the city.
                        </p>
                    </div>

                    <ul className="space-y-3">
                        {FEATURES.map((f) => (
                            <li key={f} className="flex items-start gap-3 text-sm text-primary-foreground/80">
                                <CheckCircle2 className="h-4 w-4 mt-0.5 shrink-0 text-primary-foreground/60" />
                                {f}
                            </li>
                        ))}
                    </ul>
                </div>

                <p className="text-xs text-primary-foreground/40">
                    © {new Date().getFullYear()} NYC Compliance Architect. All rights reserved.
                </p>
            </div>

            {/* ── Right form panel ── */}
            <div className="flex flex-1 flex-col items-center justify-center bg-background px-6 py-12">
                {/* Mobile logo */}
                <div className="flex lg:hidden items-center gap-2 mb-10">
                    <div className="flex h-8 w-8 items-center justify-center rounded-md bg-primary">
                        <ShieldCheck className="h-4 w-4 text-primary-foreground" />
                    </div>
                    <span className="font-semibold text-foreground">NYC Compliance Architect</span>
                </div>

                <div className="w-full max-w-sm space-y-8">
                    <div className="space-y-1.5">
                        <h2 className="text-2xl font-bold tracking-tight text-foreground">Sign in</h2>
                        <p className="text-sm text-muted-foreground">Enter your credentials to access your workspace.</p>
                    </div>

                    <form onSubmit={handleLogin} className="space-y-5">
                        <div className="space-y-1.5">
                            <Label htmlFor="email">Email address</Label>
                            <Input
                                id="email"
                                type="email"
                                autoComplete="email"
                                required
                                placeholder="you@example.com"
                                value={email}
                                onChange={(e) => setEmail(e.target.value)}
                            />
                        </div>
                        <div className="space-y-1.5">
                            <div className="flex items-center justify-between">
                                <Label htmlFor="password">Password</Label>
                            </div>
                            <Input
                                id="password"
                                type="password"
                                autoComplete="current-password"
                                required
                                placeholder="••••••••"
                                value={password}
                                onChange={(e) => setPassword(e.target.value)}
                            />
                        </div>

                        <Button type="submit" className="w-full" disabled={loading}>
                            {loading ? (
                                <>
                                    <Loader2 className="mr-2 h-4 w-4 animate-spin" />
                                    Signing in…
                                </>
                            ) : (
                                "Sign In"
                            )}
                        </Button>
                    </form>

                    <p className="text-center text-sm text-muted-foreground">
                        Don&apos;t have an account?{" "}
                        <Link href="/signup" className="font-medium text-primary hover:underline underline-offset-4">
                            Create one
                        </Link>
                    </p>
                </div>
            </div>
        </div>
    );
}

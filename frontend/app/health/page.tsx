"use client";

import { useEffect, useMemo, useState } from "react";
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { createClient } from "@/utils/supabase/client";
import { config } from "@/lib/config";

type CheckStatus = "ok" | "warn" | "fail" | "pending";

function StatusBadge({ status }: { status: CheckStatus }) {
    const map: Record<CheckStatus, { label: string; className: string }> = {
        pending: { label: "Pending", className: "bg-slate-100 text-slate-700" },
        ok: { label: "OK", className: "bg-green-100 text-green-800" },
        warn: { label: "Warn", className: "bg-amber-100 text-amber-800" },
        fail: { label: "Fail", className: "bg-red-100 text-red-800" },
    };
    const m = map[status];
    return <Badge className={m.className}>{m.label}</Badge>;
}

export default function HealthPage() {
    const [backendStatus, setBackendStatus] = useState<CheckStatus>("pending");
    const [backendDetail, setBackendDetail] = useState<string>("");

    const [supabaseStatus, setSupabaseStatus] = useState<CheckStatus>("pending");
    const [supabaseDetail, setSupabaseDetail] = useState<string>("");

    const [sessionStatus, setSessionStatus] = useState<CheckStatus>("pending");
    const [sessionDetail, setSessionDetail] = useState<string>("");

    const missingEnv = useMemo(() => {
        const missing: string[] = [];
        if (!process.env.NEXT_PUBLIC_SUPABASE_URL?.trim()) missing.push("NEXT_PUBLIC_SUPABASE_URL");
        if (!process.env.NEXT_PUBLIC_SUPABASE_ANON_KEY?.trim()) missing.push("NEXT_PUBLIC_SUPABASE_ANON_KEY");
        return missing;
    }, []);

    const runChecks = async () => {
        // Backend
        setBackendStatus("pending");
        setBackendDetail("");
        try {
            const res = await fetch(`${config.apiUrl}/health`, { cache: "no-store" });
            if (!res.ok) {
                setBackendStatus("fail");
                setBackendDetail(`HTTP ${res.status}`);
            } else {
                const data = await res.json().catch(() => null);
                setBackendStatus("ok");
                setBackendDetail(data?.status ? `status=${data.status}` : "reachable");
            }
        } catch {
            setBackendStatus("fail");
            setBackendDetail("unreachable");
        }

        // Supabase reachability (does NOT print keys)
        setSupabaseStatus("pending");
        setSupabaseDetail("");
        try {
            const supabase = createClient();
            const { data, error } = await supabase.auth.getUser();
            if (error) {
                const msg = String(error.message || "");
                if (error.status === 401 && /invalid api key/i.test(msg)) {
                    setSupabaseStatus("fail");
                    setSupabaseDetail("Invalid API key (URL/key mismatch)");
                } else {
                    setSupabaseStatus("warn");
                    setSupabaseDetail(msg || "auth error");
                }
            } else {
                setSupabaseStatus("ok");
                setSupabaseDetail(data.user ? "session user loaded" : "no session");
            }
        } catch {
            setSupabaseStatus("fail");
            setSupabaseDetail("client init failed");
        }

        // Session validity vs backend (401 is fine if logged out)
        setSessionStatus("pending");
        setSessionDetail("");
        try {
            const supabase = createClient();
            const { data: { session } } = await supabase.auth.getSession();
            if (!session?.access_token) {
                setSessionStatus("warn");
                setSessionDetail("not signed in");
                return;
            }
            const res = await fetch(`${config.apiUrl}/orgs`, {
                headers: { Authorization: `Bearer ${session.access_token}` },
                cache: "no-store",
            });
            if (res.status === 200) {
                setSessionStatus("ok");
                setSessionDetail("backend auth ok");
            } else if (res.status === 401) {
                setSessionStatus("fail");
                setSessionDetail("backend rejected token");
            } else {
                setSessionStatus("warn");
                setSessionDetail(`backend status ${res.status}`);
            }
        } catch {
            setSessionStatus("fail");
            setSessionDetail("check failed");
        }
    };

    useEffect(() => {
        runChecks();
        // eslint-disable-next-line react-hooks/exhaustive-deps
    }, []);

    return (
        <div className="max-w-3xl mx-auto space-y-6">
            <header className="space-y-1">
                <h1 className="text-3xl font-bold tracking-tight text-slate-900">Health</h1>
                <p className="text-slate-500">Quick diagnostics for env, backend, and Supabase auth.</p>
            </header>

            <Card>
                <CardHeader>
                    <CardTitle>Frontend Env</CardTitle>
                    <CardDescription>Required public variables (keys are never displayed).</CardDescription>
                </CardHeader>
                <CardContent className="space-y-2 text-sm">
                    {missingEnv.length === 0 ? (
                        <div className="flex items-center justify-between">
                            <span>Supabase env present</span>
                            <StatusBadge status="ok" />
                        </div>
                    ) : (
                        <div className="space-y-2">
                            <div className="flex items-center justify-between">
                                <span>Missing env vars</span>
                                <StatusBadge status="fail" />
                            </div>
                            <ul className="list-disc pl-5 text-slate-700">
                                {missingEnv.map((k) => (
                                    <li key={k}><code className="font-mono">{k}</code></li>
                                ))}
                            </ul>
                        </div>
                    )}
                </CardContent>
            </Card>

            <Card>
                <CardHeader>
                    <CardTitle>Backend</CardTitle>
                    <CardDescription>Checks the API proxy to backend health endpoint.</CardDescription>
                </CardHeader>
                <CardContent className="flex items-center justify-between text-sm">
                    <div className="text-slate-700">{backendDetail || "—"}</div>
                    <StatusBadge status={backendStatus} />
                </CardContent>
            </Card>

            <Card>
                <CardHeader>
                    <CardTitle>Supabase</CardTitle>
                    <CardDescription>Checks Supabase Auth (detects invalid API key).</CardDescription>
                </CardHeader>
                <CardContent className="flex items-center justify-between text-sm">
                    <div className="text-slate-700">{supabaseDetail || "—"}</div>
                    <StatusBadge status={supabaseStatus} />
                </CardContent>
            </Card>

            <Card>
                <CardHeader>
                    <CardTitle>Session → Backend</CardTitle>
                    <CardDescription>Validates that a signed-in session can call backend with Bearer token.</CardDescription>
                </CardHeader>
                <CardContent className="flex items-center justify-between text-sm">
                    <div className="text-slate-700">{sessionDetail || "—"}</div>
                    <StatusBadge status={sessionStatus} />
                </CardContent>
            </Card>

            <div className="flex justify-end">
                <Button variant="outline" onClick={runChecks}>Re-run checks</Button>
            </div>
        </div>
    );
}


"use client";

/**
 * Phase 22 — Demo Workspace Banner
 *
 * Shows a banner at the top of authenticated pages when demo mode is active.
 * Includes a "Reset Demo Data" button (admin-only, calls POST /admin/demo-reset).
 */

import { useState } from "react";
import { RefreshCw, Beaker } from "lucide-react";
import { Button } from "@/components/ui/button";
import { isDemoMode } from "@/lib/demo-data";
import { ApiClient } from "@/lib/api";
import { createClient } from "@/utils/supabase/client";

export function DemoBanner() {
    const [resetting, setResetting] = useState(false);
    const [message, setMessage] = useState<string | null>(null);

    if (!isDemoMode()) return null;

    async function handleReset() {
        setResetting(true);
        setMessage(null);
        try {
            const supabase = createClient();
            const { data: { session } } = await supabase.auth.getSession();
            await ApiClient.resetDemoWorkspace(session?.access_token);
            setMessage("Demo data reset successfully.");
            // Reload after a brief delay so user sees the confirmation
            setTimeout(() => window.location.reload(), 1200);
        } catch (e: any) {
            setMessage(e?.message ?? "Reset failed — admin access required.");
        } finally {
            setResetting(false);
        }
    }

    return (
        <div className="flex items-center justify-between gap-3 bg-amber-50 border-b border-amber-200 px-4 py-2 text-sm text-amber-800">
            <div className="flex items-center gap-2">
                <Beaker className="h-4 w-4 shrink-0 text-amber-600" />
                <span className="font-medium">Demo Workspace</span>
                <span className="hidden sm:inline text-amber-600">
                    — Data resets automatically. Explore features freely.
                </span>
            </div>
            <div className="flex items-center gap-2">
                {message && (
                    <span className="text-xs text-amber-700">{message}</span>
                )}
                <Button
                    variant="outline"
                    size="sm"
                    onClick={handleReset}
                    disabled={resetting}
                    className="h-7 gap-1.5 text-xs border-amber-300 text-amber-800 hover:bg-amber-100"
                >
                    <RefreshCw className={`h-3 w-3 ${resetting ? "animate-spin" : ""}`} />
                    {resetting ? "Resetting…" : "Reset Demo Data"}
                </Button>
            </div>
        </div>
    );
}

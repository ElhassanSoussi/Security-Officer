"use client";

import { useEffect, useState } from "react";
import { AlertTriangle, X, Mail } from "lucide-react";
import { createClient } from "@/utils/supabase/client";
import { Button } from "@/components/ui/button";

/**
 * Email Verification Banner.
 *
 * Shows a dismissible warning banner when the current user's email
 * is not yet verified. SOC2 requires email verification enforcement.
 */
export function EmailVerificationBanner() {
    const [show, setShow] = useState(false);
    const [sending, setSending] = useState(false);
    const supabase = createClient();

    useEffect(() => {
        async function check() {
            try {
                const { data: { user } } = await supabase.auth.getUser();
                if (user && !user.email_confirmed_at) {
                    setShow(true);
                }
            } catch {
                // Ignore — user may not be logged in
            }
        }
        check();
        // eslint-disable-next-line react-hooks/exhaustive-deps
    }, []);

    const handleResend = async () => {
        setSending(true);
        try {
            const { data: { user } } = await supabase.auth.getUser();
            if (user?.email) {
                await supabase.auth.resend({ type: "signup", email: user.email });
            }
        } catch {
            // best effort
        } finally {
            setSending(false);
        }
    };

    if (!show) return null;

    return (
        <div className="relative border-b border-amber-200 bg-amber-50 px-4 py-3">
            <div className="flex items-center gap-3 max-w-7xl mx-auto">
                <AlertTriangle className="h-4 w-4 text-amber-600 shrink-0" />
                <p className="text-sm text-amber-800 flex-1">
                    <strong>Email verification required.</strong> Please verify your email address to maintain full access.
                    Some features may be restricted until verification is complete.
                </p>
                <Button
                    size="sm"
                    variant="outline"
                    className="gap-1.5 text-xs border-amber-300 text-amber-700 hover:bg-amber-100"
                    onClick={handleResend}
                    disabled={sending}
                >
                    <Mail className="h-3.5 w-3.5" />
                    {sending ? "Sending…" : "Resend Email"}
                </Button>
                <button
                    onClick={() => setShow(false)}
                    className="text-amber-500 hover:text-amber-700 transition-colors"
                    aria-label="Dismiss"
                >
                    <X className="h-4 w-4" />
                </button>
            </div>
        </div>
    );
}

"use client";

import { useEffect, useState } from "react";
import { usePathname, useRouter } from "next/navigation";
import { createClient } from "@/utils/supabase/client";

type AuthGateProps = {
    children: React.ReactNode;
};

export function AuthGate({ children }: AuthGateProps) {
    const [loading, setLoading] = useState(true);
    const [isAuthed, setIsAuthed] = useState(false);
    const router = useRouter();
    const pathname = usePathname();

    useEffect(() => {
        let mounted = true;
        const supabase = createClient();

        if (!supabase) {
            setLoading(false);
            return;
        }

        const checkSession = async () => {
            const { data: { session } } = await supabase.auth.getSession();
            if (!mounted) return;
            if (!session?.access_token) {
                setIsAuthed(false);
                setLoading(false);
                if (pathname !== "/login") {
                    router.replace("/login");
                }
                return;
            }
            setIsAuthed(true);
            setLoading(false);
        };

        checkSession();

        const { data: listener } = supabase.auth.onAuthStateChange((event: string) => {
            if (!mounted) return;
            if (event === "SIGNED_OUT") {
                setIsAuthed(false);
                router.replace("/login");
            }
        });

        return () => {
            mounted = false;
            listener.subscription.unsubscribe();
        };
    }, [pathname, router]);

    if (loading) {
        return (
            <div className="min-h-screen flex items-center justify-center bg-slate-50">
                <div className="text-sm text-slate-500">Checking session…</div>
            </div>
        );
    }

    if (!isAuthed) {
        return null;
    }

    return <>{children}</>;
}


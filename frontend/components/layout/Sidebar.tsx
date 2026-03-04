"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import {
    LayoutDashboard,
    FolderKanban,
    PlayCircle,
    ShieldCheck,
    Settings,
    FileSearch,
    LogOut,
    BrainCircuit,
    MessageSquare,
    ClipboardList,
} from "lucide-react";
import { useEffect, useState } from "react";
import { createClient } from "@/utils/supabase/client";
import { ApiClient } from "@/lib/api";
import { clearStoredOrgId, getStoredOrgId, setStoredOrgId } from "@/lib/orgContext";

export function Sidebar() {
    const pathname = usePathname();
    const [planLabel, setPlanLabel] = useState<string>("Loading...");
    const [exportsLabel, setExportsLabel] = useState<string>("—");
    const [userLabel, setUserLabel] = useState<string>("Loading account…");
    const [signingOut, setSigningOut] = useState(false);

    const links = [
        { href: "/dashboard",    label: "Dashboard",         icon: LayoutDashboard },
        { href: "/projects",     label: "Projects",          icon: FolderKanban },
        { href: "/run",          label: "Run Questionnaire", icon: PlayCircle },
        { href: "/audit",        label: "Audit Review",      icon: FileSearch },
        { href: "/activity",     label: "Activity Log",      icon: ClipboardList },
        { href: "/intelligence", label: "Intelligence",      icon: BrainCircuit },
        { href: "/assistant",    label: "Assistant",         icon: MessageSquare },
        { href: "/settings",     label: "Settings",          icon: Settings },
    ];
    // split into groups for visual separation
    const primaryLinks = links.slice(0, 7);
    const secondaryLinks = links.slice(7);

    useEffect(() => {
        async function loadBillingBadge() {
            try {
                const supabase = createClient();
                const { data: { session } } = await supabase.auth.getSession();
                const { data: { user } } = await supabase.auth.getUser();
                const email = (user?.email || "").trim();
                const fullName = String((user?.user_metadata as any)?.full_name || "").trim();
                setUserLabel(fullName || email || "Signed in");
                const token = session?.access_token;
                if (!token) {
                    setPlanLabel("Sign in");
                    setExportsLabel("—");
                    return;
                }
                const orgs = await ApiClient.getMyOrgs(token);
                if (!orgs || orgs.length === 0) {
                    setPlanLabel("No org");
                    setExportsLabel("—");
                    return;
                }
                const stored = getStoredOrgId() || "";
                const selected = orgs.find((o: any) => o.id === stored) || orgs[0];
                setStoredOrgId(selected.id);
                const sub = await ApiClient.getSubscription(selected.id, token);
                const planId = (sub?.plan_id || "starter").toString();
                const used = typeof sub?.exports_used === "number" ? sub.exports_used : 0;
                const limit = typeof sub?.exports_limit === "number" ? sub.exports_limit : 0;
                setPlanLabel(planId.toUpperCase());
                setExportsLabel(limit ? `${Math.max(0, limit - used)} left` : "—");
            } catch {
                setUserLabel("Signed in");
                setPlanLabel("—");
                setExportsLabel("—");
            }
        }

        loadBillingBadge();
    }, []);

    const handleLogout = async () => {
        if (signingOut) return;
        setSigningOut(true);
        try {
            const supabase = createClient();
            await supabase.auth.signOut();
        } catch {
            // continue with local cleanup
        } finally {
            try {
                clearStoredOrgId();
                window.localStorage.clear();
            } catch {}
            try {
                window.sessionStorage.clear();
            } catch {}
            window.location.href = "/login";
        }
    };

    return (
        <div className="hidden md:flex w-64 bg-slate-900 text-white min-h-screen flex-col fixed left-0 top-0 z-30">
            {/* Logo + descriptor */}
            <div className="p-5 border-b border-slate-800">
                <div className="flex items-center gap-2.5">
                    <div className="flex h-8 w-8 items-center justify-center rounded-lg bg-blue-500/15">
                        <ShieldCheck className="h-4.5 w-4.5 text-blue-400" />
                    </div>
                    <span className="font-semibold text-[15px] tracking-tight">NYC Compliance</span>
                </div>
                <p className="mt-1.5 text-[11px] leading-snug text-slate-500">
                    AI-powered security questionnaire automation
                </p>
            </div>

            {/* Workspace badge */}
            <div className="px-5 py-3 border-b border-slate-800">
                <p className="text-[11px] font-medium uppercase tracking-wider text-slate-500 mb-1">Workspace</p>
                <p className="text-sm text-slate-300 truncate font-medium" title={userLabel}>
                    {userLabel}
                </p>
            </div>

            <nav className="flex-1 p-3 space-y-3 overflow-y-auto">
                <div className="space-y-0.5">
                    {primaryLinks.map((link) => {
                        const Icon = link.icon;
                        const isActive = pathname === link.href || (link.href !== "/" && pathname.startsWith(link.href));

                        return (
                            <Link
                                key={link.href}
                                href={link.href}
                                className={
                                    `flex items-center gap-3 px-3 py-2 transition-colors rounded-md text-sm font-medium ${isActive
                                        ? "bg-slate-800 text-white border-l-[3px] border-blue-400 rounded-r-md pl-[9px]"
                                        : "text-slate-400 hover:text-white hover:bg-slate-800/60"
                                    }`
                                }
                            >
                                <Icon className="h-[18px] w-[18px] shrink-0" />
                                <span>{link.label}</span>
                            </Link>
                        );
                    })}
                </div>
                <div className="border-t border-slate-800 pt-3 space-y-0.5">
                    {secondaryLinks.map((link) => {
                        const Icon = link.icon;
                        const isActive = pathname === link.href || (link.href !== "/" && pathname.startsWith(link.href));
                        return (
                            <Link
                                key={link.href}
                                href={link.href}
                                className={
                                    `flex items-center gap-3 px-3 py-2 transition-colors rounded-md text-sm font-medium ${isActive
                                        ? "bg-slate-800 text-white border-l-[3px] border-blue-400 rounded-r-md pl-[9px]"
                                        : "text-slate-400 hover:text-white hover:bg-slate-800/60"
                                    }`
                                }
                            >
                                <Icon className="h-[18px] w-[18px] shrink-0" />
                                <span>{link.label}</span>
                            </Link>
                        );
                    })}
                </div>
            </nav>

            <div className="p-3 border-t border-slate-800 space-y-2.5">
                <div className="bg-slate-800/80 rounded-lg p-3">
                    <div className="flex items-end justify-between gap-2 mb-0.5">
                        <span className="text-xs font-semibold uppercase tracking-wider text-slate-500">Plan</span>
                        <span className="text-xs text-slate-400">{exportsLabel}</span>
                    </div>
                    <span className="text-sm font-semibold text-white">{planLabel}</span>
                    {planLabel !== "ELITE" && (
                        <Link href="/plans" className="block mt-1.5 text-xs text-blue-400 hover:text-blue-300">
                            View Plans &rarr;
                        </Link>
                    )}
                </div>
                <button
                    type="button"
                    onClick={handleLogout}
                    disabled={signingOut}
                    className="w-full inline-flex items-center justify-center gap-2 rounded-md border border-slate-700 bg-slate-800 px-3 py-2 text-sm font-medium text-slate-300 hover:bg-slate-700 hover:text-white disabled:opacity-60 transition-colors"
                >
                    <LogOut className="h-4 w-4" />
                    {signingOut ? "Signing out…" : "Logout"}
                </button>
            </div>
        </div>
    );
}

"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { Building2, User, Palette, Shield, BrainCircuit, CreditCard, BarChart3 } from "lucide-react";
import { cn } from "@/lib/utils";

const NAV_ITEMS = [
    { href: "/settings", label: "Organization", icon: Building2, exact: true },
    { href: "/settings/profile", label: "Profile", icon: User },
    { href: "/settings/billing", label: "Plans & Billing", icon: CreditCard },
    { href: "/settings/usage", label: "Usage", icon: BarChart3 },
    { href: "/settings/appearance", label: "Appearance", icon: Palette },
    { href: "/settings/security", label: "Security", icon: Shield },
    { href: "/settings/memory", label: "Knowledge Memory", icon: BrainCircuit },
];

export default function SettingsLayout({ children }: { children: React.ReactNode }) {
    const pathname = usePathname();

    return (
        <div className="space-y-6">
            <div>
                <h1 className="text-2xl font-semibold tracking-tight text-foreground">Settings</h1>
                <p className="text-sm text-muted-foreground mt-1">Manage your organization, profile, and preferences.</p>
            </div>

            <div className="flex flex-col md:flex-row gap-6 items-start">
                {/* Sidebar nav */}
                <nav className="w-full md:w-52 shrink-0 flex md:flex-col gap-1 overflow-x-auto md:overflow-x-visible border-b md:border-b-0 md:border-r border-border pb-2 md:pb-0 md:pr-4">
                    {NAV_ITEMS.map((item) => {
                        const Icon = item.icon;
                        const isActive = item.exact
                            ? pathname === item.href
                            : pathname.startsWith(item.href);

                        return (
                            <Link
                                key={item.href}
                                href={item.href}
                                className={cn(
                                    "flex items-center gap-2.5 rounded-md px-3 py-2 text-sm font-medium transition-colors whitespace-nowrap",
                                    isActive
                                        ? "bg-muted text-foreground"
                                        : "text-muted-foreground hover:text-foreground hover:bg-muted/50"
                                )}
                            >
                                <Icon className="h-4 w-4 shrink-0" />
                                {item.label}
                            </Link>
                        );
                    })}
                </nav>

                {/* Page content */}
                <div className="flex-1 min-w-0">
                    {children}
                </div>
            </div>
        </div>
    );
}

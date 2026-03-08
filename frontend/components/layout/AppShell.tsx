"use client";

import { usePathname } from "next/navigation";
import { Sidebar } from "@/components/layout/Sidebar";
import { AuthGate } from "@/components/auth/AuthGate";
import { AppFooter } from "@/components/layout/AppFooter";
import { ErrorBoundary } from "@/components/ui/ErrorBoundary";
import { BillingPastDueBanner } from "@/components/BillingPastDueBanner";
import { DemoBanner } from "@/components/DemoBanner";
import { TrialBanner } from "@/components/TrialBanner";
import { UpgradeModal } from "@/components/UpgradeModal";

type AppShellProps = {
    children: React.ReactNode;
};

const PUBLIC_ROUTES = new Set([
    "/",
    "/login",
    "/signup",
    "/health",
    "/contact",
    "/demo",
]);

export function AppShell({ children }: AppShellProps) {
    const pathname = usePathname();
    const isOnboardingRoute = pathname === "/onboarding";
    const isPublicRoute = PUBLIC_ROUTES.has(pathname || "");

    if (isPublicRoute) {
        return <main className="w-full min-h-screen">{children}</main>;
    }

    if (isOnboardingRoute) {
        return <AuthGate><main className="w-full min-h-screen">{children}</main></AuthGate>;
    }

    return (
        <AuthGate>
            <Sidebar />
            <div className="flex-1 md:ml-64 flex flex-col min-h-screen">
                <DemoBanner />
                <BillingPastDueBanner />
                <TrialBanner />
                <UpgradeModal />
                <main className="flex-1 px-4 py-6 md:px-8 md:py-8">
                    <div className="page-container">
                        <ErrorBoundary>{children}</ErrorBoundary>
                    </div>
                </main>
                <AppFooter />
            </div>
        </AuthGate>
    );
}

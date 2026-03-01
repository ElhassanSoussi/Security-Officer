import type { Metadata } from "next";
import "./globals.css";
import { ToastProvider } from "@/components/ui/toaster";
import { AppShell } from "@/components/layout/AppShell";
import { DevBanner } from "@/components/ui/DevBanner";
import { PlanLimitModal } from "@/components/PlanLimitModal";
import { SubscriptionInactiveModal } from "@/components/SubscriptionInactiveModal";
import { SentryInit } from "@/components/SentryInit";

import { EmailVerificationBanner } from "@/components/EmailVerificationBanner";

export const metadata: Metadata = {
    title: "NYC Compliance Architect",
    description: "Automated Compliance for Construction",
};

function getMissingPublicEnv(): string[] {
    const values: Record<string, string | undefined> = {
        NEXT_PUBLIC_SUPABASE_URL: process.env.NEXT_PUBLIC_SUPABASE_URL,
        NEXT_PUBLIC_SUPABASE_ANON_KEY: process.env.NEXT_PUBLIC_SUPABASE_ANON_KEY,
    };
    return Object.entries(values)
        .filter(([, value]) => !value || !value.trim())
        .map(([key]) => key);
}

export default function RootLayout({
    children,
}: Readonly<{
    children: React.ReactNode;
}>) {
    const missing = getMissingPublicEnv();
    if (missing.length) {
        return (
            <html lang="en">
                <body className="antialiased bg-slate-50 min-h-screen flex items-center justify-center p-6">
                    <div className="w-full max-w-xl rounded-lg border border-red-200 bg-white p-6 shadow-sm">
                        <h1 className="text-xl font-semibold text-slate-900">Configuration Error</h1>
                        <p className="mt-2 text-sm text-slate-600">
                            Missing required frontend environment variables. Set them and restart the dev server.
                        </p>
                        <ul className="mt-4 list-disc pl-5 text-sm text-slate-800">
                            {missing.map((k) => (
                                <li key={k}><code className="font-mono">{k}</code></li>
                            ))}
                        </ul>
                        <p className="mt-4 text-xs text-slate-500">
                            Note: keys are never shown here. Use the Supabase Dashboard (Project Settings &rarr; API) to copy the correct values.
                        </p>
                    </div>
                </body>
            </html>
        );
    }

    return (
        <html lang="en">
            <body className="antialiased bg-slate-50 min-h-screen">
                <DevBanner />
                <EmailVerificationBanner />
                <ToastProvider>
                    <AppShell>{children}</AppShell>
                    <PlanLimitModal />
                    <SubscriptionInactiveModal />
                    <SentryInit />
                </ToastProvider>
            </body>
        </html>
    );
}

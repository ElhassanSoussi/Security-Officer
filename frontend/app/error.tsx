"use client";

import * as React from "react";
import { ErrorBoundary } from "@/components/ui/ErrorBoundary";

export default function GlobalError({
    error,
    reset,
}: {
    error: Error & { digest?: string };
    reset: () => void;
}) {
    // Wrap Next.js route errors in our ErrorBoundary UI.
    // The ErrorBoundary's reset is internal; here we call Next's reset.
    return (
        <ErrorBoundary
            fallback={
                <div className="p-6">
                    <div className="max-w-xl mx-auto">
                        <h1 className="text-xl font-semibold">Something went wrong</h1>
                        <p className="mt-2 text-sm text-muted-foreground">
                            An unexpected error occurred. Please try again.
                        </p>
                        <button
                            className="mt-4 inline-flex items-center rounded-md border px-3 py-2 text-sm"
                            onClick={() => reset()}
                        >
                            Try again
                        </button>
                    </div>
                </div>
            }
        >
            {/* Should never render, but keeps the component tree valid */}
            <div />
        </ErrorBoundary>
    );
}

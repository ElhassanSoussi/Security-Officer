"use client";

/**
 * Sentry initialization wrapper (client component).
 * Calls initSentry() once on mount. Renders nothing.
 */

import { useEffect } from "react";
import { initSentry } from "@/lib/sentry";

export function SentryInit() {
    useEffect(() => {
        initSentry();
    }, []);
    return null;
}

/**
 * Sentry client-side initialization.
 *
 * Opt-in: only initializes when NEXT_PUBLIC_SENTRY_DSN is set.
 * Import and call `initSentry()` once in the root layout or _app.
 *
 * Captures:
 *   • Unhandled exceptions (global error handler)
 *   • Unhandled promise rejections
 *   • Manual `captureException()` calls from ApiClient
 */

let _initialized = false;

export function isSentryEnabled(): boolean {
    return typeof window !== "undefined" &&
        !!process.env.NEXT_PUBLIC_SENTRY_DSN;
}

export function initSentry(): void {
    if (_initialized || typeof window === "undefined") return;
    const dsn = process.env.NEXT_PUBLIC_SENTRY_DSN;
    if (!dsn) return;

    _initialized = true;

    // Lightweight global error capture without requiring @sentry/nextjs bundle.
    // If @sentry/nextjs is installed, its auto-init takes precedence.
    window.addEventListener("error", (event) => {
        reportToSentry("unhandled_error", {
            message: event.message,
            filename: event.filename,
            lineno: event.lineno,
            colno: event.colno,
        });
    });

    window.addEventListener("unhandledrejection", (event) => {
        reportToSentry("unhandled_rejection", {
            reason: String(event.reason).slice(0, 500),
        });
    });
}

/**
 * Lightweight Sentry-compatible error reporter.
 * Falls back to console.error if Sentry SDK is not bundled.
 */
export function reportToSentry(tag: string, context: Record<string, unknown>): void {
    try {
        // If @sentry/nextjs is installed and initialized, use it
        const Sentry = (globalThis as any).__SENTRY__;
        if (Sentry?.captureException) {
            Sentry.captureException(new Error(tag), { extra: context });
            return;
        }
    } catch {
        // ignore
    }

    // Fallback: structured console error for log aggregation
    if (process.env.NODE_ENV !== "production") {
        console.error(`[sentry:${tag}]`, context);
    }
}

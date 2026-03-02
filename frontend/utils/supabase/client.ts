import { createBrowserClient } from '@supabase/ssr'

// ---------------------------------------------------------------------------
// Validated, lazy-initialised Supabase browser client.
//
// Key design decisions:
//   1. NEVER call createBrowserClient() during SSR / build-time prerendering.
//      Next.js prerenders "use client" pages on the server — if the Supabase
//      SDK receives an empty URL it throws "Invalid supabaseUrl" which kills
//      the Vercel build.
//   2. On the client, validate env vars once, then cache the singleton.
//   3. Return `null` instead of throwing so that pages can render a graceful
//      "configuration error" UI instead of crashing.
// ---------------------------------------------------------------------------

type SupabaseBrowserClient = ReturnType<typeof createBrowserClient>;

/** Cached singleton — only populated on the client side. */
let _client: SupabaseBrowserClient | null = null;
/** Sticky error message if env vars are bad — avoids re-checking every call. */
let _initError: string | null = null;

/**
 * Read and validate a NEXT_PUBLIC_* env var.
 *
 * IMPORTANT: Next.js only inlines *statically referenced* NEXT_PUBLIC_*
 * variables into the client bundle. Dynamic `process.env[name]` does NOT work.
 * We therefore map the two known names explicitly.
 */
function readEnv(name: "NEXT_PUBLIC_SUPABASE_URL" | "NEXT_PUBLIC_SUPABASE_ANON_KEY"): string {
    const raw: Record<string, string | undefined> = {
        NEXT_PUBLIC_SUPABASE_URL: process.env.NEXT_PUBLIC_SUPABASE_URL,
        NEXT_PUBLIC_SUPABASE_ANON_KEY: process.env.NEXT_PUBLIC_SUPABASE_ANON_KEY,
    };
    return (raw[name] ?? "").trim();
}

/**
 * Attempt to normalise a Supabase URL.
 *
 * Common misconfiguration: pasting the Postgres connection string
 * (postgresql://…@db.<ref>.supabase.co:5432/postgres) instead of the
 * Supabase API URL (https://<ref>.supabase.co).
 *
 * This function detects that pattern and extracts the correct API URL.
 */
function normaliseSupabaseUrl(raw: string): { url: string; wasFixed: boolean } {
    // Already correct
    if (/^https?:\/\//i.test(raw)) {
        return { url: raw, wasFixed: false };
    }

    // Detect Postgres connection string: postgresql://…@db.<ref>.supabase.co…
    const pgMatch = raw.match(/db\.([a-z0-9]+)\.supabase\.co/i);
    if (pgMatch) {
        const ref = pgMatch[1];
        const fixed = `https://${ref}.supabase.co`;
        console.warn(
            `[supabase] NEXT_PUBLIC_SUPABASE_URL looks like a Postgres connection string. ` +
            `Auto-correcting to "${fixed}". Please fix the env var in your Vercel dashboard.`
        );
        return { url: fixed, wasFixed: true };
    }

    // Unrecognised — return as-is; validation downstream will reject it.
    return { url: raw, wasFixed: false };
}

/**
 * Return a Supabase browser client, or `null` when the required env vars are
 * missing / invalid.  Safe to call at the top of any "use client" component —
 * it will never throw and will never create a client during SSR.
 *
 * @example
 * const supabase = createClient();
 * if (!supabase) return <ConfigError />;
 */
export function createClient(): SupabaseBrowserClient | null {
    // ── SSR / prerender guard ────────────────────────────────────────────
    // During `next build` the component tree is rendered on the server.
    // We must NOT instantiate a browser client there.
    if (typeof window === "undefined") {
        return null;
    }

    // ── Return cached client / error ─────────────────────────────────────
    if (_client) return _client;
    if (_initError !== null) return null; // already failed once — don't retry

    // ── Validate env vars ────────────────────────────────────────────────
    const rawUrl = readEnv("NEXT_PUBLIC_SUPABASE_URL");
    const key = readEnv("NEXT_PUBLIC_SUPABASE_ANON_KEY");

    if (!rawUrl) {
        _initError = "Missing env var: NEXT_PUBLIC_SUPABASE_URL. Set it in your Vercel dashboard or .env.local.";
        console.error(`[supabase] ${_initError}`);
        return null;
    }
    if (!key) {
        _initError = "Missing env var: NEXT_PUBLIC_SUPABASE_ANON_KEY. Set it in your Vercel dashboard or .env.local.";
        console.error(`[supabase] ${_initError}`);
        return null;
    }

    // Normalise: auto-fix common Postgres-connection-string mistake
    const { url, wasFixed } = normaliseSupabaseUrl(rawUrl);

    if (!/^https?:\/\//i.test(url)) {
        _initError =
            `Invalid NEXT_PUBLIC_SUPABASE_URL — must start with https://. ` +
            `You appear to have set a Postgres connection string instead of the Supabase API URL. ` +
            `Go to your Supabase dashboard → Project Settings → API → "Project URL" and copy that value ` +
            `(it looks like https://xxxx.supabase.co). ` +
            `Set NEXT_PUBLIC_SUPABASE_URL and NEXT_PUBLIC_SUPABASE_ANON_KEY, then restart Next.js.`;
        console.error(`[supabase] ${_initError}`);
        return null;
    }

    if (wasFixed) {
        _initError = null; // Clear — we auto-recovered
    }

    // ── Create & cache ───────────────────────────────────────────────────
    try {
        _client = createBrowserClient(url, key);
    } catch (err: unknown) {
        _initError = err instanceof Error ? err.message : String(err);
        console.error(`[supabase] failed to create client: ${_initError}`);
        return null;
    }

    if (process.env.NODE_ENV !== "production") {
        try {
            console.info(`[supabase] connected to ${new URL(url).hostname}`);
        } catch { /* ignore */ }
    }

    return _client;
}

/**
 * Return the sticky initialisation error, if any.
 * Useful for rendering a user-visible message.
 */
export function getClientInitError(): string | null {
    return _initError;
}

import { createBrowserClient } from '@supabase/ssr'

let didLogHost = false;

function requirePublicEnv(name: "NEXT_PUBLIC_SUPABASE_URL" | "NEXT_PUBLIC_SUPABASE_ANON_KEY"): string {
    // IMPORTANT: in client bundles Next.js only inlines statically referenced
    // NEXT_PUBLIC_* variables, not dynamic process.env[name] lookups.
    const envValues = {
        NEXT_PUBLIC_SUPABASE_URL: process.env.NEXT_PUBLIC_SUPABASE_URL,
        NEXT_PUBLIC_SUPABASE_ANON_KEY: process.env.NEXT_PUBLIC_SUPABASE_ANON_KEY,
    } as const;
    const value = envValues[name];
    if (!value || !value.trim()) {
        throw new Error(`Missing required env var: ${name}`);
    }
    return value.trim();
}

export function createClient() {
    const url = requirePublicEnv("NEXT_PUBLIC_SUPABASE_URL");
    const key = requirePublicEnv("NEXT_PUBLIC_SUPABASE_ANON_KEY");

    if (process.env.NODE_ENV !== "production" && !didLogHost) {
        try {
            // Dev-only sanity log (never print the key).
            // eslint-disable-next-line no-console
            console.info(`[supabase] using ${new URL(url).hostname}`);
        } catch {
            // ignore
        }
        didLogHost = true;
    }

    return createBrowserClient(url, key);
}

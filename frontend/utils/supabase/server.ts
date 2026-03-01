import { createServerClient, type CookieOptions } from '@supabase/ssr'
import { cookies } from 'next/headers'

let didLogHost = false;

function requirePublicEnv(name: "NEXT_PUBLIC_SUPABASE_URL" | "NEXT_PUBLIC_SUPABASE_ANON_KEY"): string {
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
    const cookieStore = cookies()

    const url = requirePublicEnv("NEXT_PUBLIC_SUPABASE_URL");
    const key = requirePublicEnv("NEXT_PUBLIC_SUPABASE_ANON_KEY");

    if (process.env.NODE_ENV !== "production" && !didLogHost) {
        try {
            // eslint-disable-next-line no-console
            console.info(`[supabase] server client using ${new URL(url).hostname}`);
        } catch {
            // ignore
        }
        didLogHost = true;
    }

    return createServerClient(
        url,
        key,
        {
            cookies: {
                get(name: string) {
                    return cookieStore.get(name)?.value
                },
                set(name: string, value: string, options: CookieOptions) {
                    try {
                        cookieStore.set({ name, value, ...options })
                    } catch (error) {
                        // The `set` method was called from a Server Component.
                        // This can be ignored if you have middleware refreshing
                        // user sessions.
                    }
                },
                remove(name: string, options: CookieOptions) {
                    try {
                        cookieStore.set({ name, value: '', ...options })
                    } catch (error) {
                        // The `delete` method was called from a Server Component.
                        // This can be ignored if you have middleware refreshing
                        // user sessions.
                    }
                },
            },
        }
    )
}

import { createServerClient, type CookieOptions } from '@supabase/ssr'
import { cookies } from 'next/headers'

/**
 * Create a Supabase *server* client (for Server Components / Route Handlers).
 *
 * Returns `null` when the required NEXT_PUBLIC_SUPABASE_* env vars are missing
 * so that build-time prerendering never crashes.  Callers (e.g. the landing
 * page) already wrap this in try/catch.
 */
export function createClient() {
    const url = (process.env.NEXT_PUBLIC_SUPABASE_URL ?? "").trim();
    const key = (process.env.NEXT_PUBLIC_SUPABASE_ANON_KEY ?? "").trim();

    if (!url || !key || !/^https?:\/\//i.test(url)) {
        // Build-time prerender with missing env vars — return null, don't crash.
        return null;
    }

    const cookieStore = cookies()

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

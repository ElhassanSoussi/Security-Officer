import { type NextRequest, NextResponse } from "next/server";
import { createServerClient, type CookieOptions } from "@supabase/ssr";

export async function middleware(request: NextRequest) {
    if (!process.env.NEXT_PUBLIC_SUPABASE_URL?.trim() || !process.env.NEXT_PUBLIC_SUPABASE_ANON_KEY?.trim()) {
        return NextResponse.next();
    }

    const pathname = request.nextUrl.pathname;
    const isPublicRoute =
        pathname === "/" ||
        pathname.startsWith("/login") ||
        pathname.startsWith("/signup") ||
        pathname.startsWith("/health") ||
        pathname.startsWith("/auth") ||
        pathname.startsWith("/api");

    let response = NextResponse.next({
        request: {
            headers: request.headers,
        },
    });

    const supabase = createServerClient(
        process.env.NEXT_PUBLIC_SUPABASE_URL!,
        process.env.NEXT_PUBLIC_SUPABASE_ANON_KEY!,
        {
            cookies: {
                get(name: string) {
                    return request.cookies.get(name)?.value;
                },
                set(name: string, value: string, options: CookieOptions) {
                    request.cookies.set({ name, value, ...options });
                    response = NextResponse.next({
                        request: {
                            headers: request.headers,
                        },
                    });
                    response.cookies.set({ name, value, ...options });
                },
                remove(name: string, options: CookieOptions) {
                    request.cookies.set({ name, value: "", ...options });
                    response = NextResponse.next({
                        request: {
                            headers: request.headers,
                        },
                    });
                    response.cookies.set({ name, value: "", ...options });
                },
            },
        }
    );

    const {
        data: { user },
    } = await supabase.auth.getUser();

    if (!user && !isPublicRoute) {
        const url = request.nextUrl.clone();
        url.pathname = "/login";
        return NextResponse.redirect(url);
    }

    if (user && (pathname.startsWith("/login") || pathname.startsWith("/signup"))) {
        const url = request.nextUrl.clone();
        url.pathname = "/dashboard";
        return NextResponse.redirect(url);
    }

    // Phase 6 Part 4: Security headers
    response.headers.set("X-Content-Type-Options", "nosniff");
    response.headers.set("X-Frame-Options", "DENY");
    response.headers.set("X-XSS-Protection", "1; mode=block");
    response.headers.set("Referrer-Policy", "strict-origin-when-cross-origin");
    response.headers.set(
        "Permissions-Policy",
        "camera=(), microphone=(), geolocation=(), interest-cohort=()"
    );
    response.headers.set(
        "Strict-Transport-Security",
        "max-age=31536000; includeSubDomains"
    );

    // Phase 12 Part 9: Content Security Policy
    const supabaseUrl = process.env.NEXT_PUBLIC_SUPABASE_URL || "";
    const apiUrl = process.env.NEXT_PUBLIC_API_URL || "";
    // In production: allow the backend API origin; in dev: allow localhost WebSocket for HMR
    const isProd = process.env.NODE_ENV === "production";
    const connectExtra = isProd
        ? `https://api.nyccompliancearchitect.com https://nyccompliancearchitect.com`
        : `ws://127.0.0.1:* ws://localhost:*`;
    // If NEXT_PUBLIC_API_URL points to an external origin, include it
    const apiOrigin = apiUrl.startsWith("http") ? apiUrl.replace(/\/api\/v1\/?$/, "") : "";
    const cspDirectives = [
        "default-src 'self'",
        "script-src 'self' 'unsafe-eval' 'unsafe-inline'",
        `connect-src 'self' ${supabaseUrl} https://*.supabase.co wss://*.supabase.co ${apiOrigin} ${connectExtra}`.replace(/\s+/g, " ").trim(),
        "img-src 'self' data: blob:",
        "style-src 'self' 'unsafe-inline'",
        "font-src 'self' data:",
        "frame-ancestors 'none'",
        "base-uri 'self'",
        "form-action 'self'",
    ];
    response.headers.set("Content-Security-Policy", cspDirectives.join("; "));

    return response;
}

export const config = {
    matcher: [
        "/((?!api|_next/static|_next/image|favicon.ico|.*\\.(?:svg|png|jpg|jpeg|gif|webp)$).*)",
    ],
};


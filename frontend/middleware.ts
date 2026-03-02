import { type NextRequest, NextResponse } from "next/server";

/* ------------------------------------------------------------------ */
/*  Helpers                                                           */
/* ------------------------------------------------------------------ */

/** Security headers applied to every single response. */
function applySecurityHeaders(res: NextResponse): NextResponse {
  res.headers.set("X-Content-Type-Options", "nosniff");
  res.headers.set("X-Frame-Options", "DENY");
  res.headers.set("X-XSS-Protection", "1; mode=block");
  res.headers.set("Referrer-Policy", "strict-origin-when-cross-origin");
  res.headers.set(
    "Permissions-Policy",
    "camera=(), microphone=(), geolocation=(), interest-cohort=()"
  );
  res.headers.set(
    "Strict-Transport-Security",
    "max-age=31536000; includeSubDomains"
  );

  // Content Security Policy
  const supabaseUrl = process.env.NEXT_PUBLIC_SUPABASE_URL || "";
  const apiUrl = process.env.NEXT_PUBLIC_API_URL || "";
  const isProd = process.env.NODE_ENV === "production";
  const connectExtra = isProd
    ? "https://api.nyccompliancearchitect.com https://nyccompliancearchitect.com"
    : "ws://127.0.0.1:* ws://localhost:*";
  const apiOrigin = apiUrl.startsWith("http")
    ? apiUrl.replace(/\/api\/v1\/?$/, "")
    : "";
  const csp = [
    "default-src 'self'",
    "script-src 'self' 'unsafe-eval' 'unsafe-inline'",
    `connect-src 'self' ${supabaseUrl} https://*.supabase.co wss://*.supabase.co ${apiOrigin} ${connectExtra}`
      .replace(/\s+/g, " ")
      .trim(),
    "img-src 'self' data: blob:",
    "style-src 'self' 'unsafe-inline'",
    "font-src 'self' data:",
    "frame-ancestors 'none'",
    "base-uri 'self'",
    "form-action 'self'",
  ];
  res.headers.set("Content-Security-Policy", csp.join("; "));

  return res;
}

/** Check whether ANY Supabase auth cookie is present. */
function hasAuthCookie(request: NextRequest): boolean {
  // Supabase stores auth tokens in cookies named `sb-<ref>-auth-token`
  // (plus chunked variants `sb-<ref>-auth-token.0`, `.1`, …).
  const allCookies = request.cookies.getAll();
  return allCookies.some((c) => /^sb-.+-auth-token/.test(c.name));
}

const PUBLIC_PREFIXES = [
  "/login",
  "/signup",
  "/health",
  "/auth",
  "/api",
  "/contact",
  "/security",
  "/plans",
];

function isPublicRoute(pathname: string): boolean {
  if (pathname === "/") return true;
  return PUBLIC_PREFIXES.some((p) => pathname.startsWith(p));
}

/* ------------------------------------------------------------------ */
/*  Middleware                                                         */
/* ------------------------------------------------------------------ */

export async function middleware(request: NextRequest) {
  // ── Nuclear try/catch — never crash, never 500 ──────────────────
  try {
    const pathname = request.nextUrl.pathname;

    // ── Fast path: env vars missing → pass through ────────────────
    if (
      !process.env.NEXT_PUBLIC_SUPABASE_URL?.trim() ||
      !process.env.NEXT_PUBLIC_SUPABASE_ANON_KEY?.trim()
    ) {
      return applySecurityHeaders(NextResponse.next());
    }

    // ── Fast path: public route + no auth cookie → skip Supabase ──
    if (isPublicRoute(pathname) && !hasAuthCookie(request)) {
      return applySecurityHeaders(NextResponse.next());
    }

    // ── We need Supabase auth state — dynamic import ──────────────
    let user: { id: string } | null = null;

    try {
      const { createServerClient } = await import("@supabase/ssr");

      let response = NextResponse.next({
        request: { headers: request.headers },
      });

      const supabase = createServerClient(
        process.env.NEXT_PUBLIC_SUPABASE_URL!,
        process.env.NEXT_PUBLIC_SUPABASE_ANON_KEY!,
        {
          cookies: {
            get(name: string) {
              return request.cookies.get(name)?.value;
            },
            set(name: string, value: string, options: Record<string, unknown>) {
              request.cookies.set({ name, value, ...(options as any) });
              response = NextResponse.next({
                request: { headers: request.headers },
              });
              response.cookies.set({ name, value, ...(options as any) });
            },
            remove(name: string, options: Record<string, unknown>) {
              request.cookies.set({ name, value: "", ...(options as any) });
              response = NextResponse.next({
                request: { headers: request.headers },
              });
              response.cookies.set({ name, value: "", ...(options as any) });
            },
          },
        }
      );

      const { data } = await supabase.auth.getUser();
      user = data?.user ?? null;

      // ── Redirect: unauthenticated → /login ────────────────────
      if (!user && !isPublicRoute(pathname)) {
        const url = request.nextUrl.clone();
        url.pathname = "/login";
        return applySecurityHeaders(NextResponse.redirect(url));
      }

      // ── Redirect: authenticated → /dashboard ──────────────────
      if (
        user &&
        (pathname.startsWith("/login") || pathname.startsWith("/signup"))
      ) {
        const url = request.nextUrl.clone();
        url.pathname = "/dashboard";
        return applySecurityHeaders(NextResponse.redirect(url));
      }

      // ── Normal response (cookies may have been refreshed) ─────
      return applySecurityHeaders(response);
    } catch {
      // Supabase SDK or network failure — treat as "unknown auth".
      // Public routes → pass through; protected → pass through too
      // (the page itself will re-check auth and redirect client-side).
      return applySecurityHeaders(NextResponse.next());
    }
  } catch {
    // Absolute last resort — something truly unexpected.
    // Return a bare next() so the site stays up.
    try {
      return applySecurityHeaders(NextResponse.next());
    } catch {
      return NextResponse.next();
    }
  }
}

export const config = {
  matcher: [
    /*
     * Match all request paths EXCEPT:
     *  - api        (API routes)
     *  - _next/*    (Next.js internals)
     *  - favicon.ico
     *  - static assets (.svg, .png, .jpg, .jpeg, .gif, .webp, .ico)
     */
    "/((?!api|_next/static|_next/image|favicon\\.ico|.*\\.(?:svg|png|jpg|jpeg|gif|webp|ico)$).*)",
  ],
};


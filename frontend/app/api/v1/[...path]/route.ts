import { NextRequest, NextResponse } from "next/server";

export const runtime = "nodejs";
export const dynamic = "force-dynamic";

// Allow uploads up to 15 MB through the proxy (backend enforces its own 10 MB cap)
export const maxDuration = 120; // seconds — analysis can take a while

function getBackendBaseUrl(): string {
    // BACKEND_INTERNAL_URL should be the Render backend origin, e.g.
    //   https://security-officer.onrender.com
    // It MUST NOT include /api/v1 — the proxy appends it below.
    // Safety: strip trailing slashes AND any accidental /api/v1 suffix.
    let configured = (
        process.env.BACKEND_INTERNAL_URL || "http://localhost:8000"
    ).trim().replace(/\/+$/, "");

    // Auto-strip /api/v1 suffix if someone accidentally included it
    if (/\/api\/v\d+$/i.test(configured)) {
        configured = configured.replace(/\/api\/v\d+$/i, "");
    }

    return configured;
}

async function forward(request: NextRequest, path: string[]) {
    const backendBase = getBackendBaseUrl();
    const upstreamUrl = `${backendBase}/api/v1/${path.join("/")}${request.nextUrl.search}`;

    const headers = new Headers(request.headers);
    headers.delete("host");
    headers.delete("connection");
    headers.delete("accept-encoding");

    const init: RequestInit = {
        method: request.method,
        headers,
        redirect: "manual",
    };

    if (!["GET", "HEAD"].includes(request.method)) {
        const body = await request.arrayBuffer();
        const buf = Buffer.from(body);
        init.body = buf;
        // Preserve accurate content-length so the backend can parse multipart bodies
        headers.set("content-length", String(buf.byteLength));
    }

    let upstream: Response;
    try {
        upstream = await fetch(upstreamUrl, init);
    } catch (err) {
        console.error(`[proxy] Backend unreachable at ${upstreamUrl}:`, err);
        return NextResponse.json(
            {
                detail: "Backend API is unreachable. Check BACKEND_INTERNAL_URL env var.",
                target: process.env.NODE_ENV !== "production" ? upstreamUrl : undefined,
            },
            { status: 502 }
        );
    }

    // Buffer the upstream body instead of streaming. Streaming ReadableStream
    // through Vercel serverless can produce "Decoding failed" when the body
    // encoding (e.g. chunked transfer) doesn't survive the relay intact.
    const body = await upstream.arrayBuffer();

    const responseHeaders = new Headers(upstream.headers);
    // Remove hop-by-hop / encoding headers that don't apply after buffering
    responseHeaders.delete("content-encoding");
    responseHeaders.delete("transfer-encoding");
    responseHeaders.set("content-length", String(body.byteLength));

    return new NextResponse(body, {
        status: upstream.status,
        headers: responseHeaders,
    });
}

type RouteContext = {
    params: {
        path: string[];
    };
};

export async function GET(request: NextRequest, context: RouteContext) {
    return forward(request, context.params.path || []);
}

export async function POST(request: NextRequest, context: RouteContext) {
    return forward(request, context.params.path || []);
}

export async function PATCH(request: NextRequest, context: RouteContext) {
    return forward(request, context.params.path || []);
}

export async function PUT(request: NextRequest, context: RouteContext) {
    return forward(request, context.params.path || []);
}

export async function DELETE(request: NextRequest, context: RouteContext) {
    return forward(request, context.params.path || []);
}

export async function OPTIONS(request: NextRequest, context: RouteContext) {
    return forward(request, context.params.path || []);
}

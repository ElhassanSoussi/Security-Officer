import { NextRequest, NextResponse } from "next/server";

export const runtime = "nodejs";
export const dynamic = "force-dynamic";

// Allow uploads up to 15 MB through the proxy (backend enforces its own 10 MB cap)
export const maxDuration = 120; // seconds — analysis can take a while

function getBackendBaseUrl(): string {
    const configured = process.env.BACKEND_INTERNAL_URL || "http://localhost:8000";
    return configured.replace(/\/+$/, "");
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
        console.error("[proxy] Backend unreachable:", err);
        return NextResponse.json(
            { detail: "Backend API is unreachable. Verify backend is running on port 8000." },
            { status: 502 }
        );
    }

    const responseHeaders = new Headers(upstream.headers);
    responseHeaders.delete("content-length");

    return new NextResponse(upstream.body, {
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

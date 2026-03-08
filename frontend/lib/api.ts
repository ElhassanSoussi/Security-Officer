import { Run, Project, DashboardStats, ProjectOverview, OnboardingState } from "@/types";
import { createClient } from "@/utils/supabase/client";
import { config } from "@/lib/config";
export type { Run, Project, DashboardStats };

const API_BASE = config.apiUrl;

export interface AccountProfile {
    user_id: string;
    email: string | null;
    display_name: string | null;
    public_email: string | null;
    avatar_url: string | null;
    theme_preference: "light" | "dark" | "system";
}

export class ApiClient {
    private static didRedirectUnauthorized = false;
    private static nonRetryable5xxCodes = new Set([
        "billing_disabled",
        "billing_not_configured",
        "billing_schema_missing",
    ]);

    private static sleep(ms: number) {
        return new Promise((resolve) => setTimeout(resolve, ms));
    }

    private static redirectToLoginOnce() {
        if (typeof window === "undefined") return;
        if (this.didRedirectUnauthorized) return;
        this.didRedirectUnauthorized = true;
        try {
            // Best-effort: allow UI to show a friendly banner after redirect.
            window.sessionStorage.setItem("nyccompliance:auth:redirected", String(Date.now()));
        } catch {
            // ignore
        }
        window.location.href = "/login?reason=session_expired";
    }

    private static async refreshAccessToken(): Promise<string | undefined> {
        try {
            const supabase = createClient();
            if (!supabase) return undefined;
            const { data, error } = await supabase.auth.refreshSession();
            if (error) return undefined;
            return data.session?.access_token || undefined;
        } catch {
            return undefined;
        }
    }

    public static async fetch<T>(
        endpoint: string,
        options: RequestInit = {},
        token?: string,
        allowRetry: boolean = true,
        retry5xxAttempt: number = 0
    ): Promise<T> {
        const headers: Record<string, string> = {
            ...(options.headers as Record<string, string>) || {},
        };

        const method = (options.method || "GET").toUpperCase();
        const isSafeGet = method === "GET";

        let authToken = token;
        if (!authToken) {
            // Fallback: pull current Supabase session if caller omitted token.
            try {
                const supabase = createClient();
                const { data: { session } } = await supabase.auth.getSession();
                authToken = session?.access_token || undefined;
            } catch {
                authToken = undefined;
            }
        }

        if (authToken) {
            headers["Authorization"] = `Bearer ${authToken.trim()}`;
        }

        // Also support JSON body by default if method is POST/PUT/PATCH
        if (options.method && ["POST", "PUT", "PATCH"].includes(options.method) && !(options.body instanceof FormData)) {
            headers["Content-Type"] = "application/json";
        }

        let res: Response;
        try {
            res = await fetch(`${API_BASE}${endpoint}`, { ...options, headers });
        } catch {
            throw new Error("API connection failed. Backend may be offline.");
        }

        // Guard: detect HTML responses (e.g. Vercel Deployment Protection auth page)
        // before attempting JSON parse, to produce a clear error instead of "Decoding failed".
        const contentType = (res.headers.get("content-type") || "").toLowerCase();
        if (
            contentType.includes("text/html") &&
            !contentType.includes("application/json")
        ) {
            const htmlSnippet = (await res.clone().text()).slice(0, 500);
            const isDeployProtection =
                htmlSnippet.includes("Deployment Protection") ||
                htmlSnippet.includes("Authentication Required") ||
                htmlSnippet.includes("vercel.com");
            if (isDeployProtection) {
                throw new Error(
                    "API Error: Vercel Deployment Protection is blocking requests. " +
                    "Ask the admin to disable it or deploy to Production."
                );
            }
            throw new Error(
                `API Error: Expected JSON but received HTML (${res.status} ${res.statusText}). ` +
                "The backend may be misconfigured or unreachable."
            );
        }

        // Transient backend failures: retry safe GETs with exponential backoff.
        // Do not retry known product-state errors (e.g. billing disabled) because
        // they are deterministic and retries only create noise.
        if (res.status >= 500 && isSafeGet && retry5xxAttempt < 2) {
            let nonRetryable = false;
            try {
                const clone = res.clone();
                const contentType = clone.headers.get("content-type") || "";
                if (contentType.includes("application/json")) {
                    const err = await clone.json();
                    const code = String(err?.error || "").trim();
                    if (this.nonRetryable5xxCodes.has(code)) {
                        nonRetryable = true;
                    }
                }
            } catch {
                // ignore parse issues and keep default retry behavior
            }
            if (!nonRetryable) {
                const delayMs = 250 * Math.pow(2, retry5xxAttempt) + Math.floor(Math.random() * 125);
                await this.sleep(delayMs);
                return this.fetch<T>(endpoint, options, authToken, allowRetry, retry5xxAttempt + 1);
            }
        }

        if (!res.ok) {
            let detail = `${res.status} ${res.statusText}`;
            let code: string | undefined;
            let rawDetail: any = undefined;
            const requestId = res.headers.get("X-Request-Id") || undefined;
            try {
                const err = await res.json();
                code = err?.error;
                rawDetail = err?.detail;
                // detail may be a nested object (e.g. PLAN_LIMIT_REACHED) or a string
                if (rawDetail && typeof rawDetail === "object") {
                    code = rawDetail.error || code;
                    detail = rawDetail.detail || rawDetail.message || detail;
                } else {
                    detail = err?.message || rawDetail || detail;
                }
            } catch {
                // Keep default detail when body is not JSON.
            }

            // Handle plan limit exceeded — fire global event for modal
            if (res.status === 402 && code === "PLAN_LIMIT_REACHED" && typeof window !== "undefined") {
                const planLimitDetail = rawDetail && typeof rawDetail === "object" ? rawDetail : { error: "PLAN_LIMIT_REACHED" };
                window.dispatchEvent(new CustomEvent("plan:limit_reached", { detail: planLimitDetail }));
            }

            // Handle 403 plan_limit_exceeded — fire upgrade modal event
            if (res.status === 403 && code === "plan_limit_exceeded" && typeof window !== "undefined") {
                const limitDetail = rawDetail && typeof rawDetail === "object" ? rawDetail : { error: "plan_limit_exceeded" };
                window.dispatchEvent(new CustomEvent("plan:limit_exceeded", { detail: limitDetail }));
            }

            // Handle subscription inactive — fire global event for blocking modal
            if (res.status === 402 && code === "SUBSCRIPTION_INACTIVE" && typeof window !== "undefined") {
                const subDetail = rawDetail && typeof rawDetail === "object" ? rawDetail : { error: "SUBSCRIPTION_INACTIVE" };
                window.dispatchEvent(new CustomEvent("subscription:inactive", { detail: subDetail }));
            }

            if (res.status === 401) {
                if (allowRetry) {
                    const refreshedToken = await this.refreshAccessToken();
                    if (refreshedToken && refreshedToken !== authToken) {
                        return this.fetch<T>(endpoint, options, refreshedToken, false, retry5xxAttempt);
                    }
                }
                // Avoid hammering APIs in a 401 loop.
                this.redirectToLoginOnce();
                throw new Error("Unauthorized");
            }
            const error = new Error(detail.startsWith("API Error:") ? detail : `API Error: ${detail}`);
            (error as any).requestId = requestId;
            (error as any).code = code;
            throw error;
        }
        return res.json();
    }

    // --- Generic Utils ---
    static async post<T>(endpoint: string, body: any, token?: string): Promise<T> {
        return this.fetch<T>(endpoint, {
            method: "POST",
            body: JSON.stringify(body)
        }, token);
    }

    // --- Generic Helpers ---
    static async patch<T>(endpoint: string, body: any, token?: string): Promise<T> {
        return this.fetch<T>(endpoint, {
            method: "PATCH",
            body: JSON.stringify(body)
        }, token);
    }

    static async delete<T>(endpoint: string, token?: string): Promise<T> {
        return this.fetch<T>(endpoint, { method: "DELETE" }, token);
    }

    // --- Auth & Orgs ---
    static async getMyOrgs(token?: string): Promise<any[]> {
        return this.fetch("/orgs", {}, token);
    }

    static async getCurrentOrg(token?: string, preferOrgId?: string): Promise<any> {
        const params = new URLSearchParams();
        if (preferOrgId) params.append("prefer_org_id", preferOrgId);
        const q = params.toString();
        return this.fetch(`/orgs/current${q ? `?${q}` : ""}`, {}, token);
    }

    static async createOrg(
        name: string,
        token?: string,
        options?: { trade_type?: string; company_size?: string }
    ): Promise<any> {
        const payload: Record<string, any> = { name };
        if (options?.trade_type) payload.trade_type = options.trade_type;
        if (options?.company_size) payload.company_size = options.company_size;
        return this.fetch("/orgs", {
            method: "POST",
            body: JSON.stringify(payload)
        }, token);
    }

    static async onboardOrg(token?: string): Promise<any> {
        return this.post<any>("/orgs/onboard", {}, token);
    }

    // --- Runs & Projects ---
    static async getRuns(orgId: string, projectId?: string, limit: number = 50, token?: string): Promise<Run[]> {
        const params = new URLSearchParams();
        params.append("org_id", orgId);
        if (projectId) params.append("project_id", projectId);
        params.append("limit", limit.toString());

        return this.fetch<Run[]>(`/runs?${params.toString()}`, {}, token);
    }

    static async getRun(runId: string, token?: string): Promise<Run> {
        return this.fetch<Run>(`/runs/${runId}`, {}, token);
    }

    static async getRunAudits(runId: string, token?: string): Promise<any[]> {
        return this.fetch<any[]>(`/runs/${runId}/audits`, {}, token);
    }

    static async updateAudit(runId: string, auditId: string, answerText: string, token?: string): Promise<any> {
        return this.patch<any>(`/runs/${runId}/audits/${auditId}`, { answer_text: answerText }, token);
    }

    static async getProjects(orgId: string, token?: string): Promise<Project[]> {
        const params = new URLSearchParams();
        params.append("org_id", orgId);
        return this.fetch<Project[]>(`/projects?${params.toString()}`, {}, token);
    }

    static async getProject(projectId: string, token?: string): Promise<Project> {
        return this.fetch<Project>(`/projects/${projectId}`, {}, token);
    }

    static async createProject(
        orgId: string,
        name: string,
        description?: string,
        token?: string
    ): Promise<Project> {
        return this.fetch<Project>("/projects", {
            method: "POST",
            body: JSON.stringify({
                org_id: orgId,
                name,
                description
            })
        }, token);
    }

    static async updateProject(
        projectId: string,
        payload: { name?: string; description?: string; status?: string },
        token?: string
    ): Promise<Project> {
        return this.fetch<Project>(`/projects/${projectId}`, {
            method: "PATCH",
            body: JSON.stringify(payload)
        }, token);
    }

    static async getStats(orgId: string, token?: string): Promise<DashboardStats> {
        try {
            const params = new URLSearchParams();
            params.append("org_id", orgId);
            return await this.fetch<DashboardStats>(`/runs/stats?${params.toString()}`, {}, token);
        } catch (e: any) {
            if (String(e?.message || "").toLowerCase().includes("unauthorized")) {
                throw e;
            }
            return { active_projects: 0, documents_ingested: 0, runs_completed: 0 };
        }
    }

    static async getActivities(orgId: string, limit: number = 20, token?: string): Promise<any[]> {
        const params = new URLSearchParams();
        params.append("org_id", orgId);
        params.append("limit", limit.toString());
        try {
            return await this.fetch<any[]>(`/runs/activities?${params.toString()}`, {}, token);
        } catch (e: any) {
            if (String(e?.message || "").toLowerCase().includes("unauthorized")) {
                throw e;
            }
            return [];
        }
    }

    // --- Document Upload ---
    static async uploadDocument(
        file: File,
        orgId: string,
        projectId?: string,
        scope: "LOCKER" | "PROJECT" | "NYC_GLOBAL" = "PROJECT",
        token?: string
    ): Promise<any> {
        const formData = new FormData();
        formData.append("file", file);
        formData.append("org_id", orgId);
        if (projectId) formData.append("project_id", projectId);
        formData.append("scope", scope);

        // We use raw fetch here because of FormData special handling, but need headers
        const headers: HeadersInit = {};
        let authToken = token;
        if (!authToken) {
            try {
                const supabase = createClient();
                const { data: { session } } = await supabase.auth.getSession();
                authToken = session?.access_token || undefined;
            } catch {
                authToken = undefined;
            }
        }
        if (authToken) headers["Authorization"] = `Bearer ${authToken}`;

        const res = await fetch(`${API_BASE}/ingest`, {
            method: "POST",
            body: formData,
            headers
        });

        if (!res.ok) {
            let detail: any = null;
            try { detail = await res.json(); } catch { /* ignore */ }
            // Fire upgrade modal on plan limit
            if (res.status === 403 && detail?.detail?.error === "plan_limit_exceeded" && typeof window !== "undefined") {
                window.dispatchEvent(new CustomEvent("plan:limit_exceeded", { detail: detail.detail }));
            }
            throw new Error(`Upload Failed: ${detail?.detail?.message || detail?.message || res.statusText}`);
        }
        return res.json();
    }

    // --- Project Documents ---
    static async getDocuments(orgId: string, projectId?: string | null, token?: string): Promise<any[]> {
        let url = `/documents?org_id=${orgId}`;
        if (projectId) url += `&project_id=${projectId}`;
        return this.fetch(url, {}, token);
    }

    // --- Project Documents (per-project helpers) ---
    static async getProjectDocuments(projectId: string, token?: string): Promise<any[]> {
        return this.fetch<any[]>(`/projects/${projectId}/documents`, {}, token);
    }

    static async uploadProjectDocument(
        projectId: string,
        file: File,
        token?: string
    ): Promise<any> {
        const formData = new FormData();
        formData.append("file", file);

        const headers: HeadersInit = {};
        let authToken = token;
        if (!authToken) {
            try {
                const supabase = createClient();
                const { data: { session } } = await supabase.auth.getSession();
                authToken = session?.access_token || undefined;
            } catch {
                authToken = undefined;
            }
        }
        if (authToken) headers["Authorization"] = `Bearer ${authToken}`;

        const res = await fetch(`${API_BASE}/projects/${projectId}/documents`, {
            method: "POST",
            body: formData,
            headers,
        });

        if (!res.ok) {
            let detail = res.statusText;
            let parsed: any = null;
            try {
                parsed = await res.json();
                detail = parsed?.detail?.message || parsed?.detail || detail;
            } catch { /* ignore */ }
            // Fire upgrade modal on plan limit
            if (res.status === 403 && parsed?.detail?.error === "plan_limit_exceeded" && typeof window !== "undefined") {
                window.dispatchEvent(new CustomEvent("plan:limit_exceeded", { detail: parsed.detail }));
            }
            throw new Error(`Upload Failed: ${detail}`);
        }
        return res.json();
    }

    static async deleteProjectDocument(
        projectId: string,
        documentId: string,
        token?: string
    ): Promise<any> {
        return this.delete<any>(`/projects/${projectId}/documents/${documentId}`, token);
    }

    static async downloadRun(runId: string, filename: string = "export.xlsx", token?: string): Promise<void> {
        const headers: HeadersInit = {};
        let authToken = token;
        if (!authToken) {
            try {
                const supabase = createClient();
                const { data: { session } } = await supabase.auth.getSession();
                authToken = session?.access_token || undefined;
            } catch {
                authToken = undefined;
            }
        }
        if (authToken) headers["Authorization"] = `Bearer ${authToken}`;

        const res = await fetch(`${API_BASE}/runs/${runId}/download`, { headers });

        if (!res.ok) {
            let body: any = null;
            try {
                body = await res.json();
            } catch {}

            const code = body?.error;
            const message = body?.message || res.statusText || "Download failed";

            if (res.status === 404 && code === "export_missing") {
                throw Object.assign(new Error("No export generated yet. Click Generate Export."), { code });
            }
            if (res.status === 409 && code === "export_not_ready") {
                throw Object.assign(new Error("Export not ready. Try again in a moment."), { code });
            }
            throw Object.assign(new Error(message), { code });
        }

        await this._handleBlobDownload(res, filename);
    }

    static async generateExport(
        file: File,
        answers: any[],
        orgId: string,
        projectId?: string,
        runId?: string,
        token?: string
    ): Promise<void> {
        const formData = new FormData();
        formData.append("file", file);
        formData.append("answers_json", JSON.stringify(answers));
        formData.append("org_id", orgId);
        if (projectId) formData.append("project_id", projectId);
        if (runId) formData.append("run_id", runId);

        const headers: HeadersInit = {};
        let authToken = token;
        if (!authToken) {
            try {
                const supabase = createClient();
                const { data: { session } } = await supabase.auth.getSession();
                authToken = session?.access_token || undefined;
            } catch {
                authToken = undefined;
            }
        }
        if (authToken) headers["Authorization"] = `Bearer ${authToken}`;

        const res = await fetch(`${API_BASE}/generate-excel`, {
            method: "POST",
            body: formData,
            headers
        });

        if (!res.ok) {
            let errorMsg = "Export generation failed";
            try {
                const errorData = await res.json();
                if (errorData.detail) errorMsg = `Export Failed: ${errorData.detail}`;
            } catch {
                // If JSON parsing fails, use status text
                errorMsg = `Export Failed: ${res.statusText} (${res.status})`;
            }
            throw new Error(errorMsg);
        }

        await this._handleBlobDownload(res, `filled_${file.name}`);
    }

    private static async _handleBlobDownload(res: Response, filename: string) {
        const blob = await res.blob();
        const url = window.URL.createObjectURL(blob);
        const a = document.createElement("a");
        a.href = url;
        a.download = filename;
        document.body.appendChild(a);
        a.click();
        window.URL.revokeObjectURL(url);
        document.body.removeChild(a);
    }

    static async downloadSampleQuestionnaire(): Promise<void> {
        const res = await fetch(`${API_BASE}/runs/samples/questionnaire`);
        if (!res.ok) throw new Error("Sample download failed");

        const blob = await res.blob();
        const url = window.URL.createObjectURL(blob);
        const a = document.createElement("a");
        a.href = url;
        a.download = "Sample_Questionnaire.xlsx";
        document.body.appendChild(a);
        a.click();
        window.URL.revokeObjectURL(url);
        document.body.removeChild(a);
    }

    // --- Settings: Profile & Org ---
    static async getProfile(token?: string): Promise<any> {
        return this.fetch<any>("/settings/profile", {}, token);
    }

    static async updateProfile(payload: { full_name?: string; phone?: string; title?: string }, token?: string): Promise<any> {
        return this.fetch<any>("/settings/profile", {
            method: "PUT",
            body: JSON.stringify(payload),
        }, token);
    }

    static async getOrgSettings(orgId: string, token?: string): Promise<any> {
        const params = new URLSearchParams({ org_id: orgId });
        return this.fetch<any>(`/settings/org?${params.toString()}`, {}, token);
    }

    static async updateOrgSettings(orgId: string, payload: Record<string, any>, token?: string): Promise<any> {
        const params = new URLSearchParams({ org_id: orgId });
        return this.patch<any>(`/settings/org?${params.toString()}`, payload, token);
    }

    static async inviteMember(orgId: string, email: string, role: string, token?: string): Promise<any> {
        return this.post<any>("/settings/org/invite", { org_id: orgId, email, role }, token);
    }

    static async removeMember(orgId: string, userId: string, token?: string): Promise<any> {
        const params = new URLSearchParams({ org_id: orgId });
        return this.delete<any>(`/settings/org/members/${userId}?${params.toString()}`, token);
    }

    // --- Stripe Billing ---
    static async getPlans(token?: string): Promise<any[]> {
        return this.fetch<any[]>("/billing/plans", {}, token);
    }

    static async getSubscription(orgId: string, token?: string): Promise<any> {
        const params = new URLSearchParams();
        params.append("org_id", orgId);
        return this.fetch<any>(`/billing/subscription?${params.toString()}`, {}, token);
    }

    static async getBillingSummary(orgId: string, token?: string): Promise<{
        plan: string;
        subscription_status: string;
        stripe_price_id: string | null;
        current_period_end: string | null;
        billing_configured: boolean;
        has_stripe: boolean;
        usage: {
            documents_used: number;
            documents_limit: number | null;
            projects_used: number;
            projects_limit: number | null;
            runs_used: number;
            runs_limit: number | null;
        };
    }> {
        const params = new URLSearchParams({ org_id: orgId });
        try {
            return await this.fetch(`/billing/billing-summary?${params}`, {}, token);
        } catch (e: any) {
            if (String(e?.message || "").toLowerCase().includes("unauthorized")) throw e;
            return {
                plan: "starter",
                subscription_status: "trialing",
                stripe_price_id: null,
                current_period_end: null,
                billing_configured: false,
                has_stripe: false,
                usage: {
                    documents_used: 0, documents_limit: 25,
                    projects_used: 0, projects_limit: 5,
                    runs_used: 0, runs_limit: 10,
                },
            };
        }
    }

    /** Legacy entitlements-based summary used by the Plans page. */
    static async getEntitlementsSummary(orgId: string, token?: string): Promise<any> {
        const params = new URLSearchParams({ org_id: orgId });
        return this.fetch<any>(`/billing/summary?${params.toString()}`, {}, token);
    }

    static async createCheckoutSession(orgId: string, planTier: string, token?: string): Promise<{ url: string }> {
        return this.post<{ url: string }>("/billing/create-checkout-session", {
            org_id: orgId,
            plan_tier: planTier,
        }, token);
    }

    static async createPortalSession(orgId: string, token?: string): Promise<{ url: string }> {
        return this.post<{ url: string }>(`/billing/portal?org_id=${orgId}`, {}, token);
    }

    static async createPortalSessionV2(orgId: string, token?: string): Promise<{ url: string }> {
        return this.post<{ url: string }>("/billing/portal-session", { org_id: orgId }, token);
    }

    static async createStripeCheckout(
        orgId: string,
        planName: "starter" | "growth" | "elite",
        token?: string,
    ): Promise<{ url: string; plan_name: string }> {
        return this.post<{ url: string; plan_name: string }>("/billing/checkout", {
            org_id: orgId,
            plan_name: planName,
        }, token);
    }

    static async getSubscriptionStatus(orgId: string, token?: string): Promise<{
        org_id: string;
        plan_name: string;
        stripe_status: string | null;
        stripe_customer_id: string | null;
        stripe_subscription_id: string | null;
        current_period_end: string | null;
        is_active: boolean;
    }> {
        const params = new URLSearchParams({ org_id: orgId });
        try {
            return await this.fetch(`/billing/status?${params}`, {}, token);
        } catch (e: any) {
            if (String(e?.message || "").toLowerCase().includes("unauthorized")) throw e;
            return {
                org_id: orgId,
                plan_name: "FREE",
                stripe_status: null,
                stripe_customer_id: null,
                stripe_subscription_id: null,
                current_period_end: null,
                is_active: true,
            };
        }
    }

    static async startProTrial(orgId: string, token?: string): Promise<any> {
        return this.post<any>(`/billing/trial?org_id=${orgId}`, {}, token);
    }

    // --- Usage Summary ---
    static async getUsageSummary(orgId: string, token?: string): Promise<{
        runs_this_month: number;
        documents_total: number;
        memory_entries_total: number;
        evidence_exports_total: number;
        plan: string;
        limits: {
            plan_name: string;
            max_runs_per_month: number;
            max_documents: number;
            max_memory_entries: number;
        };
    }> {
        const params = new URLSearchParams({ org_id: orgId });
        try {
            return await this.fetch(`/runs/usage?${params.toString()}`, {}, token);
        } catch (e: any) {
            if (String(e?.message || "").toLowerCase().includes("unauthorized")) throw e;
            return {
                runs_this_month: 0,
                documents_total: 0,
                memory_entries_total: 0,
                evidence_exports_total: 0,
                plan: "FREE",
                limits: { plan_name: "FREE", max_runs_per_month: 10, max_documents: 25, max_memory_entries: 100 },
            };
        }
    }

    // --- Account Usage Dashboard ---
    static async getAccountUsage(orgId?: string, token?: string): Promise<{
        plan: string;
        limits: { projects: number; documents: number; runs: number };
        usage: { projects: number; documents: number; runs: number };
        percent: { projects: number; documents: number; runs: number };
        next_plan: string | null;
    }> {
        const params = new URLSearchParams();
        if (orgId) params.set("org_id", orgId);
        const qs = params.toString() ? `?${params.toString()}` : "";
        try {
            return await this.fetch(`/account/usage${qs}`, {}, token);
        } catch (e: any) {
            if (String(e?.message || "").toLowerCase().includes("unauthorized")) throw e;
            return {
                plan: "starter",
                limits: { projects: 5, documents: 25, runs: 10 },
                usage: { projects: 0, documents: 0, runs: 0 },
                percent: { projects: 0, documents: 0, runs: 0 },
                next_plan: "growth",
            };
        }
    }

    // --- Audit Log ---
    static async getAuditLog(orgId: string, filters: Record<string, string> = {}, token?: string): Promise<any> {
        const params = new URLSearchParams({ org_id: orgId, ...filters });
        return this.fetch<any>(`/audit/log?${params.toString()}`, {}, token);
    }

    static async getExportEvents(orgId: string, filters: Record<string, string> = {}, token?: string): Promise<any> {
        const params = new URLSearchParams({ org_id: orgId, ...filters });
        return this.fetch<any>(`/audit/exports?${params.toString()}`, {}, token);
    }

    static async reviewAuditEntry(
        runId: string,
        auditId: string,
        reviewStatus: "approved" | "rejected",
        reviewNotes: string = "",
        token?: string
    ): Promise<any> {
        return this.patch<any>(`/runs/${runId}/audits/${auditId}/review`, {
            review_status: reviewStatus,
            review_notes: reviewNotes,
        }, token);
    }

    // --- Bulk Review & Export Readiness ---
    static async bulkReviewAudits(
        runId: string,
        reviewStatus: "approved" | "rejected",
        reviewNotes: string = "",
        token?: string
    ): Promise<any> {
        return this.post<any>(`/runs/${runId}/audits/bulk-review`, {
            review_status: reviewStatus,
            review_notes: reviewNotes,
        }, token);
    }

    static async getExportReadiness(runId: string, token?: string): Promise<{
        total: number;
        approved: number;
        rejected: number;
        pending: number;
        all_reviewed: boolean;
        ready_for_export: boolean;
    }> {
        return this.fetch(`/runs/${runId}/export-readiness`, {}, token);
    }

    // --- Project Overview & Onboarding ---
    static async getProjectOverview(projectId: string, token?: string): Promise<ProjectOverview> {
        return this.fetch<ProjectOverview>(`/projects/${projectId}/overview`, {}, token);
    }

    static async getProjectOnboarding(projectId: string, token?: string): Promise<OnboardingState> {
        return this.fetch<OnboardingState>(`/projects/${projectId}/onboarding`, {}, token);
    }

    static async completeOnboardingStep(projectId: string, step: string, token?: string): Promise<any> {
        return this.post<any>(`/projects/${projectId}/onboarding/complete`, { step }, token);
    }

    // --- Compliance Intelligence ---
    static async getComplianceHealth(
        orgId: string,
        token?: string,
        limit: number = 10,
    ): Promise<any> {
        const params = new URLSearchParams({ org_id: orgId, limit: String(limit) });
        try {
            return await this.fetch<any>(`/runs/compliance-health?${params.toString()}`, {}, token);
        } catch (e: any) {
            if (String(e?.message || "").toLowerCase().includes("unauthorized")) throw e;
            return null;
        }
    }

    static async compareRuns(
        runId: string,
        otherId: string,
        token?: string,
    ): Promise<any> {
        return this.fetch<any>(`/runs/${runId}/compare/${otherId}`, {}, token);
    }

    // --- Evidence Vault ---
    static async generateEvidence(runId: string, token?: string): Promise<{ blob: Blob; hash: string; filename: string }> {
        const headers: Record<string, string> = {};
        if (token) headers["Authorization"] = `Bearer ${token}`;
        const res = await fetch(`${API_BASE}/runs/${runId}/generate-evidence`, {
            method: "POST",
            headers,
        });
        if (!res.ok) {
            let detail = res.statusText;
            try { const err = await res.json(); detail = err?.detail || detail; } catch { /* ignore */ }
            throw new Error(detail);
        }
        const hash = res.headers.get("X-Evidence-Hash") || "";
        const disposition = res.headers.get("Content-Disposition") || "";
        const match = disposition.match(/filename="?([^"]+)"?/);
        const filename = match ? match[1] : `evidence_${runId.slice(0, 8)}.zip`;
        const blob = await res.blob();
        return { blob, hash, filename };
    }

    static async listRunEvidenceRecords(runId: string, token?: string): Promise<any[]> {
        try {
            return await this.fetch<any[]>(`/runs/${runId}/evidence-records`, {}, token);
        } catch { return []; }
    }

    static async listOrgEvidenceRecords(orgId: string, projectId?: string, token?: string): Promise<any[]> {
        const params = new URLSearchParams({ org_id: orgId });
        if (projectId) params.set("project_id", projectId);
        try {
            return await this.fetch<any[]>(`/runs/evidence-records?${params}`, {}, token);
        } catch { return []; }
    }

    static async deleteEvidenceRecord(recordId: string, token?: string): Promise<any> {
        return this.delete<any>(`/runs/evidence-records/${recordId}`, token);
    }

    static async unlockRun(runId: string, token?: string): Promise<any> {
        return this.post<any>(`/runs/${runId}/unlock`, {}, token);
    }

    // --- SOC2 Readiness ---
    static async getAccessReport(orgId: string, token?: string): Promise<any> {
        return this.fetch<any>(`/orgs/${orgId}/access-report?format=json`, {}, token);
    }

    static async downloadAccessReportCSV(orgId: string, token?: string): Promise<void> {
        const headers: Record<string, string> = {};
        let authToken = token;
        if (!authToken) {
            try {
                const supabase = createClient();
                const { data: { session } } = await supabase.auth.getSession();
                authToken = session?.access_token || undefined;
            } catch {
                authToken = undefined;
            }
        }
        if (authToken) headers["Authorization"] = `Bearer ${authToken}`;

        const res = await fetch(`${API_BASE}/orgs/${orgId}/access-report?format=csv`, { headers });
        if (!res.ok) {
            let detail = res.statusText;
            try { const err = await res.json(); detail = err?.message || detail; } catch { /* ignore */ }
            throw new Error(`Access report download failed: ${detail}`);
        }

        const blob = await res.blob();
        const url = window.URL.createObjectURL(blob);
        const a = document.createElement("a");
        a.href = url;
        a.download = `access_report_${orgId.slice(0, 8)}.csv`;
        document.body.appendChild(a);
        a.click();
        window.URL.revokeObjectURL(url);
        document.body.removeChild(a);
    }

    static async triggerRetentionJob(orgId: string, dryRun: boolean = false, token?: string): Promise<any> {
        return this.post<any>(`/admin/run-retention-job?org_id=${orgId}&dry_run=${dryRun}`, {}, token);
    }

    // --- Sales Engine ---
    static async submitContactForm(payload: {
        company_name: string;
        name: string;
        email: string;
        phone?: string;
        company_size?: string;
        message?: string;
    }): Promise<{ status: string; message: string }> {
        return this.post<{ status: string; message: string }>("/contact", payload);
    }

    static async trackEnterpriseInterest(orgId?: string, source: string = "billing_page", token?: string): Promise<any> {
        return this.post<any>("/track/enterprise-interest", { org_id: orgId, source }, token);
    }

    static async trackTrialEvent(orgId: string, eventType: string, token?: string): Promise<any> {
        return this.post<any>("/track/trial-event", { org_id: orgId, event_type: eventType }, token);
    }

    static async getSalesAnalytics(token?: string): Promise<any> {
        return this.fetch<any>("/admin/sales-analytics", {}, token);
    }

    static async resetDemoWorkspace(token?: string): Promise<any> {
        return this.post<any>("/admin/demo-reset", {}, token);
    }

    // --- Onboarding ---
    static async getOnboardingState(token?: string): Promise<{ onboarding_completed: boolean; onboarding_step: number }> {
        return this.fetch("/org/onboarding", {}, token);
    }

    static async patchOnboardingState(
        payload: { onboarding_completed?: boolean; onboarding_step?: number },
        token?: string
    ): Promise<{ onboarding_completed: boolean; onboarding_step: number }> {
        return this.patch("/org/onboarding", payload, token);
    }

    static async getOrgMetrics(token?: string): Promise<{
        documents_count: number;
        projects_count: number;
        runs_count: number;
        reviewed_count: number;
        exports_count: number;
    }> {
        return this.fetch("/org/metrics", {}, token);
    }

    // --- Account Profile & Appearance ---
    static async getAccountProfile(token?: string): Promise<AccountProfile> {
        return this.fetch<AccountProfile>("/account/profile", {}, token);
    }

    static async patchAccountProfile(
        payload: { display_name?: string; public_email?: string; theme_preference?: string },
        token?: string,
    ): Promise<AccountProfile> {
        return this.patch<AccountProfile>("/account/profile", payload, token);
    }

    static async uploadAvatar(file: File, token?: string): Promise<AccountProfile> {
        const formData = new FormData();
        formData.append("file", file);

        const headers: HeadersInit = {};
        let authToken = token;
        if (!authToken) {
            try {
                const supabase = createClient();
                const { data: { session } } = await supabase.auth.getSession();
                authToken = session?.access_token || undefined;
            } catch {
                authToken = undefined;
            }
        }
        if (authToken) headers["Authorization"] = `Bearer ${authToken}`;

        const res = await fetch(`${API_BASE}/account/avatar`, {
            method: "PATCH",
            body: formData,
            headers,
        });

        if (!res.ok) {
            let detail = res.statusText;
            try { const err = await res.json(); detail = err?.detail || detail; } catch { /* ignore */ }
            throw new Error(`Avatar upload failed: ${detail}`);
        }
        return res.json();
    }

    // ── Assistant ──────────────────────────────────────────────────────

    static async sendAssistantMessage(
        orgId: string,
        message: string,
        conversationId?: string,
        token?: string,
    ): Promise<{
        conversation_id: string;
        reply: string;
        actions: { label: string; href: string }[];
    }> {
        return this.post(
            "/assistant/message",
            { org_id: orgId, message, conversation_id: conversationId },
            token,
        );
    }

    // ── Audit / Activity Timeline ──────────────────────────────────────────

    static async getAuditEvents(
        orgId: string,
        params: {
            user_id?: string;
            action_type?: string;
            project_id?: string;
            from?: string;
            to?: string;
            page?: number;
            page_size?: number;
        } = {},
        token?: string,
    ): Promise<{
        events: {
            id: string;
            timestamp: string;
            user_id: string;
            user_email: string | null;
            action_type: string;
            entity_type: string;
            entity_id: string;
            metadata: Record<string, unknown>;
        }[];
        total: number;
        page: number;
        page_size: number;
    }> {
        const qs = new URLSearchParams({ org_id: orgId });
        if (params.user_id)    qs.set("user_id", params.user_id);
        if (params.action_type) qs.set("action_type", params.action_type);
        if (params.project_id) qs.set("project_id", params.project_id);
        if (params.from)       qs.set("from", params.from);
        if (params.to)         qs.set("to", params.to);
        if (params.page)       qs.set("page", String(params.page));
        if (params.page_size)  qs.set("page_size", String(params.page_size));
        return this.fetch(`/audit/events?${qs.toString()}`, {}, token);
    }

    static async exportAuditCsv(
        orgId: string,
        params: {
            user_id?: string;
            action_type?: string;
            project_id?: string;
            from?: string;
            to?: string;
        } = {},
        token?: string,
    ): Promise<void> {
        const qs = new URLSearchParams({ org_id: orgId });
        if (params.user_id)    qs.set("user_id", params.user_id);
        if (params.action_type) qs.set("action_type", params.action_type);
        if (params.project_id) qs.set("project_id", params.project_id);
        if (params.from)       qs.set("from", params.from);
        if (params.to)         qs.set("to", params.to);

        const headers: HeadersInit = {};
        let authToken = token;
        if (!authToken) {
            try {
                const supabase = createClient();
                const { data: { session } } = await supabase.auth.getSession();
                authToken = session?.access_token || undefined;
            } catch { authToken = undefined; }
        }
        if (authToken) headers["Authorization"] = `Bearer ${authToken}`;

        const res = await fetch(`${API_BASE}/audit/export?${qs.toString()}`, { headers });
        if (!res.ok) throw new Error(`Export failed: ${res.statusText}`);

        const blob = await res.blob();
        const url = URL.createObjectURL(blob);
        const a = document.createElement("a");
        const cd = res.headers.get("Content-Disposition") || "";
        const match = cd.match(/filename="([^"]+)"/);
        a.download = match ? match[1] : "audit_events.csv";
        a.href = url;
        document.body.appendChild(a);
        a.click();
        a.remove();
        URL.revokeObjectURL(url);
    }

    // ── Upgrade Analytics ─────────────────────────────────────────────────────

    /**
     * Best-effort: log an upgrade-funnel event to the backend.
     * Never throws — fire-and-forget.
     */
    static async logUpgradeEvent(
        eventType: string,
        orgId: string,
        token?: string,
        metadata?: Record<string, unknown>,
    ): Promise<void> {
        try {
            await this.post(
                "/billing/log-upgrade-event",
                { event_type: eventType, org_id: orgId, metadata: metadata ?? {} },
                token,
            );
        } catch {
            // best-effort — never propagate
        }
    }

    static async getUpgradeAnalytics(
        orgId: string,
        token?: string,
    ): Promise<{
        limit_hits: number;
        modal_shown: number;
        upgrade_clicks: number;
        conversions: number;
        top_resource: string | null;
        resource_hits: Record<string, number>;
    }> {
        const params = new URLSearchParams({ org_id: orgId });
        try {
            return await this.fetch(`/billing/upgrade-analytics?${params}`, {}, token);
        } catch (e: any) {
            if (String(e?.message || "").toLowerCase().includes("unauthorized")) throw e;
            return { limit_hits: 0, modal_shown: 0, upgrade_clicks: 0, conversions: 0, top_resource: null, resource_hits: {} };
        }
    }

    // --- Admin Dashboard Analytics ---
    static async getAdminDashboardStats(
        orgId: string,
        token?: string,
    ): Promise<{
        org_id: string;
        total_projects: number;
        total_documents: number;
        total_runs: number;
        failed_runs: number;
        total_members: number;
        completed_runs: number;
    }> {
        return this.fetch(`/admin/dashboard-stats?org_id=${orgId}`, {}, token);
    }

    static async getPlanDistribution(
        token?: string,
    ): Promise<{
        plans: Record<string, number>;
        total_orgs: number;
    }> {
        return this.fetch("/admin/plan-distribution", {}, token);
    }

    static async getMrrSummary(
        token?: string,
    ): Promise<{
        mrr_cents: number;
        mrr_dollars: number;
        plan_counts: Record<string, number>;
        total_active_orgs: number;
    }> {
        return this.fetch("/admin/mrr-summary", {}, token);
    }

    // --- Coupon / Promo Code Support ---
    static async validateCoupon(
        code: string,
        token?: string,
    ): Promise<{
        valid: boolean;
        id?: string;
        code: string;
        percent_off?: number | null;
        amount_off?: number | null;
        duration?: string;
        name?: string;
        message?: string;
    }> {
        return this.fetch("/billing/validate-coupon", {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ code }),
        }, token);
    }

    static async applyCoupon(
        orgId: string,
        code: string,
        token?: string,
    ): Promise<{
        success: boolean;
        message: string;
        discount?: {
            coupon_id: string;
            code: string;
            percent_off?: number | null;
            amount_off?: number | null;
            duration?: string;
        } | null;
    }> {
        return this.fetch("/billing/apply-coupon", {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ org_id: orgId, code }),
        }, token);
    }

    static async getOrgDiscount(
        orgId: string,
        token?: string,
    ): Promise<{
        has_discount: boolean;
        discount: {
            coupon_id: string;
            name: string;
            percent_off?: number | null;
            amount_off?: number | null;
            duration?: string;
            start?: number;
            end?: number | null;
        } | null;
    }> {
        return this.fetch(`/billing/discount?org_id=${orgId}`, {}, token);
    }

    // --- Document Expiry & Re-run Alerts ---
    static async getDocumentExpiryAlerts(
        orgId: string,
        daysAhead: number = 30,
        token?: string,
    ): Promise<{
        expiring_count: number;
        expired_count: number;
        rerun_needed_count: number;
        total_alerts: number;
        expiring_docs: Array<{
            id: string;
            filename: string;
            project_id: string;
            project_name: string;
            expiration_date: string;
            status: string;
            days_remaining: number | null;
        }>;
        expired_docs: Array<{
            id: string;
            filename: string;
            project_id: string;
            project_name: string;
            expiration_date: string;
            status: string;
            days_remaining: number | null;
        }>;
        rerun_docs: Array<{
            id: string;
            filename: string;
            project_id: string;
            project_name: string;
            last_run_at: string | null;
            days_since_run: number | null;
        }>;
    }> {
        const params = new URLSearchParams({ org_id: orgId, days_ahead: String(daysAhead) });
        try {
            return await this.fetch(`/alerts/document-expiry?${params}`, {}, token);
        } catch {
            return { expiring_count: 0, expired_count: 0, rerun_needed_count: 0, total_alerts: 0, expiring_docs: [], expired_docs: [], rerun_docs: [] };
        }
    }

    static async checkAndNotifyExpiry(
        orgId: string,
        token?: string,
    ): Promise<{
        alerts_found: number;
        notifications_sent: boolean;
    }> {
        const params = new URLSearchParams({ org_id: orgId });
        return this.fetch(`/alerts/check-expiry?${params}`, { method: "POST" }, token);
    }

    static async getRerunCandidates(
        orgId: string,
        staleDays: number = 90,
        token?: string,
    ): Promise<Array<{
        id: string;
        filename: string;
        project_id: string;
        project_name: string;
        last_run_at: string | null;
        days_since_run: number | null;
    }>> {
        const params = new URLSearchParams({ org_id: orgId, stale_days: String(staleDays) });
        try {
            return await this.fetch(`/alerts/rerun-candidates?${params}`, {}, token);
        } catch {
            return [];
        }
    }
}

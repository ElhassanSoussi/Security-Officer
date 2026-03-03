export interface Run {
    id: string;
    org_id: string;
    project_id?: string;
    questionnaire_filename: string;
    status: "QUEUED" | "PROCESSING" | "COMPLETED" | "ANALYZED" | "EXPORTED" | "FAILED";
    created_at: string;
    export_filename?: string;
    output_filename?: string;
    input_filename?: string;
    counts_answered?: number;
    counts_low_confidence?: number;
    error_message?: string;
}

export interface Audit {
    id: string;
    run_id: string;
    org_id: string;
    project_id?: string;
    cell_reference?: string;
    question_text: string;
    answer_text: string;
    // 0..1 (ratio) or 0..100 (percent) depending on backend; never NaN.
    confidence_score: number | null;
    source_document?: string;
    source_excerpt?: string;
    page_number?: string;
    is_overridden?: boolean;
    original_answer?: string;
    review_status?: string;
    reviewer_id?: string;
    reviewed_at?: string;
    editor_id?: string;
    edited_at?: string;
    created_at: string;
}

export interface Project {
    org_id: string;
    project_id: string;
    project_name?: string;
    description?: string;
    status?: string;
    created_at?: string;
    document_count?: number; // Optional if we fetch from docs endpoint later
    last_activity?: string;
}

export interface ProjectDocument {
    id: string;
    filename: string;
    file_type?: string;
    file_size_bytes?: number;
    scope?: string;
    uploaded_by?: string;
    created_at: string;
    project_id: string;
}

export interface ExportReadiness {
    total: number;
    approved: number;
    rejected: number;
    pending: number;
    all_reviewed: boolean;
    ready_for_export: boolean;
}

export interface Activity {
    id: string;
    org_id: string;
    project_id?: string;
    run_id?: string;
    event_type: string;
    description: string;
    created_at: string;
}

export interface DashboardStats {
    active_projects: number;
    documents_ingested: number;
    runs_completed: number;
}

export interface QuestionItem {
    audit_id?: string; // Backend row ID for persisting reviews
    sheet_name: string;
    cell_coordinate: string;
    question: string;
    ai_answer: string;
    final_answer: string;
    confidence: "HIGH" | "MEDIUM" | "LOW";
    analysis_duration?: number;
    sources: string[];
    source_id?: string;
    source_page?: number;
    source_excerpt?: string;
    status?: "ok" | "needs_info" | "ai_unavailable";
    status_reason?: string;
    is_verified: boolean;
    edited_by_user: boolean;
    review_status?: "pending" | "approved" | "rejected";
}

// ── Project Overview & Onboarding ──────────────────────────────────

export interface OnboardingStep {
    completed: boolean;
    completed_at: string | null;
    label: string;
}

export interface OnboardingState {
    steps: Record<string, OnboardingStep>;
    completed_count: number;
    total_steps: number;
    all_complete: boolean;
}

export interface ProjectOverview {
    project: { id: string; name: string; status: string };
    org: { id: string; name: string };
    role: string;
    docs: { total: number; expiring_count: number; expired_count: number };
    runs: { total: number; last_run_at: string | null; last_export_at: string | null };
    audit_preview: Array<{
        id: string;
        event_type: string;
        created_at: string;
        user_id: string;
        metadata: Record<string, any>;
    }>;
    onboarding: OnboardingState;
}

// ── Product Intelligence & Decision Layer ─────────────────────────

export type AnswerStatus = "auto_generated" | "under_review" | "approved" | "flagged" | "edited";

export interface ComplianceInsights {
    avg_confidence: number;
    low_confidence_count: number;
    high_risk: boolean;
    missing_sources_count: number;
    manually_overridden_count: number;
    runs_by_month: { month: string; count: number }[];
    exports_by_month: { month: string; count: number }[];
}

export interface RunIntelligence {
    confidence_distribution: { high: number; medium: number; low: number };
    auto_answered_pct: number;
    manually_edited_pct: number;
    time_to_complete_ms: number | null;
    export_readiness_score: number;
    total_questions: number;
    flagged_count: number;
    pending_review_count: number;
}

export interface IntelligenceReport {
    project: { id: string; name: string; status: string };
    risk_breakdown: { high: number; medium: number; low: number; total: number };
    confidence_heatmap: { label: string; score: number }[];
    audit_completeness: number;
    review_completion_pct: number;
    export_history: { id: string; created_at: string; filename: string; questions_count: number }[];
    total_runs: number;
    total_documents: number;
}

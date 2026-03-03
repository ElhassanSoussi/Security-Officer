/**
 * Demo Mode helpers
 * Activated by ?demo=1 URL param OR NEXT_PUBLIC_DEMO_MODE=true env flag.
 */

export const DEMO_ORG_ID = "00000000-0000-0000-0000-000000000001";
export const DEMO_PROJECT_ID = "00000000-0000-0000-0000-000000000002";
export const DEMO_RUN_ID = "00000000-0000-0000-0000-000000000003";

export function isDemoMode(): boolean {
  if (typeof window === "undefined") {
    return process.env.NEXT_PUBLIC_DEMO_MODE === "true";
  }
  const urlParam = new URLSearchParams(window.location.search).get("demo");
  if (urlParam === "1" || urlParam === "true") return true;
  return process.env.NEXT_PUBLIC_DEMO_MODE === "true";
}

export interface DemoProject {
  id: string;
  project_id: string;
  project_name: string;
  description: string;
  status: string;
  org_id: string;
  created_at: string;
  document_count: number;
}

export interface DemoDocument {
  id: string;
  filename: string;
  file_type: string;
  file_size_bytes: number;
  scope: string;
  project_id: string;
  created_at: string;
}

export interface DemoAudit {
  id: string;
  run_id: string;
  org_id: string;
  project_id: string;
  cell_reference: string;
  question_text: string;
  answer_text: string;
  confidence_score: number;
  source_document: string;
  source_excerpt: string;
  review_status: "pending" | "approved" | "rejected";
  created_at: string;
}

export const DEMO_PROJECT: DemoProject = {
  id: DEMO_PROJECT_ID,
  project_id: DEMO_PROJECT_ID,
  project_name: "NYC SCA Demo Project",
  description: "Demo workspace — NYC School Construction Authority questionnaire.",
  status: "active",
  org_id: DEMO_ORG_ID,
  created_at: "2026-01-15T10:00:00Z",
  document_count: 2,
};

export const DEMO_DOCUMENTS: DemoDocument[] = [
  {
    id: "doc-demo-1",
    filename: "cybersecurity_policy.pdf",
    file_type: "pdf",
    file_size_bytes: 512000,
    scope: "Security Policy",
    project_id: DEMO_PROJECT_ID,
    created_at: "2026-01-15T10:05:00Z",
  },
  {
    id: "doc-demo-2",
    filename: "incident_response_plan.pdf",
    file_type: "pdf",
    file_size_bytes: 204800,
    scope: "Incident Response",
    project_id: DEMO_PROJECT_ID,
    created_at: "2026-01-15T10:10:00Z",
  },
];

export const DEMO_RUN = {
  id: DEMO_RUN_ID,
  org_id: DEMO_ORG_ID,
  project_id: DEMO_PROJECT_ID,
  status: "COMPLETED" as const,
  questionnaire_filename: "SCA_Cybersecurity_Questionnaire.xlsx",
  input_filename: "SCA_Cybersecurity_Questionnaire.xlsx",
  output_filename: "SCA_Cybersecurity_Questionnaire_filled.xlsx",
  counts_answered: 15,
  counts_low_confidence: 3,
  created_at: "2026-01-16T09:00:00Z",
};

const NOW = "2026-01-16T09:05:00Z";

export const DEMO_AUDITS: DemoAudit[] = [
  {
    id: "audit-demo-1",
    run_id: DEMO_RUN_ID,
    org_id: DEMO_ORG_ID,
    project_id: DEMO_PROJECT_ID,
    cell_reference: "B5",
    question_text: "Does your organization have a documented Information Security Policy?",
    answer_text: "Yes. Our Information Security Policy (ISP-2025) was last reviewed January 2026 and covers all systems handling sensitive data.",
    confidence_score: 0.95,
    source_document: "cybersecurity_policy.pdf",
    source_excerpt: "The Information Security Policy was reviewed and updated in January 2026...",
    review_status: "approved",
    created_at: NOW,
  },
  {
    id: "audit-demo-2",
    run_id: DEMO_RUN_ID,
    org_id: DEMO_ORG_ID,
    project_id: DEMO_PROJECT_ID,
    cell_reference: "B8",
    question_text: "Is there a formal incident response plan in place?",
    answer_text: "Yes. An Incident Response Plan (IRP v3.1) is maintained and tested annually via tabletop exercises.",
    confidence_score: 0.88,
    source_document: "incident_response_plan.pdf",
    source_excerpt: "IRP v3.1 — Annual tabletop exercises conducted each Q4...",
    review_status: "approved",
    created_at: NOW,
  },
  {
    id: "audit-demo-3",
    run_id: DEMO_RUN_ID,
    org_id: DEMO_ORG_ID,
    project_id: DEMO_PROJECT_ID,
    cell_reference: "B12",
    question_text: "Do you conduct regular vulnerability scans of your network infrastructure?",
    answer_text: "Vulnerability scans are performed quarterly using automated tooling.",
    confidence_score: 0.72,
    source_document: "cybersecurity_policy.pdf",
    source_excerpt: "Section 4.3: Vulnerability Management — scans conducted quarterly...",
    review_status: "pending",
    created_at: NOW,
  },
  {
    id: "audit-demo-4",
    run_id: DEMO_RUN_ID,
    org_id: DEMO_ORG_ID,
    project_id: DEMO_PROJECT_ID,
    cell_reference: "B15",
    question_text: "Is multi-factor authentication (MFA) enforced for all remote access?",
    answer_text: "MFA is required for all VPN and cloud portal access.",
    confidence_score: 0.91,
    source_document: "cybersecurity_policy.pdf",
    source_excerpt: "Section 3.1: Access Control — MFA enforced for all remote sessions...",
    review_status: "pending",
    created_at: NOW,
  },
  {
    id: "audit-demo-5",
    run_id: DEMO_RUN_ID,
    org_id: DEMO_ORG_ID,
    project_id: DEMO_PROJECT_ID,
    cell_reference: "B19",
    question_text: "What is your Recovery Time Objective (RTO) for critical systems?",
    answer_text: "Unable to determine from available documents. Manual review recommended.",
    confidence_score: 0.28,
    source_document: "",
    source_excerpt: "",
    review_status: "rejected",
    created_at: NOW,
  },
  {
    id: "audit-demo-6",
    run_id: DEMO_RUN_ID,
    org_id: DEMO_ORG_ID,
    project_id: DEMO_PROJECT_ID,
    cell_reference: "B22",
    question_text: "Are system logs centrally collected and monitored?",
    answer_text: "Yes. All application and infrastructure logs are forwarded to a centralized SIEM with 90-day retention and real-time alerting.",
    confidence_score: 0.93,
    source_document: "cybersecurity_policy.pdf",
    source_excerpt: "Section 5.2: Logging & Monitoring — centralized SIEM with 90-day retention...",
    review_status: "approved",
    created_at: NOW,
  },
  {
    id: "audit-demo-7",
    run_id: DEMO_RUN_ID,
    org_id: DEMO_ORG_ID,
    project_id: DEMO_PROJECT_ID,
    cell_reference: "B25",
    question_text: "Is data encrypted at rest and in transit?",
    answer_text: "All data at rest is encrypted using AES-256. All data in transit uses TLS 1.2 or higher.",
    confidence_score: 0.97,
    source_document: "cybersecurity_policy.pdf",
    source_excerpt: "Section 6.1: Encryption Standards — AES-256 at rest, TLS 1.2+ in transit...",
    review_status: "approved",
    created_at: NOW,
  },
  {
    id: "audit-demo-8",
    run_id: DEMO_RUN_ID,
    org_id: DEMO_ORG_ID,
    project_id: DEMO_PROJECT_ID,
    cell_reference: "B28",
    question_text: "Do you have a Business Continuity Plan (BCP)?",
    answer_text: "A Business Continuity Plan is maintained and tested semi-annually. Last test: November 2025.",
    confidence_score: 0.85,
    source_document: "incident_response_plan.pdf",
    source_excerpt: "Appendix B: BCP tested semi-annually. Last successful test November 2025...",
    review_status: "approved",
    created_at: NOW,
  },
  {
    id: "audit-demo-9",
    run_id: DEMO_RUN_ID,
    org_id: DEMO_ORG_ID,
    project_id: DEMO_PROJECT_ID,
    cell_reference: "B31",
    question_text: "Is there a formal change management process for production systems?",
    answer_text: "Yes. All production changes require peer review, approval, and rollback plan before deployment.",
    confidence_score: 0.89,
    source_document: "cybersecurity_policy.pdf",
    source_excerpt: "Section 7.1: Change Management — peer review + approval required for all production changes...",
    review_status: "pending",
    created_at: NOW,
  },
  {
    id: "audit-demo-10",
    run_id: DEMO_RUN_ID,
    org_id: DEMO_ORG_ID,
    project_id: DEMO_PROJECT_ID,
    cell_reference: "B34",
    question_text: "Are background checks conducted for employees with access to sensitive data?",
    answer_text: "Background checks are conducted for all employees and contractors prior to granting access to sensitive systems.",
    confidence_score: 0.82,
    source_document: "cybersecurity_policy.pdf",
    source_excerpt: "Section 2.3: Personnel Security — background checks conducted pre-employment...",
    review_status: "approved",
    created_at: NOW,
  },
  {
    id: "audit-demo-11",
    run_id: DEMO_RUN_ID,
    org_id: DEMO_ORG_ID,
    project_id: DEMO_PROJECT_ID,
    cell_reference: "B37",
    question_text: "Is there a data classification policy?",
    answer_text: "Data is classified into four tiers: Public, Internal, Confidential, and Restricted. Handling procedures vary by tier.",
    confidence_score: 0.90,
    source_document: "cybersecurity_policy.pdf",
    source_excerpt: "Section 8.1: Data Classification — four tiers with distinct handling requirements...",
    review_status: "approved",
    created_at: NOW,
  },
  {
    id: "audit-demo-12",
    run_id: DEMO_RUN_ID,
    org_id: DEMO_ORG_ID,
    project_id: DEMO_PROJECT_ID,
    cell_reference: "B40",
    question_text: "What physical security controls protect your data centers?",
    answer_text: "Unable to fully determine. Partial reference to badge access found. Manual review recommended.",
    confidence_score: 0.41,
    source_document: "cybersecurity_policy.pdf",
    source_excerpt: "Section 9: Physical Security — badge-based access control at all facilities...",
    review_status: "pending",
    created_at: NOW,
  },
  {
    id: "audit-demo-13",
    run_id: DEMO_RUN_ID,
    org_id: DEMO_ORG_ID,
    project_id: DEMO_PROJECT_ID,
    cell_reference: "B43",
    question_text: "Do you perform annual security awareness training for all staff?",
    answer_text: "Yes. Annual security awareness training is mandatory for all employees. Completion rate for 2025 was 98%.",
    confidence_score: 0.94,
    source_document: "cybersecurity_policy.pdf",
    source_excerpt: "Section 2.5: Security Awareness — annual training mandatory, 98% completion 2025...",
    review_status: "approved",
    created_at: NOW,
  },
  {
    id: "audit-demo-14",
    run_id: DEMO_RUN_ID,
    org_id: DEMO_ORG_ID,
    project_id: DEMO_PROJECT_ID,
    cell_reference: "B46",
    question_text: "Is there a third-party risk management program?",
    answer_text: "A vendor risk assessment program evaluates all third-party providers annually. Questionnaires are sent to critical vendors.",
    confidence_score: 0.86,
    source_document: "cybersecurity_policy.pdf",
    source_excerpt: "Section 10.1: Third-Party Risk — annual vendor risk assessments for critical providers...",
    review_status: "approved",
    created_at: NOW,
  },
  {
    id: "audit-demo-15",
    run_id: DEMO_RUN_ID,
    org_id: DEMO_ORG_ID,
    project_id: DEMO_PROJECT_ID,
    cell_reference: "B49",
    question_text: "Are network segmentation controls in place to isolate sensitive systems?",
    answer_text: "Network segmentation isolates production, staging, and corporate environments. Firewall rules enforce least-privilege access between segments.",
    confidence_score: 0.88,
    source_document: "cybersecurity_policy.pdf",
    source_excerpt: "Section 4.6: Network Segmentation — production, staging, corporate isolated via firewall...",
    review_status: "pending",
    created_at: NOW,
  },
];

export const DEMO_STATS = {
  active_projects: 1,
  documents_ingested: 2,
  runs_completed: 1,
};

export const DEMO_ACTIVITY = [
  { id: "act-1", event_type: "run_completed", description: "Analysis completed for SCA questionnaire", created_at: NOW },
  { id: "act-2", event_type: "document_uploaded", description: "Uploaded incident_response_plan.pdf", created_at: "2026-01-15T10:10:00Z" },
  { id: "act-3", event_type: "document_uploaded", description: "Uploaded cybersecurity_policy.pdf", created_at: "2026-01-15T10:05:00Z" },
  { id: "act-4", event_type: "project_created", description: "Created project: NYC SCA Demo Project", created_at: "2026-01-15T10:00:00Z" },
  { id: "act-5", event_type: "answer_approved", description: "Approved answer for B5 — Information Security Policy", created_at: "2026-01-16T09:10:00Z" },
  { id: "act-6", event_type: "answer_approved", description: "Approved answer for B8 — Incident Response Plan", created_at: "2026-01-16T09:12:00Z" },
  { id: "act-7", event_type: "evidence_exported", description: "Evidence package exported for SCA questionnaire", created_at: "2026-01-16T09:15:00Z" },
  { id: "act-8", event_type: "memory_reused", description: "Reused institutional memory for encryption policy (B25)", created_at: "2026-01-16T09:08:00Z" },
  { id: "act-9", event_type: "risk_flagged", description: "LOW confidence flagged for B19 — RTO question", created_at: "2026-01-16T09:06:00Z" },
  { id: "act-10", event_type: "memory_reused", description: "Reused institutional memory for MFA policy (B15)", created_at: "2026-01-16T09:07:00Z" },
];

// ── Evidence Vault Demo Records ──

export interface DemoEvidenceRecord {
  id: string;
  run_id: string;
  org_id: string;
  cell_reference: string;
  question_text: string;
  answer_text: string;
  source_documents: string[];
  confidence_score: number;
  exported_at: string;
  hash: string;
}

export const DEMO_EVIDENCE_RECORDS: DemoEvidenceRecord[] = [
  {
    id: "ev-demo-1",
    run_id: DEMO_RUN_ID,
    org_id: DEMO_ORG_ID,
    cell_reference: "B5",
    question_text: "Does your organization have a documented Information Security Policy?",
    answer_text: "Yes. Our Information Security Policy (ISP-2025) was last reviewed January 2026.",
    source_documents: ["cybersecurity_policy.pdf"],
    confidence_score: 0.95,
    exported_at: "2026-01-16T09:15:00Z",
    hash: "sha256:a1b2c3d4e5f6...",
  },
  {
    id: "ev-demo-2",
    run_id: DEMO_RUN_ID,
    org_id: DEMO_ORG_ID,
    cell_reference: "B25",
    question_text: "Is data encrypted at rest and in transit?",
    answer_text: "All data at rest is encrypted using AES-256. All data in transit uses TLS 1.2 or higher.",
    source_documents: ["cybersecurity_policy.pdf"],
    confidence_score: 0.97,
    exported_at: "2026-01-16T09:15:00Z",
    hash: "sha256:b2c3d4e5f6a7...",
  },
];

// ── Compliance Health Score Demo ──

export const DEMO_HEALTH_SCORE = {
  overall_score: 82,
  risk_breakdown: {
    high: 1,    // B19 rejected (RTO unknown)
    medium: 3,  // B12, B40, B31 pending with lower confidence
    low: 11,    // remaining approved/high-confidence
  },
  reuse_stats: {
    reused_from_memory: 2,
    total_answered: 15,
    reuse_rate: 13.3,
  },
  export_gate: {
    approved_count: 9,
    pending_count: 5,
    rejected_count: 1,
    ready_for_export: false, // rejected items block export gate
    blocking_reasons: ["1 rejected answer requires manual review"],
  },
};

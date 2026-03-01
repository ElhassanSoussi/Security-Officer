/**
 * Onboarding state helpers — Phase 14
 * Persists onboarding progress in localStorage (per-org or per-project).
 * Falls back gracefully when localStorage is unavailable.
 */

export type OnboardingStepId =
  | "create_project"
  | "upload_docs"
  | "upload_questionnaire"
  | "run_analysis"
  | "review_low_confidence"
  | "export";

export interface OnboardingStep {
  id: OnboardingStepId;
  label: string;
  description: string;
  href: string;
  actionLabel: string;
}

export const ONBOARDING_STEPS: OnboardingStep[] = [
  {
    id: "create_project",
    label: "Create a Project",
    description: "Set up your first compliance project to organize documents and runs.",
    href: "/projects",
    actionLabel: "Go to Projects",
  },
  {
    id: "upload_docs",
    label: "Upload Supporting Documents",
    description: "Add policies, SOPs, and evidence docs to the Knowledge Vault.",
    href: "/projects",
    actionLabel: "Upload Documents",
  },
  {
    id: "upload_questionnaire",
    label: "Upload a Questionnaire",
    description: "Upload the Excel questionnaire you need to fill out (SCA, MTA, PASSPort).",
    href: "/run",
    actionLabel: "Start a Run",
  },
  {
    id: "run_analysis",
    label: "Run AI Analysis",
    description: "Let the AI generate answers grounded in your uploaded documents.",
    href: "/run",
    actionLabel: "Run Analysis",
  },
  {
    id: "review_low_confidence",
    label: "Review Low-Confidence Answers",
    description: "Verify and approve answers the AI wasn't sure about.",
    href: "/audit",
    actionLabel: "Open Audit",
  },
  {
    id: "export",
    label: "Export Filled Excel",
    description: "Download the submission-ready Excel file.",
    href: "/runs",
    actionLabel: "View Runs",
  },
];

function storageKey(scopeId: string): string {
  return `nyccompliance:onboarding:${scopeId}`;
}

export function getCompletedSteps(scopeId: string): Set<OnboardingStepId> {
  if (typeof window === "undefined") return new Set();
  try {
    const raw = window.localStorage.getItem(storageKey(scopeId));
    if (!raw) return new Set();
    const parsed = JSON.parse(raw);
    return new Set(Array.isArray(parsed) ? parsed : []);
  } catch {
    return new Set();
  }
}

export function markStepComplete(scopeId: string, stepId: OnboardingStepId): void {
  if (typeof window === "undefined") return;
  try {
    const existing = getCompletedSteps(scopeId);
    existing.add(stepId);
    window.localStorage.setItem(storageKey(scopeId), JSON.stringify(Array.from(existing)));
  } catch {
    // ignore
  }
}

export function markStepIncomplete(scopeId: string, stepId: OnboardingStepId): void {
  if (typeof window === "undefined") return;
  try {
    const existing = getCompletedSteps(scopeId);
    existing.delete(stepId);
    window.localStorage.setItem(storageKey(scopeId), JSON.stringify(Array.from(existing)));
  } catch {
    // ignore
  }
}

export function isOnboardingComplete(scopeId: string): boolean {
  const done = getCompletedSteps(scopeId);
  return ONBOARDING_STEPS.every((s) => done.has(s.id));
}

/**
 * Derive completed steps automatically from live stats — used on Dashboard
 * so no manual tracking is needed for the first few steps.
 */
export function deriveCompletedSteps(opts: {
  hasProject: boolean;
  hasDocuments: boolean;
  hasRun: boolean;
  hasReviewActivity: boolean;
  hasExport: boolean;
}): Set<OnboardingStepId> {
  const done = new Set<OnboardingStepId>();
  if (opts.hasProject) done.add("create_project");
  if (opts.hasDocuments) done.add("upload_docs");
  if (opts.hasRun) {
    done.add("upload_questionnaire");
    done.add("run_analysis");
  }
  if (opts.hasReviewActivity) done.add("review_low_confidence");
  if (opts.hasExport) done.add("export");
  return done;
}

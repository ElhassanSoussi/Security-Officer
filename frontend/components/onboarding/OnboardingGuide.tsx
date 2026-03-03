"use client";

import { useEffect, useMemo, useState, useCallback } from "react";
import { useRouter } from "next/navigation";
import Link from "next/link";
import { Sparkles, ArrowRight, X } from "lucide-react";

import { ApiClient } from "@/lib/api";
import { createClient } from "@/utils/supabase/client";
import { getStoredOrgId, setStoredOrgId } from "@/lib/orgContext";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";

type OnboardingStep = 1 | 2 | 3 | 4 | 5;

const SKIP_KEY = (orgId: string) => `nyccompliance:onboarding:skip:${orgId}`;

const STEPS: Record<OnboardingStep, { title: string; description: string; href: string; cta: string }>= {
  1: {
    title: "Upload compliance documents",
    description: "Add policies, SOPs, certificates, and evidence. These documents ground all answers.",
    href: "/projects",
    cta: "Upload documents",
  },
  2: {
    title: "Create a project",
    description: "Projects organize your documents, runs, audit activity, and exports for a specific bid.",
    href: "/projects",
    cta: "Create project",
  },
  3: {
    title: "Upload questionnaire (Run)",
    description: "Upload the Excel questionnaire and start analysis to generate draft answers.",
    href: "/run",
    cta: "Start a run",
  },
  4: {
    title: "Review answers",
    description: "Approve or reject at least one answer to establish a review trail.",
    href: "/audit",
    cta: "Open review",
  },
  5: {
    title: "Export",
    description: "Generate and download a submission-ready Excel file.",
    href: "/run",
    cta: "Generate export",
  },
};

function safeParseInt(v: any, fallback: OnboardingStep): OnboardingStep {
  const n = Number(v);
  if (!Number.isFinite(n)) return fallback;
  const i = Math.trunc(n);
  if (i < 1) return 1;
  if (i > 5) return 5;
  return i as OnboardingStep;
}

export function OnboardingGuide({ variant = "banner" }: { variant?: "banner" | "card" }) {
  const router = useRouter();
  const [orgId, setOrgId] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string>("");

  const [completed, setCompleted] = useState(false);
  const [step, setStep] = useState<OnboardingStep>(1);
  const [skipped, setSkipped] = useState(false);

  const [metrics, setMetrics] = useState<{ documents_count: number; projects_count: number; runs_count: number; reviewed_count: number; exports_count: number } | null>(null);

  const stepMeta = useMemo(() => STEPS[step], [step]);

  const maybeAdvanceFromMetrics = useCallback(async (
    tok: string,
    currentStep: OnboardingStep,
    isCompleted: boolean,
    m: { documents_count: number; projects_count: number; runs_count: number; reviewed_count: number; exports_count: number }
  ) => {
    if (isCompleted) return;

    let next = currentStep;

    if (next === 1 && (m.documents_count || 0) >= 1) next = 2;
    if (next === 2 && (m.projects_count || 0) >= 1) next = 3;
    if (next === 3 && (m.runs_count || 0) >= 1) next = 4;
    if (next === 4 && (m.reviewed_count || 0) >= 1) next = 5;

    // Step 5 completion: exports_count>=1
    if (next === 5 && (m.exports_count || 0) >= 1) {
      setCompleted(true);
      try {
        await ApiClient.patchOnboardingState({ onboarding_completed: true, onboarding_step: 5 }, tok);
      } catch {
        // ignore: never block UI
      }
      return;
    }

    if (next !== currentStep) {
      setStep(next);
      try {
        await ApiClient.patchOnboardingState({ onboarding_step: next }, tok);
      } catch {
        // ignore: never block UI
      }
    }
  }, []);

  const loadState = useCallback(async () => {
    setLoading(true);
    setError("");
    try {
      const supabase = createClient();
      const { data: { session } } = await supabase.auth.getSession();
      const tok = session?.access_token;
      if (!tok) {
        router.push("/login");
        return;
      }

      // keep org selection consistent with rest of app
      const orgs = await ApiClient.getMyOrgs(tok);
      if (!orgs || orgs.length === 0) {
        router.push("/onboarding");
        return;
      }
      const stored = getStoredOrgId() || "";
      const selected = orgs.find((o: any) => o.id === stored) || orgs[0];
      setStoredOrgId(selected.id);
      setOrgId(selected.id);

      const st = await ApiClient.getOnboardingState(tok);
      const isCompleted = Boolean(st?.onboarding_completed);
      const s = safeParseInt(st?.onboarding_step, 1);
      setCompleted(isCompleted);
      setStep(s);

      // local skip (non-annoying UX)
      try {
        const raw = window.localStorage.getItem(SKIP_KEY(selected.id));
        setSkipped(raw === "1");
      } catch {
        setSkipped(false);
      }

      const m = await ApiClient.getOrgMetrics(tok);
      setMetrics(m);

      // auto-advance server state if metrics show completion
      await maybeAdvanceFromMetrics(tok, s, isCompleted, m);

    } catch (e: any) {
      setError(e?.message || "Failed to load onboarding");
    } finally {
      setLoading(false);
    }
  }, [router, maybeAdvanceFromMetrics]);

  useEffect(() => {
    loadState();
  }, [loadState]);

  const handleSkip = async () => {
    if (!orgId) return;
    try {
      window.localStorage.setItem(SKIP_KEY(orgId), "1");
    } catch {
      // ignore
    }
    setSkipped(true);
  };

  const handleGo = () => {
    router.push(stepMeta.href);
  };

  const handleUnskip = () => {
    if (!orgId) return;
    try { window.localStorage.removeItem(SKIP_KEY(orgId)); } catch {}
    setSkipped(false);
  };

  // If complete: render nothing
  if (loading) return null;
  if (completed) return null;

  // If skipped: subtle persistent card only (dashboard usage)
  if (skipped) {
    return (
      <Card className={variant === "banner" ? "border-border" : "border-border"}>
        <CardHeader className="pb-2">
          <div className="flex items-center justify-between gap-3">
            <div className="min-w-0">
              <CardTitle className="text-sm">Next step</CardTitle>
              <CardDescription className="text-xs">{stepMeta.title}</CardDescription>
            </div>
            <div className="flex gap-2 shrink-0">
              <Button size="sm" variant="outline" onClick={handleUnskip}>Resume</Button>
              <Button size="sm" onClick={handleGo}>
                {stepMeta.cta} <ArrowRight className="ml-1.5 h-4 w-4" />
              </Button>
            </div>
          </div>
        </CardHeader>
      </Card>
    );
  }

  const progressLabel = `Step ${step} of 5`;

  return (
    <Card className={
      variant === "banner"
        ? "border-blue-100 bg-gradient-to-br from-blue-50/40 to-background"
        : "border-blue-100"
    }>
      <CardHeader className="pb-2">
        <div className="flex items-start justify-between gap-3">
          <div className="flex items-start gap-2.5 min-w-0">
            <div className="rounded-md bg-blue-100 p-1.5 mt-0.5">
              <Sparkles className="h-4 w-4 text-blue-600" />
            </div>
            <div className="min-w-0">
              <CardTitle className="text-base truncate">{stepMeta.title}</CardTitle>
              <CardDescription className="text-sm">{stepMeta.description}</CardDescription>
              <div className="mt-2 flex items-center gap-2">
                <Badge variant="outline" className="text-xs bg-blue-50 text-blue-700 border-blue-200">
                  {progressLabel}
                </Badge>
                {error && (
                  <span className="text-xs text-muted-foreground">{error}</span>
                )}
              </div>
            </div>
          </div>
          <button
            type="button"
            className="rounded p-1 text-muted-foreground hover:text-foreground hover:bg-muted transition-colors"
            onClick={handleSkip}
            aria-label="Skip onboarding for now"
          >
            <X className="h-4 w-4" />
          </button>
        </div>
      </CardHeader>
      <CardContent className="pt-0">
        <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-2">
          <div className="text-xs text-muted-foreground">
            You can skip for now — we&apos;ll keep a subtle next-step card on your dashboard.
          </div>
          <div className="flex gap-2">
            <Button variant="outline" onClick={handleSkip}>Skip for now</Button>
            <Button onClick={handleGo}>
              {stepMeta.cta} <ArrowRight className="ml-1.5 h-4 w-4" />
            </Button>
          </div>
        </div>

        {/* Lightweight, deterministic completion hint */}
        {metrics && (
          <div className="mt-3 text-xs text-muted-foreground">
            <span className="font-medium text-foreground">Progress signals:</span> documents {metrics.documents_count}, projects {metrics.projects_count}, runs {metrics.runs_count}, reviewed {metrics.reviewed_count}, exports {metrics.exports_count}
          </div>
        )}

        {/* Optional explicit "Mark done" for step 5 if export just happened client-side */}
        {step === 5 && (
          <div className="mt-3">
            <Link href="/runs" className="text-xs text-blue-700 hover:underline">View exports →</Link>
          </div>
        )}
      </CardContent>
    </Card>
  );
}

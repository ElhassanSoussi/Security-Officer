"use client";

/**
 * OnboardingChecklist component.
 * Persistent, collapsible onboarding checklist.
 * Auto-derives progress from live stats; can be dismissed per-scope.
 */

import { useState, useEffect } from "react";
import { CheckCircle, Circle, ChevronDown, ChevronUp, X, Sparkles } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import Link from "next/link";
import {
  ONBOARDING_STEPS,
  OnboardingStepId,
  deriveCompletedSteps,
} from "@/lib/onboarding";

interface OnboardingChecklistProps {
  /** Unique scope key (org ID or project ID) — used for localStorage. */
  scopeId: string;
  /** Derived from live data: which steps are logically done. */
  completedSteps?: Set<OnboardingStepId>;
  /** Stats-derived options (alternative to passing completedSteps). */
  derivedFrom?: {
    hasProject: boolean;
    hasDocuments: boolean;
    hasRun: boolean;
    hasReviewActivity: boolean;
    hasExport: boolean;
  };
  /** If true, hide when all steps are complete. Default: true */
  hideWhenComplete?: boolean;
  /** Card title override */
  title?: string;
  className?: string;
}

const DISMISS_KEY = (scopeId: string) => `nyccompliance:onboarding:dismissed:${scopeId}`;

export function OnboardingChecklist({
  scopeId,
  completedSteps,
  derivedFrom,
  hideWhenComplete = true,
  title = "Getting Started",
  className = "",
}: OnboardingChecklistProps) {
  const [collapsed, setCollapsed] = useState(false);
  const [dismissed, setDismissed] = useState(false);
  const [mounted, setMounted] = useState(false);

  useEffect(() => {
    setMounted(true);
    try {
      const d = window.localStorage.getItem(DISMISS_KEY(scopeId));
      if (d === "1") setDismissed(true);
    } catch {
      // ignore
    }
  }, [scopeId]);

  const done: Set<OnboardingStepId> =
    completedSteps ??
    (derivedFrom ? deriveCompletedSteps(derivedFrom) : new Set());

  const completedCount = ONBOARDING_STEPS.filter((s) => done.has(s.id)).length;
  const totalCount = ONBOARDING_STEPS.length;
  const allDone = completedCount === totalCount;

  const handleDismiss = () => {
    try {
      window.localStorage.setItem(DISMISS_KEY(scopeId), "1");
    } catch {
      // ignore
    }
    setDismissed(true);
  };

  // Don't render until mounted (avoids SSR hydration mismatch)
  if (!mounted) return null;
  if (dismissed) return null;
  if (allDone && hideWhenComplete) return null;

  const progressPct = Math.round((completedCount / totalCount) * 100);

  return (
    <Card className={`border-border ${className}`}>
      <CardHeader className="pb-2">
        <div className="flex items-center justify-between">
          <div className="flex items-center gap-2">
            <Sparkles className="h-4 w-4 text-blue-600" />
            <CardTitle className="text-sm font-semibold">{title}</CardTitle>
            <Badge
              variant="outline"
              className="text-[10px] bg-muted/50 text-muted-foreground border-border px-1.5 py-0"
            >
              {completedCount}/{totalCount}
            </Badge>
          </div>
          <div className="flex items-center gap-1">
            <button
              type="button"
              onClick={() => setCollapsed((c) => !c)}
              className="rounded p-1 text-muted-foreground hover:text-foreground hover:bg-muted transition-colors"
              aria-label={collapsed ? "Expand checklist" : "Collapse checklist"}
            >
              {collapsed ? (
                <ChevronDown className="h-4 w-4" />
              ) : (
                <ChevronUp className="h-4 w-4" />
              )}
            </button>
            <button
              type="button"
              onClick={handleDismiss}
              className="rounded p-1 text-muted-foreground hover:text-foreground hover:bg-muted transition-colors"
              aria-label="Dismiss checklist"
            >
              <X className="h-4 w-4" />
            </button>
          </div>
        </div>

                {/* Progress Bar */}
        <div className="mt-2">
          <progress
            value={completedCount}
            max={totalCount}
            aria-label={`Onboarding progress: ${completedCount} of ${totalCount} steps complete`}
            className="w-full h-1 rounded-full overflow-hidden accent-blue-500 [&::-webkit-progress-bar]:rounded-full [&::-webkit-progress-bar]:bg-muted [&::-webkit-progress-value]:rounded-full [&::-webkit-progress-value]:bg-blue-500 [&::-moz-progress-bar]:bg-blue-500 [&::-moz-progress-bar]:rounded-full"
          />
          <p className="mt-1 text-[11px] text-muted-foreground">
            {allDone
              ? "🎉 All steps complete!"
              : `${progressPct}% — ${totalCount - completedCount} remaining`}
          </p>
        </div>
      </CardHeader>

      {!collapsed && (
        <CardContent className="pt-0">
          <ol className="space-y-1">
            {ONBOARDING_STEPS.map((step) => {
              const isDone = done.has(step.id);
              return (
                <li
                  key={step.id}
                  className={`flex items-center justify-between gap-3 rounded-md px-3 py-1.5 transition-colors text-sm ${
                    isDone
                      ? "bg-muted/40 text-muted-foreground"
                      : "hover:bg-muted/30"
                  }`}
                >
                  <div className="flex items-center gap-2 min-w-0">
                    <div className="shrink-0">
                      {isDone ? (
                        <CheckCircle className="h-3.5 w-3.5 text-green-600" />
                      ) : (
                        <Circle className="h-3.5 w-3.5 text-muted-foreground/40" />
                      )}
                    </div>
                    <span
                      className={`text-sm ${
                        isDone ? "line-through decoration-muted-foreground/30" : "text-foreground font-medium"
                      }`}
                    >
                      {step.label}
                    </span>
                  </div>
                  {!isDone && (
                    <Link href={step.href} className="shrink-0">
                      <Button
                        size="sm"
                        variant="ghost"
                        className="h-6 text-xs px-2 text-muted-foreground hover:text-foreground"
                      >
                        {step.actionLabel} →
                      </Button>
                    </Link>
                  )}
                </li>
              );
            })}
          </ol>
        </CardContent>
      )}
    </Card>
  );
}

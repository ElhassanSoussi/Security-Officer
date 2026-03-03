"use client";

import { useEffect, useState } from "react";
import Link from "next/link";

import { ApiClient } from "@/lib/api";
import { createClient } from "@/utils/supabase/client";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";

export function OnboardingStepBanner({ expectedStep }: { expectedStep: 1 | 2 | 3 | 4 | 5 }) {
  const [loading, setLoading] = useState(true);
  const [show, setShow] = useState(false);
  const [step, setStep] = useState<number>(1);

  useEffect(() => {
    const run = async () => {
      try {
        const supabase = createClient();
        const { data: { session } } = await supabase.auth.getSession();
        const tok = session?.access_token;
        if (!tok) {
          setLoading(false);
          return;
        }
        const st = await ApiClient.getOnboardingState(tok);
        if (st?.onboarding_completed) {
          setShow(false);
          setLoading(false);
          return;
        }
        const s = Number(st?.onboarding_step || 1);
        setStep(s);
        setShow(s === expectedStep);
      } catch {
        // never block page render
      } finally {
        setLoading(false);
      }
    };
    run();
  }, [expectedStep]);

  if (loading) return null;
  if (!show) return null;

  return (
    <div className="rounded-lg border border-blue-100 bg-blue-50/40 px-3 py-2 flex items-center justify-between gap-3">
      <div className="min-w-0">
        <div className="flex items-center gap-2">
          <Badge variant="outline" className="text-[11px] bg-white border-blue-200 text-blue-700">
            Onboarding
          </Badge>
          <span className="text-xs text-muted-foreground">Step {step} of 5</span>
        </div>
        <p className="text-sm font-medium mt-1">You’re on step {step}. Complete this action to continue.</p>
      </div>
      <Link href="/dashboard" className="shrink-0">
        <Button size="sm" variant="outline">View guide</Button>
      </Link>
    </div>
  );
}

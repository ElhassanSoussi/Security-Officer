/**
 * StepHeader — horizontal stepper for multi-step wizards.
 */
import * as React from "react";
import { CheckCircle2 } from "lucide-react";
import { cn } from "@/lib/utils";

export interface Step {
  id: string;
  label: string;
  icon?: React.ComponentType<{ className?: string }>;
}

export interface StepHeaderProps {
  steps: Step[];
  currentStepId: string;
  className?: string;
}

export function StepHeader({ steps, currentStepId, className }: StepHeaderProps) {
  const currentIdx = steps.findIndex((s) => s.id === currentStepId);

  return (
    <nav aria-label="Progress" className={cn("flex items-center gap-0", className)}>
      {steps.map((step, i) => {
        const Icon = step.icon;
        const isActive = step.id === currentStepId;
        const isDone = currentIdx > i;

        return (
          <div key={step.id} className="flex items-center flex-1 last:flex-none">
            <div
              className={cn(
                "flex items-center gap-2 rounded-md px-3.5 py-2 text-sm font-medium transition-colors select-none",
                isActive && "bg-primary text-primary-foreground shadow-sm",
                isDone && "bg-green-50 text-green-700 border border-green-200",
                !isActive && !isDone && "bg-muted text-muted-foreground"
              )}
            >
              {isDone ? (
                <CheckCircle2 className="h-4 w-4 shrink-0" />
              ) : Icon ? (
                <Icon className="h-4 w-4 shrink-0" />
              ) : (
                <span className="flex h-4 w-4 shrink-0 items-center justify-center rounded-full border-2 border-current text-[10px] font-bold leading-none">
                  {i + 1}
                </span>
              )}
              <span className="hidden sm:inline">{step.label}</span>
            </div>
            {i < steps.length - 1 && (
              <div
                className={cn(
                  "h-px flex-1 mx-2",
                  isDone ? "bg-green-300" : isActive ? "bg-primary/30" : "bg-border"
                )}
              />
            )}
          </div>
        );
      })}
    </nav>
  );
}

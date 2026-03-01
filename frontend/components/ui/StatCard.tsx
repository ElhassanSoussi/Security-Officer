/**
 * StatCard — compact metric display for dashboards.
 */
import * as React from "react";
import { Card } from "@/components/ui/card";
import { cn } from "@/lib/utils";

export interface StatCardProps {
  /** Metric label */
  label: string;
  /** Metric value (number or formatted string) */
  value: React.ReactNode;
  /** Optional icon component */
  icon?: React.ReactNode;
  /** Optional colour classes for the icon bg */
  iconClassName?: string;
  /** Optional delta text like "+12%" */
  delta?: string;
  /** delta colour variant */
  deltaType?: "positive" | "negative" | "neutral";
  /** Loading state */
  loading?: boolean;
  className?: string;
}

export function StatCard({
  label,
  value,
  icon,
  iconClassName,
  delta,
  deltaType = "neutral",
  loading,
  className,
}: StatCardProps) {
  const deltaColor =
    deltaType === "positive"
      ? "text-green-600"
      : deltaType === "negative"
        ? "text-red-600"
        : "text-muted-foreground";

  return (
    <Card className={cn("p-5", className)}>
      <div className="flex items-start justify-between gap-3">
        <div className="min-w-0 space-y-1">
          <p className="text-sm font-medium text-muted-foreground truncate">{label}</p>
          <div className="flex items-baseline gap-2">
            {loading ? (
              <div className="h-8 w-16 rounded bg-muted animate-pulse" />
            ) : (
              <span className="text-2xl font-bold tracking-tight">{value}</span>
            )}
            {delta && !loading && (
              <span className={cn("text-xs font-medium", deltaColor)}>{delta}</span>
            )}
          </div>
        </div>
        {icon && (
          <div
            className={cn(
              "flex h-10 w-10 shrink-0 items-center justify-center rounded-lg",
              iconClassName || "bg-primary/10 text-primary"
            )}
          >
            {icon}
          </div>
        )}
      </div>
    </Card>
  );
}

/**
 * PageShell — standard page wrapper for every authenticated page.
 *
 * Handles: max-width constraint, title, subtitle, optional actions slot,
 * consistent vertical rhythm.
 */
import * as React from "react";
import { cn } from "@/lib/utils";

export interface PageShellProps {
  /** Page title (text-2xl font-semibold) */
  title: React.ReactNode;
  /** Optional subtitle (text-sm text-muted-foreground) */
  subtitle?: React.ReactNode;
  /** Slot for primary action buttons (top-right) */
  actions?: React.ReactNode;
  /** Additional className on the outer wrapper */
  className?: string;
  /** Page body */
  children: React.ReactNode;
  /** Max-width variant */
  size?: "md" | "lg" | "xl" | "full";
}

const maxWidthMap: Record<string, string> = {
  md: "max-w-3xl",
  lg: "max-w-5xl",
  xl: "max-w-6xl",
  full: "",
};

export function PageShell({
  title,
  subtitle,
  actions,
  className,
  children,
  size = "xl",
}: PageShellProps) {
  return (
    <div className={cn("mx-auto w-full space-y-6", maxWidthMap[size], className)}>
      {/* Header */}
      <div className="flex flex-col gap-1 sm:flex-row sm:items-start sm:justify-between sm:gap-4">
        <div className="min-w-0">
          <h1 className="text-2xl font-semibold tracking-tight text-foreground">{title}</h1>
          {subtitle && (
            <p className="mt-1 text-sm leading-6 text-muted-foreground">{subtitle}</p>
          )}
        </div>
        {actions && (
          <div className="flex shrink-0 items-center gap-2 pt-1 sm:pt-0">{actions}</div>
        )}
      </div>

      {/* Body */}
      {children}
    </div>
  );
}

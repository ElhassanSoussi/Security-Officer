import * as React from "react";
import { cn } from "@/lib/utils";

export default function PageHeader({
  title,
  subtitle,
  actions,
  breadcrumbs,
  className,
}: {
  title: React.ReactNode;
  subtitle?: React.ReactNode;
  actions?: React.ReactNode;
  breadcrumbs?: React.ReactNode;
  className?: string;
}) {
  return (
    <div className={cn("mb-6", className)}>
      {breadcrumbs && <div className="mb-4">{breadcrumbs}</div>}
      <div className="flex items-start justify-between gap-4">
        <div>
          <h1 className="text-2xl font-semibold tracking-tight text-foreground">{title}</h1>
          {subtitle && <p className="text-sm leading-6 text-muted-foreground mt-1">{subtitle}</p>}
        </div>
        {actions && <div className="flex items-start gap-2 shrink-0">{actions}</div>}
      </div>
    </div>
  );
}

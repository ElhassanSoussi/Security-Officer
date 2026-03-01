import * as React from "react";
import { cn } from "@/lib/utils";

export interface EmptyStateProps {
  icon?: React.ReactNode;
  title: React.ReactNode;
  description?: React.ReactNode;
  action?: React.ReactNode;
  className?: string;
}

export function EmptyState({ icon, title, description, action, className }: EmptyStateProps) {
  return (
    <div className={cn("flex flex-col items-center justify-center p-8 text-center text-muted-foreground", className)}>
      {icon && <div className="mb-4 text-muted-foreground/70">{icon}</div>}
      <h3 className="text-lg font-semibold text-foreground">{title}</h3>
      {description && <p className="mt-1 text-sm">{description}</p>}
      {action && <div className="mt-4">{action}</div>}
    </div>
  );
}

export interface TableEmptyStateProps {
  cols: number;
  icon?: React.ReactNode;
  title: React.ReactNode;
  description?: React.ReactNode;
  action?: React.ReactNode;
}

export function TableEmptyState({ cols, icon, title, description, action }: TableEmptyStateProps) {
  return (
    <tr>
      <td colSpan={cols} className="py-16">
        <EmptyState icon={icon} title={title} description={description} action={action} />
      </td>
    </tr>
  );
}

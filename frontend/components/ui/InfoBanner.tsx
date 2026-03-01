/**
 * InfoBanner — prominent inline info/warning/error banner.
 */
import * as React from "react";
import { Info, AlertTriangle, CheckCircle2, XCircle } from "lucide-react";
import { cn } from "@/lib/utils";

export interface InfoBannerProps {
  variant?: "info" | "success" | "warning" | "error";
  title?: string;
  children: React.ReactNode;
  className?: string;
}

const config = {
  info:    { icon: Info,          border: "border-blue-200",  bg: "bg-blue-50",   text: "text-blue-800" },
  success: { icon: CheckCircle2, border: "border-green-200", bg: "bg-green-50",  text: "text-green-800" },
  warning: { icon: AlertTriangle, border: "border-amber-200", bg: "bg-amber-50", text: "text-amber-800" },
  error:   { icon: XCircle,       border: "border-red-200",   bg: "bg-red-50",   text: "text-red-700" },
};

export function InfoBanner({ variant = "info", title, children, className }: InfoBannerProps) {
  const c = config[variant];
  const Icon = c.icon;
  return (
    <div className={cn("rounded-lg border px-4 py-3 flex items-start gap-3", c.border, c.bg, c.text, className)}>
      <Icon className="h-4 w-4 mt-0.5 shrink-0" />
      <div className="text-sm leading-relaxed">
        {title && <span className="font-semibold">{title} </span>}
        {children}
      </div>
    </div>
  );
}

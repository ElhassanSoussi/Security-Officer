/**
 * AnswerStatusBadge — renders the answer-level status as a semantic badge.
 */
"use client";

import * as React from "react";
import { Badge } from "@/components/ui/badge";
import { Check, Eye, Flag, Pencil, Sparkles } from "lucide-react";
import { cn } from "@/lib/utils";
import type { AnswerStatus } from "@/types";

interface AnswerStatusBadgeProps {
  status: AnswerStatus | string;
  className?: string;
}

const STATUS_CONFIG: Record<string, { label: string; icon: React.ElementType; classes: string }> = {
  auto_generated: {
    label: "Auto-generated",
    icon: Sparkles,
    classes: "bg-blue-50 text-blue-700 border-blue-200",
  },
  under_review: {
    label: "Under Review",
    icon: Eye,
    classes: "bg-amber-50 text-amber-700 border-amber-200",
  },
  approved: {
    label: "Approved",
    icon: Check,
    classes: "bg-green-50 text-green-700 border-green-200",
  },
  flagged: {
    label: "Flagged",
    icon: Flag,
    classes: "bg-red-50 text-red-700 border-red-200",
  },
  edited: {
    label: "Edited",
    icon: Pencil,
    classes: "bg-purple-50 text-purple-700 border-purple-200",
  },
};

export function AnswerStatusBadge({ status, className }: AnswerStatusBadgeProps) {
  const config = STATUS_CONFIG[status] || STATUS_CONFIG.auto_generated;
  const Icon = config.icon;

  return (
    <Badge variant="outline" className={cn("text-xs gap-1", config.classes, className)}>
      <Icon className="h-3 w-3" />
      {config.label}
    </Badge>
  );
}

/** Maps legacy review_status to AnswerStatus */
export function deriveAnswerStatus(item: {
  review_status?: string;
  edited_by_user?: boolean;
  confidence?: string;
  is_verified?: boolean;
}): AnswerStatus {
  if (item.review_status === "approved") return "approved";
  if (item.review_status === "rejected") return "flagged";
  if (item.edited_by_user) return "edited";
  if (item.confidence === "LOW") return "under_review";
  return "auto_generated";
}

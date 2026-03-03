"use client";

/**
 * AuditFilterChips component.
 * Quick-filter chip bar for the Audit review table.
 */

export type AuditFilterChip =
  | "all"
  | "high"
  | "medium"
  | "low"
  | "pending"
  | "approved"
  | "rejected";

interface ChipDef {
  id: AuditFilterChip;
  label: string;
  colorActive: string;
  colorInactive: string;
}

const CHIPS: ChipDef[] = [
  {
    id: "all",
    label: "All",
    colorActive: "bg-foreground text-background border-foreground",
    colorInactive: "bg-background text-foreground border-border hover:bg-muted",
  },
  {
    id: "high",
    label: "High Confidence",
    colorActive: "bg-green-600 text-white border-green-600",
    colorInactive: "bg-background text-green-700 border-green-200 hover:bg-green-50",
  },
  {
    id: "medium",
    label: "Medium Confidence",
    colorActive: "bg-amber-500 text-white border-amber-500",
    colorInactive: "bg-background text-amber-700 border-amber-200 hover:bg-amber-50",
  },
  {
    id: "low",
    label: "Low Confidence",
    colorActive: "bg-red-600 text-white border-red-600",
    colorInactive: "bg-background text-red-700 border-red-200 hover:bg-red-50",
  },
  {
    id: "pending",
    label: "Pending",
    colorActive: "bg-orange-500 text-white border-orange-500",
    colorInactive: "bg-background text-orange-700 border-orange-200 hover:bg-orange-50",
  },
  {
    id: "approved",
    label: "Approved",
    colorActive: "bg-blue-600 text-white border-blue-600",
    colorInactive: "bg-background text-blue-700 border-blue-200 hover:bg-blue-50",
  },
  {
    id: "rejected",
    label: "Rejected",
    colorActive: "bg-slate-700 text-white border-slate-700",
    colorInactive: "bg-background text-slate-700 border-slate-300 hover:bg-slate-50",
  },
];

interface AuditFilterChipsProps {
  active: AuditFilterChip;
  onChange: (chip: AuditFilterChip) => void;
  counts?: Partial<Record<AuditFilterChip, number>>;
  className?: string;
}

export function AuditFilterChips({
  active,
  onChange,
  counts = {},
  className = "",
}: AuditFilterChipsProps) {
  return (
    <div className={`flex flex-wrap gap-2 ${className}`}>
      {CHIPS.map((chip) => {
        const isActive = active === chip.id;
        const count = counts[chip.id];
        const ariaAttrs = isActive ? { "aria-pressed": true as const } : { "aria-pressed": false as const };
        return (
          <button
            key={chip.id}
            type="button"
            onClick={() => onChange(chip.id)}
            className={`inline-flex items-center gap-1.5 rounded-full border px-3 py-1 text-xs font-medium transition-colors ${
              isActive ? chip.colorActive : chip.colorInactive
            }`}
            {...ariaAttrs}
          >
            {chip.label}
            {count !== undefined && (
              <span
                className={`rounded-full px-1.5 py-0 text-[10px] font-bold ${
                  isActive ? "bg-white/20" : "bg-muted text-muted-foreground"
                }`}
              >
                {count}
              </span>
            )}
          </button>
        );
      })}
    </div>
  );
}

/**
 * Filter a list of audit rows based on the active chip.
 */
export function applyAuditChipFilter(
  rows: any[],
  chip: AuditFilterChip
): any[] {
  if (chip === "all") return rows;
  if (chip === "approved" || chip === "pending" || chip === "rejected") {
    return rows.filter(
      (r) =>
        String(r.review_status || "pending").toLowerCase() === chip
    );
  }
  // Confidence chips
  return rows.filter((r) => {
    const raw = String(r.confidence_score || "").trim().toUpperCase();
    if (raw === "HIGH" || raw === "MEDIUM" || raw === "LOW") {
      return raw.toLowerCase() === chip;
    }
    const ratio =
      typeof r.confidence_score === "number" ? r.confidence_score : parseFloat(r.confidence_score);
    if (isNaN(ratio)) return chip === "medium";
    const normalized = ratio > 1 ? ratio / 100 : ratio;
    if (chip === "high") return normalized >= 0.8;
    if (chip === "medium") return normalized >= 0.5 && normalized < 0.8;
    return normalized < 0.5;
  });
}

/**
 * Compute counts for each chip from a list of audit rows.
 */
export function computeChipCounts(
  rows: any[]
): Partial<Record<AuditFilterChip, number>> {
  const counts: Partial<Record<AuditFilterChip, number>> = { all: rows.length };
  for (const chip of ["high", "medium", "low", "pending", "approved", "rejected"] as AuditFilterChip[]) {
    counts[chip] = applyAuditChipFilter(rows, chip).length;
  }
  return counts;
}

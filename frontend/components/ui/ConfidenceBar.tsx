/**
 * ConfidenceBar — lightweight horizontal bar chart for confidence distribution.
 * No external chart library needed.
 */
"use client";

import * as React from "react";
import { cn } from "@/lib/utils";

export interface BarSegment {
  label: string;
  value: number;
  color: string;
}

interface ConfidenceBarProps {
  segments: BarSegment[];
  height?: string;
  showLegend?: boolean;
  className?: string;
}

export function ConfidenceBar({
  segments,
  height = "h-3",
  showLegend = true,
  className,
}: ConfidenceBarProps) {
  const total = segments.reduce((sum, s) => sum + s.value, 0);
  if (total === 0) return null;

  return (
    <div className={cn("space-y-2", className)}>
      <div className={cn("flex w-full overflow-hidden rounded-full bg-muted", height)}>
        {segments.map((seg) => {
          const pct = (seg.value / total) * 100;
          if (pct === 0) return null;
          return (
            <div
              key={seg.label}
              className={cn("transition-all duration-500", seg.color)}
              style={{ width: `${pct}%` }}
              title={`${seg.label}: ${seg.value} (${Math.round(pct)}%)`}
            />
          );
        })}
      </div>
      {showLegend && (
        <div className="flex flex-wrap gap-x-4 gap-y-1">
          {segments.map((seg) => (
            <div key={seg.label} className="flex items-center gap-1.5 text-xs text-muted-foreground">
              <div className={cn("h-2.5 w-2.5 rounded-full", seg.color)} />
              <span>{seg.label}</span>
              <span className="font-semibold text-foreground">{seg.value}</span>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}

/**
 * MiniBarChart — simple vertical bar chart for monthly trends.
 */
interface MiniBarChartProps {
  data: { label: string; value: number }[];
  barColor?: string;
  maxHeight?: number;
  className?: string;
}

export function MiniBarChart({
  data,
  barColor = "bg-primary",
  maxHeight = 64,
  className,
}: MiniBarChartProps) {
  const maxVal = Math.max(...data.map((d) => d.value), 1);

  return (
    <div className={cn("flex items-end gap-1", className)}>
      {data.map((d) => {
        const h = Math.max(4, (d.value / maxVal) * maxHeight);
        return (
          <div key={d.label} className="flex flex-col items-center gap-1 flex-1 min-w-0">
            <span className="text-[10px] font-medium text-muted-foreground">{d.value}</span>
            <div
              className={cn("w-full rounded-t", barColor, "transition-all duration-300")}
              style={{ height: `${h}px`, minWidth: "8px" }}
              title={`${d.label}: ${d.value}`}
            />
            <span className="text-[9px] text-muted-foreground truncate w-full text-center">
              {d.label}
            </span>
          </div>
        );
      })}
    </div>
  );
}

/**
 * RiskBadge — semantic badge for risk level.
 */
interface RiskBadgeProps {
  level: "high" | "medium" | "low";
  className?: string;
}

export function RiskBadge({ level, className }: RiskBadgeProps) {
  const styles = {
    high: "bg-red-100 text-red-800 border-red-200",
    medium: "bg-amber-100 text-amber-800 border-amber-200",
    low: "bg-green-100 text-green-800 border-green-200",
  };

  return (
    <span
      className={cn(
        "inline-flex items-center gap-1 rounded-full border px-2.5 py-0.5 text-xs font-semibold",
        styles[level],
        className
      )}
    >
      {level === "high" && "⚠"}
      {level === "medium" && "◉"}
      {level === "low" && "✓"}
      {level.charAt(0).toUpperCase() + level.slice(1)} Risk
    </span>
  );
}

/**
 * ScoreGauge — circular-ish readiness score display.
 */
interface ScoreGaugeProps {
  score: number; // 0-100
  label: string;
  size?: "sm" | "md";
  className?: string;
}

export function ScoreGauge({ score, label, size = "md", className }: ScoreGaugeProps) {
  const clampedScore = Math.max(0, Math.min(100, Math.round(score)));
  const color =
    clampedScore >= 80
      ? "text-green-600 border-green-200 bg-green-50"
      : clampedScore >= 50
        ? "text-amber-600 border-amber-200 bg-amber-50"
        : "text-red-600 border-red-200 bg-red-50";

  const dimensions = size === "sm" ? "h-16 w-16" : "h-20 w-20";

  return (
    <div className={cn("flex flex-col items-center gap-1.5", className)}>
      <div
        className={cn(
          "flex items-center justify-center rounded-full border-2 font-bold",
          dimensions,
          color
        )}
      >
        <span className={size === "sm" ? "text-lg" : "text-2xl"}>{clampedScore}</span>
      </div>
      <span className="text-xs font-medium text-muted-foreground text-center">{label}</span>
    </div>
  );
}

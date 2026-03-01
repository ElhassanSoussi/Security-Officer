/**
 * SourceTransparency — collapsible citation panel for each answer in ReviewGrid.
 * Shows confidence %, source document, citation preview, and reasoning summary.
 */
"use client";

import * as React from "react";
import { useState } from "react";
import { ChevronDown, ChevronRight, FileText, Percent, Quote, Lightbulb } from "lucide-react";
import { Badge } from "@/components/ui/badge";
import { cn } from "@/lib/utils";

interface SourceTransparencyProps {
  confidence: string; // "HIGH" | "MEDIUM" | "LOW"
  confidenceScore?: number | null; // raw 0-1
  sourceDocument?: string;
  sourceExcerpt?: string;
  sourcePage?: number;
  question?: string;
  className?: string;
}

export function SourceTransparency({
  confidence,
  confidenceScore,
  sourceDocument,
  sourceExcerpt,
  sourcePage,
  question: _question,
  className,
}: SourceTransparencyProps) {
  const [expanded, setExpanded] = useState(false);

  const pct = confidenceScore != null
    ? `${Math.round((confidenceScore > 1 ? confidenceScore : confidenceScore * 100))}%`
    : confidence;

  const confColor =
    confidence === "HIGH"
      ? "text-green-700 bg-green-50 border-green-200"
      : confidence === "MEDIUM"
        ? "text-amber-700 bg-amber-50 border-amber-200"
        : "text-red-700 bg-red-50 border-red-200";

  // Simple reasoning summary (stub — not fake AI, just a summary of available data)
  const reasoningSummary = React.useMemo(() => {
    const parts: string[] = [];
    if (sourceDocument) {
      parts.push(`Answer sourced from "${sourceDocument}"${sourcePage ? ` (page ${sourcePage})` : ""}.`);
    }
    if (confidence === "HIGH") {
      parts.push("High semantic similarity between the question and source content.");
    } else if (confidence === "MEDIUM") {
      parts.push("Moderate match found; manual review recommended to verify accuracy.");
    } else {
      parts.push("Low confidence — source material may not directly address this question.");
    }
    if (sourceExcerpt) {
      parts.push("A relevant excerpt was identified and used for answer generation.");
    } else {
      parts.push("No direct excerpt was matched from the document library.");
    }
    return parts.join(" ");
  }, [sourceDocument, sourcePage, confidence, sourceExcerpt]);

  return (
    <div className={cn("mt-2 rounded-lg border bg-muted/30", className)}>
      <button
        type="button"
        onClick={() => setExpanded(!expanded)}
        className="flex w-full items-center gap-2 px-3 py-2 text-xs font-medium text-muted-foreground hover:text-foreground transition-colors"
      >
        {expanded ? (
          <ChevronDown className="h-3.5 w-3.5 shrink-0" />
        ) : (
          <ChevronRight className="h-3.5 w-3.5 shrink-0" />
        )}
        <span>Source Transparency</span>
        <Badge variant="outline" className={cn("ml-auto text-[10px] px-1.5 py-0", confColor)}>
          {pct}
        </Badge>
      </button>

      {expanded && (
        <div className="border-t px-3 py-2.5 space-y-2.5 text-xs">
          {/* Confidence */}
          <div className="flex items-center gap-2">
            <Percent className="h-3.5 w-3.5 text-muted-foreground shrink-0" />
            <span className="text-muted-foreground">Confidence:</span>
            <span className="font-semibold">{pct}</span>
            <Badge variant="outline" className={cn("text-[10px] px-1.5 py-0", confColor)}>
              {confidence}
            </Badge>
          </div>

          {/* Source Document */}
          <div className="flex items-start gap-2">
            <FileText className="h-3.5 w-3.5 text-muted-foreground shrink-0 mt-0.5" />
            <div>
              <span className="text-muted-foreground">Source: </span>
              {sourceDocument ? (
                <span className="font-medium text-foreground">
                  {sourceDocument}
                  {sourcePage ? ` (p. ${sourcePage})` : ""}
                </span>
              ) : (
                <span className="italic text-muted-foreground">No source document</span>
              )}
            </div>
          </div>

          {/* Citation Preview */}
          {sourceExcerpt && (
            <div className="flex items-start gap-2">
              <Quote className="h-3.5 w-3.5 text-muted-foreground shrink-0 mt-0.5" />
              <div className="rounded border bg-background px-2 py-1.5 text-xs text-foreground leading-relaxed italic">
                &ldquo;{sourceExcerpt.length > 200
                  ? sourceExcerpt.slice(0, 200) + "…"
                  : sourceExcerpt}&rdquo;
              </div>
            </div>
          )}

          {/* Why this answer? */}
          <div className="flex items-start gap-2">
            <Lightbulb className="h-3.5 w-3.5 text-amber-500 shrink-0 mt-0.5" />
            <div>
              <span className="font-medium text-muted-foreground">Why this answer? </span>
              <span className="text-foreground leading-relaxed">{reasoningSummary}</span>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}

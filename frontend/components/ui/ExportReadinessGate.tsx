/**
 * ExportReadinessGate — modal that checks export readiness before allowing download.
 * Shows warnings for flagged, low-confidence, or unreviewed answers.
 */
"use client";

import * as React from "react";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { AlertTriangle, Download, Flag, Eye, ShieldCheck, ArrowLeft } from "lucide-react";
import { cn } from "@/lib/utils";

export interface ExportWarning {
  type: "flagged" | "low_confidence" | "unreviewed";
  count: number;
  label: string;
}

interface ExportReadinessGateProps {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  warnings: ExportWarning[];
  totalQuestions: number;
  approvedCount: number;
  isAdmin?: boolean;
  onForceExport: () => void;
  onReturnToReview: () => void;
  exporting?: boolean;
}

const warningConfig = {
  flagged: { icon: Flag, color: "text-red-700 bg-red-50 border-red-200" },
  low_confidence: { icon: AlertTriangle, color: "text-amber-700 bg-amber-50 border-amber-200" },
  unreviewed: { icon: Eye, color: "text-blue-700 bg-blue-50 border-blue-200" },
};

export function ExportReadinessGate({
  open,
  onOpenChange,
  warnings,
  totalQuestions,
  approvedCount,
  isAdmin = false,
  onForceExport,
  onReturnToReview,
  exporting = false,
}: ExportReadinessGateProps) {
  const hasWarnings = warnings.length > 0 && warnings.some((w) => w.count > 0);
  const readyPct = totalQuestions > 0 ? Math.round((approvedCount / totalQuestions) * 100) : 0;

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="sm:max-w-lg">
        <DialogHeader>
          <DialogTitle className="flex items-center gap-2">
            {hasWarnings ? (
              <>
                <AlertTriangle className="h-5 w-5 text-amber-500" />
                Export Readiness Check
              </>
            ) : (
              <>
                <ShieldCheck className="h-5 w-5 text-green-600" />
                Ready to Export
              </>
            )}
          </DialogTitle>
          <DialogDescription>
            {hasWarnings
              ? "Some answers require attention before export."
              : "All answers have been reviewed and approved."}
          </DialogDescription>
        </DialogHeader>

        <div className="space-y-4 py-2">
          {/* Readiness Score */}
          <div className="flex items-center justify-between rounded-lg border bg-muted/30 p-4">
            <div>
              <p className="text-sm font-medium text-muted-foreground">Export Readiness</p>
              <p className="text-3xl font-bold">{readyPct}%</p>
            </div>
            <div className="text-right text-sm text-muted-foreground">
              <p><span className="font-semibold text-foreground">{approvedCount}</span> approved</p>
              <p><span className="font-semibold text-foreground">{totalQuestions}</span> total</p>
            </div>
          </div>

          {/* Warnings */}
          {hasWarnings && (
            <div className="space-y-2">
              <p className="text-sm font-medium text-foreground">Issues Found</p>
              {warnings
                .filter((w) => w.count > 0)
                .map((w) => {
                  const cfg = warningConfig[w.type];
                  const Icon = cfg.icon;
                  return (
                    <div
                      key={w.type}
                      className={cn(
                        "flex items-center gap-3 rounded-lg border p-3",
                        cfg.color
                      )}
                    >
                      <Icon className="h-4 w-4 shrink-0" />
                      <span className="text-sm flex-1">{w.label}</span>
                      <Badge variant="outline" className="font-mono">
                        {w.count}
                      </Badge>
                    </div>
                  );
                })}
            </div>
          )}
        </div>

        <DialogFooter className="flex-col sm:flex-row gap-2">
          <Button
            variant="outline"
            onClick={onReturnToReview}
            className="gap-2"
          >
            <ArrowLeft className="h-4 w-4" /> Return to Review
          </Button>

          {hasWarnings && isAdmin && (
            <Button
              variant="destructive"
              onClick={onForceExport}
              disabled={exporting}
              className="gap-2"
            >
              <Download className="h-4 w-4" />
              {exporting ? "Exporting…" : "Force Export (Admin)"}
            </Button>
          )}

          {!hasWarnings && (
            <Button
              onClick={onForceExport}
              disabled={exporting}
              className="gap-2"
            >
              <Download className="h-4 w-4" />
              {exporting ? "Exporting…" : "Export Now"}
            </Button>
          )}
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}

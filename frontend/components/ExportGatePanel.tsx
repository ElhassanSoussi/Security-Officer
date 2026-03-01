"use client";

/**
 * ExportGatePanel — Phase 14 Part 3
 * Displays unreviewed low-confidence count, requires checkbox before export,
 * shows confirmation modal with status breakdown.
 */

import { useState } from "react";
import { AlertTriangle, Download, Lock, CheckCircle2, Clock, XCircle } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Label } from "@/components/ui/label";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
  DialogTrigger,
} from "@/components/ui/dialog";
import { Badge } from "@/components/ui/badge";
import type { OrgRole } from "@/lib/rbac";
import { canExport } from "@/lib/rbac";

interface ExportGatePanelProps {
  /** Total audit entries for this run */
  total: number;
  /** Count of unreviewed low-confidence answers */
  unreviewedLow: number;
  /** Count of approved */
  approved: number;
  /** Count of rejected */
  rejected: number;
  /** Count of pending */
  pending: number;
  /** Current user's role — gates the export button */
  userRole?: OrgRole | null;
  /** Called when user confirms & clicks export */
  onExport: () => Promise<void> | void;
  /** Whether export is in progress */
  exporting?: boolean;
  /** Run output filename for display */
  outputFilename?: string;
}

export function ExportGatePanel({
  total,
  unreviewedLow,
  approved,
  rejected,
  pending,
  userRole,
  onExport,
  exporting = false,
  outputFilename,
}: ExportGatePanelProps) {
  const [confirmed, setConfirmed] = useState(false);
  const [open, setOpen] = useState(false);

  const allowed = canExport(userRole);
  const blockExport = unreviewedLow > 0 && !confirmed;

  const handleConfirmExport = async () => {
    setOpen(false);
    setConfirmed(false);
    await onExport();
  };

  return (
    <div className="rounded-lg border bg-card p-4 space-y-4">
      {/* Header */}
      <div className="flex items-center gap-2">
        <Lock className="h-4 w-4 text-slate-500" />
        <h3 className="text-sm font-semibold">Export Gate</h3>
      </div>

      {/* Status Breakdown */}
      <div className="grid grid-cols-3 gap-3 text-center">
        <div className="rounded-md border border-green-200 bg-green-50/60 p-2">
          <div className="flex items-center justify-center gap-1 text-green-700 mb-1">
            <CheckCircle2 className="h-3.5 w-3.5" />
            <span className="text-[10px] font-semibold uppercase tracking-wide">Approved</span>
          </div>
          <p className="text-xl font-bold text-green-700">{approved}</p>
        </div>
        <div className="rounded-md border border-amber-200 bg-amber-50/60 p-2">
          <div className="flex items-center justify-center gap-1 text-amber-700 mb-1">
            <Clock className="h-3.5 w-3.5" />
            <span className="text-[10px] font-semibold uppercase tracking-wide">Pending</span>
          </div>
          <p className="text-xl font-bold text-amber-700">{pending}</p>
        </div>
        <div className="rounded-md border border-red-200 bg-red-50/60 p-2">
          <div className="flex items-center justify-center gap-1 text-red-700 mb-1">
            <XCircle className="h-3.5 w-3.5" />
            <span className="text-[10px] font-semibold uppercase tracking-wide">Rejected</span>
          </div>
          <p className="text-xl font-bold text-red-700">{rejected}</p>
        </div>
      </div>

      {/* Warning */}
      {unreviewedLow > 0 && (
        <div className="flex items-start gap-2 rounded-md border border-amber-200 bg-amber-50/60 px-3 py-2 text-amber-800">
          <AlertTriangle className="h-4 w-4 mt-0.5 shrink-0" />
          <div>
            <p className="text-xs font-semibold">
              {unreviewedLow} low-confidence answer{unreviewedLow !== 1 ? "s" : ""} not yet reviewed
            </p>
            <p className="text-xs mt-0.5 text-amber-700">
              Review these before exporting to ensure submission accuracy.
            </p>
          </div>
        </div>
      )}

      {!allowed && (
        <p className="text-xs text-muted-foreground flex items-center gap-1.5">
          <Lock className="h-3.5 w-3.5" />
          You need <strong>Compliance Manager</strong> or higher to export.
        </p>
      )}

      {/* Export Modal Trigger */}
      <Dialog open={open} onOpenChange={setOpen}>
        <DialogTrigger asChild>
          <Button
            className="w-full gap-2"
            disabled={!allowed || exporting || total === 0}
            variant={unreviewedLow > 0 ? "outline" : "default"}
          >
            <Download className="h-4 w-4" />
            {exporting ? "Exporting…" : "Download Excel"}
            {unreviewedLow > 0 && (
              <Badge variant="outline" className="ml-1 text-[10px] border-amber-400 text-amber-700">
                {unreviewedLow} unreviewed
              </Badge>
            )}
          </Button>
        </DialogTrigger>
        <DialogContent className="sm:max-w-md">
          <DialogHeader>
            <DialogTitle className="flex items-center gap-2">
              <Lock className="h-4 w-4 text-slate-500" /> Export Summary
            </DialogTitle>
            <DialogDescription>
              Review the compliance audit results before downloading.
            </DialogDescription>
          </DialogHeader>

          <div className="space-y-4 py-2">
            {/* Stat grid */}
            <div className="grid grid-cols-2 gap-3">
              <div className="rounded-lg border bg-muted/50 p-3 text-center">
                <div className="text-2xl font-bold">{total}</div>
                <div className="text-xs text-muted-foreground font-medium uppercase tracking-wide">
                  Questions
                </div>
              </div>
              <div className="rounded-lg border border-amber-200 bg-amber-50/60 p-3 text-center text-amber-700">
                <div className="text-2xl font-bold">{unreviewedLow}</div>
                <div className="text-xs font-medium uppercase tracking-wide">Unreviewed Low</div>
              </div>
            </div>

            {/* Detail rows */}
            <div className="rounded-lg border bg-muted/30 p-4 text-sm space-y-2">
              <div className="flex justify-between">
                <span className="text-muted-foreground">Approved:</span>
                <span className="font-semibold text-green-700">{approved}</span>
              </div>
              <div className="flex justify-between">
                <span className="text-muted-foreground">Pending:</span>
                <span className="font-semibold text-amber-700">{pending}</span>
              </div>
              <div className="flex justify-between">
                <span className="text-muted-foreground">Rejected:</span>
                <span className="font-semibold text-red-700">{rejected}</span>
              </div>
              {outputFilename && (
                <div className="flex justify-between">
                  <span className="text-muted-foreground">Output file:</span>
                  <span className="font-mono text-xs">{outputFilename}</span>
                </div>
              )}
            </div>

            {/* Low-confidence warning */}
            {unreviewedLow > 0 && (
              <div className="rounded-lg border border-amber-200 bg-amber-50/60 px-3 py-2 flex items-start gap-2 text-amber-800">
                <AlertTriangle className="h-4 w-4 mt-0.5 shrink-0" />
                <p className="text-xs leading-snug">
                  {unreviewedLow} low-confidence answer{unreviewedLow !== 1 ? "s have" : " has"} not been reviewed.
                  Please verify them in the Audit tab before exporting.
                </p>
              </div>
            )}

            {/* Confirmation checkbox */}
            <div className="flex items-start gap-2.5 rounded-lg border bg-background p-3">
              <input
                type="checkbox"
                id="export-gate-confirm"
                title="Confirm you have reviewed the generated answers"
                aria-label="Confirm review before export"
                checked={confirmed}
                onChange={(e) => setConfirmed(e.target.checked)}
                className="mt-0.5 h-4 w-4 rounded border-input cursor-pointer"
              />
              <Label
                htmlFor="export-gate-confirm"
                className="text-xs leading-snug font-medium cursor-pointer"
              >
                I confirm I have reviewed the generated answers, including any low-confidence items.
              </Label>
            </div>
          </div>

          <DialogFooter>
            <Button variant="outline" size="sm" onClick={() => setOpen(false)}>
              Cancel
            </Button>
            <Button
              size="sm"
              className="gap-2"
              disabled={blockExport || exporting}
              onClick={handleConfirmExport}
            >
              <Download className="h-4 w-4" />
              Confirm &amp; Download
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </div>
  );
}

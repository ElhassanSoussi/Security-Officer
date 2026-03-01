"use client";

/**
 * BulkActions — Phase 14 Part 4
 * Bulk approve / reject selected or filtered audit rows.
 */

import { CheckCheck, XCircle, Loader2 } from "lucide-react";
import { Button } from "@/components/ui/button";

interface BulkActionsProps {
  pendingCount: number;
  lowCount: number;
  onApproveAllHigh: () => Promise<void> | void;
  onMarkLowManual: () => Promise<void> | void;
  onApproveAllPending: () => Promise<void> | void;
  onRejectAllPending: () => Promise<void> | void;
  loading?: boolean;
  /** Whether the user has permission to review. */
  canReview?: boolean;
}

export function BulkActions({
  pendingCount,
  lowCount,
  onApproveAllHigh,
  onMarkLowManual,
  onApproveAllPending,
  onRejectAllPending,
  loading = false,
  canReview = true,
}: BulkActionsProps) {
  if (!canReview) return null;
  if (pendingCount === 0 && lowCount === 0) return null;

  return (
    <div className="flex flex-wrap items-center gap-2 rounded-lg border bg-muted/30 px-3 py-2">
      <span className="text-xs font-medium text-muted-foreground shrink-0">Bulk actions:</span>

      {pendingCount > 0 && (
        <>
          <Button
            size="sm"
            variant="outline"
            className="h-7 text-xs text-green-700 border-green-200 hover:bg-green-50 gap-1"
            disabled={loading}
            onClick={onApproveAllPending}
          >
            {loading ? (
              <Loader2 className="h-3 w-3 animate-spin" />
            ) : (
              <CheckCheck className="h-3 w-3" />
            )}
            Approve all pending ({pendingCount})
          </Button>

          <Button
            size="sm"
            variant="outline"
            className="h-7 text-xs text-red-700 border-red-200 hover:bg-red-50 gap-1"
            disabled={loading}
            onClick={onRejectAllPending}
          >
            <XCircle className="h-3 w-3" />
            Reject all pending
          </Button>
        </>
      )}

      <Button
        size="sm"
        variant="outline"
        className="h-7 text-xs text-blue-700 border-blue-200 hover:bg-blue-50 gap-1"
        disabled={loading}
        onClick={onApproveAllHigh}
        title="Approve all HIGH confidence answers that are still pending"
      >
        <CheckCheck className="h-3 w-3" />
        Approve all HIGH
      </Button>

      {lowCount > 0 && (
        <Button
          size="sm"
          variant="outline"
          className="h-7 text-xs text-amber-700 border-amber-200 hover:bg-amber-50 gap-1"
          disabled={loading}
          onClick={onMarkLowManual}
          title="Mark all LOW confidence pending answers as needing manual review (reject)"
        >
          <XCircle className="h-3 w-3" />
          Flag all LOW ({lowCount})
        </Button>
      )}
    </div>
  );
}

"use client";

/**
 * RunSummaryCards component.
 * Summary stat cards for the Run Details page.
 */

import { CheckCircle2, Clock, BarChart3, AlertTriangle } from "lucide-react";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";

interface RunSummaryCardsProps {
  total: number;
  high: number;
  medium: number;
  low: number;
  reviewed: number;
  pending: number;
  loading?: boolean;
}

function SummaryCard({
  label,
  value,
  icon,
  colorClass,
  loading,
}: {
  label: string;
  value: number;
  icon: React.ReactNode;
  colorClass: string;
  loading?: boolean;
}) {
  return (
    <Card>
      <CardHeader className="pb-2">
        <CardTitle className={`text-xs font-medium flex items-center gap-1.5 ${colorClass}`}>
          {icon}
          {label}
        </CardTitle>
      </CardHeader>
      <CardContent>
        {loading ? (
          <div className="h-7 w-12 rounded bg-muted animate-pulse" />
        ) : (
          <p className="text-2xl font-bold text-foreground">{value}</p>
        )}
      </CardContent>
    </Card>
  );
}

export function RunSummaryCards({
  total,
  high,
  medium,
  low,
  reviewed,
  pending,
  loading = false,
}: RunSummaryCardsProps) {
  return (
    <div className="grid gap-3 grid-cols-2 sm:grid-cols-3 lg:grid-cols-6">
      <SummaryCard
        label="Total"
        value={total}
        icon={<BarChart3 className="h-3.5 w-3.5" />}
        colorClass="text-muted-foreground"
        loading={loading}
      />
      <SummaryCard
        label="High Conf"
        value={high}
        icon={<CheckCircle2 className="h-3.5 w-3.5" />}
        colorClass="text-green-600"
        loading={loading}
      />
      <SummaryCard
        label="Medium Conf"
        value={medium}
        icon={<BarChart3 className="h-3.5 w-3.5" />}
        colorClass="text-amber-600"
        loading={loading}
      />
      <SummaryCard
        label="Low Conf"
        value={low}
        icon={<AlertTriangle className="h-3.5 w-3.5" />}
        colorClass="text-red-600"
        loading={loading}
      />
      <SummaryCard
        label="Reviewed"
        value={reviewed}
        icon={<CheckCircle2 className="h-3.5 w-3.5" />}
        colorClass="text-blue-600"
        loading={loading}
      />
      <SummaryCard
        label="Pending"
        value={pending}
        icon={<Clock className="h-3.5 w-3.5" />}
        colorClass="text-orange-600"
        loading={loading}
      />
    </div>
  );
}

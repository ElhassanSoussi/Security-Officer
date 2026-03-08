/**
 * Intelligence Report — executive-ready compliance intelligence dashboard.
 * Aggregates project summary, risk breakdown, confidence heatmap,
 * audit completeness, review completion, and export history.
 */
"use client";

import { useEffect, useState, useCallback } from "react";
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import {
  ShieldCheck, FileText, BarChart3, CheckCircle2,
  Download, AlertTriangle, Clock, TrendingUp,
  FolderKanban, Loader2
} from "lucide-react";
import { ApiClient } from "@/lib/api";
import { createClient } from "@/utils/supabase/client";
import { useRouter } from "next/navigation";
import { getStoredOrgId, setStoredOrgId } from "@/lib/orgContext";
import PageHeader from "@/components/ui/PageHeader";
import { StatCard } from "@/components/ui/StatCard";
import { ConfidenceBar, MiniBarChart, ScoreGauge } from "@/components/ui/ConfidenceBar";
import { EmptyState } from "@/components/ui/EmptyState";
import { normalizeConfidenceScore } from "@/lib/confidence";
import { Badge } from "@/components/ui/badge";

interface ReportData {
  orgName: string;
  projectCount: number;
  documentCount: number;
  runCount: number;
  exportCount: number;
  totalQuestions: number;
  confidenceDist: { high: number; medium: number; low: number };
  reviewCompletion: number;
  auditCompleteness: number;
  riskLevel: "high" | "medium" | "low";
  exportHistory: { id: string; created_at: string; filename: string }[];
  runsByMonth: { label: string; value: number }[];
}

interface ComplianceEngineData {
  avg_score: number | null;
  overall_risk_level: string | null;
  active_issues: number;
  expiring_documents: number;
  issues_by_severity: { high: number; medium: number; low: number };
  top_risks: Array<{
    id: string;
    issue_type: string;
    severity: string;
    description: string;
    project_id: string;
    created_at: string;
  }>;
}

const SEVERITY_BADGE: Record<string, string> = {
  high: "bg-red-100 text-red-700 border-red-200",
  medium: "bg-amber-100 text-amber-700 border-amber-200",
  low: "bg-blue-50 text-blue-700 border-blue-200",
};

export default function IntelligenceReportPage() {
  const [data, setData] = useState<ReportData | null>(null);
  const [complianceEngine, setComplianceEngine] = useState<ComplianceEngineData | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const router = useRouter();

  const loadReport = useCallback(async () => {
    try {
      setError("");
      const supabase = createClient();
      const { data: { session } } = await supabase.auth.getSession();
      const token = session?.access_token;
      if (!token) { router.push("/login"); return; }

      const orgs = await ApiClient.getMyOrgs(token);
      if (!orgs?.length) { router.push("/onboarding"); return; }

      const stored = getStoredOrgId() || "";
      const org = orgs.find((o: any) => o.id === stored) || orgs[0];
      setStoredOrgId(org.id);

      // Fetch data in parallel
      const [_projects, runs, stats, auditLog, exportEvents, complianceData] = await Promise.all([
        ApiClient.getProjects(org.id, token).catch(() => []),
        ApiClient.getRuns(org.id, undefined, 200, token).catch(() => []),
        ApiClient.getStats(org.id, token).catch(() => ({ active_projects: 0, documents_ingested: 0, runs_completed: 0 })),
        ApiClient.getAuditLog(org.id, {}, token).catch(() => []),
        ApiClient.getExportEvents(org.id, {}, token).catch(() => []),
        ApiClient.getComplianceOverview(org.id, token).catch(() => null),
      ]);

      // Compute confidence distribution from audit log
      const audits = Array.isArray(auditLog) ? auditLog : [];
      let high = 0, medium = 0, low = 0, reviewed = 0;
      for (const a of audits) {
        const ratio = normalizeConfidenceScore(a.confidence_score);
        if (ratio !== null) {
          if (ratio >= 0.8) high++;
          else if (ratio >= 0.5) medium++;
          else low++;
        }
        if (a.review_status === "approved" || a.review_status === "rejected") reviewed++;
      }

      const totalQ = audits.length;
      const reviewPct = totalQ > 0 ? Math.round((reviewed / totalQ) * 100) : 100;
      const avgConf = totalQ > 0
        ? (high * 0.9 + medium * 0.65 + low * 0.3) / totalQ
        : 0;
      const auditPct = totalQ > 0 ? Math.min(100, Math.round((reviewed / totalQ) * 100)) : 100;

      const riskLevel: "high" | "medium" | "low" =
        avgConf < 0.5 || low > totalQ * 0.3 ? "high"
        : avgConf < 0.7 || low > totalQ * 0.15 ? "medium"
        : "low";

      // Runs by month (last 6 months)
      const allRuns = Array.isArray(runs) ? runs : [];
      const now = new Date();
      const months: { label: string; value: number }[] = [];
      for (let i = 5; i >= 0; i--) {
        const d = new Date(now.getFullYear(), now.getMonth() - i, 1);
        const label = d.toLocaleString("default", { month: "short" });
        const count = allRuns.filter((r: any) => {
          const rd = new Date(r.created_at);
          return rd.getMonth() === d.getMonth() && rd.getFullYear() === d.getFullYear();
        }).length;
        months.push({ label, value: count });
      }

      // Export history (last 10)
      const exports = Array.isArray(exportEvents) ? exportEvents : [];
      const exportHist = exports.slice(0, 10).map((e: any) => ({
        id: e.id || e.run_id || "",
        created_at: e.created_at || e.exported_at || "",
        filename: e.filename || e.output_filename || "export.xlsx",
      }));

      setData({
        orgName: org.name || "Organization",
        projectCount: stats.active_projects,
        documentCount: stats.documents_ingested,
        runCount: stats.runs_completed,
        exportCount: exports.length,
        totalQuestions: totalQ,
        confidenceDist: { high, medium, low },
        reviewCompletion: reviewPct,
        auditCompleteness: auditPct,
        riskLevel,
        exportHistory: exportHist,
        runsByMonth: months,
      });

      if (complianceData) {
        setComplianceEngine(complianceData);
      }
    } catch (e: any) {
      console.error("Intelligence report error:", e);
      if (String(e?.message || "").toLowerCase().includes("unauthorized")) {
        router.push("/login");
        return;
      }
      setError("Failed to load intelligence report.");
    } finally {
      setLoading(false);
    }
  }, [router]);

  useEffect(() => { loadReport(); }, [loadReport]);

  if (loading) {
    return (
      <div className="flex h-screen items-center justify-center">
        <Loader2 className="h-8 w-8 animate-spin text-muted-foreground" />
      </div>
    );
  }

  if (error || !data) {
    return (
      <div className="space-y-6">
        <PageHeader title="Intelligence Report" subtitle="Compliance analytics and risk overview." />
        <EmptyState
          icon={<AlertTriangle className="h-10 w-10" />}
          title="Unable to load report"
          description={error || "Try refreshing the page."}
          action={<Button onClick={loadReport}>Retry</Button>}
        />
      </div>
    );
  }

  const readinessScore = Math.round(
    (data.reviewCompletion * 0.4) +
    (data.auditCompleteness * 0.3) +
    ((data.riskLevel === "low" ? 100 : data.riskLevel === "medium" ? 60 : 20) * 0.3)
  );

  return (
    <div className="space-y-6">
      <PageHeader
        title="Intelligence Report"
        subtitle={`Compliance analytics for ${data.orgName} — generated ${new Date().toLocaleDateString()}`}
        actions={
          <Button variant="outline" onClick={() => window.print()} className="gap-2">
            <Download className="h-4 w-4" /> Export PDF
          </Button>
        }
      />

      {/* Executive Summary Row */}
      <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
        <StatCard
          label="Projects"
          value={data.projectCount}
          icon={<FolderKanban className="h-5 w-5" />}
          iconClassName="text-blue-600 bg-blue-100"
        />
        <StatCard
          label="Documents"
          value={data.documentCount}
          icon={<FileText className="h-5 w-5" />}
          iconClassName="text-purple-600 bg-purple-100"
        />
        <StatCard
          label="Runs Completed"
          value={data.runCount}
          icon={<BarChart3 className="h-5 w-5" />}
          iconClassName="text-green-600 bg-green-100"
        />
        <StatCard
          label="Exports"
          value={data.exportCount}
          icon={<Download className="h-5 w-5" />}
          iconClassName="text-amber-600 bg-amber-100"
        />
      </div>

      {/* Readiness + Risk Row */}
      <div className="grid gap-6 lg:grid-cols-3">
        {/* Readiness Score */}
        <Card>
          <CardHeader className="pb-3">
            <CardTitle className="flex items-center gap-2 text-sm">
              <ShieldCheck className="h-4 w-4 text-blue-600" /> Export Readiness
            </CardTitle>
          </CardHeader>
          <CardContent className="flex items-center justify-center py-4">
            <ScoreGauge score={readinessScore} label="Readiness Score" size="md" />
          </CardContent>
        </Card>

        {/* Risk Breakdown */}
        <Card>
          <CardHeader className="pb-3">
            <CardTitle className="flex items-center gap-2 text-sm">
              <AlertTriangle className="h-4 w-4 text-amber-500" /> Confidence Distribution
            </CardTitle>
            <CardDescription>
              {data.totalQuestions} total questions analyzed
            </CardDescription>
          </CardHeader>
          <CardContent>
            <ConfidenceBar
              segments={[
                { label: "High", value: data.confidenceDist.high, color: "bg-green-500" },
                { label: "Medium", value: data.confidenceDist.medium, color: "bg-amber-400" },
                { label: "Low", value: data.confidenceDist.low, color: "bg-red-400" },
              ]}
            />
          </CardContent>
        </Card>

        {/* Audit Completeness */}
        <Card>
          <CardHeader className="pb-3">
            <CardTitle className="flex items-center gap-2 text-sm">
              <CheckCircle2 className="h-4 w-4 text-green-600" /> Review Progress
            </CardTitle>
          </CardHeader>
          <CardContent className="space-y-3">
            <div className="flex items-baseline justify-between">
              <span className="text-3xl font-bold">{data.reviewCompletion}%</span>
              <span className="text-sm text-muted-foreground">reviewed</span>
            </div>
            <div className="h-2.5 rounded-full bg-muted overflow-hidden">
              <div
                className="h-full rounded-full bg-green-500 transition-all duration-500"
                style={{ width: `${data.reviewCompletion}%` }}
              />
            </div>
            <p className="text-xs text-muted-foreground">
              {data.auditCompleteness}% audit completeness
            </p>
          </CardContent>
        </Card>
      </div>

      {/* Activity Trends */}
      <div className="grid gap-6 lg:grid-cols-2">
        <Card>
          <CardHeader className="pb-3">
            <CardTitle className="flex items-center gap-2 text-sm">
              <TrendingUp className="h-4 w-4 text-blue-600" /> Runs per Month
            </CardTitle>
            <CardDescription>Last 6 months of questionnaire activity</CardDescription>
          </CardHeader>
          <CardContent>
            {data.runsByMonth.every((m) => m.value === 0) ? (
              <p className="text-sm text-muted-foreground text-center py-4">No run activity yet.</p>
            ) : (
              <MiniBarChart data={data.runsByMonth} barColor="bg-primary" maxHeight={80} />
            )}
          </CardContent>
        </Card>

        {/* Export History */}
        <Card>
          <CardHeader className="pb-3">
            <CardTitle className="flex items-center gap-2 text-sm">
              <Clock className="h-4 w-4 text-muted-foreground" /> Export History
            </CardTitle>
            <CardDescription>Recent compliance exports</CardDescription>
          </CardHeader>
          <CardContent>
            {data.exportHistory.length === 0 ? (
              <p className="text-sm text-muted-foreground text-center py-4">No exports yet.</p>
            ) : (
              <div className="space-y-2 max-h-48 overflow-y-auto">
                {data.exportHistory.map((exp, i) => (
                  <div key={exp.id || i} className="flex items-center justify-between rounded-md border px-3 py-2 text-sm">
                    <div className="flex items-center gap-2 min-w-0">
                      <Download className="h-3.5 w-3.5 text-muted-foreground shrink-0" />
                      <span className="truncate font-medium">{exp.filename}</span>
                    </div>
                    <span className="text-xs text-muted-foreground shrink-0 ml-2">
                      {exp.created_at ? new Date(exp.created_at).toLocaleDateString() : "—"}
                    </span>
                  </div>
                ))}
              </div>
            )}
          </CardContent>
        </Card>
      </div>

      {/* Compliance Engine — Score, Issues by Severity, Top Risks */}
      {complianceEngine && (complianceEngine.avg_score !== null || complianceEngine.active_issues > 0) && (
        <div className="grid gap-6 lg:grid-cols-2">
          {/* Compliance Score */}
          <Card>
            <CardHeader className="pb-3">
              <CardTitle className="flex items-center gap-2 text-sm">
                <ShieldCheck className="h-4 w-4 text-blue-600" /> Compliance Score
              </CardTitle>
              <CardDescription>Average across all projects based on document analysis</CardDescription>
            </CardHeader>
            <CardContent className="space-y-4">
              {complianceEngine.avg_score !== null ? (
                <div className="flex items-center gap-4">
                  <ScoreGauge score={complianceEngine.avg_score} label="Avg Score" size="md" />
                  <div className="space-y-2 flex-1">
                    <div className="flex items-center justify-between text-sm">
                      <span className="text-muted-foreground">Open Issues</span>
                      <span className="font-semibold">{complianceEngine.active_issues}</span>
                    </div>
                    <div className="flex items-center justify-between text-sm">
                      <span className="text-muted-foreground">Expiring (60d)</span>
                      <span className={`font-semibold ${complianceEngine.expiring_documents > 0 ? "text-amber-700" : ""}`}>
                        {complianceEngine.expiring_documents}
                      </span>
                    </div>
                    <div className="flex items-center justify-between text-sm">
                      <span className="text-muted-foreground">Overall Risk</span>
                      <span className={`font-semibold capitalize ${
                        complianceEngine.overall_risk_level === "high" ? "text-red-700"
                        : complianceEngine.overall_risk_level === "medium" ? "text-amber-700"
                        : "text-green-700"
                      }`}>
                        {complianceEngine.overall_risk_level || "—"}
                      </span>
                    </div>
                  </div>
                </div>
              ) : (
                <p className="text-sm text-muted-foreground py-2">No compliance scans run yet.</p>
              )}
            </CardContent>
          </Card>

          {/* Issues by Severity */}
          <Card>
            <CardHeader className="pb-3">
              <CardTitle className="flex items-center gap-2 text-sm">
                <AlertTriangle className="h-4 w-4 text-amber-500" /> Issues by Severity
              </CardTitle>
              <CardDescription>Open compliance issues across all projects</CardDescription>
            </CardHeader>
            <CardContent className="space-y-3">
              {complianceEngine.active_issues === 0 ? (
                <div className="flex items-center gap-2 text-sm text-green-700">
                  <CheckCircle2 className="h-4 w-4" /> No open compliance issues.
                </div>
              ) : (
                <>
                  {(["high", "medium", "low"] as const).map((sev) => {
                    const count = complianceEngine.issues_by_severity[sev] ?? 0;
                    const pct = complianceEngine.active_issues > 0
                      ? Math.round((count / complianceEngine.active_issues) * 100)
                      : 0;
                    return (
                      <div key={sev} className="space-y-1">
                        <div className="flex items-center justify-between text-xs">
                          <span className="capitalize font-medium">{sev}</span>
                          <span className="text-muted-foreground">{count} issue{count !== 1 ? "s" : ""}</span>
                        </div>
                        <div className="h-2 rounded-full bg-muted overflow-hidden">
                          <div
                            className={`h-full rounded-full transition-all ${
                              sev === "high" ? "bg-red-500" : sev === "medium" ? "bg-amber-400" : "bg-blue-400"
                            }`}
                            style={{ width: `${pct}%` }}
                          />
                        </div>
                      </div>
                    );
                  })}
                </>
              )}
            </CardContent>
          </Card>
        </div>
      )}

      {/* Top Compliance Risks */}
      {complianceEngine && complianceEngine.top_risks.length > 0 && (
        <Card>
          <CardHeader className="pb-3">
            <CardTitle className="flex items-center gap-2 text-sm">
              <AlertTriangle className="h-4 w-4 text-red-500" /> Top Compliance Risks
            </CardTitle>
            <CardDescription>Highest-priority open issues requiring attention</CardDescription>
          </CardHeader>
          <CardContent>
            <div className="space-y-2">
              {complianceEngine.top_risks.map((risk, i) => (
                <div
                  key={risk.id || i}
                  className="flex items-start gap-3 rounded-md border px-3 py-2.5 text-sm"
                >
                  <AlertTriangle className="h-3.5 w-3.5 mt-0.5 shrink-0 text-amber-500" />
                  <p className="flex-1 text-xs text-muted-foreground leading-relaxed">{risk.description}</p>
                  <Badge
                    variant="outline"
                    className={`text-[10px] px-1.5 py-0 shrink-0 ${SEVERITY_BADGE[risk.severity] || ""}`}
                  >
                    {risk.severity}
                  </Badge>
                </div>
              ))}
            </div>
          </CardContent>
        </Card>
      )}

      {/* Risk Summary Banner */}
      <Card className={
        data.riskLevel === "high"
          ? "border-red-200 bg-red-50/30"
          : data.riskLevel === "medium"
            ? "border-amber-200 bg-amber-50/30"
            : "border-green-200 bg-green-50/30"
      }>
        <CardContent className="flex items-start gap-4 py-5">
          <div className={`rounded-lg p-2.5 shrink-0 ${
            data.riskLevel === "high" ? "bg-red-100" : data.riskLevel === "medium" ? "bg-amber-100" : "bg-green-100"
          }`}>
            <ShieldCheck className={`h-5 w-5 ${
              data.riskLevel === "high" ? "text-red-700" : data.riskLevel === "medium" ? "text-amber-700" : "text-green-700"
            }`} />
          </div>
          <div className="space-y-1">
            <h3 className="text-sm font-semibold">
              {data.riskLevel === "high"
                ? "High Risk — Immediate Review Required"
                : data.riskLevel === "medium"
                  ? "Moderate Risk — Some Answers Need Attention"
                  : "Low Risk — Compliance Posture is Strong"}
            </h3>
            <p className="text-sm text-muted-foreground leading-relaxed">
              {data.riskLevel === "high"
                ? `${data.confidenceDist.low} answers have low confidence. Review all flagged items before submission.`
                : data.riskLevel === "medium"
                  ? `${data.confidenceDist.low} low-confidence answers detected. Consider reviewing before final export.`
                  : "All answers meet confidence thresholds. The compliance package is ready for submission."}
            </p>
          </div>
        </CardContent>
      </Card>

      {/* Footer */}
      <div className="text-center text-xs text-muted-foreground pb-4 print:pb-0">
        <p>Generated by NYC Compliance Architect · {new Date().toISOString().slice(0, 10)} · Confidential</p>
      </div>
    </div>
  );
}

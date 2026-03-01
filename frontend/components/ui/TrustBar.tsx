/**
 * TrustBar — horizontal row of enterprise trust signal badges.
 */
import { ShieldCheck, Fingerprint, FileSearch, Lock } from "lucide-react";

const SIGNALS = [
  { label: "SOC 2 Aligned", icon: ShieldCheck, color: "text-green-600" },
  { label: "Full Audit Trail", icon: Fingerprint, color: "text-purple-600" },
  { label: "Source Citations", icon: FileSearch, color: "text-blue-600" },
  { label: "RBAC Enforced", icon: Lock, color: "text-slate-600" },
];

export function TrustBar() {
  return (
    <div className="flex flex-wrap items-center gap-x-5 gap-y-2 text-xs text-muted-foreground">
      {SIGNALS.map((s) => (
        <span key={s.label} className="inline-flex items-center gap-1.5">
          <s.icon className={`h-3.5 w-3.5 ${s.color}`} />
          {s.label}
        </span>
      ))}
    </div>
  );
}

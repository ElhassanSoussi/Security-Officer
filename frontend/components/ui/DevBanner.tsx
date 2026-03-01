/**
 * Phase 12 Part 1: Development mode ribbon banner.
 *
 * Renders a thin, fixed banner at the top of the viewport when the app
 * is running in development mode. Hidden in production.
 */
"use client";

import { config } from "@/lib/config";

export function DevBanner() {
  if (config.isProd) return null;

  return (
    <div className="fixed top-0 inset-x-0 z-[9999] flex items-center justify-center bg-amber-500 text-amber-950 text-xs font-semibold py-0.5 select-none pointer-events-none print:hidden">
      ⚠ DEVELOPMENT MODE — {config.environment.toUpperCase()} — v{config.version}
    </div>
  );
}

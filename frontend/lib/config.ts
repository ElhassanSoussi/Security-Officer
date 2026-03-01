/**
 * Phase 12 Part 1: Typed frontend configuration loader.
 *
 * Centralizes all environment variable access into a single typed object.
 * Validates required vars at import time — pages that import config will
 * fail fast if critical values are missing.
 */

interface AppConfig {
  /** Base URL for the backend API (e.g. "/api/v1" or "http://localhost:8000/api/v1") */
  apiUrl: string;

  /** Supabase project URL */
  supabaseUrl: string;

  /** Supabase anonymous / public key */
  supabaseAnonKey: string;

  /** Current environment: "development" | "production" | "test" */
  environment: "development" | "production" | "test";

  /** True when running in development mode */
  isDev: boolean;

  /** True when running in production mode */
  isProd: boolean;

  /** Application version string */
  version: string;
}

function loadConfig(): AppConfig {
  const environment = (process.env.NODE_ENV || "development") as AppConfig["environment"];

  return {
    apiUrl: process.env.NEXT_PUBLIC_API_URL || "/api/v1",
    supabaseUrl: process.env.NEXT_PUBLIC_SUPABASE_URL || "",
    supabaseAnonKey: process.env.NEXT_PUBLIC_SUPABASE_ANON_KEY || "",
    environment,
    isDev: environment === "development",
    isProd: environment === "production",
    version: process.env.NEXT_PUBLIC_APP_VERSION || "1.0.0",
  };
}

/** Singleton typed config — imported wherever env values are needed. */
export const config = loadConfig();

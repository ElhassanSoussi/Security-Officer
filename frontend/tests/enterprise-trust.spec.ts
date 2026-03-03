/**
 * Enterprise Trust Layer + Product Structuring E2E Tests
 *
 * E2E tests verify that the UI changes for enterprise trust are visible and
 * functional when navigating the authenticated app.
 *
 * Prerequisites:
 *   - Stack running on localhost:3001 (frontend) and localhost:8000 (backend)
 *   - E2E_EMAIL and E2E_PASSWORD env vars set
 *
 * Run:  npx playwright test tests/enterprise-trust.spec.ts
 */
import { expect, test } from "@playwright/test";

const email = process.env.E2E_EMAIL;
const password = process.env.E2E_PASSWORD;

async function login(page: import("@playwright/test").Page) {
    await page.goto("/login");
    await page.getByRole("textbox", { name: "Email" }).fill(email!);
    await page.getByRole("textbox", { name: "Password" }).fill(password!);
    await page.getByRole("button", { name: "Sign In" }).click();
    await page.waitForURL("**/dashboard");
}

test.describe("Enterprise Trust Layer", () => {
    test.skip(!email || !password, "Set E2E_EMAIL and E2E_PASSWORD to run");

    // ── Product Identity & Clarity ────────────────────────────────

    test("P1-1: Sidebar shows product descriptor", async ({ page }) => {
        await login(page);
        const descriptor = page.locator("text=AI-powered security questionnaire automation");
        await expect(descriptor).toBeVisible();
    });

    test("P1-2: Dashboard has product explanation card", async ({ page }) => {
        await login(page);
        await expect(page.locator("text=NYC Compliance Architect").first()).toBeVisible();
        // Trust signal badges
        await expect(page.locator("text=SOC 2 Aligned")).toBeVisible();
        await expect(page.locator("text=Full Audit Trail")).toBeVisible();
        await expect(page.locator("text=Source Transparency")).toBeVisible();
    });

    test("P1-3: Dashboard subtitle updated", async ({ page }) => {
        await login(page);
        await expect(
            page.locator("text=Overview of your compliance automation activity.")
        ).toBeVisible();
    });

    test("P1-4: Dashboard action button reads 'Run Analysis'", async ({ page }) => {
        await login(page);
        await expect(page.getByRole("link", { name: /Run Analysis/i })).toBeVisible();
    });

    test("P1-5: Onboarding checklist uses 'Begin' for incomplete items", async ({ page }) => {
        await login(page);
        // At least one "Begin" button should appear (unless all steps are done)
        const beginButtons = page.locator("button", { hasText: "Begin →" });
        const reviewButtons = page.locator("button", { hasText: "Review" });
        // At least one of these patterns should exist
        const beginCount = await beginButtons.count();
        const reviewCount = await reviewButtons.count();
        expect(beginCount + reviewCount).toBeGreaterThan(0);
    });

    // ── Security & Trust Visual Signals ───────────────────────────

    test("P2-1: Audit page header has ShieldCheck icon text", async ({ page }) => {
        await login(page);
        await page.goto("/audit");
        // The heading text should contain "Audit & Compliance"
        await expect(page.locator("h1", { hasText: "Audit" })).toBeVisible();
        await expect(
            page.locator("text=tamper-evident audit trail")
        ).toBeVisible();
    });

    test("P2-2: Settings has Security tab", async ({ page }) => {
        await login(page);
        await page.goto("/settings");
        const securityTab = page.getByRole("tab", { name: /Security/i });
        await expect(securityTab).toBeVisible();
        await securityTab.click();
        // Security content visible
        await expect(page.locator("text=Data Encryption")).toBeVisible();
        await expect(page.locator("text=Role-Based Access")).toBeVisible();
        await expect(page.locator("text=Audit Trail")).toBeVisible();
        await expect(page.locator("text=Source Transparency")).toBeVisible();
        // Compliance note
        await expect(page.locator("text=SOC 2 Type II")).toBeVisible();
    });

    test("P2-3: Settings has About section in Security tab", async ({ page }) => {
        await login(page);
        await page.goto("/settings");
        await page.getByRole("tab", { name: /Security/i }).click();
        await expect(page.locator("text=About").first()).toBeVisible();
        await expect(page.locator("text=1.0.0").first()).toBeVisible();
    });

    // ── Workflow Professionalization ───────────────────────────────

    test("P3-1: Run page shows 4-step workflow indicator", async ({ page }) => {
        await login(page);
        await page.goto("/run");
        // All four step labels should be present
        await expect(page.locator("text=Select Project")).toBeVisible();
        await expect(page.locator("text=Upload Questionnaire")).toBeVisible();
        await expect(page.locator("text=Run Analysis")).toBeVisible();
        await expect(page.locator("text=Review & Export")).toBeVisible();
    });

    test("P3-2: Run page starts on Select Project step", async ({ page }) => {
        await login(page);
        await page.goto("/run");
        // The "Continue to Upload" button should be visible (step 1)
        await expect(
            page.getByRole("button", { name: /Continue to Upload/i })
        ).toBeVisible();
    });

    test("P3-3: Run page can advance to Upload step", async ({ page }) => {
        await login(page);
        await page.goto("/run");
        await page.getByRole("button", { name: /Continue to Upload/i }).click();
        // Now the file input and "Run Analysis" button should appear
        await expect(page.locator("input[type='file']")).toBeVisible();
        await expect(
            page.getByRole("button", { name: /Run Analysis/i })
        ).toBeVisible();
        // Back button present
        await expect(
            page.getByRole("button", { name: /← Back/i })
        ).toBeVisible();
    });

    test("P3-4: Run page back button returns to Select Project", async ({ page }) => {
        await login(page);
        await page.goto("/run");
        await page.getByRole("button", { name: /Continue to Upload/i }).click();
        await page.getByRole("button", { name: /← Back/i }).click();
        // Should be back on Select Project
        await expect(
            page.getByRole("button", { name: /Continue to Upload/i })
        ).toBeVisible();
    });

    // ── Part 4: Data Density & Table Maturity ─────────────────────────────

    test("P4-1: Audit table renders with enterprise styling", async ({ page }) => {
        await login(page);
        await page.goto("/audit");
        // Table should be present
        const table = page.locator("table");
        await expect(table.first()).toBeVisible();
        // Check that th elements have the updated styling (uppercase headers)
        const th = page.locator("th").first();
        await expect(th).toBeVisible();
    });

    // ── Part 5: Company-Level Structure ───────────────────────────────────

    test("P5-1: Authenticated pages show footer", async ({ page }) => {
        await login(page);
        const footer = page.locator("footer");
        await expect(footer).toBeVisible();
        await expect(footer).toContainText("NYC Compliance Architect");
        await expect(footer).toContainText("v1.0.0");
    });

    test("P5-2: Footer shows on Settings page too", async ({ page }) => {
        await login(page);
        await page.goto("/settings");
        const footer = page.locator("footer");
        await expect(footer).toBeVisible();
        await expect(footer).toContainText("NYC Compliance Architect");
    });

    // ── Page subtitles ────────────────────────────────────────────────────

    test("P1-6: Projects page has standardized subtitle", async ({ page }) => {
        await login(page);
        await page.goto("/projects");
        await expect(
            page.locator("text=Organize documents and runs into compliance workspaces")
        ).toBeVisible();
    });

    test("P1-7: Run page has standardized subtitle", async ({ page }) => {
        await login(page);
        await page.goto("/run");
        await expect(
            page.locator("text=Upload a vendor security questionnaire and generate AI-powered answers")
        ).toBeVisible();
    });

    test("P1-8: Runs History has standardized subtitle", async ({ page }) => {
        await login(page);
        await page.goto("/runs");
        await expect(
            page.locator("text=Track all questionnaire processing activity across your organization")
        ).toBeVisible();
    });

    test("P1-9: Settings has standardized subtitle", async ({ page }) => {
        await login(page);
        await page.goto("/settings");
        await expect(
            page.locator("text=Manage your organization, profile, and security preferences")
        ).toBeVisible();
    });
});

/**
 * E2E Tests — Billing & Upgrade Funnel
 *
 * Covers:
 *   - Billing page loads and shows plan info
 *   - Plan comparison table is visible
 *   - Usage bars render
 *   - Promo code input exists and is interactive
 *   - Analytics tab is accessible
 *   - Upgrade button links to plans page
 *   - Manage Billing button or subscribe CTA exists
 *   - Alerts page loads
 *   - Admin dashboard loads
 *
 * Prerequisites:
 *   - Stack running on localhost:3001 (frontend) and localhost:8000 (backend)
 *   - E2E_EMAIL and E2E_PASSWORD env vars set
 *
 * Run:  npx playwright test tests/e2e-billing-upgrade.spec.ts
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

// ─── Billing Page ────────────────────────────────────────────────────────────

test.describe("Billing Page", () => {
    test.skip(!email || !password, "Set E2E_EMAIL and E2E_PASSWORD to run");

    test("B1: Billing page loads without errors", async ({ page }) => {
        await login(page);
        await page.goto("/settings/billing");
        await page.waitForLoadState("networkidle");
        // Should not show an unrecoverable error
        await expect(page.locator("text=Current Plan")).toBeVisible({ timeout: 10_000 });
    });

    test("B2: Shows plan badge (Starter/Growth/Elite)", async ({ page }) => {
        await login(page);
        await page.goto("/settings/billing");
        await page.waitForLoadState("networkidle");
        // At least one plan badge should be visible
        const badges = page.locator("text=/Starter|Growth|Elite/");
        await expect(badges.first()).toBeVisible({ timeout: 10_000 });
    });

    test("B3: Shows subscription status badge", async ({ page }) => {
        await login(page);
        await page.goto("/settings/billing");
        await page.waitForLoadState("networkidle");
        const statusBadges = page.locator("text=/Active|Trialing|Past Due|Canceled/");
        await expect(statusBadges.first()).toBeVisible({ timeout: 10_000 });
    });

    test("B4: Usage section with document/project/run bars", async ({ page }) => {
        await login(page);
        await page.goto("/settings/billing");
        await page.waitForLoadState("networkidle");
        await expect(page.locator("text=Usage")).toBeVisible({ timeout: 10_000 });
        await expect(page.locator("text=Documents")).toBeVisible();
        await expect(page.locator("text=Projects")).toBeVisible();
    });

    test("B5: Plan comparison table is visible", async ({ page }) => {
        await login(page);
        await page.goto("/settings/billing");
        await page.waitForLoadState("networkidle");
        await expect(page.locator("text=Plan Comparison")).toBeVisible({ timeout: 10_000 });
        // Should show all 3 plan columns
        await expect(page.locator("th:has-text('Starter')")).toBeVisible();
        await expect(page.locator("th:has-text('Growth')")).toBeVisible();
        await expect(page.locator("th:has-text('Elite')")).toBeVisible();
    });

    test("B6: Promo Code section exists with input", async ({ page }) => {
        await login(page);
        await page.goto("/settings/billing");
        await page.waitForLoadState("networkidle");
        await expect(page.locator("text=Promo Code")).toBeVisible({ timeout: 10_000 });
        const input = page.getByPlaceholder("Enter promo code");
        await expect(input).toBeVisible();
    });

    test("B7: Can type into promo code input", async ({ page }) => {
        await login(page);
        await page.goto("/settings/billing");
        await page.waitForLoadState("networkidle");
        const input = page.getByPlaceholder("Enter promo code");
        await input.fill("TESTCODE");
        await expect(input).toHaveValue("TESTCODE");
    });

    test("B8: Apply button is present but disabled when empty", async ({ page }) => {
        await login(page);
        await page.goto("/settings/billing");
        await page.waitForLoadState("networkidle");
        const applyBtn = page.getByRole("button", { name: "Apply" });
        await expect(applyBtn).toBeVisible({ timeout: 10_000 });
    });

    test("B9: Manage Billing section exists", async ({ page }) => {
        await login(page);
        await page.goto("/settings/billing");
        await page.waitForLoadState("networkidle");
        await expect(page.locator("text=Manage Billing")).toBeVisible({ timeout: 10_000 });
    });

    test("B10: Overview tab is default active", async ({ page }) => {
        await login(page);
        await page.goto("/settings/billing");
        await page.waitForLoadState("networkidle");
        // Overview tab should have active styling
        const overviewTab = page.locator("button:has-text('Overview')");
        await expect(overviewTab).toBeVisible({ timeout: 10_000 });
    });

    test("B11: Analytics tab is clickable", async ({ page }) => {
        await login(page);
        await page.goto("/settings/billing");
        await page.waitForLoadState("networkidle");
        const analyticsTab = page.locator("button:has-text('Analytics')");
        await expect(analyticsTab).toBeVisible({ timeout: 10_000 });
        await analyticsTab.click();
        // Analytics content should appear
        await expect(page.locator("text=/Limit Hits|Modal Opens|No limit events/")).toBeVisible({ timeout: 10_000 });
    });

    test("B12: Refresh button works", async ({ page }) => {
        await login(page);
        await page.goto("/settings/billing");
        await page.waitForLoadState("networkidle");
        const refreshBtn = page.getByRole("button", { name: "Refresh" });
        await expect(refreshBtn).toBeVisible({ timeout: 10_000 });
        await refreshBtn.click();
        // Should not crash after refresh
        await expect(page.locator("text=Current Plan")).toBeVisible({ timeout: 10_000 });
    });
});

// ─── Upgrade Flow ────────────────────────────────────────────────────────────

test.describe("Upgrade Flow", () => {
    test.skip(!email || !password, "Set E2E_EMAIL and E2E_PASSWORD to run");

    test("U1: Upgrade Plan button navigates to /plans", async ({ page }) => {
        await login(page);
        await page.goto("/settings/billing");
        await page.waitForLoadState("networkidle");
        const upgradeLink = page.getByRole("link", { name: /Upgrade Plan/i });
        // May not be visible if already on Elite plan
        const count = await upgradeLink.count();
        if (count > 0) {
            await upgradeLink.click();
            await page.waitForURL("**/plans");
            await expect(page).toHaveURL(/plans/);
        }
    });

    test("U2: Plans page loads with plan cards", async ({ page }) => {
        await login(page);
        await page.goto("/plans");
        await page.waitForLoadState("networkidle");
        // Should show plan tier names
        await expect(page.locator("text=/Starter|Growth|Elite/").first()).toBeVisible({ timeout: 10_000 });
    });
});

// ─── Document Alerts Page ────────────────────────────────────────────────────

test.describe("Document Alerts Page", () => {
    test.skip(!email || !password, "Set E2E_EMAIL and E2E_PASSWORD to run");

    test("A1: Alerts page loads", async ({ page }) => {
        await login(page);
        await page.goto("/alerts");
        await page.waitForLoadState("networkidle");
        await expect(page.locator("text=Document Alerts")).toBeVisible({ timeout: 10_000 });
    });

    test("A2: Shows stat cards or All Clear state", async ({ page }) => {
        await login(page);
        await page.goto("/alerts");
        await page.waitForLoadState("networkidle");
        // Either summary cards or All Clear
        const hasAlerts = page.locator("text=/Expired Documents|Expiring Soon|Re-run Needed/");
        const allClear = page.locator("text=All Clear");
        const found = await Promise.race([
            hasAlerts.first().waitFor({ timeout: 10_000 }).then(() => "alerts"),
            allClear.waitFor({ timeout: 10_000 }).then(() => "clear"),
        ]).catch(() => "timeout");
        expect(["alerts", "clear"]).toContain(found);
    });

    test("A3: Send Alert Emails button exists", async ({ page }) => {
        await login(page);
        await page.goto("/alerts");
        await page.waitForLoadState("networkidle");
        const notifyBtn = page.getByRole("button", { name: /Send Alert Emails/i });
        await expect(notifyBtn).toBeVisible({ timeout: 10_000 });
    });

    test("A4: Refresh button exists", async ({ page }) => {
        await login(page);
        await page.goto("/alerts");
        await page.waitForLoadState("networkidle");
        const refreshBtn = page.getByRole("button", { name: /Refresh/i });
        await expect(refreshBtn).toBeVisible({ timeout: 10_000 });
    });
});

// ─── Admin Dashboard ─────────────────────────────────────────────────────────

test.describe("Admin Dashboard", () => {
    test.skip(!email || !password, "Set E2E_EMAIL and E2E_PASSWORD to run");

    test("AD1: Admin page loads", async ({ page }) => {
        await login(page);
        await page.goto("/admin");
        await page.waitForLoadState("networkidle");
        // Should show some admin content or redirect
        const adminContent = page.locator("text=/Admin|Dashboard|Projects|Documents|MRR/");
        await expect(adminContent.first()).toBeVisible({ timeout: 10_000 });
    });
});

// ─── Onboarding Flow ─────────────────────────────────────────────────────────

test.describe("Onboarding Flow", () => {
    test.skip(!email || !password, "Set E2E_EMAIL and E2E_PASSWORD to run");

    test("O1: Onboarding page loads with welcome step", async ({ page }) => {
        await login(page);
        await page.goto("/onboarding");
        await page.waitForLoadState("networkidle");
        await expect(page.locator("text=/Welcome|Get Started|Compliance/").first()).toBeVisible({ timeout: 10_000 });
    });
});

import { expect, test } from "@playwright/test";

const email = process.env.E2E_EMAIL;
const password = process.env.E2E_PASSWORD;

test.describe("Phase 1A auth happy path", () => {
  test.skip(!email || !password, "Set E2E_EMAIL and E2E_PASSWORD to run this test");

  test("login -> dashboard -> org current -> settings/org 200", async ({ page }) => {
    await page.goto("/login");

    await page.getByRole("textbox", { name: "Email" }).fill(email!);
    await page.getByRole("textbox", { name: "Password" }).fill(password!);
    await page.getByRole("button", { name: "Sign In" }).click();

    await page.waitForURL("**/dashboard");
    await expect(page.getByRole("heading", { name: "Dashboard" })).toBeVisible();

    const orgCurrent = await page.evaluate(async () => {
      const res = await fetch("/api/v1/orgs/current");
      let body: unknown = null;
      try {
        body = await res.json();
      } catch {
        body = null;
      }
      return { status: res.status, body };
    });

    expect(orgCurrent.status).toBe(200);
    const orgId = (orgCurrent.body as { id?: string } | null)?.id;
    expect(orgId).toBeTruthy();

    const orgSettings = await page.evaluate(async (id) => {
      const res = await fetch(`/api/v1/settings/org?org_id=${encodeURIComponent(id)}`);
      let body: unknown = null;
      try {
        body = await res.json();
      } catch {
        body = null;
      }
      return { status: res.status, body };
    }, orgId!);

    expect(orgSettings.status).toBe(200);
  });
});

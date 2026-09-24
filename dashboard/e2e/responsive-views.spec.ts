import { expect, test, type Page } from "@playwright/test";

// ── Session & mock API (mirrors assurance-views.spec.ts) ──────────
const session = {
  access_token: "test-access-token",
  role: "admin",
  expires_at: Math.floor(Date.now() / 1000) + 3600,
};

async function mockApi(page: Page) {
  await page.route("http://127.0.0.1:4173/api/**", async (route) => {
    const path = new URL(route.request().url()).pathname;
    if (path === "/api/auth/login") return route.fulfill({ json: session });
    if (path === "/api/auth/me") {
      return route.fulfill({ json: { username: "admin", role: "admin" } });
    }
    if (path === "/api/dashboard/summary") {
      return route.fulfill({
        json: {
          total_assets: 1,
          high_risk_count: 1,
          avg_confidence: 0.92,
          coverage_pct: 98,
          blind_spots: [],
          risk_distribution: { CRITICAL: 0, HIGH: 1, MEDIUM: 0, LOW: 0 },
          quantum_vulnerable_count: 1,
          conflict_count: 0,
          latest_scan_id: 73,
          collector_stats: { ast: 1 },
        },
      });
    }
    if (path === "/api/reports/risk") {
      return route.fulfill({
        json: {
          title: "Repository risk report",
          scan_id: 73,
          repository: "/test-repo",
          coverage_pct: 98,
          summary: {},
          blind_spots: ["Native binaries were not inspected"],
          migration_priorities: [
            {
              asset_id: 901,
              algorithm: "RSA",
              location: "src/crypto.ts:18",
              score: 91,
              label: "HIGH",
              reasons: ["Quantum-vulnerable public-key algorithm"],
              recommendation: "Migrate to ML-KEM with a hybrid transition",
              hybrid: true,
            },
          ],
          pagination: { total: 1, filtered: 1, offset: 0, limit: 100, loaded: 1 },
        },
      });
    }
    if (path === "/api/evaluation") {
      return route.fulfill({
        json: {
          available: true,
          scan_id: 73,
          coverage_pct: 98,
          duration_ms: 420,
          precision: 0.95,
          recall: 0.9,
          f1: 0.92,
        },
      });
    }
    if (path === "/api/cbom") {
      return route.fulfill({
        json: {
          bom_format: "CycloneDX",
          spec_version: "1.6",
          serial_number: "urn:uuid:test-cbom",
          metadata: { timestamp: "2026-09-07T10:00:00Z" },
          components: [
            {
              type: "library",
              name: "OpenSSL",
              purl: "pkg:generic/openssl@3.0",
              evidence: [
                {
                  algorithm: "RSA",
                  category: "asymmetric",
                  location: "src/crypto.ts:18",
                  usage: "encryption",
                  library: "OpenSSL",
                  confidence: 0.92,
                  source: ["ast", "rules"],
                },
              ],
            },
          ],
          vulnerabilities: [],
          dependencies: [{ ref: "openssl" }],
          services: [],
          pagination: { total: 1, filtered: 1, offset: 0, limit: 100, loaded: 1 },
        },
      });
    }
    if (path === "/api/evidence-graph") {
      return route.fulfill({ json: { nodes: [{ id: "openssl", type: "library" }], edges: [] } });
    }
    if (path === "/api/scans/73") {
      return route.fulfill({
        json: {
          id: 73,
          repo_path: "/test-repo",
          status: "completed",
          started_at: "2026-09-07T10:00:00Z",
          finished_at: "2026-09-07T10:00:02Z",
          assets_found: 1,
          avg_confidence: 0.92,
          total_files: 25,
          in_scope_files: 20,
          scanned_files: 19,
          failed_files: 1,
          coverage_pct: 95,
          duration_ms: 2400,
          collector_stats: { ast: 1, rules: 1 },
          blind_spots: ["One supported file could not be parsed"],
          failures: [{ path: "fixtures/bad-certificate.pem", reason: "certificate_error" }],
          assets: [
            {
              id: 901,
              scan_job_id: 73,
              logical_asset_id: "rsa-encryption-src-crypto",
              algorithm: "RSA",
              category: "asymmetric",
              source: ["ast", "rules"],
              location: "src/crypto.ts:18",
              evidence_json: {},
              confidence: 0.92,
              conflict: false,
              quantum_vulnerable: true,
              priority_score: 91,
              priority_label: "HIGH",
              pqc_candidate: "ML-KEM",
              business_criticality: "high",
              usage: "encryption",
              library: "OpenSSL",
              protocol: "",
              key_size: 2048,
              data_sensitivity: "confidential",
              data_lifetime_years: 10,
              migration_time_years: 2,
              threat_horizon_years: 5,
              exposure: "external",
              migration_effort: "medium",
              risk_reasons: ["Harvest-now-decrypt-later exposure"],
              hybrid_recommended: true,
              created_at: "2026-09-07T10:00:02Z",
            },
          ],
        },
      });
    }
    if (path === "/api/assets") {
      return route.fulfill({
        headers: { "X-Total-Count": "1" },
        json: {
          items: [
            {
              id: 901,
              scan_job_id: 73,
              logical_asset_id: "rsa-encryption-src-crypto",
              algorithm: "RSA",
              category: "asymmetric",
              source: ["ast", "rules"],
              location: "src/crypto.ts:18",
              evidence_json: {},
              confidence: 0.92,
              conflict: false,
              quantum_vulnerable: true,
              priority_score: 91,
              priority_label: "HIGH",
              pqc_candidate: "ML-KEM",
              business_criticality: "high",
              usage: "encryption",
              library: "OpenSSL",
              protocol: "",
              key_size: 2048,
              data_sensitivity: "confidential",
              data_lifetime_years: 10,
              migration_time_years: 2,
              threat_horizon_years: 5,
              exposure: "external",
              migration_effort: "medium",
              risk_reasons: ["Harvest-now-decrypt-later exposure"],
              hybrid_recommended: true,
              created_at: "2026-09-07T10:00:02Z",
            },
          ],
          total: 1,
        },
      });
    }
    return route.fulfill({ status: 404, json: { detail: `Unhandled test route: ${path}` } });
  });
}

async function signIn(page: Page) {
  await page.goto("/");
  await page.getByLabel("Username").fill("admin");
  await page.getByLabel("Password").fill("valid-password");
  await page.getByRole("button", { name: "Sign in" }).click();
  await expect(page.locator(".app-shell")).toBeVisible();
}

// ── Viewport definitions ──────────────────────────────────────────
const viewports = [
  { name: "iPhone X", width: 375, height: 812 },
  { name: "iPhone 14 Pro", width: 390, height: 844 },
  { name: "iPad", width: 768, height: 1024 },
  { name: "iPad Pro", width: 1024, height: 1366 },
  { name: "Standard Laptop", width: 1280, height: 800 },
  { name: "Large Desktop", width: 1440, height: 900 },
];

// ── Per-viewport test suites ──────────────────────────────────────
for (const vp of viewports) {
  test.describe(`Responsive: ${vp.name} (${vp.width}px)`, () => {
    test.beforeEach(async ({ page }) => {
      await page.setViewportSize({ width: vp.width, height: vp.height });
      await mockApi(page);
    });

    test("layout has no horizontal overflow", async ({ page }) => {
      await signIn(page);

      const layout = await page.evaluate(() => ({
        viewport: document.documentElement.clientWidth,
        scrollWidth: document.documentElement.scrollWidth,
      }));

      expect(layout.viewport).toBe(vp.width);
      expect(layout.scrollWidth).toBeLessThanOrEqual(layout.viewport);
    });

    test("topbar navigation visibility matches the viewport and remains functional", async ({
      page,
    }) => {
      await signIn(page);

      const nav = page.locator(".topbar-nav");
      if (vp.width <= 860) {
        await expect(nav).toBeHidden();
        await page.getByRole("button", { name: "Toggle navigation menu" }).click();
      }
      await expect(nav).toBeVisible();

      // Every nav link should be in the DOM
      const links = ["Overview", "Inventory", "New scan", "Reports", "CBOM"];

      for (const label of links) {
        await expect(page.getByRole("link", { name: label, exact: true })).toBeVisible();
      }

      // Navigate via the nav to CBOM
      await page.getByRole("link", { name: "CBOM", exact: true }).click();
      await expect(page).toHaveURL(/\/cbom$/);

      // Navigate back to Overview
      if (vp.width <= 860) {
        await page.getByRole("button", { name: "Toggle navigation menu" }).click();
      }
      await page.getByRole("link", { name: "Overview", exact: true }).click();
      await expect(page).toHaveURL(/\/$/);
    });

    test("assurance metrics are visible on the dashboard", async ({ page }) => {
      await signIn(page);

      const metrics = page.locator(".assurance-metric");
      await expect(metrics.first()).toBeVisible();
      await expect(metrics).toHaveCount(5);
    });

    test("CBOM page renders components without clipping", async ({ page }) => {
      await signIn(page);
      if (vp.width <= 860) {
        await page.getByRole("button", { name: "Toggle navigation menu" }).click();
      }
      await page.getByRole("link", { name: "CBOM", exact: true }).click();

      await expect(page.getByRole("button", { name: "Components (1)" })).toBeVisible();
      await expect(page.getByRole("heading", { name: "OpenSSL" })).toBeVisible();

      // Switch to dependency graph tab
      await page.getByRole("button", { name: "Dependency graph" }).click();
      await expect(page.getByRole("heading", { name: "Dependency graph" })).toBeVisible();

      // Switch to raw JSON tab
      await page.getByRole("button", { name: "Raw JSON" }).click();
      await expect(page.getByRole("heading", { name: "Raw CBOM JSON" })).toBeVisible();
      await expect(page.locator("pre")).toContainText('"bom_format": "CycloneDX"');

      // Verify no horizontal overflow on the CBOM page
      const cbomLayout = await page.evaluate(() => ({
        scrollWidth: document.documentElement.scrollWidth,
        clientWidth: document.documentElement.clientWidth,
      }));
      expect(cbomLayout.scrollWidth).toBeLessThanOrEqual(cbomLayout.clientWidth);
    });

    test("scan detail tables are accessible", async ({ page }) => {
      await signIn(page);
      await page.goto("/scans/73");

      await expect(page.getByRole("heading", { name: "Scan #73" })).toBeVisible();
      await expect(page.getByText("src/crypto.ts:18")).toBeVisible();

      // The asset table should be rendered and scrollable if needed
      const assetRows = page.locator("table tbody tr");
      await expect(assetRows).toHaveCount(1);

      // Each row's first cell (algorithm) should be fully visible
      const firstRow = assetRows.first();
      const firstCell = firstRow.locator("td").first();
      await expect(firstCell).toBeVisible();

      // Verify no horizontal overflow on scan detail page
      const scanLayout = await page.evaluate(() => ({
        scrollWidth: document.documentElement.scrollWidth,
        clientWidth: document.documentElement.clientWidth,
      }));
      expect(scanLayout.scrollWidth).toBeLessThanOrEqual(scanLayout.clientWidth);
    });

    test("no element has overflow-visible that causes clipping", async ({ page }) => {
      await signIn(page);

      const overflowResults = await page.evaluate(() => {
        const offenders: string[] = [];
        // Check topbar and main content areas for overflow
        const selectors = [
          ".topbar",
          ".topbar-nav",
          "main",
          ".app-shell",
          ".assurance-metric",
          "table",
          ".cbom-container",
          "footer",
        ];
        for (const sel of selectors) {
          const el = document.querySelector(sel);
          if (el) {
            const style = getComputedStyle(el);
            if (style.overflowX === "visible" && el.scrollWidth > el.clientWidth) {
              offenders.push(sel);
            }
          }
        }
        return offenders;
      });

      expect(overflowResults).toEqual([]);
    });

    test("all nav links are keyboard accessible", async ({ page }) => {
      await signIn(page);

      // Walk through all nav links with Tab and verify focus lands on each
      const navLinks = ["Overview", "Inventory", "Scan history", "New scan", "Reports", "CBOM"];
      if (vp.width <= 860) {
        await page.getByRole("button", { name: "Toggle navigation menu" }).click();
        await expect(page.getByRole("link", { name: navLinks[0], exact: true })).toBeFocused();
      } else {
        await page.locator(".brand").focus();
        await page.keyboard.press("Tab");
      }
      for (const label of navLinks) {
        const link = page.getByRole("link", { name: label, exact: true });
        await expect(link).toBeFocused();
        await page.keyboard.press("Tab");
      }
    });
  });
}

// ── Mobile nav push-down behavior ─────────────────────────────────
test.describe("Mobile nav: push-down behavior at 375px", () => {
  test.beforeEach(async ({ page }) => {
    await page.setViewportSize({ width: 375, height: 812 });
    await mockApi(page);
  });

  test("hamburger toggle opens nav that pushes content down", async ({ page }) => {
    await signIn(page);

    // Click the hamburger toggle
    const toggle = page.getByRole("button", { name: "Toggle navigation menu" });
    await expect(toggle).toBeVisible();
    await toggle.click();

    // Wait for the nav-open class to apply
    const nav = page.locator(".topbar-nav");
    await expect(nav).toHaveClass(/open/);

    // Verify all nav links are visible in the opened menu
    const navLinks = ["Overview", "Inventory", "Reports", "CBOM"];
    for (const label of navLinks) {
      await expect(page.getByRole("link", { name: label, exact: true })).toBeVisible();
    }

    // Measure positions after nav opens
    const afterOpen = await page.evaluate(() => {
      const main = document.querySelector("main");
      const nav = document.querySelector(".topbar-nav");
      const header = document.querySelector(".topbar");
      return {
        mainTop: (main as HTMLElement | null)?.offsetTop ?? 0,
        navBottom: (header as HTMLElement | null)?.offsetHeight ?? 0,
        navHeight: nav?.getBoundingClientRect().height ?? 0,
        navDisplay: getComputedStyle(nav!).display,
        navPosition: getComputedStyle(nav!).position,
      };
    });

    // Push-down: the main content should be below the nav, not underneath it.
    // The nav should NOT be absolutely positioned overlaying the content.
    expect(afterOpen.navPosition).not.toBe("absolute");
    // Layout animations can move the dashboard slightly while it settles; the
    // invariant is that the open menu remains in flow and does not cover main.
    expect(afterOpen.mainTop).toBeGreaterThanOrEqual(afterOpen.navBottom - 1);

    // Navigate via the mobile nav
    await page.getByRole("link", { name: "CBOM", exact: true }).click();
    await expect(page).toHaveURL(/\/cbom$/);
  });

  test("closed navigation is absent from layout and keyboard order", async ({ page }) => {
    await signIn(page);

    const toggle = page.getByRole("button", { name: "Toggle navigation menu" });
    const nav = page.locator(".topbar-nav");
    await expect(toggle).toHaveAttribute("aria-expanded", "false");
    await expect(nav).toBeHidden();

    await page.locator(".brand").focus();
    await page.keyboard.press("Tab");
    await expect(toggle).toBeFocused();
  });

  test("opening navigation moves focus to the first destination", async ({ page }) => {
    await signIn(page);

    await page.getByRole("button", { name: "Toggle navigation menu" }).click();

    await expect(page.getByRole("link", { name: "Overview", exact: true })).toBeFocused();
  });

  test("route navigation closes the menu", async ({ page }) => {
    await signIn(page);

    const toggle = page.getByRole("button", { name: "Toggle navigation menu" });
    await toggle.click();
    await page.getByRole("link", { name: "CBOM", exact: true }).click();

    await expect(page).toHaveURL(/\/cbom$/);
    await expect(toggle).toHaveAttribute("aria-expanded", "false");
    await expect(page.locator(".topbar-nav")).toBeHidden();
  });

  test("outside interaction closes the menu without stealing focus", async ({ page }) => {
    await signIn(page);

    const toggle = page.getByRole("button", { name: "Toggle navigation menu" });
    await toggle.click();
    await page.getByRole("heading", { name: "Cryptographic assurance overview" }).click();

    await expect(toggle).toHaveAttribute("aria-expanded", "false");
    await expect(page.locator(".topbar-nav")).toBeHidden();
    await expect(toggle).not.toBeFocused();
  });

  test("moving focus beyond the navigation closes it", async ({ page }) => {
    await signIn(page);

    const toggle = page.getByRole("button", { name: "Toggle navigation menu" });
    const themeToggle = page.getByRole("button", { name: /switch to .+ mode/i });
    await toggle.click();
    await themeToggle.focus();

    await expect(toggle).toHaveAttribute("aria-expanded", "false");
    await expect(themeToggle).toBeFocused();
  });

  test("primary mobile navigation targets are at least 44 by 44 pixels", async ({ page }) => {
    await signIn(page);
    await page.getByRole("button", { name: "Toggle navigation menu" }).click();

    const undersized = await page.locator(".topbar button, .topbar-nav a").evaluateAll((items) =>
      items
        .map((item) => {
          const box = item.getBoundingClientRect();
          return {
            label: item.getAttribute("aria-label") || item.textContent?.trim(),
            ...box.toJSON(),
          };
        })
        .filter(({ width, height }) => width < 44 || height < 44),
    );
    expect(undersized).toEqual([]);
  });

  test("Escape key closes the mobile navigation", async ({ page }) => {
    await signIn(page);

    const toggle = page.getByRole("button", { name: "Toggle navigation menu" });
    await toggle.click();

    const nav = page.locator(".topbar-nav");
    await expect(nav).toHaveClass(/open/);

    // Press Escape
    await page.keyboard.press("Escape");

    // The nav should lose the open class
    await expect(nav).not.toHaveClass(/open/);
    await expect(page.getByRole("button", { name: "Toggle navigation menu" })).toHaveAttribute(
      "aria-expanded",
      "false",
    );
    await expect(toggle).toBeFocused();
  });

  test("toggling the hamburger twice returns to closed state", async ({ page }) => {
    await signIn(page);

    const toggle = page.getByRole("button", { name: "Toggle navigation menu" });
    await toggle.click();
    await expect(page.locator(".topbar-nav")).toHaveClass(/open/);

    await toggle.click();
    await expect(page.locator(".topbar-nav")).not.toHaveClass(/open/);
  });
});

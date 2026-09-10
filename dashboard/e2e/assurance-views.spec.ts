import { expect, test, type Page } from "@playwright/test";

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
        json: [
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
  await expect(page.getByRole("navigation", { name: "Main navigation" })).toBeVisible();
}

test.beforeEach(async ({ page }) => mockApi(page));

test("reports show ranked migration priorities and evaluation metrics", async ({ page }) => {
  await signIn(page);
  await page.getByRole("link", { name: "Reports" }).click();

  await expect(page.getByRole("heading", { name: "Repository risk report" })).toBeVisible();
  await expect(page.getByRole("cell", { name: "RSA" })).toBeVisible();
  await expect(page.getByText("Precision 95%")).toBeVisible();
});

test("CBOM switches between components, dependency graph, and raw JSON", async ({ page }) => {
  await signIn(page);
  await page.getByRole("link", { name: "CBOM" }).click();

  await expect(page.getByRole("heading", { name: "Components (1)" })).toBeVisible();
  await expect(page.getByRole("heading", { name: "OpenSSL" })).toBeVisible();
  await page.getByRole("button", { name: "Dependency graph" }).click();
  await expect(page.getByRole("heading", { name: "Dependency graph" })).toBeVisible();
  await page.getByRole("button", { name: "Raw JSON" }).click();
  await expect(page.getByRole("heading", { name: "Raw CBOM JSON" })).toBeVisible();
  await expect(page.locator("pre")).toContainText('"bom_format": "CycloneDX"');
});

test("completed scan detail exposes metrics, assets, and a CSV download", async ({ page }) => {
  await signIn(page);
  await page.goto("/scans/73");

  await expect(page.getByRole("heading", { name: "Scan #73" })).toBeVisible();
  await expect(page.getByText("src/crypto.ts:18")).toBeVisible();
  await expect(page.getByRole("heading", { name: "Failed files" })).toBeVisible();
  await expect(page.getByText("fixtures/bad-certificate.pem")).toBeVisible();
  await expect(page.getByText("Certificate error")).toBeVisible();
  const downloadPromise = page.waitForEvent("download");
  await page.getByRole("button", { name: "Export displayed CSV" }).click();
  const download = await downloadPromise;
  expect(download.suggestedFilename()).toBe("scan-73-assets.csv");
});

test("mobile dark mode honors the 375px viewport and reduced-motion preference", async ({
  page,
}) => {
  await page.setViewportSize({ width: 375, height: 812 });
  await page.emulateMedia({ reducedMotion: "reduce" });
  await signIn(page);

  await page.getByRole("button", { name: "Switch to dark mode" }).click();
  await expect(page.locator("html")).toHaveAttribute("data-theme", "dark");
  await expect(page.getByRole("navigation", { name: "Main navigation" })).toBeVisible();
  const navigation = page.getByRole("navigation", { name: "Main navigation" });
  const navWidth = await navigation.evaluate((element) => element.clientWidth);
  expect(navWidth).toBeGreaterThan(300);
  await page.getByRole("link", { name: "CBOM", exact: true }).click();
  await expect(page).toHaveURL(/\/cbom$/);
  await page.getByRole("link", { name: "Overview", exact: true }).click();
  await expect(page.getByRole("heading", { name: "Risk distribution", exact: true })).toBeVisible();
  const layout = await page.evaluate(() => ({
    viewport: document.documentElement.clientWidth,
    page: document.documentElement.scrollWidth,
    reducedMotion: matchMedia("(prefers-reduced-motion: reduce)").matches,
    transitionDuration: getComputedStyle(document.querySelector(".theme-toggle")!)
      .transitionDuration,
  }));
  expect(layout.viewport).toBe(375);
  expect(layout.page).toBe(layout.viewport);
  expect(layout.reducedMotion).toBe(true);
  expect(Number.parseFloat(layout.transitionDuration)).toBeLessThanOrEqual(0.001);
});

test("keyboard users can reveal the skip link and move focus to main content", async ({ page }) => {
  await signIn(page);
  const skipLink = page.getByRole("link", { name: "Skip to main content" });
  await skipLink.focus();
  await expect(skipLink).toBeFocused();
  await expect(skipLink).toHaveCSS("top", "0px");
  await page.keyboard.press("Enter");
  await expect(page.locator("#main-content")).toBeFocused();
});

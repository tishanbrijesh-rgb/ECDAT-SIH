import { afterEach, describe, expect, it, vi } from "vitest";
import { getCbom, getRiskReport, getScanDetail } from "./client";

describe("getScanDetail", () => {
  afterEach(() => vi.restoreAllMocks());

  it("combines the scan job with its assets", async () => {
    const scan = {
      id: 7,
      repo_path: "repo",
      status: "completed",
      started_at: null,
      finished_at: null,
      assets_found: 1,
      avg_confidence: 0.9,
      total_files: 1,
      in_scope_files: 1,
      scanned_files: 1,
      failed_files: 0,
      coverage_pct: 100,
      duration_ms: 10,
      collector_stats: {},
      blind_spots: [],
    };
    const asset = { id: 11 };
    vi.spyOn(globalThis, "fetch")
      .mockResolvedValueOnce(new Response(JSON.stringify(scan), { status: 200 }))
      .mockResolvedValueOnce(
        new Response(JSON.stringify({ items: [asset], total: 325 }), {
          status: 200,
          headers: { "X-Total-Count": "325" },
        }),
      )
      .mockResolvedValueOnce(
        new Response(
          JSON.stringify({
            total_assets: 325,
            high_risk_count: 1,
            avg_confidence: 0.9,
            coverage_pct: 100,
            blind_spots: [],
            risk_distribution: { CRITICAL: 0, HIGH: 1, MEDIUM: 0, LOW: 324 },
            quantum_vulnerable_count: 1,
            conflict_count: 0,
            latest_scan_id: 7,
            collector_stats: {},
          }),
          { status: 200 },
        ),
      );

    await expect(getScanDetail(7)).resolves.toMatchObject({
      id: 7,
      assets: [asset],
      assets_total: 325,
      summary: { total_assets: 325 },
    });
    expect(fetch).toHaveBeenNthCalledWith(
      2,
      expect.stringContaining("/api/assets?scan_job_id=7&limit=200"),
      expect.any(Object),
    );
    expect(fetch).toHaveBeenNthCalledWith(
      3,
      expect.stringContaining("/api/dashboard/summary?scan_id=7"),
      expect.any(Object),
    );
  });
});

describe("paged output requests", () => {
  afterEach(() => vi.restoreAllMocks());

  it("sends stable pagination and filtering parameters", async () => {
    vi.spyOn(globalThis, "fetch")
      .mockResolvedValueOnce(new Response(JSON.stringify({ components: [] }), { status: 200 }))
      .mockResolvedValueOnce(
        new Response(JSON.stringify({ migration_priorities: [] }), { status: 200 }),
      );

    await getCbom(9, { limit: 100, offset: 200, query: "sha" });
    await getRiskReport(9, { limit: 100, offset: 300, risk: "HIGH", query: "tls" });

    expect(fetch).toHaveBeenNthCalledWith(
      1,
      expect.stringContaining("/api/cbom?scan_id=9&limit=100&offset=200&q=sha"),
      expect.any(Object),
    );
    expect(fetch).toHaveBeenNthCalledWith(
      2,
      expect.stringContaining("/api/reports/risk?scan_id=9&limit=100&offset=300&risk=HIGH&q=tls"),
      expect.any(Object),
    );
  });
});

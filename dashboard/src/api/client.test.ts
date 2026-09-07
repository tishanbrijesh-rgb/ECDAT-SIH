import { afterEach, describe, expect, it, vi } from "vitest";
import { getScanDetail } from "./client";

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
        new Response(JSON.stringify([asset]), {
          status: 200,
          headers: { "X-Total-Count": "325" },
        }),
      );

    await expect(getScanDetail(7)).resolves.toMatchObject({
      id: 7,
      assets: [asset],
      assets_total: 325,
    });
    expect(fetch).toHaveBeenNthCalledWith(
      2,
      expect.stringContaining("/api/assets?scan_job_id=7&limit=200"),
      expect.any(Object),
    );
  });
});

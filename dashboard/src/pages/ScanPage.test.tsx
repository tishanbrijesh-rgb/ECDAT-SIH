import { describe, expect, it } from "vitest";

import { progressDisplay, isActiveScanStatus, shouldPollScanStatus } from "./ScanPage";

describe("scan lifecycle", () => {
  it("keeps the running screen visible for every accepted scan status", () => {
    expect(
      ["started", "queued", "pending", "initialising", "running"].every(isActiveScanStatus),
    ).toBe(true);
  });
});

describe("scan progress fallback", () => {
  it("polls while a scan is active and stops after completion", () => {
    expect(shouldPollScanStatus("running")).toBe(true);
    expect(shouldPollScanStatus("completed")).toBe(false);
  });

  it("shows discovered files while a large repository is being indexed", () => {
    expect(
      progressDisplay({
        scan_id: 7,
        status: "running",
        collector_stats: {
          _phase: "indexing",
          _files_discovered: 8421,
          _files_supported: 312,
        },
        assets_found: 0,
        coverage_pct: 0,
        duration_ms: 500,
      }),
    ).toEqual({ phase: "indexing", files: 8421, label: "Files discovered" });
  });

  it("derives live scan progress from processed and supported files", () => {
    expect(
      progressDisplay({
        scan_id: 38,
        status: "running",
        collector_stats: {
          _phase: "collecting",
          _files_processed: 509,
          _files_supported: 2312,
        },
        assets_found: 0,
        coverage_pct: 0,
        duration_ms: 207000,
      }),
    ).toEqual({
      phase: "collecting",
      files: 509,
      label: "Files processed",
      progressPercent: 22.02,
    });
  });
});

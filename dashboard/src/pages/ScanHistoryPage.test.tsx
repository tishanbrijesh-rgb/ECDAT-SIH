import { render, screen } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import { beforeEach, describe, expect, it, vi } from "vitest";

import ScanHistoryPage from "./ScanHistoryPage";

vi.mock("../api/client", () => ({ getScans: vi.fn() }));
import { getScans } from "../api/client";

describe("ScanHistoryPage", () => {
  beforeEach(() => {
    vi.mocked(getScans).mockResolvedValue([
      {
        id: 29,
        repo_path: "C:\\Python314",
        status: "completed",
        started_at: null,
        finished_at: null,
        assets_found: 12,
        avg_confidence: 0.8,
        total_files: 100,
        in_scope_files: 80,
        scanned_files: 80,
        failed_files: 0,
        coverage_pct: 100,
        duration_ms: 1500,
        collector_stats: {},
        blind_spots: [],
      },
    ]);
  });

  it("provides an inspect action for every scan", async () => {
    render(
      <MemoryRouter>
        <ScanHistoryPage />
      </MemoryRouter>,
    );
    expect(await screen.findByText("C:\\Python314")).toBeInTheDocument();
    expect(screen.getByRole("columnheader", { name: "Supported-file coverage" })).toBeVisible();
    expect(screen.getByRole("link", { name: /inspect/i })).toHaveAttribute("href", "/scans/29");
  });
});

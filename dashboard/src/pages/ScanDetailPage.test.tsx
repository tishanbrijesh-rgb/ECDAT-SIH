import { render, screen } from "@testing-library/react";
import { MemoryRouter, Route, Routes } from "react-router-dom";
import { describe, expect, it, vi } from "vitest";
import { getScanDetail } from "../api/client";
import ScanDetailPage from "./ScanDetailPage";

vi.mock("../api/client", () => ({
  downloadCsv: vi.fn(),
  getScanDetail: vi.fn(),
}));

describe("ScanDetailPage", () => {
  it("transitions from loading to the scan details", async () => {
    vi.mocked(getScanDetail).mockResolvedValue({
      id: 7,
      repo_path: "/repo",
      status: "completed",
      started_at: null,
      finished_at: null,
      assets_found: 0,
      avg_confidence: null,
      total_files: 1,
      in_scope_files: 1,
      scanned_files: 1,
      failed_files: 0,
      coverage_pct: 100,
      duration_ms: 10,
      collector_stats: {},
      blind_spots: [],
      assets: [],
      assets_total: 0,
    });

    render(
      <MemoryRouter initialEntries={["/scans/7"]}>
        <Routes>
          <Route path="/scans/:id" element={<ScanDetailPage />} />
        </Routes>
      </MemoryRouter>,
    );

    expect(screen.getByText("Loading scan detail")).toBeInTheDocument();
    expect(await screen.findByRole("heading", { name: "Scan #7" })).toBeInTheDocument();
  });

  it("shows sanitized failed file details", async () => {
    vi.mocked(getScanDetail).mockResolvedValue({
      id: 8,
      repo_path: "/repo",
      status: "completed",
      started_at: null,
      finished_at: null,
      assets_found: 0,
      avg_confidence: null,
      total_files: 2,
      in_scope_files: 2,
      scanned_files: 1,
      failed_files: 1,
      coverage_pct: 50,
      duration_ms: 10,
      collector_stats: {},
      blind_spots: [],
      failures: [{ path: "certs/broken.pem", reason: "certificate_error" }],
      assets: [],
      assets_total: 0,
    } as any);

    render(
      <MemoryRouter initialEntries={["/scans/8"]}>
        <Routes>
          <Route path="/scans/:id" element={<ScanDetailPage />} />
        </Routes>
      </MemoryRouter>,
    );

    expect(await screen.findByRole("heading", { name: "Failed files" })).toBeInTheDocument();
    expect(screen.getByText("certs/broken.pem")).toBeInTheDocument();
    expect(screen.getByText("Certificate error")).toBeInTheDocument();
  });
});

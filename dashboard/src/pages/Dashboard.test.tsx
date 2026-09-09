import { act, render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { Link, MemoryRouter } from "react-router-dom";
import type { DashboardSummary } from "../types";
import { describe, expect, it, vi } from "vitest";
import { downloadReport, getDashboardSummary, getEvaluation } from "../api/client";
import Dashboard from "./Dashboard";

vi.mock("../api/client", () => ({
  canWrite: vi.fn(() => false),
  downloadReport: vi.fn(),
  getDashboardSummary: vi.fn(),
  getEvaluation: vi.fn(),
}));

vi.mock("../components/RiskDistributionChart", () => ({
  default: () => <div>Risk chart</div>,
}));

describe("Dashboard", () => {
  const summary: DashboardSummary = {
    total_assets: 1,
    high_risk_count: 0,
    avg_confidence: 0.9,
    coverage_pct: 100,
    blind_spots: [],
    risk_distribution: { CRITICAL: 0, HIGH: 0, MEDIUM: 0, LOW: 1 },
    quantum_vulnerable_count: 0,
    conflict_count: 0,
    latest_scan_id: 7,
    collector_stats: {},
  };

  it("keeps the dashboard available after a failed download", async () => {
    vi.mocked(getDashboardSummary).mockResolvedValue(summary);
    vi.mocked(getEvaluation).mockRejectedValue(new Error("unavailable"));
    vi.mocked(downloadReport).mockRejectedValue(new Error("Download failed"));
    render(
      <MemoryRouter>
        <Dashboard />
      </MemoryRouter>,
    );
    await userEvent.click(await screen.findByRole("button", { name: "Download risk report" }));
    expect(await screen.findByRole("alert")).toHaveTextContent("Download failed");
    expect(
      screen.getByRole("heading", { name: "Cryptographic assurance overview" }),
    ).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Download risk report" })).toBeEnabled();
  });

  it("ignores an older scan failure after navigation", async () => {
    let rejectOld!: (error: Error) => void;
    vi.mocked(getDashboardSummary)
      .mockImplementationOnce(
        () =>
          new Promise((_, reject) => {
            rejectOld = reject;
          }),
      )
      .mockResolvedValueOnce(summary);
    vi.mocked(getEvaluation).mockRejectedValue(new Error("unavailable"));
    render(
      <MemoryRouter initialEntries={["/?scan_id=8"]}>
        <Link to="/?scan_id=7">Next scan</Link>
        <Dashboard />
      </MemoryRouter>,
    );
    await userEvent.click(screen.getByRole("link", { name: "Next scan" }));
    expect(
      await screen.findByRole("heading", { name: "Cryptographic assurance overview" }),
    ).toBeInTheDocument();
    await act(async () => rejectOld(new Error("Old scan failed")));
    expect(screen.queryByText("Dashboard unavailable")).not.toBeInTheDocument();
  });

  it("transitions from loading to the populated summary", async () => {
    vi.mocked(getDashboardSummary).mockResolvedValue({
      total_assets: 1,
      high_risk_count: 0,
      avg_confidence: 0.9,
      coverage_pct: 100,
      blind_spots: [],
      risk_distribution: { CRITICAL: 0, HIGH: 0, MEDIUM: 0, LOW: 1 },
      quantum_vulnerable_count: 0,
      conflict_count: 0,
      latest_scan_id: 7,
      collector_stats: { ast: 1 },
    });
    vi.mocked(getEvaluation).mockRejectedValue(new Error("not available"));

    render(
      <MemoryRouter>
        <Dashboard />
      </MemoryRouter>,
    );

    expect(screen.getByText("Building assurance view")).toBeInTheDocument();
    expect(
      await screen.findByRole("heading", { name: "Cryptographic assurance overview" }),
    ).toBeInTheDocument();
  });

  it("keeps the selected scan in downloads and CBOM navigation", async () => {
    vi.mocked(getDashboardSummary).mockResolvedValue({
      total_assets: 1,
      high_risk_count: 1,
      avg_confidence: 0.9,
      coverage_pct: 100,
      blind_spots: [],
      risk_distribution: { CRITICAL: 0, HIGH: 1, MEDIUM: 0, LOW: 0 },
      quantum_vulnerable_count: 1,
      conflict_count: 0,
      latest_scan_id: 9,
      collector_stats: {},
    });
    vi.mocked(getEvaluation).mockRejectedValue(new Error("not available"));
    vi.mocked(downloadReport).mockResolvedValue();

    render(
      <MemoryRouter initialEntries={["/?scan_id=9"]}>
        <Dashboard />
      </MemoryRouter>,
    );

    await userEvent.click(await screen.findByRole("button", { name: "Download risk report" }));
    expect(downloadReport).toHaveBeenCalledWith(
      "/api/reports/risk.txt?scan_id=9",
      "ecdat-risk-report-scan-9.txt",
    );
    expect(screen.getByRole("link", { name: "View CBOM" })).toHaveAttribute(
      "href",
      "/cbom?scan_id=9",
    );
  });
});

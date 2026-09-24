import { render, screen } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import { describe, expect, it, vi } from "vitest";
import { getEvaluation, getRiskReport } from "../api/client";
import RiskReportPage from "./RiskReport";

vi.mock("../api/client", () => ({
  downloadReport: vi.fn(),
  getEvaluation: vi.fn(),
  getRiskReport: vi.fn(),
}));

vi.mock("../components/RiskDistributionChart", () => ({
  default: () => <div>Risk chart</div>,
}));

describe("RiskReportPage", () => {
  it("transitions from loading to the populated report", async () => {
    vi.mocked(getEvaluation).mockResolvedValue({
      available: false,
      scan_id: 7,
      coverage_pct: 100,
      duration_ms: 0,
    });
    vi.mocked(getRiskReport).mockResolvedValue({
      title: "Risk report",
      scan_id: 7,
      repository: "/repo",
      coverage_pct: 100,
      summary: {},
      blind_spots: [],
      pagination: { total: 0, filtered: 0, offset: 0, limit: 100, loaded: 0 },
      migration_priorities: [],
    });

    render(
      <MemoryRouter>
        <RiskReportPage />
      </MemoryRouter>,
    );

    expect(screen.getByText("Building risk view")).toBeInTheDocument();
    expect(await screen.findByRole("heading", { name: "Risk report" })).toBeInTheDocument();
  });

  it("keeps a 10k-result report bounded to the server page", async () => {
    vi.mocked(getEvaluation).mockResolvedValue({
      available: false,
      scan_id: 10,
      coverage_pct: 100,
      duration_ms: 0,
    });
    vi.mocked(getRiskReport).mockResolvedValue({
      title: "Large risk report",
      scan_id: 10,
      repository: "/repo",
      coverage_pct: 100,
      summary: { assets: 10_000, risk_distribution: { HIGH: 10_000 } },
      blind_spots: [],
      pagination: { total: 10_000, filtered: 10_000, offset: 0, limit: 100, loaded: 100 },
      migration_priorities: Array.from({ length: 100 }, (_, index) => ({
        asset_id: index + 1,
        algorithm: `Algorithm ${index}`,
        location: `src/${index}.ts`,
        score: 50,
        label: "HIGH" as const,
        reasons: [],
        recommendation: "Migrate",
        hybrid: false,
      })),
    });

    render(
      <MemoryRouter>
        <RiskReportPage />
      </MemoryRouter>,
    );

    expect(await screen.findByText("Large risk report")).toBeInTheDocument();
    expect(screen.getAllByRole("row")).toHaveLength(101);
    expect(
      screen.getByText("Total 10,000 · Loaded 100 · Filtered 10,000 · Exported 0"),
    ).toBeInTheDocument();
  });
});

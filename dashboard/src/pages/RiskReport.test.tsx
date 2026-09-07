import { render, screen } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import { describe, expect, it, vi } from "vitest";
import { getEvaluation, getRiskReport } from "../api/client";
import RiskReportPage from "./RiskReport";

vi.mock("../api/client", () => ({
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
});

import { render, screen, waitFor } from "@testing-library/react";
import { MemoryRouter, Route, Routes } from "react-router-dom";
import { beforeEach, describe, expect, it, vi } from "vitest";
import AssetDetail from "./AssetDetail";

const getAsset = vi.fn();

vi.mock("../api/client", () => ({
  getAsset: (...args: unknown[]) => getAsset(...args),
  updateAsset: vi.fn(),
  canWrite: () => true,
}));

describe("AssetDetail", () => {
  beforeEach(() => {
    getAsset.mockResolvedValue({
      id: 4758,
      scan_job_id: 35,
      logical_asset_id: "ecdsa-signature-testmock",
      algorithm: "ECDSA",
      category: "asymmetric",
      source: ["rule"],
      location: "vendor/truststore/_macos.py",
      evidence_json: {
        component: "testmock",
        evidence_list: [{ kind: "rule", confidence: 0.82 }],
      },
      confidence: 0.9,
      conflict: false,
      quantum_vulnerable: true,
      priority_score: 60,
      priority_label: "HIGH",
      pqc_candidate: "ML-DSA",
      business_criticality: "medium",
      usage: "signature",
      library: "",
      protocol: "",
      key_size: null,
      data_sensitivity: "medium",
      data_lifetime_years: 10,
      migration_time_years: 3,
      threat_horizon_years: 10,
      exposure: "internal",
      migration_effort: "medium",
      risk_reasons: ["Quantum-vulnerable signature"],
      hybrid_recommended: true,
      capability_only: false,
      risk_context_provenance: {},
      created_at: "2026-09-21T14:43:00Z",
    });
  });

  it("separates evidence, editable context, and the computed migration decision", async () => {
    render(
      <MemoryRouter initialEntries={["/assets/4758"]}>
        <Routes>
          <Route path="/assets/:id" element={<AssetDetail />} />
        </Routes>
      </MemoryRouter>,
    );

    expect(await screen.findByRole("heading", { name: "Discovery assurance" })).toBeVisible();
    expect(screen.getByRole("group", { name: "Business and migration risk inputs" })).toBeVisible();
    expect(screen.getByRole("heading", { name: "Mosca planning window" })).toBeVisible();
    expect(screen.getByText("X — Data lifetime")).toBeVisible();
    expect(screen.getByText("Y — Migration time")).toBeVisible();
    expect(screen.getByText("Z — Threat horizon")).toBeVisible();
    expect(screen.getByText("Conservative estimate")).toBeVisible();
    expect(screen.getByText("Selected baseline")).toBeVisible();
    expect(screen.getByText("Aggressive migration")).toBeVisible();
    expect(screen.getByText("13 years")).toBeVisible();
    expect(screen.getByText("Action is overdue by 3 years.")).toBeVisible();
    expect(screen.getByText(/Begin migration now/)).toBeVisible();

    await waitFor(() => expect(getAsset).toHaveBeenCalledWith(4758));
  });
});

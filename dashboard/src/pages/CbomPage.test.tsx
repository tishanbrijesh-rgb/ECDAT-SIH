import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter } from "react-router-dom";
import { describe, expect, it, vi } from "vitest";
import { getCbom, getEvidenceGraph } from "../api/client";
import CbomPage from "./CbomPage";

vi.mock("../api/client", () => ({
  downloadReport: vi.fn(),
  getCbom: vi.fn(),
  getEvidenceGraph: vi.fn(),
  getRiskReport: vi.fn(),
}));

describe("CbomPage", () => {
  it("shows a completed empty state when the CBOM has no components", async () => {
    vi.mocked(getCbom).mockResolvedValue({
      bom_format: "CycloneDX",
      components: [],
      pagination: { total: 0, filtered: 0, offset: 0, limit: 100, loaded: 0 },
    });
    vi.mocked(getEvidenceGraph).mockResolvedValue({
      scan_id: 1,
      nodes: [],
      edges: [],
    });

    render(
      <MemoryRouter>
        <CbomPage />
      </MemoryRouter>,
    );

    expect(document.querySelector(".cbom-skeleton-grid")).toBeInTheDocument();
    expect(await screen.findByText("No components found")).toBeInTheDocument();
    expect(
      screen.getByText(
        "This scan did not produce any cryptographic components. Run a full discovery scan with dependency analysis enabled.",
      ),
    ).toBeInTheDocument();
    expect(screen.queryByText("CRITICAL")).not.toBeInTheDocument();
    expect(screen.queryByText("HIGH")).not.toBeInTheDocument();
    expect(screen.queryByText("MEDIUM")).not.toBeInTheDocument();
    expect(screen.queryByText("LOW")).not.toBeInTheDocument();
  });

  it("reports a CBOM request failure and lets the user retry", async () => {
    vi.mocked(getCbom)
      .mockRejectedValueOnce(new Error("offline"))
      .mockResolvedValueOnce({
        bom_format: "CycloneDX",
        components: [],
        pagination: { total: 0, filtered: 0, offset: 0, limit: 100, loaded: 0 },
      });
    vi.mocked(getEvidenceGraph).mockResolvedValue({
      scan_id: 1,
      nodes: [],
      edges: [],
    });

    render(
      <MemoryRouter>
        <CbomPage />
      </MemoryRouter>,
    );

    expect(await screen.findByRole("alert")).toHaveTextContent("Unable to load the CBOM");
    await userEvent.click(screen.getByRole("button", { name: "Try again" }));
    expect(await screen.findByText("No components found")).toBeInTheDocument();
    expect(getCbom).toHaveBeenCalledTimes(2);
  });

  it("keeps a 10k-component CBOM bounded to the server page", async () => {
    vi.mocked(getCbom).mockResolvedValue({
      bomFormat: "CycloneDX",
      specVersion: "1.6",
      serialNumber: "urn:uuid:test",
      metadata: {},
      pagination: { total: 10_000, filtered: 10_000, offset: 0, limit: 100, loaded: 100 },
      components: Array.from({ length: 100 }, (_, index) => ({
        type: "library",
        name: `Algorithm ${index}`,
        properties: [],
      })),
    });
    vi.mocked(getEvidenceGraph).mockResolvedValue({ scan_id: 1, nodes: [], edges: [] });

    render(
      <MemoryRouter>
        <CbomPage />
      </MemoryRouter>,
    );

    expect(await screen.findByRole("heading", { name: "Algorithm 0" })).toBeInTheDocument();
    expect(document.querySelectorAll(".cbom-component-card")).toHaveLength(100);
    expect(
      screen.getByText("Total 10,000 · Loaded 100 · Filtered 10,000 · Exported 0"),
    ).toBeInTheDocument();
  });
});

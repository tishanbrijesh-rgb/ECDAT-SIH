import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter } from "react-router-dom";
import { describe, expect, it, vi } from "vitest";
import { getCbom, getEvidenceGraph } from "../api/client";
import CbomPage from "./CbomPage";

vi.mock("../api/client", () => ({
  getCbom: vi.fn(),
  getEvidenceGraph: vi.fn(),
  getRiskReport: vi.fn(),
}));

describe("CbomPage", () => {
  it("shows a completed empty state when the CBOM has no components", async () => {
    vi.mocked(getCbom).mockResolvedValue({
      bom_format: "CycloneDX",
      components: [],
    });
    vi.mocked(getEvidenceGraph).mockResolvedValue({});

    render(
      <MemoryRouter>
        <CbomPage />
      </MemoryRouter>,
    );

    expect(screen.getByText("Building CBOM")).toBeInTheDocument();
    expect(await screen.findByText("No components found")).toBeInTheDocument();
    expect(
      screen.getByText(
        "This scan did not produce any cryptographic components. Run a full discovery scan with dependency analysis enabled.",
      ),
    ).toBeInTheDocument();
  });

  it("reports a CBOM request failure and lets the user retry", async () => {
    vi.mocked(getCbom)
      .mockRejectedValueOnce(new Error("offline"))
      .mockResolvedValueOnce({ bom_format: "CycloneDX", components: [] });
    vi.mocked(getEvidenceGraph).mockResolvedValue({});

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
});

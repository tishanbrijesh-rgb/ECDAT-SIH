import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it } from "vitest";
import { EvidenceChain } from "./EvidenceChain";

describe("EvidenceChain", () => {
  it("deduplicates evidence sources and reveals the supporting records on demand", async () => {
    const user = userEvent.setup();
    render(
      <EvidenceChain
        sources={["ast", "rule", "ast"]}
        evidenceDetails={[
          { algorithm: "RSA", line: 17, call: "KeyPairGenerator.getInstance" },
          { key_size: 2048, pattern: "RSA-2048" },
        ]}
      />,
    );

    expect(screen.getAllByText("ast")).toHaveLength(1);
    expect(screen.queryByText(/KeyPairGenerator/)).not.toBeInTheDocument();

    await user.click(screen.getByRole("button", { name: "2 records — Details" }));
    expect(screen.getByText(/KeyPairGenerator/)).toBeVisible();
    expect(screen.getByText(/RSA-2048/)).toBeVisible();

    await user.click(screen.getByRole("button", { name: "Hide" }));
    expect(screen.queryByText(/KeyPairGenerator/)).not.toBeInTheDocument();
  });

  it("states when a finding has no individual evidence records", () => {
    render(<EvidenceChain sources={["dep"]} evidenceDetails={[]} />);
    expect(screen.getByText(/No individual evidence records/)).toBeVisible();
  });
});

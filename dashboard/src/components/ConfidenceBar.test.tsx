import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import { ConfidenceBar } from "./ConfidenceBar";

describe("ConfidenceBar", () => {
  it.each([
    [0.92, "92% confidence", "conf-high"],
    [0.67, "67% confidence", "conf-mid"],
    [0.3, "30% confidence", "conf-low"],
  ])("presents %s as a labelled severity band", (confidence, label, band) => {
    const { container } = render(<ConfidenceBar confidence={confidence as number} />);
    expect(screen.getByText(label as string)).toBeVisible();
    expect(container.firstChild).toHaveClass(band as string);
  });
});

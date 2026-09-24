import { describe, expect, it } from "vitest";
import { buildMoscaScenarios } from "./mosca";

describe("buildMoscaScenarios", () => {
  it("exposes X, Y, Z and bounded threat-horizon scenarios", () => {
    expect(buildMoscaScenarios(10, 3, 10)).toEqual([
      {
        id: "conservative",
        label: "Conservative estimate",
        x: 10,
        y: 5,
        z: 10,
        gap: 5,
        overlaps: true,
      },
      { id: "baseline", label: "Selected baseline", x: 10, y: 3, z: 10, gap: 3, overlaps: true },
      {
        id: "aggressive",
        label: "Aggressive migration",
        x: 10,
        y: 1,
        z: 10,
        gap: 1,
        overlaps: true,
      },
    ]);
  });
});

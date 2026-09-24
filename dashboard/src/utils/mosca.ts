export type MoscaScenario = {
  id: "conservative" | "baseline" | "aggressive";
  label: string;
  x: number;
  y: number;
  z: number;
  gap: number;
  overlaps: boolean;
};

export function buildMoscaScenarios(x: number, y: number, z: number): MoscaScenario[] {
  const estimates = [
    ["conservative", "Conservative estimate", y + 2],
    ["baseline", "Selected baseline", y],
    ["aggressive", "Aggressive migration", Math.max(1, y - 2)],
  ] as const;

  return estimates.map(([id, label, migrationYears]) => {
    const gap = x + migrationYears - z;
    return { id, label, x, y: migrationYears, z, gap, overlaps: gap >= 0 };
  });
}

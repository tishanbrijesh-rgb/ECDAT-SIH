// src/components/RiskBadge.tsx
// Colored pill badge for risk labels: CRITICAL=red, HIGH=orange,
// MEDIUM=yellow, LOW=green.

import React from "react";

const COLORS: Record<string, { bg: string; text: string }> = {
  CRITICAL: { bg: "#dc2626", text: "#ffffff" },
  HIGH: { bg: "#f97316", text: "#ffffff" },
  MEDIUM: { bg: "#eab308", text: "#1f2937" },
  LOW: { bg: "#22c55e", text: "#ffffff" },
};

interface Props {
  label: string;
  score?: number;
}

export const RiskBadge: React.FC<Props> = ({ label, score }) => {
  const c = COLORS[label] || { bg: "#9ca3af", text: "#fff" };
  return (
    <span
      style={{
        display: "inline-block",
        padding: "3px 10px",
        borderRadius: 14,
        background: c.bg,
        color: c.text,
        fontSize: 12,
        fontWeight: 700,
        letterSpacing: "0.02em",
      }}
      title={score != null ? `Priority score: ${score}` : undefined}
    >
      {label}
      {score != null ? ` (${score})` : ""}
    </span>
  );
};

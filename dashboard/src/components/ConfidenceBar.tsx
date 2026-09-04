// src/components/ConfidenceBar.tsx
// Renders a horizontal bar whose width maps confidence (0–1) to 0–100%,
// color-coded: green > 0.8, yellow 0.5–0.8, red < 0.5.

import React from "react";

interface Props {
  confidence: number;
}

export const ConfidenceBar: React.FC<Props> = ({ confidence }) => {
  const pct = Math.round(confidence * 100);
  const color = confidence > 0.8 ? "#22c55e" : confidence >= 0.5 ? "#eab308" : "#ef4444";

  return (
    <div style={{ width: "100%" }}>
      <div
        style={{
          width: "100%",
          height: 14,
          background: "#e5e7eb",
          borderRadius: 7,
          overflow: "hidden",
        }}
      >
        <div
          style={{
            width: `${pct}%`,
            height: "100%",
            background: color,
            borderRadius: 7,
            transition: "width 0.4s ease",
          }}
        />
      </div>
      <span style={{ fontSize: 12, color: "#6b7280", marginTop: 2, display: "inline-block" }}>
        {pct}%
      </span>
    </div>
  );
};

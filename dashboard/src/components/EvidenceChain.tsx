// src/components/EvidenceChain.tsx
// Renders a row of colored source badges and an expandable accordion
// showing per-source evidence fields.

import React, { useState } from "react";

const SOURCE_COLORS: Record<string, string> = {
  ast: "#3b82f6",
  cert: "#22c55e",
  dep: "#f97316",
  semgrep: "#a855f7",
  binary: "#6b7280",
};

interface EvidenceDetail {
  algorithm?: string;
  call?: string;
  import?: string;
  pattern?: string;
  line?: number;
  package?: string;
  key_size?: number;
  subject_cn?: string;
  [k: string]: unknown;
}

interface Props {
  sources: string[];
  evidenceDetails: EvidenceDetail[];
}

export const EvidenceChain: React.FC<Props> = ({ sources, evidenceDetails = [] }) => {
  const [expanded, setExpanded] = useState(false);

  return (
    <div>
      <div style={{ display: "flex", gap: 6, flexWrap: "wrap", marginBottom: 6 }}>
        {sources.map((src) => (
          <span
            key={src}
            style={{
              display: "inline-block",
              padding: "2px 8px",
              borderRadius: 12,
              background: SOURCE_COLORS[src] || "#9ca3af",
              color: "#fff",
              fontSize: 11,
              fontWeight: 600,
              textTransform: "uppercase",
            }}
          >
            {src}
          </span>
        ))}
        {evidenceDetails.length > 0 && (
          <button
            onClick={() => setExpanded(!expanded)}
            style={{
              background: "none",
              border: "1px solid #d1d5db",
              borderRadius: 12,
              padding: "2px 8px",
              cursor: "pointer",
              fontSize: 11,
            }}
          >
            {expanded ? "Hide" : "Details"}
          </button>
        )}
      </div>
      {expanded && evidenceDetails.length > 0 && (
        <div
          style={{
            border: "1px solid #e5e7eb",
            borderRadius: 6,
            padding: 8,
            background: "#f9fafb",
            fontSize: 12,
            maxHeight: 200,
            overflowY: "auto",
          }}
        >
          {evidenceDetails.map((ev, i) => (
            <pre
              key={i}
              style={{ margin: 0, marginBottom: i < evidenceDetails.length - 1 ? 8 : 0 }}
            >
              {JSON.stringify(ev, null, 2)}
            </pre>
          ))}
        </div>
      )}
    </div>
  );
};

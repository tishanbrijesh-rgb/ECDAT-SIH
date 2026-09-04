// Renders a row of colored source badges and an expandable accordion
// showing per-source evidence fields.
import React, { useState } from "react";

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

const SOURCE_CLASS: Record<string, string> = {
  ast: "badge-ast",
  rule: "badge-rule",
  dep: "badge-dep",
  cert: "badge-cert",
};

export const EvidenceChain: React.FC<Props> = ({ sources, evidenceDetails = [] }) => {
  const [expanded, setExpanded] = useState(false);

  return (
    <div>
      <div className="evidence-chain">
        {sources.map((src) => (
          <span className={`badge ${SOURCE_CLASS[src] || ""}`} key={src}>
            {src}
          </span>
        ))}
        {evidenceDetails.length > 0 && (
          <button className="evidence-toggle" onClick={() => setExpanded(!expanded)}>
            {expanded ? "Hide" : "Details"}
          </button>
        )}
      </div>
      {expanded && evidenceDetails.length > 0 && (
        <div className="evidence-details">
          {evidenceDetails.map((ev, i) => (
            <pre key={i}>{JSON.stringify(ev, null, 2)}</pre>
          ))}
        </div>
      )}
    </div>
  );
};

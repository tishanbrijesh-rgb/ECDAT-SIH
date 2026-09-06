// Renders source badges with expandable evidence details. Shows a summary
// line even when collapsed so empty evidence lists aren't confusing.
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

  const totalRecords = evidenceDetails.length;
  const srcTypes = [...new Set(sources)];

  return (
    <div>
      <div className="evidence-chain">
        {srcTypes.map((src) => (
          <span className={`badge ${SOURCE_CLASS[src] || ""}`} key={src}>
            {src}
          </span>
        ))}
        {totalRecords > 0 && (
          <button className="evidence-toggle" onClick={() => setExpanded(!expanded)}>
            {expanded ? "Hide" : `${totalRecords} record${totalRecords === 1 ? "" : "s"} — Details`}
          </button>
        )}
      </div>
      {!totalRecords && (
        <p className="evidence-empty">No individual evidence records for this finding.</p>
      )}
      {expanded && totalRecords > 0 && (
        <div className="evidence-details">
          {evidenceDetails.map((ev, i) => (
            <pre key={i}>{JSON.stringify(ev, null, 2)}</pre>
          ))}
        </div>
      )}
    </div>
  );
};

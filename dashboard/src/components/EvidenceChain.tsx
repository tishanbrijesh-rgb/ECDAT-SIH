// Renders source badges with expandable evidence details.
// Formats JSON records into readable key-value pairs instead of raw dumps.
import React, { memo, useState } from "react";
import type { CSSProperties, ReactNode } from "react";

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

const VALUE_STYLE: Record<string, CSSProperties> = {
  line: { color: "#6366f1", fontWeight: 600 },
  key_size: { color: "#14b8a6", fontWeight: 600 },
  algorithm: { fontWeight: 600 },
};

function formatValue(key: string, val: unknown): ReactNode {
  if (val == null) return <span style={{ opacity: 0.4 }}>null</span>;
  if (key === "line" || key === "key_size")
    return <span style={VALUE_STYLE[key]}>{String(val)}</span>;
  if (typeof val === "string") return <span>"{val}"</span>;
  if (typeof val === "number") return <span>{val}</span>;
  if (typeof val === "boolean") return <span>{val ? "true" : "false"}</span>;
  return <span>{JSON.stringify(val)}</span>;
}

function EvidenceRecord({ record }: { record: EvidenceDetail }) {
  const keys = Object.keys(record).filter((k) => record[k] != null && record[k] !== "");
  if (keys.length === 0)
    return (
      <pre>
        <em style={{ opacity: 0.5 }}>Empty record</em>
      </pre>
    );
  return (
    <pre>
      {keys.map((k) => (
        <div key={k} style={{ display: "inline" }}>
          <span style={{ opacity: 0.5 }}>{k}: </span>
          {formatValue(k, record[k])}
          {k !== keys[keys.length - 1] && ", "}
        </div>
      ))}
    </pre>
  );
}

export const EvidenceChain = memo(function EvidenceChain({ sources, evidenceDetails = [] }: Props) {
  const [expanded, setExpanded] = useState(false);

  const totalRecords = evidenceDetails.length;
  const srcTypes = [...new Set(sources)];
  const detailsId = `evidence-details-${srcTypes.length}-${totalRecords}`;

  return (
    <div>
      <div className="evidence-chain">
        {srcTypes.map((src) => (
          <span className={`badge ${SOURCE_CLASS[src] || ""}`} key={src}>
            {src}
          </span>
        ))}
        {totalRecords > 0 && (
          <button
            className="evidence-toggle"
            onClick={() => setExpanded(!expanded)}
            aria-expanded={expanded}
            aria-controls={detailsId}
          >
            {expanded ? "Hide" : `${totalRecords} record${totalRecords === 1 ? "" : "s"} — Details`}
          </button>
        )}
      </div>
      {!totalRecords && (
        <p className="evidence-empty">No individual evidence records for this finding.</p>
      )}
      {expanded && totalRecords > 0 && (
        <div id={detailsId} className="evidence-details">
          {evidenceDetails.map((ev, i) => (
            <EvidenceRecord key={i} record={ev} />
          ))}
        </div>
      )}
    </div>
  );
});

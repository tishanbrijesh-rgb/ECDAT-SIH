// Searchable and filterable cryptographic inventory.
import { useEffect, useMemo, useState } from "react";
import { Link, useSearchParams } from "react-router-dom";
import { getAssets, canWrite } from "../api/client";
import { RiskBadge } from "../components/RiskBadge";
import type { CryptoAsset } from "../types";

export default function AssetsPage() {
  const [params] = useSearchParams();
  const scanId = params.get("scan_id");
  const [assets, setAssets] = useState<CryptoAsset[]>([]);
  const [query, setQuery] = useState("");
  const [risk, setRisk] = useState("ALL");
  const [quantum, setQuantum] = useState(false);
  const [error, setError] = useState("");
  const [sortBy, setSortBy] = useState<"priority" | "confidence" | "algorithm">("priority");

  const riskOrder: Record<string, number> = { CRITICAL: 0, HIGH: 1, MEDIUM: 2, LOW: 3 };

  useEffect(() => {
    getAssets(scanId ? Number(scanId) : undefined)
      .then(setAssets)
      .catch((e) => setError(String(e)));
  }, [scanId]);

  const filtered = useMemo(() => {
    let result = assets.filter(
      (a) =>
        (risk === "ALL" || a.priority_label === risk) &&
        (!quantum || a.quantum_vulnerable) &&
        `${a.algorithm} ${a.location} ${a.library} ${a.usage}`
          .toLowerCase()
          .includes(query.toLowerCase()),
    );
    result = [...result].sort((a, b) => {
      if (sortBy === "priority")
        return (
          (riskOrder[a.priority_label] ?? 4) - (riskOrder[b.priority_label] ?? 4) ||
          b.priority_score - a.priority_score
        );
      if (sortBy === "confidence") return b.confidence - a.confidence;
      return a.algorithm.localeCompare(b.algorithm);
    });
    return result;
  }, [assets, query, risk, quantum, sortBy]);

  const filterActive = risk !== "ALL" || quantum || query;

  return (
    <>
      <section className="hero compact">
        <div>
          <p className="eyebrow">Standardized inventory</p>
          <h1>Cryptographic assets</h1>
          <p>
            {filtered.length !== assets.length
              ? `${filtered.length} of ${assets.length} shown`
              : `${assets.length} correlated finding${assets.length === 1 ? "" : "s"}`}
          </p>
        </div>
        {canWrite() && (
          <Link className="button" to="/scan">
            New scan
          </Link>
        )}
      </section>
      <section className="toolbar">
        <input
          aria-label="Search inventory"
          placeholder="Search algorithm, location, library…"
          value={query}
          onChange={(e) => setQuery(e.target.value)}
        />
        <select value={risk} onChange={(e) => setRisk(e.target.value)}>
          <option value="ALL">All risks</option>
          <option value="CRITICAL">Critical</option>
          <option value="HIGH">High</option>
          <option value="MEDIUM">Medium</option>
          <option value="LOW">Low</option>
        </select>
        <label className="check" title="Show only quantum-vulnerable assets">
          <input type="checkbox" checked={quantum} onChange={(e) => setQuantum(e.target.checked)} />
          Quantum vulnerable
        </label>
        <select
          value={sortBy}
          onChange={(e) => setSortBy(e.target.value as typeof sortBy)}
          aria-label="Sort assets"
          style={{ minWidth: 140 }}
        >
          <option value="priority">Sort: Priority</option>
          <option value="confidence">Sort: Confidence</option>
          <option value="algorithm">Sort: Algorithm</option>
        </select>
        {filterActive && (
          <button
            className="button secondary"
            style={{ padding: "11px 14px", fontSize: 13, flexShrink: 0 }}
            onClick={() => {
              setQuery("");
              setRisk("ALL");
              setQuantum(false);
            }}
          >
            Clear
          </button>
        )}
      </section>
      {error && <div className="callout error">{error}</div>}
      <div className="panel table-wrap">
        <table>
          <thead>
            <tr>
              <th>Asset</th>
              <th>Context</th>
              <th>Evidence</th>
              <th>Assurance</th>
              <th>Priority</th>
              <th />
            </tr>
          </thead>
          <tbody>
            {filtered.map((a) => (
              <tr key={a.id}>
                <td>
                  <strong>
                    {a.algorithm}
                    {a.key_size ? `-${a.key_size}` : ""}
                  </strong>
                  <small>
                    {a.category} · {a.usage}
                  </small>
                </td>
                <td>
                  <span className="path">{a.location}</span>
                  <small>{a.library || a.protocol || "Direct source usage"}</small>
                </td>
                <td>
                  <div className="source-row">
                    {a.source.map((s) => (
                      <span className={`source source-${s}`} key={s}>
                        {s}
                      </span>
                    ))}
                  </div>
                  <small>{a.evidence_json.evidence_list?.length || 0} records</small>
                </td>
                <td>
                  <strong>{Math.round(a.confidence * 100)}%</strong>
                  <small>{a.conflict ? "Review conflict" : "Evidence consistent"}</small>
                </td>
                <td>
                  <RiskBadge label={a.priority_label} score={a.priority_score} size="sm" />
                </td>
                <td>
                  <Link className="row-link" to={`/assets/${a.id}`}>
                    Inspect &rarr;
                  </Link>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
        {!filtered.length && !error && (
          <div className="empty-table-msg">
            {filterActive
              ? "No assets match these filters."
              : "No assets found. Run a scan to begin."}
          </div>
        )}
      </div>
    </>
  );
}

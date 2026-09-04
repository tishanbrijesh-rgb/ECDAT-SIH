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
  useEffect(() => {
    getAssets(scanId ? Number(scanId) : undefined)
      .then(setAssets)
      .catch((e) => setError(String(e)));
  }, [scanId]);
  const filtered = useMemo(
    () =>
      assets.filter(
        (a) =>
          (risk === "ALL" || a.priority_label === risk) &&
          (!quantum || a.quantum_vulnerable) &&
          `${a.algorithm} ${a.location} ${a.library} ${a.usage}`
            .toLowerCase()
            .includes(query.toLowerCase()),
      ),
    [assets, query, risk, quantum],
  );
  return (
    <>
      <section className="hero compact">
        <div>
          <p className="eyebrow">Standardized inventory</p>
          <h1>Cryptographic assets</h1>
          <p>
            {filtered.length} of {assets.length} correlated findings
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
          <option>ALL</option>
          <option>CRITICAL</option>
          <option>HIGH</option>
          <option>MEDIUM</option>
          <option>LOW</option>
        </select>
        <label className="check">
          <input type="checkbox" checked={quantum} onChange={(e) => setQuantum(e.target.checked)} />
          Quantum vulnerable only
        </label>
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
                  <RiskBadge label={a.priority_label} score={a.priority_score} />
                </td>
                <td>
                  <Link className="row-link" to={`/assets/${a.id}`}>
                    Inspect →
                  </Link>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
        {!filtered.length && !error && <p className="empty">No assets match these filters.</p>}
      </div>
    </>
  );
}

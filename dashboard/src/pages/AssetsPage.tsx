// Searchable, filterable, paginated cryptographic inventory.
// Filter state is synced to URL search params for shareability.
import { useEffect, useRef, useState, useCallback } from "react";
import { Link, useSearchParams } from "react-router-dom";
import { getAssets, canWrite } from "../api/client";
import { RiskBadge } from "../components/RiskBadge";
import type { CryptoAsset } from "../types";

const PAGE_SIZE_OPTIONS = [25, 50, 100];
const RISK_LABELS = ["CRITICAL", "HIGH", "MEDIUM", "LOW"] as const;
type RiskFilter = (typeof RISK_LABELS)[number] | "ALL";
type SortOption = "priority" | "confidence" | "algorithm";

function readNonNegativeInt(value: string | null, fallback: number) {
  const parsed = Number(value);
  return Number.isInteger(parsed) && parsed >= 0 ? parsed : fallback;
}

export default function AssetsPage() {
  const [params, setParams] = useSearchParams();
  const scanId = params.get("scan_id");
  const page = readNonNegativeInt(params.get("page"), 0);
  const requestedPageSize = readNonNegativeInt(params.get("page_size"), 50);
  const pageSize = PAGE_SIZE_OPTIONS.includes(requestedPageSize) ? requestedPageSize : 50;
  const [query, setQuery] = useState(() => params.get("q") || "");
  const [debouncedQuery, setDebouncedQuery] = useState(query);
  const [risk, setRisk] = useState<RiskFilter>(() => {
    const value = params.get("risk");
    return RISK_LABELS.includes(value as (typeof RISK_LABELS)[number])
      ? (value as RiskFilter)
      : "ALL";
  });
  const [quantum, setQuantum] = useState(() => params.get("quantum") === "1");
  const [sortBy, setSortBy] = useState<SortOption>(() => {
    const value = params.get("sort");
    return value === "confidence" || value === "algorithm" ? value : "priority";
  });
  const [assets, setAssets] = useState<CryptoAsset[]>([]);
  const [total, setTotal] = useState(0);
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(true);

  const syncParams = useCallback(
    (updates: Record<string, string | undefined>) => {
      setParams(
        (prev) => {
          const next = new URLSearchParams(prev);
          for (const [k, v] of Object.entries(updates)) {
            if (v === undefined || v === "" || v === "ALL") next.delete(k);
            else next.set(k, v);
          }
          return next;
        },
        { replace: true },
      );
    },
    [setParams],
  );

  const filterSignature = `${query}\u0000${risk}\u0000${quantum}\u0000${sortBy}`;
  const filterRef = useRef(filterSignature);

  useEffect(() => {
    syncParams({
      q: query || undefined,
      risk: risk === "ALL" ? undefined : risk,
      quantum: quantum ? "1" : undefined,
      sort: sortBy === "priority" ? undefined : sortBy,
    });
  }, [query, risk, quantum, sortBy, syncParams]);

  useEffect(() => {
    if (filterRef.current !== filterSignature) {
      filterRef.current = filterSignature;
      syncParams({ page: undefined });
    }
  }, [filterSignature, syncParams]);

  useEffect(() => {
    const timer = window.setTimeout(() => setDebouncedQuery(query), 250);
    return () => window.clearTimeout(timer);
  }, [query]);

  useEffect(() => {
    const effectiveScanId = scanId ? Number(scanId) : undefined;
    const controller = new AbortController();
    setLoading(true);
    setError("");
    getAssets(effectiveScanId, {
      limit: pageSize,
      offset: page * pageSize,
      query: debouncedQuery,
      risk: risk === "ALL" ? undefined : risk,
      quantum: quantum ? true : undefined,
      sort: sortBy,
      signal: controller.signal,
    })
      .then((result) => {
        const lastPage = Math.max(0, Math.ceil(result.total / pageSize) - 1);
        if (page > lastPage) {
          syncParams({ page: lastPage ? String(lastPage) : undefined });
          return;
        }
        setAssets(result.items);
        setTotal(result.total);
        setLoading(false);
      })
      .catch((e) => {
        if (controller.signal.aborted) return;
        setError(String(e));
        setLoading(false);
      });
    return () => controller.abort();
  }, [scanId, page, pageSize, debouncedQuery, risk, quantum, sortBy, syncParams]);

  const totalPages = Math.max(1, Math.ceil(total / pageSize));
  const hasFilters = risk !== "ALL" || quantum || query;

  const goToPage = useCallback(
    (p: number) => {
      syncParams({ page: String(Math.max(0, p)) });
    },
    [syncParams],
  );

  return (
    <>
      <section className="hero compact">
        <div>
          <p className="eyebrow">Standardized inventory</p>
          <h1>Cryptographic assets</h1>
          <p>{loading ? "Loading…" : `${total} matching finding${total === 1 ? "" : "s"}`}</p>
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
        <select value={risk} onChange={(e) => setRisk(e.target.value as RiskFilter)}>
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
          onChange={(e) => setSortBy(e.target.value as SortOption)}
          aria-label="Sort assets"
          style={{ minWidth: 140 }}
        >
          <option value="priority">Sort: Priority</option>
          <option value="confidence">Sort: Confidence</option>
          <option value="algorithm">Sort: Algorithm</option>
        </select>
        {hasFilters && (
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
      {error && !loading && <div className="callout error">{error}</div>}
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
            {loading
              ? Array.from({ length: pageSize }).map((_, i) => (
                  <tr key={`sk-${i}`}>
                    {Array.from({ length: 6 }).map((_, j) => (
                      <td key={j}>
                        <div
                          className="skeleton"
                          style={{ height: 12, width: j === 0 ? "80%" : "50%" }}
                        />
                      </td>
                    ))}
                  </tr>
                ))
              : assets.map((a) => (
                  <tr key={a.id}>
                    <td>
                      <strong>
                        {a.algorithm}
                        {a.key_size ? `-${a.key_size}` : ""}
                      </strong>
                      <small>
                        {a.category} &middot; {a.usage}
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
            {!loading && !assets.length && (
              <tr>
                <td colSpan={6} className="empty-table-msg">
                  {hasFilters
                    ? "No assets match these filters."
                    : "No assets found. Run a scan to begin."}
                </td>
              </tr>
            )}
          </tbody>
        </table>
      </div>
      {!loading && total > 0 && (
        <PaginationControls
          page={page}
          totalPages={totalPages}
          pageSize={pageSize}
          total={total}
          onPageChange={goToPage}
          onPageSizeChange={(sz) => {
            syncParams({ page_size: String(sz), page: "0" });
          }}
        />
      )}
    </>
  );
}

function PaginationControls({
  page,
  totalPages,
  pageSize,
  total,
  onPageChange,
  onPageSizeChange,
}: {
  page: number;
  totalPages: number;
  pageSize: number;
  total: number;
  onPageChange: (p: number) => void;
  onPageSizeChange: (sz: number) => void;
}) {
  const start = total === 0 ? 0 : page * pageSize + 1;
  const end = Math.min((page + 1) * pageSize, total);

  return (
    <div className="pagination-bar">
      <span className="muted">
        {start}–{end} of {total}
      </span>
      <select
        value={pageSize}
        onChange={(e) => onPageSizeChange(Number(e.target.value))}
        aria-label="Page size"
        className="page-size-select"
      >
        {PAGE_SIZE_OPTIONS.map((sz) => (
          <option value={sz} key={sz}>
            {sz} / page
          </option>
        ))}
      </select>
      <div className="pagination-buttons">
        <button
          className="button secondary"
          disabled={page <= 0}
          onClick={() => onPageChange(page - 1)}
        >
          &larr; Prev
        </button>
        <span>
          {page + 1} / {totalPages}
        </span>
        <button
          className="button secondary"
          disabled={page >= totalPages - 1}
          onClick={() => onPageChange(page + 1)}
        >
          Next &rarr;
        </button>
      </div>
    </div>
  );
}

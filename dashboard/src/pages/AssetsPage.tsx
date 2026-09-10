// Searchable, filterable, paginated cryptographic inventory.
// Filter state is synced to URL search params for shareability.
import { useEffect, useRef, useState, useCallback } from "react";
import { Link, useSearchParams } from "react-router-dom";
import { motion } from "framer-motion";
import { getAssets, canWrite } from "../api/client";
import { RiskBadge } from "../components/RiskBadge";
import { highlightText } from "../utils/format";
import type { CryptoAsset } from "../types";

// ── Stagger variants ───────────────────────────────────────────
const staggerContainer = {
  animate: { transition: { staggerChildren: 0.04 } },
};
const staggerItem = {
  initial: { opacity: 0, y: 8 },
  animate: { opacity: 1, y: 0, transition: { duration: 0.25, ease: [0.25, 0.1, 0.25, 1] } },
};

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
          <p aria-live="polite" aria-atomic="true">
            {loading ? "Loading…" : `${total} matching finding${total === 1 ? "" : "s"}`}
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
        <select
          value={risk}
          onChange={(e) => setRisk(e.target.value as RiskFilter)}
          aria-label="Filter by risk level"
        >
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
      {error && !loading && (
        <div className="callout error" role="alert">
          {error}
        </div>
      )}
      <div className="panel table-wrap" role="region" aria-label="Cryptographic assets table">
        <table role="grid" aria-rowcount={Math.max(total, pageSize) + 1}>
          <thead>
            <tr>
              <th scope="col">Asset</th>
              <th scope="col">Context</th>
              <th scope="col">Evidence</th>
              <th scope="col">Assurance</th>
              <th scope="col">Priority</th>
              <th scope="col" />
            </tr>
          </thead>
          <motion.tbody variants={staggerContainer} initial="initial" animate="animate">
            {loading
              ? Array.from({ length: pageSize }).map((_, i) => (
                  <tr key={`sk-${i}`} aria-rowindex={page * pageSize + i + 2}>
                    {Array.from({ length: 6 }).map((_, j) => (
                      <td key={j} aria-colindex={j + 1}>
                        <div
                          className="skeleton"
                          style={{ height: 12, width: j === 0 ? "80%" : "50%" }}
                        />
                      </td>
                    ))}
                  </tr>
                ))
              : assets.map((a, rowIndex) => (
                  <motion.tr
                    key={a.id}
                    variants={staggerItem}
                    aria-rowindex={page * pageSize + rowIndex + 2}
                  >
                    <td aria-colindex={1} data-label="Asset">
                      <strong
                        dangerouslySetInnerHTML={{
                          __html: highlightText(
                            a.algorithm + (a.key_size ? `-${a.key_size}` : ""),
                            query,
                          ),
                        }}
                      />
                      <small>
                        {a.category} ·{" "}
                        <span dangerouslySetInnerHTML={{ __html: highlightText(a.usage, query) }} />
                      </small>
                    </td>
                    <td aria-colindex={2} data-label="Context">
                      <span
                        className="path"
                        dangerouslySetInnerHTML={{ __html: highlightText(a.location, query) }}
                      />
                      <small>{a.library || a.protocol || "Direct source usage"}</small>
                    </td>
                    <td aria-colindex={3} data-label="Evidence">
                      <div className="source-row">
                        {a.source.map((s) => (
                          <span className={`source source-${s}`} key={s}>
                            {s}
                          </span>
                        ))}
                      </div>
                      <small>{a.evidence_json.evidence_list?.length || 0} records</small>
                    </td>
                    <td aria-colindex={4} data-label="Assurance">
                      <strong>{Math.round(a.confidence * 100)}%</strong>
                      <small>{a.conflict ? "Review conflict" : "Evidence consistent"}</small>
                    </td>
                    <td aria-colindex={5} data-label="Priority">
                      <RiskBadge label={a.priority_label} score={a.priority_score} size="sm" />
                    </td>
                    <td aria-colindex={6} data-label="Action">
                      <Link className="row-link" to={`/assets/${a.id}`}>
                        Inspect &rarr;
                      </Link>
                    </td>
                  </motion.tr>
                ))}
            {!loading && !assets.length && (
              <tr>
                <td colSpan={6} className="empty-table-msg">
                  <span className="empty-data-icon">&#9632;</span>
                  <strong>
                    {hasFilters ? "No assets match these filters" : "No assets found"}
                  </strong>
                  <span>
                    {hasFilters
                      ? "Try adjusting your search or risk filter to see results."
                      : "Run a discovery scan to build your cryptographic inventory."}
                  </span>
                </td>
              </tr>
            )}
          </motion.tbody>
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
    <nav className="pagination-bar" aria-label="Pagination">
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
    </nav>
  );
}

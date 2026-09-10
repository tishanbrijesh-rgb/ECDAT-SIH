// Scan detail — full job metrics, evidence summary, asset breakdown.
import { useState, useEffect, useMemo } from "react";
import { Link, useParams } from "react-router-dom";
import { motion } from "framer-motion";
import { getScanDetail, downloadCsv, subscribeScanEvents } from "../api/client";
import { RiskBadge } from "../components/RiskBadge";
import { formatDate } from "../utils/format";
import type { ScanDetail } from "../types";

// ── Stagger variants ───────────────────────────────────────────
const staggerContainer = {
  animate: { transition: { staggerChildren: 0.05, delayChildren: 0.05 } },
};
const staggerItem = {
  initial: { opacity: 0, y: 10 },
  animate: { opacity: 1, y: 0, transition: { duration: 0.3, ease: [0.25, 0.1, 0.25, 1] } },
};

function formatDuration(ms: number): string {
  if (ms < 1000) return `${ms} ms`;
  const s = Math.floor(ms / 1000);
  if (s < 60) return `${s} s`;
  const m = Math.floor(s / 60);
  const rem = s % 60;
  return rem ? `${m}m ${rem}s` : `${m}m`;
}

const STATUS_CLASS: Record<string, string> = {
  completed: "status-completed",
  failed: "status-failed",
  running: "status-running",
  cancelled: "status-cancelled",
  timed_out: "status-timed_out",
  queued: "status-running",
};

const FAILURE_LABELS: Record<string, string> = {
  unreadable: "Unreadable file",
  oversized: "File too large",
  linked_file: "Linked file",
  parse_error: "Parse error",
  certificate_error: "Certificate error",
};

export default function ScanDetailPage() {
  const { id } = useParams();
  const [detail, setDetail] = useState<ScanDetail | null>(null);
  const [error, setError] = useState("");
  const [exporting, setExporting] = useState(false);

  useEffect(() => {
    setDetail(null);
    setError("");
    if (!id || !/^\d+$/.test(id) || !Number.isSafeInteger(Number(id)) || Number(id) <= 0) {
      setError("Invalid scan ID.");
      return;
    }
    let cancelled = false;
    let unsubscribe: (() => void) | undefined;
    const numericId = Number(id);

    getScanDetail(numericId)
      .then((d) => {
        if (cancelled) return;
        setDetail(d);
        if (
          d.status === "completed" ||
          d.status === "failed" ||
          d.status === "cancelled" ||
          d.status === "timed_out"
        ) {
          return;
        }
        unsubscribe = subscribeScanEvents(
          numericId,
          (event) => {
            if (!cancelled) {
              setDetail((prev) => {
                if (!prev) return prev;
                return {
                  ...prev,
                  status: event.status,
                  collector_stats: event.collector_stats,
                  assets_found: event.assets_found,
                  coverage_pct: event.coverage_pct,
                  duration_ms: event.duration_ms,
                };
              });
            }
          },
          (final) => {
            if (!cancelled) {
              setDetail((prev) => {
                if (!prev) return prev;
                return {
                  ...prev,
                  status: final.status,
                  assets_found: final.assets_found,
                  coverage_pct: final.coverage_pct,
                  duration_ms: final.duration_ms,
                };
              });
            }
          },
          () => {
            if (!cancelled) setDetail((prev) => prev);
          },
        );
      })
      .catch((e) => {
        if (!cancelled) setError(String(e));
      });

    return () => {
      cancelled = true;
      unsubscribe?.();
    };
  }, [id]);

  const riskCounts = useMemo(() => {
    const counts: Record<string, number> = {};
    detail?.assets.forEach((asset) => {
      counts[asset.priority_label] = (counts[asset.priority_label] || 0) + 1;
    });
    return counts;
  }, [detail?.assets]);

  const hasMoreAssets = detail ? detail.assets_total > detail.assets.length : false;

  const handleExport = async () => {
    if (!detail) return;
    setExporting(true);
    try {
      const rows = detail.assets.map((a) => ({
        id: a.id,
        algorithm: a.algorithm,
        category: a.category,
        location: a.location,
        confidence: Math.round(a.confidence * 100),
        priority: a.priority_label,
        score: a.priority_score,
        quantum: a.quantum_vulnerable ? "Yes" : "No",
        sources: a.source.join("; "),
      }));
      const columns = [
        "id",
        "algorithm",
        "category",
        "location",
        "confidence",
        "priority",
        "score",
        "quantum",
        "sources",
      ];
      await downloadCsv(`scan-${detail.id}-assets.csv`, rows, columns);
    } catch {
      setError("Failed to export CSV.");
    } finally {
      setExporting(false);
    }
  };

  if (error)
    return (
      <div className="callout error" role="alert">
        {error}
      </div>
    );
  if (!detail) {
    return (
      <div className="state">
        <span className="spinner" />
        <h1>Loading scan detail</h1>
        <p>Fetching scan job and asset results…</p>
      </div>
    );
  }

  return (
    <>
      <section className="hero compact">
        <div>
          <p className="eyebrow">Scan detail</p>
          <h1>Scan #{detail.id}</h1>
          <p>
            {detail.repo_path} &middot;{" "}
            <span className={`status ${STATUS_CLASS[detail.status] || ""}`}>{detail.status}</span>{" "}
            &middot;
            {formatDuration(detail.duration_ms)}
          </p>
        </div>
        <div className="hero-actions">
          {detail.status === "completed" && (
            <button className="button secondary" disabled={exporting} onClick={handleExport}>
              {exporting ? "Exporting…" : "Export displayed CSV"}
            </button>
          )}
          <Link className="button" to={`/assets?scan_id=${detail.id}`}>
            View all assets
          </Link>
        </div>
      </section>

      <motion.section
        className="stats six"
        variants={staggerContainer}
        initial="initial"
        animate="animate"
      >
        <motion.div variants={staggerItem}>
          <Stat label="Assets found" value={detail.assets_found} tone="blue" />
        </motion.div>
        <motion.div variants={staggerItem}>
          <Stat label="Scanned" value={detail.scanned_files} tone="teal" />
        </motion.div>
        <motion.div variants={staggerItem}>
          <Stat label="Coverage" value={`${detail.coverage_pct}%`} tone="teal" />
        </motion.div>
        <motion.div variants={staggerItem}>
          <Stat
            label="Confidence"
            value={`${detail.avg_confidence ? Math.round(detail.avg_confidence * 100) : 0}%`}
            tone={detail.avg_confidence != null && detail.avg_confidence >= 0.8 ? "teal" : "amber"}
          />
        </motion.div>
        <motion.div variants={staggerItem}>
          <Stat
            label="Conflicts"
            value={detail.assets.filter((a) => a.conflict).length}
            tone="red"
          />
        </motion.div>
        <motion.div variants={staggerItem}>
          <Stat
            label="Quantum exposed"
            value={detail.assets.filter((a) => a.quantum_vulnerable).length}
            tone="amber"
          />
        </motion.div>
      </motion.section>

      <motion.section
        className="dashboard-grid"
        variants={staggerContainer}
        initial="initial"
        animate="animate"
      >
        <motion.article
          className="panel"
          variants={staggerItem}
          initial="initial"
          animate="animate"
        >
          <div className="panel-title">
            <h2>Job metrics</h2>
            <p>Scan execution details</p>
          </div>
          <div className="scan-detail-facts">
            <Fact label="Repository" value={detail.repo_path} />
            <Fact label="Status" value={detail.status} />
            <Fact label="Duration" value={formatDuration(detail.duration_ms)} />
            <Fact label="Total files" value={String(detail.total_files)} />
            <Fact label="In scope" value={String(detail.in_scope_files)} />
            <Fact label="Scanned" value={String(detail.scanned_files)} />
            <Fact label="Failed" value={String(detail.failed_files)} />
            {detail.started_at && <Fact label="Started" value={formatDate(detail.started_at)} />}
            {detail.finished_at && <Fact label="Finished" value={formatDate(detail.finished_at)} />}
          </div>
        </motion.article>

        <motion.article
          className="panel"
          variants={staggerItem}
          initial="initial"
          animate="animate"
        >
          <div className="panel-title">
            <h2>Risk breakdown</h2>
            <p>Assets by priority level</p>
          </div>
          {["CRITICAL", "HIGH", "MEDIUM", "LOW"].map((label) => (
            <div key={label} className="scan-risk-row">
              <RiskBadge label={label} score={undefined} />
              <span className="scan-risk-count">{riskCounts[label] || 0}</span>
            </div>
          ))}
        </motion.article>

        <motion.article
          className="panel"
          variants={staggerItem}
          initial="initial"
          animate="animate"
        >
          <div className="panel-title">
            <h2>Collector output</h2>
            <p>Independent evidence records</p>
          </div>
          <motion.div
            className="collector-list"
            variants={staggerContainer}
            initial="initial"
            animate="animate"
          >
            {Object.entries(detail.collector_stats).map(([label, count]) => (
              <motion.div key={label} variants={staggerItem}>
                <span>{label.toUpperCase()}</span>
                <strong>{count}</strong>
                <i
                  style={{
                    width: `${Math.min(100, (count / Math.max(1, detail.scanned_files)) * 100)}%`,
                  }}
                />
              </motion.div>
            ))}
          </motion.div>
        </motion.article>

        <motion.article
          className="panel span-2"
          variants={staggerItem}
          initial="initial"
          animate="animate"
        >
          <div className="panel-title">
            <h2>
              Assets ({detail.assets.length}
              {hasMoreAssets ? ` of ${detail.assets_total}` : ""})
            </h2>
            <p>Cryptographic findings from this scan</p>
          </div>
          {hasMoreAssets && (
            <div className="callout callout-amber">
              This detail view is limited to the first 200 findings to stay responsive. Use the
              paginated <Link to={`/assets?scan_id=${detail.id}`}>inventory</Link> to inspect all{" "}
              {detail.assets_total} assets.
            </div>
          )}
          {detail.assets.length === 0 ? (
            <p className="muted">No assets found in this scan.</p>
          ) : (
            <div className="table-wrap">
              <table>
                <thead>
                  <tr>
                    <th scope="col">Algorithm</th>
                    <th scope="col">Location</th>
                    <th scope="col">Evidence</th>
                    <th scope="col">Confidence</th>
                    <th scope="col">Priority</th>
                    <th scope="col" />
                  </tr>
                </thead>
                <motion.tbody variants={staggerContainer} initial="initial" animate="animate">
                  {detail.assets.map((a) => (
                    <motion.tr key={a.id} variants={staggerItem}>
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
                      </td>
                      <td>
                        <div className="source-row">
                          {a.source.map((s) => (
                            <span className={`source source-${s}`} key={s}>
                              {s}
                            </span>
                          ))}
                        </div>
                      </td>
                      <td>
                        <strong>{Math.round(a.confidence * 100)}%</strong>
                        <small>{a.conflict ? "Review conflict" : "Consistent"}</small>
                      </td>
                      <td>
                        <RiskBadge label={a.priority_label} score={a.priority_score} size="sm" />
                      </td>
                      <td>
                        <Link className="row-link" to={`/assets/${a.id}`}>
                          Inspect &rarr;
                        </Link>
                      </td>
                    </motion.tr>
                  ))}
                </motion.tbody>
              </table>
            </div>
          )}
        </motion.article>

        {detail.failures && detail.failures.length > 0 && (
          <motion.article
            className="panel span-2 scan-failures"
            variants={staggerItem}
            initial="initial"
            animate="animate"
          >
            <div className="panel-title">
              <h2>Failed files</h2>
              <p>Safe relative paths and controlled failure categories</p>
            </div>
            <motion.ul
              className="scan-failure-list"
              variants={staggerContainer}
              initial="initial"
              animate="animate"
            >
              {detail.failures.map((failure) => (
                <motion.li key={`${failure.path}:${failure.reason}`} variants={staggerItem}>
                  <span className="path">{failure.path}</span>
                  <span className="status status-failed">
                    {FAILURE_LABELS[failure.reason] || "Processing error"}
                  </span>
                </motion.li>
              ))}
            </motion.ul>
          </motion.article>
        )}

        {detail.blind_spots.length > 0 && (
          <motion.article
            className="panel span-2 blind"
            variants={staggerItem}
            initial="initial"
            animate="animate"
          >
            <div className="panel-title">
              <h2>Blind spots</h2>
              <p>Areas outside this scan's measured scope</p>
            </div>
            <motion.div
              className="gap-list"
              variants={staggerContainer}
              initial="initial"
              animate="animate"
            >
              {detail.blind_spots.map((gap, i) => (
                <motion.div key={gap} variants={staggerItem}>
                  <span>{i + 1}</span>
                  <p>{gap}</p>
                </motion.div>
              ))}
            </motion.div>
          </motion.article>
        )}
      </motion.section>
    </>
  );
}

function Stat({ label, value, tone }: { label: string; value: string | number; tone?: string }) {
  return (
    <article className={`stat tone-${tone || "blue"}`}>
      <span>{label}</span>
      <strong>{value}</strong>
    </article>
  );
}

function Fact({ label, value }: { label: string; value: string }) {
  return (
    <div className="scan-fact">
      <span className="scan-fact-label">{label}</span>
      <span className="scan-fact-value">{value}</span>
    </div>
  );
}

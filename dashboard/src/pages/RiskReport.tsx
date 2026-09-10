// Structured risk report viewer — migration priorities, distribution, blind spots.
import { lazy, Suspense, useMemo, useState, useEffect } from "react";
import { useSearchParams } from "react-router-dom";
import { motion } from "framer-motion";
import { getRiskReport, getEvaluation } from "../api/client";
import type { RiskLabel } from "../types";

// ── Stagger variants ───────────────────────────────────────────
const staggerContainer = {
  animate: { transition: { staggerChildren: 0.04, delayChildren: 0.05 } },
};
const staggerItem = {
  initial: { opacity: 0, y: 8 },
  animate: { opacity: 1, y: 0, transition: { duration: 0.25, ease: [0.25, 0.1, 0.25, 1] } },
};

const RiskDistributionChart = lazy(() => import("../components/RiskDistributionChart"));

const LABEL_ORDER: RiskLabel[] = ["CRITICAL", "HIGH", "MEDIUM", "LOW"];

export default function RiskReportPage() {
  const [params] = useSearchParams();
  const scanId = params.get("scan_id") ? Number(params.get("scan_id")) : undefined;

  const [report, setReport] = useState<import("../types").RiskReport | null>(null);
  const [evaluation, setEvaluation] = useState<import("../types").Evaluation | null>(null);
  const [error, setError] = useState("");

  useEffect(() => {
    let cancelled = false;
    Promise.all([getRiskReport(scanId), getEvaluation(scanId).catch(() => null)])
      .then(([r, ev]) => {
        if (cancelled) return;
        setReport(r);
        setEvaluation(ev);
      })
      .catch((e) => {
        if (!cancelled) setError(String(e));
      });
    return () => {
      cancelled = true;
    };
  }, [scanId]);

  const sorted = useMemo(
    () => [...(report?.migration_priorities ?? [])].sort((a, b) => b.score - a.score),
    [report?.migration_priorities],
  );

  if (error)
    return (
      <div className="callout error" role="alert">
        {error}
      </div>
    );
  if (!report) {
    return (
      <div className="state">
        <span className="spinner" />
        <h1>Building risk view</h1>
        <p>Loading migration priorities and coverage data…</p>
      </div>
    );
  }

  const distribution = LABEL_ORDER.map((label) => ({
    label,
    count: (report.migration_priorities ?? []).filter((p) => p.label === label).length,
  }));
  const visiblePriorities = sorted.slice(0, 250);

  return (
    <>
      <section className="hero compact">
        <div>
          <p className="eyebrow">Migration roadmap</p>
          <h1>{report.title || "Risk report"}</h1>
          <p>
            {report.repository || "Current repository"} &middot; Scan #{report.scan_id} &middot;
            {report.coverage_pct}% coverage
          </p>
        </div>
      </section>

      <motion.section
        className="dashboard-grid"
        variants={staggerContainer}
        initial="initial"
        animate="animate"
      >
        <motion.article variants={staggerItem} className="panel span-2">
          <PanelTitle title="Risk distribution" sub="Assets sorted by migration urgency" />
          <Suspense fallback={<div className="skeleton" style={{ height: 250 }} />}>
            <RiskDistributionChart data={distribution} />
          </Suspense>
        </motion.article>

        <motion.article variants={staggerItem} className="panel">
          <div className="panel-title">
            <h2>Evaluation</h2>
            {evaluation?.available && (
              <p>
                Precision {Math.round((evaluation.precision ?? 0) * 100)}% &middot; Recall{" "}
                {Math.round((evaluation.recall ?? 0) * 100)}% &middot; F1{" "}
                {Math.round((evaluation.f1 ?? 0) * 100)}%
              </p>
            )}
          </div>
          {evaluation?.available ? (
            <div className="metric-grid">
              <MetricBlock
                label="Precision"
                raw={
                  evaluation.precision != null ? `${Math.round(evaluation.precision * 100)}%` : "—"
                }
              />
              <MetricBlock
                label="Recall"
                raw={evaluation.recall != null ? `${Math.round(evaluation.recall * 100)}%` : "—"}
              />
              <MetricBlock
                label="F1"
                raw={evaluation.f1 != null ? `${Math.round(evaluation.f1 * 100)}%` : "—"}
              />
              <MetricBlock label="Duration" raw={`${evaluation.duration_ms ?? 0} ms`} />
            </div>
          ) : (
            <p className="muted">Run a scan to calculate precision and recall.</p>
          )}
        </motion.article>

        <motion.article variants={staggerItem} className="panel span-2">
          <div className="panel-title">
            <h2>Migration priorities</h2>
            <p>
              {sorted.length > visiblePriorities.length
                ? `Showing the top ${visiblePriorities.length} of ${sorted.length} assets`
                : `${sorted.length} assets ranked by risk score`}
            </p>
          </div>
          <div className="table-wrap">
            <table>
              <thead>
                <tr>
                  <th scope="col">Algorithm</th>
                  <th scope="col">Location</th>
                  <th scope="col">Score</th>
                  <th scope="col">Level</th>
                  <th scope="col">Hybrid</th>
                  <th scope="col">Recommendation</th>
                </tr>
              </thead>
              <motion.tbody variants={staggerContainer} initial="initial" animate="animate">
                {visiblePriorities.map((p) => (
                  <motion.tr key={p.asset_id} variants={staggerItem}>
                    <td>
                      <strong>{p.algorithm}</strong>
                      <small>Asset #{p.asset_id}</small>
                    </td>
                    <td>
                      <span className="path">{p.location}</span>
                    </td>
                    <td>
                      <strong>{p.score}</strong>
                    </td>
                    <td>
                      <RiskLevelBadge label={p.label} />
                    </td>
                    <td>{p.hybrid ? "Yes" : "No"}</td>
                    <td>{p.recommendation}</td>
                  </motion.tr>
                ))}
                {!sorted.length && (
                  <tr>
                    <td colSpan={6} className="empty-table-msg">
                      <span className="empty-data-icon">&#9632;</span>
                      <strong>No migration priorities in this report</strong>
                      <span>
                        This report will surface migration priorities once assets with cryptographic
                        exposure are detected.
                      </span>
                    </td>
                  </tr>
                )}
              </motion.tbody>
            </table>
          </div>
        </motion.article>

        {report.blind_spots?.length > 0 && (
          <motion.article variants={staggerItem} className="panel span-2 blind">
            <div className="panel-title">
              <h2>Visibility gaps</h2>
              <p>Surfaces outside this scan's measured scope</p>
            </div>
            <motion.div
              className="gap-list"
              variants={staggerContainer}
              initial="initial"
              animate="animate"
            >
              {report.blind_spots.map((gap, i) => (
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

function PanelTitle({ title, sub }: { title: string; sub: string }) {
  return (
    <div className="panel-title">
      <h2>{title}</h2>
      <p>{sub}</p>
    </div>
  );
}

function MetricBlock({ label, raw }: { label: string; raw: string }) {
  return (
    <div>
      <strong>{raw}</strong>
      <span>{label}</span>
    </div>
  );
}

function RiskLevelBadge({ label }: { label: RiskLabel }) {
  const cls: Record<string, string> = {
    CRITICAL: "risk-critical",
    HIGH: "risk-high",
    MEDIUM: "risk-medium",
    LOW: "risk-low",
  };
  return (
    <span className={`risk-badge risk-badge-sm ${cls[label] || ""}`}>
      <span className="dot" />
      {label}
    </span>
  );
}

// Portfolio posture, assurance measurements, and research evaluation.
import { lazy, Suspense, useEffect, useState, useRef, useMemo, memo, type ReactNode } from "react";
import { Link, useSearchParams } from "react-router-dom";
import { motion, type Variants } from "framer-motion";
import { downloadReport, getDashboardSummary, getEvaluation, canWrite } from "../api/client";
import type { DashboardSummary, Evaluation } from "../types";

// ── Stagger animation variants ──────────────────────────────────
const staggerContainer = {
  animate: {
    transition: { staggerChildren: 0.06, delayChildren: 0.05 },
  },
} satisfies Variants;

const listStagger = {
  animate: {
    transition: { staggerChildren: 0.04 },
  },
} satisfies Variants;

const staggerItem = {
  initial: { opacity: 0, y: 14 },
  animate: {
    opacity: 1,
    y: 0,
    transition: { duration: 0.35, ease: [0.25, 0.1, 0.25, 1] },
  },
} satisfies Variants;

const RiskDistributionChart = lazy(() => import("../components/RiskDistributionChart"));

// Animated number that counts up from 0 to the target value.
// Memoized so parent Dashboard doesn't re-render every frame.
const AnimatedNumber = memo(function AnimatedNumber({
  value,
  suffix = "",
}: {
  value: number;
  suffix?: string;
}) {
  const [display, setDisplay] = useState(0);
  const rafRef = useRef<number>(0);
  const fromRef = useRef(0);

  useEffect(() => {
    if (window.matchMedia("(prefers-reduced-motion: reduce)").matches) {
      setDisplay(value);
      fromRef.current = value;
      return;
    }
    const target = value;
    const duration = 600;
    const start = performance.now();
    fromRef.current = display;
    const from = fromRef.current;
    const step = (now: number) => {
      const t = Math.min(1, (now - start) / duration);
      const eased = 1 - Math.pow(1 - t, 3);
      setDisplay(Math.round(from + (target - from) * eased));
      if (t < 1) rafRef.current = requestAnimationFrame(step);
    };
    rafRef.current = requestAnimationFrame(step);
    return () => cancelAnimationFrame(rafRef.current);
  }, [value]);
  return (
    <>
      {display}
      {suffix}
    </>
  );
});

export default function Dashboard() {
  const [summary, setSummary] = useState<DashboardSummary>();
  const [evaluation, setEvaluation] = useState<Evaluation>();
  const [error, setError] = useState("");
  const [downloadError, setDownloadError] = useState("");
  const [sending, setSending] = useState<string>("");
  const [searchParams, setSearchParams] = useSearchParams();
  const rawScanId = searchParams.get("scan_id");
  const scanId = rawScanId && /^\d+$/.test(rawScanId) ? Number(rawScanId) : undefined;
  useEffect(() => {
    let cancelled = false;
    setSummary(undefined);
    setEvaluation(undefined);
    setError("");
    setDownloadError("");
    Promise.all([getDashboardSummary(scanId), getEvaluation(scanId).catch(() => undefined)])
      .then(([s, e]) => {
        if (cancelled) return;
        setSummary(s);
        setEvaluation(e);
      })
      .catch((e) => {
        if (!cancelled) setError(String(e));
      });
    return () => {
      cancelled = true;
    };
  }, [scanId]);
  const clearScanFilter = () => {
    const next = new URLSearchParams(searchParams);
    next.delete("scan_id");
    setSearchParams(next, { replace: true });
  };
  const risk = useMemo(
    () =>
      ["CRITICAL", "HIGH", "MEDIUM", "LOW"].map((label) => ({
        label,
        count:
          summary?.risk_distribution[label as keyof DashboardSummary["risk_distribution"]] || 0,
      })),
    [summary?.risk_distribution],
  );
  const collectors = useMemo(
    () =>
      Object.entries(summary?.collector_stats ?? {}).map(([label, count]) => ({
        label: label.toUpperCase(),
        count,
      })),
    [summary?.collector_stats],
  );
  if (error) return <State title="Dashboard unavailable" body={error} />;
  if (!summary)
    return (
      <State
        title="Building assurance view"
        body="Loading inventory, risk, and evidence metrics…"
      />
    );
  if (!summary.latest_scan_id) {
    if (scanId) {
      return (
        <State
          title="Scan not found"
          body={`Scan #${scanId} was not found or has not completed yet.`}
        />
      );
    }
    return <Empty />;
  }

  const confidencePct = Math.round(summary.avg_confidence * 100);
  const scanQuery = scanId ? `?scan_id=${scanId}` : "";

  // Build a confidence indicator color for the conf stat
  const confTone = confidencePct >= 80 ? "teal" : confidencePct >= 50 ? "amber" : "red";

  return (
    <>
      {scanId && (
        <div className="scan-filter-banner">
          <span>Viewing results from scan #{scanId}</span>
          <button
            className="button secondary"
            onClick={clearScanFilter}
            style={{ padding: "4px 12px", fontSize: 12 }}
          >
            Show latest
          </button>
        </div>
      )}
      <motion.section
        className="hero"
        initial={{ opacity: 0, y: 18 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ duration: 0.5, ease: [0.25, 0.1, 0.25, 1] }}
      >
        <div>
          <p className="eyebrow">Enterprise posture</p>
          <h1>Cryptographic assurance overview</h1>
          <p>
            Measured discovery coverage, evidence strength, quantum exposure, and migration
            priority.
          </p>
        </div>
        <div className="hero-actions">
          <button
            className="button secondary"
            disabled={sending !== ""}
            onClick={() => {
              setDownloadError("");
              setSending("risk");
              downloadReport(
                `/api/reports/risk.txt${scanQuery}`,
                scanId ? `ecdat-risk-report-scan-${scanId}.txt` : "ecdat-risk-report.txt",
              )
                .catch((e) => setDownloadError(String(e)))
                .finally(() => setSending(""));
            }}
          >
            {sending === "risk" ? "Preparing…" : "Download risk report"}
          </button>
          <Link className="button" to={`/cbom${scanQuery}`}>
            View CBOM
          </Link>
        </div>
      </motion.section>
      {downloadError && (
        <div className="callout error" role="alert">
          {downloadError}
        </div>
      )}
      <motion.section
        className="stats six"
        variants={staggerContainer}
        initial="initial"
        animate="animate"
      >
        <motion.div variants={staggerItem}>
          <Stat
            label="Assets"
            value={<AnimatedNumber value={summary.total_assets} />}
            note="correlated findings"
            tone="blue"
          />
        </motion.div>
        <motion.div variants={staggerItem}>
          <Stat
            label="High risk"
            value={<AnimatedNumber value={summary.high_risk_count} />}
            note="critical + high"
            tone="red"
          />
        </motion.div>
        <motion.div variants={staggerItem}>
          <Stat
            label="Quantum exposed"
            value={<AnimatedNumber value={summary.quantum_vulnerable_count} />}
            note="public-key assets"
            tone="amber"
          />
        </motion.div>
        <motion.div variants={staggerItem}>
          <Stat
            label="Confidence"
            value={`${confidencePct}%`}
            note="average evidence score"
            tone={confTone}
          />
        </motion.div>
        <motion.div variants={staggerItem}>
          <Stat
            label="Coverage"
            value={`${summary.coverage_pct}%`}
            note="supported files scanned"
            tone="teal"
          />
        </motion.div>
        <motion.div variants={staggerItem}>
          <Stat
            label="Conflicts"
            value={<AnimatedNumber value={summary.conflict_count} />}
            note="operation-level contradictions"
            tone="violet"
          />
        </motion.div>
      </motion.section>
      <motion.section
        className="dashboard-grid"
        variants={staggerContainer}
        initial="initial"
        animate="animate"
      >
        <motion.div variants={staggerItem} className="panel span-2">
          <PanelTitle
            title="Risk distribution"
            sub="Migration urgency across the latest inventory"
          />
          <Suspense fallback={<div className="skeleton" style={{ height: 270 }} />}>
            <RiskDistributionChart data={risk} />
          </Suspense>
        </motion.div>
        <motion.div variants={staggerItem} className="panel">
          <PanelTitle title="Evidence collectors" sub="Independent records supporting findings" />
          <motion.div
            className="collector-list"
            variants={listStagger}
            initial="initial"
            animate="animate"
          >
            {collectors.length === 0 && (
              <motion.p variants={staggerItem} className="muted" style={{ padding: "10px 0" }}>
                No collector data available.
              </motion.p>
            )}
            {collectors.map((c) => (
              <motion.div key={c.label} variants={staggerItem}>
                <span>{c.label}</span>
                <strong>{c.count}</strong>
                <i style={{ width: `${Math.min(100, c.count * 3)}%` }} />
              </motion.div>
            ))}
          </motion.div>
        </motion.div>
        <motion.div variants={staggerItem} className="panel">
          <PanelTitle
            title="Research evaluation"
            sub="Controlled component/algorithm pairs—not operation-level or real-world accuracy"
          />
          {evaluation?.available ? (
            <div className="metric-grid">
              <Metric label="Precision" value={evaluation.precision} />
              <Metric label="Recall" value={evaluation.recall} />
              <Metric label="F1 score" value={evaluation.f1} />
              <Metric label="Duration" raw={`${evaluation.duration_ms} ms`} />
            </div>
          ) : (
            <p className="muted">
              Run the bundled test repository to calculate precision and recall.
            </p>
          )}
        </motion.div>
        <motion.div variants={staggerItem} className="panel span-2 blind">
          <PanelTitle
            title="Visibility gaps"
            sub="Explicit uncertainty—not a false claim of completeness"
          />
          <motion.div
            className="gap-list"
            variants={listStagger}
            initial="initial"
            animate="animate"
          >
            {summary.blind_spots.map((gap, i) => (
              <motion.div key={gap} variants={staggerItem}>
                <span>{i + 1}</span>
                <p>{gap}</p>
              </motion.div>
            ))}
          </motion.div>
        </motion.div>
      </motion.section>
    </>
  );
}
const Stat = memo(function Stat({
  label,
  value,
  note,
  tone = "blue",
}: {
  label: string;
  value: ReactNode;
  note: string;
  tone?: string;
}) {
  return (
    <article className={`stat tone-${tone}`}>
      <span>{label}</span>
      <strong>{value}</strong>
      <small>{note}</small>
    </article>
  );
});

const PanelTitle = memo(function PanelTitle({ title, sub }: { title: string; sub: string }) {
  return (
    <div className="panel-title">
      <h2>{title}</h2>
      <p>{sub}</p>
    </div>
  );
});

const Metric = memo(function Metric({
  label,
  value,
  raw,
}: {
  label: string;
  value?: number;
  raw?: string;
}) {
  return (
    <div>
      <strong>{raw ?? `${Math.round((value || 0) * 100)}%`}</strong>
      <span>{label}</span>
    </div>
  );
});

const State = memo(function State({ title, body }: { title: string; body: string }) {
  return (
    <div className="state">
      <span className="spinner" />
      <h1>{title}</h1>
      <p>{body}</p>
    </div>
  );
});

const Empty = memo(function Empty() {
  return (
    <div className="empty-hero">
      <span className="radar">&#9672;</span>
      <p className="eyebrow">No completed inventory</p>
      <h1>Start with evidence, not assumptions.</h1>
      <p>
        Scan the bundled enterprise repository to build a measured cryptographic inventory and PQC
        migration view.
      </p>
      {canWrite() ? (
        <Link className="button" to="/scan">
          Run discovery scan
        </Link>
      ) : (
        <p className="muted" style={{ marginTop: 12 }}>
          Ask an administrator or security analyst to run a scan.
        </p>
      )}
    </div>
  );
});

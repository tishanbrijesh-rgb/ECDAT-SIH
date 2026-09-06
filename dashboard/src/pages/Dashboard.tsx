// Portfolio posture, assurance measurements, and research evaluation.
import { lazy, Suspense, useEffect, useState, useRef } from "react";
import { Link } from "react-router-dom";
import { downloadReport, getDashboardSummary, getEvaluation, canWrite } from "../api/client";
import type { DashboardSummary, Evaluation } from "../types";

const RiskDistributionChart = lazy(() => import("../components/RiskDistributionChart"));

// Animated number that counts up from 0 to the target value.
function AnimatedNumber({ value, suffix = "" }: { value: number; suffix?: string }) {
  const [display, setDisplay] = useState(0);
  const ref = useRef<number>();
  useEffect(() => {
    if (window.matchMedia("(prefers-reduced-motion: reduce)").matches) {
      setDisplay(value);
      return;
    }
    const target = value;
    const duration = 600;
    const start = performance.now();
    const from = display;
    const step = (now: number) => {
      const t = Math.min(1, (now - start) / duration);
      const eased = 1 - Math.pow(1 - t, 3);
      setDisplay(Math.round(from + (target - from) * eased));
      if (t < 1) ref.current = requestAnimationFrame(step);
    };
    ref.current = requestAnimationFrame(step);
    return () => {
      if (ref.current !== undefined) cancelAnimationFrame(ref.current);
    };
  }, [value]);
  return (
    <>
      {display}
      {suffix}
    </>
  );
}

export default function Dashboard() {
  const [summary, setSummary] = useState<DashboardSummary>();
  const [evaluation, setEvaluation] = useState<Evaluation>();
  const [error, setError] = useState("");
  useEffect(() => {
    Promise.all([getDashboardSummary(), getEvaluation().catch(() => undefined)])
      .then(([s, e]) => {
        setSummary(s);
        setEvaluation(e);
      })
      .catch((e) => setError(String(e)));
  }, []);
  if (error) return <State title="Dashboard unavailable" body={error} />;
  if (!summary)
    return (
      <State
        title="Building assurance view"
        body="Loading inventory, risk, and evidence metrics…"
      />
    );
  if (!summary.latest_scan_id) return <Empty />;

  const confidencePct = Math.round(summary.avg_confidence * 100);

  const risk = ["CRITICAL", "HIGH", "MEDIUM", "LOW"].map((label) => ({
    label,
    count: summary.risk_distribution[label as keyof typeof summary.risk_distribution] || 0,
  }));
  const collectors = Object.entries(summary.collector_stats).map(([label, count]) => ({
    label: label.toUpperCase(),
    count,
  }));

  // Build a confidence indicator color for the conf stat
  const confTone = confidencePct >= 80 ? "teal" : confidencePct >= 50 ? "amber" : "red";

  return (
    <>
      <section className="hero">
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
            onClick={() =>
              downloadReport("/api/reports/risk.txt", "ecdat-risk-report.txt").catch((e) =>
                setError(String(e)),
              )
            }
          >
            Download risk report
          </button>
          <button
            className="button"
            onClick={() =>
              downloadReport("/api/cbom", "ecdat-cbom.json").catch((e) => setError(String(e)))
            }
          >
            View CBOM
          </button>
        </div>
      </section>
      <section className="stats six">
        <Stat
          label="Assets"
          value={<AnimatedNumber value={summary.total_assets} />}
          note="correlated findings"
          tone="blue"
        />
        <Stat
          label="High risk"
          value={<AnimatedNumber value={summary.high_risk_count} />}
          note="critical + high"
          tone="red"
        />
        <Stat
          label="Quantum exposed"
          value={<AnimatedNumber value={summary.quantum_vulnerable_count} />}
          note="public-key assets"
          tone="amber"
        />
        <Stat
          label="Confidence"
          value={`${confidencePct}%`}
          note="average evidence score"
          tone={confTone}
        />
        <Stat
          label="Coverage"
          value={`${summary.coverage_pct}%`}
          note="supported files scanned"
          tone="teal"
        />
        <Stat
          label="Conflicts"
          value={<AnimatedNumber value={summary.conflict_count} />}
          note="operation-level contradictions"
          tone="violet"
        />
      </section>
      <section className="dashboard-grid">
        <article className="panel span-2">
          <PanelTitle
            title="Risk distribution"
            sub="Migration urgency across the latest inventory"
          />
          <Suspense fallback={<div className="skeleton" style={{ height: 270 }} />}>
            <RiskDistributionChart data={risk} />
          </Suspense>
        </article>
        <article className="panel">
          <PanelTitle title="Evidence collectors" sub="Independent records supporting findings" />
          <div className="collector-list">
            {collectors.length === 0 && (
              <p className="muted" style={{ padding: "10px 0" }}>
                No collector data available.
              </p>
            )}
            {collectors.map((c) => (
              <div key={c.label}>
                <span>{c.label}</span>
                <strong>{c.count}</strong>
                <i style={{ width: `${Math.min(100, c.count * 3)}%` }} />
              </div>
            ))}
          </div>
        </article>
        <article className="panel">
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
        </article>
        <article className="panel span-2 blind">
          <PanelTitle
            title="Visibility gaps"
            sub="Explicit uncertainty—not a false claim of completeness"
          />
          <div className="gap-list">
            {summary.blind_spots.map((gap, i) => (
              <div key={gap}>
                <span>{i + 1}</span>
                <p>{gap}</p>
              </div>
            ))}
          </div>
        </article>
      </section>
    </>
  );
}
function Stat({
  label,
  value,
  note,
  tone = "blue",
}: {
  label: string;
  value: React.ReactNode;
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
}
function PanelTitle({ title, sub }: { title: string; sub: string }) {
  return (
    <div className="panel-title">
      <h2>{title}</h2>
      <p>{sub}</p>
    </div>
  );
}
function Metric({ label, value, raw }: { label: string; value?: number; raw?: string }) {
  return (
    <div>
      <strong>{raw ?? `${Math.round((value || 0) * 100)}%`}</strong>
      <span>{label}</span>
    </div>
  );
}
function State({ title, body }: { title: string; body: string }) {
  return (
    <div className="state">
      <span className="spinner" />
      <h1>{title}</h1>
      <p>{body}</p>
    </div>
  );
}
function Empty() {
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
}

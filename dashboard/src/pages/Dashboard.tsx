// Portfolio posture, assurance measurements, and research evaluation.
import { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { Bar, BarChart, CartesianGrid, ResponsiveContainer, Tooltip, XAxis, YAxis } from "recharts";
import { downloadReport, getDashboardSummary, getEvaluation, canWrite } from "../api/client";
import type { DashboardSummary, Evaluation } from "../types";

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
  const risk = ["CRITICAL", "HIGH", "MEDIUM", "LOW"].map((label) => ({
    label,
    count: summary.risk_distribution[label as keyof typeof summary.risk_distribution] || 0,
  }));
  const collectors = Object.entries(summary.collector_stats).map(([label, count]) => ({
    label: label.toUpperCase(),
    count,
  }));
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
        <Stat label="Assets" value={summary.total_assets} note="correlated findings" />
        <Stat label="High risk" value={summary.high_risk_count} tone="red" note="critical + high" />
        <Stat
          label="Quantum exposed"
          value={summary.quantum_vulnerable_count}
          tone="amber"
          note="public-key assets"
        />
        <Stat
          label="Confidence"
          value={`${Math.round(summary.avg_confidence * 100)}%`}
          note="average evidence score"
        />
        <Stat
          label="Coverage"
          value={`${summary.coverage_pct}%`}
          tone="teal"
          note="supported files scanned"
        />
        <Stat
          label="Conflicts"
          value={summary.conflict_count}
          tone="violet"
          note="operation-level contradictions"
        />
      </section>
      <section className="dashboard-grid">
        <article className="panel span-2">
          <PanelTitle
            title="Risk distribution"
            sub="Migration urgency across the latest inventory"
          />
          <ResponsiveContainer width="100%" height={270}>
            <BarChart data={risk}>
              <CartesianGrid stroke="#e9edf4" vertical={false} />
              <XAxis dataKey="label" tickLine={false} />
              <YAxis allowDecimals={false} tickLine={false} />
              <Tooltip />
              <Bar dataKey="count" fill="#4257d6" radius={[8, 8, 0, 0]} />
            </BarChart>
          </ResponsiveContainer>
        </article>
        <article className="panel">
          <PanelTitle title="Evidence collectors" sub="Independent records supporting findings" />
          <div className="collector-list">
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
  value: string | number;
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
      <span className="radar">◎</span>
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
        <p>Ask an administrator or security analyst to run a scan.</p>
      )}
    </div>
  );
}

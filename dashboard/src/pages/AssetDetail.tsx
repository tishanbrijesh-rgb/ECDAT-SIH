// Detailed evidence, Mosca inputs, and use-case-aware migration guidance.
import { useEffect, useState } from "react";
import { Link, useParams } from "react-router-dom";
import { getAsset, updateAsset } from "../api/client";
import { ConfidenceBar } from "../components/ConfidenceBar";
import { EvidenceChain } from "../components/EvidenceChain";
import { RiskBadge } from "../components/RiskBadge";
import type { CryptoAsset } from "../types";

export default function AssetDetail() {
  const { id } = useParams();
  const [asset, setAsset] = useState<CryptoAsset>();
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState("");
  useEffect(() => {
    if (id)
      getAsset(Number(id))
        .then(setAsset)
        .catch((e) => setError(String(e)));
  }, [id]);
  const change = async (field: string, value: string | number) => {
    if (!asset) return;
    setSaving(true);
    try {
      setAsset(await updateAsset(asset.id, { [field]: value }));
    } catch (e) {
      setError(String(e));
    } finally {
      setSaving(false);
    }
  };
  if (error && !asset) return <div className="callout error">{error}</div>;
  if (!asset)
    return (
      <div className="state">
        <span className="spinner" />
        <h1>Loading evidence</h1>
      </div>
    );
  return (
    <>
      <Link className="back" to="/assets">
        ← Inventory
      </Link>
      <section className="hero compact asset-hero">
        <div>
          <p className="eyebrow">Logical asset · {asset.logical_asset_id}</p>
          <h1>
            {asset.algorithm}
            {asset.key_size ? `-${asset.key_size}` : ""}
          </h1>
          <p className="path">{asset.location}</p>
        </div>
        <div className="risk-stack">
          <RiskBadge label={asset.priority_label} score={asset.priority_score} />
          <span>
            {asset.quantum_vulnerable ? "Quantum migration required" : "No modeled Shor exposure"}
          </span>
        </div>
      </section>
      {asset.conflict && (
        <div className="callout error">
          <strong>Evidence conflict detected.</strong> Review the operation-level evidence before
          migration.
        </div>
      )}
      <section className="detail-grid">
        <article className="panel">
          <h2>Discovery assurance</h2>
          <ConfidenceBar confidence={asset.confidence} />
          <dl className="facts">
            <dt>Component</dt>
            <dd>{asset.evidence_json.component}</dd>
            <dt>Usage</dt>
            <dd>{asset.usage}</dd>
            <dt>Library</dt>
            <dd>{asset.library || "Direct / unknown"}</dd>
            <dt>Protocol</dt>
            <dd>{asset.protocol || "Not established"}</dd>
            <dt>Evidence sources</dt>
            <dd>{asset.source.length}</dd>
          </dl>
          <h3>Evidence chain</h3>
          <EvidenceChain
            sources={asset.source}
            evidenceDetails={asset.evidence_json.evidence_list || []}
          />
        </article>
        <article className="panel">
          <div className="panel-title inline">
            <div>
              <h2>Risk context</h2>
              <p>Changes recalculate risk immediately.</p>
            </div>
            {saving && <span className="saving">Saving…</span>}
          </div>
          <div className="form-grid">
            <Select
              label="Business criticality"
              value={asset.business_criticality}
              options={["low", "medium", "high", "critical"]}
              onChange={(v) => change("business_criticality", v)}
            />
            <Select
              label="Data sensitivity"
              value={asset.data_sensitivity}
              options={["low", "medium", "high", "critical"]}
              onChange={(v) => change("data_sensitivity", v)}
            />
            <Select
              label="Exposure"
              value={asset.exposure}
              options={["isolated", "internal", "partner", "internet"]}
              onChange={(v) => change("exposure", v)}
            />
            <Select
              label="Migration effort"
              value={asset.migration_effort}
              options={["low", "medium", "high", "critical"]}
              onChange={(v) => change("migration_effort", v)}
            />
            <NumberField
              label="Data lifetime (years)"
              value={asset.data_lifetime_years}
              onChange={(v) => change("data_lifetime_years", v)}
            />
            <NumberField
              label="Migration time (years)"
              value={asset.migration_time_years}
              onChange={(v) => change("migration_time_years", v)}
            />
            <NumberField
              label="Threat horizon (years)"
              value={asset.threat_horizon_years}
              onChange={(v) => change("threat_horizon_years", v)}
            />
          </div>
          <div className="mosca">
            <strong>Mosca planning window</strong>
            <span>
              {asset.data_lifetime_years} + {asset.migration_time_years} ={" "}
              {asset.data_lifetime_years + asset.migration_time_years} years
            </span>
            <small>Compared with a {asset.threat_horizon_years}-year threat horizon</small>
          </div>
        </article>
        <article className="panel span-2 recommendation">
          <div>
            <p className="eyebrow">Migration guidance</p>
            <h2>
              {asset.hybrid_recommended ? "Hybrid transition recommended" : "PQC recommendation"}
            </h2>
            <p>{asset.pqc_candidate}</p>
          </div>
          <div>
            <h3>Why this priority?</h3>
            <ul>
              {asset.risk_reasons.map((reason) => (
                <li key={reason}>{reason}</li>
              ))}
            </ul>
          </div>
        </article>
      </section>
    </>
  );
}
function Select({
  label,
  value,
  options,
  onChange,
}: {
  label: string;
  value: string;
  options: string[];
  onChange: (v: string) => void;
}) {
  return (
    <label>
      {label}
      <select value={value} onChange={(e) => onChange(e.target.value)}>
        {options.map((o) => (
          <option value={o} key={o}>
            {o[0].toUpperCase() + o.slice(1)}
          </option>
        ))}
      </select>
    </label>
  );
}
function NumberField({
  label,
  value,
  onChange,
}: {
  label: string;
  value: number;
  onChange: (v: number) => void;
}) {
  return (
    <label>
      {label}
      <input
        type="number"
        min="0"
        value={value}
        onChange={(e) => onChange(Number(e.target.value))}
      />
    </label>
  );
}

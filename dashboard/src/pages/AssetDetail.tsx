// Detailed evidence, Mosca inputs, and use-case-aware migration guidance.
import { useEffect, useState } from "react";
import { Link, useParams } from "react-router-dom";
import { getAsset, updateAsset, canWrite } from "../api/client";
import { ConfidenceBar } from "../components/ConfidenceBar";
import { EvidenceChain } from "../components/EvidenceChain";
import { RiskBadge } from "../components/RiskBadge";
import Breadcrumb from "../components/Breadcrumb";
import { relativeTime, formatDate } from "../utils/format";
import { useDirtyGuard } from "../utils/hooks";
import type { CryptoAsset } from "../types";

export default function AssetDetail() {
  const { id } = useParams();
  const [asset, setAsset] = useState<CryptoAsset>();
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState("");
  const [pendingChange, setPendingChange] = useState<{
    field: string;
    value: string | number;
  } | null>(null);
  const [isDirty, setIsDirty] = useState(false);
  useDirtyGuard(isDirty);
  useEffect(() => {
    if (id)
      getAsset(Number(id))
        .then(setAsset)
        .catch((e) => setError(String(e)));
  }, [id]);
  const change = async (field: string, value: string | number) => {
    if (!asset || !canWrite()) return;
    setError("");
    setPendingChange({ field, value });
    setIsDirty(true);
    setSaving(true);
    try {
      const updated = await updateAsset(asset.id, { [field]: value });
      setAsset(updated);
      setPendingChange(null);
      setIsDirty(false);
    } catch (e) {
      setError(`Risk context was not saved. Check the connection and retry. (${String(e)})`);
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
  const planWindow = asset.data_lifetime_years + asset.migration_time_years;
  const threatGap = planWindow - asset.threat_horizon_years;
  const threatOverlap = asset.quantum_vulnerable && threatGap >= 0;
  return (
    <>
      <Breadcrumb
        items={[
          { label: "Inventory", to: "/assets" },
          {
            label: `${asset.algorithm}${asset.key_size ? `-${asset.key_size}` : ""}`,
            to: undefined,
          },
        ]}
      />
      <section className="hero compact asset-hero">
        <div>
          <p className="eyebrow">Logical asset &middot; {asset.logical_asset_id}</p>
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
          migration. Multiple sources disagree about this finding.
        </div>
      )}
      {threatOverlap && (
        <div className="callout mosca-warning">
          <strong>Mosca window reaches the threat horizon.</strong> This quantum-vulnerable asset's
          planning window ({planWindow} years) meets or exceeds the modeled threat horizon (
          {asset.threat_horizon_years} years).{" "}
          {threatGap > 0
            ? `It exceeds the horizon by ${threatGap} years.`
            : "No migration safety margin remains."}
        </div>
      )}
      <section className="detail-grid">
        <article className="panel">
          <h2>Discovery assurance</h2>
          <ConfidenceBar confidence={asset.confidence} />
          <dl className="facts">
            <dt>Component</dt>
            <dd>{asset.evidence_json.component || "—"}</dd>
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
            {saving && (
              <span className="saving" aria-live="polite">
                Saving…
              </span>
            )}
          </div>
          {error && (
            <div className="callout error" role="alert">
              <p>{error}</p>
              {pendingChange && (
                <div className="inline-actions">
                  <button
                    className="button"
                    disabled={saving}
                    onClick={() => change(pendingChange.field, pendingChange.value)}
                  >
                    Retry save
                  </button>
                  <button
                    className="button secondary"
                    disabled={saving}
                    onClick={() => {
                      setPendingChange(null);
                      setIsDirty(false);
                      setError("");
                    }}
                  >
                    Discard change
                  </button>
                </div>
              )}
            </div>
          )}
          {!canWrite() && (
            <p className="muted">
              Read-only access. An administrator or security analyst can edit risk context.
            </p>
          )}
          <fieldset
            className="form-grid"
            disabled={!canWrite() || saving}
            style={{ border: 0, padding: 0, margin: 0 }}
          >
            <Select
              id="business-criticality"
              label="Business criticality"
              value={asset.business_criticality}
              options={["low", "medium", "high", "critical"]}
              onChange={(v) => change("business_criticality", v)}
            />
            <Select
              id="data-sensitivity"
              label="Data sensitivity"
              value={asset.data_sensitivity}
              options={["low", "medium", "high", "critical"]}
              onChange={(v) => change("data_sensitivity", v)}
            />
            <Select
              id="exposure"
              label="Exposure"
              value={asset.exposure}
              options={["isolated", "internal", "partner", "internet"]}
              onChange={(v) => change("exposure", v)}
            />
            <Select
              id="migration-effort"
              label="Migration effort"
              value={asset.migration_effort}
              options={["low", "medium", "high", "critical"]}
              onChange={(v) => change("migration_effort", v)}
            />
            <NumberField
              id="data-lifetime"
              label="Data lifetime (years)"
              value={asset.data_lifetime_years}
              onChange={(v) => change("data_lifetime_years", v)}
            />
            <NumberField
              id="migration-time"
              label="Migration time (years)"
              value={asset.migration_time_years}
              onChange={(v) => change("migration_time_years", v)}
            />
            <NumberField
              id="threat-horizon"
              label="Threat horizon (years)"
              value={asset.threat_horizon_years}
              onChange={(v) => change("threat_horizon_years", v)}
            />
          </fieldset>
          <div className={`mosca${threatOverlap ? " mosca-warning" : ""}`}>
            <strong>Mosca planning window</strong>
            <span>
              {asset.data_lifetime_years} + {asset.migration_time_years} = {planWindow} years
            </span>
            <small>Compared with a {asset.threat_horizon_years}-year threat horizon</small>
            {threatOverlap && (
              <small className="mosca-threat-note">
                {threatGap > 0
                  ? `Plan window exceeds horizon by ${threatGap} years`
                  : "Plan window meets the horizon; no safety margin remains"}
              </small>
            )}
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
  id,
}: {
  label: string;
  value: string;
  options: string[];
  onChange: (v: string) => void;
  id: string;
}) {
  return (
    <label htmlFor={id}>
      {label}
      <select id={id} value={value} onChange={(e) => onChange(e.target.value)}>
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
  id,
}: {
  label: string;
  value: number;
  onChange: (v: number) => void;
  id: string;
}) {
  return (
    <label htmlFor={id}>
      {label}
      <input
        id={id}
        type="number"
        min="0"
        max="999"
        value={value}
        onChange={(e) => onChange(Number(e.target.value))}
      />
    </label>
  );
}

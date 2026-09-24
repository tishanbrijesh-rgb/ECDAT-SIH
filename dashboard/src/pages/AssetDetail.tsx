// Detailed evidence, Mosca inputs, and use-case-aware migration guidance.
import { useState, useEffect } from "react";
import { useParams } from "react-router-dom";
import { getAsset, updateAsset, canWrite } from "../api/client";
import { ConfidenceBar } from "../components/ConfidenceBar";
import { EvidenceChain } from "../components/EvidenceChain";
import { RiskBadge } from "../components/RiskBadge";
import Breadcrumb from "../components/Breadcrumb";
import { Disclosure } from "../components/Disclosure";
import { useDirtyGuard } from "../utils/hooks";
import { buildMoscaScenarios } from "../utils/mosca";
import Select from "../components/Select";
import NumberField from "../components/NumberField";
import type { CryptoAsset, EvidenceEntry } from "../types";

const DEPRECATED_ALGOS = new Set(["MD5", "SHA-1"]);

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
  const [scoreUpdated, setScoreUpdated] = useState(false);
  const [prevScore, setPrevScore] = useState<number | null>(null);

  useDirtyGuard(isDirty);

  useEffect(() => {
    if (id)
      getAsset(Number(id))
        .then((a) => {
          setAsset(a);
          setPrevScore(a.priority_score);
        })
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
      // Flash the recalculation indicator if the score changed.
      if (prevScore !== null && updated.priority_score !== prevScore) {
        setScoreUpdated(true);
        setTimeout(() => setScoreUpdated(false), 2000);
      }
      setPrevScore(updated.priority_score);
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
  const moscaScenarios = buildMoscaScenarios(
    asset.data_lifetime_years,
    asset.migration_time_years,
    asset.threat_horizon_years,
  );
  const hasClassicalWeakness = DEPRECATED_ALGOS.has(asset.algorithm);
  const hasQuantumExposure = asset.quantum_vulnerable;

  function provenanceLabel(field: string): string {
    return asset!.risk_context_provenance?.[field] === "user-provided"
      ? "User-provided"
      : "Policy default";
  }

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
          {scoreUpdated && (
            <span className="score-recalculated" aria-live="polite">
              Score recalculated
            </span>
          )}
          {asset.capability_only && (
            <span
              className="capability-badge"
              title="Usage inferred from capabilities, not observed operations"
            >
              Capability only
            </span>
          )}
          <span>
            {hasQuantumExposure ? "Quantum migration required" : "No modeled Shor exposure"}
          </span>
        </div>
      </section>

      {asset.conflict && (
        <div className="callout error">
          <strong>Evidence conflict detected.</strong> Review the operation-level evidence before
          migration. Multiple sources disagree about this finding.
        </div>
      )}

      {/* Combined overlap callout — only shown when both quantum exposure AND window overlap exist */}
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

      <section className="detail-grid asset-detail-grid">
        <article className="panel discovery-panel">
          <div className="panel-title">
            <p className="eyebrow">Observed evidence</p>
            <h2>Discovery assurance</h2>
            <p>What the scanner found and how strongly the sources agree.</p>
          </div>
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
          {asset.evidence_json.evidence_list && asset.evidence_json.evidence_list.length > 0 && (
            <>
              <h3>Evidence timeline</h3>
              <div className="evidence-timeline">
                {(asset.evidence_json.evidence_list as EvidenceEntry[]).map(
                  (entry: EvidenceEntry, idx: number) => (
                    <Disclosure key={idx} defaultOpen={idx === 0}>
                      {({ isOpen, setOpen, buttonId, panelId }) => {
                        const detailText = entry.detail as string | undefined;
                        const componentText = entry.component as string | undefined;
                        const kindText = entry.kind as string | undefined;
                        const confidenceVal = entry.confidence as number | undefined;
                        const timestampText = entry.timestamp as string | undefined;
                        const sourceText = entry.source as string | undefined;
                        return (
                          <div
                            className="timeline-entry"
                            data-open={isOpen}
                            style={
                              timestampText
                                ? ({ "--ts": timestampText } as React.CSSProperties)
                                : undefined
                            }
                          >
                            <button
                              id={buttonId}
                              aria-expanded={isOpen}
                              aria-controls={panelId}
                              className="disclosure-trigger timeline-trigger"
                              onClick={() => setOpen(!isOpen)}
                            >
                              <span className={`evidence-kind kind-${kindText || "unknown"}`}>
                                {kindText || "unknown"}
                              </span>
                              <span className="timeline-meta">
                                {confidenceVal !== undefined &&
                                  `${Math.round(confidenceVal * 100)}%`}
                                {sourceText && <> · {sourceText}</>}
                              </span>
                              {timestampText && (
                                <time className="timeline-time">{timestampText}</time>
                              )}
                            </button>
                            <div
                              id={panelId}
                              role="region"
                              aria-labelledby={buttonId}
                              className="disclosure-panel"
                              data-open={isOpen}
                            >
                              <div className="timeline-detail">
                                {detailText && <p>{detailText}</p>}
                                {!detailText && componentText && (
                                  <p>
                                    <strong>Component:</strong> {componentText}
                                  </p>
                                )}
                                {!detailText && !componentText && (
                                  <p className="muted">No additional detail recorded.</p>
                                )}
                              </div>
                            </div>
                          </div>
                        );
                      }}
                    </Disclosure>
                  ),
                )}
              </div>
            </>
          )}
        </article>

        <article className="panel risk-context-panel">
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
          <fieldset className="risk-context-form" disabled={!canWrite() || saving}>
            <legend className="sr-only">Business and migration risk inputs</legend>
            <div className="context-field">
              <Select
                id="business-criticality"
                label="Business criticality"
                value={asset.business_criticality}
                options={["low", "medium", "high", "critical"]}
                onChange={(v) => change("business_criticality", v)}
              />
              <span className="field-provenance">{provenanceLabel("business_criticality")}</span>
            </div>
            <div className="context-field">
              <Select
                id="data-sensitivity"
                label="Data sensitivity"
                value={asset.data_sensitivity}
                options={["low", "medium", "high", "critical"]}
                onChange={(v) => change("data_sensitivity", v)}
              />
              <span className="field-provenance">{provenanceLabel("data_sensitivity")}</span>
            </div>
            <div className="context-field">
              <Select
                id="exposure"
                label="Exposure"
                value={asset.exposure}
                options={["isolated", "internal", "partner", "internet"]}
                onChange={(v) => change("exposure", v)}
              />
              <span className="field-provenance">{provenanceLabel("exposure")}</span>
            </div>
            <div className="context-field">
              <Select
                id="migration-effort"
                label="Migration effort"
                value={asset.migration_effort}
                options={["low", "medium", "high", "critical"]}
                onChange={(v) => change("migration_effort", v)}
              />
              <span className="field-provenance">{provenanceLabel("migration_effort")}</span>
            </div>
            <div className="context-field">
              <NumberField
                id="data-lifetime"
                label="Data lifetime (years)"
                value={asset.data_lifetime_years}
                onChange={(v) => change("data_lifetime_years", v)}
              />
              <span className="field-provenance">{provenanceLabel("data_lifetime_years")}</span>
            </div>
            <div className="context-field">
              <NumberField
                id="migration-time"
                label="Migration time (years)"
                value={asset.migration_time_years}
                onChange={(v) => change("migration_time_years", v)}
              />
              <span className="field-provenance">{provenanceLabel("migration_time_years")}</span>
            </div>
            <div className="context-field">
              <NumberField
                id="threat-horizon"
                label="Threat horizon (years)"
                value={asset.threat_horizon_years}
                onChange={(v) => change("threat_horizon_years", v)}
              />
              <span className="field-provenance">{provenanceLabel("threat_horizon_years")}</span>
            </div>
          </fieldset>

          <div className={`migration-window${threatOverlap ? " is-urgent" : ""}`}>
            <div className="migration-window-heading">
              <div>
                <p className="eyebrow">Computed decision</p>
                <h3>Mosca planning window</h3>
              </div>
              <strong className="migration-window-total">{planWindow} years</strong>
            </div>
            <div
              className="migration-equation"
              aria-label={`${asset.data_lifetime_years} years data lifetime plus ${asset.migration_time_years} years migration time equals ${planWindow} years`}
            >
              <span>
                <strong>{asset.data_lifetime_years}y</strong>
                <small>X — Data lifetime</small>
              </span>
              <b aria-hidden="true">+</b>
              <span>
                <strong>{asset.migration_time_years}y</strong>
                <small>Y — Migration time</small>
              </span>
              <b aria-hidden="true">vs</b>
              <span>
                <strong>{asset.threat_horizon_years}y</strong>
                <small>Z — Threat horizon</small>
              </span>
            </div>
            <p className="migration-window-result">
              {threatOverlap
                ? threatGap > 0
                  ? `Action is overdue by ${threatGap} years.`
                  : "No migration safety margin remains."
                : `${Math.abs(threatGap)} years of migration margin remain.`}
            </p>
            <div className="mosca-scenarios" aria-label="Mosca threat-horizon scenarios">
              {moscaScenarios.map((scenario) => (
                <section
                  key={scenario.id}
                  className={`mosca-scenario${scenario.overlaps ? " is-urgent" : ""}`}
                >
                  <strong>{scenario.label}</strong>
                  <span>
                    X + Y = {scenario.x + scenario.y}y vs Z = {scenario.z}y
                  </span>
                  <small>
                    {scenario.overlaps
                      ? `${scenario.gap}y overlap`
                      : `${Math.abs(scenario.gap)}y margin`}
                  </small>
                </section>
              ))}
            </div>
          </div>

          {/* Separated: algorithmic weakness vs quantum exposure */}
          {(() => {
            if (!hasClassicalWeakness && !hasQuantumExposure) return null;
            return (
              <div className="exposure-summary">
                {hasClassicalWeakness && (
                  <section className="exposure-item classical-weakness">
                    <p className="exposure-label">Algorithmic weakness</p>
                    <p>
                      {asset.algorithm} is deprecated — replace with SHA-256 or SHA-3 independent of
                      quantum migration. This is a classical cryptographic weakness with no quantum
                      component.
                    </p>
                  </section>
                )}
                {hasQuantumExposure && (
                  <section
                    className={`exposure-item quantum-exposure${threatOverlap ? " overlap" : ""}`}
                  >
                    <p className="exposure-label">Quantum exposure</p>
                    <p>
                      {asset.algorithm} is vulnerable to large-scale quantum attacks (Shor&apos;s
                      algorithm).
                    </p>
                    {threatOverlap && (
                      <p className="exposure-action">
                        {threatGap > 0
                          ? `Begin migration now; the modeled window is ${threatGap} years beyond the threat horizon.`
                          : "No safety margin remains — migration should already be underway."}
                      </p>
                    )}
                  </section>
                )}
              </div>
            );
          })()}
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
              {asset.risk_reasons.map((reason: string) => (
                <li key={reason}>{reason}</li>
              ))}
            </ul>
          </div>
        </article>
      </section>
    </>
  );
}

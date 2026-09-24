// CBOM (Cryptographic Bill of Materials) viewer.
import { useState, useEffect, useMemo, useCallback } from "react";
import { useSearchParams } from "react-router-dom";
import { motion } from "framer-motion";
import { downloadReport, getCbom, getEvidenceGraph, getRiskReport } from "../api/client";
import type { OutputPagination } from "../api/client";
import { displayPath, formatDate } from "../utils/format";
import type { CbomEntry } from "../types";

// ── CBOM schema validation ──────────────────────────────────────
const REQUIRED_FIELDS = ["bomFormat", "specVersion", "serialNumber", "metadata", "components"];

function validateCbomSchema(entry: CbomEntry): { valid: boolean; errors: string[] } {
  const errors: string[] = [];
  for (const field of REQUIRED_FIELDS) {
    const val = (entry as unknown as Record<string, unknown>)[field];
    if (val === undefined || val === null || val === "") {
      errors.push(`Missing or empty "${field}"`);
    }
  }
  if (!Array.isArray(entry.components)) {
    errors.push("Components must be an array");
  }
  return { valid: errors.length === 0, errors };
}

// ── Stagger variants ───────────────────────────────────────────
const staggerContainer = {
  animate: { transition: { staggerChildren: 0.05, delayChildren: 0.05 } },
};
const staggerItem = {
  initial: { opacity: 0, y: 8 },
  animate: { opacity: 1, y: 0, transition: { duration: 0.25, ease: [0.25, 0.1, 0.25, 1] } },
};

const EMPTY_CBOM: CbomEntry = {
  bomFormat: "",
  specVersion: "",
  serialNumber: "",
  metadata: {},
  components: [],
  vulnerabilities: [],
  dependencies: [],
  services: [],
};

const SKELETON_COUNT = 6;
const PAGE_SIZE = 100;

type JsonRecord = Record<string, unknown>;

function readProperties(value: unknown): Record<string, string> {
  if (!Array.isArray(value)) return {};
  return Object.fromEntries(
    value
      .filter((item): item is JsonRecord => Boolean(item) && typeof item === "object")
      .filter((item) => typeof item.name === "string" && typeof item.value === "string")
      .map((item) => [item.name as string, item.value as string]),
  );
}

function readStringArray(value: string | undefined): string[] {
  if (!value) return [];
  try {
    const parsed = JSON.parse(value) as unknown;
    return Array.isArray(parsed) ? parsed.map(String) : [];
  } catch {
    return value
      .split(",")
      .map((item) => item.trim())
      .filter(Boolean);
  }
}

export default function CbomPage() {
  const [params] = useSearchParams();
  const scanId = params.get("scan_id") ? Number(params.get("scan_id")) : undefined;

  const [cbom, setCbom] = useState<CbomEntry & { pagination?: OutputPagination }>(EMPTY_CBOM);
  const [graph, setGraph] = useState<import("../types").EvidenceGraphResponse | null>(null);
  const [report, setReport] = useState<{
    title: string;
    scan_id: number;
    repository: string;
  } | null>(null);
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(true);
  const [view, setView] = useState<"components" | "graph" | "raw">("components");
  const [retryKey, setRetryKey] = useState(0);
  const [compFilter, setCompFilter] = useState("");
  const [offset, setOffset] = useState(0);
  const [exporting, setExporting] = useState(false);
  const [exportedCount, setExportedCount] = useState(0);

  useEffect(() => {
    let cancelled = false;
    setCbom(EMPTY_CBOM);
    setGraph(null);
    setReport(null);
    setError("");
    setLoading(true);
    Promise.all([
      getCbom(scanId, { limit: PAGE_SIZE, offset, query: compFilter }),
      getEvidenceGraph(scanId).catch(() => null),
      scanId ? getRiskReport(scanId).catch(() => null) : Promise.resolve(null),
    ])
      .then(([c, g, r]) => {
        if (cancelled) return;
        setCbom(c);
        setGraph(g);
        if (r) setReport({ title: r.title, scan_id: r.scan_id, repository: r.repository });
      })
      .catch((e) => {
        if (!cancelled) {
          setError(
            `Unable to load the CBOM. Check the API connection and try again. (${e instanceof Error ? e.message : String(e)})`,
          );
        }
      })
      .finally(() => {
        if (!cancelled) setLoading(false);
      });
    return () => {
      cancelled = true;
    };
  }, [scanId, retryKey, offset, compFilter]);

  const components = useMemo(() => {
    const c = cbom.components || [];
    return c as Array<Record<string, unknown>>;
  }, [cbom]);

  const schemaValidation = useMemo(() => {
    if (cbom.bomFormat === "" && cbom.specVersion === "") return null;
    return validateCbomSchema(cbom);
  }, [cbom]);

  const riskDistribution = useMemo(() => {
    const counts = { CRITICAL: 0, HIGH: 0, MEDIUM: 0, LOW: 0 };
    for (const comp of components) {
      const cp = comp.properties as Array<{ name: string; value: string }> | undefined;
      const labelEntry = cp?.find((p) => p.name === "ecdat:risk-label");
      const scoreEntry = cp?.find((p) => p.name === "ecdat:risk-score");
      let label = labelEntry?.value;
      if (!label) {
        const score = scoreEntry ? Number(scoreEntry.value) : 0;
        label = score >= 75 ? "CRITICAL" : score >= 50 ? "HIGH" : score >= 25 ? "MEDIUM" : "LOW";
      }
      if (label in counts) (counts as Record<string, number>)[label]++;
    }
    return counts;
  }, [components]);

  const vulnerabilities = cbom.vulnerabilities || [];
  const services = cbom.services || [];
  // Type filter
  const typeCounts = useMemo(() => {
    const counts: Record<string, number> = {};
    for (const comp of components) {
      const t = (comp.type as string) || "library";
      counts[t] = (counts[t] || 0) + 1;
    }
    return counts;
  }, [components]);

  const filteredComponents = useMemo(() => {
    return components;
  }, [components]);

  const pagination = cbom.pagination ?? {
    total: components.length,
    filtered: components.length,
    offset: 0,
    limit: PAGE_SIZE,
    loaded: components.length,
  };

  const handleExportCsv = useCallback(async () => {
    if (exporting || pagination.total === 0) return;
    setExporting(true);
    try {
      await downloadReport(
        `/api/cbom.csv${scanId ? `?scan_id=${scanId}` : ""}`,
        `ecdat-cbom-${report?.scan_id || "latest"}.csv`,
      );
      setExportedCount(pagination.total);
    } finally {
      setExporting(false);
    }
  }, [exporting, pagination.total, report?.scan_id, scanId]);

  const metadataRecord = cbom.metadata as Record<string, unknown> | undefined;
  const metadataProperties = readProperties(metadataRecord?.properties);
  const serial =
    cbom.serialNumber ||
    cbom.serial_number ||
    (metadataRecord as Record<string, string> | undefined)?.["serial_number"] ||
    "";
  const bomFormat = cbom.bomFormat || cbom.bom_format || "CycloneDX";
  const specVersion =
    cbom.specVersion ||
    cbom.spec_version ||
    (metadataRecord as Record<string, string> | undefined)?.["spec_version"] ||
    "";
  const timestamp = (metadataRecord?.["timestamp"] as string | undefined) || "";

  if (error)
    return (
      <div className="state" role="alert">
        <h1>CBOM unavailable</h1>
        <p>{error}</p>
        <button className="button" onClick={() => setRetryKey((key) => key + 1)}>
          Try again
        </button>
      </div>
    );

  return (
    <>
      <section className="hero compact">
        <div>
          <p className="eyebrow">Cryptographic inventory</p>
          <h1>CBOM — Cryptographic Bill of Materials</h1>
          <p>
            {report?.repository ||
              metadataProperties["ecdat:repository:path"] ||
              "Current repository"}{" "}
            &middot; Scan #{report?.scan_id ?? metadataProperties["ecdat:scan:id"] ?? scanId ?? "—"}
          </p>
        </div>
        <div className="hero-actions">
          <button
            className={`button ${view === "components" ? "" : "secondary"}`}
            onClick={() => setView("components")}
          >
            Components ({pagination.total})
          </button>
          {graph && Object.keys(graph).length > 0 && (
            <button
              className={`button ${view === "graph" ? "" : "secondary"}`}
              onClick={() => setView("graph")}
            >
              Dependency graph
            </button>
          )}
          <button
            className={`button ${view === "raw" ? "" : "secondary"}`}
            onClick={() => setView("raw")}
          >
            Raw JSON
          </button>
          <button
            className="button secondary"
            onClick={handleExportCsv}
            disabled={exporting || pagination.total === 0}
            title="Export CBOM components as CSV"
          >
            {exporting ? "Exporting..." : "Export CSV"}
          </button>
        </div>
      </section>

      {/* Summary chips */}
      {!loading && (
        <section className="cbom-summary" aria-label="CBOM summary">
          <span className="cbom-summary-chip">
            <strong>{pagination.total}</strong> component{pagination.total !== 1 ? "s" : ""}
          </span>
          {Object.entries(typeCounts).map(([type, count]) => (
            <span key={type} className="cbom-summary-chip cbom-summary-chip--type">
              <strong>{count}</strong> {type}
            </span>
          ))}
          {vulnerabilities.length > 0 && (
            <span className="cbom-summary-chip cbom-summary-chip--vuln">
              <strong>{vulnerabilities.length}</strong> vuln
              {vulnerabilities.length !== 1 ? "s" : ""}
            </span>
          )}
          {services.length > 0 && (
            <span className="cbom-summary-chip">
              <strong>{services.length}</strong> service{services.length !== 1 ? "s" : ""}
            </span>
          )}
        </section>
      )}

      {loading && view === "components" ? (
        <>
          <div className="cbom-skeleton-header">
            {Array.from({ length: 4 }).map((_, i) => (
              <div className="cbom-skeleton-chip" key={i} />
            ))}
          </div>
          <div className="cbom-skeleton-grid">
            {Array.from({ length: SKELETON_COUNT }).map((_, i) => (
              <div className="cbom-skeleton-card" key={i}>
                <div className="cbom-skeleton-pulse" />
                <div className="cbom-skeleton-line short" />
                <div className="cbom-skeleton-line" />
                <div className="cbom-skeleton-line medium" />
                <div className="cbom-skeleton-line short" />
              </div>
            ))}
          </div>
        </>
      ) : (
        <>
          <div className="cbom-risk-bar">
            {(["CRITICAL", "HIGH", "MEDIUM", "LOW"] as const)
              .filter((label) => riskDistribution[label] > 0)
              .map((label) => (
                <span key={label} className={`cbom-risk-chip cbom-risk-${label.toLowerCase()}`}>
                  <span className="cbom-risk-count">{riskDistribution[label]}</span>
                  {label}
                </span>
              ))}
          </div>
          {view === "components" && components.length > 0 && (
            <div className="cbom-search-bar">
              <input
                aria-label="Filter components"
                placeholder="Search algorithm, location, category, or usage..."
                value={compFilter}
                onChange={(e) => {
                  setCompFilter(e.target.value);
                  setOffset(0);
                }}
              />
              {compFilter && (
                <button
                  className="cbom-search-clear"
                  onClick={() => {
                    setCompFilter("");
                    setOffset(0);
                  }}
                  aria-label="Clear filter"
                >
                  &times;
                </button>
              )}
            </div>
          )}
          <motion.section
            className="cbom-meta"
            variants={staggerContainer}
            initial="initial"
            animate="animate"
          >
            <motion.div variants={staggerItem} className="cbom-meta-card">
              <span className="cbom-meta-label">BOM format</span>
              <span className="cbom-meta-value">{bomFormat}</span>
            </motion.div>
            <motion.div variants={staggerItem} className="cbom-meta-card">
              <span className="cbom-meta-label">Spec version</span>
              <span className="cbom-meta-value">{specVersion}</span>
            </motion.div>
            <motion.div variants={staggerItem} className="cbom-meta-card">
              <span className="cbom-meta-label">Serial number</span>
              <span className="cbom-meta-value">{serial ? <code>{serial}</code> : "—"}</span>
            </motion.div>
            {timestamp && (
              <motion.div variants={staggerItem} className="cbom-meta-card">
                <span className="cbom-meta-label">Generated</span>
                <span className="cbom-meta-value">{formatDate(timestamp)}</span>
              </motion.div>
            )}
            {schemaValidation && (
              <motion.div
                variants={staggerItem}
                className={`cbom-meta-card ${schemaValidation.valid ? "cbom-schema-valid" : "cbom-schema-invalid"}`}
              >
                <span className="cbom-meta-label">Schema validation</span>
                <span className="cbom-meta-value">
                  {schemaValidation.valid ? (
                    <>Valid CycloneDX</>
                  ) : (
                    <span className="cbom-schema-errors">
                      {schemaValidation.errors.length} issue
                      {schemaValidation.errors.length !== 1 ? "s" : ""}
                    </span>
                  )}
                </span>
              </motion.div>
            )}
          </motion.section>

          {view === "components" && (
            <section className="cbom-section">
              <h2>
                Total {pagination.total.toLocaleString()} · Loaded{" "}
                {pagination.loaded.toLocaleString()} · Filtered{" "}
                {pagination.filtered.toLocaleString()} · Exported {exportedCount.toLocaleString()}
              </h2>
              {compFilter && filteredComponents.length === 0 && (
                <div className="empty-table-msg">
                  <strong>No components match "{compFilter}"</strong>
                  <span>Try a different search term.</span>
                </div>
              )}
              {components.length === 0 ? (
                <div className="empty-state">
                  <span className="empty-state-icon">&#9632;</span>
                  <p className="empty-state-eyebrow">CBOM</p>
                  <h1>No components found</h1>
                  <p>
                    This scan did not produce any cryptographic components. Run a full discovery
                    scan with dependency analysis enabled.
                  </p>
                </div>
              ) : (
                <motion.div
                  className="cbom-component-grid"
                  variants={staggerContainer}
                  initial="initial"
                  animate="animate"
                >
                  {filteredComponents.map((comp, i) => {
                    const componentProperties = readProperties(comp.properties);
                    const cryptoProperties = comp.cryptoProperties as JsonRecord | undefined;
                    const algorithmProperties = cryptoProperties?.algorithmProperties as
                      JsonRecord | undefined;
                    const legacyEvidence = (comp.evidence as Array<JsonRecord>) || [];
                    const standardEvidence: JsonRecord = {
                      algorithm:
                        algorithmProperties?.primitive ||
                        algorithmProperties?.algorithmFamily ||
                        comp.name,
                      category: componentProperties["ecdat:category"],
                      location: componentProperties["ecdat:location"],
                      usage: componentProperties["ecdat:usage"],
                      library: componentProperties["ecdat:library"],
                      confidence: Number(componentProperties["ecdat:confidence"]),
                      source: readStringArray(componentProperties["ecdat:evidence:sources"]),
                    };
                    const evidence = legacyEvidence.length ? legacyEvidence : [standardEvidence];
                    const hashes = (comp.hashes as Array<unknown>) || [];
                    const typeVal = (comp.type as string) || "library";
                    const nameVal = (comp.name as string) || `Component ${i + 1}`;
                    const descVal = (comp.description as string) || "";
                    const purlVal = comp.purl as string | undefined;
                    const riskLabel =
                      componentProperties["ecdat:risk-label"] ||
                      (() => {
                        const s = Number(componentProperties["ecdat:risk-score"] || 0);
                        return s >= 75 ? "CRITICAL" : s >= 50 ? "HIGH" : s >= 25 ? "MEDIUM" : "LOW";
                      })();
                    let riskClass = "cbom-risk-low";
                    if (riskLabel === "CRITICAL") riskClass = "cbom-risk-critical";
                    else if (riskLabel === "HIGH") riskClass = "cbom-risk-high";
                    else if (riskLabel === "MEDIUM") riskClass = "cbom-risk-medium";
                    const compKey = `${(comp.purl as string) || (comp.name as string) || "component"}-${i}`;
                    return (
                      <motion.article
                        className={`cbom-component-card ${riskClass}`}
                        key={compKey}
                        variants={staggerItem}
                      >
                        <div className="cbom-comp-header">
                          <span className="cbom-comp-type">{typeVal}</span>
                          {purlVal && <code className="cbom-purl">{purlVal}</code>}
                        </div>
                        <h3>{nameVal}</h3>
                        {descVal && <p>{descVal}</p>}
                        {evidence.length > 0 && (
                          <div className="cbom-evidence-list">
                            {evidence.map((ev, j) => {
                              const alg = ev.algorithm as string | undefined;
                              const cat = ev.category as string | undefined;
                              const conf = ev.confidence as number | undefined;
                              const loc = ev.location as string | undefined;
                              const usg = ev.usage as string | undefined;
                              const lib = ev.library as string | undefined;
                              const src = ev.source as string[] | undefined;
                              return (
                                <div key={j} className="cbom-evidence-item">
                                  <div className="cbom-evidence-row">
                                    {alg && <span className="cbom-algorithm">{alg}</span>}
                                    {cat && <span className="cbom-category">{cat}</span>}
                                    {conf != null && (
                                      <span className="cbom-confidence">
                                        {Math.round(conf * 100)}%
                                      </span>
                                    )}
                                  </div>
                                  <div className="cbom-evidence-detail">
                                    {loc && <span title={loc}>Location: {displayPath(loc)}</span>}
                                    {usg && <span>Usage: {usg}</span>}
                                    {lib && <span>Library: {lib}</span>}
                                    {src && <span>Sources: {src.join(", ")}</span>}
                                  </div>
                                </div>
                              );
                            })}
                          </div>
                        )}
                        {hashes.length > 0 && (
                          <div className="cbom-hashes">
                            <span className="cbom-meta-label">Hashes</span>
                            {hashes.map((h, k) => (
                              <code key={k} className="cbom-hash">
                                {JSON.stringify(h)}
                              </code>
                            ))}
                          </div>
                        )}
                      </motion.article>
                    );
                  })}
                </motion.div>
              )}
              {pagination.filtered > pagination.limit && (
                <nav aria-label="CBOM component pages">
                  <button
                    className="button secondary"
                    disabled={pagination.offset === 0}
                    onClick={() => setOffset(Math.max(0, pagination.offset - pagination.limit))}
                  >
                    Previous
                  </button>
                  <button
                    className="button secondary"
                    disabled={pagination.offset + pagination.loaded >= pagination.filtered}
                    onClick={() => setOffset(pagination.offset + pagination.limit)}
                  >
                    Next
                  </button>
                </nav>
              )}
            </section>
          )}

          {view === "graph" && (
            <section className="cbom-section">
              <h2>Dependency graph</h2>
              {graph && Object.keys(graph).length > 0 ? (
                <div className="cbom-graph">{renderGraph(graph)}</div>
              ) : (
                <div className="empty-state empty-state-variant">
                  <span className="empty-state-icon">&#9656;&#9632;</span>
                  <p className="empty-state-eyebrow">Dependency graph</p>
                  <h1>No graph data</h1>
                  <p>
                    The dependency graph requires a scan with SBOM or manifest data. Re-run the scan
                    with dependency analysis enabled.
                  </p>
                </div>
              )}
            </section>
          )}

          {view === "raw" && (
            <section className="cbom-section">
              <h2>Raw CBOM JSON</h2>
              <pre className="cbom-raw-json">{JSON.stringify(cbom, null, 2)}</pre>
            </section>
          )}

          {vulnerabilities.length > 0 && (
            <section className="cbom-section">
              <h2>Known vulnerabilities</h2>
              <div className="cbom-vuln-list">
                {(vulnerabilities as Array<Record<string, unknown>>).map((v, i) => (
                  <div className="cbom-vuln-item" key={(v.id as string) || `vuln-${i}`}>
                    <span className="cbom-vuln-id">{(v.id as string) || `VULN-${i}`}</span>
                    <span
                      className={`cbom-vuln-severity sev-${(v.severity as string) || "unknown"}`}
                    >
                      {(v.severity as string) || "unknown"}
                    </span>
                    <span>{(v.description as string) || "No description available."}</span>
                  </div>
                ))}
              </div>
            </section>
          )}

          {services.length > 0 && (
            <section className="cbom-section">
              <h2>Services</h2>
              <div className="cbom-service-list">
                {(services as Array<Record<string, unknown>>).map((s, i) => (
                  <div className="cbom-service-item" key={(s.name as string) || `svc-${i}`}>
                    <strong>{(s.name as string) || `Service ${i + 1}`}</strong>
                    <span>{(s.description as string) || "—"}</span>
                  </div>
                ))}
              </div>
            </section>
          )}
        </>
      )}
    </>
  );
}

function renderGraph(data: import("../types").EvidenceGraphResponse | null): React.ReactNode {
  if (!data) return <p className="muted">No graph data.</p>;
  const nodes = data.nodes;
  const edges = data.edges;

  if (nodes.length === 0) {
    const entries = Object.entries(data as unknown as Record<string, unknown>).filter(
      ([k]) => k !== "nodes" && k !== "edges",
    );
    if (entries.length === 0) return <p className="muted">No graph data.</p>;
    return (
      <div className="cbom-graph-raw">
        {entries.map(([k, v]) => (
          <div key={k}>
            <strong>{k}:</strong> {JSON.stringify(v)}
          </div>
        ))}
      </div>
    );
  }

  const nodeMap = new Map(nodes.map((n, i) => [String(n.id ?? i), n]));
  const edgesBySource = new Map<string, typeof edges>();
  edges.forEach((edge) => {
    const source = String(edge.source);
    edgesBySource.set(source, [...(edgesBySource.get(source) || []), edge]);
  });

  return (
    <div className="cbom-graph-visual">
      {nodes.map((node, i) => {
        const deps = edgesBySource.get(String(node.id ?? i)) || [];
        const nodeKey = String(node.id ?? node.label ?? `node-${i}`);
        return (
          <div className="cbom-graph-node" key={nodeKey}>
            <div className="cbom-node-card">
              <strong>{(node.label as string) || `Node ${node.id ?? i}`}</strong>
              {node.type ? <span className="cbom-node-type">{node.type as string}</span> : null}
            </div>
            {deps.length > 0 && (
              <div className="cbom-node-deps">
                {deps.map((d, _j) => {
                  const target = nodeMap.get(String(d.target));
                  return (
                    <div key={`${String(d.source)}-${String(d.target)}`} className="cbom-dep-edge">
                      {target ? (target.label as string) || `Node ${d.target}` : `→ ${d.target}`}
                    </div>
                  );
                })}
              </div>
            )}
          </div>
        );
      })}
    </div>
  );
}

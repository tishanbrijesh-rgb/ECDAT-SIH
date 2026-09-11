// CBOM (Cryptographic Bill of Materials) viewer.
import { useState, useEffect, useMemo } from "react";
import { useSearchParams } from "react-router-dom";
import { motion } from "framer-motion";
import { getCbom, getEvidenceGraph, getRiskReport } from "../api/client";
import { formatDate } from "../utils/format";
import type { CbomEntry } from "../types";

// ── Stagger variants ───────────────────────────────────────────
const staggerContainer = {
  animate: { transition: { staggerChildren: 0.05, delayChildren: 0.05 } },
};
const staggerItem = {
  initial: { opacity: 0, y: 8 },
  animate: { opacity: 1, y: 0, transition: { duration: 0.25, ease: [0.25, 0.1, 0.25, 1] } },
};

const EMPTY_CBOM: CbomEntry = {
  bom_format: "",
  spec_version: "",
  serial_number: "",
  metadata: {},
  components: [],
  vulnerabilities: [],
  dependencies: [],
  services: [],
};

const SKELETON_COUNT = 6;

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

  const [cbom, setCbom] = useState<CbomEntry>(EMPTY_CBOM);
  const [graph, setGraph] = useState<Record<string, unknown> | null>(null);
  const [report, setReport] = useState<{
    title: string;
    scan_id: number;
    repository: string;
  } | null>(null);
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(true);
  const [view, setView] = useState<"components" | "graph" | "raw">("components");
  const [retryKey, setRetryKey] = useState(0);

  useEffect(() => {
    let cancelled = false;
    setCbom(EMPTY_CBOM);
    setGraph(null);
    setReport(null);
    setError("");
    setLoading(true);
    Promise.all([
      getCbom(scanId),
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
  }, [scanId, retryKey]);

  const components = useMemo(() => {
    const c = cbom.components || [];
    return c as Array<Record<string, unknown>>;
  }, [cbom]);

  const riskDistribution = useMemo(() => {
    const counts = { CRITICAL: 0, HIGH: 0, MEDIUM: 0, LOW: 0 };
    for (const comp of components) {
      const cp = comp.properties as Array<{ name: string; value: string }> | undefined;
      const confEntry = cp?.find((p) => p.name === "ecdat:confidence");
      const conf = confEntry ? Number(confEntry.value) : 0.5;
      if (conf < 0.4) counts.CRITICAL++;
      else if (conf < 0.6) counts.HIGH++;
      else if (conf < 0.8) counts.MEDIUM++;
      else counts.LOW++;
    }
    return counts;
  }, [components]);

  const vulnerabilities = cbom.vulnerabilities || [];
  const services = cbom.services || [];
  const visibleComponents = components.slice(0, 250);

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
            Components ({components.length})
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
        </div>
      </section>

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
            {(["CRITICAL", "HIGH", "MEDIUM", "LOW"] as const).map((label) => (
              <span key={label} className={`cbom-risk-chip cbom-risk-${label.toLowerCase()}`}>
                <span className="cbom-risk-count">{riskDistribution[label]}</span>
                {label}
              </span>
            ))}
          </div>
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
          </motion.section>

          {view === "components" && (
            <section className="cbom-section">
              <h2>Components ({components.length})</h2>
              {components.length > visibleComponents.length && (
                <div className="callout callout-amber">
                  Showing the first {visibleComponents.length} components to keep this view
                  responsive. Raw JSON retains all {components.length} components.
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
                  {visibleComponents.map((comp, i) => {
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
                    const confidenceVal = Number(componentProperties["ecdat:confidence"] || 0);
                    let riskClass = "cbom-risk-low";
                    if (confidenceVal < 0.4) riskClass = "cbom-risk-critical";
                    else if (confidenceVal < 0.6) riskClass = "cbom-risk-high";
                    else if (confidenceVal < 0.8) riskClass = "cbom-risk-medium";
                    return (
                      <motion.article
                        className={`cbom-component-card ${riskClass}`}
                        key={i}
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
                                    {loc && <span>Location: {loc}</span>}
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

          {vulnerabilities.length > 0 && view === "components" && (
            <section className="cbom-section">
              <h2>Known vulnerabilities</h2>
              <div className="cbom-vuln-list">
                {(vulnerabilities as Array<Record<string, unknown>>).map((v, i) => (
                  <div className="cbom-vuln-item" key={i}>
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

          {services.length > 0 && view === "components" && (
            <section className="cbom-section">
              <h2>Services</h2>
              <div className="cbom-service-list">
                {(services as Array<Record<string, unknown>>).map((s, i) => (
                  <div className="cbom-service-item" key={i}>
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

function renderGraph(data: Record<string, unknown>): React.ReactNode {
  const nodes = (data.nodes as Array<Record<string, unknown>>) || [];
  const edges = (data.edges as Array<{ source: string | number; target: string | number }>) || [];

  if (nodes.length === 0) {
    const entries = Object.entries(data).filter(([k]) => k !== "nodes" && k !== "edges");
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
        return (
          <div className="cbom-graph-node" key={i}>
            <div className="cbom-node-card">
              <strong>{(node.label as string) || `Node ${node.id ?? i}`}</strong>
              {node.type ? <span className="cbom-node-type">{node.type as string}</span> : null}
            </div>
            {deps.length > 0 && (
              <div className="cbom-node-deps">
                {deps.map((d, j) => {
                  const target = nodeMap.get(String(d.target));
                  return (
                    <div key={j} className="cbom-dep-edge">
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

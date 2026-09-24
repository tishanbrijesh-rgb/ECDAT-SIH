// Evidence graph page — renders the dependency graph for a scan.
import { Suspense, useEffect, useState } from "react";
import { useSearchParams, Link } from "react-router-dom";
import { getEvidenceGraph } from "../api/client";
import { EvidenceGraph } from "../components/EvidenceGraph";
import type { EvidenceGraphResponse } from "../types";

function LoadingGraph() {
  return (
    <div className="state" role="status" aria-live="polite">
      <span className="spinner" aria-hidden="true" />
      <p>Loading evidence graph…</p>
    </div>
  );
}

function EmptyState({ scanId }: { scanId?: number }) {
  return (
    <div className="panel" style={{ padding: "var(--sp-6)", textAlign: "center" }}>
      <p className="muted">
        No evidence graph data{scanId ? ` for scan #${scanId}` : ""}. Run a scan to build the
        dependency graph.
      </p>
      <Link className="button" to={`/scans${scanId ? `?scan_id=${scanId}` : ""}`}>
        View scans
      </Link>
    </div>
  );
}

function EvidenceGraphPageInner() {
  const [params] = useSearchParams();
  const scanId = params.get("scan_id") ? Number(params.get("scan_id")) : undefined;
  const [data, setData] = useState<EvidenceGraphResponse | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let cancelled = false;
    getEvidenceGraph(scanId)
      .then((res) => {
        if (!cancelled) setData(res);
      })
      .catch((err) => {
        if (!cancelled) setError(err.message);
      });
    return () => {
      cancelled = true;
    };
  }, [scanId]);

  if (error) {
    return (
      <div className="panel" style={{ padding: "var(--sp-6)" }}>
        <h2>Graph error</h2>
        <p className="muted">{error}</p>
      </div>
    );
  }

  if (!data) {
    return <LoadingGraph />;
  }

  if (data.nodes.length === 0) {
    return <EmptyState scanId={scanId} />;
  }

  return (
    <div>
      <div className="hero">
        <div>
          <p className="eyebrow">Evidence graph</p>
          <h1>Dependency Graph</h1>
          <p className="muted">
            Scan #{data.scan_id} — {data.nodes.length} nodes, {data.edges.length} edges
          </p>
        </div>
      </div>
      <EvidenceGraph data={data} />
    </div>
  );
}

export default function EvidenceGraphPageSuspense() {
  return (
    <Suspense fallback={<LoadingGraph />}>
      <EvidenceGraphPageInner />
    </Suspense>
  );
}

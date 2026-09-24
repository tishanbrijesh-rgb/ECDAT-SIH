import { useEffect, useMemo, useState } from "react";
import { Link } from "react-router-dom";

import { getScans } from "../api/client";
import type { ScanJob } from "../types";

const terminal = new Set(["completed", "failed", "cancelled", "timed_out"]);

const duration = (milliseconds: number) => {
  if (!milliseconds) return "—";
  if (milliseconds < 1000) return `${milliseconds} ms`;
  return `${(milliseconds / 1000).toFixed(milliseconds < 10_000 ? 1 : 0)} s`;
};

export default function ScanHistoryPage() {
  const [scans, setScans] = useState<ScanJob[]>([]);
  const [status, setStatus] = useState("all");
  const [query, setQuery] = useState("");
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");

  useEffect(() => {
    let active = true;
    const load = () => {
      getScans()
        .then((items) => {
          if (active) {
            setScans(items);
            setError("");
          }
        })
        .catch(() => active && setError("Scan history could not be loaded."))
        .finally(() => active && setLoading(false));
    };
    load();
    const interval = window.setInterval(load, 2000);
    return () => {
      active = false;
      window.clearInterval(interval);
    };
  }, []);

  const visible = useMemo(() => {
    const needle = query.trim().toLowerCase();
    return scans.filter((scan) => {
      const matchesStatus = status === "all" || scan.status === status;
      const matchesQuery =
        !needle ||
        scan.repo_path.toLowerCase().includes(needle) ||
        String(scan.id).includes(needle);
      return matchesStatus && matchesQuery;
    });
  }, [query, scans, status]);

  return (
    <div className="scan-history-page">
      <header className="scan-history-header">
        <div>
          <p className="eyebrow">Operations</p>
          <h1>Scan history</h1>
          <p>Inspect results and execution evidence from every repository scan.</p>
        </div>
        <Link className="button primary" to="/scan">
          New scan
        </Link>
      </header>

      <section className="scan-history-toolbar" aria-label="Scan history filters">
        <input
          type="search"
          value={query}
          onChange={(event) => setQuery(event.target.value)}
          placeholder="Search path or scan ID"
          aria-label="Search scan history"
        />
        <select
          value={status}
          onChange={(event) => setStatus(event.target.value)}
          aria-label="Filter by status"
        >
          <option value="all">All statuses</option>
          <option value="running">Running</option>
          <option value="queued">Queued</option>
          <option value="completed">Completed</option>
          <option value="failed">Failed</option>
          <option value="cancelled">Cancelled</option>
          <option value="timed_out">Timed out</option>
        </select>
        <span>
          {visible.length} of {scans.length} scans
        </span>
      </section>

      {loading ? (
        <div className="state">
          <span className="spinner" />
          <p>Loading scan history…</p>
        </div>
      ) : null}
      {error ? (
        <div className="error-banner" role="alert">
          {error}
        </div>
      ) : null}
      {!loading && !error && visible.length === 0 ? (
        <div className="empty-state">
          <h2>No matching scans</h2>
          <p>Adjust the filters or start a new scan.</p>
        </div>
      ) : null}

      {!loading && visible.length > 0 ? (
        <div className="scan-history-table-wrap">
          <table className="scan-history-table">
            <thead>
              <tr>
                <th>Scan</th>
                <th>Repository</th>
                <th>Status</th>
                <th>Files</th>
                <th>Findings</th>
                <th>Supported-file coverage</th>
                <th>Duration</th>
                <th>
                  <span className="sr-only">Action</span>
                </th>
              </tr>
            </thead>
            <tbody>
              {visible.map((scan) => (
                <tr key={scan.id}>
                  <td>
                    <strong>#{scan.id}</strong>
                  </td>
                  <td>
                    <span className="scan-history-path" title={scan.repo_path}>
                      {scan.repo_path}
                    </span>
                  </td>
                  <td>
                    <span className={`scan-history-status status-${scan.status}`}>
                      {terminal.has(scan.status)
                        ? scan.status.replace("_", " ")
                        : `${scan.status}…`}
                    </span>
                  </td>
                  <td>
                    {scan.scanned_files.toLocaleString()} / {scan.in_scope_files.toLocaleString()}
                  </td>
                  <td>{scan.assets_found.toLocaleString()}</td>
                  <td>{scan.coverage_pct}%</td>
                  <td>{duration(scan.duration_ms)}</td>
                  <td>
                    <Link className="scan-history-inspect" to={`/scans/${scan.id}`}>
                      Inspect <span aria-hidden="true">→</span>
                    </Link>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      ) : null}
    </div>
  );
}

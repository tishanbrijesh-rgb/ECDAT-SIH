// Repository scan launcher with job progress, coverage, and history.
import { useEffect, useState } from "react";
import { Link, useNavigate } from "react-router-dom";
import { getScan, getScans, scanRepo } from "../api/client";
import type { ScanJob } from "../types";

export default function ScanPage() {
  const [path, setPath] = useState("/test-repo");
  const [scanId, setScanId] = useState<number>();
  const [job, setJob] = useState<ScanJob>();
  const [history, setHistory] = useState<ScanJob[]>([]);
  const [error, setError] = useState("");
  const navigate = useNavigate();
  useEffect(() => {
    getScans()
      .then(setHistory)
      .catch(() => undefined);
  }, []);
  useEffect(() => {
    if (!scanId) return;
    const poll = () =>
      getScan(scanId)
        .then((current) => {
          setJob(current);
          if (current.status === "completed")
            setTimeout(() => navigate(`/assets?scan_id=${scanId}`), 900);
          else if (current.status !== "failed") timer = setTimeout(poll, 700);
        })
        .catch((e) => setError(String(e)));
    let timer = setTimeout(poll, 300);
    return () => clearTimeout(timer);
  }, [scanId, navigate]);
  const start = async () => {
    setError("");
    setJob(undefined);
    try {
      const result = await scanRepo(path);
      setScanId(result.scan_id);
    } catch (e) {
      setError(String(e));
    }
  };
  const running = !!scanId && job?.status !== "completed" && job?.status !== "failed";
  return (
    <>
      <section className="scan-layout">
        <div className="scan-copy">
          <p className="eyebrow">Privacy-first local analysis</p>
          <h1>Build a trustworthy cryptographic inventory.</h1>
          <p>
            Four independent collectors inspect source structure, auditable rules, dependencies, and
            certificates. ECDAT then correlates evidence, measures coverage, calculates risk, and
            creates migration guidance.
          </p>
          <ol>
            <li>
              <span>01</span>Enumerate scope
            </li>
            <li>
              <span>02</span>Collect independent evidence
            </li>
            <li>
              <span>03</span>Correlate and score assurance
            </li>
            <li>
              <span>04</span>Prioritize PQC migration
            </li>
          </ol>
        </div>
        <div className="scan-card panel">
          <h2>Start discovery scan</h2>
          <label>
            Repository path
            <input value={path} onChange={(e) => setPath(e.target.value)} disabled={running} />
            <small>Use /test-repo for the bundled controlled dataset.</small>
          </label>
          <button className="button wide" onClick={() => void start()} disabled={!path || running}>
            {running ? "Scanning securely…" : "Run discovery scan"}
          </button>
          {scanId && (
            <div className="scan-progress">
              <div className="progress-track">
                <i className={job?.status === "completed" ? "done" : ""} />
              </div>
              <div>
                <strong>{job?.status || "queued"}</strong>
                <span>Scan #{scanId}</span>
              </div>
              {job?.coverage_pct ? (
                <small>
                  {job.scanned_files}/{job.in_scope_files} supported files · {job.coverage_pct}%
                  coverage
                </small>
              ) : (
                <small>Preparing collectors and enumerating scope…</small>
              )}
            </div>
          )}
          {error && <div className="callout error">{error}</div>}
        </div>
      </section>
      <section className="history">
        <div className="panel-title">
          <h2>Recent scans</h2>
          <p>Coverage and assurance history</p>
        </div>
        <div className="panel table-wrap">
          <table>
            <thead>
              <tr>
                <th>ID</th>
                <th>Repository</th>
                <th>Status</th>
                <th>Assets</th>
                <th>Coverage</th>
                <th>Duration</th>
                <th />
              </tr>
            </thead>
            <tbody>
              {history.map((scan) => (
                <tr key={scan.id}>
                  <td>#{scan.id}</td>
                  <td className="path">{scan.repo_path}</td>
                  <td>
                    <span className={`status status-${scan.status}`}>{scan.status}</span>
                  </td>
                  <td>{scan.assets_found}</td>
                  <td>{scan.coverage_pct}%</td>
                  <td>{scan.duration_ms} ms</td>
                  <td>
                    {scan.status === "completed" && (
                      <Link to={`/assets?scan_id=${scan.id}`}>Open →</Link>
                    )}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </section>
    </>
  );
}

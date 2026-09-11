// Repository scan launcher with job progress, coverage, and history.
import { useEffect, useState, useCallback } from "react";
import { Link, useNavigate } from "react-router-dom";
import { getScan, getScans, scanRepo, canWrite, cancelScan } from "../api/client";
import { ConfirmDialog } from "../components/ConfirmDialog";
import { useToast } from "../components/Toast";
import { relativeTime, formatDate } from "../utils/format";
import type { ScanJob } from "../types";

const terminal = (status?: string) =>
  ["completed", "failed", "cancelled", "timed_out"].includes(status || "");

const STATUS_CLASS: Record<string, string> = {
  completed: "status-completed",
  failed: "status-failed",
  running: "status-running",
  cancelled: "status-cancelled",
  timed_out: "status-timed_out",
  queued: "status-running",
};

function formatDuration(ms: number): string {
  if (ms < 1000) return `${ms} ms`;
  const s = Math.floor(ms / 1000);
  if (s < 60) return `${s} s`;
  const m = Math.floor(s / 60);
  const rem = s % 60;
  return rem ? `${m}m ${rem}s` : `${m}m`;
}

export default function ScanPage() {
  const [path, setPath] = useState("/test-repo");
  const [pathError, setPathError] = useState("");
  const [scanId, setScanId] = useState<number>();
  const [job, setJob] = useState<ScanJob>();
  const [history, setHistory] = useState<ScanJob[]>([]);
  const [error, setError] = useState("");
  const [starting, setStarting] = useState(false);
  const [cancelling, setCancelling] = useState(false);
  const [showCancelConfirm, setShowCancelConfirm] = useState(false);
  const navigate = useNavigate();
  const toast = useToast();

  const validatePath = useCallback((raw: string): string => {
    const trimmed = raw.trim();
    if (!trimmed) return "Repository path is required.";
    if (/[\u0000-\u001f\u007f]/.test(raw)) {
      return "Path must not contain control characters.";
    }
    return "";
  }, []);

  const handlePathChange = useCallback(
    (e: React.ChangeEvent<HTMLInputElement>) => {
      const next = e.target.value;
      setPath(next);
      if (pathError) setPathError(validatePath(next));
    },
    [pathError, validatePath],
  );

  const handlePathBlur = useCallback(() => {
    setPathError(validatePath(path));
  }, [path, validatePath]);
  useEffect(() => {
    getScans()
      .then(setHistory)
      .catch(() => undefined);
  }, []);
  useEffect(() => {
    if (!scanId) return;
    let cancelled = false;
    let timer: ReturnType<typeof setTimeout> | undefined;

    const poll = async () => {
      if (cancelled) return;
      try {
        const current = await getScan(scanId);
        if (cancelled) return;
        setError("");
        setJob(current);
        if (current.status === "completed") {
          toast.success(`Scan #${scanId} completed — ${current.assets_found} assets found`);
          timer = setTimeout(() => navigate(`/assets?scan_id=${scanId}`), 900);
        } else if (!terminal(current.status)) {
          timer = setTimeout(poll, 700);
        } else {
          getScans()
            .then(setHistory)
            .catch(() => undefined);
        }
      } catch {
        if (cancelled) return;
        setError(
          "Status connection interrupted. Retrying automatically; do not start another scan.",
        );
        timer = setTimeout(poll, 2000);
      }
    };

    timer = setTimeout(poll, 0);

    return () => {
      cancelled = true;
      if (timer) clearTimeout(timer);
    };
  }, [scanId, navigate]);
  const start = async () => {
    if (!canWrite() || starting) return;
    const validationError = validatePath(path);
    if (validationError) {
      setPathError(validationError);
      return;
    }
    setPathError("");
    setStarting(true);
    setCancelling(false);
    setError("");
    setScanId(undefined);
    setJob(undefined);
    try {
      const result = await scanRepo(path.trim());
      setScanId(result.scan_id);
    } catch (e) {
      setError(String(e));
    } finally {
      setStarting(false);
    }
  };
  const cancel = async () => {
    if (!scanId || cancelling || !canWrite()) return;
    setCancelling(true);
    try {
      await cancelScan(scanId);
    } catch (e) {
      setError(String(e));
      setCancelling(false);
    }
  };
  const askCancel = useCallback(() => setShowCancelConfirm(true), []);
  const monitor = useCallback((scan: ScanJob) => {
    setScanId(scan.id);
    setJob(scan);
    setCancelling(false);
  }, []);
  const running = starting || (!!scanId && !terminal(job?.status));

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
        <fieldset className="scan-card panel" disabled={!canWrite()}>
          <h2>Start discovery scan</h2>
          {!canWrite() && (
            <p>Read-only access. An administrator or security analyst can start scans.</p>
          )}
          <label htmlFor="scan-path">
            Repository path
            <input
              id="scan-path"
              value={path}
              onChange={handlePathChange}
              onBlur={handlePathBlur}
              disabled={running}
              aria-invalid={Boolean(pathError)}
              aria-describedby={pathError ? "scan-path-error" : "scan-path-hint"}
              autoComplete="off"
            />
            <small id="scan-path-hint">Use /test-repo for the bundled controlled dataset.</small>
            {pathError && (
              <small id="scan-path-error" className="field-error" role="alert">
                {pathError}
              </small>
            )}
          </label>
          <button
            className="button wide"
            onClick={() => void start()}
            disabled={!path || !!pathError || starting || running}
          >
            {starting ? "Starting scan…" : "Run discovery scan"}
          </button>
          {scanId && running && (
            <button className="button" onClick={askCancel} disabled={cancelling}>
              {cancelling ? "Cancellation requested…" : "Cancel scan"}
            </button>
          )}
          {scanId && (
            <div className="scan-progress" role="status" aria-live="polite">
              <div className="progress-track">
                <i className={job?.status === "completed" ? "done" : "loading"} />
              </div>
              <div className="scan-progress-info">
                <div className="scan-status-indicator">
                  {job?.status === "running" && <span className="scan-radar" aria-hidden="true" />}
                  <strong>{job?.status || "queued"}</strong>
                </div>
                <span>Scan #{scanId}</span>
              </div>
              {terminal(job?.status) && job?.status !== "completed" ? (
                <small>
                  {job?.blind_spots.join("; ") || "Scan stopped. Results are incomplete."}
                </small>
              ) : running && job?.collector_stats._files_total !== undefined ? (
                <small>
                  {job.collector_stats._files_processed}/{job.collector_stats._files_total}{" "}
                  supported files processed
                  {job.collector_stats._files_processed === job.collector_stats._files_total
                    ? " · Correlating and saving results…"
                    : " · Collecting evidence…"}
                </small>
              ) : job?.status === "completed" ? (
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
        </fieldset>
        <ConfirmDialog
          open={showCancelConfirm}
          title="Cancel scan?"
          message="Any collected evidence will be discarded. The scan status will be marked as cancelled."
          confirmLabel="Cancel scan"
          danger
          onConfirm={async () => {
            setShowCancelConfirm(false);
            await cancel();
          }}
          onCancel={() => setShowCancelConfirm(false)}
        />
      </section>
      <section className="history">
        <div className="panel-title">
          <h2>Recent scans</h2>
          <p>Coverage and assurance history</p>
        </div>
        <div className="panel table-wrap">
          <table aria-label="Scan history">
            <thead>
              <tr>
                <th>ID</th>
                <th>Repository</th>
                <th>Status</th>
                <th>Assets</th>
                <th>Coverage</th>
                <th>Duration</th>
                <th>Started</th>
                <th />
              </tr>
            </thead>
            <tbody>
              {history.map((scan) => (
                <tr key={scan.id}>
                  <td>#{scan.id}</td>
                  <td className="path">{scan.repo_path}</td>
                  <td>
                    <span className={`status ${STATUS_CLASS[scan.status] || ""}`}>
                      {scan.status}
                    </span>
                  </td>
                  <td>{scan.assets_found}</td>
                  <td>{scan.coverage_pct}%</td>
                  <td>{formatDuration(scan.duration_ms)}</td>
                  <td>
                    {scan.started_at ? (
                      <small title={formatDate(scan.started_at)}>
                        {relativeTime(scan.started_at)}
                      </small>
                    ) : (
                      "—"
                    )}
                  </td>
                  <td>
                    {scan.status === "completed" && (
                      <Link className="row-link" to={`/assets?scan_id=${scan.id}`}>
                        Open results →
                      </Link>
                    )}
                    {!terminal(scan.status) && (
                      <button
                        className="button secondary"
                        style={{ padding: "6px 12px", fontSize: 12, marginRight: 6 }}
                        onClick={() => monitor(scan)}
                      >
                        Monitor
                      </button>
                    )}
                  </td>
                </tr>
              ))}
              {!history.length && !error && (
                <tr>
                  <td colSpan={8} className="empty-table-msg">
                    <span className="empty-data-icon">&#9656;&#9632;</span>
                    <strong>No scan history yet</strong>
                    <span>
                      Run a discovery scan from the panel above to build your cryptographic
                      inventory.
                    </span>
                  </td>
                </tr>
              )}
            </tbody>
          </table>
        </div>
      </section>
    </>
  );
}

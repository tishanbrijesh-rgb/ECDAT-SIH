// src/api/client.ts — thin HTTP client for ECDAT backend API

const API_BASE: string = (import.meta as any).env?.VITE_API_URL || "http://localhost:8000";
const SESSION_STORAGE_KEY = "ecdat-session";

export class ApiError extends Error {
  constructor(
    message: string,
    readonly status: number,
  ) {
    super(message);
    this.name = "ApiError";
  }
}
let accessToken = "";
let role = "";
let expiresAt = 0;
let sessionExpiredOnLoad = false;
let expiryTimer: ReturnType<typeof setTimeout> | undefined;
export const SESSION_EXPIRED = "ecdat-session-expired";
export const canWrite = () => role === "admin" || role === "security_analyst";

interface StoredSession {
  accessToken: string;
  role: string;
  expiresAt: number;
}

function readStoredSession(): StoredSession | null {
  try {
    const raw = window.sessionStorage.getItem(SESSION_STORAGE_KEY);
    if (!raw) return null;
    const value = JSON.parse(raw) as Partial<StoredSession>;
    if (
      typeof value.accessToken !== "string" ||
      !value.accessToken ||
      typeof value.role !== "string" ||
      typeof value.expiresAt !== "number"
    ) {
      window.sessionStorage.removeItem(SESSION_STORAGE_KEY);
      return null;
    }
    return value as StoredSession;
  } catch {
    return null;
  }
}

function persistSession() {
  try {
    window.sessionStorage.setItem(
      SESSION_STORAGE_KEY,
      JSON.stringify({ accessToken, role, expiresAt }),
    );
  } catch {
    // The in-memory session still works if storage is unavailable.
  }
}

function clearStoredSession() {
  try {
    window.sessionStorage.removeItem(SESSION_STORAGE_KEY);
  } catch {
    // Storage can be unavailable in privacy-restricted browser contexts.
  }
}

function scheduleExpiry() {
  clearTimeout(expiryTimer);
  const remaining = expiresAt * 1000 - Date.now();
  if (remaining <= 0) {
    expireSession();
    return;
  }
  expiryTimer = setTimeout(expireSession, remaining);
}

export function logout() {
  clearTimeout(expiryTimer);
  expiryTimer = undefined;
  accessToken = "";
  role = "";
  expiresAt = 0;
  clearStoredSession();
}
function expireSession() {
  if (!accessToken) return;
  logout();
  window.dispatchEvent(
    new CustomEvent(SESSION_EXPIRED, {
      detail: "Your session expired. Please sign in again.",
    }),
  );
}
export const hasSession = () => Boolean(accessToken && expiresAt * 1000 > Date.now());
export const getInitialSessionExpiry = () =>
  sessionExpiredOnLoad ? "Your session expired. Please sign in again." : "";

export async function restoreSession(): Promise<boolean> {
  if (!hasSession()) return false;
  try {
    const response = await authenticatedFetch("/api/auth/me");
    if (response.status >= 500) return hasSession();
    if (!response.ok) {
      logout();
      return false;
    }
    const account = (await response.json()) as { role?: string };
    if (typeof account.role === "string") {
      role = account.role;
      persistSession();
    }
    return true;
  } catch {
    // Keep a locally valid session during a temporary connection failure. The
    // normal request path will still reject it if the server no longer accepts it.
    return hasSession();
  }
}

export async function login(username: string, password: string) {
  const result = await _post<{ access_token: string; role: string; expires_at: number }>(
    "/api/auth/login",
    { username, password },
  );
  logout();
  accessToken = result.access_token;
  role = result.role;
  expiresAt = result.expires_at;
  persistSession();
  scheduleExpiry();
}
async function authenticatedFetch(path: string, init: RequestInit = {}) {
  const requestToken = accessToken;
  const response = await fetch(`${API_BASE}${path}`, {
    ...init,
    headers: { ...init.headers, ...authHeaders() },
  });
  if (
    response.status === 401 &&
    path !== "/api/auth/login" &&
    requestToken &&
    requestToken === accessToken
  )
    expireSession();
  if (response.status === 403)
    throw new Error("Your account does not have permission for this action.");
  return response;
}
const authHeaders = (): Record<string, string> =>
  accessToken ? { Authorization: `Bearer ${accessToken}` } : {};
export async function downloadReport(path: string, filename: string) {
  const response = await authenticatedFetch(path);
  if (!response.ok) throw new Error(`Download failed: ${response.status}`);
  const url = URL.createObjectURL(await response.blob());
  const link = document.createElement("a");
  link.href = url;
  link.download = filename;
  document.body.appendChild(link);
  link.click();
  link.remove();
  setTimeout(() => URL.revokeObjectURL(url), 30000);
}

async function _get<T>(path: string): Promise<T> {
  const res = await authenticatedFetch(path);
  if (!res.ok) throw new Error(`GET ${path} → ${res.status}`);
  return res.json() as Promise<T>;
}

async function _post<T>(path: string, body: unknown): Promise<T> {
  const res = await authenticatedFetch(path, {
    method: "POST",
    headers: { "Content-Type": "application/json", ...authHeaders() },
    body: JSON.stringify(body),
  });
  if (!res.ok) throw new ApiError(`POST ${path} → ${res.status}`, res.status);
  return res.json() as Promise<T>;
}

async function _patch<T>(path: string, body: unknown): Promise<T> {
  const res = await authenticatedFetch(path, {
    method: "PATCH",
    headers: { "Content-Type": "application/json", ...authHeaders() },
    body: JSON.stringify(body),
  });
  if (!res.ok) throw new Error(`PATCH ${path} → ${res.status}`);
  return res.json() as Promise<T>;
}

export const API_BASE_URL = API_BASE;

export async function scanRepo(repoPath: string): Promise<{ scan_id: number; status: string }> {
  return _post("/api/scan", { repo_path: repoPath });
}

export async function getScans(): Promise<import("../types").ScanJob[]> {
  return _get("/api/scans");
}

export async function getScan(id: number): Promise<import("../types").ScanJob> {
  return _get(`/api/scans/${id}`);
}

export async function cancelScan(id: number): Promise<{ status: string }> {
  return _post(`/api/scans/${id}/cancel`, {});
}

export async function getAssets(
  scanJobId?: number,
  options: {
    limit?: number;
    offset?: number;
    query?: string;
    risk?: "CRITICAL" | "HIGH" | "MEDIUM" | "LOW";
    quantum?: boolean;
    sort?: "priority" | "confidence" | "algorithm";
    signal?: AbortSignal;
  } = {},
): Promise<{ items: import("../types").CryptoAsset[]; total: number }> {
  const qs = new URLSearchParams();
  if (scanJobId != null) qs.set("scan_job_id", String(scanJobId));
  if (options.limit != null) qs.set("limit", String(options.limit));
  if (options.offset != null) qs.set("offset", String(options.offset));
  if (options.query?.trim()) qs.set("q", options.query.trim());
  if (options.risk) qs.set("risk", options.risk);
  if (options.quantum != null) qs.set("quantum", String(options.quantum));
  if (options.sort) qs.set("sort", options.sort);
  const queryString = qs.toString();
  const res = await authenticatedFetch(`/api/assets${queryString ? `?${queryString}` : ""}`, {
    signal: options.signal,
  });
  if (!res.ok) throw new Error(`GET /api/assets → ${res.status}`);
  const total = parseInt(res.headers.get("X-Total-Count") || "0", 10);
  const items = (await res.json()) as import("../types").CryptoAsset[];
  return { items, total };
}

export async function getAsset(id: number): Promise<import("../types").CryptoAsset> {
  return _get(`/api/assets/${id}`);
}

export async function updateAsset(
  id: number,
  data: Partial<
    Pick<
      import("../types").CryptoAsset,
      | "business_criticality"
      | "data_sensitivity"
      | "data_lifetime_years"
      | "migration_time_years"
      | "threat_horizon_years"
      | "exposure"
      | "migration_effort"
    >
  >,
): Promise<import("../types").CryptoAsset> {
  return _patch(`/api/assets/${id}`, data);
}

export const getEvaluation = (scanId?: number) =>
  _get<import("../types").Evaluation>(`/api/evaluation${scanId ? `?scan_id=${scanId}` : ""}`);
export const getRiskReport = (scanId?: number) =>
  _get<import("../types").RiskReport>(`/api/reports/risk${scanId ? `?scan_id=${scanId}` : ""}`);
export const getCbom = (scanId?: number) =>
  _get<Record<string, unknown>>(`/api/cbom${scanId ? `?scan_id=${scanId}` : ""}`);

export async function getScanDetail(id: number): Promise<import("../types").ScanDetail> {
  const scan = await getScan(id);
  const { items: assets, total } = await getAssets(id, { limit: 200 });
  return { ...scan, assets, assets_total: total };
}

export async function getEvidenceGraph(scanId?: number): Promise<Record<string, unknown>> {
  return _get(`/api/evidence-graph${scanId ? `?scan_id=${scanId}` : ""}`);
}

export async function downloadCsv(
  filename: string,
  rows: Record<string, unknown>[],
  columns: string[],
): Promise<void> {
  const header = columns.join(",");
  const body = rows
    .map((row) =>
      columns
        .map((col) => {
          const val = row[col];
          const str = val == null ? "" : String(val);
          return str.includes(",") || str.includes('"') || str.includes("\n")
            ? `"${str.replace(/"/g, '""')}"`
            : str;
        })
        .join(","),
    )
    .join("\n");
  const blob = new Blob([`${header}\n${body}\n`], { type: "text/csv;charset=utf-8" });
  const url = URL.createObjectURL(blob);
  const link = document.createElement("a");
  link.href = url;
  link.download = filename;
  document.body.appendChild(link);
  link.click();
  link.remove();
  setTimeout(() => URL.revokeObjectURL(url), 30000);
}

export async function getDashboardSummary(
  scanId?: number,
): Promise<import("../types").DashboardSummary> {
  const qs = scanId != null ? `?scan_id=${scanId}` : "";
  return _get(`/api/dashboard/summary${qs}`);
}

const storedSession = readStoredSession();
if (storedSession) {
  if (storedSession.expiresAt * 1000 <= Date.now()) {
    clearStoredSession();
    sessionExpiredOnLoad = true;
  } else {
    accessToken = storedSession.accessToken;
    role = storedSession.role;
    expiresAt = storedSession.expiresAt;
    scheduleExpiry();
  }
}

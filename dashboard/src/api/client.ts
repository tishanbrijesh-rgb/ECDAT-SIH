// src/api/client.ts — thin HTTP client for ECDAT backend API

const API_BASE: string = (import.meta as any).env?.VITE_API_URL || "http://localhost:8000";
let accessToken = "";
let role = "";
let expiryTimer: ReturnType<typeof setTimeout> | undefined;
export const SESSION_EXPIRED = "ecdat-session-expired";
export const canWrite = () => role === "admin" || role === "security_analyst";
export function logout() {
  clearTimeout(expiryTimer);
  accessToken = "";
  role = "";
}
function expireSession() {
  logout();
  window.dispatchEvent(new Event(SESSION_EXPIRED));
}
export async function login(username: string, password: string) {
  const result = await _post<{ access_token: string; role: string; expires_at: number }>(
    "/api/auth/login",
    { username, password },
  );
  logout();
  accessToken = result.access_token;
  role = result.role;
  expiryTimer = setTimeout(expireSession, Math.max(0, result.expires_at * 1000 - Date.now()));
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
  if (!res.ok) throw new Error(`POST ${path} → ${res.status}`);
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

export async function getAssets(scanJobId?: number): Promise<import("../types").CryptoAsset[]> {
  const qs = scanJobId != null ? `?scan_job_id=${scanJobId}` : "";
  return _get(`/api/assets${qs}`);
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

export async function getDashboardSummary(): Promise<import("../types").DashboardSummary> {
  return _get("/api/dashboard/summary");
}

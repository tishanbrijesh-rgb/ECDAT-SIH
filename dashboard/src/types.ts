// Shared contracts matching the ECDAT FastAPI responses.
export interface EvidenceEntry {
  [key: string]: unknown;
  source?: string;
  evidence?: Record<string, unknown>;
}
export type RiskLabel = "CRITICAL" | "HIGH" | "MEDIUM" | "LOW";
export interface CryptoAsset {
  id: number;
  scan_job_id: number;
  logical_asset_id: string;
  algorithm: string;
  category: string;
  source: string[];
  location: string;
  evidence_json: {
    component?: string;
    confidence_by_source?: Record<string, number>;
    evidence_list?: EvidenceEntry[];
    reasons?: string[];
    conflicting_operations?: string[];
  };
  confidence: number;
  conflict: boolean;
  quantum_vulnerable: boolean;
  priority_score: number;
  priority_label: RiskLabel;
  pqc_candidate: string;
  business_criticality: string;
  usage: string;
  library: string;
  protocol: string;
  key_size: number | null;
  data_sensitivity: string;
  data_lifetime_years: number;
  migration_time_years: number;
  threat_horizon_years: number;
  exposure: string;
  migration_effort: string;
  risk_reasons: string[];
  hybrid_recommended: boolean;
  created_at: string;
}
export interface ScanJob {
  id: number;
  repo_path: string;
  status: string;
  started_at: string | null;
  finished_at: string | null;
  assets_found: number;
  avg_confidence: number | null;
  total_files: number;
  in_scope_files: number;
  scanned_files: number;
  failed_files: number;
  coverage_pct: number;
  duration_ms: number;
  collector_stats: Record<string, number>;
  blind_spots: string[];
}
export interface DashboardSummary {
  total_assets: number;
  high_risk_count: number;
  avg_confidence: number;
  coverage_pct: number;
  blind_spots: string[];
  risk_distribution: Record<RiskLabel, number>;
  quantum_vulnerable_count: number;
  conflict_count: number;
  latest_scan_id: number | null;
  collector_stats: Record<string, number>;
}
export interface Evaluation {
  available: boolean;
  message?: string;
  scan_id: number;
  coverage_pct: number;
  duration_ms: number;
  expected?: number;
  found?: number;
  true_positives?: number;
  false_positives?: number;
  false_negatives?: number;
  precision?: number;
  recall?: number;
  f1?: number;
  per_source?: Record<string, { findings: number; precision: number; recall: number }>;
  missed?: Array<{ component: string; algorithm: string }>;
  unexpected?: Array<{ component: string; algorithm: string }>;
  declared_blind_spots?: Array<Record<string, string>>;
}
export interface RiskReport {
  title: string;
  scan_id: number;
  repository: string;
  coverage_pct: number;
  summary: Record<string, unknown>;
  blind_spots: string[];
  migration_priorities: Array<{
    asset_id: number;
    algorithm: string;
    location: string;
    score: number;
    label: RiskLabel;
    reasons: string[];
    recommendation: string;
    hybrid: boolean;
  }>;
}

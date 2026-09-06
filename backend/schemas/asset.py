"""Pydantic schemas for API serialization."""
from __future__ import annotations
from datetime import datetime
from pydantic import BaseModel, ConfigDict, Field, field_validator
from scanner.redaction import redact_evidence
from typing import Any


class AssetCreate(BaseModel):
    """Create an asset (used internally by the scanner runner)."""
    scan_job_id: int
    algorithm: str
    category: str
    source: list[str] = Field(default_factory=list)
    location: str
    evidence_json: dict[str, Any] = Field(default_factory=dict)
    confidence: float = 0.0
    conflict: bool = False
    quantum_vulnerable: bool = False
    priority_score: int = 0
    priority_label: str = "LOW"
    pqc_candidate: str = ""
    business_criticality: str = "medium"
    usage: str = "unknown"
    library: str = ""
    protocol: str = ""
    key_size: int | None = None
    data_sensitivity: str = "medium"
    data_lifetime_years: int = 10
    migration_time_years: int = 3
    threat_horizon_years: int = 15
    exposure: str = "internal"
    migration_effort: str = "medium"
    risk_reasons: list[str] = Field(default_factory=list)
    hybrid_recommended: bool = False
    logical_asset_id: str = ""


class AssetResponse(BaseModel):
    """Full asset response returned by the API."""
    model_config = ConfigDict(from_attributes=True)

    id: int
    scan_job_id: int
    algorithm: str
    category: str
    source: list[str]
    location: str
    evidence_json: dict[str, Any]
    confidence: float
    conflict: bool
    quantum_vulnerable: bool
    priority_score: int
    priority_label: str
    pqc_candidate: str
    business_criticality: str
    usage: str
    library: str
    protocol: str
    key_size: int | None
    data_sensitivity: str
    data_lifetime_years: int
    migration_time_years: int
    threat_horizon_years: int
    exposure: str
    migration_effort: str
    risk_reasons: list[str]
    hybrid_recommended: bool
    logical_asset_id: str
    created_at: datetime

    @field_validator("evidence_json")
    @classmethod
    def sanitize_evidence(cls, value):
        return redact_evidence(value)

class AssetUpdate(BaseModel):
    """Partial update — e.g. change business_criticality."""
    business_criticality: str | None = None
    data_sensitivity: str | None = None
    data_lifetime_years: int | None = Field(default=None, ge=0, le=100)
    migration_time_years: int | None = Field(default=None, ge=0, le=50)
    threat_horizon_years: int | None = Field(default=None, ge=1, le=100)
    exposure: str | None = None
    migration_effort: str | None = None


class ScanJobResponse(BaseModel):
    """Scan job summary."""
    model_config = ConfigDict(from_attributes=True)

    id: int
    repo_path: str
    status: str
    started_at: datetime | None = None
    finished_at: datetime | None = None
    assets_found: int
    avg_confidence: float | None = None
    total_files: int = 0
    in_scope_files: int = 0
    scanned_files: int = 0
    failed_files: int = 0
    coverage_pct: float = 0.0
    duration_ms: int = 0
    collector_stats: dict[str, int] = Field(default_factory=dict)
    blind_spots: list[str] = Field(default_factory=list)

class DashboardSummary(BaseModel):
    """Aggregated dashboard data."""
    total_assets: int
    high_risk_count: int
    avg_confidence: float
    coverage_pct: float
    blind_spots: list[str]
    risk_distribution: dict[str, int]
    quantum_vulnerable_count: int = 0
    conflict_count: int = 0
    latest_scan_id: int | None = None
    collector_stats: dict[str, int] = Field(default_factory=dict)

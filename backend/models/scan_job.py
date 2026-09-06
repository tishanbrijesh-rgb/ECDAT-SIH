"""ScanJob model — represents a single scan execution."""
from datetime import datetime, timezone
from sqlalchemy import Column, Integer, String, DateTime, Float, JSON

from backend.db import Base


class ScanJobDB(Base):
    __tablename__ = "scan_jobs"

    id: int = Column(Integer, primary_key=True, index=True)
    repo_path: str = Column(String, nullable=False)
    started_at: datetime = Column(DateTime, default=lambda: datetime.now(timezone.utc))
    finished_at: datetime | None = Column(DateTime, nullable=True)
    status: str = Column(String, default="pending")  # pending|queued|running|completed|failed|cancelled|timed_out
    assets_found: int = Column(Integer, default=0)
    avg_confidence: float | None = Column(Float, nullable=True)
    total_files: int = Column(Integer, default=0)
    in_scope_files: int = Column(Integer, default=0)
    scanned_files: int = Column(Integer, default=0)
    failed_files: int = Column(Integer, default=0)
    coverage_pct: float = Column(Float, default=0.0)
    duration_ms: int = Column(Integer, default=0)
    collector_stats = Column(JSON, default=dict)
    blind_spots = Column(JSON, default=list)

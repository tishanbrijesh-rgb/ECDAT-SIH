"""ScanJob model — represents a single scan execution."""
from datetime import datetime, timezone

from sqlalchemy import JSON, Column, DateTime, Float, Index, Integer, String
from sqlalchemy.orm import relationship

from backend.db import Base


class ScanJobDB(Base):
    __tablename__ = "scan_jobs"

    id: int = Column(Integer, primary_key=True, index=True)  # type: ignore[assignment]
    repo_path: str = Column(String, nullable=False)  # type: ignore[assignment]
    started_at: datetime = Column(DateTime, default=lambda: datetime.now(timezone.utc), index=True)  # type: ignore[assignment]
    finished_at: datetime | None = Column(DateTime, nullable=True)  # type: ignore[assignment]
    status: str = Column(String, default="pending", index=True)  # pending|queued|running|completed|failed|cancelled|timed_out  # type: ignore[assignment]
    result_version: int = Column(Integer, default=0, nullable=False)  # type: ignore[assignment]
    assets_found: int = Column(Integer, default=0)  # type: ignore[assignment]
    avg_confidence: float | None = Column(Float, nullable=True)  # type: ignore[assignment]
    total_files: int = Column(Integer, default=0)  # type: ignore[assignment]
    in_scope_files: int = Column(Integer, default=0)  # type: ignore[assignment]
    scanned_files: int = Column(Integer, default=0)  # type: ignore[assignment]
    failed_files: int = Column(Integer, default=0)  # type: ignore[assignment]
    coverage_pct: float = Column(Float, default=0.0)  # type: ignore[assignment]
    duration_ms: int = Column(Integer, default=0)  # type: ignore[assignment]
    collector_stats = Column(JSON, default=dict)  # type: ignore[assignment]
    blind_spots = Column(JSON, default=list)  # type: ignore[assignment]

    __table_args__ = (
        Index("ix_scan_jobs_created_at", "started_at"),
    )

    failures = relationship(
        "ScanFailureDB",
        back_populates="scan_job",
        cascade="all, delete-orphan",
        passive_deletes=True,
    )

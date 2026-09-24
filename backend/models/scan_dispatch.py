"""Durable outbox entry for dispatching an accepted scan job."""

from datetime import datetime, timezone

from sqlalchemy import Column, DateTime, ForeignKey, Integer, String

from backend.db import Base


class ScanDispatchDB(Base):
    __tablename__ = "scan_dispatches"

    id: int = Column(Integer, primary_key=True, index=True)  # type: ignore[assignment]
    scan_job_id: int = Column(  # type: ignore[assignment]
        Integer,
        ForeignKey("scan_jobs.id", ondelete="CASCADE"),
        unique=True,
        nullable=False,
        index=True,
    )
    version: int = Column(Integer, nullable=False, default=1)  # type: ignore[assignment]
    state: str = Column(String, nullable=False, default="pending", index=True)  # type: ignore[assignment]
    available_at: datetime = Column(  # type: ignore[assignment]
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), nullable=False
    )
    claimed_by: str | None = Column(String, nullable=True)  # type: ignore[assignment]
    claim_expires_at: datetime | None = Column(DateTime(timezone=True), nullable=True)  # type: ignore[assignment]
    heartbeat_at: datetime | None = Column(DateTime(timezone=True), nullable=True)  # type: ignore[assignment]
    cancellation_requested_at: datetime | None = Column(DateTime(timezone=True), nullable=True)  # type: ignore[assignment]
    attempt_count: int = Column(Integer, nullable=False, default=0)  # type: ignore[assignment]
    created_at: datetime = Column(  # type: ignore[assignment]
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), nullable=False
    )
    updated_at: datetime = Column(  # type: ignore[assignment]
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
        nullable=False,
    )

"""ScanLease model — tracks which worker holds an active scan claim."""
from datetime import datetime, timezone

from sqlalchemy import Boolean, Column, DateTime, ForeignKey, Integer, String
from sqlalchemy.orm import relationship

from backend.db import Base


class ScanLeaseDB(Base):
    __tablename__ = "scan_leases"

    id: int = Column(Integer, primary_key=True, index=True)  # type: ignore[assignment]
    scan_job_id: int = Column(Integer, ForeignKey("scan_jobs.id", ondelete="CASCADE"),  # type: ignore[assignment]
                              unique=True, nullable=False)
    worker_id: str = Column(String, nullable=False)  # type: ignore[assignment]
    acquired_at: datetime = Column(DateTime, default=lambda: datetime.now(timezone.utc), nullable=False)  # type: ignore[assignment]
    expires_at: datetime = Column(DateTime, nullable=False)  # type: ignore[assignment]
    released: bool = Column(Boolean, default=False, nullable=False)  # type: ignore[assignment]

    scan_job = relationship("ScanJobDB", back_populates="lease")


# Attach lease relationship to ScanJobDB (avoid circular import by lazy import).
from backend.models.scan_job import ScanJobDB

ScanJobDB.lease = relationship(
    "ScanLeaseDB", back_populates="scan_job", uselist=False,
    cascade="all, delete-orphan", passive_deletes=True,
)

"""ScanLease model — tracks which worker holds an active scan claim."""
from datetime import datetime, timezone

from sqlalchemy import Column, Integer, String, DateTime, Boolean, ForeignKey
from sqlalchemy.orm import relationship

from backend.db import Base


class ScanLeaseDB(Base):
    __tablename__ = "scan_leases"

    id: int = Column(Integer, primary_key=True, index=True)
    scan_job_id: int = Column(Integer, ForeignKey("scan_jobs.id", ondelete="CASCADE"),
                              unique=True, nullable=False)
    worker_id: str = Column(String, nullable=False)
    acquired_at: datetime = Column(DateTime, default=lambda: datetime.now(timezone.utc), nullable=False)
    expires_at: datetime = Column(DateTime, nullable=False)
    released: bool = Column(Boolean, default=False, nullable=False)

    scan_job = relationship("ScanJobDB", back_populates="lease")


# Attach lease relationship to ScanJobDB (avoid circular import by lazy import).
from backend.models.scan_job import ScanJobDB  # noqa: E402
ScanJobDB.lease = relationship(
    "ScanLeaseDB", back_populates="scan_job", uselist=False,
    cascade="all, delete-orphan", passive_deletes=True,
)

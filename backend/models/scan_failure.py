"""ScanFailure model — durable structured failure record for a scan job."""
from datetime import datetime, timezone
from sqlalchemy import Column, Integer, String, DateTime, ForeignKey
from sqlalchemy.orm import relationship

from backend.db import Base


class ScanFailureDB(Base):
    __tablename__ = "scan_failures"

    id = Column(Integer, primary_key=True, autoincrement=True)
    scan_job_id = Column(
        Integer,
        ForeignKey("scan_jobs.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    path = Column(String, nullable=False)
    reason = Column(String, nullable=False)
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))

    scan_job = relationship("ScanJobDB", back_populates="failures")

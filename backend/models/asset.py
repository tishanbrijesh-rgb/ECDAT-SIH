"""CryptoAsset model — persisted finding from a scan job."""
from datetime import datetime, timezone
from sqlalchemy import Column, Integer, String, Float, Boolean, ForeignKey, DateTime, JSON

from backend.db import Base


class CryptoAssetDB(Base):
    __tablename__ = "crypto_assets"

    id = Column(Integer, primary_key=True, index=True)
    scan_job_id = Column(
        Integer, ForeignKey("scan_jobs.id", ondelete="CASCADE"),
        nullable=False, index=True,
    )
    algorithm = Column(String, nullable=False, index=True)
    category = Column(String, default="")
    source = Column(JSON, default=list)
    location = Column(String, nullable=False, index=True)
    evidence_json = Column(JSON, default=dict)
    confidence = Column(Float, default=0.0)
    conflict = Column(Boolean, default=False)
    quantum_vulnerable = Column(Boolean, default=False)
    priority_score = Column(Integer, default=0)
    priority_label = Column(String, default="LOW")
    pqc_candidate = Column(String, default="")
    business_criticality = Column(String, default="medium")
    usage = Column(String, default="unknown")
    library = Column(String, default="")
    protocol = Column(String, default="")
    key_size = Column(Integer, nullable=True)
    data_sensitivity = Column(String, default="medium")
    data_lifetime_years = Column(Integer, default=10)
    migration_time_years = Column(Integer, default=3)
    threat_horizon_years = Column(Integer, default=15)
    exposure = Column(String, default="internal")
    migration_effort = Column(String, default="medium")
    risk_reasons = Column(JSON, default=list)
    hybrid_recommended = Column(Boolean, default=False)
    logical_asset_id = Column(String, default="", index=True)
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))

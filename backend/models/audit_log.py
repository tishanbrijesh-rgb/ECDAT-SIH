"""Append-only audit event model for security-sensitive ECDAT actions."""
from datetime import datetime, timezone
from sqlalchemy import Column, DateTime, Integer, JSON, String
from backend.db import Base

class AuditLogDB(Base):
    __tablename__ = "audit_logs"
    id = Column(Integer, primary_key=True)
    timestamp = Column(DateTime, default=lambda: datetime.now(timezone.utc), index=True)
    actor_role = Column(String, default="security_analyst")
    action = Column(String, nullable=False, index=True)
    resource = Column(String, nullable=False)
    details = Column(JSON, default=dict)

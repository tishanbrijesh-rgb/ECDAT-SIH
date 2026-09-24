"""Append-only audit event model for security-sensitive ECDAT actions."""
from datetime import datetime, timezone

from sqlalchemy import JSON, Column, DateTime, Integer, String

from backend.db import Base


class AuditLogDB(Base):
    __tablename__ = "audit_logs"
    id = Column(Integer, primary_key=True)
    timestamp = Column(DateTime, default=lambda: datetime.now(timezone.utc), index=True)
    actor_subject = Column(String, nullable=False, default="legacy")
    actor_role = Column(String, default="security_analyst")
    actor_session_id = Column(String, nullable=False, default="legacy")
    actor_expires_at = Column(Integer, nullable=True)
    action = Column(String, nullable=False, index=True)
    resource = Column(String, nullable=False)
    details = Column(JSON, default=dict)


class RevokedSessionDB(Base):
    """Persistent deny-list entry for a signed session identifier."""

    __tablename__ = "revoked_sessions"

    session_id = Column(String, primary_key=True)
    subject = Column(String, nullable=False, index=True)
    expires_at = Column(Integer, nullable=False)
    revoked_at = Column(DateTime, default=lambda: datetime.now(timezone.utc), nullable=False)

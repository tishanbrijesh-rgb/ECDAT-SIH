"""0001_baseline

Revision ID: 69254661dfed
Revises:
Create Date: 2026-09-07
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSON as PGJSON


revision: str = "69254661dfed"
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def _col_type(column_type):
    """Map SQLAlchemy types to dialect-appropriate DDL."""
    dialect = op.get_context().dialect.name
    if isinstance(column_type, sa.JSON):
        if dialect == "postgresql":
            return PGJSON()
        return sa.JSON()
    if isinstance(column_type, sa.DateTime):
        return sa.DateTime(timezone=True)
    return column_type


def upgrade() -> None:
    op.create_table(
        "scan_jobs",
        sa.Column("id", sa.Integer, primary_key=True, autoincrement=True),
        sa.Column("repo_path", sa.String, nullable=False),
        sa.Column("started_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("finished_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("status", sa.String, server_default="pending"),
        sa.Column("assets_found", sa.Integer, server_default="0"),
        sa.Column("avg_confidence", sa.Float, nullable=True),
        sa.Column("total_files", sa.Integer, server_default="0"),
        sa.Column("in_scope_files", sa.Integer, server_default="0"),
        sa.Column("scanned_files", sa.Integer, server_default="0"),
        sa.Column("failed_files", sa.Integer, server_default="0"),
        sa.Column("coverage_pct", sa.Float, server_default="0.0"),
        sa.Column("duration_ms", sa.Integer, server_default="0"),
        sa.Column("collector_stats", _col_type(sa.JSON()), server_default="{}"),
        sa.Column("blind_spots", _col_type(sa.JSON()), server_default="[]"),
        sa.Index("ix_scan_jobs_id", "id"),
    )

    op.create_table(
        "crypto_assets",
        sa.Column("id", sa.Integer, primary_key=True, autoincrement=True),
        sa.Column("scan_job_id", sa.Integer, nullable=False),
        sa.Column("algorithm", sa.String, nullable=False),
        sa.Column("category", sa.String, server_default=""),
        sa.Column("source", _col_type(sa.JSON()), server_default="[]"),
        sa.Column("location", sa.String, nullable=False),
        sa.Column("evidence_json", _col_type(sa.JSON()), server_default="{}"),
        sa.Column("confidence", sa.Float, server_default="0.0"),
        sa.Column("conflict", sa.Boolean, server_default="0"),
        sa.Column("quantum_vulnerable", sa.Boolean, server_default="0"),
        sa.Column("priority_score", sa.Integer, server_default="0"),
        sa.Column("priority_label", sa.String, server_default="LOW"),
        sa.Column("pqc_candidate", sa.String, server_default=""),
        sa.Column("business_criticality", sa.String, server_default="medium"),
        sa.Column("usage", sa.String, server_default="unknown"),
        sa.Column("library", sa.String, server_default=""),
        sa.Column("protocol", sa.String, server_default=""),
        sa.Column("key_size", sa.Integer, nullable=True),
        sa.Column("data_sensitivity", sa.String, server_default="medium"),
        sa.Column("data_lifetime_years", sa.Integer, server_default="10"),
        sa.Column("migration_time_years", sa.Integer, server_default="3"),
        sa.Column("threat_horizon_years", sa.Integer, server_default="15"),
        sa.Column("exposure", sa.String, server_default="internal"),
        sa.Column("migration_effort", sa.String, server_default="medium"),
        sa.Column("risk_reasons", _col_type(sa.JSON()), server_default="[]"),
        sa.Column("hybrid_recommended", sa.Boolean, server_default="0"),
        sa.Column("logical_asset_id", sa.String, server_default=""),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Index("ix_crypto_assets_id", "id"),
        sa.Index("ix_crypto_assets_scan_job_id", "scan_job_id"),
        sa.Index("ix_crypto_assets_algorithm", "algorithm"),
        sa.Index("ix_crypto_assets_location", "location"),
        sa.Index("ix_crypto_assets_logical_asset_id", "logical_asset_id"),
        sa.Index("ix_crypto_assets_priority_label", "priority_label"),
        sa.ForeignKeyConstraint(["scan_job_id"], ["scan_jobs.id"], ondelete="CASCADE"),
    )

    op.create_table(
        "audit_logs",
        sa.Column("id", sa.Integer, primary_key=True, autoincrement=True),
        sa.Column("timestamp", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("actor_role", sa.String, server_default="security_analyst"),
        sa.Column("action", sa.String, nullable=False),
        sa.Column("resource", sa.String, nullable=False),
        sa.Column("details", _col_type(sa.JSON()), server_default="{}"),
        sa.Index("ix_audit_logs_id", "id"),
        sa.Index("ix_audit_logs_timestamp", "timestamp"),
        sa.Index("ix_audit_logs_action", "action"),
    )


def downgrade() -> None:
    op.drop_table("audit_logs")
    op.drop_table("crypto_assets")
    op.drop_table("scan_jobs")

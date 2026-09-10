"""0004_scan_leases

Revision ID: f9c6d3a18b72
Revises: e1b4a7c93f52
Create Date: 2026-09-09
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "f9c6d3a18b72"
down_revision: Union[str, None] = "e1b4a7c93f52"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "scan_leases",
        sa.Column("id", sa.Integer, primary_key=True, autoincrement=True),
        sa.Column(
            "scan_job_id",
            sa.Integer,
            sa.ForeignKey("scan_jobs.id", ondelete="CASCADE"),
            nullable=False,
            unique=True,
        ),
        sa.Column("worker_id", sa.String, nullable=False),
        sa.Column("acquired_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("released", sa.Boolean, nullable=False, server_default=sa.false()),
        sa.Index("ix_scan_leases_scan_job_id", "scan_job_id"),
    )


def downgrade() -> None:
    op.drop_table("scan_leases")

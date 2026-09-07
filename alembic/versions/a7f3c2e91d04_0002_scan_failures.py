"""0002_scan_failures

Revision ID: a7f3c2e91d04
Revises: 69254661dfed
Create Date: 2026-09-07
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "a7f3c2e91d04"
down_revision: Union[str, None] = "69254661dfed"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "scan_failures",
        sa.Column("id", sa.Integer, primary_key=True, autoincrement=True),
        sa.Column(
            "scan_job_id",
            sa.Integer,
            sa.ForeignKey("scan_jobs.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("path", sa.String, nullable=False),
        sa.Column("reason", sa.String, nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.Index("ix_scan_failures_scan_job_id", "scan_job_id"),
        sa.Index("ix_scan_failures_scan_job_id_path", "scan_job_id", "path"),
    )


def downgrade() -> None:
    op.drop_table("scan_failures")

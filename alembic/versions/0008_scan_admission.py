"""Add durable scan dispatch outbox and result version.

Revision ID: 0008_scan_admission
Revises: 0007_audit_principal
Create Date: 2026-09-20
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "0008_scan_admission"
down_revision: str | None = "0007_audit_principal"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "scan_jobs",
        sa.Column("result_version", sa.Integer(), nullable=False, server_default="0"),
    )
    op.create_table(
        "scan_dispatches",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column(
            "scan_job_id",
            sa.Integer(),
            sa.ForeignKey("scan_jobs.id", ondelete="CASCADE"),
            nullable=False,
            unique=True,
        ),
        sa.Column("version", sa.Integer(), nullable=False, server_default="1"),
        sa.Column("state", sa.String(), nullable=False, server_default="pending"),
        sa.Column("available_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("claimed_by", sa.String(), nullable=True),
        sa.Column("claim_expires_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("heartbeat_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("cancellation_requested_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("attempt_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_scan_dispatches_scan_job_id", "scan_dispatches", ["scan_job_id"])
    op.create_index("ix_scan_dispatches_state", "scan_dispatches", ["state"])


def downgrade() -> None:
    op.drop_index("ix_scan_dispatches_state", table_name="scan_dispatches")
    op.drop_index("ix_scan_dispatches_scan_job_id", table_name="scan_dispatches")
    op.drop_table("scan_dispatches")
    with op.batch_alter_table("scan_jobs") as batch_op:
        batch_op.drop_column("result_version")

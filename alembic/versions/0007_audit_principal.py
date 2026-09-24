"""Persist authenticated principal identity on audit events.

Revision ID: 0007_audit_principal
Revises: 0006_provenance
Create Date: 2026-09-20
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "0007_audit_principal"
down_revision: str | None = "0006_provenance"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    with op.batch_alter_table("audit_logs") as batch:
        batch.add_column(
            sa.Column("actor_subject", sa.String(), nullable=False, server_default="legacy")
        )
        batch.add_column(
            sa.Column("actor_session_id", sa.String(), nullable=False, server_default="legacy")
        )
        batch.add_column(sa.Column("actor_expires_at", sa.Integer(), nullable=True))

    op.execute(
        sa.text(
            "UPDATE audit_logs "
            "SET actor_subject = 'legacy-role:' || actor_role "
            "WHERE actor_subject = 'legacy'"
        )
    )

    with op.batch_alter_table("audit_logs") as batch:
        batch.alter_column("actor_subject", server_default=None)
        batch.alter_column("actor_session_id", server_default=None)

    op.create_table(
        "revoked_sessions",
        sa.Column("session_id", sa.String(), nullable=False),
        sa.Column("subject", sa.String(), nullable=False),
        sa.Column("expires_at", sa.Integer(), nullable=False),
        sa.Column("revoked_at", sa.DateTime(), nullable=False),
        sa.PrimaryKeyConstraint("session_id"),
    )
    op.create_index(
        "ix_revoked_sessions_subject",
        "revoked_sessions",
        ["subject"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index("ix_revoked_sessions_subject", table_name="revoked_sessions")
    op.drop_table("revoked_sessions")
    with op.batch_alter_table("audit_logs") as batch:
        batch.drop_column("actor_expires_at")
        batch.drop_column("actor_session_id")
        batch.drop_column("actor_subject")

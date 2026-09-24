"""0006_risk_context_provenance

Revision ID: 0006_provenance
Revises: b2e4f1a7c39d
Create Date: 2026-09-13

Add risk_context_provenance JSON column to crypto_assets to track whether
each risk context input was user-provided or a policy default.
"""

from alembic import op
import sqlalchemy as sa


revision = "0006_provenance"
down_revision = "b2e4f1a7c39d"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column(
        "crypto_assets",
        sa.Column("risk_context_provenance", sa.JSON(), nullable=False, server_default="{}"),
    )
    # Drop the server_default on SQLite after backfill; on Postgres this is a no-op
    # because the column was added with a default that fills existing rows.
    with op.batch_alter_table("crypto_assets") as batch:
        batch.alter_column("risk_context_provenance", server_default=None)


def downgrade():
    with op.batch_alter_table("crypto_assets") as batch:
        batch.drop_column("risk_context_provenance")

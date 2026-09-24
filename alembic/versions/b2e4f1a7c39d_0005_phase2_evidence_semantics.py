"""0005_phase2_evidence_semantics

Revision ID: b2e4f1a7c39d
Revises: f9c6d3a18b72
Create Date: 2026-09-11

Phase 2: Add evidence-semantics columns to crypto_assets.
Carries evidence_kind, parser_version, confirmed_use, capability_only,
span, confidence_reasons, and evidence_quality from the scanner
pipeline through persistence to the API layer.
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "b2e4f1a7c39d"
down_revision: Union[str, None] = "f9c6d3a18b72"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    with op.batch_alter_table("crypto_assets", schema=None) as batch_op:
        batch_op.add_column(sa.Column("evidence_kind", sa.String(length=32), nullable=False, server_default="unknown"))
        batch_op.add_column(sa.Column("parser_version", sa.String(length=32), nullable=False, server_default=""))
        batch_op.add_column(sa.Column("evidence_quality", sa.String(length=32), nullable=False, server_default="unknown"))
        batch_op.add_column(sa.Column("confirmed_use", sa.Boolean(), nullable=False, server_default=sa.false()))
        batch_op.add_column(sa.Column("capability_only", sa.Boolean(), nullable=False, server_default=sa.false()))
        batch_op.add_column(sa.Column("span", sa.JSON(), nullable=False, server_default=sa.text("'{}'")))
        batch_op.add_column(sa.Column("confidence_reasons", sa.JSON(), nullable=False, server_default=sa.text("'[]'")))
        batch_op.create_index("ix_crypto_assets_evidence_kind", ["evidence_kind"])


def downgrade() -> None:
    with op.batch_alter_table("crypto_assets", schema=None) as batch_op:
        batch_op.drop_index("ix_crypto_assets_evidence_kind")
        batch_op.drop_column("confidence_reasons")
        batch_op.drop_column("span")
        batch_op.drop_column("capability_only")
        batch_op.drop_column("confirmed_use")
        batch_op.drop_column("evidence_quality")
        batch_op.drop_column("parser_version")
        batch_op.drop_column("evidence_kind")

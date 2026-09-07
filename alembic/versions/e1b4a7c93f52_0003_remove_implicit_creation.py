"""0003_remove_implicit_creation

Revision ID: e1b4a7c93f52
Revises: a7f3c2e91d04
Create Date: 2026-09-07
"""
from typing import Sequence, Union

revision: str = "e1b4a7c93f52"
down_revision: Union[str, None] = "a7f3c2e91d04"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """No schema change — records that table creation is now migration-only.

    The ECDAT_AUTO_CREATE_TABLES env var (set in docker-compose.yml) disables
    Base.metadata.create_all() in production. See backend/main.py lifespan.
    """
    pass


def downgrade() -> None:
    pass

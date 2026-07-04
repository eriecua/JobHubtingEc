"""Phase 3.1 baseline schema.

Revision ID: 202607020001
Revises:
Create Date: 2026-07-02
"""

from __future__ import annotations

from collections.abc import Sequence

from alembic import op

from app.models.database_models import Base


revision: str = "202607020001"
down_revision: str | None = None
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Create the current schema when tables do not already exist."""

    Base.metadata.create_all(bind=op.get_bind(), checkfirst=True)


def downgrade() -> None:
    """Drop all application tables; use only on disposable or backed-up databases."""

    Base.metadata.drop_all(bind=op.get_bind(), checkfirst=True)

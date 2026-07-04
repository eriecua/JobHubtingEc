"""Phase 6.1 learning stabilization.

Revision ID: 202607020006
Revises: 202607020005
Create Date: 2026-07-03
"""

from __future__ import annotations

from collections.abc import Sequence

from alembic import op
import sqlalchemy as sa


revision: str = "202607020006"
down_revision: str | None = "202607020005"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def _columns(table_name: str) -> set[str]:
    inspector = sa.inspect(op.get_bind())
    return {column["name"] for column in inspector.get_columns(table_name)}


def _indexes(table_name: str) -> set[str]:
    inspector = sa.inspect(op.get_bind())
    return {index["name"] for index in inspector.get_indexes(table_name)}


def upgrade() -> None:
    """Associate application tracking rows with profiles for isolated learning."""

    inspector = sa.inspect(op.get_bind())
    tables = set(inspector.get_table_names())

    if "applications" in tables and "profile_id" not in _columns("applications"):
        op.add_column("applications", sa.Column("profile_id", sa.Integer(), nullable=True))

    if "applications" in tables and "ix_applications_profile_id" not in _indexes("applications"):
        op.create_index("ix_applications_profile_id", "applications", ["profile_id"])

    if "applications" in tables and "professional_profiles" in tables:
        bind = op.get_bind()
        profile_id = bind.execute(
            sa.text(
                """
                SELECT id
                FROM professional_profiles
                WHERE is_primary = 1 AND is_active = 1
                ORDER BY id
                LIMIT 1
                """
            )
        ).scalar()
        if profile_id is not None:
            bind.execute(
                sa.text(
                    """
                    UPDATE applications
                    SET profile_id = :profile_id
                    WHERE profile_id IS NULL
                    """
                ),
                {"profile_id": profile_id},
            )

    if "adjustment_proposals" in tables and "expires_at" not in _columns("adjustment_proposals"):
        op.add_column("adjustment_proposals", sa.Column("expires_at", sa.DateTime(), nullable=True))
    if "adjustment_proposals" in tables and "ix_adjustment_proposals_expires_at" not in _indexes("adjustment_proposals"):
        op.create_index("ix_adjustment_proposals_expires_at", "adjustment_proposals", ["expires_at"])


def downgrade() -> None:
    """Remove the optional profile association from application tracking."""

    inspector = sa.inspect(op.get_bind())
    tables = set(inspector.get_table_names())
    if "adjustment_proposals" in tables and "expires_at" in _columns("adjustment_proposals"):
        if "ix_adjustment_proposals_expires_at" in _indexes("adjustment_proposals"):
            op.drop_index("ix_adjustment_proposals_expires_at", table_name="adjustment_proposals")
        op.drop_column("adjustment_proposals", "expires_at")
    if "applications" not in tables or "profile_id" not in _columns("applications"):
        return
    if "ix_applications_profile_id" in _indexes("applications"):
        op.drop_index("ix_applications_profile_id", table_name="applications")
    with op.batch_alter_table("applications") as batch_op:
        batch_op.drop_column("profile_id")

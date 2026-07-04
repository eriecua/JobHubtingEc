"""Phase 5 application effort overrides.

Revision ID: 202607020004
Revises: 202607020003
Create Date: 2026-07-02
"""

from __future__ import annotations

from collections.abc import Sequence

from alembic import op
import sqlalchemy as sa


revision: str = "202607020004"
down_revision: str | None = "202607020003"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Create manual effort override table without modifying priorities."""

    inspector = sa.inspect(op.get_bind())
    existing_tables = set(inspector.get_table_names())
    if "application_effort_overrides" in existing_tables:
        return
    op.create_table(
        "application_effort_overrides",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("job_id", sa.Integer(), sa.ForeignKey("jobs.id"), nullable=False),
        sa.Column("profile_id", sa.Integer(), sa.ForeignKey("professional_profiles.id"), nullable=False),
        sa.Column("effort_level", sa.String(length=80), nullable=False),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.UniqueConstraint("job_id", "profile_id", name="uq_effort_override_job_profile"),
    )
    op.create_index("ix_application_effort_overrides_job_id", "application_effort_overrides", ["job_id"])
    op.create_index("ix_application_effort_overrides_profile_id", "application_effort_overrides", ["profile_id"])


def downgrade() -> None:
    """Drop only the Phase 5 effort override table."""

    inspector = sa.inspect(op.get_bind())
    existing_tables = set(inspector.get_table_names())
    if "application_effort_overrides" not in existing_tables:
        return
    op.drop_index("ix_application_effort_overrides_profile_id", table_name="application_effort_overrides")
    op.drop_index("ix_application_effort_overrides_job_id", table_name="application_effort_overrides")
    op.drop_table("application_effort_overrides")

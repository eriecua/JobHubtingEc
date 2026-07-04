"""Phase 5 strategic prioritization schema.

Revision ID: 202607020003
Revises: 202607020002
Create Date: 2026-07-02
"""

from __future__ import annotations

from collections.abc import Sequence

from alembic import op
import sqlalchemy as sa


revision: str = "202607020003"
down_revision: str | None = "202607020002"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Create Phase 5 tables without modifying existing records."""

    inspector = sa.inspect(op.get_bind())
    existing_tables = set(inspector.get_table_names())
    existing_indexes = {
        table_name: {index["name"] for index in inspector.get_indexes(table_name)}
        for table_name in existing_tables
    }

    def create_table_once(table_name: str, *columns, **kwargs) -> None:
        if table_name not in existing_tables:
            op.create_table(table_name, *columns, **kwargs)
            existing_tables.add(table_name)

    def create_index_once(index_name: str, table_name: str, columns: list[str]) -> None:
        if index_name not in existing_indexes.get(table_name, set()):
            op.create_index(index_name, table_name, columns)
            existing_indexes.setdefault(table_name, set()).add(index_name)

    create_table_once(
        "prioritization_runs",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("profile_id", sa.Integer(), sa.ForeignKey("professional_profiles.id"), nullable=False),
        sa.Column("prioritization_version", sa.String(length=80), nullable=False),
        sa.Column("configuration_hash", sa.String(length=128), nullable=False),
        sa.Column("evaluation_run_id", sa.Integer(), sa.ForeignKey("evaluation_runs.id"), nullable=True),
        sa.Column("started_at", sa.DateTime(), nullable=False),
        sa.Column("completed_at", sa.DateTime(), nullable=True),
        sa.Column("status", sa.String(length=80), nullable=False, server_default="Creado"),
        sa.Column("jobs_considered", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("jobs_prioritized", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("jobs_excluded", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("jobs_failed", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("error_summary", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
    )
    for column in ["profile_id", "prioritization_version", "configuration_hash", "evaluation_run_id", "status"]:
        create_index_once(f"ix_prioritization_runs_{column}", "prioritization_runs", [column])

    create_table_once(
        "job_priorities",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("prioritization_run_id", sa.Integer(), sa.ForeignKey("prioritization_runs.id"), nullable=False),
        sa.Column("job_id", sa.Integer(), sa.ForeignKey("jobs.id"), nullable=False),
        sa.Column("evaluation_id", sa.Integer(), sa.ForeignKey("job_evaluations.id"), nullable=True),
        sa.Column("profile_id", sa.Integer(), sa.ForeignKey("professional_profiles.id"), nullable=False),
        sa.Column("priority_score", sa.Numeric(5, 2), nullable=False),
        sa.Column("urgency_score", sa.Numeric(5, 2), nullable=False),
        sa.Column("strategic_value_score", sa.Numeric(5, 2), nullable=False),
        sa.Column("actionability_score", sa.Numeric(5, 2), nullable=False),
        sa.Column("application_effort_score", sa.Numeric(5, 2), nullable=False),
        sa.Column("recommended_action", sa.String(length=120), nullable=False),
        sa.Column("priority_bucket", sa.String(length=80), nullable=False),
        sa.Column("position_in_queue", sa.Integer(), nullable=False),
        sa.Column("decision_deadline", sa.Date(), nullable=True),
        sa.Column("reasons", sa.JSON(), nullable=False),
        sa.Column("warnings", sa.JSON(), nullable=False),
        sa.Column("blocking_factors", sa.JSON(), nullable=False),
        sa.Column("configuration_hash", sa.String(length=128), nullable=False),
        sa.Column("job_snapshot_hash", sa.String(length=128), nullable=False),
        sa.Column("evaluation_snapshot_hash", sa.String(length=128), nullable=False),
        sa.Column("is_stale", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.UniqueConstraint("prioritization_run_id", "position_in_queue", name="uq_priority_run_position"),
    )
    for column in [
        "prioritization_run_id",
        "job_id",
        "evaluation_id",
        "profile_id",
        "priority_score",
        "recommended_action",
        "priority_bucket",
        "position_in_queue",
        "configuration_hash",
        "job_snapshot_hash",
        "evaluation_snapshot_hash",
        "is_stale",
    ]:
        create_index_once(f"ix_job_priorities_{column}", "job_priorities", [column])

    create_table_once(
        "job_decisions",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("job_id", sa.Integer(), sa.ForeignKey("jobs.id"), nullable=False),
        sa.Column("profile_id", sa.Integer(), sa.ForeignKey("professional_profiles.id"), nullable=False),
        sa.Column("priority_id", sa.Integer(), sa.ForeignKey("job_priorities.id"), nullable=True),
        sa.Column("decision", sa.String(length=120), nullable=False),
        sa.Column("reason_code", sa.String(length=160), nullable=True),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column("decided_at", sa.DateTime(), nullable=False),
        sa.Column("follow_up_date", sa.Date(), nullable=True),
        sa.Column("decision_source", sa.String(length=80), nullable=False, server_default="Usuario"),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
    )
    for column in ["job_id", "profile_id", "priority_id", "decision", "decided_at", "decision_source"]:
        create_index_once(f"ix_job_decisions_{column}", "job_decisions", [column])

    create_table_once(
        "saved_views",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("profile_id", sa.Integer(), sa.ForeignKey("professional_profiles.id"), nullable=False),
        sa.Column("name", sa.String(length=160), nullable=False),
        sa.Column("filters_json", sa.JSON(), nullable=False),
        sa.Column("sort_json", sa.JSON(), nullable=False),
        sa.Column("is_default", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.UniqueConstraint("profile_id", "name", name="uq_saved_view_profile_name"),
    )
    for column in ["profile_id", "is_default"]:
        create_index_once(f"ix_saved_views_{column}", "saved_views", [column])

    create_table_once(
        "daily_shortlists",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("profile_id", sa.Integer(), sa.ForeignKey("professional_profiles.id"), nullable=False),
        sa.Column("shortlist_date", sa.Date(), nullable=False),
        sa.Column("status", sa.String(length=80), nullable=False, server_default="Borrador"),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.UniqueConstraint("profile_id", "shortlist_date", name="uq_daily_shortlist_profile_date"),
    )
    for column in ["profile_id", "shortlist_date", "status"]:
        create_index_once(f"ix_daily_shortlists_{column}", "daily_shortlists", [column])

    create_table_once(
        "daily_shortlist_items",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("shortlist_id", sa.Integer(), sa.ForeignKey("daily_shortlists.id"), nullable=False),
        sa.Column("job_id", sa.Integer(), sa.ForeignKey("jobs.id"), nullable=False),
        sa.Column("priority_id", sa.Integer(), sa.ForeignKey("job_priorities.id"), nullable=True),
        sa.Column("position", sa.Integer(), nullable=False),
        sa.Column("planned_action", sa.String(length=120), nullable=False),
        sa.Column("completion_status", sa.String(length=80), nullable=False, server_default="Pendiente"),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.UniqueConstraint("shortlist_id", "job_id", name="uq_shortlist_job"),
        sa.UniqueConstraint("shortlist_id", "position", name="uq_shortlist_position"),
    )
    for column in ["shortlist_id", "job_id", "priority_id", "completion_status"]:
        create_index_once(f"ix_daily_shortlist_items_{column}", "daily_shortlist_items", [column])


def downgrade() -> None:
    """Drop only Phase 5 tables. Use only on disposable or backed-up databases."""

    inspector = sa.inspect(op.get_bind())
    existing_tables = set(inspector.get_table_names())
    for table_name in [
        "daily_shortlist_items",
        "daily_shortlists",
        "saved_views",
        "job_decisions",
        "job_priorities",
        "prioritization_runs",
    ]:
        if table_name in existing_tables:
            op.drop_table(table_name)

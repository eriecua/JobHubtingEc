"""Phase 4 compatibility evaluation schema.

Revision ID: 202607020002
Revises: 202607020001
Create Date: 2026-07-02
"""

from __future__ import annotations

from collections.abc import Sequence

from alembic import op
import sqlalchemy as sa


revision: str = "202607020002"
down_revision: str | None = "202607020001"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Create Phase 4 evaluation tables without touching existing data."""

    inspector = sa.inspect(op.get_bind())
    existing_tables = set(inspector.get_table_names())
    existing_indexes = {
        table_name: {index["name"] for index in inspector.get_indexes(table_name)}
        for table_name in existing_tables
    }

    def create_table_once(table_name: str, *columns, **kwargs) -> None:
        if table_name not in existing_tables:
            op.create_table(table_name, *columns, **kwargs)

    def create_index_once(index_name: str, table_name: str, columns: list[str]) -> None:
        if index_name not in existing_indexes.get(table_name, set()):
            op.create_index(index_name, table_name, columns)

    create_table_once(
        "job_requirements",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("job_id", sa.Integer(), sa.ForeignKey("jobs.id"), nullable=False),
        sa.Column("requirement_type", sa.String(length=80), nullable=False),
        sa.Column("raw_text", sa.Text(), nullable=False),
        sa.Column("normalized_value", sa.String(length=255), nullable=True),
        sa.Column("importance", sa.String(length=80), nullable=False, server_default="No determinada"),
        sa.Column("source_field", sa.String(length=120), nullable=False),
        sa.Column("extraction_method", sa.String(length=80), nullable=False),
        sa.Column("extraction_confidence", sa.Numeric(4, 2), nullable=False, server_default="0.50"),
        sa.Column("skill_id", sa.Integer(), sa.ForeignKey("skills.id"), nullable=True),
        sa.Column("tool_id", sa.Integer(), sa.ForeignKey("tools.id"), nullable=True),
        sa.Column("is_confirmed_by_user", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
    )
    create_index_once("ix_job_requirements_job_id", "job_requirements", ["job_id"])
    create_index_once("ix_job_requirements_requirement_type", "job_requirements", ["requirement_type"])
    create_index_once("ix_job_requirements_normalized_value", "job_requirements", ["normalized_value"])
    create_index_once("ix_job_requirements_importance", "job_requirements", ["importance"])
    create_index_once("ix_job_requirements_is_active", "job_requirements", ["is_active"])

    create_table_once(
        "evaluation_runs",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("profile_id", sa.Integer(), sa.ForeignKey("professional_profiles.id"), nullable=False),
        sa.Column("scoring_version", sa.String(length=80), nullable=False),
        sa.Column("configuration_hash", sa.String(length=128), nullable=False),
        sa.Column("profile_snapshot_hash", sa.String(length=128), nullable=False),
        sa.Column("started_at", sa.DateTime(), nullable=False),
        sa.Column("completed_at", sa.DateTime(), nullable=True),
        sa.Column("status", sa.String(length=80), nullable=False, server_default="Creado"),
        sa.Column("jobs_requested", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("jobs_evaluated", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("jobs_failed", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("error_summary", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
    )
    for column in ["profile_id", "scoring_version", "configuration_hash", "profile_snapshot_hash", "status"]:
        create_index_once(f"ix_evaluation_runs_{column}", "evaluation_runs", [column])

    create_table_once(
        "job_evaluations",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("run_id", sa.Integer(), sa.ForeignKey("evaluation_runs.id"), nullable=False),
        sa.Column("job_id", sa.Integer(), sa.ForeignKey("jobs.id"), nullable=False),
        sa.Column("profile_id", sa.Integer(), sa.ForeignKey("professional_profiles.id"), nullable=False),
        sa.Column("scoring_version", sa.String(length=80), nullable=False),
        sa.Column("total_score", sa.Numeric(5, 2), nullable=False),
        sa.Column("confidence_score", sa.Numeric(5, 2), nullable=False),
        sa.Column("data_coverage_score", sa.Numeric(5, 2), nullable=False),
        sa.Column("eligibility_status", sa.String(length=80), nullable=False),
        sa.Column("recommendation_type", sa.String(length=120), nullable=False),
        sa.Column("strengths", sa.JSON(), nullable=False),
        sa.Column("gaps", sa.JSON(), nullable=False),
        sa.Column("missing_information", sa.JSON(), nullable=False),
        sa.Column("hard_constraint_results", sa.JSON(), nullable=False),
        sa.Column("growth_opportunities", sa.JSON(), nullable=False),
        sa.Column("summary_explanation", sa.Text(), nullable=False),
        sa.Column("profile_snapshot_hash", sa.String(length=128), nullable=False),
        sa.Column("job_snapshot_hash", sa.String(length=128), nullable=False),
        sa.Column("configuration_hash", sa.String(length=128), nullable=False),
        sa.Column("is_stale", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
    )
    for column in [
        "run_id",
        "job_id",
        "profile_id",
        "scoring_version",
        "total_score",
        "eligibility_status",
        "recommendation_type",
        "profile_snapshot_hash",
        "job_snapshot_hash",
        "configuration_hash",
        "is_stale",
    ]:
        create_index_once(f"ix_job_evaluations_{column}", "job_evaluations", [column])

    create_table_once(
        "evaluation_components",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("evaluation_id", sa.Integer(), sa.ForeignKey("job_evaluations.id"), nullable=False),
        sa.Column("component_name", sa.String(length=120), nullable=False),
        sa.Column("weight", sa.Integer(), nullable=False),
        sa.Column("raw_score", sa.Numeric(5, 4), nullable=False),
        sa.Column("awarded_points", sa.Numeric(5, 2), nullable=False),
        sa.Column("confidence", sa.Numeric(5, 4), nullable=False),
        sa.Column("status", sa.String(length=80), nullable=False),
        sa.Column("evidence", sa.JSON(), nullable=False),
        sa.Column("missing_data", sa.JSON(), nullable=False),
        sa.Column("explanation", sa.Text(), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
    )
    create_index_once("ix_evaluation_components_evaluation_id", "evaluation_components", ["evaluation_id"])
    create_index_once("ix_evaluation_components_component_name", "evaluation_components", ["component_name"])


def downgrade() -> None:
    """Drop only Phase 4 tables. Run on disposable or backed-up databases."""

    inspector = sa.inspect(op.get_bind())
    existing_tables = set(inspector.get_table_names())
    if "evaluation_components" not in existing_tables:
        return
    op.drop_index("ix_evaluation_components_component_name", table_name="evaluation_components")
    op.drop_index("ix_evaluation_components_evaluation_id", table_name="evaluation_components")
    op.drop_table("evaluation_components")
    for column in [
        "is_stale",
        "configuration_hash",
        "job_snapshot_hash",
        "profile_snapshot_hash",
        "recommendation_type",
        "eligibility_status",
        "total_score",
        "scoring_version",
        "profile_id",
        "job_id",
        "run_id",
    ]:
        op.drop_index(f"ix_job_evaluations_{column}", table_name="job_evaluations")
    op.drop_table("job_evaluations")
    for column in ["status", "profile_snapshot_hash", "configuration_hash", "scoring_version", "profile_id"]:
        op.drop_index(f"ix_evaluation_runs_{column}", table_name="evaluation_runs")
    op.drop_table("evaluation_runs")
    op.drop_index("ix_job_requirements_is_active", table_name="job_requirements")
    op.drop_index("ix_job_requirements_importance", table_name="job_requirements")
    op.drop_index("ix_job_requirements_normalized_value", table_name="job_requirements")
    op.drop_index("ix_job_requirements_requirement_type", table_name="job_requirements")
    op.drop_index("ix_job_requirements_job_id", table_name="job_requirements")
    op.drop_table("job_requirements")

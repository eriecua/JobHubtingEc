"""Phase 6 controlled feedback learning.

Revision ID: 202607020005
Revises: 202607020004
Create Date: 2026-07-02
"""

from __future__ import annotations

from collections.abc import Sequence

from alembic import op
import sqlalchemy as sa


revision: str = "202607020005"
down_revision: str | None = "202607020004"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Create Phase 6 learning tables without touching previous schema."""

    inspector = sa.inspect(op.get_bind())
    existing_tables = set(inspector.get_table_names())

    if "application_outcomes" not in existing_tables:
        op.create_table(
            "application_outcomes",
            sa.Column("id", sa.Integer(), primary_key=True),
            sa.Column("application_id", sa.Integer(), sa.ForeignKey("applications.id"), nullable=False),
            sa.Column("outcome_type", sa.String(length=120), nullable=False),
            sa.Column("outcome_date", sa.Date(), nullable=False),
            sa.Column("stage", sa.String(length=120), nullable=False),
            sa.Column("company_response", sa.String(length=120), nullable=False),
            sa.Column("user_assessment", sa.String(length=120), nullable=True),
            sa.Column("salary_offered", sa.Numeric(12, 2), nullable=True),
            sa.Column("currency", sa.String(length=10), nullable=True),
            sa.Column("rejection_reason", sa.String(length=180), nullable=True),
            sa.Column("notes", sa.Text(), nullable=True),
            sa.Column("created_at", sa.DateTime(), nullable=False),
            sa.Column("updated_at", sa.DateTime(), nullable=False),
        )
        op.create_index("ix_application_outcomes_application_id", "application_outcomes", ["application_id"])
        op.create_index("ix_application_outcomes_outcome_type", "application_outcomes", ["outcome_type"])
        op.create_index("ix_application_outcomes_outcome_date", "application_outcomes", ["outcome_date"])
        op.create_index("ix_application_outcomes_stage", "application_outcomes", ["stage"])

    if "feedback_events" not in existing_tables:
        op.create_table(
            "feedback_events",
            sa.Column("id", sa.Integer(), primary_key=True),
            sa.Column("profile_id", sa.Integer(), sa.ForeignKey("professional_profiles.id"), nullable=False),
            sa.Column("job_id", sa.Integer(), sa.ForeignKey("jobs.id"), nullable=False),
            sa.Column("evaluation_id", sa.Integer(), sa.ForeignKey("job_evaluations.id"), nullable=True),
            sa.Column("priority_id", sa.Integer(), sa.ForeignKey("job_priorities.id"), nullable=True),
            sa.Column("application_id", sa.Integer(), sa.ForeignKey("applications.id"), nullable=True),
            sa.Column("event_type", sa.String(length=120), nullable=False),
            sa.Column("event_category", sa.String(length=80), nullable=False),
            sa.Column("signal_value", sa.Numeric(6, 3), nullable=False),
            sa.Column("reason_code", sa.String(length=160), nullable=True),
            sa.Column("notes", sa.Text(), nullable=True),
            sa.Column("source", sa.String(length=80), nullable=False),
            sa.Column("occurred_at", sa.DateTime(), nullable=False),
            sa.Column("created_at", sa.DateTime(), nullable=False),
            sa.Column("deduplication_key", sa.String(length=255), nullable=False),
            sa.Column("metadata_json", sa.JSON(), nullable=True),
            sa.UniqueConstraint("deduplication_key", name="uq_feedback_event_deduplication_key"),
        )
        for column in ["profile_id", "job_id", "evaluation_id", "priority_id", "application_id", "event_type", "event_category", "source", "occurred_at", "deduplication_key"]:
            op.create_index(f"ix_feedback_events_{column}", "feedback_events", [column])

    if "learning_runs" not in existing_tables:
        op.create_table(
            "learning_runs",
            sa.Column("id", sa.Integer(), primary_key=True),
            sa.Column("profile_id", sa.Integer(), sa.ForeignKey("professional_profiles.id"), nullable=False),
            sa.Column("learning_version", sa.String(length=80), nullable=False),
            sa.Column("configuration_hash", sa.String(length=128), nullable=False),
            sa.Column("period_start", sa.Date(), nullable=False),
            sa.Column("period_end", sa.Date(), nullable=False),
            sa.Column("started_at", sa.DateTime(), nullable=False),
            sa.Column("completed_at", sa.DateTime(), nullable=True),
            sa.Column("status", sa.String(length=80), nullable=False),
            sa.Column("feedback_events_considered", sa.Integer(), nullable=False),
            sa.Column("applications_considered", sa.Integer(), nullable=False),
            sa.Column("outcomes_considered", sa.Integer(), nullable=False),
            sa.Column("proposals_generated", sa.Integer(), nullable=False),
            sa.Column("warnings_json", sa.JSON(), nullable=True),
            sa.Column("error_summary", sa.Text(), nullable=True),
            sa.Column("created_at", sa.DateTime(), nullable=False),
        )
        for column in ["profile_id", "learning_version", "configuration_hash", "period_start", "period_end", "status"]:
            op.create_index(f"ix_learning_runs_{column}", "learning_runs", [column])

    if "learning_metrics" not in existing_tables:
        op.create_table(
            "learning_metrics",
            sa.Column("id", sa.Integer(), primary_key=True),
            sa.Column("learning_run_id", sa.Integer(), sa.ForeignKey("learning_runs.id"), nullable=False),
            sa.Column("metric_name", sa.String(length=160), nullable=False),
            sa.Column("metric_scope", sa.String(length=120), nullable=False),
            sa.Column("scope_value", sa.String(length=255), nullable=True),
            sa.Column("sample_size", sa.Integer(), nullable=False),
            sa.Column("metric_value", sa.Numeric(8, 4), nullable=False),
            sa.Column("baseline_value", sa.Numeric(8, 4), nullable=True),
            sa.Column("confidence_level", sa.String(length=80), nullable=False),
            sa.Column("explanation", sa.Text(), nullable=False),
            sa.Column("evidence_json", sa.JSON(), nullable=False),
            sa.Column("created_at", sa.DateTime(), nullable=False),
        )
        for column in ["learning_run_id", "metric_name", "metric_scope", "scope_value", "confidence_level"]:
            op.create_index(f"ix_learning_metrics_{column}", "learning_metrics", [column])

    if "adjustment_proposals" not in existing_tables:
        op.create_table(
            "adjustment_proposals",
            sa.Column("id", sa.Integer(), primary_key=True),
            sa.Column("learning_run_id", sa.Integer(), sa.ForeignKey("learning_runs.id"), nullable=False),
            sa.Column("profile_id", sa.Integer(), sa.ForeignKey("professional_profiles.id"), nullable=False),
            sa.Column("proposal_type", sa.String(length=160), nullable=False),
            sa.Column("target_key", sa.String(length=255), nullable=False),
            sa.Column("current_value_json", sa.JSON(), nullable=True),
            sa.Column("proposed_value_json", sa.JSON(), nullable=True),
            sa.Column("expected_effect", sa.Text(), nullable=False),
            sa.Column("evidence_summary", sa.Text(), nullable=False),
            sa.Column("evidence_json", sa.JSON(), nullable=False),
            sa.Column("sample_size", sa.Integer(), nullable=False),
            sa.Column("confidence_score", sa.Numeric(5, 2), nullable=False),
            sa.Column("risk_level", sa.String(length=80), nullable=False),
            sa.Column("status", sa.String(length=80), nullable=False),
            sa.Column("reviewed_at", sa.DateTime(), nullable=True),
            sa.Column("reviewed_by", sa.String(length=120), nullable=True),
            sa.Column("review_notes", sa.Text(), nullable=True),
            sa.Column("applied_at", sa.DateTime(), nullable=True),
            sa.Column("reverted_at", sa.DateTime(), nullable=True),
            sa.Column("created_at", sa.DateTime(), nullable=False),
            sa.Column("updated_at", sa.DateTime(), nullable=False),
        )
        for column in ["learning_run_id", "profile_id", "proposal_type", "target_key", "risk_level", "status"]:
            op.create_index(f"ix_adjustment_proposals_{column}", "adjustment_proposals", [column])

    if "configuration_change_history" not in existing_tables:
        op.create_table(
            "configuration_change_history",
            sa.Column("id", sa.Integer(), primary_key=True),
            sa.Column("proposal_id", sa.Integer(), sa.ForeignKey("adjustment_proposals.id"), nullable=True),
            sa.Column("profile_id", sa.Integer(), sa.ForeignKey("professional_profiles.id"), nullable=False),
            sa.Column("configuration_area", sa.String(length=160), nullable=False),
            sa.Column("previous_value_json", sa.JSON(), nullable=True),
            sa.Column("new_value_json", sa.JSON(), nullable=True),
            sa.Column("reason", sa.Text(), nullable=False),
            sa.Column("changed_by", sa.String(length=120), nullable=False),
            sa.Column("changed_at", sa.DateTime(), nullable=False),
            sa.Column("rollback_data_json", sa.JSON(), nullable=True),
            sa.Column("reverted_at", sa.DateTime(), nullable=True),
            sa.Column("reverted_by", sa.String(length=120), nullable=True),
        )
        for column in ["proposal_id", "profile_id", "configuration_area", "changed_at"]:
            op.create_index(f"ix_configuration_change_history_{column}", "configuration_change_history", [column])


def downgrade() -> None:
    """Drop only Phase 6 learning tables."""

    inspector = sa.inspect(op.get_bind())
    existing_tables = set(inspector.get_table_names())
    drop_order = [
        ("configuration_change_history", ["proposal_id", "profile_id", "configuration_area", "changed_at"]),
        ("adjustment_proposals", ["learning_run_id", "profile_id", "proposal_type", "target_key", "risk_level", "status"]),
        ("learning_metrics", ["learning_run_id", "metric_name", "metric_scope", "scope_value", "confidence_level"]),
        ("learning_runs", ["profile_id", "learning_version", "configuration_hash", "period_start", "period_end", "status"]),
        ("feedback_events", ["profile_id", "job_id", "evaluation_id", "priority_id", "application_id", "event_type", "event_category", "source", "occurred_at", "deduplication_key"]),
        ("application_outcomes", ["application_id", "outcome_type", "outcome_date", "stage"]),
    ]
    for table_name, columns in drop_order:
        if table_name not in existing_tables:
            continue
        for column in columns:
            op.drop_index(f"ix_{table_name}_{column}", table_name=table_name)
        op.drop_table(table_name)

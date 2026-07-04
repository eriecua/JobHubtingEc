"""Phase 7 authorized job source capture schema.

Revision ID: 202607030001
Revises: 202607020006
Create Date: 2026-07-03
"""

from __future__ import annotations

from collections.abc import Sequence

from alembic import op
import sqlalchemy as sa


revision: str = "202607030001"
down_revision: str | None = "202607020006"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def _tables() -> set[str]:
    return set(sa.inspect(op.get_bind()).get_table_names())


def _indexes(table_name: str) -> set[str]:
    return {index["name"] for index in sa.inspect(op.get_bind()).get_indexes(table_name)}


def upgrade() -> None:
    """Create non-destructive Phase 7 source capture tables."""

    tables = _tables()
    if "job_sources" not in tables:
        op.create_table(
            "job_sources",
            sa.Column("id", sa.Integer(), nullable=False),
            sa.Column("name", sa.String(length=255), nullable=False),
            sa.Column("source_type", sa.String(length=80), nullable=False),
            sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.true()),
            sa.Column("configuration", sa.JSON(), nullable=False),
            sa.Column("last_test_at", sa.DateTime(), nullable=True),
            sa.Column("last_test_status", sa.String(length=80), nullable=True),
            sa.Column("last_error", sa.Text(), nullable=True),
            sa.Column("created_at", sa.DateTime(), nullable=False),
            sa.Column("updated_at", sa.DateTime(), nullable=False),
            sa.PrimaryKeyConstraint("id"),
            sa.UniqueConstraint("name", name="uq_job_source_name"),
        )
        op.create_index(op.f("ix_job_sources_id"), "job_sources", ["id"], unique=False)
        op.create_index(op.f("ix_job_sources_is_active"), "job_sources", ["is_active"], unique=False)
        op.create_index(op.f("ix_job_sources_source_type"), "job_sources", ["source_type"], unique=False)

    tables = _tables()
    if "job_source_capture_runs" not in tables:
        op.create_table(
            "job_source_capture_runs",
            sa.Column("id", sa.Integer(), nullable=False),
            sa.Column("source_id", sa.Integer(), nullable=True),
            sa.Column("source_type", sa.String(length=80), nullable=False),
            sa.Column("status", sa.String(length=80), nullable=False),
            sa.Column("started_at", sa.DateTime(), nullable=False),
            sa.Column("completed_at", sa.DateTime(), nullable=True),
            sa.Column("records_found", sa.Integer(), nullable=False, server_default="0"),
            sa.Column("records_staged", sa.Integer(), nullable=False, server_default="0"),
            sa.Column("records_skipped", sa.Integer(), nullable=False, server_default="0"),
            sa.Column("errors_count", sa.Integer(), nullable=False, server_default="0"),
            sa.Column("error_summary", sa.Text(), nullable=True),
            sa.Column("import_batch_id", sa.Integer(), nullable=True),
            sa.ForeignKeyConstraint(["import_batch_id"], ["import_batches.id"]),
            sa.ForeignKeyConstraint(["source_id"], ["job_sources.id"]),
            sa.PrimaryKeyConstraint("id"),
        )
        op.create_index(op.f("ix_job_source_capture_runs_id"), "job_source_capture_runs", ["id"], unique=False)
        op.create_index(op.f("ix_job_source_capture_runs_import_batch_id"), "job_source_capture_runs", ["import_batch_id"], unique=False)
        op.create_index(op.f("ix_job_source_capture_runs_source_id"), "job_source_capture_runs", ["source_id"], unique=False)
        op.create_index(op.f("ix_job_source_capture_runs_source_type"), "job_source_capture_runs", ["source_type"], unique=False)
        op.create_index(op.f("ix_job_source_capture_runs_status"), "job_source_capture_runs", ["status"], unique=False)

    tables = _tables()
    if "captured_source_items" not in tables:
        op.create_table(
            "captured_source_items",
            sa.Column("id", sa.Integer(), nullable=False),
            sa.Column("source_id", sa.Integer(), nullable=True),
            sa.Column("capture_run_id", sa.Integer(), nullable=True),
            sa.Column("import_batch_id", sa.Integer(), nullable=True),
            sa.Column("staging_job_id", sa.Integer(), nullable=True),
            sa.Column("external_id", sa.String(length=500), nullable=True),
            sa.Column("source_uri", sa.String(length=1000), nullable=True),
            sa.Column("filename", sa.String(length=255), nullable=True),
            sa.Column("content_hash", sa.String(length=128), nullable=False),
            sa.Column("raw_content", sa.Text(), nullable=True),
            sa.Column("raw_metadata", sa.JSON(), nullable=True),
            sa.Column("status", sa.String(length=80), nullable=False),
            sa.Column("error_message", sa.Text(), nullable=True),
            sa.Column("captured_at", sa.DateTime(), nullable=False),
            sa.ForeignKeyConstraint(["capture_run_id"], ["job_source_capture_runs.id"]),
            sa.ForeignKeyConstraint(["import_batch_id"], ["import_batches.id"]),
            sa.ForeignKeyConstraint(["source_id"], ["job_sources.id"]),
            sa.ForeignKeyConstraint(["staging_job_id"], ["import_staging_jobs.id"]),
            sa.PrimaryKeyConstraint("id"),
        )
        op.create_index(op.f("ix_captured_source_items_capture_run_id"), "captured_source_items", ["capture_run_id"], unique=False)
        op.create_index(op.f("ix_captured_source_items_content_hash"), "captured_source_items", ["content_hash"], unique=False)
        op.create_index(op.f("ix_captured_source_items_external_id"), "captured_source_items", ["external_id"], unique=False)
        op.create_index(op.f("ix_captured_source_items_id"), "captured_source_items", ["id"], unique=False)
        op.create_index(op.f("ix_captured_source_items_import_batch_id"), "captured_source_items", ["import_batch_id"], unique=False)
        op.create_index(op.f("ix_captured_source_items_source_id"), "captured_source_items", ["source_id"], unique=False)
        op.create_index(op.f("ix_captured_source_items_staging_job_id"), "captured_source_items", ["staging_job_id"], unique=False)
        op.create_index(op.f("ix_captured_source_items_status"), "captured_source_items", ["status"], unique=False)


def downgrade() -> None:
    """Drop Phase 7 tables only."""

    tables = _tables()
    if "captured_source_items" in tables:
        for index_name in _indexes("captured_source_items"):
            op.drop_index(index_name, table_name="captured_source_items")
        op.drop_table("captured_source_items")
    tables = _tables()
    if "job_source_capture_runs" in tables:
        for index_name in _indexes("job_source_capture_runs"):
            op.drop_index(index_name, table_name="job_source_capture_runs")
        op.drop_table("job_source_capture_runs")
    tables = _tables()
    if "job_sources" in tables:
        for index_name in _indexes("job_sources"):
            op.drop_index(index_name, table_name="job_sources")
        op.drop_table("job_sources")

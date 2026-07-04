"""Repositories for Phase 7 authorized job source capture."""

from __future__ import annotations

import hashlib
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import CapturedSourceItem, ImportStagingJob, JobSource, JobSourceCaptureRun
from app.models.database_models import utc_now
from app.services.source_security import validate_non_sensitive_config
from app.services.validation import ValidationError, require_text


class JobSourceRepository:
    """Manage configured job sources and capture audit records."""

    def __init__(self, session: Session) -> None:
        self.session = session

    def create_source(self, **data: Any) -> JobSource:
        """Create a source configuration without storing credentials."""

        configuration = data.get("configuration") or {}
        validate_non_sensitive_config(configuration)
        source = JobSource(
            name=require_text(data.get("name"), "Nombre de fuente"),
            source_type=require_text(data.get("source_type"), "Tipo de fuente"),
            is_active=bool(data.get("is_active", True)),
            configuration=configuration,
        )
        self.session.add(source)
        self.session.commit()
        self.session.refresh(source)
        return source

    def update_source(self, source_id: int, **data: Any) -> JobSource:
        """Update source metadata and non-sensitive configuration."""

        source = self.get_source(source_id)
        if "name" in data:
            source.name = require_text(data.get("name"), "Nombre de fuente")
        if "source_type" in data:
            source.source_type = require_text(data.get("source_type"), "Tipo de fuente")
        if "is_active" in data:
            source.is_active = bool(data.get("is_active"))
        if "configuration" in data:
            configuration = data.get("configuration") or {}
            validate_non_sensitive_config(configuration)
            source.configuration = configuration
        self.session.commit()
        self.session.refresh(source)
        return source

    def set_active(self, source_id: int, is_active: bool) -> JobSource:
        """Activate or deactivate a source."""

        return self.update_source(source_id, is_active=is_active)

    def save_test_result(self, source_id: int, status: str, error: str | None = None) -> JobSource:
        """Persist the last connection test result."""

        source = self.get_source(source_id)
        source.last_test_at = utc_now()
        source.last_test_status = status
        source.last_error = error
        self.session.commit()
        self.session.refresh(source)
        return source

    def get_source(self, source_id: int) -> JobSource:
        """Return a configured source or raise."""

        source = self.session.get(JobSource, source_id)
        if source is None:
            raise ValidationError("No se encontro la fuente configurada.")
        return source

    def list_sources(self, include_inactive: bool = True) -> list[JobSource]:
        """List configured sources."""

        statement = select(JobSource).order_by(JobSource.created_at.desc())
        if not include_inactive:
            statement = statement.where(JobSource.is_active.is_(True))
        return list(self.session.scalars(statement))

    def create_run(self, source: JobSource | None, source_type: str) -> JobSourceCaptureRun:
        """Create a capture run audit row."""

        run = JobSourceCaptureRun(
            source_id=source.id if source else None,
            source_type=source.source_type if source else source_type,
            status="Ejecutando",
        )
        self.session.add(run)
        self.session.commit()
        self.session.refresh(run)
        return run

    def complete_run(
        self,
        run_id: int,
        *,
        status: str,
        records_found: int = 0,
        records_staged: int = 0,
        records_skipped: int = 0,
        errors_count: int = 0,
        error_summary: str | None = None,
        import_batch_id: int | None = None,
    ) -> JobSourceCaptureRun:
        """Mark a run as completed or failed."""

        run = self.get_run(run_id)
        run.status = status
        run.records_found = records_found
        run.records_staged = records_staged
        run.records_skipped = records_skipped
        run.errors_count = errors_count
        run.error_summary = error_summary
        run.import_batch_id = import_batch_id
        run.completed_at = utc_now()
        self.session.commit()
        self.session.refresh(run)
        return run

    def get_run(self, run_id: int) -> JobSourceCaptureRun:
        """Return a capture run or raise."""

        run = self.session.get(JobSourceCaptureRun, run_id)
        if run is None:
            raise ValidationError("No se encontro la ejecucion de captura.")
        return run

    def list_runs(self, limit: int = 50) -> list[JobSourceCaptureRun]:
        """Return recent capture runs."""

        return list(
            self.session.scalars(
                select(JobSourceCaptureRun).order_by(JobSourceCaptureRun.started_at.desc()).limit(limit)
            )
        )

    def has_seen_item(self, source_id: int | None, content_hash: str, external_id: str | None = None) -> bool:
        """Return whether a source item was already captured."""

        statement = select(CapturedSourceItem).where(CapturedSourceItem.content_hash == content_hash)
        if source_id is not None:
            statement = statement.where(CapturedSourceItem.source_id == source_id)
        if external_id:
            external_statement = select(CapturedSourceItem).where(CapturedSourceItem.external_id == external_id)
            if source_id is not None:
                external_statement = external_statement.where(CapturedSourceItem.source_id == source_id)
            if self.session.scalar(external_statement):
                return True
        return self.session.scalar(statement) is not None

    def has_seen_file(self, source_id: int | None, filename: str | None, file_hash: str | None) -> bool:
        """Return whether a local source file was already captured."""

        if not filename or not file_hash:
            return False
        statement = select(CapturedSourceItem).where(CapturedSourceItem.filename == filename)
        if source_id is not None:
            statement = statement.where(CapturedSourceItem.source_id == source_id)
        for item in self.session.scalars(statement):
            metadata = item.raw_metadata or {}
            if metadata.get("_file_hash") == file_hash:
                return True
        return False

    def record_item(
        self,
        *,
        source_id: int | None,
        capture_run_id: int | None,
        import_batch_id: int | None,
        staging_job_id: int | None,
        external_id: str | None,
        source_uri: str | None,
        filename: str | None,
        raw_content: str | None,
        raw_metadata: dict[str, Any] | None,
        status: str,
        error_message: str | None = None,
        content_hash: str | None = None,
    ) -> CapturedSourceItem:
        """Record one external item and its staging link."""

        item_hash = content_hash or stable_content_hash(raw_content or raw_metadata or {})
        item = CapturedSourceItem(
            source_id=source_id,
            capture_run_id=capture_run_id,
            import_batch_id=import_batch_id,
            staging_job_id=staging_job_id,
            external_id=external_id,
            source_uri=source_uri,
            filename=filename,
            content_hash=item_hash,
            raw_content=raw_content,
            raw_metadata=raw_metadata,
            status=status,
            error_message=error_message,
        )
        self.session.add(item)
        self.session.commit()
        self.session.refresh(item)
        return item

    def link_staging_rows(
        self,
        *,
        source_id: int | None,
        capture_run_id: int | None,
        import_batch_id: int,
        raw_items: list[dict[str, Any]],
    ) -> None:
        """Create captured item rows for each staging row in an import batch."""

        rows = list(
            self.session.scalars(
                select(ImportStagingJob)
                .where(ImportStagingJob.import_batch_id == import_batch_id)
                .order_by(ImportStagingJob.row_number)
            )
        )
        for row, raw_item in zip(rows, raw_items, strict=False):
            self.record_item(
                source_id=source_id,
                capture_run_id=capture_run_id,
                import_batch_id=import_batch_id,
                staging_job_id=row.id,
                external_id=raw_item.get("external_id") or raw_item.get("source_record_id"),
                source_uri=raw_item.get("source_url"),
                filename=raw_item.get("_filename"),
                raw_content=raw_item.get("_raw_content"),
                raw_metadata=raw_item,
                status="Staged" if row.validation_status != "Invalida" else "Error",
                error_message="; ".join(row.validation_errors or []) or None,
                content_hash=raw_item.get("_capture_hash"),
            )


def stable_content_hash(value: Any) -> str:
    """Return a stable SHA-256 hash for source idempotency."""

    import json

    encoded = json.dumps(value, sort_keys=True, ensure_ascii=False, default=str).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()

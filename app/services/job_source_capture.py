"""Capture orchestration for authorized job sources."""

from __future__ import annotations

from typing import Any

from sqlalchemy.orm import Session

from app.config import PROJECT_ROOT, load_yaml_file
from app.repositories import ImportBatchRepository, JobSourceRepository, StagingJobRepository
from app.services.job_import import JobImportService
from app.services.job_source_connectors import connector_for, quick_link_record
from app.services.job_source_connectors import EMLFileConnector
from app.services.job_source_types import CaptureContext, CapturedJobRecord, ConnectionTestResult
from app.services.validation import ValidationError
from app.repositories.job_source_repository import stable_content_hash


class JobSourceCaptureService:
    """Coordinate connector execution and staging for human review."""

    def __init__(self, session: Session) -> None:
        self.session = session
        self.source_repo = JobSourceRepository(session)
        self.config = load_yaml_file(PROJECT_ROOT / "config" / "job_sources.yaml")

    def test_source(self, source_id: int) -> ConnectionTestResult:
        """Run a source configuration test and persist its result."""

        source = self.source_repo.get_source(source_id)
        connector = connector_for(source.source_type)
        context = self._context(source)
        try:
            result = connector.test_connection(context)
        except ValidationError as exc:
            result = ConnectionTestResult(False, str(exc))
        self.source_repo.save_test_result(source.id, "Correcta" if result.ok else "Fallida", None if result.ok else result.message)
        return result

    def capture_source(self, source_id: int) -> int:
        """Capture a configured source into staging and return the import batch id."""

        source = self.source_repo.get_source(source_id)
        if not source.is_active:
            raise ValidationError("La fuente esta desactivada.")
        connector = connector_for(source.source_type)
        run = self.source_repo.create_run(source, source.source_type)
        try:
            result = connector.capture(self._context(source))
            batch_id, staged_count, skipped_count = self._stage_records(
                source_id=source.id,
                capture_run_id=run.id,
                source_type=source.source_type,
                source_name=source.name,
                records=result.records,
            )
            status = "Completado con errores" if result.errors else "Completado"
            self.source_repo.complete_run(
                run.id,
                status=status,
                records_found=len(result.records),
                records_staged=staged_count,
                records_skipped=skipped_count + result.skipped,
                errors_count=len(result.errors),
                error_summary="; ".join(result.errors) or None,
                import_batch_id=batch_id,
            )
            return batch_id
        except Exception as exc:
            self.source_repo.complete_run(run.id, status="Fallido", errors_count=1, error_summary=str(exc))
            raise

    def capture_quick_link(self, *, url: str, title: str = "", company: str = "", city: str = "", notes: str = "") -> int:
        """Stage a manually entered link without scraping it."""

        run = self.source_repo.create_run(None, "QUICK_LINK")
        record = quick_link_record(url, "Enlace manual", title=title, company=company, city=city, notes=notes)
        batch_id, staged_count, skipped_count = self._stage_records(
            source_id=None,
            capture_run_id=run.id,
            source_type="QUICK_LINK",
            source_name="Enlace manual",
            records=[record],
        )
        self.source_repo.complete_run(
            run.id,
            status="Completado",
            records_found=1,
            records_staged=staged_count,
            records_skipped=skipped_count,
            import_batch_id=batch_id,
        )
        return batch_id

    def capture_uploaded_eml(self, *, filename: str, content: bytes, source_name: str = "EML manual") -> int:
        """Stage an uploaded EML file without connecting to any mailbox."""

        run = self.source_repo.create_run(None, "EML_FILE")
        context = CaptureContext(
            source_id=None,
            source_name=source_name,
            source_type="EML_FILE",
            configuration={"filename": filename, "content_bytes": content},
        )
        result = EMLFileConnector().capture(context)
        batch_id, staged_count, skipped_count = self._stage_records(
            source_id=None,
            capture_run_id=run.id,
            source_type="EML_FILE",
            source_name=source_name,
            records=result.records,
        )
        self.source_repo.complete_run(
            run.id,
            status="Completado con errores" if result.errors else "Completado",
            records_found=len(result.records),
            records_staged=staged_count,
            records_skipped=skipped_count,
            errors_count=len(result.errors),
            error_summary="; ".join(result.errors) or None,
            import_batch_id=batch_id,
        )
        return batch_id

    def _stage_records(
        self,
        *,
        source_id: int | None,
        capture_run_id: int | None,
        source_type: str,
        source_name: str,
        records: list[CapturedJobRecord],
    ) -> tuple[int, int, int]:
        if not records:
            batch = ImportBatchRepository(self.session).create_batch(
                source_type=source_type,
                source_name=source_name,
                status="Completado",
            )
            return batch.id, 0, 0
        prepared: list[dict[str, Any]] = []
        skipped = 0
        for record in records:
            raw = dict(record.raw)
            raw["_raw_content"] = record.raw_content
            raw["_filename"] = record.filename
            file_hash = raw.get("_file_hash")
            allow_reprocess = bool(raw.get("_allow_reprocess", False))
            raw["_capture_hash"] = stable_content_hash(
                {
                    "external_id": record.external_id,
                    "source_uri": record.source_uri,
                    "raw": record.raw,
                    "raw_content": record.raw_content,
                }
            )
            raw["source"] = raw.get("source") or source_name
            if not allow_reprocess and self.source_repo.has_seen_file(source_id, record.filename, file_hash):
                skipped += 1
                self.source_repo.record_item(
                    source_id=source_id,
                    capture_run_id=capture_run_id,
                    import_batch_id=None,
                    staging_job_id=None,
                    external_id=record.external_id,
                    source_uri=record.source_uri,
                    filename=record.filename,
                    raw_content=record.raw_content,
                    raw_metadata=raw,
                    status="Duplicado",
                    content_hash=raw["_capture_hash"],
                    error_message="Archivo ya procesado con el mismo hash.",
                )
                continue
            if not allow_reprocess and self.source_repo.has_seen_item(source_id, raw["_capture_hash"], record.external_id):
                skipped += 1
                self.source_repo.record_item(
                    source_id=source_id,
                    capture_run_id=capture_run_id,
                    import_batch_id=None,
                    staging_job_id=None,
                    external_id=record.external_id,
                    source_uri=record.source_uri,
                    filename=record.filename,
                    raw_content=record.raw_content,
                    raw_metadata=raw,
                    status="Duplicado",
                    content_hash=raw["_capture_hash"],
                )
                continue
            prepared.append(raw)
        batch_id = JobImportService(self.session).stage_records(
            prepared,
            source_type=source_type,
            source_name=source_name,
        )
        self.source_repo.link_staging_rows(
            source_id=source_id,
            capture_run_id=capture_run_id,
            import_batch_id=batch_id,
            raw_items=prepared,
        )
        return batch_id, len(prepared), skipped

    def _context(self, source) -> CaptureContext:
        limits = self.config.get("remote_limits", {})
        return CaptureContext(
            source_id=source.id,
            source_name=source.name,
            source_type=source.source_type,
            configuration=source.configuration or {},
            timeout_seconds=int(limits.get("timeout_seconds", 10)),
            max_response_bytes=int(limits.get("max_response_bytes", 1_048_576)),
            max_records=int(limits.get("max_records", 50)),
            max_pages=int(limits.get("max_pages", 3)),
        )

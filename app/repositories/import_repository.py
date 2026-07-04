"""Repositories for job import batches and staging rows."""

from __future__ import annotations

from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import ImportBatch, ImportStagingJob, JobImportError
from app.models.database_models import utc_now
from app.services.validation import ValidationError


class ImportBatchRepository:
    """Manage import batch audit records."""

    def __init__(self, session: Session) -> None:
        self.session = session

    def create_batch(self, **data: Any) -> ImportBatch:
        """Create an import batch."""

        batch = ImportBatch(source_type=data["source_type"], source_name=data.get("source_name"), filename=data.get("filename"), file_hash=data.get("file_hash"), status=data.get("status", "Creado"), created_by=data.get("created_by"))
        self.session.add(batch)
        self.session.commit()
        self.session.refresh(batch)
        return batch

    def update_status(self, batch_id: int, status: str, error_summary: str | None = None) -> ImportBatch:
        """Update batch status."""

        batch = self.get_batch(batch_id)
        batch.status = status
        batch.error_summary = error_summary
        if status in {"Completado", "Completado con errores", "Fallido", "Cancelado"}:
            batch.completed_at = utc_now()
        self.session.commit()
        self.session.refresh(batch)
        return batch

    def save_statistics(self, batch_id: int, **stats: int) -> ImportBatch:
        """Persist batch statistics."""

        batch = self.get_batch(batch_id)
        for key, value in stats.items():
            if hasattr(batch, key):
                setattr(batch, key, value)
        self.session.commit()
        self.session.refresh(batch)
        return batch

    def get_batch(self, batch_id: int) -> ImportBatch:
        """Return a batch or raise."""

        batch = self.session.get(ImportBatch, batch_id)
        if batch is None:
            raise ValidationError("No se encontro el lote de importacion.")
        return batch

    def list_batches(self) -> list[ImportBatch]:
        """Return import history."""

        return list(self.session.scalars(select(ImportBatch).order_by(ImportBatch.created_at.desc())))

    def register_error(self, batch_id: int, **data: Any) -> JobImportError:
        """Register an import error."""

        error = JobImportError(
            import_batch_id=batch_id,
            staging_job_id=data.get("staging_job_id"),
            row_number=data.get("row_number"),
            field_name=data.get("field_name"),
            error_code=data["error_code"],
            error_message=data["error_message"],
            raw_value=data.get("raw_value"),
            severity=data.get("severity", "Error"),
        )
        self.session.add(error)
        self.session.commit()
        self.session.refresh(error)
        return error


class StagingJobRepository:
    """Manage temporary import rows awaiting user decisions."""

    def __init__(self, session: Session) -> None:
        self.session = session

    def save_row(self, **data: Any) -> ImportStagingJob:
        """Save a staging row."""

        row = ImportStagingJob(**data)
        self.session.add(row)
        self.session.commit()
        self.session.refresh(row)
        return row

    def update_parsed_data(self, staging_job_id: int, parsed_data: dict[str, Any], validation_status: str = "Valida") -> ImportStagingJob:
        """Update corrected parsed data for a staging row."""

        row = self.get_row(staging_job_id)
        row.parsed_data = parsed_data
        row.validation_status = validation_status
        row.validation_errors = None
        self.session.commit()
        self.session.refresh(row)
        return row

    def register_decision(self, staging_job_id: int, decision: str) -> ImportStagingJob:
        """Register a user decision for a staging row."""

        row = self.get_row(staging_job_id)
        row.user_decision = decision
        self.session.commit()
        self.session.refresh(row)
        return row

    def list_by_batch(self, batch_id: int, status: str | None = None) -> list[ImportStagingJob]:
        """List staging rows for a batch."""

        statement = select(ImportStagingJob).where(ImportStagingJob.import_batch_id == batch_id)
        if status:
            statement = statement.where(ImportStagingJob.validation_status == status)
        return list(self.session.scalars(statement.order_by(ImportStagingJob.row_number)))

    def get_row(self, staging_job_id: int) -> ImportStagingJob:
        """Return a staging row or raise."""

        row = self.session.get(ImportStagingJob, staging_job_id)
        if row is None:
            raise ValidationError("No se encontro la fila temporal.")
        return row

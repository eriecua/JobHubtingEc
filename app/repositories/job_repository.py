"""Repository for job vacancy records."""

from __future__ import annotations

from typing import Any

from sqlalchemy import func, or_, select
from sqlalchemy.orm import Session

from app.config import load_job_import_config
from app.models import Job, JobStatusHistory, JobTag, JobTagAssignment
from app.services.job_duplicate import DuplicateResult, JobDuplicateService
from app.services.job_normalization import JobNormalizationService
from app.services.job_quality import JobQualityService, SuspiciousJobService
from app.services.validation import ValidationError
from app.utils.normalization import normalize_text


class JobRepository:
    """Data access and business validation for job vacancies."""

    def __init__(self, session: Session) -> None:
        self.session = session
        self.config = load_job_import_config()
        self.normalizer = JobNormalizationService()
        self.quality = JobQualityService()
        self.suspicious = SuspiciousJobService()

    def create_job(
        self,
        data: dict[str, Any],
        confirm_possible_duplicate: bool = False,
        source: str = "Usuario",
        commit: bool = True,
    ) -> tuple[Job, DuplicateResult]:
        """Create a job after validation, normalization and duplicate checks."""

        normalized, warnings = self.normalizer.normalize_job_data(data)
        duplicate = JobDuplicateService(self.session).detect(normalized)
        if duplicate.status in {"Duplicado exacto", "Posible duplicado"} and not confirm_possible_duplicate:
            raise ValidationError(f"{duplicate.status}: requiere confirmacion humana antes de guardar.")
        quality = self.quality.evaluate(normalized)
        suspicious = self.suspicious.evaluate(normalized)
        normalized.update(
            {
                "data_quality_status": quality.status,
                "is_suspicious": suspicious.is_suspicious,
                "suspicious_reason": "; ".join(suspicious.reasons) if suspicious.reasons else None,
                "is_duplicate": duplicate.status in {"Duplicado exacto", "Posible duplicado"},
                "duplicate_of_job_id": duplicate.job_id if duplicate.status != "No duplicada" else None,
            }
        )
        if warnings:
            normalized["notes"] = self._append_notes(normalized.get("notes"), "Advertencias: " + "; ".join(warnings))
        job = Job(**normalized)
        self.session.add(job)
        self.session.flush()
        self._record_status(job.id, None, job.status, "Creacion de vacante", source)
        if commit:
            self.session.commit()
            self.session.refresh(job)
        return job, duplicate

    def get_job(self, job_id: int) -> Job | None:
        """Return a job by ID."""

        return self.session.get(Job, job_id)

    def update_job(self, job_id: int, data: dict[str, Any], commit: bool = True) -> Job:
        """Update a job with normalized data."""

        job = self.session.get(Job, job_id)
        if job is None:
            raise ValidationError("No se encontro la vacante.")
        merged = {column.name: getattr(job, column.name) for column in Job.__table__.columns}
        merged.update(data)
        normalized, _warnings = self.normalizer.normalize_job_data(merged)
        quality = self.quality.evaluate(normalized)
        suspicious = self.suspicious.evaluate(normalized)
        normalized["data_quality_status"] = quality.status
        normalized["is_suspicious"] = suspicious.is_suspicious
        normalized["suspicious_reason"] = "; ".join(suspicious.reasons) if suspicious.reasons else None
        for key, value in normalized.items():
            if hasattr(job, key):
                setattr(job, key, value)
        if commit:
            self.session.commit()
            self.session.refresh(job)
        else:
            self.session.flush()
        return job

    def fill_empty_fields(self, job_id: int, data: dict[str, Any], commit: bool = True) -> Job:
        """Complete only empty fields on an existing job."""

        job = self.session.get(Job, job_id)
        if job is None:
            raise ValidationError("No se encontro la vacante.")
        update_data = {}
        for column in Job.__table__.columns:
            field = column.name
            if field in {"id", "created_at", "updated_at"}:
                continue
            current_value = getattr(job, field)
            new_value = data.get(field)
            if current_value in (None, "", [], {}) and new_value not in (None, "", [], {}):
                update_data[field] = new_value
        if update_data:
            return self.update_job(job_id, update_data, commit=commit)
        if commit:
            self.session.commit()
            self.session.refresh(job)
        return job

    def list_jobs(self, filters: dict[str, Any] | None = None, limit: int = 100) -> list[Job]:
        """List jobs with simple repository-level filters."""

        filters = filters or {}
        statement = select(Job).where(Job.is_active.is_(filters.get("is_active", True)))
        if filters.get("text"):
            pattern = f"%{filters['text']}%"
            statement = statement.where(or_(Job.title.ilike(pattern), Job.company.ilike(pattern), Job.description.ilike(pattern)))
        for field in ["city", "province", "modality", "source", "sector", "status", "data_quality_status", "review_status"]:
            if filters.get(field):
                statement = statement.where(getattr(Job, field) == filters[field])
        if filters.get("is_duplicate") is not None:
            statement = statement.where(Job.is_duplicate.is_(bool(filters["is_duplicate"])))
        if filters.get("is_suspicious") is not None:
            statement = statement.where(Job.is_suspicious.is_(bool(filters["is_suspicious"])))
        if filters.get("salary_min") is not None:
            statement = statement.where(Job.salary_min >= filters["salary_min"])
        return list(self.session.scalars(statement.order_by(Job.created_at.desc()).limit(limit)))

    def change_status(self, job_id: int, new_status: str, reason: str | None = None, source: str = "Usuario") -> Job:
        """Change job status and record history."""

        if new_status not in self.config["job_statuses"]:
            raise ValidationError("Estado de vacante no permitido.")
        job = self.session.get(Job, job_id)
        if job is None:
            raise ValidationError("No se encontro la vacante.")
        previous = job.status
        job.status = new_status
        self._record_status(job.id, previous, new_status, reason, source)
        self.session.commit()
        self.session.refresh(job)
        return job

    def logical_delete(self, job_id: int, reason: str | None = None) -> Job:
        """Logically delete a job without removing it physically."""

        job = self.change_status(job_id, "Eliminada logicamente", reason, "Usuario")
        job.is_active = False
        self.session.commit()
        return job

    def restore(self, job_id: int, reason: str | None = None) -> Job:
        """Restore a logically deleted job."""

        job = self.session.get(Job, job_id)
        if job is None:
            raise ValidationError("No se encontro la vacante.")
        job.is_active = True
        previous = job.status
        job.status = "Activa"
        self._record_status(job.id, previous, "Activa", reason, "Usuario")
        self.session.commit()
        self.session.refresh(job)
        return job

    def count_by_status(self) -> dict[str, int]:
        """Count active jobs by status."""

        rows = self.session.execute(select(Job.status, func.count(Job.id)).group_by(Job.status)).all()
        return {status: count for status, count in rows}

    def find_duplicate_candidates(self, data: dict[str, Any]) -> DuplicateResult:
        """Detect duplicate candidates for a prospective job."""

        normalized, _warnings = self.normalizer.normalize_job_data(data)
        return JobDuplicateService(self.session).detect(normalized)

    def get_status_history(self, job_id: int) -> list[JobStatusHistory]:
        """Return status history for a job."""

        return list(
            self.session.scalars(
                select(JobStatusHistory).where(JobStatusHistory.job_id == job_id).order_by(JobStatusHistory.changed_at)
            )
        )

    def create_or_get_tag(self, name: str) -> JobTag:
        """Create or return a normalized tag."""

        normalized = normalize_text(name)
        if not normalized:
            raise ValidationError("La etiqueta es obligatoria.")
        existing = self.session.scalar(select(JobTag).where(JobTag.normalized_name == normalized))
        if existing:
            return existing
        tag = JobTag(name=name.strip(), normalized_name=normalized)
        self.session.add(tag)
        self.session.commit()
        self.session.refresh(tag)
        return tag

    def assign_tag(self, job_id: int, tag_name: str) -> JobTagAssignment:
        """Assign a tag without duplicating the association."""

        tag = self.create_or_get_tag(tag_name)
        existing = self.session.scalar(
            select(JobTagAssignment).where(JobTagAssignment.job_id == job_id, JobTagAssignment.tag_id == tag.id)
        )
        if existing:
            return existing
        assignment = JobTagAssignment(job_id=job_id, tag_id=tag.id)
        self.session.add(assignment)
        self.session.commit()
        self.session.refresh(assignment)
        return assignment

    def _record_status(
        self,
        job_id: int,
        previous_status: str | None,
        new_status: str,
        reason: str | None,
        source: str,
    ) -> None:
        history = JobStatusHistory(
            job_id=job_id,
            previous_status=previous_status,
            new_status=new_status,
            reason=reason,
            source=source,
        )
        self.session.add(history)

    def _append_notes(self, notes: str | None, addition: str) -> str:
        return f"{notes}\n{addition}" if notes else addition

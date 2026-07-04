"""Deterministic duplicate detection for job vacancies."""

from __future__ import annotations

from dataclasses import dataclass, field
from difflib import SequenceMatcher
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.config import load_job_import_config
from app.models import Job
from app.utils.normalization import normalize_text


@dataclass
class DuplicateResult:
    """Duplicate detection result with explanation."""

    status: str
    score: int = 0
    job_id: int | None = None
    explanation: list[str] = field(default_factory=list)
    changed_fields: dict[str, tuple[Any, Any]] = field(default_factory=dict)


class JobDuplicateService:
    """Detect exact, probable and potential-update duplicates."""

    def __init__(self, session: Session, preload_existing: bool = False) -> None:
        self.session = session
        self.thresholds = load_job_import_config()["duplicate_thresholds"]
        self._preloaded_jobs = (
            list(self.session.scalars(select(Job).where(Job.is_active.is_(True))).all())
            if preload_existing
            else None
        )

    def detect(self, data: dict[str, Any]) -> DuplicateResult:
        """Detect duplicate status against persisted jobs."""

        exact = self._exact_duplicate(data)
        if exact:
            changes = self._changed_fields(exact, data)
            if changes:
                return DuplicateResult("Actualizacion potencial", 100, exact.id, ["Coincide por identificador exacto y trae cambios."], changes)
            return DuplicateResult("Duplicado exacto", 100, exact.id, ["Coincide por external_id, URL o hash."])

        best_job: Job | None = None
        best_score = 0
        best_explanation: list[str] = []
        for candidate in self._candidate_jobs(data):
            score, explanation = self._similarity(candidate, data)
            if score > best_score:
                best_job = candidate
                best_score = score
                best_explanation = explanation
        if best_job and best_score >= self.thresholds["exact"]:
            return DuplicateResult("Duplicado exacto", best_score, best_job.id, best_explanation)
        if best_job and best_score >= self.thresholds["probable"]:
            return DuplicateResult("Posible duplicado", best_score, best_job.id, best_explanation)
        if best_job and best_score >= self.thresholds["relevant"]:
            return DuplicateResult("Pendiente de revision", best_score, best_job.id, best_explanation)
        return DuplicateResult("No duplicada", best_score, None, best_explanation)

    def _exact_duplicate(self, data: dict[str, Any]) -> Job | None:
        if self._preloaded_jobs is not None:
            for job in self._preloaded_jobs:
                if data.get("external_id") and job.source == data.get("source") and job.external_id == data.get("external_id"):
                    return job
                if data.get("source_url") and job.source == data.get("source") and job.source_url == data.get("source_url"):
                    return job
                if data.get("content_hash") and job.content_hash == data.get("content_hash"):
                    return job
            return None
        if data.get("external_id"):
            found = self.session.scalar(
                select(Job).where(Job.source == data.get("source"), Job.external_id == data.get("external_id"))
            )
            if found:
                return found
        if data.get("source_url"):
            found = self.session.scalar(
                select(Job).where(Job.source == data.get("source"), Job.source_url == data.get("source_url"))
            )
            if found:
                return found
        if data.get("content_hash"):
            return self.session.scalar(select(Job).where(Job.content_hash == data.get("content_hash")))
        return None

    def _candidate_jobs(self, data: dict[str, Any]) -> list[Job]:
        if self._preloaded_jobs is not None:
            if data.get("normalized_company"):
                return [job for job in self._preloaded_jobs if job.normalized_company == data.get("normalized_company")]
            return self._preloaded_jobs
        statement = select(Job).where(Job.is_active.is_(True))
        if data.get("normalized_company"):
            statement = statement.where(Job.normalized_company == data.get("normalized_company"))
        return list(self.session.scalars(statement).all())

    def _similarity(self, job: Job, data: dict[str, Any]) -> tuple[int, list[str]]:
        title = self._ratio(job.normalized_title, data.get("normalized_title"))
        company = self._ratio(job.normalized_company, data.get("normalized_company"))
        city = 100 if normalize_text(job.city or "") == normalize_text(str(data.get("city") or "")) and data.get("city") else 0
        source = 100 if normalize_text(job.source or "") == normalize_text(str(data.get("source") or "")) else 0
        date_score = 0
        if job.publication_date and data.get("publication_date"):
            delta = abs((job.publication_date - data["publication_date"]).days)
            date_score = max(0, 100 - min(delta, 10) * 10)
        description = self._ratio(job.description[:500], str(data.get("description") or "")[:500])
        score = round(title * 0.30 + company * 0.30 + city * 0.10 + date_score * 0.10 + source * 0.05 + description * 0.15)
        explanation = [
            f"Cargo: {title}/100",
            f"Empresa: {company}/100",
            f"Ciudad: {city}/100",
            f"Fecha: {date_score}/100",
            f"Fuente: {source}/100",
            f"Descripcion: {description}/100",
        ]
        return score, explanation

    def _ratio(self, left: str | None, right: str | None) -> int:
        return round(SequenceMatcher(None, normalize_text(left or ""), normalize_text(right or "")).ratio() * 100)

    def _changed_fields(self, job: Job, data: dict[str, Any]) -> dict[str, tuple[Any, Any]]:
        changes: dict[str, tuple[Any, Any]] = {}
        for field in ["salary_min", "salary_max", "expiration_date", "description", "requirements", "responsibilities"]:
            old = getattr(job, field)
            new = data.get(field)
            if (old in (None, "") and new not in (None, "")) or (old not in (None, "") and new not in (None, "") and old != new):
                changes[field] = (old, new)
        return changes

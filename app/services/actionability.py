"""Actionability checks for strategic prioritization."""

from __future__ import annotations

from typing import Any

from app.models import Job, JobEvaluation


class ActionabilityService:
    """Evaluate whether the user has enough information to act now."""

    def score(
        self,
        job: Job,
        evaluation: JobEvaluation | None,
        has_application: bool,
    ) -> tuple[float, list[dict[str, str]], list[str], list[str]]:
        """Return raw actionability, reasons, warnings and blockers."""

        checks: list[float] = []
        reasons: list[dict[str, str]] = []
        warnings: list[str] = []
        blockers: list[str] = []

        self._check(bool(job.source_url), "enlace", "La vacante tiene enlace de fuente.", "La vacante no tiene enlace.", checks, reasons, warnings)
        self._check(job.is_active, "estado", "La vacante esta activa.", "La vacante no esta activa.", checks, reasons, blockers)
        self._check(bool(job.company.strip()), "empresa", "Empresa identificada.", "Empresa no identificada.", checks, reasons, warnings)
        self._check(len(job.description or "") >= 30, "descripcion", "Descripcion suficiente.", "Descripcion insuficiente.", checks, reasons, warnings)
        self._check(bool(job.requirements or job.responsibilities), "requisitos", "Requisitos o responsabilidades disponibles.", "Requisitos poco claros.", checks, reasons, warnings)

        if evaluation is None:
            checks.append(0.0)
            blockers.append("No existe evaluacion de compatibilidad.")
        elif evaluation.is_stale:
            checks.append(0.20)
            warnings.append("La evaluacion esta obsoleta.")
        else:
            checks.append(1.0)
            reasons.append({"factor": "evaluacion", "detail": "Evaluacion vigente disponible."})

        if job.is_duplicate:
            checks.append(0.20)
            warnings.append("Vacante marcada como duplicada o posible duplicada.")
        if job.is_suspicious:
            checks.append(0.10)
            blockers.append("Vacante marcada como sospechosa.")
        if has_application:
            checks.append(0.10)
            blockers.append("Ya existe una postulacion registrada.")

        raw = sum(checks) / len(checks) if checks else 0.50
        return max(0.0, min(raw, 1.0)), reasons, warnings, blockers

    def _check(
        self,
        condition: bool,
        factor: str,
        positive: str,
        negative: str,
        checks: list[float],
        reasons: list[dict[str, str]],
        problems: list[str],
    ) -> None:
        checks.append(1.0 if condition else 0.0)
        if condition:
            reasons.append({"factor": factor, "detail": positive})
        else:
            problems.append(negative)

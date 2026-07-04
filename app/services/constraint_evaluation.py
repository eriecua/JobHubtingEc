"""Mandatory constraint evaluation before compatibility scoring."""

from __future__ import annotations

from decimal import Decimal
from typing import Any

from sqlalchemy.orm import Session

from app.models import Job, ProfessionalProfile
from app.repositories import CareerPreferenceRepository
from app.services.compatibility_types import ConstraintResult
from app.utils.normalization import normalize_text


class ConstraintEvaluationService:
    """Evaluate active profile constraints against a job."""

    def __init__(self, session: Session) -> None:
        self.session = session

    def evaluate(self, profile: ProfessionalProfile, job: Job) -> tuple[str, list[ConstraintResult]]:
        """Return eligibility status and detailed constraint results."""

        constraints = CareerPreferenceRepository(self.session).list_constraints(profile.id)
        results = [self._evaluate_one(constraint, profile, job) for constraint in constraints if constraint.is_active]
        if any(item.result == "Incumple" for item in results):
            return "No elegible", results
        if any(item.result == "No se puede determinar" for item in results):
            return "Requiere revision", results
        return "Elegible", results

    def _evaluate_one(self, constraint, profile: ProfessionalProfile, job: Job) -> ConstraintResult:
        ctype = constraint.constraint_type
        expected = constraint.value
        if ctype == "Salario minimo obligatorio":
            return self._salary_minimum(expected, job)
        field_map = {
            "Ciudad excluida": ("city", job.city),
            "Provincia excluida": ("province", job.province),
            "Modalidad excluida": ("modality", job.modality),
            "Jornada excluida": ("schedule_type", job.schedule_type),
            "Sector excluido": ("sector", job.sector),
            "Tipo de contrato excluido": ("contract_type", job.contract_type),
        }
        if ctype in field_map:
            field_name, value = field_map[ctype]
            return self._excluded(ctype, expected, value, field_name)
        if ctype == "Disponibilidad para viajar":
            return self._availability_required(ctype, expected, job.travel_required, profile.willing_to_travel, "travel_required")
        if ctype == "Disponibilidad para reubicarse":
            return self._availability_required(ctype, expected, job.relocation_required, profile.willing_to_relocate, "relocation_required")
        return ConstraintResult(ctype, expected, None, "No aplica", "", "Tipo de restriccion no implementado.", "Baja")

    def _salary_minimum(self, expected: str, job: Job) -> ConstraintResult:
        minimum = Decimal(str(expected))
        salary = job.salary_max or job.salary_min
        if salary is None:
            return ConstraintResult(
                "Salario minimo obligatorio",
                str(minimum),
                None,
                "No se puede determinar",
                "La vacante no informa salario.",
                "No se penaliza como incumplimiento por ausencia de dato.",
                "Media",
            )
        if job.currency != "USD":
            return ConstraintResult(
                "Salario minimo obligatorio",
                str(minimum),
                f"{salary} {job.currency}",
                "No se puede determinar",
                "La moneda no es USD.",
                "No se convierten monedas extranjeras en esta fase.",
                "Media",
            )
        result = "Cumple" if salary >= minimum else "Incumple"
        return ConstraintResult(
            "Salario minimo obligatorio",
            str(minimum),
            str(salary),
            result,
            f"Salario publicado usado: {salary} USD.",
            "El salario publicado se compara contra la restriccion minima.",
            "Alta" if result == "Incumple" else "Baja",
        )

    def _excluded(self, ctype: str, expected: str, value: str | None, field_name: str) -> ConstraintResult:
        if not value:
            return ConstraintResult(ctype, expected, None, "No se puede determinar", f"Falta {field_name}.", "Dato ausente.", "Media")
        result = "Incumple" if normalize_text(expected) == normalize_text(value) else "Cumple"
        return ConstraintResult(ctype, expected, value, result, f"{field_name}: {value}.", "Comparacion exacta normalizada.", "Alta" if result == "Incumple" else "Baja")

    def _availability_required(
        self,
        ctype: str,
        expected: str,
        job_requires: bool | None,
        profile_accepts: bool | None,
        field_name: str,
    ) -> ConstraintResult:
        if job_requires is None:
            return ConstraintResult(ctype, expected, None, "No se puede determinar", f"Falta {field_name}.", "Dato ausente.", "Media")
        if job_requires is False:
            return ConstraintResult(ctype, expected, False, "No aplica", f"{field_name}: False.", "La vacante no exige esta condicion.", "Baja")
        if profile_accepts is None:
            return ConstraintResult(ctype, expected, True, "No se puede determinar", "El perfil no informa disponibilidad.", "Dato ausente en el perfil.", "Media")
        result = "Cumple" if profile_accepts else "Incumple"
        return ConstraintResult(ctype, expected, True, result, f"{field_name}: True; perfil acepta: {profile_accepts}.", "La vacante exige disponibilidad y se compara contra el perfil.", "Alta" if result == "Incumple" else "Baja")

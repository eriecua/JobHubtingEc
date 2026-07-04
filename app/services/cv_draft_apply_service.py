"""Apply reviewed CV profile candidates through existing repositories."""

from __future__ import annotations

from datetime import date
from decimal import Decimal
from typing import Any

from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.repositories import (
    CareerPreferenceRepository,
    CertificationRepository,
    EducationRepository,
    ExperienceRepository,
    ProfileRepository,
    SkillRepository,
    ToolRepository,
)
from app.services.cv_draft_validator import accepted_candidates
from app.services.cv_types import CVApplyResult, CVCandidate
from app.services.validation import ValidationError
from app.utils.normalization import normalize_text


class CVDraftApplyService:
    """Persist accepted or edited CV candidates after human confirmation."""

    def __init__(self, session: Session) -> None:
        self.session = session
        self.profile_repo = ProfileRepository(session)
        self.skill_repo = SkillRepository(session)
        self.tool_repo = ToolRepository(session)
        self.experience_repo = ExperienceRepository(session)
        self.education_repo = EducationRepository(session)
        self.certification_repo = CertificationRepository(session)
        self.career_repo = CareerPreferenceRepository(session)

    def apply(self, candidates: list[dict[str, Any] | CVCandidate]) -> CVApplyResult:
        """Persist accepted/edited candidates and return an explainable summary."""

        result = CVApplyResult()
        reviewed = accepted_candidates(candidates)
        if not reviewed:
            result.skipped.append("No hay candidatos aceptados o editados para guardar.")
            return result

        profile = self._ensure_profile(reviewed, result)
        if profile is None:
            return result

        for candidate in reviewed:
            if candidate.section == "profile":
                continue
            try:
                self._apply_candidate(profile.id, candidate, result)
            except (ValidationError, IntegrityError) as exc:
                self.session.rollback()
                result.errors.append(f"{self._candidate_label(candidate)}: {exc}")
        return result

    def _ensure_profile(self, candidates: list[CVCandidate], result: CVApplyResult):
        profile = self.profile_repo.get_main_profile()
        profile_updates = {
            candidate.field: str(candidate.value).strip()
            for candidate in candidates
            if candidate.section == "profile" and str(candidate.value).strip()
        }
        try:
            if profile is None:
                payload = {
                    "full_name": profile_updates.get("full_name", ""),
                    "professional_title": profile_updates.get("professional_title", ""),
                    "professional_summary": profile_updates.get("professional_summary", ""),
                    "country": profile_updates.get("country", "Ecuador") or "Ecuador",
                    "current_city": profile_updates.get("current_city", ""),
                    "current_province": profile_updates.get("current_province", ""),
                }
                profile = self.profile_repo.create_profile(**payload)
                result.saved.append("Perfil principal creado desde candidatos confirmados.")
            elif profile_updates:
                allowed = {
                    "full_name",
                    "professional_title",
                    "professional_summary",
                    "current_city",
                    "current_province",
                    "country",
                    "availability_status",
                    "remote_preference",
                }
                payload = {key: value for key, value in profile_updates.items() if key in allowed}
                if payload:
                    profile = self.profile_repo.update_profile(profile.id, **payload)
                    result.saved.append("Datos generales del perfil actualizados.")
        except ValidationError as exc:
            result.errors.append(f"No se pudo crear o actualizar el perfil: {exc}")
            return None
        return profile

    def _apply_candidate(self, profile_id: int, candidate: CVCandidate, result: CVApplyResult) -> None:
        if candidate.section == "experience":
            value = self._dict_value(candidate)
            self.experience_repo.create_experience(
                profile_id,
                company=value.get("company"),
                job_title=value.get("job_title"),
                sector=value.get("sector") or None,
                city=value.get("city") or None,
                start_date=value.get("start_date"),
                end_date=value.get("end_date"),
                is_current=bool(value.get("is_current")),
                description=value.get("description") or None,
                achievements=value.get("achievements") or None,
            )
            result.saved.append(f"Experiencia guardada: {value.get('job_title')} - {value.get('company')}.")
        elif candidate.section == "skill":
            skill = self.skill_repo.create_or_get_skill(str(candidate.value), "Otra")
            self.skill_repo.assign_skill(profile_id, skill.id, level="Intermedio", self_assessed=False)
            result.saved.append(f"Habilidad asignada: {skill.name}.")
        elif candidate.section == "tool":
            tool = self.tool_repo.create_or_get_tool(str(candidate.value), "Otro")
            self.tool_repo.assign_tool(profile_id, tool.id, level="Intermedio")
            result.saved.append(f"Herramienta asignada: {tool.name}.")
        elif candidate.section == "education":
            value = self._dict_value(candidate)
            self.education_repo.create(
                profile_id,
                institution=value.get("institution") or "",
                degree=value.get("degree"),
                field_of_study=value.get("field_of_study"),
                education_level=value.get("education_level") or "Universitario",
                status=value.get("status") or "En curso",
            )
            result.saved.append(f"Formacion guardada: {value.get('degree')}.")
        elif candidate.section == "certification":
            value = self._dict_value(candidate)
            self.certification_repo.create(
                profile_id,
                name=value.get("name"),
                issuing_organization=value.get("issuing_organization"),
                issue_date=value.get("issue_date"),
                expiration_date=value.get("expiration_date"),
                does_not_expire=bool(value.get("does_not_expire", True)),
            )
            result.saved.append(f"Certificacion guardada: {value.get('name')}.")
        elif candidate.section == "target_role":
            value = self._dict_value(candidate)
            role_name = value.get("role_name")
            existing = {normalize_text(role.role_name) for role in self.career_repo.list_target_roles(profile_id)}
            if normalize_text(str(role_name)) in existing:
                result.skipped.append(f"Cargo objetivo omitido por duplicado: {role_name}.")
                return
            self.career_repo.add_target_role(
                profile_id,
                role_name=role_name,
                priority=value.get("priority") or "Exploratoria",
                desired_level=value.get("desired_level") or None,
                minimum_salary=Decimal(str(value["minimum_salary"])) if value.get("minimum_salary") else None,
            )
            result.saved.append(f"Cargo objetivo guardado: {role_name}.")
        elif candidate.section == "evidence":
            value = self._dict_value(candidate)
            skill_name = str(value.get("skill_name") or "").strip()
            if not skill_name:
                raise ValidationError("Asocia la evidencia a una habilidad antes de guardarla.")
            skill = self.skill_repo.create_or_get_skill(skill_name, "Otra")
            assignment = next(
                (item for item in self.skill_repo.list_profile_skills(profile_id) if item.skill_id == skill.id),
                None,
            )
            if assignment is None:
                assignment = self.skill_repo.assign_skill(profile_id, skill.id, level="Intermedio", self_assessed=False)
            metric_value = value.get("metric_value")
            self.skill_repo.add_evidence(
                assignment.id,
                evidence_type=value.get("evidence_type") or "Logro",
                title=value.get("title"),
                description=value.get("description"),
                metric_value=Decimal(str(metric_value)) if metric_value not in {None, ""} else None,
                metric_unit=value.get("metric_unit") or None,
            )
            result.saved.append(f"Evidencia guardada para {skill.name}: {value.get('title')}.")

    def _dict_value(self, candidate: CVCandidate) -> dict[str, Any]:
        if not isinstance(candidate.value, dict):
            raise ValidationError("El candidato no tiene estructura editable valida.")
        value = dict(candidate.value)
        for key in ["start_date", "end_date", "issue_date", "expiration_date"]:
            if isinstance(value.get(key), str):
                value[key] = self._date_from_string(value[key])
        return value

    def _date_from_string(self, raw: str) -> date | None:
        value = raw.strip()
        if not value:
            return None
        try:
            year, month, day = [int(part) for part in value.split("-")]
        except ValueError as exc:
            raise ValidationError("Usa fechas en formato YYYY-MM-DD antes de guardar.") from exc
        return date(year, month, day)

    def _candidate_label(self, candidate: CVCandidate) -> str:
        return f"{candidate.section}.{candidate.field}"

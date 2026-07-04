"""Validation helpers for CV profile drafts before applying them."""

from __future__ import annotations

from datetime import date
from typing import Any

from sqlalchemy.orm import Session

from app.repositories import SkillRepository, ToolRepository
from app.services.cv_types import CVCandidate, CVDraft
from app.utils.normalization import canonical_name, normalize_text


class CVDraftValidator:
    """Apply domain checks to CV candidates before review or persistence."""

    def __init__(self, session: Session) -> None:
        self.session = session

    def validate(self, draft: CVDraft, profile_id: int | None = None) -> CVDraft:
        """Return a copy of the draft with duplicate and date warnings."""

        skill_repo = SkillRepository(self.session)
        tool_repo = ToolRepository(self.session)
        existing_skills = set()
        existing_tools = set()
        if profile_id is not None:
            existing_skills = {item.skill.normalized_name for item in skill_repo.list_profile_skills(profile_id)}
            existing_tools = {item.tool.normalized_name for item in tool_repo.list_profile_tools(profile_id)}

        seen_skills: set[str] = set()
        seen_tools: set[str] = set()
        validated: list[CVCandidate] = []
        for candidate in draft.candidates:
            updated = candidate.model_copy(deep=True)
            if updated.section == "skill":
                key = canonical_name(str(updated.value), skill_repo.catalogs.get("skill_aliases", {}))
                if key in seen_skills or key in existing_skills:
                    updated.warnings.append("Esta habilidad ya existe en el borrador o en el perfil.")
                    updated.status = "Omitido" if key in existing_skills else updated.status
                seen_skills.add(key)
            if updated.section == "tool":
                key = canonical_name(str(updated.value), tool_repo.catalogs.get("tool_aliases", {}))
                if key in seen_tools or key in existing_tools:
                    updated.warnings.append("Esta herramienta ya existe en el borrador o en el perfil.")
                    updated.status = "Omitido" if key in existing_tools else updated.status
                seen_tools.add(key)
            if updated.section == "experience":
                self._validate_experience_dates(updated)
            validated.append(updated)
        return draft.model_copy(update={"candidates": validated})

    def _validate_experience_dates(self, candidate: CVCandidate) -> None:
        value = candidate.value if isinstance(candidate.value, dict) else {}
        start_date = value.get("start_date")
        end_date = value.get("end_date")
        is_current = bool(value.get("is_current"))
        if not isinstance(start_date, date):
            candidate.warnings.append("La fecha inicial debe revisarse antes de guardar.")
            candidate.status = "Pendiente"
        if not is_current and not isinstance(end_date, date):
            candidate.warnings.append("La fecha final debe revisarse antes de guardar.")
            candidate.status = "Pendiente"
        if isinstance(start_date, date) and isinstance(end_date, date) and end_date < start_date:
            candidate.warnings.append("La fecha final no puede ser anterior a la inicial.")
            candidate.status = "Pendiente"


def accepted_candidates(candidates: list[dict[str, Any] | CVCandidate]) -> list[CVCandidate]:
    """Return reviewed candidates that should be persisted."""

    parsed = [item if isinstance(item, CVCandidate) else CVCandidate(**item) for item in candidates]
    return [candidate for candidate in parsed if candidate.status in {"Aceptado", "Editado"}]

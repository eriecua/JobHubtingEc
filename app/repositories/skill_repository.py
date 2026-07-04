"""Repository for skills, profile skills and evidences."""

from __future__ import annotations

from datetime import date
from decimal import Decimal
from typing import Any

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.config import load_profile_catalogs
from app.models import ProfileSkill, Skill, SkillEvidence
from app.services.validation import (
    ValidationError,
    require_text,
    validate_catalog_value,
    validate_non_negative,
)
from app.utils.normalization import canonical_name


class SkillRepository:
    """Operations for normalized skills and profile assignments."""

    def __init__(self, session: Session) -> None:
        self.session = session
        self.catalogs = load_profile_catalogs()

    def create_or_get_skill(
        self,
        name: str,
        category: str = "Otra",
        description: str | None = None,
    ) -> Skill:
        """Create a skill or return an existing normalized equivalent."""

        cleaned_name = require_text(name, "Habilidad")
        category = validate_catalog_value(category, "skill_categories", "Categoria")
        normalized = canonical_name(cleaned_name, self.catalogs.get("skill_aliases", {}))
        existing = self.session.scalar(select(Skill).where(Skill.normalized_name == normalized))
        if existing:
            return existing
        skill = Skill(
            name=cleaned_name,
            normalized_name=normalized,
            category=category,
            description=(description or "").strip() or None,
        )
        self.session.add(skill)
        self.session.commit()
        self.session.refresh(skill)
        return skill

    def list_skills(self) -> list[Skill]:
        """List active skills."""

        return list(self.session.scalars(select(Skill).order_by(Skill.name)))

    def assign_skill(self, profile_id: int, skill_id: int, **data: Any) -> ProfileSkill:
        """Assign a skill to a profile without duplicating it."""

        existing = self.session.scalar(
            select(ProfileSkill).where(
                ProfileSkill.profile_id == profile_id,
                ProfileSkill.skill_id == skill_id,
            )
        )
        if existing:
            raise ValidationError("La habilidad ya esta asignada a este perfil.")
        cleaned = self._clean_profile_skill_data(data)
        assignment = ProfileSkill(profile_id=profile_id, skill_id=skill_id, **cleaned)
        self.session.add(assignment)
        self.session.commit()
        self.session.refresh(assignment)
        return assignment

    def update_level(self, profile_skill_id: int, **data: Any) -> ProfileSkill:
        """Update level and metadata for an assigned skill."""

        assignment = self.session.get(ProfileSkill, profile_skill_id)
        if assignment is None:
            raise ValidationError("No se encontro la habilidad asignada.")
        cleaned = self._clean_profile_skill_data(data, partial=True)
        for key, value in cleaned.items():
            setattr(assignment, key, value)
        self.session.commit()
        self.session.refresh(assignment)
        return assignment

    def delete_assignment(self, profile_skill_id: int, confirmed: bool = False) -> None:
        """Delete a profile skill assignment after confirmation."""

        if not confirmed:
            raise ValidationError("Confirma la eliminacion antes de continuar.")
        assignment = self.session.get(ProfileSkill, profile_skill_id)
        if assignment:
            self.session.delete(assignment)
            self.session.commit()

    def list_profile_skills(self, profile_id: int) -> list[ProfileSkill]:
        """List assigned skills for a profile."""

        return list(
            self.session.scalars(
                select(ProfileSkill)
                .where(ProfileSkill.profile_id == profile_id)
                .join(ProfileSkill.skill)
                .order_by(Skill.name)
            )
        )

    def search_duplicates(self, name: str) -> list[Skill]:
        """Find skills matching the same normalized key."""

        normalized = canonical_name(name, self.catalogs.get("skill_aliases", {}))
        return list(self.session.scalars(select(Skill).where(Skill.normalized_name == normalized)))

    def add_evidence(self, profile_skill_id: int, **data: Any) -> SkillEvidence:
        """Add evidence to an assigned skill."""

        if self.session.get(ProfileSkill, profile_skill_id) is None:
            raise ValidationError("No se encontro la habilidad asignada.")
        evidence_type = validate_catalog_value(data.get("evidence_type"), "evidence_types", "Tipo")
        title = require_text(data.get("title"), "Titulo")
        description = require_text(data.get("description"), "Descripcion")
        metric_value = data.get("metric_value")
        if metric_value is not None:
            validate_non_negative(metric_value, "Valor de metrica")
        evidence = SkillEvidence(
            profile_skill_id=profile_skill_id,
            evidence_type=evidence_type,
            title=title,
            description=description,
            metric_value=metric_value,
            metric_unit=(data.get("metric_unit") or "").strip() or None,
            source_type=(data.get("source_type") or "").strip() or None,
            source_reference=(data.get("source_reference") or "").strip() or None,
        )
        self.session.add(evidence)
        self.session.commit()
        self.session.refresh(evidence)
        return evidence

    def list_evidences(self, profile_skill_id: int | None = None) -> list[SkillEvidence]:
        """List skill evidences, optionally filtered by assigned skill."""

        statement = select(SkillEvidence).order_by(SkillEvidence.created_at.desc())
        if profile_skill_id is not None:
            statement = statement.where(SkillEvidence.profile_skill_id == profile_skill_id)
        return list(self.session.scalars(statement))

    def count_skills_with_evidence(self, profile_id: int) -> int:
        """Count assigned skills that have at least one evidence item."""

        return self.session.scalar(
            select(func.count(func.distinct(ProfileSkill.id)))
            .join(SkillEvidence)
            .where(ProfileSkill.profile_id == profile_id)
        ) or 0

    def _clean_profile_skill_data(self, data: dict[str, Any], partial: bool = False) -> dict[str, Any]:
        fields = dict(data)
        if not partial or "level" in fields:
            fields["level"] = validate_catalog_value(fields.get("level"), "skill_levels", "Nivel")
        if fields.get("interest_level"):
            fields["interest_level"] = validate_catalog_value(
                fields.get("interest_level"),
                "interest_levels",
                "Interes",
            )
        if fields.get("years_experience") is not None:
            validate_non_negative(fields["years_experience"], "Anios de experiencia")
        if fields.get("last_used_year") is not None and int(fields["last_used_year"]) > date.today().year:
            raise ValidationError("El anio de ultimo uso no puede ser futuro.")
        return fields

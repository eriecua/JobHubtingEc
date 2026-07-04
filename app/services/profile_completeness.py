"""Explainable profile completeness service."""

from __future__ import annotations

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.config import load_profile_completeness_weights
from app.models import (
    Certification,
    EducationRecord,
    GrowthGoal,
    JobConstraint,
    JobPreference,
    ProfessionalProfile,
    ProfileSkill,
    ProfileTool,
    SkillEvidence,
    TargetRole,
    WorkExperience,
)
from app.schemas import ProfileCompletenessResult


class ProfileCompletenessService:
    """Calculate profile completeness from persisted structured data."""

    def __init__(self, session: Session) -> None:
        self.session = session
        self.weights = load_profile_completeness_weights()

    def calculate(self, profile: ProfessionalProfile | None) -> ProfileCompletenessResult:
        """Return an explainable completeness score."""

        if profile is None:
            return ProfileCompletenessResult(
                total_percentage=0,
                missing_components=list(self.weights.model_dump().keys()),
                recommendations=["Crea tu perfil profesional principal."],
            )

        checks = {
            "basic_professional_data": self._has_basic_data(profile),
            "professional_summary": bool(profile.professional_summary.strip()),
            "work_experience": self._count(WorkExperience, profile.id) >= 1,
            "skills": self._count(ProfileSkill, profile.id) >= 5,
            "skills_with_evidence": self._skills_with_evidence(profile.id) >= 3,
            "tools": self._count(ProfileTool, profile.id) >= 1,
            "education": self._count(EducationRecord, profile.id) >= 1,
            "certifications": self._count(Certification, profile.id) >= 1,
            "target_roles": self._count(TargetRole, profile.id) >= 1,
            "preferences_and_constraints": self._has_preferences_or_constraints(profile.id),
        }
        weights = self.weights.model_dump()
        component_scores = {key: weights[key] if value else 0 for key, value in checks.items()}
        total = sum(component_scores.values())
        completed = [key for key, value in checks.items() if value]
        missing = [key for key, value in checks.items() if not value]

        return ProfileCompletenessResult(
            total_percentage=total,
            completed_components=completed,
            missing_components=missing,
            recommendations=self._recommendations(missing, profile.id),
            component_scores=component_scores,
        )

    def _count(self, model: type, profile_id: int) -> int:
        return self.session.scalar(select(func.count(model.id)).where(model.profile_id == profile_id)) or 0

    def _skills_with_evidence(self, profile_id: int) -> int:
        return self.session.scalar(
            select(func.count(func.distinct(ProfileSkill.id)))
            .join(SkillEvidence)
            .where(ProfileSkill.profile_id == profile_id)
        ) or 0

    def _has_preferences_or_constraints(self, profile_id: int) -> bool:
        preferences = self.session.scalar(select(func.count(JobPreference.id)).where(JobPreference.profile_id == profile_id)) or 0
        constraints = self.session.scalar(select(func.count(JobConstraint.id)).where(JobConstraint.profile_id == profile_id)) or 0
        return preferences > 0 or constraints > 0

    def _has_basic_data(self, profile: ProfessionalProfile) -> bool:
        return all(
            [
                profile.full_name.strip(),
                profile.professional_title.strip(),
                profile.current_city.strip(),
                profile.country.strip(),
            ]
        )

    def _recommendations(self, missing: list[str], profile_id: int) -> list[str]:
        messages = {
            "basic_professional_data": "Completa nombre, titulo profesional, ciudad y pais.",
            "professional_summary": "Anade un resumen profesional breve y verificable.",
            "work_experience": "Registra al menos una experiencia laboral.",
            "skills": "Registra al menos cinco habilidades relevantes.",
            "skills_with_evidence": "Anade evidencia a tres habilidades principales.",
            "tools": "Registra herramientas o software que realmente uses.",
            "education": "Registra tu formacion academica.",
            "certifications": "Registra certificaciones relevantes si las tienes.",
            "target_roles": "Define al menos un cargo objetivo.",
            "preferences_and_constraints": "Registra preferencias de ubicacion, modalidad o restricciones obligatorias.",
        }
        recommendations = [messages[key] for key in missing if key in messages]
        if "skills_with_evidence" in missing and self._count(ProfileSkill, profile_id) > 0:
            recommendations.append("Anade un logro cuantificable o responsabilidad verificable a tus habilidades clave.")
        return recommendations

"""Strength, gap and growth opportunity identification."""

from __future__ import annotations

from typing import Any

from sqlalchemy.orm import Session

from app.models import JobRequirement, ProfessionalProfile
from app.repositories import CertificationRepository, EducationRepository, SkillRepository, ToolRepository
from app.utils.normalization import normalize_text


class StrengthGapService:
    """Identify backed strengths, gaps and growth opportunities."""

    def __init__(self, session: Session) -> None:
        self.session = session
        self._skills: dict[int, list[Any]] = {}
        self._tools: dict[int, list[Any]] = {}
        self._educations: dict[int, list[Any]] = {}
        self._certifications: dict[int, list[Any]] = {}

    def analyze(
        self,
        profile: ProfessionalProfile,
        requirements: list[JobRequirement],
        components: list[Any],
    ) -> tuple[list[dict[str, Any]], list[dict[str, Any]], list[dict[str, Any]]]:
        """Return strengths, gaps and growth opportunities."""

        skills = self._skills_for(profile.id)
        tools = self._tools_for(profile.id)
        skill_names = {item.skill.normalized_name: item for item in skills}
        tool_names = {item.tool.normalized_name: item for item in tools}
        strengths: list[dict[str, Any]] = []
        gaps: list[dict[str, Any]] = []
        opportunities: list[dict[str, Any]] = []
        for req in requirements:
            if req.requirement_type not in {"Habilidad", "Herramienta", "Formacion", "Certificacion", "Idioma"} or not req.is_active:
                continue
            evidence = self._evidence_for_requirement(profile, req, skill_names, tool_names)
            if evidence:
                strengths.append(
                    {
                        "title": f"{req.raw_text} cubierta",
                        "explanation": "El perfil contiene este requisito.",
                        "profile_evidence": evidence,
                        "requirement": req.raw_text,
                        "relevance": "Alta" if req.importance == "Obligatorio" else "Media",
                    }
                )
            else:
                severity = "Critica" if req.importance == "Obligatorio" else "Moderada"
                evidence_status = (
                    "Ausente en registros del perfil"
                    if req.is_confirmed_by_user or req.extraction_method == "Manual"
                    else "No evidenciada en registros del perfil"
                )
                gap = {
                    "requirement": req.raw_text,
                    "importance": req.importance,
                    "severity": severity,
                    "available_evidence": evidence_status,
                    "difference": f"No existe {req.requirement_type.lower()} equivalente registrado.",
                    "score_impact": "Reduce la dimension de habilidades.",
                    "possible_action": f"Revisar si {req.raw_text} existe con otro nombre o desarrollarla.",
                }
                gaps.append(gap)
                if req.importance != "Obligatorio":
                    opportunities.append(
                        {
                            "title": f"Desarrollar {req.raw_text}",
                            "reason": "Aparece en la vacante y no esta suficientemente cubierta.",
                            "related_requirement": req.raw_text,
                        }
                    )
        for component in components:
            if component.component_name in {"target_role", "company_sector", "salary", "location_modality"} and component.raw_score >= 0.80:
                strengths.append(
                    {
                        "title": component.component_name,
                        "explanation": component.explanation,
                        "profile_evidence": component.evidence,
                        "requirement": f"Dimension {component.component_name}",
                        "relevance": "Media",
                    }
                )
            if component.raw_score < 0.40 and component.component_name not in {"skills"}:
                gaps.append(
                    {
                        "requirement": component.component_name,
                        "importance": "Informativo",
                        "severity": "Importante" if component.status == "Incumplido" else "No confirmada",
                        "available_evidence": component.evidence,
                        "difference": "; ".join(component.missing_data) or component.explanation,
                        "score_impact": f"{component.awarded_points}/{component.weight} puntos.",
                        "possible_action": "Completar informacion o revisar la vacante.",
                    }
                )
        return strengths[:8], gaps[:8], opportunities[:5]

    def _evidence_for_requirement(
        self,
        profile: ProfessionalProfile,
        req: JobRequirement,
        skill_names: dict[str, Any],
        tool_names: dict[str, Any],
    ) -> dict[str, Any] | None:
        value = normalize_text(req.normalized_value or req.raw_text)
        if req.requirement_type in {"Habilidad", "Idioma"}:
            assignment = skill_names.get(value)
            if assignment:
                return {
                    "item": assignment.skill.name,
                    "level": assignment.level,
                    "evidence_count": len(getattr(assignment, "evidences", [])),
                }
        if req.requirement_type == "Herramienta":
            assignment = tool_names.get(value)
            if assignment:
                return {"item": assignment.tool.name, "level": assignment.level}
        if req.requirement_type == "Formacion":
            profile_text = normalize_text(" ".join([profile.professional_title or "", profile.professional_summary or ""]))
            if value and value in profile_text:
                return {"item": profile.professional_title, "source": "Perfil principal"}
            for education in self._educations_for(profile.id):
                text = normalize_text(" ".join([education.degree, education.field_of_study, education.education_level, education.status]))
                if value and value in text:
                    return {
                        "item": f"{education.degree} - {education.field_of_study}",
                        "status": education.status,
                    }
        if req.requirement_type == "Certificacion":
            for certification in self._certifications_for(profile.id):
                text = normalize_text(" ".join([certification.name, certification.issuing_organization, certification.notes or ""]))
                if value and (value in text or text in value):
                    return {"item": certification.name, "issuer": certification.issuing_organization}
        return None

    def _skills_for(self, profile_id: int) -> list[Any]:
        if profile_id not in self._skills:
            self._skills[profile_id] = SkillRepository(self.session).list_profile_skills(profile_id)
        return self._skills[profile_id]

    def _tools_for(self, profile_id: int) -> list[Any]:
        if profile_id not in self._tools:
            self._tools[profile_id] = ToolRepository(self.session).list_profile_tools(profile_id)
        return self._tools[profile_id]

    def _educations_for(self, profile_id: int) -> list[Any]:
        if profile_id not in self._educations:
            self._educations[profile_id] = EducationRepository(self.session).list_records(profile_id)
        return self._educations[profile_id]

    def _certifications_for(self, profile_id: int) -> list[Any]:
        if profile_id not in self._certifications:
            self._certifications[profile_id] = CertificationRepository(self.session).list_records(profile_id)
        return self._certifications[profile_id]

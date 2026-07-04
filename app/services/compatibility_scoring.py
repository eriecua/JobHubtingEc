"""Deterministic compatibility scoring service."""

from __future__ import annotations

from datetime import date
from decimal import Decimal
from typing import Any

from sqlalchemy.orm import Session

from app.config import load_compatibility_config
from app.models import Job, JobRequirement, ProfessionalProfile
from app.repositories import (
    CareerPreferenceRepository,
    CertificationRepository,
    EducationRepository,
    ExperienceRepository,
    SkillRepository,
    ToolRepository,
)
from app.services.compatibility_types import ComponentScore, ScoreBundle
from app.utils.normalization import normalize_text


class CompatibilityScoringService:
    """Calculate explainable compatibility components and totals."""

    def __init__(self, session: Session, config: dict[str, Any] | None = None) -> None:
        self.session = session
        self.config = config or load_compatibility_config()
        self.weights = self.config["weights"]
        self._profile_skills: dict[int, list[Any]] = {}
        self._profile_tools: dict[int, list[Any]] = {}
        self._preferences: dict[int, Any] = {}
        self._target_roles: dict[int, list[Any]] = {}
        self._target_sectors: dict[int, list[Any]] = {}
        self._growth_goals: dict[int, list[Any]] = {}
        self._experiences: dict[int, list[Any]] = {}
        self._educations: dict[int, list[Any]] = {}
        self._certifications: dict[int, list[Any]] = {}

    def score(self, profile: ProfessionalProfile, job: Job, requirements: list[JobRequirement]) -> ScoreBundle:
        """Score one job/profile pair."""

        components = [
            self._skills(profile, requirements),
            self._experience(profile, job, requirements),
            self._target_role(profile, job),
            self._growth(profile, job, requirements),
            self._salary(profile, job),
            self._location_modality(profile, job),
            self._company_sector(profile, job),
            self._recency(job),
        ]
        total = round(sum(item.awarded_points for item in components), 2)
        confidence = round(sum(item.confidence * item.weight for item in components) / 100 * 100, 2)
        coverage = round(sum((1.0 if not item.missing_data else max(0.25, item.confidence)) * item.weight for item in components) / 100 * 100, 2)
        missing = [
            {"dimension": item.component_name, "missing": value}
            for item in components
            for value in item.missing_data
        ]
        return ScoreBundle(total, confidence, coverage, components, missing)

    def _skills(self, profile: ProfessionalProfile, requirements: list[JobRequirement]) -> ComponentScore:
        weight = self.weights["skills"]
        skill_requirements = [
            req
            for req in requirements
            if req.requirement_type in {"Habilidad", "Herramienta", "Formacion", "Certificacion", "Idioma"} and req.is_active
        ]
        if not skill_requirements:
            policy = self.config["missing_data_policy"]["skills"]
            return self._component("skills", weight, policy["neutral_score"], policy["confidence"], ["No se detectaron requisitos de habilidades."], [], "No evaluable", "No se detectaron habilidades requeridas; se usa valor neutral.")

        profile_skills = self._skills_for(profile.id)
        profile_tools = self._tools_for(profile.id)
        skill_by_id = {item.skill_id: item for item in profile_skills}
        tool_by_id = {item.tool_id: item for item in profile_tools}
        normalized_profile = {item.skill.normalized_name: item for item in profile_skills}
        normalized_tools = {item.tool.normalized_name: item for item in profile_tools}
        required_scores: list[float] = []
        desired_scores: list[float] = []
        evidence: list[dict[str, Any]] = []
        missing: list[str] = []
        for req in skill_requirements:
            assignment: Any | None = None
            if req.requirement_type == "Habilidad":
                assignment = skill_by_id.get(req.skill_id) or normalized_profile.get(req.normalized_value or "")
                value, evidence_item = self._assignment_score(assignment, req)
            elif req.requirement_type == "Herramienta":
                assignment = tool_by_id.get(req.tool_id) or normalized_tools.get(req.normalized_value or "")
                value, evidence_item = self._assignment_score(assignment, req)
            elif req.requirement_type == "Formacion":
                value, evidence_item = self._education_score(profile, req)
            elif req.requirement_type == "Certificacion":
                value, evidence_item = self._certification_score(profile.id, req)
            else:
                assignment = normalized_profile.get(req.normalized_value or "")
                value, evidence_item = self._assignment_score(assignment, req)
            bucket = required_scores if req.importance == "Obligatorio" else desired_scores
            bucket.append(value)
            if evidence_item:
                evidence.append(evidence_item)
            else:
                missing.append(f"No evidenciada en el perfil: {req.raw_text}")
        required_part = sum(required_scores) / len(required_scores) if required_scores else 0.75
        desired_part = sum(desired_scores) / len(desired_scores) if desired_scores else 0.75
        raw = required_part * 0.70 + desired_part * 0.30
        confidence = 0.85 if evidence else 0.45
        explanation = f"Se compararon {len(skill_requirements)} requisitos de competencia, herramienta, formacion, certificacion o idioma."
        return self._component("skills", weight, raw, confidence, missing, evidence, self._status(raw), explanation)

    def _experience(self, profile: ProfessionalProfile, job: Job, requirements: list[JobRequirement]) -> ComponentScore:
        weight = self.weights["experience"]
        minimum = self._experience_minimum(job, requirements)
        total_years = float(profile.years_total_experience or 0) or self._years_from_experiences(profile.id)
        evidence = [{"profile_years": round(total_years, 2)}]
        if minimum is None:
            related = self._has_related_experience(profile.id, job)
            raw = 0.70 if related else 0.50
            return self._component("experience", weight, raw, 0.55, ["No se informo experiencia minima."], evidence, self._status(raw), "Se uso experiencia relacionada como aproximacion.")
        ratio = total_years / minimum if minimum else 1
        if ratio >= 1:
            raw = 1.0
        elif ratio >= self.config["experience_bands"]["high_min_ratio"]:
            raw = 0.85
        elif ratio >= self.config["experience_bands"]["medium_min_ratio"]:
            raw = 0.65
        elif ratio >= self.config["experience_bands"]["low_min_ratio"]:
            raw = 0.40
        else:
            raw = 0.20
        missing = [] if total_years else ["El perfil no informa anios totales de experiencia."]
        evidence.append({"minimum_required_years": minimum, "ratio": round(ratio, 2)})
        return self._component("experience", weight, raw, 0.80, missing, evidence, self._status(raw), "La experiencia total se compara con el minimo solicitado.")

    def _target_role(self, profile: ProfessionalProfile, job: Job) -> ComponentScore:
        weight = self.weights["target_role"]
        roles = [role for role in self._roles_for(profile.id) if role.is_active]
        title = normalize_text(job.normalized_title or job.title)
        if not roles or not title:
            return self._neutral("target_role", weight, "No hay cargos objetivo o cargo normalizado suficiente.")
        evidence: list[dict[str, Any]] = []
        best = 0.20
        for role in roles:
            role_key = normalize_text(role.normalized_role_name or role.role_name)
            related = self._same_family(title, role_key)
            exact = title == role_key or role_key in title or title in role_key
            if exact and role.priority == "Principal":
                score = 1.0
            elif related and role.priority == "Principal":
                score = 0.90
            elif exact and role.priority == "Secundaria":
                score = 0.85
            elif related and role.priority == "Secundaria":
                score = 0.75
            elif role.priority == "Exploratoria" and (exact or related):
                score = 0.65
            elif related:
                score = 0.50
            else:
                score = 0.20
            if score > best:
                best = score
                evidence = [{"target_role": role.role_name, "priority": role.priority}]
        return self._component("target_role", weight, best, 0.85, [], evidence, self._status(best), "El cargo se compara con cargos objetivo y familias configuradas.")

    def _growth(self, profile: ProfessionalProfile, job: Job, requirements: list[JobRequirement]) -> ComponentScore:
        weight = self.weights["growth"]
        goals = self._goals_for(profile.id)
        title = normalize_text(job.title)
        gaps = [req for req in requirements if req.requirement_type in {"Habilidad", "Herramienta"} and req.importance != "Obligatorio"]
        aligned_goal = next((goal for goal in goals if goal.target_role and normalize_text(goal.target_role) in title), None)
        if aligned_goal:
            raw = 0.90
            evidence = [{"goal": aligned_goal.title, "target_role": aligned_goal.target_role}]
            explanation = "La vacante se alinea con un objetivo de crecimiento."
        elif 1 <= len(gaps) <= 2:
            raw = 0.80
            evidence = [{"solvable_gaps": [gap.raw_text for gap in gaps[:2]]}]
            explanation = "Tiene una o dos brechas no obligatorias que pueden representar crecimiento."
        elif any(word in title for word in ["coordinador", "supervisor", "jefe"]):
            raw = 0.70
            evidence = [{"title": job.title}]
            explanation = "El cargo puede representar exposicion a liderazgo."
        else:
            raw = 0.45
            evidence = []
            explanation = "No se detecto alineacion fuerte con objetivos de crecimiento."
        return self._component("growth", weight, raw, 0.60 if evidence else 0.45, [], evidence, self._status(raw), explanation)

    def _salary(self, profile: ProfessionalProfile, job: Job) -> ComponentScore:
        weight = self.weights["salary"]
        preferences = self._preferences_for(profile.id)
        minimum = preferences.minimum_salary if preferences else None
        expected = preferences.expected_salary if preferences else None
        salary = job.salary_max or job.salary_min
        if salary is None:
            policy = self.config["missing_data_policy"]["salary"]
            return self._component("salary", weight, policy["neutral_score"], policy["confidence"], ["La vacante no informa salario."], [], "No evaluable", "Salario ausente; se usa valor neutral.")
        if job.currency != "USD" or (job.salary_period and job.salary_period not in {"Mensual", "No especificado"}):
            return self._component("salary", weight, 0.50, 0.25, ["Periodo o moneda no convertible en esta fase."], [{"salary": str(salary), "currency": job.currency, "period": job.salary_period}], "No evaluable", "No se convierten monedas extranjeras ni periodos incompatibles.")
        if expected and salary >= expected:
            raw = 1.0
        elif minimum and expected and salary >= minimum:
            span = max(Decimal("1"), expected - minimum)
            raw = 0.60 + float((salary - minimum) / span) * 0.40
        elif minimum and salary >= minimum:
            raw = 0.65
        elif minimum and salary < minimum:
            raw = 0.20
        else:
            raw = 0.70
        return self._component("salary", weight, min(raw, 1.0), 0.85, [], [{"salary": str(salary), "minimum": str(minimum), "expected": str(expected)}], self._status(raw), "El salario publicado se compara contra preferencias registradas.")

    def _location_modality(self, profile: ProfessionalProfile, job: Job) -> ComponentScore:
        weight = self.weights["location_modality"]
        preferences = self._preferences_for(profile.id)
        if preferences is None:
            return self._neutral("location_modality", weight, "No hay preferencias de ubicacion o modalidad.")
        missing: list[str] = []
        city_score = 0.45
        if job.city:
            if normalize_text(job.city) in {normalize_text(value) for value in preferences.preferred_cities}:
                city_score = 1.0
            elif job.province and normalize_text(job.province) in {normalize_text(value) for value in preferences.preferred_provinces}:
                city_score = 0.85
            elif profile.willing_to_relocate:
                city_score = 0.65
        else:
            missing.append("La vacante no informa ciudad.")
            city_score = self.config["missing_data_policy"]["location"]["neutral_score"]
        modality_score = 0.60
        if job.modality:
            modality_score = 1.0 if normalize_text(job.modality) in {normalize_text(value) for value in preferences.accepted_modalities} else 0.45
        else:
            missing.append("La vacante no informa modalidad.")
            modality_score = self.config["missing_data_policy"]["location"]["neutral_score"]
        raw = (city_score + modality_score) / 2
        confidence = 0.80 if not missing else 0.35
        return self._component("location_modality", weight, raw, confidence, missing, [{"city": job.city, "province": job.province, "modality": job.modality}], self._status(raw), "Ubicacion y modalidad se comparan contra preferencias.")

    def _company_sector(self, profile: ProfessionalProfile, job: Job) -> ComponentScore:
        weight = self.weights["company_sector"]
        sectors = self._sectors_for(profile.id)
        if not job.sector:
            policy = self.config["missing_data_policy"]["sector"]
            return self._component("company_sector", weight, policy["neutral_score"], policy["confidence"], ["La vacante no informa sector."], [], "No evaluable", "Sector ausente; se usa valor neutral.")
        normalized_job_sector = normalize_text(job.sector)
        raw = 0.50
        evidence: list[dict[str, Any]] = [{"job_sector": job.sector}]
        for sector in sectors:
            normalized_sector = normalize_text(sector.sector_name)
            if normalized_sector == normalized_job_sector:
                raw = {"Principal": 1.0, "Secundaria": 0.80, "Exploratoria": 0.65}.get(sector.priority, 0.60)
                evidence.append({"target_sector": sector.sector_name, "priority": sector.priority})
                break
        return self._component("company_sector", weight, raw, 0.75, [], evidence, self._status(raw), "El sector se compara con sectores objetivo.")

    def _recency(self, job: Job) -> ComponentScore:
        weight = self.weights["recency"]
        if job.expiration_date and job.expiration_date < date.today():
            return self._component("recency", weight, 0.0, 0.90, [], [{"expiration_date": job.expiration_date.isoformat()}], "Incumplido", "La vacante esta vencida.")
        if not job.publication_date:
            policy = self.config["missing_data_policy"]["recency"]
            return self._component("recency", weight, policy["neutral_score"], policy["confidence"], ["No se informa fecha de publicacion."], [], "No evaluable", "Fecha de publicacion ausente; se usa valor neutral.")
        age = (date.today() - job.publication_date).days
        bands = self.config["recency_days"]
        if age <= bands["fresh"]:
            raw = 1.0
        elif age <= bands["week"]:
            raw = 0.90
        elif age <= bands["two_weeks"]:
            raw = 0.75
        elif age <= bands["month"]:
            raw = 0.50
        elif age <= bands["two_months"]:
            raw = 0.25
        else:
            raw = 0.10
        return self._component("recency", weight, raw, 0.90, [], [{"age_days": age}], self._status(raw), "La antiguedad se calcula con la fecha actual del sistema.")

    def _match_assignment(self, assignment: Any | None) -> float:
        if assignment is None:
            return 0.0
        evidence_count = len(getattr(assignment, "evidences", []))
        return 1.0 if evidence_count else 0.75

    def _assignment_score(self, assignment: Any | None, requirement: JobRequirement) -> tuple[float, dict[str, Any] | None]:
        value = self._match_assignment(assignment)
        if assignment is None:
            return value, None
        profile_item = getattr(getattr(assignment, "skill", None) or getattr(assignment, "tool", None), "name", "")
        return value, {
            "requirement": requirement.raw_text,
            "profile_item": profile_item,
            "level": assignment.level,
            "evidence_count": len(getattr(assignment, "evidences", [])),
        }

    def _education_score(self, profile: ProfessionalProfile, requirement: JobRequirement) -> tuple[float, dict[str, Any] | None]:
        value = normalize_text(requirement.normalized_value or requirement.raw_text)
        profile_text = normalize_text(" ".join([profile.professional_title or "", profile.professional_summary or ""]))
        if value and value in profile_text:
            return 0.85, {"requirement": requirement.raw_text, "profile_item": profile.professional_title, "source": "Perfil principal"}
        for education in self._educations_for(profile.id):
            text = normalize_text(" ".join([education.degree, education.field_of_study, education.education_level, education.status]))
            if value and value in text:
                score = 1.0 if education.status == "Completado" else 0.80
                return score, {
                    "requirement": requirement.raw_text,
                    "profile_item": f"{education.degree} - {education.field_of_study}",
                    "status": education.status,
                }
        return 0.0, None

    def _certification_score(self, profile_id: int, requirement: JobRequirement) -> tuple[float, dict[str, Any] | None]:
        value = normalize_text(requirement.normalized_value or requirement.raw_text)
        for certification in self._certifications_for(profile_id):
            text = normalize_text(" ".join([certification.name, certification.issuing_organization, certification.notes or ""]))
            if value and (value in text or text in value):
                return 1.0, {
                    "requirement": requirement.raw_text,
                    "profile_item": certification.name,
                    "issuer": certification.issuing_organization,
                }
        return 0.0, None

    def _experience_minimum(self, job: Job, requirements: list[JobRequirement]) -> float | None:
        if job.experience_min_years is not None:
            return float(job.experience_min_years)
        for req in requirements:
            if req.requirement_type == "Experiencia" and req.normalized_value:
                try:
                    return float(req.normalized_value)
                except ValueError:
                    continue
        return None

    def _years_from_experiences(self, profile_id: int) -> float:
        intervals = []
        for item in self._experiences_for(profile_id):
            start = item.start_date
            end = item.end_date or date.today()
            intervals.append((start, end))
        if not intervals:
            return 0.0
        intervals.sort()
        merged = []
        for start, end in intervals:
            if not merged or start > merged[-1][1]:
                merged.append([start, end])
            else:
                merged[-1][1] = max(merged[-1][1], end)
        days = sum((end - start).days for start, end in merged)
        return days / 365.25

    def _has_related_experience(self, profile_id: int, job: Job) -> bool:
        title = normalize_text(job.title)
        for item in self._experiences_for(profile_id):
            text = normalize_text(" ".join([item.job_title, item.sector or "", item.description or ""]))
            if self._same_family(title, text):
                return True
        return False

    def _same_family(self, a: str, b: str) -> bool:
        for terms in self.config["job_families"].values():
            if any(term in a for term in terms) and any(term in b for term in terms):
                return True
        return False

    def _skills_for(self, profile_id: int) -> list[Any]:
        if profile_id not in self._profile_skills:
            self._profile_skills[profile_id] = SkillRepository(self.session).list_profile_skills(profile_id)
        return self._profile_skills[profile_id]

    def _tools_for(self, profile_id: int) -> list[Any]:
        if profile_id not in self._profile_tools:
            self._profile_tools[profile_id] = ToolRepository(self.session).list_profile_tools(profile_id)
        return self._profile_tools[profile_id]

    def _preferences_for(self, profile_id: int) -> Any:
        if profile_id not in self._preferences:
            self._preferences[profile_id] = CareerPreferenceRepository(self.session).get_preferences(profile_id)
        return self._preferences[profile_id]

    def _roles_for(self, profile_id: int) -> list[Any]:
        if profile_id not in self._target_roles:
            self._target_roles[profile_id] = CareerPreferenceRepository(self.session).list_target_roles(profile_id)
        return self._target_roles[profile_id]

    def _sectors_for(self, profile_id: int) -> list[Any]:
        if profile_id not in self._target_sectors:
            self._target_sectors[profile_id] = CareerPreferenceRepository(self.session).list_target_sectors(profile_id)
        return self._target_sectors[profile_id]

    def _goals_for(self, profile_id: int) -> list[Any]:
        if profile_id not in self._growth_goals:
            self._growth_goals[profile_id] = CareerPreferenceRepository(self.session).list_growth_goals(profile_id)
        return self._growth_goals[profile_id]

    def _experiences_for(self, profile_id: int) -> list[Any]:
        if profile_id not in self._experiences:
            self._experiences[profile_id] = ExperienceRepository(self.session).list_experiences(profile_id)
        return self._experiences[profile_id]

    def _educations_for(self, profile_id: int) -> list[Any]:
        if profile_id not in self._educations:
            self._educations[profile_id] = EducationRepository(self.session).list_records(profile_id)
        return self._educations[profile_id]

    def _certifications_for(self, profile_id: int) -> list[Any]:
        if profile_id not in self._certifications:
            self._certifications[profile_id] = CertificationRepository(self.session).list_records(profile_id)
        return self._certifications[profile_id]

    def _neutral(self, name: str, weight: int, explanation: str) -> ComponentScore:
        policy = self.config["missing_data_policy"].get(name, {"neutral_score": 0.50, "confidence": 0.30})
        return self._component(name, weight, policy["neutral_score"], policy["confidence"], [explanation], [], "No evaluable", explanation)

    def _component(
        self,
        name: str,
        weight: int,
        raw: float,
        confidence: float,
        missing: list[str],
        evidence: list[dict[str, Any]],
        status: str,
        explanation: str,
    ) -> ComponentScore:
        raw = max(0.0, min(float(raw), 1.0))
        confidence = max(0.0, min(float(confidence), 1.0))
        return ComponentScore(
            component_name=name,
            weight=weight,
            raw_score=round(raw, 4),
            awarded_points=round(raw * weight, 2),
            confidence=round(confidence, 4),
            status=status,
            evidence=evidence,
            missing_data=missing,
            explanation=explanation,
        )

    def _status(self, raw: float) -> str:
        if raw >= 0.90:
            return "Excelente"
        if raw >= 0.75:
            return "Alto"
        if raw >= 0.55:
            return "Medio"
        if raw >= 0.30:
            return "Bajo"
        return "Incumplido"

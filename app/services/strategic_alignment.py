"""Strategic alignment scoring for prioritization."""

from __future__ import annotations

from typing import Any

from sqlalchemy.orm import Session

from app.models import Job, JobEvaluation, ProfessionalProfile
from app.repositories import CareerPreferenceRepository
from app.utils.normalization import normalize_text


class StrategicAlignmentService:
    """Evaluate how a job fits the user's strategic search direction."""

    def __init__(self, session: Session) -> None:
        self.session = session
        self.repo = CareerPreferenceRepository(session)
        self._roles: dict[int, list[Any]] = {}
        self._sectors: dict[int, list[Any]] = {}
        self._goals: dict[int, list[Any]] = {}

    def score(self, profile: ProfessionalProfile, job: Job, evaluation: JobEvaluation | None) -> tuple[float, list[dict[str, str]], list[str]]:
        """Return raw alignment, reasons and warnings."""

        reasons: list[dict[str, str]] = []
        warnings: list[str] = []
        scores: list[float] = []
        title = normalize_text(job.normalized_title or job.title)
        sector = normalize_text(job.sector or "")

        role_score = self._role_score(profile.id, title, reasons)
        if role_score is not None:
            scores.append(role_score)
        else:
            warnings.append("No hay cargo objetivo comparable.")

        sector_score = self._sector_score(profile.id, sector, reasons)
        if sector_score is not None:
            scores.append(sector_score)

        goal_score = self._goal_score(profile.id, title, reasons)
        if goal_score is not None:
            scores.append(goal_score)

        if profile.current_city and job.city and normalize_text(profile.current_city) == normalize_text(job.city):
            scores.append(0.85)
            reasons.append({"factor": "ubicacion", "detail": "La ciudad coincide con el perfil."})

        if evaluation and evaluation.recommendation_type == "Oportunidad de crecimiento":
            scores.append(0.80)
            reasons.append({"factor": "crecimiento", "detail": "La evaluacion la marco como oportunidad de crecimiento."})

        if not scores:
            return 0.45, reasons, warnings
        return max(0.0, min(sum(scores) / len(scores), 1.0)), reasons, warnings

    def _role_score(self, profile_id: int, title: str, reasons: list[dict[str, str]]) -> float | None:
        best: float | None = None
        for role in self._target_roles(profile_id):
            if not role.is_active:
                continue
            role_text = normalize_text(role.normalized_role_name or role.role_name)
            exact_or_contains = role_text in title or title in role_text
            related = any(term in title and term in role_text for term in ["produccion", "operaciones", "procesos", "logistica", "calidad", "mejora"])
            score = 0.0
            if exact_or_contains:
                score = {"Principal": 1.0, "Secundaria": 0.85, "Exploratoria": 0.70}.get(role.priority, 0.60)
            elif related:
                score = {"Principal": 0.80, "Secundaria": 0.70, "Exploratoria": 0.60}.get(role.priority, 0.50)
            if score > (best or 0):
                best = score
                reasons.append({"factor": "cargo", "detail": f"Relacionado con {role.role_name} ({role.priority})."})
        return best

    def _sector_score(self, profile_id: int, sector: str, reasons: list[dict[str, str]]) -> float | None:
        if not sector:
            return None
        best: float | None = None
        for target in self._target_sectors(profile_id):
            if not target.is_active:
                continue
            if normalize_text(target.sector_name) == sector:
                score = {"Principal": 1.0, "Secundaria": 0.80, "Exploratoria": 0.65}.get(target.priority, 0.60)
                if score > (best or 0):
                    best = score
                    reasons.append({"factor": "sector", "detail": f"Sector objetivo {target.sector_name} ({target.priority})."})
        return best

    def _goal_score(self, profile_id: int, title: str, reasons: list[dict[str, str]]) -> float | None:
        for goal in self._growth_goals(profile_id):
            if goal.status in {"Completado", "Descartado"}:
                continue
            if goal.target_role and normalize_text(goal.target_role) in title:
                reasons.append({"factor": "objetivo", "detail": f"Alineada con objetivo: {goal.title}."})
                return {"Principal": 0.95, "Secundaria": 0.80, "Exploratoria": 0.70}.get(goal.priority, 0.75)
        return None

    def _target_roles(self, profile_id: int) -> list[Any]:
        if profile_id not in self._roles:
            self._roles[profile_id] = self.repo.list_target_roles(profile_id)
        return self._roles[profile_id]

    def _target_sectors(self, profile_id: int) -> list[Any]:
        if profile_id not in self._sectors:
            self._sectors[profile_id] = self.repo.list_target_sectors(profile_id)
        return self._sectors[profile_id]

    def _growth_goals(self, profile_id: int) -> list[Any]:
        if profile_id not in self._goals:
            self._goals[profile_id] = self.repo.list_growth_goals(profile_id)
        return self._goals[profile_id]

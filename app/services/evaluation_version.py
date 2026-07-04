"""Hashing and stale-evaluation helpers for compatibility scoring."""

from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal
import hashlib
import json
from typing import Any

from sqlalchemy.orm import Session

from app.config import load_compatibility_config
from app.models import Job, ProfessionalProfile
from app.repositories import (
    CareerPreferenceRepository,
    CertificationRepository,
    EducationRepository,
    ExperienceRepository,
    EvaluationRepository,
    SkillRepository,
    ToolRepository,
)


class EvaluationVersionService:
    """Generate reproducible hashes for profile, job and configuration state."""

    def __init__(self, session: Session, config: dict[str, Any] | None = None) -> None:
        self.session = session
        self.config = config or load_compatibility_config()

    @property
    def scoring_version(self) -> str:
        """Return the configured scoring version."""

        return str(self.config["scoring_version"])

    def configuration_hash(self, config: dict[str, Any] | None = None) -> str:
        """Hash the active scoring configuration."""

        return self._hash(config or self.config)

    def profile_hash(self, profile: ProfessionalProfile) -> str:
        """Hash the profile and dependent career data used by the evaluator."""

        skill_repo = SkillRepository(self.session)
        tool_repo = ToolRepository(self.session)
        career_repo = CareerPreferenceRepository(self.session)
        experience_repo = ExperienceRepository(self.session)
        education_repo = EducationRepository(self.session)
        certification_repo = CertificationRepository(self.session)
        data = {
            "profile": self._model(profile),
            "skills": [
                {
                    **self._model(item),
                    "skill": self._model(item.skill),
                    "evidences": [self._model(ev) for ev in item.evidences],
                }
                for item in skill_repo.list_profile_skills(profile.id)
            ],
            "tools": [
                {**self._model(item), "tool": self._model(item.tool)}
                for item in tool_repo.list_profile_tools(profile.id)
            ],
            "experiences": [self._model(item) for item in experience_repo.list_experiences(profile.id)],
            "education": [self._model(item) for item in education_repo.list_records(profile.id)],
            "certifications": [self._model(item) for item in certification_repo.list_records(profile.id)],
            "target_roles": [self._model(item) for item in career_repo.list_target_roles(profile.id)],
            "target_sectors": [self._model(item) for item in career_repo.list_target_sectors(profile.id)],
            "preferences": self._model(career_repo.get_preferences(profile.id)),
            "constraints": [self._model(item) for item in career_repo.list_constraints(profile.id)],
            "growth_goals": [self._model(item) for item in career_repo.list_growth_goals(profile.id)],
        }
        return self._hash(data)

    def job_hash(self, job: Job) -> str:
        """Hash job data and active confirmed or extracted requirements."""

        repo = EvaluationRepository(self.session)
        data = {
            "job": self._model(job),
            "requirements": [self._model(item) for item in repo.list_requirements(job.id)],
        }
        return self._hash(data)

    def mark_stale_if_needed(self, profile: ProfessionalProfile, job: Job) -> bool:
        """Mark the latest evaluation stale when any stored hash no longer matches."""

        repo = EvaluationRepository(self.session)
        latest = repo.get_latest_evaluation(job.id, profile.id)
        if latest is None or latest.is_stale:
            return False
        changed = (
            latest.scoring_version != self.scoring_version
            or latest.configuration_hash != self.configuration_hash()
            or latest.profile_snapshot_hash != self.profile_hash(profile)
            or latest.job_snapshot_hash != self.job_hash(job)
        )
        if changed:
            repo.mark_stale(latest.id)
        return changed

    def _hash(self, data: Any) -> str:
        return hashlib.sha256(
            json.dumps(data, sort_keys=True, ensure_ascii=False, default=self._json_default).encode("utf-8")
        ).hexdigest()

    def _model(self, item: Any) -> dict[str, Any] | None:
        if item is None:
            return None
        return {column.name: getattr(item, column.name) for column in item.__table__.columns}

    def _json_default(self, value: Any) -> Any:
        if isinstance(value, (datetime, date)):
            return value.isoformat()
        if isinstance(value, Decimal):
            return str(value)
        return str(value)

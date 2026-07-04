"""Repository for compatibility evaluation persistence."""

from __future__ import annotations

from decimal import Decimal
from typing import Any

from sqlalchemy import func, select
from sqlalchemy.orm import Session, selectinload

from app.models import EvaluationComponent, EvaluationRun, JobEvaluation, JobRequirement
from app.models.database_models import utc_now
from app.services.validation import ValidationError


class EvaluationRepository:
    """Persist requirements, runs, evaluations and components."""

    def __init__(self, session: Session) -> None:
        self.session = session

    def create_run(
        self,
        profile_id: int,
        scoring_version: str,
        configuration_hash: str,
        profile_snapshot_hash: str,
        jobs_requested: int,
    ) -> EvaluationRun:
        """Create an evaluation run."""

        run = EvaluationRun(
            profile_id=profile_id,
            scoring_version=scoring_version,
            configuration_hash=configuration_hash,
            profile_snapshot_hash=profile_snapshot_hash,
            jobs_requested=jobs_requested,
            status="Procesando",
        )
        self.session.add(run)
        self.session.flush()
        return run

    def finish_run(self, run_id: int, jobs_evaluated: int, jobs_failed: int, errors: list[str]) -> EvaluationRun:
        """Mark a run as completed or completed with errors."""

        run = self.get_run(run_id)
        run.jobs_evaluated = jobs_evaluated
        run.jobs_failed = jobs_failed
        run.error_summary = "; ".join(errors) if errors else None
        run.status = "Completado con errores" if errors else "Completado"
        run.completed_at = utc_now()
        self.session.commit()
        self.session.refresh(run)
        return run

    def fail_run(self, run_id: int, error: str) -> EvaluationRun:
        """Mark a run as failed."""

        run = self.get_run(run_id)
        run.jobs_failed = run.jobs_requested
        run.error_summary = error
        run.status = "Fallido"
        run.completed_at = utc_now()
        self.session.commit()
        self.session.refresh(run)
        return run

    def get_run(self, run_id: int) -> EvaluationRun:
        """Return a run or raise."""

        run = self.session.get(EvaluationRun, run_id)
        if run is None:
            raise ValidationError("No se encontro la corrida de evaluacion.")
        return run

    def save_evaluation(self, data: dict[str, Any], components: list[dict[str, Any]]) -> JobEvaluation:
        """Persist one complete evaluation and its components."""

        evaluation = JobEvaluation(**self._decimalized(data))
        self.session.add(evaluation)
        self.session.flush()
        for component in components:
            self.session.add(
                EvaluationComponent(
                    evaluation_id=evaluation.id,
                    **self._decimalized(component),
                )
            )
        self.session.flush()
        return evaluation

    def list_results(
        self,
        filters: dict[str, Any] | None = None,
        limit: int = 200,
    ) -> list[JobEvaluation]:
        """List evaluations with simple filters."""

        filters = filters or {}
        statement = (
            select(JobEvaluation)
            .options(selectinload(JobEvaluation.job), selectinload(JobEvaluation.components))
            .order_by(JobEvaluation.created_at.desc())
        )
        if filters.get("eligibility_status"):
            statement = statement.where(JobEvaluation.eligibility_status == filters["eligibility_status"])
        if filters.get("recommendation_type"):
            statement = statement.where(JobEvaluation.recommendation_type == filters["recommendation_type"])
        if filters.get("is_stale") is not None:
            statement = statement.where(JobEvaluation.is_stale.is_(bool(filters["is_stale"])))
        if filters.get("min_score") is not None:
            statement = statement.where(JobEvaluation.total_score >= filters["min_score"])
        if filters.get("max_score") is not None:
            statement = statement.where(JobEvaluation.total_score <= filters["max_score"])
        if filters.get("min_confidence") is not None:
            statement = statement.where(JobEvaluation.confidence_score >= filters["min_confidence"])
        return list(self.session.scalars(statement.limit(limit)))

    def get_latest_evaluation(self, job_id: int, profile_id: int) -> JobEvaluation | None:
        """Return the latest evaluation for a job/profile pair."""

        statement = (
            select(JobEvaluation)
            .options(selectinload(JobEvaluation.components), selectinload(JobEvaluation.job))
            .where(JobEvaluation.job_id == job_id, JobEvaluation.profile_id == profile_id)
            .order_by(JobEvaluation.created_at.desc())
        )
        return self.session.scalar(statement)

    def get_evaluation(self, evaluation_id: int) -> JobEvaluation:
        """Return an evaluation with components or raise."""

        evaluation = self.session.scalar(
            select(JobEvaluation)
            .options(selectinload(JobEvaluation.components), selectinload(JobEvaluation.job))
            .where(JobEvaluation.id == evaluation_id)
        )
        if evaluation is None:
            raise ValidationError("No se encontro la evaluacion.")
        return evaluation

    def list_history(self, job_id: int, profile_id: int) -> list[JobEvaluation]:
        """List evaluation history for a job/profile pair."""

        statement = (
            select(JobEvaluation)
            .where(JobEvaluation.job_id == job_id, JobEvaluation.profile_id == profile_id)
            .order_by(JobEvaluation.created_at.desc())
        )
        return list(self.session.scalars(statement))

    def mark_stale(self, evaluation_id: int) -> None:
        """Mark one evaluation as stale."""

        evaluation = self.session.get(JobEvaluation, evaluation_id)
        if evaluation:
            evaluation.is_stale = True
            self.session.commit()

    def mark_stale_by_profile(self, profile_id: int) -> int:
        """Mark active evaluations for a profile as stale."""

        evaluations = list(
            self.session.scalars(
                select(JobEvaluation).where(
                    JobEvaluation.profile_id == profile_id,
                    JobEvaluation.is_stale.is_(False),
                )
            )
        )
        for evaluation in evaluations:
            evaluation.is_stale = True
        self.session.commit()
        return len(evaluations)

    def summary(self) -> dict[str, Any]:
        """Return high-level compatibility counters."""

        total = self.session.scalar(select(func.count(JobEvaluation.id))) or 0
        stale = self.session.scalar(select(func.count(JobEvaluation.id)).where(JobEvaluation.is_stale.is_(True))) or 0
        avg_score = self.session.scalar(select(func.avg(JobEvaluation.total_score))) or 0
        by_eligibility = self.session.execute(
            select(JobEvaluation.eligibility_status, func.count(JobEvaluation.id)).group_by(JobEvaluation.eligibility_status)
        ).all()
        by_recommendation = self.session.execute(
            select(JobEvaluation.recommendation_type, func.count(JobEvaluation.id)).group_by(JobEvaluation.recommendation_type)
        ).all()
        return {
            "total": total,
            "stale": stale,
            "average_score": float(avg_score or 0),
            "by_eligibility": dict(by_eligibility),
            "by_recommendation": dict(by_recommendation),
        }

    def list_requirements(self, job_id: int, active_only: bool = True) -> list[JobRequirement]:
        """List job requirements."""

        statement = select(JobRequirement).where(JobRequirement.job_id == job_id)
        if active_only:
            statement = statement.where(JobRequirement.is_active.is_(True))
        return list(self.session.scalars(statement.order_by(JobRequirement.requirement_type, JobRequirement.raw_text)))

    def add_requirement(self, **data: Any) -> JobRequirement:
        """Create a manual requirement."""

        requirement = JobRequirement(**data)
        self.session.add(requirement)
        self.session.commit()
        self.session.refresh(requirement)
        return requirement

    def update_requirement(self, requirement_id: int, **data: Any) -> JobRequirement:
        """Update a requirement after manual review."""

        requirement = self.session.get(JobRequirement, requirement_id)
        if requirement is None:
            raise ValidationError("No se encontro el requisito.")
        for key, value in data.items():
            if hasattr(requirement, key):
                setattr(requirement, key, value)
        self.session.commit()
        self.session.refresh(requirement)
        return requirement

    def upsert_extracted_requirements(
        self,
        job_id: int,
        extracted: list[dict[str, Any]],
        commit: bool = True,
    ) -> list[JobRequirement]:
        """Store extracted requirements without overriding confirmed manual corrections."""

        existing = self.list_requirements(job_id, active_only=True)
        protected_keys = {
            self._requirement_key(item)
            for item in existing
            if item.is_confirmed_by_user or item.extraction_method == "Manual"
        }
        all_keys = {self._requirement_key(item) for item in existing}
        saved: list[JobRequirement] = []
        for data in extracted:
            key = (
                data["requirement_type"],
                data.get("normalized_value") or data["raw_text"].strip().lower(),
            )
            if key in protected_keys or key in all_keys:
                continue
            requirement = JobRequirement(job_id=job_id, **data)
            self.session.add(requirement)
            saved.append(requirement)
            all_keys.add(key)
        if commit:
            self.session.commit()
        else:
            self.session.flush()
        return self.list_requirements(job_id, active_only=True)

    def _requirement_key(self, requirement: JobRequirement) -> tuple[str, str]:
        return (
            requirement.requirement_type,
            requirement.normalized_value or requirement.raw_text.strip().lower(),
        )

    def _decimalized(self, data: dict[str, Any]) -> dict[str, Any]:
        cleaned = dict(data)
        for key in ["total_score", "confidence_score", "data_coverage_score", "raw_score", "awarded_points", "confidence"]:
            if key in cleaned:
                cleaned[key] = Decimal(str(cleaned[key]))
        return cleaned

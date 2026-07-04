"""Orchestrates individual and batch compatibility evaluations."""

from __future__ import annotations

from dataclasses import asdict
from typing import Any

from sqlalchemy.orm import Session

from app.config import load_compatibility_config
from app.models import Job, ProfessionalProfile
from app.models.database_models import utc_now
from app.repositories import EvaluationRepository, JobRepository, ProfileRepository
from app.services.compatibility_scoring import CompatibilityScoringService
from app.services.constraint_evaluation import ConstraintEvaluationService
from app.services.evaluation_version import EvaluationVersionService
from app.services.explanation import ExplanationService
from app.services.recommendation_classification import RecommendationClassificationService
from app.services.requirement_extraction import RequirementExtractionService
from app.services.strength_gap import StrengthGapService
from app.services.validation import ValidationError


class EvaluationEngineService:
    """Run deterministic compatibility evaluations and persist results."""

    def __init__(self, session: Session, config: dict[str, Any] | None = None) -> None:
        self.session = session
        self.config = config or load_compatibility_config()
        self.repo = EvaluationRepository(session)
        self.version = EvaluationVersionService(session, self.config)
        self.extractor = RequirementExtractionService(session, self.config)
        self.constraint_service = ConstraintEvaluationService(session)
        self.scoring_service = CompatibilityScoringService(session, self.config)
        self.strength_gap_service = StrengthGapService(session)
        self.classifier = RecommendationClassificationService(self.config)

    def evaluate_job(self, job_id: int, profile_id: int | None = None) -> dict[str, Any]:
        """Evaluate a single job and return a summary."""

        profile = self._profile(profile_id)
        run = self.repo.create_run(
            profile.id,
            self.version.scoring_version,
            self.version.configuration_hash(),
            self.version.profile_hash(profile),
            jobs_requested=1,
        )
        self.session.commit()
        try:
            configuration_hash = self.version.configuration_hash()
            profile_hash = self.version.profile_hash(profile)
            evaluation = self._evaluate_one(run.id, profile, self._job(job_id), profile_hash, configuration_hash)
            self.repo.finish_run(run.id, 1, 0, [])
            return {"run_id": run.id, "evaluation_id": evaluation.id, "total_score": float(evaluation.total_score)}
        except Exception as exc:
            self.session.rollback()
            self.repo.fail_run(run.id, str(exc))
            raise

    def evaluate_jobs(self, job_ids: list[int], profile_id: int | None = None) -> dict[str, Any]:
        """Evaluate several jobs, continuing after individual failures."""

        if not job_ids:
            raise ValidationError("Selecciona al menos una vacante para evaluar.")
        profile = self._profile(profile_id)
        configuration_hash = self.version.configuration_hash()
        profile_hash = self.version.profile_hash(profile)
        run = self.repo.create_run(
            profile.id,
            self.version.scoring_version,
            configuration_hash,
            profile_hash,
            jobs_requested=len(job_ids),
        )
        self.session.commit()
        evaluated = 0
        errors: list[str] = []
        for job_id in job_ids:
            try:
                with self.session.begin_nested():
                    self._evaluate_one(run.id, profile, self._job(job_id), profile_hash, configuration_hash, commit_requirements=False)
                evaluated += 1
                if evaluated % 100 == 0:
                    self.session.commit()
            except Exception as exc:
                errors.append(f"Vacante {job_id}: {exc}")
        self.repo.finish_run(run.id, evaluated, len(errors), errors)
        return {"run_id": run.id, "jobs_evaluated": evaluated, "jobs_failed": len(errors), "errors": errors}

    def evaluate_all_active(self, limit: int = 1000, profile_id: int | None = None) -> dict[str, Any]:
        """Evaluate active jobs up to a local safety limit."""

        jobs = JobRepository(self.session).list_jobs({"is_active": True}, limit=limit)
        return self.evaluate_jobs([job.id for job in jobs], profile_id)

    def mark_stale_for_current_state(self, job_id: int, profile_id: int | None = None) -> bool:
        """Check and mark the latest evaluation stale if hashes changed."""

        profile = self._profile(profile_id)
        job = self._job(job_id)
        self.extractor.extract_for_job(job, persist=True)
        return self.version.mark_stale_if_needed(profile, job)

    def _evaluate_one(
        self,
        run_id: int,
        profile: ProfessionalProfile,
        job: Job,
        profile_hash: str | None = None,
        configuration_hash: str | None = None,
        commit_requirements: bool = True,
    ):
        self.version.mark_stale_if_needed(profile, job)
        self.extractor.extract_for_job(job, persist=True, commit=commit_requirements)
        requirements = self.repo.list_requirements(job.id)
        eligibility_status, constraints = self.constraint_service.evaluate(profile, job)
        scoring = self.scoring_service.score(profile, job, requirements)
        strengths, gaps, growth = self.strength_gap_service.analyze(profile, requirements, scoring.components)
        recommendation = self.classifier.classify(
            scoring.total_score,
            scoring.confidence_score,
            eligibility_status,
            scoring.components,
            gaps,
        )
        explanation = ExplanationService().build(
            scoring.total_score,
            scoring.confidence_score,
            scoring.data_coverage_score,
            eligibility_status,
            recommendation,
            strengths,
            gaps,
            scoring.missing_information,
        )
        profile_hash = profile_hash or self.version.profile_hash(profile)
        job_hash = self.version.job_hash(job)
        configuration_hash = configuration_hash or self.version.configuration_hash()
        evaluation = self.repo.save_evaluation(
            {
                "run_id": run_id,
                "job_id": job.id,
                "profile_id": profile.id,
                "scoring_version": self.version.scoring_version,
                "total_score": scoring.total_score,
                "confidence_score": scoring.confidence_score,
                "data_coverage_score": scoring.data_coverage_score,
                "eligibility_status": eligibility_status,
                "recommendation_type": recommendation,
                "strengths": strengths,
                "gaps": gaps,
                "missing_information": scoring.missing_information,
                "hard_constraint_results": [asdict(item) for item in constraints],
                "growth_opportunities": growth,
                "summary_explanation": explanation,
                "profile_snapshot_hash": profile_hash,
                "job_snapshot_hash": job_hash,
                "configuration_hash": configuration_hash,
                "is_stale": False,
            },
            [asdict(item) for item in scoring.components],
        )
        evaluation.updated_at = utc_now()
        return evaluation

    def _profile(self, profile_id: int | None) -> ProfessionalProfile:
        profile = self.session.get(ProfessionalProfile, profile_id) if profile_id else ProfileRepository(self.session).get_main_profile()
        if profile is None:
            raise ValidationError("Crea un perfil profesional antes de evaluar vacantes.")
        return profile

    def _job(self, job_id: int) -> Job:
        job = JobRepository(self.session).get_job(job_id)
        if job is None:
            raise ValidationError("No se encontro la vacante.")
        return job

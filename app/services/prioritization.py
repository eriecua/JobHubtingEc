"""Strategic prioritization engine for evaluated job opportunities."""

from __future__ import annotations

from dataclasses import asdict
from datetime import date
from decimal import Decimal
import hashlib
import json
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.config import load_priority_config
from app.models import Job, JobEvaluation, JobPriority, ProfessionalProfile
from app.repositories import JobRepository, PrioritizationRepository, ProfileRepository
from app.services.actionability import ActionabilityService
from app.services.application_effort import ApplicationEffortService
from app.services.evaluation_version import EvaluationVersionService
from app.services.priority_types import PriorityComponent, PriorityResult
from app.services.strategic_alignment import StrategicAlignmentService
from app.services.urgency import UrgencyService
from app.services.validation import ValidationError


class PrioritizationService:
    """Calculate and persist deterministic strategic priorities."""

    def __init__(self, session: Session, config: dict[str, Any] | None = None) -> None:
        self.session = session
        self.config = config or load_priority_config()
        self.repo = PrioritizationRepository(session)
        self.urgency = UrgencyService(self.config)
        self.alignment = StrategicAlignmentService(session)
        self.actionability = ActionabilityService()
        self.effort = ApplicationEffortService(self.config)
        self.version = EvaluationVersionService(session)

    @property
    def prioritization_version(self) -> str:
        """Return configured prioritization version."""

        return str(self.config["prioritization_version"])

    def configuration_hash(self, config: dict[str, Any] | None = None) -> str:
        """Return stable hash of active prioritization configuration."""

        return self._hash(config or self.config)

    def prioritize_job(
        self,
        job_id: int,
        profile_id: int | None = None,
        manual_effort_level: str | None = None,
    ) -> dict[str, Any]:
        """Prioritize one job and persist the result."""

        profile = self._profile(profile_id)
        job = self._job(job_id)
        run = self.repo.create_run(profile.id, self.prioritization_version, self.configuration_hash(), jobs_considered=1)
        self.session.commit()
        try:
            result = self.calculate_priority(profile, job, manual_effort_level)
            priority = self._save_priority(run.id, profile, job, result, position=1)
            self.repo.finish_run(run.id, 1, 0, 0, [])
            return {"run_id": run.id, "priority_id": priority.id, "priority_score": float(priority.priority_score)}
        except Exception as exc:
            self.session.rollback()
            self.repo.fail_run(run.id, str(exc))
            raise

    def prioritize_jobs(self, job_ids: list[int], profile_id: int | None = None) -> dict[str, Any]:
        """Prioritize several jobs, continuing after individual failures."""

        if not job_ids:
            raise ValidationError("Selecciona al menos una vacante para priorizar.")
        profile = self._profile(profile_id)
        run = self.repo.create_run(profile.id, self.prioritization_version, self.configuration_hash(), jobs_considered=len(job_ids))
        self.session.commit()
        calculated: list[tuple[Job, PriorityResult]] = []
        errors: list[str] = []
        excluded = 0
        for job_id in job_ids:
            try:
                job = self._job(job_id)
                if self._exclude_from_main_inbox(job, profile.id):
                    excluded += 1
                    continue
                calculated.append((job, self.calculate_priority(profile, job)))
            except Exception as exc:
                errors.append(f"Vacante {job_id}: {exc}")
        calculated.sort(key=lambda item: (item[1].priority_score, item[1].urgency_score), reverse=True)
        saved = 0
        for position, (job, result) in enumerate(calculated, start=1):
            try:
                self._save_priority(run.id, profile, job, result, position)
                saved += 1
            except Exception as exc:
                errors.append(f"Vacante {job.id}: {exc}")
        self.repo.finish_run(run.id, saved, excluded, len(errors), errors)
        return {"run_id": run.id, "jobs_prioritized": saved, "jobs_excluded": excluded, "jobs_failed": len(errors), "errors": errors}

    def prioritize_all_active(self, limit: int = 1000, profile_id: int | None = None) -> dict[str, Any]:
        """Prioritize active jobs with a local safety limit."""

        jobs = JobRepository(self.session).list_jobs({"is_active": True}, limit=limit)
        return self.prioritize_jobs([job.id for job in jobs], profile_id)

    def calculate_priority(
        self,
        profile: ProfessionalProfile,
        job: Job,
        manual_effort_level: str | None = None,
    ) -> PriorityResult:
        """Calculate strategic priority without persisting it."""

        evaluation = self.repo.latest_evaluation(job.id, profile.id)
        has_application = self.repo.application_exists(job.id, profile.id)
        effort_override = self.repo.get_effort_override(job.id, profile.id)
        effective_effort_level = manual_effort_level or (effort_override.effort_level if effort_override else None)
        weights = self.config["priority_weights"]
        reasons: list[dict[str, Any]] = []
        warnings: list[str] = []
        blockers: list[str] = []
        components: list[PriorityComponent] = []

        compatibility_raw = self._compatibility_raw(evaluation, warnings)
        components.append(self._component("compatibility", weights["compatibility"], compatibility_raw, "Compatibilidad vigente de Fase 4."))

        confidence_raw = self._confidence_raw(evaluation, warnings)
        components.append(self._component("confidence", weights["confidence"], confidence_raw, "Confianza de la evaluacion."))

        urgency_raw, deadline, urgency_reasons, urgency_warnings, urgency_blockers = self.urgency.score(job)
        reasons.extend(urgency_reasons)
        warnings.extend(urgency_warnings)
        blockers.extend(urgency_blockers)
        components.append(self._component("urgency", weights["urgency"], urgency_raw, "Urgencia por publicacion, vencimiento y estado."))

        alignment_raw, alignment_reasons, alignment_warnings = self.alignment.score(profile, job, evaluation)
        reasons.extend(alignment_reasons)
        warnings.extend(alignment_warnings)
        components.append(self._component("strategic_alignment", weights["strategic_alignment"], alignment_raw, "Alineacion con estrategia profesional."))

        growth_raw = self._growth_raw(evaluation, reasons, warnings)
        components.append(self._component("growth_value", weights["growth_value"], growth_raw, "Valor de crecimiento profesional."))

        salary_location_raw = self._salary_location_raw(evaluation, warnings)
        components.append(self._component("salary_location_fit", weights["salary_location_fit"], salary_location_raw, "Ajuste de salario, ubicacion y modalidad."))

        actionability_raw, actionability_reasons, actionability_warnings, actionability_blockers = self.actionability.score(job, evaluation, has_application)
        reasons.extend(actionability_reasons)
        warnings.extend(actionability_warnings)
        blockers.extend(actionability_blockers)
        components.append(self._component("actionability", weights["actionability"], actionability_raw, "Capacidad de actuar con informacion actual."))

        effort_raw, effort_level, effort_reasons, effort_warnings = self.effort.score(job, evaluation, effective_effort_level)
        reasons.extend(effort_reasons)
        warnings.extend(effort_warnings)
        components.append(self._component("application_effort", weights["application_effort"], effort_raw, f"Esfuerzo estimado: {effort_level}."))

        priority_score = round(sum(component.awarded_points for component in components), 2)
        action = self._recommended_action(priority_score, job, evaluation, actionability_raw, effort_level, blockers, warnings)
        bucket = self._bucket(priority_score, action, blockers, evaluation, job)
        self._add_summary_reasons(evaluation, priority_score, action, reasons, warnings, blockers)
        return PriorityResult(
            priority_score=max(0.0, min(priority_score, 100.0)),
            urgency_score=round(urgency_raw * 100, 2),
            strategic_value_score=round(alignment_raw * 100, 2),
            actionability_score=round(actionability_raw * 100, 2),
            application_effort_score=round(effort_raw * 100, 2),
            recommended_action=action,
            priority_bucket=bucket,
            decision_deadline=deadline,
            reasons=reasons[:12],
            warnings=list(dict.fromkeys(warnings))[:10],
            blocking_factors=list(dict.fromkeys(blockers))[:10],
            components=components,
        )

    def set_effort_override(
        self,
        job_id: int,
        profile_id: int | None,
        effort_level: str,
        notes: str | None = None,
    ) -> None:
        """Persist a manual effort correction and mark latest priority stale."""

        profile = self._profile(profile_id)
        if effort_level not in self.config["application_effort"]:
            raise ValidationError("Nivel de esfuerzo no permitido.")
        job = self._job(job_id)
        self.repo.set_effort_override(job.id, profile.id, effort_level, notes)
        latest = self.repo.latest_priority(job.id, profile.id)
        if latest:
            self.repo.mark_stale(latest.id)

    def mark_stale_for_current_state(self, job_id: int, profile_id: int | None = None) -> bool:
        """Mark latest priority stale when job, evaluation, config or decision changed."""

        profile = self._profile(profile_id)
        job = self._job(job_id)
        latest = self.repo.latest_priority(job.id, profile.id)
        if latest is None or latest.is_stale:
            return False
        evaluation = self.repo.latest_evaluation(job.id, profile.id)
        changed = (
            latest.configuration_hash != self.configuration_hash()
            or latest.job_snapshot_hash != self._job_hash(job)
            or latest.evaluation_snapshot_hash != self._evaluation_hash(evaluation, job.id, profile.id)
        )
        if changed:
            self.repo.mark_stale(latest.id)
        return changed

    def _save_priority(
        self,
        run_id: int,
        profile: ProfessionalProfile,
        job: Job,
        result: PriorityResult,
        position: int,
    ) -> JobPriority:
        evaluation = self.repo.latest_evaluation(job.id, profile.id)
        priority = self.repo.save_priority(
            {
                "prioritization_run_id": run_id,
                "job_id": job.id,
                "evaluation_id": evaluation.id if evaluation else None,
                "profile_id": profile.id,
                "priority_score": result.priority_score,
                "urgency_score": result.urgency_score,
                "strategic_value_score": result.strategic_value_score,
                "actionability_score": result.actionability_score,
                "application_effort_score": result.application_effort_score,
                "recommended_action": result.recommended_action,
                "priority_bucket": result.priority_bucket,
                "position_in_queue": position,
                "decision_deadline": result.decision_deadline,
                "reasons": [*result.reasons, {"factor": "componentes", "detail": [asdict(component) for component in result.components]}],
                "warnings": result.warnings,
                "blocking_factors": result.blocking_factors,
                "configuration_hash": self.configuration_hash(),
                "job_snapshot_hash": self._job_hash(job),
                "evaluation_snapshot_hash": self._evaluation_hash(evaluation, job.id, profile.id),
                "is_stale": False,
            }
        )
        self.session.commit()
        self.session.refresh(priority)
        return priority

    def _component(self, name: str, weight: int, raw: float, explanation: str) -> PriorityComponent:
        raw = max(0.0, min(float(raw), 1.0))
        return PriorityComponent(name, weight, round(raw, 4), round(raw * weight, 2), explanation)

    def _compatibility_raw(self, evaluation: JobEvaluation | None, warnings: list[str]) -> float:
        if evaluation is None:
            warnings.append("No existe evaluacion de compatibilidad.")
            return 0.35
        if evaluation.is_stale:
            warnings.append("La evaluacion esta obsoleta.")
        return float(evaluation.total_score) / 100

    def _confidence_raw(self, evaluation: JobEvaluation | None, warnings: list[str]) -> float:
        if evaluation is None:
            return 0.20
        confidence = float(evaluation.confidence_score)
        if confidence < 50:
            warnings.append("Confianza baja en la evaluacion.")
        if confidence >= 85:
            return 1.0
        if confidence >= 70:
            return 0.85
        if confidence >= 50:
            return 0.65
        if confidence >= 30:
            return 0.35
        return 0.15

    def _growth_raw(self, evaluation: JobEvaluation | None, reasons: list[dict[str, Any]], warnings: list[str]) -> float:
        if evaluation is None:
            return 0.40
        growth_component = next((component for component in evaluation.components if component.component_name == "growth"), None)
        critical_gaps = [gap for gap in evaluation.gaps if gap.get("severity") == "Critica"]
        raw = float(growth_component.raw_score) if growth_component else 0.50
        if critical_gaps:
            raw = min(raw, 0.45)
            warnings.append("Existen brechas criticas que reducen el valor de crecimiento.")
        elif evaluation.growth_opportunities:
            raw = max(raw, 0.75)
            reasons.append({"factor": "crecimiento", "detail": "Tiene oportunidades de crecimiento registradas."})
        return raw

    def _salary_location_raw(self, evaluation: JobEvaluation | None, warnings: list[str]) -> float:
        if evaluation is None:
            return 0.45
        scores = [
            float(component.raw_score)
            for component in evaluation.components
            if component.component_name in {"salary", "location_modality"}
        ]
        if not scores:
            warnings.append("No hay datos suficientes de salario o ubicacion.")
            return 0.45
        return sum(scores) / len(scores)

    def _recommended_action(
        self,
        priority_score: float,
        job: Job,
        evaluation: JobEvaluation | None,
        actionability_raw: float,
        effort_level: str,
        blockers: list[str],
        warnings: list[str],
    ) -> str:
        if job.expiration_date and job.expiration_date < date.today():
            return "Descartar"
        if job.status in {"Vencida", "Cerrada", "Eliminada logicamente"}:
            return "Descartar"
        if job.is_suspicious:
            return "Revisar"
        if job.publication_date and (date.today() - job.publication_date).days > 30 and not job.expiration_date:
            return "Revisar"
        if evaluation is None or evaluation.is_stale:
            return "Revisar"
        if evaluation.eligibility_status == "No elegible":
            return "Descartar"
        if evaluation.eligibility_status == "Requiere revision":
            return "Revisar"
        if job.is_duplicate:
            return "Revisar"
        if any("postulacion registrada" in blocker.lower() for blocker in blockers):
            return "Revisar"
        if actionability_raw < 0.45:
            return "Esperar informacion"
        if any("salario" in warning.lower() for warning in warnings) and float(evaluation.confidence_score) < 60:
            return "Esperar informacion"
        critical_gaps = [gap for gap in evaluation.gaps if gap.get("severity") == "Critica"]
        if len(critical_gaps) >= 2:
            return "Descartar"
        if critical_gaps or effort_level in {"Medio", "Alto"} and priority_score >= 70:
            return "Preparar postulacion"
        if evaluation.recommendation_type == "Oportunidad de crecimiento" and evaluation.growth_opportunities and priority_score < self.config["priority_thresholds"]["critical"]:
            return "Explorar" if priority_score < self.config["priority_thresholds"]["high"] else "Preparar postulacion"
        if priority_score >= self.config["priority_thresholds"]["high"] and float(evaluation.total_score) >= 75 and actionability_raw >= 0.70 and float(evaluation.confidence_score) >= 60:
            return "Postular"
        if evaluation.recommendation_type == "Oportunidad de crecimiento" or (priority_score >= 55 and not critical_gaps):
            return "Explorar"
        if priority_score < self.config["priority_thresholds"]["low"]:
            return "Descartar"
        return "Guardar"

    def _bucket(self, priority_score: float, action: str, blockers: list[str], evaluation: JobEvaluation | None, job: Job) -> str:
        if action == "Revisar" or (evaluation and evaluation.is_stale):
            return "Requiere revision"
        if action == "Descartar" or blockers or (job.expiration_date and job.expiration_date < date.today()):
            return "Sin prioridad"
        thresholds = self.config["priority_thresholds"]
        if priority_score >= thresholds["critical"]:
            return "Critica"
        if priority_score >= thresholds["high"]:
            return "Alta"
        if priority_score >= thresholds["medium"]:
            return "Media"
        if priority_score >= thresholds["low"]:
            return "Baja"
        return "Sin prioridad"

    def _add_summary_reasons(
        self,
        evaluation: JobEvaluation | None,
        priority_score: float,
        action: str,
        reasons: list[dict[str, Any]],
        warnings: list[str],
        blockers: list[str],
    ) -> None:
        reasons.insert(0, {"factor": "prioridad", "detail": f"Prioridad calculada: {priority_score:.0f}/100."})
        reasons.insert(1, {"factor": "accion", "detail": f"Accion recomendada: {action}."})
        if evaluation:
            reasons.insert(2, {"factor": "compatibilidad", "detail": f"Compatibilidad: {float(evaluation.total_score):.0f}/100."})
        if blockers:
            reasons.append({"factor": "bloqueos", "detail": "; ".join(blockers[:3])})

    def _exclude_from_main_inbox(self, job: Job, profile_id: int) -> bool:
        if not job.is_active:
            return True
        if job.status in set(self.config.get("excluded_job_statuses", [])):
            return True
        if job.expiration_date and job.expiration_date < date.today():
            return True
        latest_decision = self.repo.latest_decision(job.id, profile_id)
        if latest_decision and latest_decision.decision in {"Descartar", "Postular"}:
            return True
        return self.repo.application_exists(job.id, profile_id)

    def _job_hash(self, job: Job) -> str:
        return self.version.job_hash(job)

    def _evaluation_hash(self, evaluation: JobEvaluation | None, job_id: int, profile_id: int) -> str:
        decision = self.repo.latest_decision(job_id, profile_id)
        data = {
            "evaluation": self._model(evaluation),
            "components": [self._model(component) for component in evaluation.components] if evaluation else [],
            "decision": self._model(decision),
            "profile_hash": self.version.profile_hash(self._profile(profile_id)),
            "effort_override": self._model(self.repo.get_effort_override(job_id, profile_id)),
        }
        return self._hash(data)

    def _hash(self, data: Any) -> str:
        return hashlib.sha256(json.dumps(data, sort_keys=True, ensure_ascii=False, default=self._json_default).encode("utf-8")).hexdigest()

    def _model(self, item: Any) -> dict[str, Any] | None:
        if item is None:
            return None
        return {column.name: getattr(item, column.name) for column in item.__table__.columns}

    def _json_default(self, value: Any) -> Any:
        if isinstance(value, (date,)):
            return value.isoformat()
        if isinstance(value, Decimal):
            return str(value)
        return str(value)

    def _profile(self, profile_id: int | None) -> ProfessionalProfile:
        profile = self.session.get(ProfessionalProfile, profile_id) if profile_id else ProfileRepository(self.session).get_main_profile()
        if profile is None:
            raise ValidationError("Crea un perfil profesional antes de priorizar vacantes.")
        return profile

    def _job(self, job_id: int) -> Job:
        job = self.session.get(Job, job_id)
        if job is None:
            raise ValidationError("No se encontro la vacante.")
        return job

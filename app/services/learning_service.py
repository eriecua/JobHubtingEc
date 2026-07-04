"""Deterministic supervised learning analysis for Phase 6."""

from __future__ import annotations

from collections import Counter, defaultdict
from datetime import date, timedelta
from decimal import Decimal
import hashlib
import json
from typing import Any

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.config import load_feedback_learning_config
from app.models import AdjustmentProposal, Application, ConfigurationChangeHistory, Job, JobDecision, JobPriority, LearningRun, ProfessionalProfile
from app.repositories import FeedbackRepository, ProfileRepository
from app.services import feedback_types as types
from app.services.validation import ValidationError


class LearningService:
    """Analyze feedback patterns and generate explainable proposals."""

    RESPONSE_OUTCOMES = {
        "Respuesta automatica",
        "Contacto de reclutador",
        "Rechazo",
        "Prueba tecnica",
        "Entrevista",
        "Segunda entrevista",
        "Entrevista final",
        "Oferta",
        "Oferta aceptada",
        "Oferta rechazada",
    }
    INTERVIEW_OUTCOMES = {"Entrevista", "Segunda entrevista", "Entrevista final"}
    OFFER_OUTCOMES = {"Oferta", "Oferta aceptada", "Oferta rechazada"}

    def __init__(self, session: Session, config: dict[str, Any] | None = None) -> None:
        self.session = session
        self.config = config or load_feedback_learning_config()
        self.repo = FeedbackRepository(session)

    @property
    def learning_version(self) -> str:
        """Return the configured learning version."""

        return str(self.config["learning_version"])

    def configuration_hash(self) -> str:
        """Return a stable hash of the learning configuration."""

        return hashlib.sha256(json.dumps(self.config, sort_keys=True, ensure_ascii=False, default=str).encode("utf-8")).hexdigest()

    def run_analysis(
        self,
        profile_id: int | None = None,
        period_start: date | None = None,
        period_end: date | None = None,
    ) -> dict[str, Any]:
        """Run a deterministic learning analysis for one profile and period."""

        profile = ProfileRepository(self.session).get_main_profile() if profile_id is None else self.session.get(ProfessionalProfile, profile_id)
        if profile is None:
            raise ValidationError("Crea un perfil profesional antes de ejecutar aprendizaje.")
        end = period_end or date.today()
        start = period_start or end - timedelta(days=90)
        if start > end:
            raise ValidationError("La fecha inicial no puede ser posterior a la fecha final.")
        run = self.repo.create_learning_run(profile.id, self.learning_version, self.configuration_hash(), start, end)
        try:
            result = self._analyze(run, start, end)
            self.repo.complete_learning_run(
                run.id,
                result["status"],
                result["events"],
                result["applications"],
                result["outcomes"],
                result["proposals"],
                result["warnings"],
            )
            return {"run_id": run.id, **result}
        except Exception as exc:
            self.session.rollback()
            self.repo.fail_learning_run(run.id, str(exc))
            raise

    def review_proposal(self, proposal_id: int, approve: bool, reviewed_by: str = "Usuario", notes: str | None = None) -> AdjustmentProposal:
        """Approve or reject a proposal without applying it automatically."""

        proposal = self.repo.get_proposal(proposal_id)
        if proposal.status not in {types.PROPOSAL_STATUS_PENDING, types.PROPOSAL_STATUS_POSTPONED}:
            raise ValidationError("Solo se pueden revisar propuestas pendientes o pospuestas.")
        status = types.PROPOSAL_STATUS_APPROVED if approve else types.PROPOSAL_STATUS_REJECTED
        return self.repo.update_proposal_status(proposal.id, status, reviewed_by, notes)

    def postpone_proposal(self, proposal_id: int, reviewed_by: str = "Usuario", notes: str | None = None) -> AdjustmentProposal:
        """Postpone a pending proposal without applying or rejecting it."""

        proposal = self.repo.get_proposal(proposal_id)
        if proposal.status != types.PROPOSAL_STATUS_PENDING:
            raise ValidationError("Solo se pueden posponer propuestas pendientes.")
        return self.repo.update_proposal_status(proposal.id, types.PROPOSAL_STATUS_POSTPONED, reviewed_by, notes)

    def apply_proposal(self, proposal_id: int, changed_by: str = "Usuario", notes: str | None = None) -> ConfigurationChangeHistory:
        """Apply an approved proposal by recording a reversible versioned change."""

        proposal = self.repo.get_proposal(proposal_id)
        if proposal.status != types.PROPOSAL_STATUS_APPROVED:
            raise ValidationError("La propuesta debe estar aprobada antes de aplicarla.")
        if proposal.learning_run.configuration_hash != self.configuration_hash():
            raise ValidationError("La configuracion de aprendizaje cambio desde que se genero la propuesta; vuelve a analizar antes de aplicarla.")
        change = self.repo.save_configuration_change(
            {
                "proposal_id": proposal.id,
                "profile_id": proposal.profile_id,
                "configuration_area": proposal.proposal_type,
                "previous_value_json": proposal.current_value_json,
                "new_value_json": proposal.proposed_value_json,
                "reason": (notes or proposal.evidence_summary).strip(),
                "changed_by": changed_by,
                "rollback_data_json": proposal.current_value_json,
            }
        )
        self.repo.update_proposal_status(proposal.id, types.PROPOSAL_STATUS_APPLIED, mark_applied=True)
        return change

    def revert_proposal(self, proposal_id: int, reverted_by: str = "Usuario") -> ConfigurationChangeHistory:
        """Revert an applied proposal in the change history."""

        proposal = self.repo.get_proposal(proposal_id)
        if proposal.status != types.PROPOSAL_STATUS_APPLIED:
            raise ValidationError("Solo se pueden revertir propuestas aplicadas.")
        change = self.repo.latest_change_for_proposal(proposal.id)
        if change is None:
            raise ValidationError("No se encontro el cambio versionado para revertir.")
        change.reverted_at = date_to_datetime(date.today())
        change.reverted_by = reverted_by
        self.session.commit()
        self.repo.update_proposal_status(proposal.id, types.PROPOSAL_STATUS_REVERTED, mark_reverted=True)
        self.session.refresh(change)
        return change

    def _analyze(self, run: LearningRun, period_start: date, period_end: date) -> dict[str, Any]:
        events = self.repo.list_feedback_events(run.profile_id, period_start, period_end)
        decisions = self.repo.list_decisions(run.profile_id, period_start, period_end)
        applications = self.repo.list_applications(period_start, period_end, run.profile_id)
        outcomes = self.repo.list_outcomes(period_start, period_end, run.profile_id)
        priorities = self.repo.list_priorities(run.profile_id, period_start, period_end, limit=1000)
        warnings: list[str] = []
        metric_count = 0
        proposal_count = 0
        expired = self.repo.expire_stale_proposals(run.profile_id, date_to_datetime(date.today()))
        if expired:
            warnings.append(f"Se marcaron {expired} propuestas vencidas como expiradas.")

        metric_count += self._conversion_metrics(run.id, events, decisions, applications, outcomes)
        metric_count += self._signal_recency_metrics(run.id, events, period_end)
        metric_count += self._ranking_metrics(run.id, events, applications, outcomes, priorities)
        metric_count += self._calibration_metrics(run.id, applications, outcomes, priorities)
        metric_count += self._segment_metrics(run.id, applications, outcomes)
        proposal_count += self._generate_source_proposals(run, applications, outcomes, warnings)
        proposal_count += self._generate_location_discard_proposals(run, decisions, warnings)
        proposal_count += self._generate_gap_proposals(run, priorities, warnings)
        if len(events) < self.config["learning_thresholds"]["minimum_events_for_pattern"]:
            warnings.append("Muestra insuficiente de eventos para patrones fuertes.")
        if len(applications) < self.config["learning_thresholds"]["minimum_applications_for_rate"]:
            warnings.append("Muestra insuficiente de postulaciones para tasas estables.")
        self.session.commit()
        return {
            "status": types.LEARNING_STATUS_COMPLETED_WITH_WARNINGS if warnings else types.LEARNING_STATUS_COMPLETED,
            "events": len(events),
            "applications": len(applications),
            "outcomes": len(outcomes),
            "metrics": metric_count,
            "proposals": proposal_count,
            "warnings": list(dict.fromkeys(warnings)),
        }

    def _conversion_metrics(self, run_id: int, events: list[Any], decisions: list[JobDecision], applications: list[Application], outcomes: list[Any]) -> int:
        reviewed_job_ids = {event.job_id for event in events if event.event_type in {"viewed_detail", "opened_source", "revisited"}}
        reviewed_job_ids.update(decision.job_id for decision in decisions)
        captured = self.session.scalar(select(func.count(Job.id))) or 0
        saved = len({event.job_id for event in events if event.event_type == "saved"} | {decision.job_id for decision in decisions if decision.decision == "Guardar"})
        response_jobs = self._jobs_with_outcomes(outcomes, self.RESPONSE_OUTCOMES)
        interview_jobs = self._jobs_with_outcomes(outcomes, self.INTERVIEW_OUTCOMES)
        offer_jobs = self._jobs_with_outcomes(outcomes, self.OFFER_OUTCOMES)
        accepted_jobs = self._jobs_with_outcomes(outcomes, {"Oferta aceptada"})
        rows = [
            ("vacantes_revisadas_sobre_captadas", len(reviewed_job_ids), captured, "Vacantes revisadas sobre vacantes captadas."),
            ("guardadas_sobre_revisadas", saved, len(reviewed_job_ids), "Vacantes guardadas sobre vacantes revisadas."),
            ("respuestas_sobre_postulaciones", len(response_jobs), len(applications), "Postulaciones con al menos una respuesta real de empresa."),
            ("entrevistas_sobre_postulaciones", len(interview_jobs), len(applications), "Postulaciones con al menos una entrevista."),
            ("ofertas_sobre_entrevistas", len(offer_jobs), len(interview_jobs), "Postulaciones con oferta sobre postulaciones con entrevista."),
            ("ofertas_sobre_postulaciones", len(offer_jobs), len(applications), "Postulaciones con oferta sobre postulaciones."),
            ("aceptaciones_sobre_ofertas", len(accepted_jobs), len(offer_jobs), "Ofertas aceptadas sobre postulaciones con oferta."),
        ]
        for name, numerator, denominator, explanation in rows:
            self._save_rate_metric(run_id, name, "General", None, numerator, denominator, explanation)
        return len(rows)

    def _signal_recency_metrics(self, run_id: int, events: list[Any], period_end: date) -> int:
        weighted_total = sum(float(event.signal_value) * self._recency_factor(event.occurred_at.date(), period_end) for event in events)
        band_counts = Counter(self._recency_band(event.occurred_at.date(), period_end) for event in events)
        self._save_value_metric(
            run_id,
            "senal_ponderada_por_recencia",
            "General",
            None,
            len(events),
            weighted_total,
            "Suma de senales con decaimiento por recencia segun config/feedback_learning.yaml; no implica causalidad.",
            evidence={"bands": dict(band_counts), "period_end": period_end.isoformat()},
        )
        return 1

    def _ranking_metrics(self, run_id: int, events: list[Any], applications: list[Application], outcomes: list[Any], priorities: list[JobPriority]) -> int:
        relevant_jobs = {event.job_id for event in events if event.event_type in types.RELEVANT_EVENT_TYPES}
        relevant_jobs.update(application.job_id for application in applications)
        interview_jobs = self._jobs_with_outcomes(outcomes, self.INTERVIEW_OUTCOMES)
        ordered = sorted(priorities, key=lambda item: float(item.priority_score), reverse=True)
        top5 = ordered[:5]
        top10 = ordered[:10]
        discarded_top5 = sum(1 for item in top5 if item.job_id in {event.job_id for event in events if event.event_type == "discarded"})
        count = 0
        self._save_rate_metric(run_id, "precision_at_5", "Recomendacion", "Top 5", sum(1 for item in top5 if item.job_id in relevant_jobs), len(top5), "Proporcion de Top 5 con senales relevantes.")
        self._save_rate_metric(run_id, "precision_at_10", "Recomendacion", "Top 10", sum(1 for item in top10 if item.job_id in relevant_jobs), len(top10), "Proporcion de Top 10 con senales relevantes.")
        self._save_count_metric(run_id, "descartadas_en_top_5", "Recomendacion", "Top 5", discarded_top5, len(top5), "Recomendaciones Top 5 descartadas por el usuario.")
        self._save_count_metric(run_id, "entrevistas_en_top_5", "Recomendacion", "Top 5", sum(1 for item in top5 if item.job_id in interview_jobs), len(top5), "Entrevistas originadas desde el Top 5.")
        self._save_count_metric(run_id, "entrevistas_fuera_top_10", "Recomendacion", "Fuera Top 10", sum(1 for job_id in interview_jobs if job_id not in {item.job_id for item in top10}), len(interview_jobs), "Entrevistas originadas fuera del Top 10.")
        count += 5
        interview_priorities = [item for item in priorities if item.job_id in interview_jobs]
        if interview_priorities:
            avg_priority = sum(float(item.priority_score) for item in interview_priorities) / len(interview_priorities)
            avg_compatibility = sum(float(item.evaluation.total_score) for item in interview_priorities if item.evaluation) / max(1, sum(1 for item in interview_priorities if item.evaluation))
            self._save_value_metric(run_id, "prioridad_media_con_entrevista", "Recomendacion", "Entrevistas", len(interview_priorities), avg_priority, "Prioridad promedio de vacantes que generaron entrevista.")
            self._save_value_metric(run_id, "compatibilidad_media_con_entrevista", "Recomendacion", "Entrevistas", len(interview_priorities), avg_compatibility, "Compatibilidad promedio de vacantes que generaron entrevista.")
            count += 2
        return count

    def _calibration_metrics(self, run_id: int, applications: list[Application], outcomes: list[Any], priorities: list[JobPriority]) -> int:
        latest_by_job: dict[int, JobPriority] = {}
        for priority in sorted(priorities, key=lambda item: item.created_at):
            latest_by_job[priority.job_id] = priority
        outcomes_by_job: dict[int, list[str]] = defaultdict(list)
        for outcome in outcomes:
            outcomes_by_job[outcome.application.job_id].append(outcome.outcome_type)
        count = 0
        for item in self.config["priority_ranges"]:
            label = item["label"]
            minimum = float(item["minimum"])
            maximum = float(item["maximum"])
            job_ids = [app.job_id for app in applications if app.job_id in latest_by_job and minimum <= float(latest_by_job[app.job_id].priority_score) <= maximum]
            response = sum(1 for job_id in job_ids if any(value in self.RESPONSE_OUTCOMES for value in outcomes_by_job[job_id]))
            interview = sum(1 for job_id in job_ids if any(value in self.INTERVIEW_OUTCOMES for value in outcomes_by_job[job_id]))
            offer = sum(1 for job_id in job_ids if any(value in self.OFFER_OUTCOMES for value in outcomes_by_job[job_id]))
            successful = len({job_id for job_id in job_ids if any(value in self.RESPONSE_OUTCOMES for value in outcomes_by_job[job_id])})
            self._save_rate_metric(
                run_id,
                "calibracion_prioridad",
                "Rango de prioridad",
                label,
                successful,
                len(job_ids),
                f"Rango {label}: {len(job_ids)} postulaciones, {response} respuestas, {interview} entrevistas, {offer} ofertas. No implica causalidad.",
            )
            count += 1
        return count

    def _segment_metrics(self, run_id: int, applications: list[Application], outcomes: list[Any]) -> int:
        by_job_outcomes: dict[int, list[str]] = defaultdict(list)
        for outcome in outcomes:
            by_job_outcomes[outcome.application.job_id].append(outcome.outcome_type)
        counters: dict[tuple[str, str], list[int]] = defaultdict(lambda: [0, 0])
        for application in applications:
            segments = {
                "Fuente": application.job.source,
                "Ciudad": application.job.city or application.job.location or "No especificada",
                "Sector": application.job.sector or "No especificado",
                "Cargo": application.job.normalized_title or application.job.title,
                "Empresa": application.job.company,
                "Modalidad": application.job.modality or "No especificada",
            }
            got_interview = any(value in self.INTERVIEW_OUTCOMES for value in by_job_outcomes[application.job_id])
            for scope, value in segments.items():
                counters[(scope, value)][0] += 1
                counters[(scope, value)][1] += int(got_interview)
        count = 0
        minimum = self.config["learning_thresholds"]["minimum_applications_for_rate"]
        for (scope, value), (sample, interviews) in counters.items():
            if sample < minimum:
                continue
            self._save_rate_metric(run_id, "tasa_entrevista_por_segmento", scope, value, interviews, sample, f"Entrevistas sobre postulaciones para {scope.lower()} '{value}'.")
            count += 1
        return count

    def _generate_source_proposals(self, run: LearningRun, applications: list[Application], outcomes: list[Any], warnings: list[str]) -> int:
        minimum = self.config["learning_thresholds"]["minimum_applications_for_rate"]
        minimum_outcomes = self.config["learning_thresholds"]["minimum_outcomes_for_adjustment"]
        by_source: dict[str, set[int]] = defaultdict(set)
        interview_jobs = self._jobs_with_outcomes(outcomes, self.INTERVIEW_OUTCOMES)
        response_jobs = self._jobs_with_outcomes(outcomes, self.RESPONSE_OUTCOMES)
        for application in applications:
            by_source[application.job.source].add(application.job_id)
        if len(applications) < minimum:
            warnings.append("No se crean propuestas por fuente: muestra insuficiente de postulaciones.")
            return 0
        if len(response_jobs) < minimum_outcomes:
            warnings.append("No se crean propuestas por fuente: resultados reales insuficientes.")
            return 0
        overall = len(interview_jobs) / max(1, len(applications))
        proposals = 0
        for source, job_ids in by_source.items():
            if len(job_ids) < minimum:
                continue
            rate = len(job_ids & interview_jobs) / len(job_ids)
            if rate > overall and len(job_ids & interview_jobs) >= self.config["learning_thresholds"]["minimum_interviews_for_strong_signal"]:
                recency = self._average_recency_for_jobs(outcomes, job_ids, run.period_end)
                inserted = self._save_proposal(
                    run,
                    proposal_type="Ajustar preferencia",
                    target_key=f"source:{source}",
                    current={"source": source, "visibility": "normal"},
                    proposed={
                        "source": source,
                        "visibility": "prioritaria moderada",
                        "maximum_change_percent": self.config["learning_thresholds"]["maximum_adjustment_per_run_percent"],
                    },
                    expected=f"Dar mayor visibilidad a vacantes de {source} en revision manual sin convertirla en restriccion.",
                    evidence=f"{source} genero {len(job_ids & interview_jobs)} entrevistas en {len(job_ids)} postulaciones frente a una tasa general de {overall:.2f}; recencia media {recency:.2f}.",
                    evidence_json={
                        "source": source,
                        "applications": len(job_ids),
                        "interviews": len(job_ids & interview_jobs),
                        "overall_rate": overall,
                        "source_rate": rate,
                        "recency_factor": recency,
                    },
                    sample_size=len(job_ids),
                    confidence=min(0.85, (0.45 + rate) * recency),
                    risk=types.RISK_MEDIUM,
                )
                proposals += int(inserted)
        return proposals

    def _generate_location_discard_proposals(self, run: LearningRun, decisions: list[JobDecision], warnings: list[str]) -> int:
        minimum = self.config["learning_thresholds"]["minimum_events_for_pattern"]
        location_discards = [
            decision
            for decision in decisions
            if decision.decision == "Descartar" and decision.reason_code and "ubicacion" in decision.reason_code.lower()
        ]
        if len(location_discards) < minimum:
            warnings.append("No se crean propuestas de ubicacion: descartes por ubicacion insuficientes.")
            return 0
        provinces = Counter(decision.job.province or decision.job.location or "No especificada" for decision in location_discards)
        province, count = provinces.most_common(1)[0]
        inserted = self._save_proposal(
            run,
            proposal_type="Ajustar preferencia",
            target_key=f"location:{province}",
            current={"province": province, "preference": "no inferida"},
            proposed={"province": province, "preference": "baja"},
            expected="Reducir visibilidad de ubicaciones descartadas repetidamente sin convertirlas en exclusion obligatoria.",
            evidence=f"Se descartaron {len(location_discards)} vacantes por ubicacion; {count} corresponden a {province}.",
            evidence_json={
                "discard_count": len(location_discards),
                "top_province": province,
                "top_count": count,
                "recency_factor": sum(self._recency_factor(item.decided_at.date(), run.period_end) for item in location_discards) / len(location_discards),
            },
            sample_size=len(location_discards),
            confidence=min(0.80, 0.40 + (count / len(location_discards))),
            risk=types.RISK_MEDIUM,
        )
        return int(inserted)

    def _generate_gap_proposals(self, run: LearningRun, priorities: list[JobPriority], warnings: list[str]) -> int:
        gaps = Counter()
        for priority in priorities:
            if not priority.evaluation:
                continue
            for gap in priority.evaluation.gaps:
                label = gap.get("label") or gap.get("name") or gap.get("requirement") or gap.get("description")
                if label:
                    gaps[str(label)] += 1
        minimum = self.config["learning_thresholds"]["minimum_events_for_pattern"]
        if not gaps or gaps.most_common(1)[0][1] < minimum:
            warnings.append("No se crean propuestas de brechas: frecuencia insuficiente.")
            return 0
        label, count = gaps.most_common(1)[0]
        inserted = self._save_proposal(
            run,
            proposal_type="Destacar brecha frecuente",
            target_key=f"gap:{label}",
            current={"gap": label, "highlighted": False},
            proposed={"gap": label, "highlighted": True},
            expected="Priorizar revision de una brecha que aparece de forma recurrente.",
            evidence=f"La brecha '{label}' aparece en {count} prioridades evaluadas.",
            evidence_json={"gap": label, "count": count},
            sample_size=count,
            confidence=min(0.75, 0.35 + count / 20),
            risk=types.RISK_LOW,
        )
        return int(inserted)

    def _save_proposal(
        self,
        run: LearningRun,
        proposal_type: str,
        target_key: str,
        current: dict[str, Any],
        proposed: dict[str, Any],
        expected: str,
        evidence: str,
        evidence_json: dict[str, Any],
        sample_size: int,
        confidence: float,
        risk: str,
    ) -> bool:
        if self.repo.find_active_proposal(run.profile_id, proposal_type, target_key):
            return False
        expiration_days = int(self.config["learning_thresholds"]["proposal_expiration_days"])
        self.repo.save_proposal(
            {
                "learning_run_id": run.id,
                "profile_id": run.profile_id,
                "proposal_type": proposal_type,
                "target_key": target_key,
                "current_value_json": current,
                "proposed_value_json": proposed,
                "expected_effect": expected,
                "evidence_summary": evidence,
                "evidence_json": evidence_json,
                "sample_size": sample_size,
                "confidence_score": round(confidence * 100, 2),
                "risk_level": risk,
                "status": types.PROPOSAL_STATUS_PENDING,
                "expires_at": date_to_datetime(date.today() + timedelta(days=expiration_days)),
            }
        )
        return True

    def _save_rate_metric(self, run_id: int, name: str, scope: str, scope_value: str | None, numerator: int, denominator: int, explanation: str) -> None:
        value = min(1.0, numerator / denominator) if denominator else 0
        self._save_value_metric(
            run_id,
            name,
            scope,
            scope_value,
            denominator,
            value,
            explanation if denominator else f"{explanation} Muestra insuficiente.",
            evidence={"numerator": numerator, "denominator": denominator},
        )

    def _jobs_with_outcomes(self, outcomes: list[Any], outcome_types: set[str]) -> set[int]:
        """Return unique job IDs that reached any of the provided outcome types."""

        return {outcome.application.job_id for outcome in outcomes if outcome.outcome_type in outcome_types}

    def _average_recency_for_jobs(self, outcomes: list[Any], job_ids: set[int], period_end: date) -> float:
        """Return average recency factor for outcomes tied to a group of jobs."""

        factors = [
            self._recency_factor(outcome.outcome_date, period_end)
            for outcome in outcomes
            if outcome.application.job_id in job_ids
        ]
        return sum(factors) / len(factors) if factors else 1.0

    def _recency_factor(self, event_date: date, period_end: date) -> float:
        """Return configured recency decay factor for a signal date."""

        age_days = max(0, (period_end - event_date).days)
        return float(self.config["feedback_recency"][self._recency_band(event_date, period_end)])

    def _recency_band(self, event_date: date, period_end: date) -> str:
        """Return the configured recency band label for a signal date."""

        age_days = max(0, (period_end - event_date).days)
        if age_days <= 30:
            return "0_30_days"
        if age_days <= 90:
            return "31_90_days"
        if age_days <= 180:
            return "91_180_days"
        return "over_180_days"

    def _save_count_metric(self, run_id: int, name: str, scope: str, scope_value: str | None, value: int, sample: int, explanation: str) -> None:
        self._save_value_metric(run_id, name, scope, scope_value, sample, value, explanation, evidence={"count": value, "sample_size": sample})

    def _save_value_metric(
        self,
        run_id: int,
        name: str,
        scope: str,
        scope_value: str | None,
        sample_size: int,
        value: float,
        explanation: str,
        baseline: float | None = None,
        evidence: dict[str, Any] | None = None,
    ) -> None:
        confidence = self._confidence_level(sample_size)
        self.repo.save_metric(
            {
                "learning_run_id": run_id,
                "metric_name": name,
                "metric_scope": scope,
                "scope_value": scope_value,
                "sample_size": sample_size,
                "metric_value": round(float(value), 4),
                "baseline_value": baseline,
                "confidence_level": confidence,
                "explanation": explanation,
                "evidence_json": evidence or {},
            }
        )

    def _confidence_level(self, sample_size: int) -> str:
        thresholds = self.config["learning_thresholds"]
        if sample_size >= thresholds["minimum_applications_for_rate"] * 3:
            return "Alta"
        if sample_size >= thresholds["minimum_applications_for_rate"]:
            return "Media"
        return "Baja"


def date_to_datetime(value: date):
    """Convert a date to a naive datetime at midnight."""

    from datetime import datetime, time

    return datetime.combine(value, time.min)

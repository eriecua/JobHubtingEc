"""Repository for Phase 6 feedback learning data."""

from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal
from typing import Any

from sqlalchemy import or_, select
from sqlalchemy.orm import Session, selectinload

from app.models import (
    AdjustmentProposal,
    Application,
    ApplicationOutcome,
    ConfigurationChangeHistory,
    FeedbackEvent,
    JobDecision,
    JobPriority,
    LearningMetric,
    LearningRun,
)
from app.models.database_models import utc_now
from app.services.validation import ValidationError


class FeedbackRepository:
    """Persist and query feedback events, learning metrics and proposals."""

    def __init__(self, session: Session) -> None:
        self.session = session

    def create_feedback_event(self, data: dict[str, Any]) -> tuple[FeedbackEvent, bool]:
        """Create a deduplicated feedback event.

        Returns the event and a boolean that is True when it was inserted.
        """

        existing = self.get_feedback_event_by_key(str(data["deduplication_key"]))
        if existing:
            return existing, False
        cleaned = dict(data)
        cleaned["signal_value"] = Decimal(str(cleaned["signal_value"]))
        event = FeedbackEvent(**cleaned)
        self.session.add(event)
        self.session.flush()
        return event, True

    def get_feedback_event_by_key(self, deduplication_key: str) -> FeedbackEvent | None:
        """Return an event by deduplication key."""

        return self.session.scalar(select(FeedbackEvent).where(FeedbackEvent.deduplication_key == deduplication_key))

    def list_feedback_events(self, profile_id: int, period_start: date, period_end: date) -> list[FeedbackEvent]:
        """List feedback events for a profile and date period."""

        return list(
            self.session.scalars(
                select(FeedbackEvent)
                .options(selectinload(FeedbackEvent.job))
                .where(
                    FeedbackEvent.profile_id == profile_id,
                    FeedbackEvent.occurred_at >= datetime.combine(period_start, datetime.min.time()),
                    FeedbackEvent.occurred_at <= datetime.combine(period_end, datetime.max.time()),
                )
                .order_by(FeedbackEvent.occurred_at.desc())
            )
        )

    def create_application_outcome(self, data: dict[str, Any]) -> ApplicationOutcome:
        """Create one application outcome stage."""

        cleaned = dict(data)
        if cleaned.get("salary_offered") is not None:
            cleaned["salary_offered"] = Decimal(str(cleaned["salary_offered"]))
        outcome = ApplicationOutcome(**cleaned)
        self.session.add(outcome)
        self.session.flush()
        return outcome

    def list_applications(self, period_start: date, period_end: date, profile_id: int | None = None) -> list[Application]:
        """List applications created in a date period, optionally scoped by profile."""

        statement = (
            select(Application)
            .options(selectinload(Application.job), selectinload(Application.outcomes))
            .where(Application.application_date >= period_start, Application.application_date <= period_end)
            .order_by(Application.application_date.desc())
        )
        if profile_id is not None:
            statement = statement.where(or_(Application.profile_id == profile_id, Application.profile_id.is_(None)))
        return list(self.session.scalars(statement))

    def list_outcomes(self, period_start: date, period_end: date, profile_id: int | None = None) -> list[ApplicationOutcome]:
        """List application outcomes in a date period, optionally scoped by profile."""

        statement = (
            select(ApplicationOutcome)
            .join(Application)
            .options(selectinload(ApplicationOutcome.application).selectinload(Application.job))
            .where(ApplicationOutcome.outcome_date >= period_start, ApplicationOutcome.outcome_date <= period_end)
            .order_by(ApplicationOutcome.outcome_date.desc())
        )
        if profile_id is not None:
            statement = statement.where(or_(Application.profile_id == profile_id, Application.profile_id.is_(None)))
        return list(self.session.scalars(statement))

    def list_decisions(self, profile_id: int, period_start: date, period_end: date) -> list[JobDecision]:
        """List human decisions in a date period."""

        return list(
            self.session.scalars(
                select(JobDecision)
                .options(selectinload(JobDecision.job), selectinload(JobDecision.priority))
                .where(
                    JobDecision.profile_id == profile_id,
                    JobDecision.decided_at >= datetime.combine(period_start, datetime.min.time()),
                    JobDecision.decided_at <= datetime.combine(period_end, datetime.max.time()),
                )
                .order_by(JobDecision.decided_at.desc())
            )
        )

    def list_priorities(self, profile_id: int, period_start: date, period_end: date, limit: int = 500) -> list[JobPriority]:
        """List priorities created in a date period."""

        return list(
            self.session.scalars(
                select(JobPriority)
                .options(selectinload(JobPriority.job), selectinload(JobPriority.evaluation))
                .where(
                    JobPriority.profile_id == profile_id,
                    JobPriority.created_at >= datetime.combine(period_start, datetime.min.time()),
                    JobPriority.created_at <= datetime.combine(period_end, datetime.max.time()),
                )
                .order_by(JobPriority.priority_score.desc())
                .limit(limit)
            )
        )

    def create_learning_run(
        self,
        profile_id: int,
        learning_version: str,
        configuration_hash: str,
        period_start: date,
        period_end: date,
    ) -> LearningRun:
        """Create a learning run in analyzing state."""

        run = LearningRun(
            profile_id=profile_id,
            learning_version=learning_version,
            configuration_hash=configuration_hash,
            period_start=period_start,
            period_end=period_end,
            status="Analizando",
        )
        self.session.add(run)
        self.session.commit()
        self.session.refresh(run)
        return run

    def complete_learning_run(
        self,
        run_id: int,
        status: str,
        events: int,
        applications: int,
        outcomes: int,
        proposals: int,
        warnings: list[str],
    ) -> LearningRun:
        """Mark a learning run as completed."""

        run = self.get_learning_run(run_id)
        run.status = status
        run.feedback_events_considered = events
        run.applications_considered = applications
        run.outcomes_considered = outcomes
        run.proposals_generated = proposals
        run.warnings_json = warnings or None
        run.completed_at = utc_now()
        self.session.commit()
        self.session.refresh(run)
        return run

    def fail_learning_run(self, run_id: int, error: str) -> LearningRun:
        """Mark a learning run as failed."""

        run = self.get_learning_run(run_id)
        run.status = "Fallido"
        run.error_summary = error
        run.completed_at = utc_now()
        self.session.commit()
        self.session.refresh(run)
        return run

    def get_learning_run(self, run_id: int) -> LearningRun:
        """Return a learning run or raise."""

        run = self.session.get(LearningRun, run_id)
        if run is None:
            raise ValidationError("No se encontro la corrida de aprendizaje.")
        return run

    def save_metric(self, data: dict[str, Any]) -> LearningMetric:
        """Persist one explainable learning metric."""

        cleaned = dict(data)
        cleaned["metric_value"] = Decimal(str(cleaned["metric_value"]))
        if cleaned.get("baseline_value") is not None:
            cleaned["baseline_value"] = Decimal(str(cleaned["baseline_value"]))
        metric = LearningMetric(**cleaned)
        self.session.add(metric)
        self.session.flush()
        return metric

    def save_proposal(self, data: dict[str, Any]) -> AdjustmentProposal:
        """Persist one adjustment proposal."""

        cleaned = dict(data)
        cleaned["confidence_score"] = Decimal(str(cleaned["confidence_score"]))
        proposal = AdjustmentProposal(**cleaned)
        self.session.add(proposal)
        self.session.flush()
        return proposal

    def find_active_proposal(self, profile_id: int, proposal_type: str, target_key: str) -> AdjustmentProposal | None:
        """Return an existing non-final proposal for the same target."""

        return self.session.scalar(
            select(AdjustmentProposal)
            .where(
                AdjustmentProposal.profile_id == profile_id,
                AdjustmentProposal.proposal_type == proposal_type,
                AdjustmentProposal.target_key == target_key,
                AdjustmentProposal.status.in_(["Pendiente", "Aprobada", "Aplicada", "Pospuesta"]),
            )
            .order_by(AdjustmentProposal.created_at.desc())
        )

    def expire_stale_proposals(self, profile_id: int, now: datetime) -> int:
        """Expire pending or postponed proposals past their review window."""

        proposals = list(
            self.session.scalars(
                select(AdjustmentProposal).where(
                    AdjustmentProposal.profile_id == profile_id,
                    AdjustmentProposal.status.in_(["Pendiente", "Pospuesta"]),
                    AdjustmentProposal.expires_at.is_not(None),
                    AdjustmentProposal.expires_at < now,
                )
            )
        )
        for proposal in proposals:
            proposal.status = "Expirada"
        if proposals:
            self.session.flush()
        return len(proposals)

    def list_recent_runs(self, profile_id: int, limit: int = 20) -> list[LearningRun]:
        """List recent learning runs."""

        return list(
            self.session.scalars(
                select(LearningRun)
                .where(LearningRun.profile_id == profile_id)
                .order_by(LearningRun.started_at.desc())
                .limit(limit)
            )
        )

    def list_metrics(self, learning_run_id: int) -> list[LearningMetric]:
        """List metrics for one run."""

        return list(
            self.session.scalars(
                select(LearningMetric).where(LearningMetric.learning_run_id == learning_run_id).order_by(LearningMetric.metric_name)
            )
        )

    def list_proposals(self, profile_id: int, statuses: list[str] | None = None) -> list[AdjustmentProposal]:
        """List proposals for a profile."""

        statement = select(AdjustmentProposal).where(AdjustmentProposal.profile_id == profile_id).order_by(AdjustmentProposal.created_at.desc())
        if statuses:
            statement = statement.where(AdjustmentProposal.status.in_(statuses))
        return list(self.session.scalars(statement))

    def get_proposal(self, proposal_id: int) -> AdjustmentProposal:
        """Return a proposal or raise."""

        proposal = self.session.get(AdjustmentProposal, proposal_id)
        if proposal is None:
            raise ValidationError("No se encontro la propuesta de ajuste.")
        return proposal

    def update_proposal_status(
        self,
        proposal_id: int,
        status: str,
        reviewed_by: str | None = None,
        review_notes: str | None = None,
        mark_applied: bool = False,
        mark_reverted: bool = False,
    ) -> AdjustmentProposal:
        """Update proposal review or application status."""

        proposal = self.get_proposal(proposal_id)
        proposal.status = status
        if reviewed_by is not None:
            proposal.reviewed_by = reviewed_by
        if review_notes is not None:
            proposal.review_notes = review_notes.strip() or None
        if reviewed_by or review_notes:
            proposal.reviewed_at = utc_now()
        if mark_applied:
            proposal.applied_at = utc_now()
        if mark_reverted:
            proposal.reverted_at = utc_now()
        self.session.commit()
        self.session.refresh(proposal)
        return proposal

    def save_configuration_change(self, data: dict[str, Any]) -> ConfigurationChangeHistory:
        """Persist a reversible configuration change record."""

        change = ConfigurationChangeHistory(**data)
        self.session.add(change)
        self.session.commit()
        self.session.refresh(change)
        return change

    def latest_change_for_proposal(self, proposal_id: int) -> ConfigurationChangeHistory | None:
        """Return the latest configuration change for a proposal."""

        return self.session.scalar(
            select(ConfigurationChangeHistory)
            .where(ConfigurationChangeHistory.proposal_id == proposal_id)
            .order_by(ConfigurationChangeHistory.changed_at.desc())
        )

    def list_configuration_changes(self, profile_id: int, limit: int = 50) -> list[ConfigurationChangeHistory]:
        """List configuration change history for a profile."""

        return list(
            self.session.scalars(
                select(ConfigurationChangeHistory)
                .where(ConfigurationChangeHistory.profile_id == profile_id)
                .order_by(ConfigurationChangeHistory.changed_at.desc())
                .limit(limit)
            )
        )

"""Repository for strategic prioritization, decisions and daily shortlists."""

from __future__ import annotations

from datetime import UTC, date, datetime
from decimal import Decimal
from typing import Any

from sqlalchemy import func, or_, select
from sqlalchemy.orm import Session, selectinload

from app.models import (
    Application,
    ApplicationEffortOverride,
    DailyShortlist,
    DailyShortlistItem,
    Interaction,
    JobDecision,
    JobEvaluation,
    JobPriority,
    PrioritizationRun,
    SavedView,
)
from app.models.database_models import utc_now
from app.services.validation import ValidationError, require_text


class PrioritizationRepository:
    """Persist and query strategic priorities and related user decisions."""

    def __init__(self, session: Session) -> None:
        self.session = session

    def create_run(
        self,
        profile_id: int,
        prioritization_version: str,
        configuration_hash: str,
        evaluation_run_id: int | None = None,
        jobs_considered: int = 0,
    ) -> PrioritizationRun:
        """Create a prioritization run."""

        run = PrioritizationRun(
            profile_id=profile_id,
            prioritization_version=prioritization_version,
            configuration_hash=configuration_hash,
            evaluation_run_id=evaluation_run_id,
            jobs_considered=jobs_considered,
            status="Procesando",
        )
        self.session.add(run)
        self.session.flush()
        return run

    def finish_run(self, run_id: int, prioritized: int, excluded: int, failed: int, errors: list[str]) -> PrioritizationRun:
        """Mark a prioritization run as completed."""

        run = self.get_run(run_id)
        run.jobs_prioritized = prioritized
        run.jobs_excluded = excluded
        run.jobs_failed = failed
        run.error_summary = "; ".join(errors) if errors else None
        run.status = "Completado con errores" if errors else "Completado"
        run.completed_at = utc_now()
        self.session.commit()
        self.session.refresh(run)
        return run

    def fail_run(self, run_id: int, error: str) -> PrioritizationRun:
        """Mark a prioritization run as failed."""

        run = self.get_run(run_id)
        run.jobs_failed = run.jobs_considered
        run.error_summary = error
        run.status = "Fallido"
        run.completed_at = utc_now()
        self.session.commit()
        self.session.refresh(run)
        return run

    def get_run(self, run_id: int) -> PrioritizationRun:
        """Return a prioritization run or raise."""

        run = self.session.get(PrioritizationRun, run_id)
        if run is None:
            raise ValidationError("No se encontro la corrida de priorizacion.")
        return run

    def save_priority(self, data: dict[str, Any]) -> JobPriority:
        """Persist one priority record."""

        cleaned = dict(data)
        for key in [
            "priority_score",
            "urgency_score",
            "strategic_value_score",
            "actionability_score",
            "application_effort_score",
        ]:
            cleaned[key] = Decimal(str(cleaned[key]))
        priority = JobPriority(**cleaned)
        self.session.add(priority)
        self.session.flush()
        return priority

    def latest_priority(self, job_id: int, profile_id: int) -> JobPriority | None:
        """Return latest priority for one job/profile pair."""

        statement = (
            select(JobPriority)
            .options(selectinload(JobPriority.job), selectinload(JobPriority.evaluation))
            .where(JobPriority.job_id == job_id, JobPriority.profile_id == profile_id)
            .order_by(JobPriority.created_at.desc())
        )
        return self.session.scalar(statement)

    def latest_evaluation(self, job_id: int, profile_id: int) -> JobEvaluation | None:
        """Return latest evaluation for one job/profile pair."""

        statement = (
            select(JobEvaluation)
            .options(selectinload(JobEvaluation.job), selectinload(JobEvaluation.components))
            .where(JobEvaluation.job_id == job_id, JobEvaluation.profile_id == profile_id)
            .order_by(JobEvaluation.created_at.desc())
        )
        return self.session.scalar(statement)

    def list_priorities(self, filters: dict[str, Any] | None = None, limit: int = 200) -> list[JobPriority]:
        """List priorities with simple filters."""

        filters = filters or {}
        statement = (
            select(JobPriority)
            .options(selectinload(JobPriority.job), selectinload(JobPriority.evaluation))
            .order_by(JobPriority.priority_score.desc(), JobPriority.urgency_score.desc(), JobPriority.created_at.desc())
        )
        if filters.get("profile_id"):
            statement = statement.where(JobPriority.profile_id == filters["profile_id"])
        if filters.get("recommended_action"):
            statement = statement.where(JobPriority.recommended_action == filters["recommended_action"])
        if filters.get("priority_bucket"):
            statement = statement.where(JobPriority.priority_bucket == filters["priority_bucket"])
        if filters.get("is_stale") is not None:
            statement = statement.where(JobPriority.is_stale.is_(bool(filters["is_stale"])))
        if filters.get("min_priority") is not None:
            statement = statement.where(JobPriority.priority_score >= filters["min_priority"])
        return list(self.session.scalars(statement.limit(limit)))

    def mark_stale(self, priority_id: int) -> None:
        """Mark a priority as stale."""

        priority = self.session.get(JobPriority, priority_id)
        if priority:
            priority.is_stale = True
            self.session.commit()

    def latest_decision(self, job_id: int, profile_id: int) -> JobDecision | None:
        """Return latest human decision for one job/profile pair."""

        return self.session.scalar(
            select(JobDecision)
            .where(JobDecision.job_id == job_id, JobDecision.profile_id == profile_id)
            .order_by(JobDecision.decided_at.desc(), JobDecision.created_at.desc())
        )

    def list_decisions(self, profile_id: int, limit: int = 200) -> list[JobDecision]:
        """List human decisions."""

        return list(
            self.session.scalars(
                select(JobDecision)
                .options(selectinload(JobDecision.job), selectinload(JobDecision.priority))
                .where(JobDecision.profile_id == profile_id)
                .order_by(JobDecision.decided_at.desc())
                .limit(limit)
            )
        )

    def record_decision(
        self,
        job_id: int,
        profile_id: int,
        decision: str,
        priority_id: int | None = None,
        reason_code: str | None = None,
        notes: str | None = None,
        follow_up_date: date | None = None,
        decision_source: str = "Usuario",
    ) -> JobDecision:
        """Record one human decision and preserve previous history."""

        decision_row = JobDecision(
            job_id=job_id,
            profile_id=profile_id,
            priority_id=priority_id,
            decision=decision,
            reason_code=reason_code,
            notes=(notes or "").strip() or None,
            follow_up_date=follow_up_date,
            decision_source=decision_source,
        )
        self.session.add(decision_row)
        self.session.add(
            Interaction(
                job_id=job_id,
                action=decision,
                reason=reason_code,
                notes=(notes or "").strip() or None,
            )
        )
        self.session.commit()
        self.session.refresh(decision_row)
        return decision_row

    def application_exists(self, job_id: int, profile_id: int | None = None) -> bool:
        """Return whether an application already exists for a job/profile pair."""

        statement = select(Application.id).where(Application.job_id == job_id).limit(1)
        if profile_id is not None:
            statement = statement.where(or_(Application.profile_id == profile_id, Application.profile_id.is_(None)))
        return bool(self.session.scalar(statement))

    def create_application(
        self,
        job_id: int,
        profile_id: int | None = None,
        status: str = "Preparando",
        application_date: date | None = None,
        notes: str | None = None,
        allow_duplicate: bool = False,
    ) -> Application:
        """Create application tracking without duplicating unless confirmed."""

        if not allow_duplicate and self.application_exists(job_id, profile_id):
            raise ValidationError("Ya existe una postulacion registrada para esta vacante.")
        application = Application(
            job_id=job_id,
            profile_id=profile_id,
            application_date=application_date or date.today(),
            status=status,
            offer_received=False,
            notes=(notes or "").strip() or None,
        )
        self.session.add(application)
        self.session.commit()
        self.session.refresh(application)
        return application

    def create_saved_view(
        self,
        profile_id: int,
        name: str,
        filters: dict[str, Any],
        sort: dict[str, Any],
        is_default: bool = False,
    ) -> SavedView:
        """Create a saved view and keep at most one default per profile."""

        clean_name = require_text(name, "Nombre de vista")
        if is_default:
            self._clear_default_views(profile_id)
        view = SavedView(
            profile_id=profile_id,
            name=clean_name,
            filters_json=filters,
            sort_json=sort,
            is_default=is_default,
        )
        self.session.add(view)
        self.session.commit()
        self.session.refresh(view)
        return view

    def get_effort_override(self, job_id: int, profile_id: int) -> ApplicationEffortOverride | None:
        """Return manual effort override for one job/profile pair."""

        return self.session.scalar(
            select(ApplicationEffortOverride).where(
                ApplicationEffortOverride.job_id == job_id,
                ApplicationEffortOverride.profile_id == profile_id,
            )
        )

    def set_effort_override(
        self,
        job_id: int,
        profile_id: int,
        effort_level: str,
        notes: str | None = None,
    ) -> ApplicationEffortOverride:
        """Create or update a manual effort override."""

        override = self.get_effort_override(job_id, profile_id)
        if override is None:
            override = ApplicationEffortOverride(job_id=job_id, profile_id=profile_id, effort_level=effort_level)
            self.session.add(override)
        override.effort_level = effort_level
        override.notes = (notes or "").strip() or None
        self.session.commit()
        self.session.refresh(override)
        return override

    def update_saved_view(self, view_id: int, **data: Any) -> SavedView:
        """Update a saved view."""

        view = self.session.get(SavedView, view_id)
        if view is None:
            raise ValidationError("No se encontro la vista guardada.")
        if data.get("is_default") is True:
            self._clear_default_views(view.profile_id)
        for key in ["name", "filters_json", "sort_json", "is_default"]:
            if key in data:
                setattr(view, key, data[key])
        self.session.commit()
        self.session.refresh(view)
        return view

    def delete_saved_view(self, view_id: int, confirmed: bool = False) -> None:
        """Delete a saved view after confirmation."""

        if not confirmed:
            raise ValidationError("Confirma la eliminacion de la vista.")
        view = self.session.get(SavedView, view_id)
        if view:
            self.session.delete(view)
            self.session.commit()

    def list_saved_views(self, profile_id: int) -> list[SavedView]:
        """List saved views."""

        return list(self.session.scalars(select(SavedView).where(SavedView.profile_id == profile_id).order_by(SavedView.name)))

    def find_stalled_priorities(self, profile_id: int, limits: dict[str, int], today: date | None = None) -> list[dict[str, Any]]:
        """Find priorities that stayed too long without a follow-up decision."""

        current_date = today or date.today()
        priorities = self.list_priorities({"profile_id": profile_id, "is_stale": False}, limit=500)
        stalled: list[dict[str, Any]] = []
        for priority in priorities:
            latest_decision = self.latest_decision(priority.job_id, profile_id)
            age_days = (current_date - priority.created_at.date()).days
            threshold = limits["new_without_review_days"]
            state = "Nueva"
            if latest_decision:
                age_days = (current_date - latest_decision.decided_at.date()).days
                state = latest_decision.decision
                if latest_decision.decision == "Revisar":
                    threshold = limits["review_without_decision_days"]
                elif latest_decision.decision == "Preparar postulacion":
                    threshold = limits["prepare_without_application_days"]
                elif latest_decision.decision == "Guardar":
                    threshold = limits["saved_without_action_days"]
            if age_days > threshold:
                stalled.append(
                    {
                        "priority": priority,
                        "state": state,
                        "age_days": age_days,
                        "suggested_action": "Revisar decision o cerrar pendiente.",
                    }
                )
        return stalled

    def create_or_get_shortlist(self, profile_id: int, shortlist_date: date | None = None) -> DailyShortlist:
        """Create or return the daily shortlist for a date."""

        target_date = shortlist_date or date.today()
        existing = self.session.scalar(
            select(DailyShortlist).where(DailyShortlist.profile_id == profile_id, DailyShortlist.shortlist_date == target_date)
        )
        if existing:
            return existing
        shortlist = DailyShortlist(profile_id=profile_id, shortlist_date=target_date, status="Borrador")
        self.session.add(shortlist)
        self.session.commit()
        self.session.refresh(shortlist)
        return shortlist

    def add_shortlist_item(
        self,
        shortlist_id: int,
        job_id: int,
        priority_id: int | None,
        planned_action: str,
        notes: str | None = None,
    ) -> DailyShortlistItem:
        """Add a job to a daily shortlist without duplicating it."""

        existing = self.session.scalar(
            select(DailyShortlistItem).where(DailyShortlistItem.shortlist_id == shortlist_id, DailyShortlistItem.job_id == job_id)
        )
        if existing:
            raise ValidationError("La vacante ya esta en la lista diaria.")
        next_position = (self.session.scalar(select(func.max(DailyShortlistItem.position)).where(DailyShortlistItem.shortlist_id == shortlist_id)) or 0) + 1
        item = DailyShortlistItem(
            shortlist_id=shortlist_id,
            job_id=job_id,
            priority_id=priority_id,
            position=next_position,
            planned_action=planned_action,
            completion_status="Pendiente",
            notes=(notes or "").strip() or None,
        )
        self.session.add(item)
        self.session.commit()
        self.session.refresh(item)
        return item

    def list_shortlist_items(self, shortlist_id: int) -> list[DailyShortlistItem]:
        """List shortlist items."""

        return list(
            self.session.scalars(
                select(DailyShortlistItem)
                .options(selectinload(DailyShortlistItem.job), selectinload(DailyShortlistItem.priority))
                .where(DailyShortlistItem.shortlist_id == shortlist_id)
                .order_by(DailyShortlistItem.position)
            )
        )

    def update_shortlist_item(self, item_id: int, **data: Any) -> DailyShortlistItem:
        """Update one shortlist item."""

        item = self.session.get(DailyShortlistItem, item_id)
        if item is None:
            raise ValidationError("No se encontro el elemento de la lista diaria.")
        for key in ["position", "planned_action", "completion_status", "notes"]:
            if key in data:
                setattr(item, key, data[key])
        self.session.commit()
        self.session.refresh(item)
        return item

    def reorder_shortlist_item(self, item_id: int, new_position: int) -> DailyShortlistItem:
        """Move an item and swap with an existing item if needed."""

        item = self.session.get(DailyShortlistItem, item_id)
        if item is None:
            raise ValidationError("No se encontro el elemento de la lista diaria.")
        other = self.session.scalar(
            select(DailyShortlistItem).where(
                DailyShortlistItem.shortlist_id == item.shortlist_id,
                DailyShortlistItem.position == new_position,
                DailyShortlistItem.id != item.id,
            )
        )
        old_position = item.position
        if other:
            item.position = -item.id
            self.session.flush()
            other.position = old_position
            self.session.flush()
        item.position = new_position
        self.session.commit()
        self.session.refresh(item)
        return item

    def archive_shortlist(self, shortlist_id: int) -> DailyShortlist:
        """Archive a daily shortlist."""

        shortlist = self.session.get(DailyShortlist, shortlist_id)
        if shortlist is None:
            raise ValidationError("No se encontro la lista diaria.")
        shortlist.status = "Archivada"
        self.session.commit()
        self.session.refresh(shortlist)
        return shortlist

    def _clear_default_views(self, profile_id: int) -> None:
        for view in self.session.scalars(select(SavedView).where(SavedView.profile_id == profile_id, SavedView.is_default.is_(True))):
            view.is_default = False

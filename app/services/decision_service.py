"""Human decision workflow for strategic inbox items."""

from __future__ import annotations

from datetime import date
from typing import Any

from sqlalchemy.orm import Session

from app.config import load_priority_config
from app.models import JobDecision
from app.repositories import PrioritizationRepository
from app.services.feedback_service import FeedbackService
from app.services.validation import ValidationError


class DecisionService:
    """Record human decisions and update local tracking records."""

    def __init__(self, session: Session, config: dict[str, Any] | None = None) -> None:
        self.session = session
        self.config = config or load_priority_config()
        self.repo = PrioritizationRepository(session)
        self.feedback = FeedbackService(session)

    def record_decision(
        self,
        job_id: int,
        profile_id: int,
        decision: str,
        priority_id: int | None = None,
        reason_code: str | None = None,
        notes: str | None = None,
        follow_up_date: date | None = None,
        create_application: bool = False,
        allow_duplicate_application: bool = False,
    ) -> JobDecision:
        """Record a user decision without performing external actions."""

        self._validate_decision(decision)
        if follow_up_date and follow_up_date < date.today():
            raise ValidationError("La fecha de seguimiento no puede estar en el pasado.")
        should_create_application = create_application or decision in {"Postular", "Preparar postulacion"}
        if should_create_application and not allow_duplicate_application and self.repo.application_exists(job_id, profile_id):
            raise ValidationError("Ya existe una postulacion registrada para esta vacante.")
        row = self.repo.record_decision(
            job_id=job_id,
            profile_id=profile_id,
            priority_id=priority_id,
            decision=decision,
            reason_code=reason_code,
            notes=notes,
            follow_up_date=follow_up_date,
            decision_source="Usuario",
        )
        if should_create_application:
            status = "Postulada" if decision == "Postular" else "Preparando"
            self.repo.create_application(
                job_id,
                profile_id=profile_id,
                status=status,
                notes=notes,
                allow_duplicate=allow_duplicate_application,
            )
        if priority_id:
            self.repo.mark_stale(priority_id)
        if decision in {"Guardar", "Explorar", "Preparar postulacion", "Postular", "Descartar"}:
            self.feedback.record_decision_signal(
                profile_id=profile_id,
                job_id=job_id,
                decision=decision,
                reason_code=reason_code,
                priority_id=priority_id,
                occurred_at=row.decided_at,
                deduplication_key=f"decision:{row.id}:{decision}",
            )
        return row

    def _validate_decision(self, decision: str) -> None:
        if decision not in self.config["actions"]:
            raise ValidationError("Decision no permitida para la bandeja estrategica.")

"""Application outcome registration for Phase 6."""

from __future__ import annotations

from datetime import date
from typing import Any

from sqlalchemy.orm import Session

from app.config import load_feedback_learning_config
from app.models import Application
from app.repositories import FeedbackRepository
from app.services import feedback_types as types
from app.services.feedback_service import FeedbackService
from app.services.validation import ValidationError


class ApplicationOutcomeService:
    """Record real application outcomes and emit supervised feedback signals."""

    TERMINAL_OUTCOMES = {
        "Oferta aceptada",
        "Oferta rechazada",
        "Rechazo",
        "Postulacion retirada",
        "Proceso cancelado",
        "Sin respuesta",
    }
    PROGRESS_OUTCOMES = {
        "Respuesta automatica",
        "Contacto de reclutador",
        "Prueba tecnica",
        "Entrevista",
        "Segunda entrevista",
        "Entrevista final",
        "Oferta",
    }

    def __init__(self, session: Session, config: dict[str, Any] | None = None) -> None:
        self.session = session
        self.config = config or load_feedback_learning_config()
        self.repo = FeedbackRepository(session)
        self.feedback = FeedbackService(session, self.config)

    def record_outcome(
        self,
        application_id: int,
        profile_id: int,
        outcome_type: str,
        outcome_date: date,
        stage: str,
        company_response: str,
        user_assessment: str | None = None,
        salary_offered: float | None = None,
        currency: str | None = None,
        rejection_reason: str | None = None,
        notes: str | None = None,
    ) -> dict[str, Any]:
        """Persist an application outcome and register the related signal."""

        application = self.session.get(Application, application_id)
        if application is None:
            raise ValidationError("No se encontro la postulacion.")
        if application.profile_id is not None and application.profile_id != profile_id:
            raise ValidationError("La postulacion no corresponde al perfil indicado.")
        if application.profile_id is None:
            application.profile_id = profile_id
        if outcome_type not in self.config["application_outcome_types"]:
            raise ValidationError("Resultado de postulacion no permitido.")
        if outcome_date < application.application_date:
            raise ValidationError("La fecha del resultado no puede ser anterior a la postulacion.")
        self._validate_outcome_sequence(application, outcome_type)
        try:
            outcome = self.repo.create_application_outcome(
                {
                    "application_id": application_id,
                    "outcome_type": outcome_type,
                    "outcome_date": outcome_date,
                    "stage": stage.strip() or outcome_type,
                    "company_response": company_response.strip() or outcome_type,
                    "user_assessment": (user_assessment or "").strip() or None,
                    "salary_offered": salary_offered,
                    "currency": (currency or "").strip() or None,
                    "rejection_reason": (rejection_reason or "").strip() or None,
                    "notes": (notes or "").strip() or None,
                }
            )
            event_type = types.OUTCOME_EVENT_TYPES[outcome_type]
            event_result = self.feedback.register_event(
                profile_id=profile_id,
                job_id=application.job_id,
                application_id=application_id,
                event_type=event_type,
                event_category=types.EVENT_CATEGORY_OUTCOME,
                source=types.EVENT_SOURCE_USER,
                occurred_at=date_to_datetime(outcome_date),
                reason_code=rejection_reason,
                notes=notes,
                deduplication_key=f"outcome:{outcome.id}:{event_type}",
                metadata_json={"outcome_id": outcome.id, "stage": stage},
                commit=False,
            )
            self._sync_application_summary(application, outcome_type, outcome_date)
            self.session.commit()
            self.session.refresh(outcome)
            self.session.refresh(event_result["event"])
            self.session.refresh(application)
            return {"outcome": outcome, "feedback_event": event_result["event"], "event_inserted": event_result["inserted"]}
        except Exception:
            self.session.rollback()
            raise

    def _sync_application_summary(self, application: Application, outcome_type: str, outcome_date: date) -> None:
        if outcome_type in {"Respuesta automatica", "Contacto de reclutador"}:
            application.response_date = outcome_date
            application.status = "En revision"
        elif outcome_type in {"Entrevista", "Segunda entrevista", "Entrevista final"}:
            application.response_date = application.response_date or outcome_date
            application.interview_date = outcome_date
            application.status = outcome_type
        elif outcome_type in {"Oferta", "Oferta aceptada", "Oferta rechazada"}:
            application.response_date = application.response_date or outcome_date
            application.offer_received = True
            application.status = outcome_type
        elif outcome_type == "Rechazo":
            application.response_date = application.response_date or outcome_date
            application.status = "Rechazada"
        elif outcome_type == "Sin respuesta":
            application.status = "Cerrada sin respuesta"
        elif outcome_type == "Postulacion retirada":
            application.status = "Retirada"
    def _validate_outcome_sequence(self, application: Application, outcome_type: str) -> None:
        existing_types = {outcome.outcome_type for outcome in application.outcomes}
        existing_terminal = existing_types & self.TERMINAL_OUTCOMES
        if existing_terminal and outcome_type not in existing_terminal:
            raise ValidationError("La postulacion ya tiene un resultado terminal registrado.")
        if outcome_type in self.TERMINAL_OUTCOMES and existing_terminal and outcome_type not in existing_terminal:
            raise ValidationError("No se puede registrar un resultado contradictorio para la misma postulacion.")
        if outcome_type == "Sin respuesta" and existing_types & self.PROGRESS_OUTCOMES:
            raise ValidationError("No se puede registrar 'Sin respuesta' despues de avances del proceso.")
        if outcome_type in {"Rechazo", "Postulacion retirada", "Proceso cancelado"} and "Oferta aceptada" in existing_types:
            raise ValidationError("No se puede registrar un resultado negativo despues de una oferta aceptada.")


def date_to_datetime(value: date):
    """Convert a date to a naive datetime at midnight."""

    from datetime import datetime, time

    return datetime.combine(value, time.min)

"""Controlled feedback event registration."""

from __future__ import annotations

from datetime import datetime
from decimal import Decimal
import hashlib
import json
from typing import Any

from sqlalchemy.orm import Session

from app.config import load_feedback_learning_config
from app.models import Application, Job, JobEvaluation, JobPriority, ProfessionalProfile
from app.repositories import FeedbackRepository
from app.services import feedback_types as types
from app.services.validation import ValidationError


class FeedbackService:
    """Register explicit and implicit signals without invasive tracking."""

    def __init__(self, session: Session, config: dict[str, Any] | None = None) -> None:
        self.session = session
        self.config = config or load_feedback_learning_config()
        self.repo = FeedbackRepository(session)

    def register_event(
        self,
        profile_id: int,
        job_id: int,
        event_type: str,
        event_category: str,
        source: str,
        signal_value: float | None = None,
        evaluation_id: int | None = None,
        priority_id: int | None = None,
        application_id: int | None = None,
        reason_code: str | None = None,
        notes: str | None = None,
        occurred_at: datetime | None = None,
        deduplication_key: str | None = None,
        metadata_json: dict[str, Any] | None = None,
        commit: bool = True,
    ):
        """Validate and persist a deduplicated feedback event."""

        self._validate_references(profile_id, job_id, evaluation_id, priority_id, application_id)
        self._validate_catalog(event_category, self.config["event_categories"], "categoria de evento")
        self._validate_catalog(source, self.config["event_sources"], "fuente de evento")
        value = self._signal_value(event_type, event_category, signal_value)
        occurred = occurred_at or datetime.now()
        key = deduplication_key or self._default_deduplication_key(
            profile_id,
            job_id,
            event_type,
            event_category,
            source,
            reason_code,
            occurred,
        )
        event, inserted = self.repo.create_feedback_event(
            {
                "profile_id": profile_id,
                "job_id": job_id,
                "evaluation_id": evaluation_id,
                "priority_id": priority_id,
                "application_id": application_id,
                "event_type": event_type,
                "event_category": event_category,
                "signal_value": value,
                "reason_code": (reason_code or "").strip() or None,
                "notes": (notes or "").strip() or None,
                "source": source,
                "occurred_at": occurred,
                "deduplication_key": key,
                "metadata_json": metadata_json,
            }
        )
        if commit:
            self.session.commit()
            self.session.refresh(event)
        return {"event": event, "inserted": inserted}

    def record_viewed_detail(self, profile_id: int, job_id: int) -> dict[str, Any]:
        """Register a low-weight detail view signal."""

        return self.register_event(
            profile_id=profile_id,
            job_id=job_id,
            event_type="viewed_detail",
            event_category=types.EVENT_CATEGORY_IMPLICIT,
            source=types.EVENT_SOURCE_INTERFACE,
        )

    def record_decision_signal(
        self,
        profile_id: int,
        job_id: int,
        decision: str,
        reason_code: str | None = None,
        priority_id: int | None = None,
        occurred_at: datetime | None = None,
        deduplication_key: str | None = None,
    ) -> dict[str, Any]:
        """Register a feedback signal for a human decision without duplicating the decision."""

        event_type = {
            "Guardar": "saved",
            "Explorar": "explored",
            "Preparar postulacion": "prepared_application",
            "Postular": "applied",
            "Descartar": "discarded",
        }.get(decision)
        if event_type is None:
            raise ValidationError("La decision no tiene una senal de aprendizaje asociada.")
        return self.register_event(
            profile_id=profile_id,
            job_id=job_id,
            event_type=event_type,
            event_category=types.EVENT_CATEGORY_EXPLICIT,
            source=types.EVENT_SOURCE_USER,
            priority_id=priority_id,
            reason_code=reason_code,
            occurred_at=occurred_at,
            deduplication_key=deduplication_key,
        )

    def _signal_value(self, event_type: str, event_category: str, explicit_value: float | None) -> Decimal:
        if explicit_value is not None:
            value = float(explicit_value)
        else:
            group = {
                types.EVENT_CATEGORY_IMPLICIT: "implicit",
                types.EVENT_CATEGORY_EXPLICIT: "explicit",
                types.EVENT_CATEGORY_OUTCOME: "outcomes",
                types.EVENT_CATEGORY_CORRECTION: "corrections",
                types.EVENT_CATEGORY_PREFERENCE: "preferences",
            }.get(event_category)
            if group is None:
                raise ValidationError("Categoria de evento no permitida.")
            try:
                value = float(self.config["feedback_signal_weights"][group][event_type])
            except KeyError as exc:
                raise ValidationError("Tipo de evento no configurado para aprendizaje.") from exc
        lower = float(self.config["signal_value_limits"]["minimum"])
        upper = float(self.config["signal_value_limits"]["maximum"])
        if value < lower or value > upper:
            raise ValidationError("El valor de senal esta fuera de los limites configurados.")
        return Decimal(str(value))

    def _validate_references(
        self,
        profile_id: int,
        job_id: int,
        evaluation_id: int | None,
        priority_id: int | None,
        application_id: int | None,
    ) -> None:
        if self.session.get(ProfessionalProfile, profile_id) is None:
            raise ValidationError("No se encontro el perfil profesional.")
        if self.session.get(Job, job_id) is None:
            raise ValidationError("No se encontro la vacante.")
        if evaluation_id is not None:
            evaluation = self.session.get(JobEvaluation, evaluation_id)
            if evaluation is None:
                raise ValidationError("No se encontro la evaluacion.")
            if evaluation.profile_id != profile_id or evaluation.job_id != job_id:
                raise ValidationError("La evaluacion no corresponde al perfil y vacante indicados.")
        if priority_id is not None:
            priority = self.session.get(JobPriority, priority_id)
            if priority is None:
                raise ValidationError("No se encontro la prioridad.")
            if priority.profile_id != profile_id or priority.job_id != job_id:
                raise ValidationError("La prioridad no corresponde al perfil y vacante indicados.")
        if application_id is not None:
            application = self.session.get(Application, application_id)
            if application is None:
                raise ValidationError("No se encontro la postulacion.")
            if application.job_id != job_id or (application.profile_id is not None and application.profile_id != profile_id):
                raise ValidationError("La postulacion no corresponde al perfil y vacante indicados.")

    def _validate_catalog(self, value: str, allowed: list[str], label: str) -> None:
        if value not in allowed:
            raise ValidationError(f"{label.capitalize()} no permitida.")

    def _deduplication_key(self, data: dict[str, Any]) -> str:
        payload = json.dumps(data, sort_keys=True, ensure_ascii=False, default=str)
        return hashlib.sha256(payload.encode("utf-8")).hexdigest()

    def _default_deduplication_key(
        self,
        profile_id: int,
        job_id: int,
        event_type: str,
        event_category: str,
        source: str,
        reason_code: str | None,
        occurred: datetime,
    ) -> str:
        payload: dict[str, Any] = {
            "profile_id": profile_id,
            "job_id": job_id,
            "event_type": event_type,
            "event_category": event_category,
            "source": source,
            "reason_code": reason_code,
        }
        if event_category == types.EVENT_CATEGORY_IMPLICIT:
            payload["occurred_on"] = occurred.date().isoformat()
        else:
            payload["occurred_at"] = occurred.isoformat(timespec="seconds")
        return self._deduplication_key(payload)

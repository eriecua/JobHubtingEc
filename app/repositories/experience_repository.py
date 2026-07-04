"""Repository for work experience records."""

from __future__ import annotations

from datetime import date
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import WorkExperience
from app.services.validation import (
    ValidationError,
    require_text,
    validate_date_order,
    validate_non_negative,
)
from app.utils.normalization import normalize_text


class ExperienceRepository:
    """CRUD operations for work experiences."""

    def __init__(self, session: Session) -> None:
        self.session = session

    def list_experiences(self, profile_id: int) -> list[WorkExperience]:
        """List experiences for a profile."""

        return list(
            self.session.scalars(
                select(WorkExperience)
                .where(WorkExperience.profile_id == profile_id)
                .order_by(WorkExperience.start_date.desc())
            )
        )

    def create_experience(self, profile_id: int, **data: Any) -> WorkExperience:
        """Create a validated work experience."""

        cleaned = self._clean_data(data)
        experience = WorkExperience(profile_id=profile_id, **cleaned)
        self.session.add(experience)
        self.session.commit()
        self.session.refresh(experience)
        return experience

    def update_experience(self, experience_id: int, **data: Any) -> WorkExperience:
        """Update a work experience."""

        experience = self.session.get(WorkExperience, experience_id)
        if experience is None:
            raise ValidationError("No se encontro la experiencia indicada.")
        cleaned = self._clean_data(data, partial=True)
        start_date = cleaned.get("start_date", experience.start_date)
        end_date = cleaned.get("end_date", experience.end_date)
        is_current = cleaned.get("is_current", experience.is_current)
        self._validate_dates(start_date, end_date, is_current)
        if is_current:
            cleaned["end_date"] = None
        for key, value in cleaned.items():
            setattr(experience, key, value)
        self.session.commit()
        self.session.refresh(experience)
        return experience

    def delete_experience(self, experience_id: int, confirmed: bool = False) -> None:
        """Delete an experience only after explicit confirmation."""

        if not confirmed:
            raise ValidationError("Confirma la eliminacion antes de continuar.")
        experience = self.session.get(WorkExperience, experience_id)
        if experience is None:
            return
        self.session.delete(experience)
        self.session.commit()

    def _clean_data(self, data: dict[str, Any], partial: bool = False) -> dict[str, Any]:
        fields = dict(data)
        if not partial:
            for field in ["company", "job_title", "start_date"]:
                if field == "start_date" and not fields.get(field):
                    raise ValidationError("La fecha inicial es obligatoria.")
                if field != "start_date":
                    fields[field] = require_text(fields.get(field), field)
        for field in ["company", "job_title"]:
            if field in fields and fields[field] is not None:
                fields[field] = require_text(fields.get(field), field)
        if "job_title" in fields and fields["job_title"]:
            fields["normalized_job_title"] = normalize_text(fields["job_title"])
        start_date = fields.get("start_date")
        end_date = fields.get("end_date")
        if isinstance(start_date, date) or isinstance(end_date, date):
            validate_date_order(start_date, end_date)
        if not partial:
            self._validate_dates(start_date, end_date, fields.get("is_current", False))
        if fields.get("is_current") is True:
            fields["end_date"] = None
        if fields.get("people_managed") is not None:
            validate_non_negative(fields["people_managed"], "Personas gestionadas")
        return fields

    def _validate_dates(
        self,
        start_date: date | None,
        end_date: date | None,
        is_current: bool | None,
    ) -> None:
        """Validate current and past experience date rules."""

        if not is_current and end_date is None:
            raise ValidationError("La fecha final es obligatoria para experiencias pasadas.")
        validate_date_order(start_date, end_date)

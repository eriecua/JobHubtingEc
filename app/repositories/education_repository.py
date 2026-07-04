"""Repositories for education and certification records."""

from __future__ import annotations

from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import Certification, EducationRecord
from app.services.validation import (
    ValidationError,
    require_text,
    validate_catalog_value,
    validate_date_order,
    validate_optional_url,
)


class EducationRepository:
    """CRUD operations for education records."""

    def __init__(self, session: Session) -> None:
        self.session = session

    def list_records(self, profile_id: int) -> list[EducationRecord]:
        """List education records for a profile."""

        return list(self.session.scalars(select(EducationRecord).where(EducationRecord.profile_id == profile_id)))

    def create(self, profile_id: int, **data: Any) -> EducationRecord:
        """Create an education record."""

        cleaned = self._clean(data)
        record = EducationRecord(profile_id=profile_id, **cleaned)
        self.session.add(record)
        self.session.commit()
        self.session.refresh(record)
        return record

    def update(self, record_id: int, **data: Any) -> EducationRecord:
        """Update an education record."""

        record = self.session.get(EducationRecord, record_id)
        if record is None:
            raise ValidationError("No se encontro el registro academico.")
        cleaned = self._clean(data, partial=True)
        validate_date_order(
            cleaned.get("start_date", record.start_date),
            cleaned.get("end_date", record.end_date),
        )
        for key, value in cleaned.items():
            setattr(record, key, value)
        self.session.commit()
        self.session.refresh(record)
        return record

    def delete(self, record_id: int, confirmed: bool = False) -> None:
        """Delete an education record after confirmation."""

        if not confirmed:
            raise ValidationError("Confirma la eliminacion antes de continuar.")
        record = self.session.get(EducationRecord, record_id)
        if record:
            self.session.delete(record)
            self.session.commit()

    def _clean(self, data: dict[str, Any], partial: bool = False) -> dict[str, Any]:
        fields = dict(data)
        if not partial:
            for field in ["degree", "field_of_study", "education_level", "status"]:
                fields[field] = require_text(fields.get(field), field)
        for field in ["degree", "field_of_study", "education_level"]:
            if field in fields and fields[field] is not None:
                fields[field] = require_text(fields.get(field), field)
        if not partial or "status" in fields:
            fields["status"] = validate_catalog_value(fields.get("status"), "education_statuses", "Estado")
        validate_date_order(fields.get("start_date"), fields.get("end_date"))
        return fields


class CertificationRepository:
    """CRUD operations for certifications."""

    def __init__(self, session: Session) -> None:
        self.session = session

    def list_records(self, profile_id: int) -> list[Certification]:
        """List certifications for a profile."""

        return list(self.session.scalars(select(Certification).where(Certification.profile_id == profile_id)))

    def create(self, profile_id: int, **data: Any) -> Certification:
        """Create a certification."""

        cleaned = self._clean(data)
        record = Certification(profile_id=profile_id, **cleaned)
        self.session.add(record)
        self.session.commit()
        self.session.refresh(record)
        return record

    def update(self, record_id: int, **data: Any) -> Certification:
        """Update a certification."""

        record = self.session.get(Certification, record_id)
        if record is None:
            raise ValidationError("No se encontro la certificacion.")
        cleaned = self._clean(data, partial=True)
        issue_date = cleaned.get("issue_date", record.issue_date)
        expiration_date = cleaned.get("expiration_date", record.expiration_date)
        does_not_expire = cleaned.get("does_not_expire", record.does_not_expire)
        if does_not_expire:
            expiration_date = None
            cleaned["expiration_date"] = None
        validate_date_order(issue_date, expiration_date, "Fecha de expiracion")
        for key, value in cleaned.items():
            setattr(record, key, value)
        self.session.commit()
        self.session.refresh(record)
        return record

    def delete(self, record_id: int, confirmed: bool = False) -> None:
        """Delete a certification after confirmation."""

        if not confirmed:
            raise ValidationError("Confirma la eliminacion antes de continuar.")
        record = self.session.get(Certification, record_id)
        if record:
            self.session.delete(record)
            self.session.commit()

    def _clean(self, data: dict[str, Any], partial: bool = False) -> dict[str, Any]:
        fields = dict(data)
        if not partial:
            for field in ["name", "issuing_organization"]:
                fields[field] = require_text(fields.get(field), field)
        for field in ["name", "issuing_organization"]:
            if field in fields and fields[field] is not None:
                fields[field] = require_text(fields.get(field), field)
        if "credential_url" in fields:
            fields["credential_url"] = validate_optional_url(fields.get("credential_url"), "URL de credencial")
        if fields.get("does_not_expire") is True:
            fields["expiration_date"] = None
        validate_date_order(fields.get("issue_date"), fields.get("expiration_date"), "Fecha de expiracion")
        return fields

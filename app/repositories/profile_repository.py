"""Repository for professional profile records."""

from __future__ import annotations

from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import ProfessionalProfile
from app.services.validation import ValidationError, require_text, validate_non_negative, validate_optional_url


class ProfileRepository:
    """Data access and validation for the main professional profile."""

    def __init__(self, session: Session) -> None:
        self.session = session

    def get_main_profile(self) -> ProfessionalProfile | None:
        """Return the active primary profile, if it exists."""

        return self.session.scalar(
            select(ProfessionalProfile).where(
                ProfessionalProfile.is_primary.is_(True),
                ProfessionalProfile.is_active.is_(True),
            )
        )

    def exists_profile(self) -> bool:
        """Return whether an active primary profile exists."""

        return self.get_main_profile() is not None

    def create_profile(self, **data: Any) -> ProfessionalProfile:
        """Create the only active primary profile allowed in this phase."""

        if self.exists_profile():
            raise ValidationError("Ya existe un perfil principal activo.")
        cleaned = self._clean_profile_data(data)
        profile = ProfessionalProfile(**cleaned)
        self.session.add(profile)
        self.session.commit()
        self.session.refresh(profile)
        return profile

    def update_profile(self, profile_id: int, **data: Any) -> ProfessionalProfile:
        """Update the main profile."""

        profile = self.session.get(ProfessionalProfile, profile_id)
        if profile is None:
            raise ValidationError("No se encontro el perfil indicado.")
        cleaned = self._clean_profile_data(data, partial=True)
        for key, value in cleaned.items():
            setattr(profile, key, value)
        self.session.commit()
        self.session.refresh(profile)
        return profile

    def get_completeness_summary(self) -> dict[str, Any]:
        """Return profile completeness as a serializable dictionary."""

        from app.services.profile_completeness import ProfileCompletenessService

        profile = self.get_main_profile()
        return ProfileCompletenessService(self.session).calculate(profile).model_dump()

    def _clean_profile_data(self, data: dict[str, Any], partial: bool = False) -> dict[str, Any]:
        fields = dict(data)
        required = ["full_name", "professional_title", "country"]
        if not partial:
            for field in required:
                fields[field] = require_text(fields.get(field), field)
        for field in required:
            if field in fields and fields[field] is not None:
                fields[field] = require_text(fields.get(field), field)
        for field in ["professional_summary", "current_city", "current_province"]:
            if field in fields and fields[field] is not None:
                fields[field] = str(fields[field]).strip()
        if "years_total_experience" in fields:
            validate_non_negative(fields["years_total_experience"], "Anios de experiencia")
        if "linkedin_url" in fields:
            fields["linkedin_url"] = validate_optional_url(fields.get("linkedin_url"), "LinkedIn")
        if "portfolio_url" in fields:
            fields["portfolio_url"] = validate_optional_url(fields.get("portfolio_url"), "Portafolio")
        return fields

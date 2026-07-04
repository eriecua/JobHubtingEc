"""Repository for reusable CSV mapping profiles."""

from __future__ import annotations

from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import CSVMappingProfile
from app.services.validation import ValidationError


class CSVMappingProfileRepository:
    """Persist and retrieve CSV mapping profiles without storing file content."""

    def __init__(self, session: Session) -> None:
        self.session = session

    def list_profiles(self) -> list[CSVMappingProfile]:
        """Return saved mapping profiles ordered by source name."""

        statement = select(CSVMappingProfile).order_by(CSVMappingProfile.source_name)
        return list(self.session.scalars(statement))

    def get_by_source(self, source_name: str) -> CSVMappingProfile | None:
        """Return a profile by source name when it exists."""

        cleaned = self._clean_source(source_name)
        statement = select(CSVMappingProfile).where(CSVMappingProfile.source_name == cleaned)
        return self.session.scalar(statement)

    def get_profile(self, profile_id: int) -> CSVMappingProfile:
        """Return a profile by id or raise."""

        profile = self.session.get(CSVMappingProfile, profile_id)
        if profile is None:
            raise ValidationError("No se encontro el perfil de mapeo.")
        return profile

    def save_profile(
        self,
        source_name: str,
        mapping: dict[str, str],
        notes: str | None = None,
    ) -> CSVMappingProfile:
        """Create or update a mapping profile for a source."""

        cleaned = self._clean_source(source_name)
        profile = self.get_by_source(cleaned)
        if profile is None:
            profile = CSVMappingProfile(source_name=cleaned, mapping=mapping, notes=notes)
            self.session.add(profile)
        else:
            profile.mapping = mapping
            profile.notes = notes
        self.session.commit()
        self.session.refresh(profile)
        return profile

    def delete_profile(self, profile_id: int) -> None:
        """Delete a mapping profile after UI-level confirmation."""

        profile = self.session.get(CSVMappingProfile, profile_id)
        if profile is None:
            raise ValidationError("No se encontro el perfil de mapeo.")
        self.session.delete(profile)
        self.session.commit()

    def _clean_source(self, source_name: str) -> str:
        cleaned = source_name.strip()
        if not cleaned:
            raise ValidationError("El nombre de la fuente es obligatorio para guardar el perfil.")
        return cleaned

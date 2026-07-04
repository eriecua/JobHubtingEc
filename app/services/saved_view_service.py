"""Saved view workflow for the strategic inbox."""

from __future__ import annotations

from typing import Any

from sqlalchemy.orm import Session

from app.config import load_priority_config
from app.models import SavedView
from app.repositories import PrioritizationRepository
from app.services.validation import ValidationError


class SavedViewService:
    """Persist reusable filters and sort preferences."""

    def __init__(self, session: Session) -> None:
        self.repo = PrioritizationRepository(session)
        self.config = load_priority_config()

    def create(self, profile_id: int, name: str, filters: dict[str, Any], sort: dict[str, Any], is_default: bool = False) -> SavedView:
        """Create a saved view."""

        self._validate(filters, sort)
        return self.repo.create_saved_view(profile_id, name, filters, sort, is_default)

    def rename(self, view_id: int, name: str) -> SavedView:
        """Rename a saved view."""

        return self.repo.update_saved_view(view_id, name=name)

    def set_default(self, view_id: int) -> SavedView:
        """Set one saved view as default for its profile."""

        return self.repo.update_saved_view(view_id, is_default=True)

    def delete(self, view_id: int, confirmed: bool = False) -> None:
        """Delete a saved view after confirmation."""

        self.repo.delete_saved_view(view_id, confirmed)

    def _validate(self, filters: dict[str, Any], sort: dict[str, Any]) -> None:
        allowed_filters = set(self.config["saved_view_filters"])
        invalid_filters = [key for key, value in filters.items() if value is not None and key not in allowed_filters]
        if invalid_filters:
            raise ValidationError(f"Filtros no permitidos para vista guardada: {', '.join(invalid_filters)}.")
        if sort:
            field = sort.get("field")
            direction = sort.get("direction", "desc")
            if field not in set(self.config["saved_view_sort_fields"]):
                raise ValidationError("Campo de ordenamiento no permitido para vista guardada.")
            if direction not in {"asc", "desc"}:
                raise ValidationError("Direccion de ordenamiento no permitida.")

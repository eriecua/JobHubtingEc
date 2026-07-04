"""Daily shortlist workflow for strategic job search execution."""

from __future__ import annotations

from datetime import date
from typing import Any

from sqlalchemy.orm import Session

from app.config import load_priority_config
from app.models import DailyShortlist, DailyShortlistItem
from app.repositories import PrioritizationRepository
from app.services.validation import ValidationError


class ShortlistService:
    """Create and manage local daily work lists."""

    def __init__(self, session: Session, config: dict[str, Any] | None = None) -> None:
        self.session = session
        self.config = config or load_priority_config()
        self.repo = PrioritizationRepository(session)

    def create_for_date(self, profile_id: int, shortlist_date: date | None = None) -> DailyShortlist:
        """Create or return a daily shortlist."""

        return self.repo.create_or_get_shortlist(profile_id, shortlist_date)

    def add_job(
        self,
        shortlist_id: int,
        job_id: int,
        priority_id: int | None,
        planned_action: str,
        notes: str | None = None,
    ) -> DailyShortlistItem:
        """Add a job to the shortlist."""

        if planned_action not in self.config["actions"]:
            raise ValidationError("Accion planificada no permitida.")
        return self.repo.add_shortlist_item(shortlist_id, job_id, priority_id, planned_action, notes)

    def reorder(self, item_id: int, new_position: int) -> DailyShortlistItem:
        """Move an item to a new positive position."""

        if new_position <= 0:
            raise ValidationError("La posicion debe ser positiva.")
        return self.repo.reorder_shortlist_item(item_id, new_position)

    def complete(self, item_id: int, status: str = "Completada", notes: str | None = None) -> DailyShortlistItem:
        """Update completion status for one shortlist item."""

        if status not in self.config["shortlist_item_statuses"]:
            raise ValidationError("Estado de elemento no permitido.")
        data: dict[str, Any] = {"completion_status": status}
        if notes is not None:
            data["notes"] = notes
        return self.repo.update_shortlist_item(item_id, **data)

    def archive(self, shortlist_id: int) -> DailyShortlist:
        """Archive a daily shortlist."""

        return self.repo.archive_shortlist(shortlist_id)

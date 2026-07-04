"""Repository for tools and profile tool assignments."""

from __future__ import annotations

from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.config import load_profile_catalogs
from app.models import ProfileTool, Tool
from app.services.validation import (
    ValidationError,
    require_text,
    validate_catalog_value,
    validate_non_negative,
)
from app.utils.normalization import canonical_name


class ToolRepository:
    """Operations for normalized tools and assignments."""

    def __init__(self, session: Session) -> None:
        self.session = session
        self.catalogs = load_profile_catalogs()

    def create_or_get_tool(self, name: str, category: str = "Otro") -> Tool:
        """Create a tool or return an equivalent normalized record."""

        cleaned_name = require_text(name, "Herramienta")
        category = validate_catalog_value(category, "tool_categories", "Categoria")
        normalized = canonical_name(cleaned_name, self.catalogs.get("tool_aliases", {}))
        existing = self.session.scalar(select(Tool).where(Tool.normalized_name == normalized))
        if existing:
            return existing
        tool = Tool(name=cleaned_name, category=category, normalized_name=normalized)
        self.session.add(tool)
        self.session.commit()
        self.session.refresh(tool)
        return tool

    def list_tools(self) -> list[Tool]:
        """List tools."""

        return list(self.session.scalars(select(Tool).order_by(Tool.name)))

    def assign_tool(self, profile_id: int, tool_id: int, **data: Any) -> ProfileTool:
        """Assign a tool to a profile."""

        existing = self.session.scalar(
            select(ProfileTool).where(
                ProfileTool.profile_id == profile_id,
                ProfileTool.tool_id == tool_id,
            )
        )
        if existing:
            raise ValidationError("La herramienta ya esta asignada a este perfil.")
        level = validate_catalog_value(data.get("level"), "skill_levels", "Nivel")
        years = data.get("years_experience")
        if years is not None:
            validate_non_negative(years, "Anios de experiencia")
        assignment = ProfileTool(
            profile_id=profile_id,
            tool_id=tool_id,
            level=level,
            years_experience=years,
            notes=(data.get("notes") or "").strip() or None,
        )
        self.session.add(assignment)
        self.session.commit()
        self.session.refresh(assignment)
        return assignment

    def list_profile_tools(self, profile_id: int) -> list[ProfileTool]:
        """List assigned tools for a profile."""

        return list(
            self.session.scalars(
                select(ProfileTool)
                .where(ProfileTool.profile_id == profile_id)
                .join(ProfileTool.tool)
                .order_by(Tool.name)
            )
        )

    def update_level(self, profile_tool_id: int, **data: Any) -> ProfileTool:
        """Update an assigned tool."""

        assignment = self.session.get(ProfileTool, profile_tool_id)
        if assignment is None:
            raise ValidationError("No se encontro la herramienta asignada.")
        if "level" in data:
            assignment.level = validate_catalog_value(data.get("level"), "skill_levels", "Nivel")
        if "years_experience" in data:
            validate_non_negative(data.get("years_experience"), "Anios de experiencia")
            assignment.years_experience = data.get("years_experience")
        if "notes" in data:
            assignment.notes = (data.get("notes") or "").strip() or None
        self.session.commit()
        self.session.refresh(assignment)
        return assignment

    def delete_assignment(self, profile_tool_id: int, confirmed: bool = False) -> None:
        """Delete a tool assignment after confirmation."""

        if not confirmed:
            raise ValidationError("Confirma la eliminacion antes de continuar.")
        assignment = self.session.get(ProfileTool, profile_tool_id)
        if assignment:
            self.session.delete(assignment)
            self.session.commit()

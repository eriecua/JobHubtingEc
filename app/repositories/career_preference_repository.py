"""Repository for target roles, sectors, preferences, constraints and goals."""

from __future__ import annotations

from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import GrowthGoal, JobConstraint, JobPreference, TargetRole, TargetSector
from app.services.validation import (
    ValidationError,
    require_text,
    validate_catalog_value,
    validate_non_negative,
    validate_percentage,
)
from app.utils.normalization import normalize_text


class CareerPreferenceRepository:
    """Manage career preferences and mandatory constraints."""

    def __init__(self, session: Session) -> None:
        self.session = session

    def add_target_role(self, profile_id: int, **data: Any) -> TargetRole:
        """Create a target role."""

        role_name = require_text(data.get("role_name"), "Cargo objetivo")
        priority = validate_catalog_value(data.get("priority"), "priorities", "Prioridad")
        salary = data.get("minimum_salary")
        if salary is not None:
            validate_non_negative(salary, "Salario minimo")
        role = TargetRole(
            profile_id=profile_id,
            role_name=role_name,
            normalized_role_name=normalize_text(role_name),
            priority=priority,
            desired_level=(data.get("desired_level") or "").strip() or None,
            minimum_salary=salary,
            currency=data.get("currency") or "USD",
            is_active=data.get("is_active", True),
            notes=(data.get("notes") or "").strip() or None,
        )
        self.session.add(role)
        self.session.commit()
        self.session.refresh(role)
        return role

    def list_target_roles(self, profile_id: int) -> list[TargetRole]:
        """List target roles."""

        return list(self.session.scalars(select(TargetRole).where(TargetRole.profile_id == profile_id)))

    def add_target_sector(self, profile_id: int, **data: Any) -> TargetSector:
        """Create a target sector."""

        sector_name = require_text(data.get("sector_name"), "Sector")
        priority = validate_catalog_value(data.get("priority"), "priorities", "Prioridad")
        sector = TargetSector(
            profile_id=profile_id,
            sector_name=sector_name,
            priority=priority,
            is_active=data.get("is_active", True),
            notes=(data.get("notes") or "").strip() or None,
        )
        self.session.add(sector)
        self.session.commit()
        self.session.refresh(sector)
        return sector

    def list_target_sectors(self, profile_id: int) -> list[TargetSector]:
        """List target sectors."""

        return list(self.session.scalars(select(TargetSector).where(TargetSector.profile_id == profile_id)))

    def set_preferences(self, profile_id: int, **data: Any) -> JobPreference:
        """Create or replace the current preference record for a profile."""

        min_salary = data.get("minimum_salary")
        expected_salary = data.get("expected_salary")
        commute = data.get("maximum_commute_minutes")
        for value, label in [
            (min_salary, "Salario minimo"),
            (expected_salary, "Salario esperado"),
            (commute, "Tiempo maximo de traslado"),
        ]:
            if value is not None:
                validate_non_negative(value, label)
        existing = self.session.scalar(select(JobPreference).where(JobPreference.profile_id == profile_id))
        if existing is None:
            existing = JobPreference(profile_id=profile_id)
            self.session.add(existing)
        for key in [
            "preferred_cities",
            "preferred_provinces",
            "accepted_modalities",
            "minimum_salary",
            "expected_salary",
            "currency",
            "accepts_shift_work",
            "accepts_weekend_work",
            "accepts_temporary_contract",
            "maximum_commute_minutes",
            "company_size_preference",
            "notes",
        ]:
            if key in data:
                setattr(existing, key, data[key])
        self.session.commit()
        self.session.refresh(existing)
        return existing

    def get_preferences(self, profile_id: int) -> JobPreference | None:
        """Return current job preferences."""

        return self.session.scalar(select(JobPreference).where(JobPreference.profile_id == profile_id))

    def add_constraint(self, profile_id: int, **data: Any) -> JobConstraint:
        """Create a mandatory job constraint."""

        constraint = JobConstraint(
            profile_id=profile_id,
            constraint_type=validate_catalog_value(data.get("constraint_type"), "constraint_types", "Tipo"),
            operator=validate_catalog_value(data.get("operator"), "constraint_operators", "Operador"),
            value=require_text(data.get("value"), "Valor"),
            is_active=data.get("is_active", True),
            reason=(data.get("reason") or "").strip() or None,
        )
        self.session.add(constraint)
        self.session.commit()
        self.session.refresh(constraint)
        return constraint

    def list_constraints(self, profile_id: int) -> list[JobConstraint]:
        """List constraints."""

        return list(self.session.scalars(select(JobConstraint).where(JobConstraint.profile_id == profile_id)))

    def detect_basic_contradictions(self, profile_id: int) -> list[str]:
        """Detect simple preference/constraint contradictions."""

        preferences = self.get_preferences(profile_id)
        constraints = self.list_constraints(profile_id)
        if preferences is None:
            return []
        accepted_modalities = {normalize_text(value) for value in preferences.accepted_modalities}
        preferred_cities = {normalize_text(value) for value in preferences.preferred_cities}
        issues: list[str] = []
        for constraint in constraints:
            value = normalize_text(constraint.value)
            if constraint.is_active and constraint.constraint_type == "Modalidad excluida" and value in accepted_modalities:
                issues.append(f"Modalidad preferida y excluida: {constraint.value}")
            if constraint.is_active and constraint.constraint_type == "Ciudad excluida" and value in preferred_cities:
                issues.append(f"Ciudad preferida y excluida: {constraint.value}")
        return issues

    def add_growth_goal(self, profile_id: int, **data: Any) -> GrowthGoal:
        """Create a growth goal."""

        progress = int(data.get("progress_percentage", 0))
        validate_percentage(progress, "Progreso")
        goal = GrowthGoal(
            profile_id=profile_id,
            title=require_text(data.get("title"), "Objetivo"),
            description=require_text(data.get("description"), "Descripcion"),
            target_skill_id=data.get("target_skill_id"),
            target_role=(data.get("target_role") or "").strip() or None,
            priority=validate_catalog_value(data.get("priority"), "priorities", "Prioridad"),
            target_date=data.get("target_date"),
            status=validate_catalog_value(data.get("status"), "goal_statuses", "Estado"),
            progress_percentage=progress,
        )
        self.session.add(goal)
        self.session.commit()
        self.session.refresh(goal)
        return goal

    def list_growth_goals(self, profile_id: int) -> list[GrowthGoal]:
        """List growth goals."""

        return list(self.session.scalars(select(GrowthGoal).where(GrowthGoal.profile_id == profile_id)))

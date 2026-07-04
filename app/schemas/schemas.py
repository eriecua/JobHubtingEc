"""Pydantic schemas used by services and UI."""

from __future__ import annotations

from pydantic import BaseModel, Field


class DashboardMetrics(BaseModel):
    """Minimal counters shown on the first-phase dashboard."""

    total_jobs: int = Field(default=0, ge=0)
    saved_jobs: int = Field(default=0, ge=0)
    applications: int = Field(default=0, ge=0)


class DashboardSnapshot(BaseModel):
    """Current dashboard state, including database availability."""

    database_available: bool = False
    metrics: DashboardMetrics = Field(default_factory=DashboardMetrics)


class ProfileCompletenessResult(BaseModel):
    """Explainable profile completeness result."""

    total_percentage: int = Field(ge=0, le=100)
    completed_components: list[str] = Field(default_factory=list)
    missing_components: list[str] = Field(default_factory=list)
    recommendations: list[str] = Field(default_factory=list)
    component_scores: dict[str, int] = Field(default_factory=dict)

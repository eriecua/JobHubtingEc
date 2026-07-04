"""Shared data structures for strategic prioritization."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date
from typing import Any


@dataclass(frozen=True)
class PriorityComponent:
    """One weighted priority component before persistence."""

    name: str
    weight: int
    raw_score: float
    awarded_points: float
    explanation: str


@dataclass(frozen=True)
class PriorityResult:
    """Strategic priority output before persistence."""

    priority_score: float
    urgency_score: float
    strategic_value_score: float
    actionability_score: float
    application_effort_score: float
    recommended_action: str
    priority_bucket: str
    decision_deadline: date | None
    reasons: list[dict[str, Any]] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    blocking_factors: list[str] = field(default_factory=list)
    components: list[PriorityComponent] = field(default_factory=list)

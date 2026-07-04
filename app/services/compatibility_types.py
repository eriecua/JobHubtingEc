"""Shared data structures for deterministic compatibility evaluation."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass(frozen=True)
class ComponentScore:
    """One scored dimension before persistence."""

    component_name: str
    weight: int
    raw_score: float
    awarded_points: float
    confidence: float
    status: str
    evidence: list[dict[str, Any]] = field(default_factory=list)
    missing_data: list[str] = field(default_factory=list)
    explanation: str = ""


@dataclass(frozen=True)
class ConstraintResult:
    """Result of one hard constraint check."""

    constraint: str
    profile_value: Any
    job_value: Any
    result: str
    evidence: str
    reason: str
    severity: str


@dataclass(frozen=True)
class ScoreBundle:
    """Compatibility scoring output before persistence."""

    total_score: float
    confidence_score: float
    data_coverage_score: float
    components: list[ComponentScore]
    missing_information: list[dict[str, Any]]

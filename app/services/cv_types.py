"""Shared types for assisted CV-to-profile ingestion."""

from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, Field, field_validator


Confidence = Literal["Alta", "Media", "Baja"]
CandidateStatus = Literal["Pendiente", "Aceptado", "Editado", "Omitido"]
CandidateSection = Literal[
    "profile",
    "experience",
    "skill",
    "tool",
    "education",
    "certification",
    "target_role",
    "evidence",
]


class CVCandidate(BaseModel):
    """One extracted CV value awaiting human review."""

    section: CandidateSection
    field: str
    value: Any
    source_snippet: str
    confidence: Confidence = "Media"
    status: CandidateStatus = "Pendiente"
    warnings: list[str] = Field(default_factory=list)

    @field_validator("source_snippet")
    @classmethod
    def shorten_snippet(cls, value: str) -> str:
        """Keep snippets readable in Streamlit and tests."""

        return " ".join(str(value).split())[:300]


class CVDraft(BaseModel):
    """Structured draft generated from a CV before persistence."""

    source_name: str
    text_character_count: int
    candidates: list[CVCandidate] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)

    def grouped_candidates(self) -> dict[str, list[CVCandidate]]:
        """Return candidates grouped by domain section."""

        grouped: dict[str, list[CVCandidate]] = {}
        for candidate in self.candidates:
            grouped.setdefault(candidate.section, []).append(candidate)
        return grouped


class CVApplyResult(BaseModel):
    """Summary returned after applying reviewed CV candidates."""

    saved: list[str] = Field(default_factory=list)
    skipped: list[str] = Field(default_factory=list)
    errors: list[str] = Field(default_factory=list)

    @property
    def has_errors(self) -> bool:
        """Return whether any candidate failed to persist."""

        return bool(self.errors)

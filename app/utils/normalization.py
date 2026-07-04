"""Deterministic text normalization helpers."""

from __future__ import annotations

import re
import unicodedata


def normalize_text(value: str) -> str:
    """Return a lowercase, accent-free and whitespace-normalized key."""

    normalized = unicodedata.normalize("NFKD", value.strip().lower())
    without_accents = "".join(ch for ch in normalized if not unicodedata.combining(ch))
    return re.sub(r"\s+", " ", without_accents).strip()


def canonical_name(value: str, aliases: dict[str, list[str]] | None = None) -> str:
    """Normalize a name and collapse configured aliases into a stable key."""

    normalized = normalize_text(value)
    for canonical, alias_values in (aliases or {}).items():
        canonical_key = normalize_text(canonical)
        alias_keys = {normalize_text(alias) for alias in alias_values}
        if normalized == canonical_key or normalized in alias_keys:
            return canonical_key
    return normalized

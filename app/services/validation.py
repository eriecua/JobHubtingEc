"""Business validation helpers for profile data."""

from __future__ import annotations

from datetime import date
from decimal import Decimal
from urllib.parse import urlparse

from app.config import load_profile_catalogs


class ValidationError(ValueError):
    """Raised when user-provided profile data is invalid."""


def require_text(value: str | None, field_name: str) -> str:
    """Return stripped text or raise a user-readable validation error."""

    cleaned = (value or "").strip()
    if not cleaned:
        raise ValidationError(f"{field_name} es obligatorio.")
    return cleaned


def validate_optional_url(value: str | None, field_name: str) -> str | None:
    """Validate optional HTTP/HTTPS URLs."""

    cleaned = (value or "").strip()
    if not cleaned:
        return None
    parsed = urlparse(cleaned)
    if parsed.scheme not in {"http", "https"} or not parsed.netloc:
        raise ValidationError(f"{field_name} debe ser una URL valida con http o https.")
    return cleaned


def validate_non_negative(value: Decimal | int | float | None, field_name: str) -> None:
    """Reject negative numeric values."""

    if value is not None and value < 0:
        raise ValidationError(f"{field_name} no puede ser negativo.")


def validate_percentage(value: int, field_name: str) -> None:
    """Validate a percentage between 0 and 100."""

    if value < 0 or value > 100:
        raise ValidationError(f"{field_name} debe estar entre 0 y 100.")


def validate_date_order(
    start_date: date | None,
    end_date: date | None,
    field_name: str = "fecha final",
) -> None:
    """Validate that end date is not earlier than start date."""

    if start_date and end_date and end_date < start_date:
        raise ValidationError(f"{field_name} no puede ser anterior a la fecha inicial.")


def validate_catalog_value(value: str | None, catalog_key: str, field_name: str) -> str:
    """Validate a value against a YAML catalog."""

    cleaned = require_text(value, field_name)
    allowed = set(load_profile_catalogs().get(catalog_key, []))
    if cleaned not in allowed:
        raise ValidationError(f"{field_name} debe ser uno de: {', '.join(sorted(allowed))}.")
    return cleaned

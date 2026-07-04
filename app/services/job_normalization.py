"""Normalization and validation helpers for job vacancies."""

from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal, InvalidOperation
import hashlib
import json
import re
from typing import Any
from urllib.parse import urlparse, urlunparse

from app.config import load_job_import_config
from app.services.validation import ValidationError
from app.utils.normalization import canonical_name, normalize_text


class JobNormalizationService:
    """Deterministic normalization service for Phase 3 job data."""

    def __init__(self) -> None:
        self.config = load_job_import_config()

    def clean_text(self, value: Any) -> str:
        """Clean text conservatively while preserving meaning."""

        if value is None:
            return ""
        text = str(value).replace("\r\n", "\n").replace("\r", "\n")
        text = re.sub(r"[ \t]+", " ", text)
        return re.sub(r"\n{3,}", "\n\n", text).strip()

    def normalize_title(self, title: str) -> str:
        """Normalize a job title using configured aliases."""

        cleaned = self.clean_text(title)
        return canonical_name(cleaned, self.config.get("job_title_aliases", {}))

    def normalize_company(self, company: str) -> str:
        """Normalize company names moderately for deduplication."""

        key = normalize_text(self.clean_text(company))
        for suffix in self.config.get("company_suffixes", []):
            suffix_key = normalize_text(suffix)
            key = re.sub(rf"\b{re.escape(suffix_key)}$", "", key).strip()
        return re.sub(r"\s+", " ", key)

    def normalize_location(self, city: str | None, province: str | None, raw: str | None = None) -> dict[str, str | None]:
        """Normalize Ecuador city/province aliases without geocoding."""

        raw_key = normalize_text(raw or city or "")
        aliases = self.config.get("location_aliases", {})
        if raw_key in aliases:
            return {
                "city": aliases[raw_key].get("city"),
                "province": aliases[raw_key].get("province"),
                "country": "Ecuador",
            }
        return {
            "city": self.clean_text(city) or None,
            "province": self.clean_text(province) or None,
            "country": "Ecuador",
        }

    def normalize_url(self, value: str | None) -> str | None:
        """Validate and normalize an optional URL."""

        cleaned = self.clean_text(value)
        if not cleaned:
            return None
        parsed = urlparse(cleaned)
        if parsed.scheme not in {"http", "https"} or not parsed.netloc:
            raise ValidationError("La URL debe iniciar con http o https y tener dominio.")
        return urlunparse((parsed.scheme.lower(), parsed.netloc.lower(), parsed.path.rstrip("/"), "", parsed.query, ""))

    def parse_decimal(self, value: Any, field_name: str) -> Decimal | None:
        """Parse an optional decimal value."""

        if value is None or str(value).strip() == "":
            return None
        try:
            parsed = Decimal(str(value).replace(",", ".").strip())
        except InvalidOperation as exc:
            raise ValidationError(f"{field_name} debe ser numerico.") from exc
        if parsed < 0:
            raise ValidationError(f"{field_name} no puede ser negativo.")
        return parsed

    def parse_int(self, value: Any, field_name: str) -> int | None:
        """Parse an optional non-negative integer."""

        if value is None or str(value).strip() == "":
            return None
        parsed = int(float(str(value).replace(",", ".").strip()))
        if parsed < 0:
            raise ValidationError(f"{field_name} no puede ser negativo.")
        return parsed

    def parse_date(self, value: Any, field_name: str) -> tuple[date | None, list[str]]:
        """Parse frequent date formats and warn on ambiguous dates."""

        cleaned = self.clean_text(value)
        if not cleaned:
            return None, []
        match = re.match(r"^(\d{1,2})/(\d{1,2})/(\d{4})$", cleaned)
        if match:
            first, second, year = [int(part) for part in match.groups()]
            if first <= 12 and second <= 12:
                return None, [f"{field_name} es ambigua y requiere revision."]
            if first <= 12 < second:
                return date(year, first, second), []
        formats = ["%Y-%m-%d", "%d/%m/%Y", "%d-%m-%Y"]
        for fmt in formats:
            try:
                return datetime.strptime(cleaned, fmt).date(), []
            except ValueError:
                pass
        raise ValidationError(f"{field_name} tiene un formato de fecha invalido.")

    def validate_enum(self, value: str | None, allowed_key: str, default: str | None = None) -> str | None:
        """Validate an optional catalog value."""

        cleaned = self.clean_text(value)
        if not cleaned:
            return default
        allowed = set(self.config.get(allowed_key, []))
        if cleaned not in allowed:
            raise ValidationError(f"Valor no permitido: {cleaned}.")
        return cleaned

    def normalize_job_data(self, data: dict[str, Any]) -> tuple[dict[str, Any], list[str]]:
        """Normalize and validate raw job data for persistence or staging."""

        warnings: list[str] = []
        title = self.clean_text(data.get("title"))
        company = self.clean_text(data.get("company"))
        source = self.clean_text(data.get("source"))
        description = self.clean_text(data.get("description"))
        missing = [name for name, value in [("title", title), ("company", company), ("source", source), ("description", description)] if not value]
        if missing:
            raise ValidationError(f"Campos obligatorios faltantes: {', '.join(missing)}.")

        publication_date, date_warnings = self.parse_date(data.get("publication_date"), "publication_date")
        warnings.extend(date_warnings)
        expiration_date, expiration_warnings = self.parse_date(data.get("expiration_date"), "expiration_date")
        warnings.extend(expiration_warnings)
        if publication_date and expiration_date and expiration_date < publication_date:
            raise ValidationError("La fecha de vencimiento no puede ser anterior a la publicacion.")

        salary_min = self.parse_decimal(data.get("salary_min"), "salary_min")
        salary_max = self.parse_decimal(data.get("salary_max"), "salary_max")
        if salary_min is not None and salary_max is not None and salary_max < salary_min:
            raise ValidationError("salary_max no puede ser menor que salary_min.")
        if salary_min is not None and salary_max is None and not data.get("salary_period"):
            warnings.append("Existe un solo valor salarial; revise si es minimo o maximo.")

        location = self.normalize_location(data.get("city"), data.get("province"), data.get("location_raw") or data.get("location"))
        modality = self.validate_enum(data.get("modality"), "modalities", "No especificada")
        employment_type = self.validate_enum(data.get("employment_type"), "employment_types", "No especificado")
        salary_period = self.validate_enum(data.get("salary_period"), "salary_periods", "No especificado")
        currency = self.validate_enum(data.get("currency"), "currencies", "USD")
        source_url = self.normalize_url(data.get("source_url"))
        experience_min = self.parse_decimal(data.get("experience_min_years"), "experience_min_years")
        experience_max = self.parse_decimal(data.get("experience_max_years"), "experience_max_years")
        if experience_min is not None and experience_max is not None and experience_max < experience_min:
            raise ValidationError("experience_max_years no puede ser menor que experience_min_years.")

        normalized = {
            "external_id": self.clean_text(data.get("external_id")) or None,
            "source_record_id": self.clean_text(data.get("source_record_id")) or None,
            "title": title,
            "normalized_title": self.normalize_title(title),
            "company": company,
            "normalized_company": self.normalize_company(company),
            "source": source,
            "source_url": source_url,
            "country": location["country"],
            "city": location["city"],
            "province": location["province"],
            "location": self.clean_text(data.get("location")) or self.clean_text(data.get("location_raw")) or None,
            "location_raw": self.clean_text(data.get("location_raw")) or None,
            "modality": modality,
            "workplace_type": self.clean_text(data.get("workplace_type")) or None,
            "employment_type": employment_type,
            "contract_type": self.clean_text(data.get("contract_type")) or None,
            "schedule_type": self.clean_text(data.get("schedule_type")) or None,
            "salary_min": salary_min,
            "salary_max": salary_max,
            "salary_period": salary_period,
            "currency": currency,
            "salary_is_estimated": bool(data.get("salary_is_estimated", False)),
            "benefits": self.clean_text(data.get("benefits")) or None,
            "description": description,
            "responsibilities": self.clean_text(data.get("responsibilities")) or None,
            "requirements": self.clean_text(data.get("requirements")) or None,
            "education_required": self.clean_text(data.get("education_required")) or None,
            "experience_min_years": experience_min,
            "experience_max_years": experience_max,
            "seniority_level": self.clean_text(data.get("seniority_level")) or None,
            "languages_required": self.clean_text(data.get("languages_required")) or None,
            "travel_required": data.get("travel_required"),
            "relocation_required": data.get("relocation_required"),
            "sector": self.clean_text(data.get("sector")) or None,
            "department": self.clean_text(data.get("department")) or None,
            "category": self.clean_text(data.get("category")) or None,
            "vacancies_count": self.parse_int(data.get("vacancies_count"), "vacancies_count"),
            "publication_date": publication_date,
            "expiration_date": expiration_date,
            "status": data.get("status") or "Nueva",
            "review_status": data.get("review_status") or "Pendiente",
            "notes": self.clean_text(data.get("notes")) or None,
            "raw_data": data.get("raw_data"),
        }
        normalized["is_remote"] = modality == "Remota"
        normalized["content_hash"] = self.content_hash(normalized)
        normalized["deduplication_key"] = self.deduplication_key(normalized)
        return normalized, warnings

    def content_hash(self, data: dict[str, Any]) -> str:
        """Calculate a stable content hash from core fields."""

        payload = {
            "title": normalize_text(str(data.get("title") or "")),
            "company": normalize_text(str(data.get("company") or "")),
            "description": normalize_text(str(data.get("description") or ""))[:1000],
            "source": normalize_text(str(data.get("source") or "")),
        }
        encoded = json.dumps(payload, sort_keys=True, ensure_ascii=False).encode("utf-8")
        return hashlib.sha256(encoded).hexdigest()

    def deduplication_key(self, data: dict[str, Any]) -> str:
        """Build a readable deterministic deduplication key."""

        parts = [
            data.get("normalized_title") or self.normalize_title(str(data.get("title") or "")),
            data.get("normalized_company") or self.normalize_company(str(data.get("company") or "")),
            normalize_text(str(data.get("city") or "")),
            normalize_text(str(data.get("source") or "")),
        ]
        return "|".join(parts)

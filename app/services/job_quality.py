"""Job data quality and suspicious vacancy services."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from app.config import load_job_import_config
from app.utils.normalization import normalize_text


@dataclass
class JobQualityResult:
    """Explainable job quality result."""

    status: str
    present_fields: list[str]
    missing_fields: list[str]
    errors: list[str]
    warnings: list[str]
    recommendations: list[str]


@dataclass
class SuspiciousResult:
    """Suspicious-job rule result."""

    is_suspicious: bool
    risk_level: str | None
    reasons: list[str]


class JobQualityService:
    """Calculate initial data quality for job records."""

    required_fields = ["title", "company", "source", "description"]

    def evaluate(self, data: dict[str, Any]) -> JobQualityResult:
        """Return quality status, missing fields and recommendations."""

        present = [field for field, value in data.items() if value not in (None, "", [], {})]
        missing_required = [field for field in self.required_fields if not data.get(field)]
        warnings: list[str] = []
        recommendations: list[str] = []
        if missing_required:
            return JobQualityResult(
                status="Invalida",
                present_fields=present,
                missing_fields=missing_required,
                errors=[f"Falta {field}" for field in missing_required],
                warnings=[],
                recommendations=["Completa cargo, empresa, fuente y descripcion antes de guardar."],
            )
        completeness_fields = [
            "city",
            "province",
            "modality",
            "publication_date",
            "requirements",
            "responsibilities",
            "source_url",
            "external_id",
        ]
        missing_relevant = [field for field in completeness_fields if not data.get(field)]
        if data.get("description") and len(str(data["description"])) < 40:
            warnings.append("La descripcion es muy breve.")
        if not (data.get("city") or data.get("province") or data.get("modality")):
            recommendations.append("Agrega ubicacion o modalidad.")
        if not (data.get("requirements") or data.get("responsibilities")):
            recommendations.append("Agrega requisitos o responsabilidades.")
        if not (data.get("source_url") or data.get("external_id")):
            recommendations.append("Agrega URL o identificador externo.")

        if not missing_relevant and not warnings:
            status = "Completa"
        elif len(str(data.get("description") or "")) < 40 and len(missing_relevant) >= 5:
            status = "Minima"
        else:
            status = "Parcial"
        return JobQualityResult(
            status=status,
            present_fields=present,
            missing_fields=missing_relevant,
            errors=[],
            warnings=warnings,
            recommendations=recommendations,
        )


class SuspiciousJobService:
    """Apply configurable suspicious vacancy rules."""

    severity_order = {"Bajo": 1, "Medio": 2, "Alto": 3}

    def __init__(self) -> None:
        self.config = load_job_import_config()

    def evaluate(self, data: dict[str, Any]) -> SuspiciousResult:
        """Return risk level and matched rules without rejecting the job."""

        text = normalize_text(" ".join(str(data.get(key) or "") for key in ["company", "title", "description", "requirements", "notes"]))
        reasons: list[str] = []
        risk = 0
        if not data.get("company") or normalize_text(str(data.get("company"))) in {"confidencial", "empresa importante"}:
            reasons.append("Empresa vacia o generica.")
            risk = max(risk, self.severity_order["Bajo"])
        if len(str(data.get("description") or "")) < 25:
            reasons.append("Descripcion extremadamente corta.")
            risk = max(risk, self.severity_order["Bajo"])
        if str(data.get("description") or "").isupper() and len(str(data.get("description") or "")) > 40:
            reasons.append("Uso excesivo de mayusculas.")
            risk = max(risk, self.severity_order["Medio"])
        for rule_name, rule in self.config.get("suspicious_patterns", {}).items():
            for term in rule.get("terms", []):
                if normalize_text(term) in text:
                    reasons.append(f"{rule_name}: {term}")
                    risk = max(risk, self.severity_order.get(rule.get("severity", "Bajo"), 1))
        level = {1: "Bajo", 2: "Medio", 3: "Alto"}.get(risk)
        return SuspiciousResult(is_suspicious=bool(reasons), risk_level=level, reasons=reasons)

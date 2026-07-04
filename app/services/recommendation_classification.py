"""Deterministic recommendation type classification."""

from __future__ import annotations

from typing import Any


class RecommendationClassificationService:
    """Apply configurable precedence rules to assign recommendation type."""

    def __init__(self, config: dict[str, Any]) -> None:
        self.config = config

    def classify(
        self,
        total_score: float,
        confidence_score: float,
        eligibility_status: str,
        components: list[Any],
        gaps: list[dict[str, Any]],
    ) -> str:
        """Return the recommendation type."""

        thresholds = self.config["recommendation_thresholds"]
        critical_gaps = [gap for gap in gaps if gap.get("severity") == "Critica"]
        growth_component = next((item for item in components if item.component_name == "growth"), None)
        if eligibility_status == "No elegible":
            return "No recomendada"
        if eligibility_status in {"Requiere revision", "Informacion insuficiente"}:
            return "Requiere revision"
        if confidence_score < self.config["confidence"]["minimum_review"]:
            return "Requiere revision"
        if critical_gaps:
            return "Baja compatibilidad" if total_score >= thresholds["low_match"] else "No recomendada"
        if 60 <= total_score and growth_component and growth_component.raw_score >= 0.75 and gaps:
            return "Oportunidad de crecimiento"
        if total_score >= thresholds["high_match"] and not critical_gaps and confidence_score >= self.config["confidence"]["sufficient_for_high_match"]:
            return "Alta compatibilidad"
        if total_score >= thresholds["good_match"]:
            return "Buena compatibilidad"
        if total_score >= thresholds["exploratory"]:
            return "Exploratoria"
        if total_score >= thresholds["low_match"]:
            return "Baja compatibilidad"
        return "No recomendada"

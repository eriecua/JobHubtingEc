"""Deterministic explanation templates for compatibility results."""

from __future__ import annotations

from typing import Any


class ExplanationService:
    """Build readable explanations without ungrounded claims."""

    def build(
        self,
        total_score: float,
        confidence_score: float,
        coverage_score: float,
        eligibility_status: str,
        recommendation_type: str,
        strengths: list[dict[str, Any]],
        gaps: list[dict[str, Any]],
        missing_information: list[dict[str, Any]],
    ) -> str:
        """Return a deterministic explanation."""

        lines = [
            f"Compatibilidad: {total_score:.0f}/100",
            f"Confianza: {confidence_score:.0f}/100",
            f"Cobertura de datos: {coverage_score:.0f}/100",
            f"Elegibilidad: {eligibility_status}.",
            "",
            "La evaluacion compara la vacante con el perfil mediante reglas configurables y evidencia registrada.",
        ]
        if strengths:
            lines.append("Fortalezas principales:")
            for item in strengths[:3]:
                lines.append(f"- {item.get('title')}: {item.get('explanation')}")
        if gaps:
            lines.append("Brechas principales:")
            for item in gaps[:3]:
                lines.append(f"- {item.get('requirement')}: {item.get('available_evidence')}")
        if missing_information:
            lines.append("Informacion pendiente:")
            for item in missing_information[:4]:
                lines.append(f"- {item.get('dimension')}: {item.get('missing')}")
        lines.append(f"Recomendacion: {recommendation_type}.")
        if eligibility_status == "No elegible":
            lines.append("La vacante no debe priorizarse mientras exista una restriccion obligatoria incumplida.")
        elif recommendation_type == "Oportunidad de crecimiento":
            lines.append("Puede revisarse como oportunidad de aprendizaje si las brechas son aceptables para el usuario.")
        return "\n".join(lines)

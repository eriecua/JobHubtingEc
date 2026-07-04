"""Application effort estimation for strategic prioritization."""

from __future__ import annotations

from typing import Any

from app.models import Job, JobEvaluation


class ApplicationEffortService:
    """Estimate application effort without generating documents."""

    def __init__(self, config: dict[str, Any]) -> None:
        self.config = config

    def score(self, job: Job, evaluation: JobEvaluation | None, manual_level: str | None = None) -> tuple[float, str, list[dict[str, str]], list[str]]:
        """Return inverse effort score, level, reasons and warnings."""

        values = self.config["application_effort"]
        if manual_level:
            level = manual_level if manual_level in values else "Desconocido"
            return float(values[level]), level, [{"factor": "esfuerzo", "detail": f"Nivel corregido manualmente: {level}."}], []

        indicators = 0
        reasons: list[dict[str, str]] = []
        warnings: list[str] = []
        text = " ".join([job.description or "", job.requirements or "", job.responsibilities or ""]).lower()
        for marker, detail in [
            ("carta", "Puede requerir carta o texto adicional."),
            ("portafolio", "Puede requerir portafolio."),
            ("formulario", "Puede requerir formulario extenso."),
            ("documentos", "Puede requerir documentos adicionales."),
            ("prueba", "Puede requerir prueba tecnica."),
        ]:
            if marker in text:
                indicators += 1
                reasons.append({"factor": "esfuerzo", "detail": detail})
        critical_gaps = [gap for gap in (evaluation.gaps if evaluation else []) if gap.get("severity") == "Critica"]
        if critical_gaps:
            indicators += min(len(critical_gaps), 2)
            reasons.append({"factor": "brechas", "detail": "Hay brechas criticas que pueden exigir preparacion previa."})
        if not job.source_url:
            warnings.append("Sin enlace, el esfuerzo real de postulacion es desconocido.")
            return float(values["Desconocido"]), "Desconocido", reasons, warnings
        if indicators >= 3:
            level = "Alto"
        elif indicators >= 1:
            level = "Medio"
        else:
            level = "Bajo"
            reasons.append({"factor": "esfuerzo", "detail": "No se detectan requisitos extra de postulacion."})
        return float(values[level]), level, reasons, warnings

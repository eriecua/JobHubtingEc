"""Deterministic urgency calculation for strategic prioritization."""

from __future__ import annotations

from datetime import date
from typing import Any

from app.models import Job


class UrgencyService:
    """Calculate urgency from publication, expiration and job status."""

    def __init__(self, config: dict[str, Any]) -> None:
        self.config = config

    def score(self, job: Job) -> tuple[float, date | None, list[dict[str, str]], list[str], list[str]]:
        """Return raw urgency, deadline, reasons, warnings and blockers."""

        reasons: list[dict[str, str]] = []
        warnings: list[str] = []
        blockers: list[str] = []
        today = date.today()
        status = (job.status or "").strip()
        status_penalty = self.config["urgency"].get("status_penalties", {}).get(status)
        if status_penalty == 0:
            blockers.append(f"Vacante en estado {status}.")
            return 0.0, job.expiration_date, reasons, warnings, blockers
        if job.expiration_date and job.expiration_date < today:
            blockers.append("Vacante vencida.")
            return 0.0, job.expiration_date, reasons, warnings, blockers

        publication_score = self._publication_score(job.publication_date, today, reasons, warnings)
        expiration_score = self._expiration_score(job.expiration_date, today, reasons, warnings)
        raw = publication_score * 0.65 + expiration_score * 0.35
        if status_penalty is not None:
            raw *= float(status_penalty)
        return max(0.0, min(raw, 1.0)), job.expiration_date, reasons, warnings, blockers

    def _publication_score(self, publication_date: date | None, today: date, reasons: list[dict[str, str]], warnings: list[str]) -> float:
        bands = self.config["urgency"]["publication_age"]
        if publication_date is None:
            warnings.append("No se informa fecha de publicacion.")
            return float(bands["unknown"])
        age = (today - publication_date).days
        if age < 0:
            warnings.append("La fecha de publicacion es futura; revisar dato.")
            return float(bands["unknown"])
        if age <= 3:
            score = bands["0_3_days"]
        elif age <= 7:
            score = bands["4_7_days"]
        elif age <= 14:
            score = bands["8_14_days"]
        elif age <= 30:
            score = bands["15_30_days"]
        elif age <= 60:
            score = bands["31_60_days"]
        else:
            score = bands["over_60_days"]
        reasons.append({"factor": "antiguedad", "detail": f"Publicada hace {age} dias."})
        return float(score)

    def _expiration_score(self, expiration_date: date | None, today: date, reasons: list[dict[str, str]], warnings: list[str]) -> float:
        bands = self.config["urgency"]["expiration"]
        if expiration_date is None:
            warnings.append("No se informa fecha de vencimiento.")
            return float(bands["unknown"])
        days = (expiration_date - today).days
        if days <= 2:
            score = bands["0_2_days"]
        elif days <= 5:
            score = bands["3_5_days"]
        elif days <= 10:
            score = bands["6_10_days"]
        else:
            score = bands["over_10_days"]
        reasons.append({"factor": "vencimiento", "detail": f"Vence en {days} dias."})
        return float(score)

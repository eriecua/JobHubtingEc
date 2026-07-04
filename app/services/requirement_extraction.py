"""Deterministic extraction of structured job requirements."""

from __future__ import annotations

from decimal import Decimal
import re
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.config import load_compatibility_config, load_profile_catalogs
from app.models import Job, Skill, Tool
from app.repositories.evaluation_repository import EvaluationRepository
from app.utils.normalization import canonical_name, normalize_text


class RequirementExtractionService:
    """Extract requirements from job fields using explicit rules and aliases."""

    TEXT_FIELDS = ["requirements", "responsibilities", "description", "education_required", "languages_required"]

    def __init__(self, session: Session, config: dict[str, Any] | None = None) -> None:
        self.session = session
        self.config = config or load_compatibility_config()
        self.catalogs = load_profile_catalogs()
        self._skills_cache: list[Skill] | None = None
        self._tools_cache: list[Tool] | None = None

    def extract_for_job(self, job: Job, persist: bool = True, commit: bool = True) -> list[dict[str, Any]]:
        """Extract requirements for one job and optionally persist them."""

        extracted: list[dict[str, Any]] = []
        text_by_field = {field: getattr(job, field) for field in self.TEXT_FIELDS if getattr(job, field, None)}
        extracted.extend(self._extract_skills(text_by_field))
        extracted.extend(self._extract_tools(text_by_field))
        extracted.extend(self._extract_text_requirements(text_by_field))
        extracted.extend(self._extract_structured(job))
        unique = self._deduplicate(extracted)
        if persist:
            return [
                self._requirement_to_dict(item)
                for item in EvaluationRepository(self.session).upsert_extracted_requirements(job.id, unique, commit=commit)
            ]
        return unique

    def _extract_skills(self, text_by_field: dict[str, str]) -> list[dict[str, Any]]:
        skills = self._skills()
        aliases = self.catalogs.get("skill_aliases", {})
        output: list[dict[str, Any]] = []
        for field, text in text_by_field.items():
            normalized_text = normalize_text(text)
            for skill in skills:
                names = [skill.name, skill.normalized_name, *aliases.get(skill.normalized_name, [])]
                match = self._find_name(normalized_text, names)
                if match and not self._is_name_negated(text, match):
                    output.append(
                        self._base(
                            "Habilidad",
                            match,
                            skill.normalized_name,
                            field,
                            self._importance_near(text, match),
                            "Alias" if normalize_text(match) != skill.normalized_name else "Palabra clave",
                            Decimal("0.85"),
                            skill_id=skill.id,
                        )
                    )
        return output

    def _extract_tools(self, text_by_field: dict[str, str]) -> list[dict[str, Any]]:
        tools = self._tools()
        aliases = self.catalogs.get("tool_aliases", {})
        output: list[dict[str, Any]] = []
        for field, text in text_by_field.items():
            normalized_text = normalize_text(text)
            for tool in tools:
                names = [tool.name, tool.normalized_name, *aliases.get(tool.normalized_name, [])]
                match = self._find_name(normalized_text, names)
                if match and not self._is_name_negated(text, match):
                    output.append(
                        self._base(
                            "Herramienta",
                            match,
                            tool.normalized_name,
                            field,
                            self._importance_near(text, match),
                            "Alias" if normalize_text(match) != tool.normalized_name else "Palabra clave",
                            Decimal("0.85"),
                            tool_id=tool.id,
                        )
                    )
        return output

    def _extract_text_requirements(self, text_by_field: dict[str, str]) -> list[dict[str, Any]]:
        output: list[dict[str, Any]] = []
        for field, text in text_by_field.items():
            lowered = normalize_text(text)
            experience = re.search(r"(\d+(?:[\.,]\d+)?)\s*(?:anos|anios|years)", lowered)
            if experience:
                output.append(
                    self._base(
                        "Experiencia",
                        experience.group(0),
                        experience.group(1).replace(",", "."),
                        field,
                        self._importance(text),
                        "Palabra clave",
                        Decimal("0.70"),
                    )
                )
            for keyword in ["ingenieria industrial", "universitario", "tecnico", "bachiller"]:
                if keyword in lowered:
                    output.append(
                        self._base("Formacion", keyword, keyword, field, self._importance_near(text, keyword), "Palabra clave", Decimal("0.65"))
                    )
            for keyword in ["ingles", "english"]:
                if keyword in lowered:
                    output.append(
                        self._base("Idioma", keyword, "ingles", field, self._importance_near(text, keyword), "Palabra clave", Decimal("0.65"))
                    )
            for certification in self.config.get("known_certifications", []):
                if self._find_name(lowered, [certification]) and not self._is_name_negated(text, certification):
                    output.append(
                        self._base(
                            "Certificacion",
                            certification,
                            normalize_text(certification),
                            field,
                            self._importance_near(text, certification),
                            "Catalogo configurado",
                            Decimal("0.70"),
                        )
                    )
        return output

    def _extract_structured(self, job: Job) -> list[dict[str, Any]]:
        output: list[dict[str, Any]] = []
        structured = [
            ("Experiencia", "experience_min_years", job.experience_min_years),
            ("Experiencia", "experience_max_years", job.experience_max_years),
            ("Modalidad", "modality", job.modality),
            ("Jornada", "schedule_type", job.schedule_type),
            ("Contrato", "contract_type", job.contract_type),
            ("Viaje", "travel_required", job.travel_required),
            ("Reubicacion", "relocation_required", job.relocation_required),
            ("Salario", "salary_min", job.salary_min),
            ("Salario", "salary_max", job.salary_max),
            ("Otro", "sector", job.sector),
            ("Otro", "seniority_level", job.seniority_level),
        ]
        for req_type, field, value in structured:
            if value in (None, ""):
                continue
            output.append(
                self._base(
                    req_type,
                    str(value),
                    normalize_text(str(value)),
                    field,
                    "Informativo" if field not in {"experience_min_years", "salary_min"} else "No determinada",
                    "Campo estructurado",
                    Decimal("0.95"),
                )
            )
        return output

    def _importance(self, text: str) -> str:
        normalized = normalize_text(text)
        if any(marker in normalized for marker in self.config["required_markers"]):
            return "Obligatorio"
        if any(marker in normalized for marker in self.config["desired_markers"]):
            return "Deseable"
        return "No determinada"

    def _importance_near(self, text: str, match: str) -> str:
        """Detect importance in the sentence where the match appears."""

        normalized_match = normalize_text(match)
        for sentence in re.split(r"[\.;\n]", text):
            normalized_sentence = normalize_text(sentence)
            if normalized_match in normalized_sentence:
                return self._importance(sentence)
        return self._importance(text)

    def _find_name(self, normalized_text: str, names: list[str]) -> str | None:
        for name in sorted({value for value in names if value}, key=len, reverse=True):
            normalized_name = normalize_text(name)
            pattern = rf"(?<!\w){re.escape(normalized_name)}(?!\w)"
            if re.search(pattern, normalized_text):
                return name
        return None

    def _is_name_negated(self, text: str, match: str) -> bool:
        """Return true when a matched term appears only in a negated sentence."""

        normalized_match = normalize_text(match)
        negation_markers = ["no se requiere", "no requiere", "sin requisito", "no es necesario"]
        for sentence in re.split(r"[\.;\n]", text):
            normalized_sentence = normalize_text(sentence)
            if normalized_match in normalized_sentence:
                return any(marker in normalized_sentence for marker in negation_markers)
        return False

    def _base(
        self,
        requirement_type: str,
        raw_text: str,
        normalized_value: str | None,
        source_field: str,
        importance: str,
        method: str,
        confidence: Decimal,
        skill_id: int | None = None,
        tool_id: int | None = None,
    ) -> dict[str, Any]:
        return {
            "requirement_type": requirement_type,
            "raw_text": raw_text.strip(),
            "normalized_value": normalized_value,
            "importance": importance,
            "source_field": source_field,
            "extraction_method": method,
            "extraction_confidence": confidence,
            "skill_id": skill_id,
            "tool_id": tool_id,
            "is_confirmed_by_user": False,
            "is_active": True,
        }

    def _deduplicate(self, rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
        seen: set[tuple[str, str]] = set()
        output: list[dict[str, Any]] = []
        for row in rows:
            key = (row["requirement_type"], row.get("normalized_value") or normalize_text(row["raw_text"]))
            if key in seen:
                continue
            seen.add(key)
            output.append(row)
        return output

    def _skills(self) -> list[Skill]:
        if self._skills_cache is None:
            self._skills_cache = list(self.session.scalars(select(Skill).where(Skill.is_active.is_(True))))
        return self._skills_cache

    def _tools(self) -> list[Tool]:
        if self._tools_cache is None:
            self._tools_cache = list(self.session.scalars(select(Tool)))
        return self._tools_cache

    def _requirement_to_dict(self, item) -> dict[str, Any]:
        return {
            "id": item.id,
            "job_id": item.job_id,
            "requirement_type": item.requirement_type,
            "raw_text": item.raw_text,
            "normalized_value": item.normalized_value,
            "importance": item.importance,
            "source_field": item.source_field,
            "extraction_method": item.extraction_method,
            "extraction_confidence": float(item.extraction_confidence),
            "skill_id": item.skill_id,
            "tool_id": item.tool_id,
            "is_confirmed_by_user": item.is_confirmed_by_user,
            "is_active": item.is_active,
        }

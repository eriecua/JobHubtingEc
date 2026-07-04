"""Map deterministic CV sections into reviewable profile candidates."""

from __future__ import annotations

from datetime import date
import re
from typing import Any

from app.config import load_profile_catalogs
from app.services.cv_text_extractor import CVSection, CVTextExtractor
from app.services.cv_types import CVCandidate, CVDraft
from app.utils.normalization import canonical_name, normalize_text


DATE_RANGE_RE = re.compile(
    r"(?P<start>(?:\d{4}[-/]\d{1,2})|(?:\d{1,2}[-/]\d{4})|(?:\d{4}))\s*"
    r"(?:-|–|a|hasta)\s*"
    r"(?P<end>actualidad|actual|presente|(?:\d{4}[-/]\d{1,2})|(?:\d{1,2}[-/]\d{4})|(?:\d{4}))",
    re.IGNORECASE,
)


class CVProfileMapper:
    """Build a structured draft from extracted CV text using local rules."""

    def __init__(self, extractor: CVTextExtractor | None = None) -> None:
        self.extractor = extractor or CVTextExtractor()
        self.catalogs = load_profile_catalogs()

    def build_draft(self, text: str, source_name: str) -> CVDraft:
        """Create profile candidates from cleaned CV text."""

        sections = self.extractor.extract_sections(text)
        candidates: list[CVCandidate] = []
        candidates.extend(self._profile_candidates(sections))
        candidates.extend(self._experience_candidates(sections.get("experience")))
        candidates.extend(self._skill_candidates(sections.get("skill")))
        candidates.extend(self._tool_candidates(sections.get("tool")))
        candidates.extend(self._education_candidates(sections.get("education")))
        candidates.extend(self._certification_candidates(sections.get("certification")))
        candidates.extend(self._target_role_candidates(sections.get("target_role")))
        warnings = []
        if not candidates:
            warnings.append("No se detectaron secciones reconocibles. Puedes completar el perfil manualmente.")
        return CVDraft(source_name=source_name, text_character_count=len(text), candidates=candidates, warnings=warnings)

    def _profile_candidates(self, sections: dict[str, CVSection]) -> list[CVCandidate]:
        identity_lines = sections.get("identity").lines if sections.get("identity") else []
        profile_text = sections.get("profile").text if sections.get("profile") else ""
        candidates: list[CVCandidate] = []
        clean_identity = [line for line in identity_lines if "@" not in line and not line.lower().startswith("http")]
        if clean_identity:
            first = clean_identity[0]
            if 1 < len(first.split()) <= 6:
                candidates.append(
                    CVCandidate(
                        section="profile",
                        field="full_name",
                        value=first,
                        source_snippet=first,
                        confidence="Media",
                        status="Pendiente",
                    )
                )
        if len(clean_identity) >= 2:
            title = clean_identity[1]
            candidates.append(
                CVCandidate(
                    section="profile",
                    field="professional_title",
                    value=title,
                    source_snippet=title,
                    confidence="Media",
                    status="Pendiente",
                )
            )
        if profile_text:
            candidates.append(
                CVCandidate(
                    section="profile",
                    field="professional_summary",
                    value=profile_text,
                    source_snippet=profile_text,
                    confidence="Alta",
                    status="Aceptado",
                )
            )
        return candidates

    def _experience_candidates(self, section: CVSection | None) -> list[CVCandidate]:
        if section is None:
            return []
        blocks = self._split_blocks(section.lines)
        candidates: list[CVCandidate] = []
        for block in blocks:
            header = block[0]
            parsed = self._parse_experience_header(header)
            if not parsed:
                continue
            responsibilities, achievements = self._split_responsibilities_and_achievements(block[1:])
            value = {
                "company": parsed["company"],
                "job_title": parsed["job_title"],
                "start_date": parsed["start_date"],
                "end_date": parsed["end_date"],
                "is_current": parsed["is_current"],
                "description": "\n".join(responsibilities).strip(),
                "achievements": "\n".join(achievements).strip(),
                "city": "",
                "sector": "",
            }
            warnings = list(parsed["warnings"])
            status = "Pendiente" if warnings else "Aceptado"
            confidence = "Baja" if warnings else "Media"
            candidates.append(
                CVCandidate(
                    section="experience",
                    field="work_experience",
                    value=value,
                    source_snippet="\n".join(block),
                    confidence=confidence,
                    status=status,
                    warnings=warnings,
                )
            )
            candidates.extend(self._evidence_candidates_from_achievements(achievements, block))
        return candidates

    def _skill_candidates(self, section: CVSection | None) -> list[CVCandidate]:
        return self._name_candidates(section, "skill", "skill", self.catalogs.get("skill_aliases", {}))

    def _tool_candidates(self, section: CVSection | None) -> list[CVCandidate]:
        return self._name_candidates(section, "tool", "tool", self.catalogs.get("tool_aliases", {}))

    def _education_candidates(self, section: CVSection | None) -> list[CVCandidate]:
        if section is None:
            return []
        candidates: list[CVCandidate] = []
        for line in section.lines:
            value = self._parse_education_line(line)
            candidates.append(
                CVCandidate(
                    section="education",
                    field="education_record",
                    value=value,
                    source_snippet=line,
                    confidence="Media",
                    status="Pendiente" if not value["field_of_study"] else "Aceptado",
                    warnings=[] if value["field_of_study"] else ["Completa el campo de estudio antes de guardar."],
                )
            )
        return candidates

    def _certification_candidates(self, section: CVSection | None) -> list[CVCandidate]:
        if section is None:
            return []
        candidates: list[CVCandidate] = []
        for line in section.lines:
            name, organization = self._split_name_organization(line)
            warnings = []
            if not organization:
                warnings.append("La organizacion emisora no fue detectada; puedes editarla antes de guardar.")
            candidates.append(
                CVCandidate(
                    section="certification",
                    field="certification",
                    value={
                        "name": name,
                        "issuing_organization": organization,
                        "issue_date": None,
                        "expiration_date": None,
                        "does_not_expire": True,
                    },
                    source_snippet=line,
                    confidence="Media" if organization else "Baja",
                    status="Pendiente" if warnings else "Aceptado",
                    warnings=warnings,
                )
            )
        return candidates

    def _target_role_candidates(self, section: CVSection | None) -> list[CVCandidate]:
        if section is None:
            return []
        candidates: list[CVCandidate] = []
        seen: set[str] = set()
        for name in self._split_values(section.text):
            key = normalize_text(name)
            if not key or key in seen:
                continue
            seen.add(key)
            candidates.append(
                CVCandidate(
                    section="target_role",
                    field="target_role",
                    value={"role_name": name, "priority": "Exploratoria", "desired_level": ""},
                    source_snippet=name,
                    confidence="Media",
                    status="Pendiente",
                )
            )
        return candidates

    def _evidence_candidates_from_achievements(self, achievements: list[str], block: list[str]) -> list[CVCandidate]:
        candidates: list[CVCandidate] = []
        for achievement in achievements:
            title = achievement[:80].rstrip(". ")
            candidates.append(
                CVCandidate(
                    section="evidence",
                    field="skill_evidence",
                    value={
                        "skill_name": "",
                        "evidence_type": "Logro",
                        "title": title or "Logro detectado",
                        "description": achievement,
                        "metric_value": None,
                        "metric_unit": "",
                    },
                    source_snippet="\n".join(block),
                    confidence="Baja",
                    status="Pendiente",
                    warnings=["Asocia esta evidencia a una habilidad antes de guardarla."],
                )
            )
        return candidates

    def _name_candidates(
        self,
        section: CVSection | None,
        section_name: str,
        field: str,
        aliases: dict[str, list[str]],
    ) -> list[CVCandidate]:
        if section is None:
            return []
        candidates: list[CVCandidate] = []
        seen: set[str] = set()
        for raw_name in self._split_values(section.text):
            canonical = canonical_name(raw_name, aliases)
            if not canonical or canonical in seen:
                continue
            seen.add(canonical)
            candidates.append(
                CVCandidate(
                    section=section_name,  # type: ignore[arg-type]
                    field=field,
                    value=self._display_name(canonical),
                    source_snippet=raw_name,
                    confidence="Alta" if normalize_text(raw_name) == canonical else "Media",
                    status="Aceptado",
                )
            )
        return candidates

    def _split_blocks(self, lines: list[str]) -> list[list[str]]:
        blocks: list[list[str]] = []
        current: list[str] = []
        for line in lines:
            if DATE_RANGE_RE.search(line) and current:
                blocks.append(current)
                current = [line]
            else:
                current.append(line)
        if current:
            blocks.append(current)
        return blocks

    def _parse_experience_header(self, header: str) -> dict[str, Any] | None:
        match = DATE_RANGE_RE.search(header)
        if not match:
            return None
        before_dates = header[: match.start()].strip(" -|,")
        parts = re.split(r"\s+-\s+|\s+\|\s+|\s+en\s+", before_dates, maxsplit=1, flags=re.IGNORECASE)
        if len(parts) < 2:
            return None
        start_date, start_ambiguous = self._parse_date(match.group("start"))
        end_raw = match.group("end")
        is_current = normalize_text(end_raw) in {"actualidad", "actual", "presente"}
        end_date, end_ambiguous = (None, False) if is_current else self._parse_date(end_raw)
        warnings = []
        if start_ambiguous or end_ambiguous:
            warnings.append("Fecha laboral ambigua; confirma dia y mes antes de guardar.")
        return {
            "job_title": parts[0].strip(),
            "company": parts[1].strip(),
            "start_date": start_date,
            "end_date": end_date,
            "is_current": is_current,
            "warnings": warnings,
        }

    def _parse_date(self, raw: str) -> tuple[date | None, bool]:
        value = raw.strip()
        if re.fullmatch(r"\d{4}", value):
            return None, True
        year_month = re.fullmatch(r"(?P<year>\d{4})[-/](?P<month>\d{1,2})", value)
        month_year = re.fullmatch(r"(?P<month>\d{1,2})[-/](?P<year>\d{4})", value)
        match = year_month or month_year
        if not match:
            return None, True
        month = int(match.group("month"))
        year = int(match.group("year"))
        if month < 1 or month > 12:
            return None, True
        return date(year, month, 1), False

    def _split_responsibilities_and_achievements(self, lines: list[str]) -> tuple[list[str], list[str]]:
        responsibilities: list[str] = []
        achievements: list[str] = []
        current = responsibilities
        for raw_line in lines:
            line = raw_line.strip(" -•")
            label = normalize_text(line.rstrip(":"))
            if label.startswith("responsabilidades"):
                current = responsibilities
                remainder = line.split(":", 1)[1].strip() if ":" in line else ""
            elif label.startswith("logros") or label.startswith("achievements"):
                current = achievements
                remainder = line.split(":", 1)[1].strip() if ":" in line else ""
            else:
                remainder = line
            if remainder:
                current.append(remainder)
        return responsibilities, achievements

    def _parse_education_line(self, line: str) -> dict[str, Any]:
        degree, institution = self._split_name_organization(line)
        field = ""
        if "ingenieria" in normalize_text(degree):
            field = degree
        return {
            "institution": institution,
            "degree": degree,
            "field_of_study": field,
            "education_level": "Universitario",
            "status": "En curso" if "curso" in normalize_text(line) or "estudiante" in normalize_text(line) else "Completado",
        }

    def _split_name_organization(self, line: str) -> tuple[str, str]:
        parts = re.split(r"\s+-\s+|\s+\|\s+|\s+,\s+", line, maxsplit=1)
        if len(parts) == 1:
            return parts[0].strip(), ""
        return parts[0].strip(), parts[1].strip()

    def _split_values(self, text: str) -> list[str]:
        values: list[str] = []
        for line in text.splitlines():
            normalized_line = re.sub(r"^[\-•*]\s*", "", line).strip()
            values.extend(part.strip() for part in re.split(r",|;|\|", normalized_line) if part.strip())
        return values

    def _display_name(self, canonical: str) -> str:
        upper_words = {"erp", "bi", "sql", "sap"}
        return " ".join(word.upper() if word in upper_words else word.capitalize() for word in canonical.split())

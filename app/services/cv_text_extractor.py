"""Deterministic section extraction for CV text."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from app.config import PROJECT_ROOT, load_yaml_file
from app.utils.normalization import normalize_text


DEFAULT_CV_CONFIG_PATH = PROJECT_ROOT / "config" / "cv_ingestion.yaml"


@dataclass(frozen=True)
class CVSection:
    """A detected CV section."""

    name: str
    lines: list[str]

    @property
    def text(self) -> str:
        """Return section lines joined as readable text."""

        return "\n".join(self.lines).strip()


class CVTextExtractor:
    """Split CV text into known deterministic sections."""

    def __init__(self, config_path: Path | None = None) -> None:
        config = load_yaml_file(config_path or DEFAULT_CV_CONFIG_PATH)
        self.heading_to_section: dict[str, str] = {}
        for section, headings in config.get("section_headings", {}).items():
            for heading in headings:
                self.heading_to_section[normalize_text(str(heading).rstrip(":"))] = section

    def extract_sections(self, text: str) -> dict[str, CVSection]:
        """Return detected sections, placing pre-heading lines in identity."""

        sections: dict[str, CVSection] = {}
        current = "identity"
        sections[current] = CVSection(name=current, lines=[])
        for raw_line in text.splitlines():
            line = raw_line.strip()
            if not line:
                continue
            heading_key = normalize_text(line.rstrip(":"))
            if heading_key in self.heading_to_section:
                current = self.heading_to_section[heading_key]
                sections.setdefault(current, CVSection(name=current, lines=[]))
                continue
            sections.setdefault(current, CVSection(name=current, lines=[])).lines.append(line)
        return {name: section for name, section in sections.items() if section.lines}

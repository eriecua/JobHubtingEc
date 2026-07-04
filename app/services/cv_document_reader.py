"""Local document readers for assisted CV ingestion."""

from __future__ import annotations

from dataclasses import dataclass
from io import BytesIO
from pathlib import Path
from typing import Any

from app.config import PROJECT_ROOT, load_yaml_file
from app.services.validation import ValidationError


DEFAULT_CV_CONFIG_PATH = PROJECT_ROOT / "config" / "cv_ingestion.yaml"


@dataclass(frozen=True)
class CVReaderConfig:
    """Configuration limits for uploaded CV documents."""

    supported_extensions: tuple[str, ...]
    max_file_size_mb: int
    minimum_extractable_characters: int


def load_cv_reader_config(path: Path | None = None) -> CVReaderConfig:
    """Load CV ingestion file limits from YAML."""

    data = load_yaml_file(path or DEFAULT_CV_CONFIG_PATH)
    return CVReaderConfig(
        supported_extensions=tuple(str(value).lower() for value in data.get("supported_extensions", [])),
        max_file_size_mb=int(data.get("max_file_size_mb", 5)),
        minimum_extractable_characters=int(data.get("minimum_extractable_characters", 20)),
    )


class CVDocumentReader:
    """Extract text from supported CV document bytes without storing the file."""

    def __init__(self, config: CVReaderConfig | None = None) -> None:
        self.config = config or load_cv_reader_config()

    def extract_text(self, file_name: str, content: bytes) -> str:
        """Validate and extract text from a supported CV file."""

        extension = Path(file_name).suffix.lower()
        if extension not in self.config.supported_extensions:
            allowed = ", ".join(self.config.supported_extensions)
            raise ValidationError(f"Formato no soportado. Usa: {allowed}.")

        max_bytes = self.config.max_file_size_mb * 1024 * 1024
        if len(content) > max_bytes:
            raise ValidationError(f"El archivo supera el maximo configurado de {self.config.max_file_size_mb} MB.")

        if extension == ".txt":
            text = self._read_txt(content)
        elif extension == ".pdf":
            text = self._read_pdf(content)
        elif extension == ".docx":
            text = self._read_docx(content)
        else:
            raise ValidationError("Formato no soportado.")

        text = self._clean_text(text)
        if len(text) < self.config.minimum_extractable_characters:
            raise ValidationError(
                "No se encontro texto suficiente para analizar. "
                "Si el PDF es escaneado, necesitara OCR en una fase futura."
            )
        return text

    def _read_txt(self, content: bytes) -> str:
        """Decode plain text using safe local fallbacks."""

        for encoding in ("utf-8-sig", "utf-8", "latin-1"):
            try:
                return content.decode(encoding)
            except UnicodeDecodeError:
                continue
        raise ValidationError("No se pudo decodificar el archivo de texto.")

    def _read_pdf(self, content: bytes) -> str:
        """Extract text from a selectable PDF."""

        try:
            from pypdf import PdfReader
        except ImportError as exc:
            raise ValidationError("Falta la dependencia pypdf para leer PDF.") from exc

        try:
            reader = PdfReader(BytesIO(content))
            page_text = [page.extract_text() or "" for page in reader.pages]
        except Exception as exc:  # pragma: no cover - pypdf error types vary by file
            raise ValidationError("No se pudo leer el PDF. Verifica que no este protegido o danado.") from exc
        return "\n".join(page_text)

    def _read_docx(self, content: bytes) -> str:
        """Extract body text from a DOCX document."""

        try:
            from docx import Document
        except ImportError as exc:
            raise ValidationError("Falta la dependencia python-docx para leer DOCX.") from exc

        try:
            document = Document(BytesIO(content))
        except Exception as exc:  # pragma: no cover - python-docx error types vary by file
            raise ValidationError("No se pudo leer el DOCX. Verifica que el archivo sea valido.") from exc
        return "\n".join(paragraph.text for paragraph in document.paragraphs)

    def _clean_text(self, text: Any) -> str:
        """Normalize whitespace while preserving line boundaries."""

        lines = [" ".join(str(line).strip().split()) for line in str(text or "").splitlines()]
        return "\n".join(line for line in lines if line).strip()

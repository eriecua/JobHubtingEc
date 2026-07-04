"""CSV column mapping inference, validation and preview helpers."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

import pandas as pd

from app.config import load_job_import_config
from app.services.job_import import CSV_TEMPLATE_COLUMNS
from app.services.job_normalization import JobNormalizationService


SKIP_FIELD = "__skip__"
SKIP_LABEL = "No importar esta columna"
REQUIRED_IMPORT_FIELDS = ["title", "company", "source", "description"]


@dataclass(frozen=True)
class ColumnMappingSuggestion:
    """Mapping suggestion and editable selection for a CSV column."""

    original_column: str
    inferred_field: str | None
    confidence: float
    selected_field: str
    preview_values: list[str]


@dataclass(frozen=True)
class MappingValidationResult:
    """Validation result for a selected CSV mapping."""

    is_valid: bool
    missing_required_fields: list[str]
    duplicate_fields: dict[str, list[str]]
    warnings: list[str]


class CSVMappingService:
    """Infer and validate CSV column mappings using YAML aliases."""

    def __init__(self, config: dict[str, Any] | None = None) -> None:
        self.config = config or load_job_import_config()
        self.normalizer = JobNormalizationService()
        self.target_fields = CSV_TEMPLATE_COLUMNS

    def field_options(self) -> list[str]:
        """Return UI-safe target field options including the skip option."""

        return [SKIP_FIELD, *self.target_fields]

    def infer_column(self, column: str) -> tuple[str | None, float]:
        """Infer the target field for one column and return confidence."""

        key = self.normalizer.clean_text(column).lower()
        aliases = self.config["column_aliases"]
        for field in self.target_fields:
            if key == self.normalizer.clean_text(field).lower():
                return field, 1.0
            accepted_aliases = aliases.get(field, [])
            normalized_aliases = {
                self.normalizer.clean_text(value).lower() for value in accepted_aliases
            }
            if key in normalized_aliases:
                return field, 0.85
        return None, 0.0

    def infer_mapping(self, columns: list[str]) -> dict[str, str]:
        """Infer a mapping dictionary, excluding unknown columns."""

        mapping: dict[str, str] = {}
        for column in columns:
            inferred, _confidence = self.infer_column(column)
            if inferred:
                mapping[column] = inferred
        return mapping

    def build_suggestions(
        self,
        dataframe: pd.DataFrame,
        selected_mapping: dict[str, str] | None = None,
        preview_rows: int | None = None,
    ) -> list[ColumnMappingSuggestion]:
        """Return editable suggestions with preview values for each CSV column."""

        selected_mapping = selected_mapping or {}
        rows = preview_rows or self.config["import_limits"]["preview_rows"]
        suggestions: list[ColumnMappingSuggestion] = []
        for column in dataframe.columns:
            original = str(column)
            inferred, confidence = self.infer_column(original)
            selected = selected_mapping.get(original, inferred or SKIP_FIELD)
            suggestions.append(
                ColumnMappingSuggestion(
                    original_column=original,
                    inferred_field=inferred,
                    confidence=confidence,
                    selected_field=selected,
                    preview_values=self._preview_values(dataframe[original].head(rows)),
                )
            )
        return suggestions

    def validate_mapping(self, selected_mapping: dict[str, str]) -> MappingValidationResult:
        """Validate required fields and incompatible duplicate assignments."""

        cleaned = self.clean_mapping(selected_mapping)
        assigned_fields: dict[str, list[str]] = {}
        for column, field in cleaned.items():
            assigned_fields.setdefault(field, []).append(column)
        duplicate_fields = {
            field: columns for field, columns in assigned_fields.items() if len(columns) > 1
        }
        missing_required = [
            field for field in REQUIRED_IMPORT_FIELDS if field not in assigned_fields
        ]
        warnings: list[str] = []
        if duplicate_fields:
            warnings.append("Hay columnas asignadas al mismo campo de destino.")
        if missing_required:
            warnings.append("Faltan campos obligatorios para validar la importacion.")
        return MappingValidationResult(
            is_valid=not missing_required and not duplicate_fields,
            missing_required_fields=missing_required,
            duplicate_fields=duplicate_fields,
            warnings=warnings,
        )

    def clean_mapping(self, selected_mapping: dict[str, str]) -> dict[str, str]:
        """Drop skipped or unknown assignments from a selected mapping."""

        valid_fields = set(self.target_fields)
        cleaned: dict[str, str] = {}
        for column, field in selected_mapping.items():
            if field in (None, "", SKIP_FIELD, SKIP_LABEL):
                continue
            if field in valid_fields:
                cleaned[column] = field
        return cleaned

    def _preview_values(self, values: pd.Series) -> list[str]:
        preview: list[str] = []
        for value in values.tolist():
            if pd.isna(value):
                continue
            text = str(value)
            preview.append(text[:120])
        return preview[:5]

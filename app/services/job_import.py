"""CSV import and export services for job vacancies."""

from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal
import hashlib
from io import BytesIO, StringIO
import json
from pathlib import Path
from typing import Any

import pandas as pd

from app.config import load_job_import_config
from app.models import ImportStagingJob, JobImportError
from app.models.database_models import utc_now
from app.repositories.import_repository import ImportBatchRepository, StagingJobRepository
from app.repositories.job_repository import JobRepository
from app.services.job_duplicate import JobDuplicateService
from app.services.job_normalization import JobNormalizationService
from app.services.job_quality import JobQualityService
from app.services.validation import ValidationError


CSV_TEMPLATE_COLUMNS = [
    "title",
    "company",
    "city",
    "province",
    "country",
    "modality",
    "employment_type",
    "contract_type",
    "salary_min",
    "salary_max",
    "currency",
    "salary_period",
    "publication_date",
    "expiration_date",
    "description",
    "responsibilities",
    "requirements",
    "education_required",
    "experience_min_years",
    "experience_max_years",
    "seniority_level",
    "sector",
    "source",
    "source_url",
    "external_id",
    "benefits",
    "notes",
]


class JobImportService:
    """Read, validate, stage and commit CSV job imports."""

    def __init__(self, session) -> None:
        self.session = session
        self.config = load_job_import_config()
        self.normalizer = JobNormalizationService()

    def template_csv(self) -> bytes:
        """Return a UTF-8 BOM CSV template."""

        output = StringIO()
        pd.DataFrame(columns=CSV_TEMPLATE_COLUMNS).to_csv(output, index=False)
        return output.getvalue().encode("utf-8-sig")

    def read_csv_bytes(self, content: bytes, filename: str) -> pd.DataFrame:
        """Validate file size and read CSV content."""

        max_size = self.config["import_limits"]["max_file_size_mb"] * 1024 * 1024
        if len(content) > max_size:
            raise ValidationError("El archivo supera el tamano maximo permitido.")
        if not filename.lower().endswith(".csv"):
            raise ValidationError("Solo se admiten archivos CSV.")
        try:
            dataframe = pd.read_csv(BytesIO(content), encoding="utf-8-sig")
        except UnicodeDecodeError:
            dataframe = pd.read_csv(BytesIO(content), encoding="latin-1")
        if dataframe.empty:
            raise ValidationError("El archivo CSV esta vacio.")
        if len(dataframe) > self.config["import_limits"]["max_rows"]:
            raise ValidationError("El archivo supera el numero maximo de filas permitido.")
        normalized_headers = [str(column).strip() for column in dataframe.columns]
        if len(set(normalized_headers)) != len(normalized_headers):
            raise ValidationError("El archivo contiene columnas duplicadas.")
        dataframe.columns = normalized_headers
        return dataframe.dropna(how="all")

    def infer_column_mapping(self, columns: list[str]) -> dict[str, str]:
        """Infer file-column to system-field mapping from aliases."""

        from app.services.csv_mapping import CSVMappingService

        return CSVMappingService(self.config).infer_mapping(columns)

    def stage_csv(self, content: bytes, filename: str, source_name: str | None = None, mapping: dict[str, str] | None = None) -> int:
        """Create an import batch and staging rows; does not persist jobs."""

        batch_id, _metrics = self.stage_csv_with_metrics(content, filename, source_name, mapping)
        return batch_id

    def stage_records(
        self,
        records: list[dict[str, Any]],
        *,
        source_type: str,
        source_name: str | None = None,
    ) -> int:
        """Stage already captured job-like records for human review."""

        batch_repo = ImportBatchRepository(self.session)
        batch = batch_repo.create_batch(source_type=source_type, source_name=source_name, status="Validando")
        stats = {"total_rows": len(records), "valid_rows": 0, "invalid_rows": 0, "duplicate_rows": 0}
        duplicate_service = JobDuplicateService(self.session, preload_existing=True)
        seen_hashes: set[str] = set()
        for index, raw_record in enumerate(records, start=1):
            raw_data = dict(raw_record)
            errors: list[str] = []
            warnings: list[str] = []
            parsed_data: dict[str, Any] | None = None
            validation_status = "Pendiente"
            duplicate_status = "Pendiente de revision"
            duplicate_job_id = None
            try:
                normalized, row_warnings = self.normalizer.normalize_job_data(raw_data)
                warnings.extend(row_warnings)
                quality = JobQualityService().evaluate(normalized)
                warnings.extend(quality.warnings)
                if normalized["content_hash"] in seen_hashes:
                    warnings.append("Contenido principal duplicado dentro de la captura.")
                    duplicate_status = "Duplicado exacto"
                seen_hashes.add(normalized["content_hash"])
                if duplicate_status != "Duplicado exacto":
                    duplicate = duplicate_service.detect(normalized)
                    duplicate_status = duplicate.status
                    duplicate_job_id = duplicate.job_id
                parsed_data = self._jsonable(normalized)
                validation_status = "Valida con advertencias" if warnings else "Valida"
                stats["valid_rows"] += 1
                if duplicate_status != "No duplicada":
                    stats["duplicate_rows"] += 1
            except ValidationError as exc:
                errors.append(str(exc))
                validation_status = "Invalida"
                stats["invalid_rows"] += 1
            self.session.add(
                ImportStagingJob(
                    import_batch_id=batch.id,
                    row_number=index,
                    raw_data=raw_data,
                    parsed_data=parsed_data,
                    validation_status=validation_status,
                    validation_errors=errors or None,
                    validation_warnings=warnings or None,
                    duplicate_status=duplicate_status,
                    duplicate_job_id=duplicate_job_id,
                )
            )
        for key, value in stats.items():
            setattr(batch, key, value)
        batch.status = "En revision" if records else "Completado"
        self.session.commit()
        return batch.id

    def stage_csv_with_metrics(
        self,
        content: bytes,
        filename: str,
        source_name: str | None = None,
        mapping: dict[str, str] | None = None,
    ) -> tuple[int, dict[str, Any]]:
        """Create staging rows and return local volume-verification metrics."""

        import time
        from app.services.csv_mapping import CSVMappingService

        metrics: dict[str, Any] = {
            "records_processed": 0,
            "errors_found": 0,
            "read_seconds": 0.0,
            "validation_seconds": 0.0,
            "deduplication_seconds": 0.0,
            "save_seconds": 0.0,
        }
        read_started = time.perf_counter()
        dataframe = self.read_csv_bytes(content, filename)
        metrics["read_seconds"] = round(time.perf_counter() - read_started, 6)
        mapping_service = CSVMappingService(self.config)
        mapping = mapping_service.clean_mapping(mapping or self.infer_column_mapping(list(dataframe.columns)))
        mapping_validation = mapping_service.validate_mapping(mapping)
        batch_repo = ImportBatchRepository(self.session)
        file_hash = hashlib.sha256(content).hexdigest()
        batch = batch_repo.create_batch(source_type="CSV", source_name=source_name, filename=filename, file_hash=file_hash, status="Validando")
        if not mapping_validation.is_valid:
            messages = []
            if mapping_validation.missing_required_fields:
                messages.append(
                    "Columnas obligatorias faltantes: "
                    + ", ".join(mapping_validation.missing_required_fields)
                )
            if mapping_validation.duplicate_fields:
                duplicated = ", ".join(sorted(mapping_validation.duplicate_fields))
                messages.append(f"Asignaciones duplicadas incompatibles: {duplicated}")
            message = ". ".join(messages) + "."
            batch_repo.update_status(batch.id, "Completado con errores", message)
            raise ValidationError(message)

        seen_rows: set[str] = set()
        seen_content_hashes: set[str] = set()
        stats = {"total_rows": len(dataframe), "valid_rows": 0, "invalid_rows": 0, "duplicate_rows": 0}
        duplicate_service = JobDuplicateService(self.session, preload_existing=True)
        for index, row in dataframe.iterrows():
            raw_data = {str(key): self._cell_value(value) for key, value in row.to_dict().items()}
            mapped_data = {system_field: raw_data[file_column] for file_column, system_field in mapping.items() if file_column in raw_data}
            mapped_data["raw_data"] = raw_data
            errors: list[str] = []
            warnings: list[str] = []
            parsed_data: dict[str, Any] | None = None
            validation_status = "Pendiente"
            duplicate_status = "Pendiente de revision"
            duplicate_job_id = None
            row_hash = hashlib.sha256(json.dumps(raw_data, sort_keys=True, ensure_ascii=False).encode("utf-8")).hexdigest()
            file_duplicate = False
            if row_hash in seen_rows:
                warnings.append("Fila completamente duplicada dentro del archivo.")
                duplicate_status = "Duplicado exacto"
                file_duplicate = True
            seen_rows.add(row_hash)
            try:
                validation_started = time.perf_counter()
                normalized, row_warnings = self.normalizer.normalize_job_data(mapped_data)
                warnings.extend(row_warnings)
                quality = JobQualityService().evaluate(normalized)
                warnings.extend(quality.warnings)
                metrics["validation_seconds"] += time.perf_counter() - validation_started
                if normalized["content_hash"] in seen_content_hashes:
                    warnings.append("Contenido principal duplicado dentro del archivo.")
                    duplicate_status = "Duplicado exacto"
                    file_duplicate = True
                seen_content_hashes.add(normalized["content_hash"])
                parsed_data = self._jsonable(normalized)
                dedup_started = time.perf_counter()
                duplicate = duplicate_service.detect(normalized)
                metrics["deduplication_seconds"] += time.perf_counter() - dedup_started
                if not file_duplicate:
                    duplicate_status = duplicate.status
                    duplicate_job_id = duplicate.job_id
                validation_status = "Valida con advertencias" if warnings else "Valida"
                stats["valid_rows"] += 1
                if duplicate_status != "No duplicada":
                    stats["duplicate_rows"] += 1
            except ValidationError as exc:
                errors.append(str(exc))
                validation_status = "Invalida"
                stats["invalid_rows"] += 1
                metrics["errors_found"] += 1

            save_started = time.perf_counter()
            self.session.add(
                ImportStagingJob(
                    import_batch_id=batch.id,
                    row_number=int(index) + 2,
                    raw_data=raw_data,
                    parsed_data=parsed_data,
                    validation_status=validation_status,
                    validation_errors=errors or None,
                    validation_warnings=warnings or None,
                    duplicate_status=duplicate_status,
                    duplicate_job_id=duplicate_job_id,
                )
            )
            metrics["save_seconds"] += time.perf_counter() - save_started
            metrics["records_processed"] += 1
        for key, value in stats.items():
            setattr(batch, key, value)
        batch.status = "En revision"
        save_started = time.perf_counter()
        self.session.commit()
        metrics["save_seconds"] += time.perf_counter() - save_started
        metrics["save_seconds"] = round(metrics["save_seconds"], 6)
        metrics["validation_seconds"] = round(metrics["validation_seconds"], 6)
        metrics["deduplication_seconds"] = round(metrics["deduplication_seconds"], 6)
        return batch.id, metrics

    def apply_bulk_decisions(self, batch_id: int) -> None:
        """Set default decisions for common staging states."""

        staging_repo = StagingJobRepository(self.session)
        for row in staging_repo.list_by_batch(batch_id):
            if row.validation_status == "Invalida":
                row.user_decision = "Rechazar"
            elif row.duplicate_status == "Duplicado exacto":
                row.user_decision = "Omitir"
            elif row.validation_status in {"Valida", "Valida con advertencias"}:
                row.user_decision = "Importar"
        self.session.commit()

    def process_decisions(self, batch_id: int, confirmed: bool = False) -> dict[str, int]:
        """Persist selected staging rows transactionally after explicit confirmation."""

        if not confirmed:
            raise ValidationError("Confirma la importacion antes de guardar.")
        batch_repo = ImportBatchRepository(self.session)
        staging_repo = StagingJobRepository(self.session)
        rows = staging_repo.list_by_batch(batch_id)
        stats = {"inserted_rows": 0, "updated_rows": 0, "skipped_rows": 0}
        try:
            batch = batch_repo.get_batch(batch_id)
            batch.status = "Procesando"
            job_repo = JobRepository(self.session)
            for row in rows:
                decision = row.user_decision or ("Importar" if row.validation_status in {"Valida", "Valida con advertencias"} else "Rechazar")
                if row.validation_status == "Invalida" and row.user_decision is None:
                    raise ValidationError(f"La fila {row.row_number} es invalida y requiere decision explicita.")
                if row.validation_status == "Invalida" and decision in {"Importar", "Importar como nueva", "Actualizar existente"}:
                    raise ValidationError(f"La fila {row.row_number} es invalida y no puede importarse.")
                if decision in {"Omitir", "Rechazar", "Corregir"}:
                    stats["skipped_rows"] += 1
                    continue
                if not row.parsed_data:
                    raise ValidationError(f"La fila {row.row_number} no tiene datos normalizados.")
                parsed = self._restore_types(row.parsed_data)
                parsed["import_batch_id"] = batch_id
                if decision == "Actualizar existente" and row.duplicate_job_id:
                    job_repo.update_job(row.duplicate_job_id, parsed, commit=False)
                    stats["updated_rows"] += 1
                elif decision == "Completar campos vacios" and row.duplicate_job_id:
                    job_repo.fill_empty_fields(row.duplicate_job_id, parsed, commit=False)
                    stats["updated_rows"] += 1
                else:
                    job_repo.create_job(parsed, confirm_possible_duplicate=True, source="Importacion", commit=False)
                    stats["inserted_rows"] += 1
            for key, value in stats.items():
                setattr(batch, key, value)
            status = "Completado con errores" if any(row.validation_status == "Invalida" for row in rows) else "Completado"
            batch.status = status
            batch.completed_at = utc_now()
            self.session.commit()
            return stats
        except Exception as exc:
            self.session.rollback()
            failed_batch = batch_repo.get_batch(batch_id)
            failed_batch.status = "Fallido"
            failed_batch.error_summary = str(exc)
            failed_batch.completed_at = utc_now()
            self.session.add(
                JobImportError(
                    import_batch_id=batch_id,
                    error_code="CRITICAL_IMPORT_ERROR",
                    error_message=str(exc),
                    severity="Critico",
                )
            )
            self.session.commit()
            raise

    def export_jobs_csv(self, jobs: list[Any]) -> bytes:
        """Export visible jobs to UTF-8 BOM CSV excluding internal JSON fields."""

        rows = [
            {
                "title": job.title,
                "company": job.company,
                "city": job.city,
                "province": job.province,
                "modality": job.modality,
                "source": job.source,
                "publication_date": job.publication_date.isoformat() if job.publication_date else "",
                "salary_min": job.salary_min,
                "salary_max": job.salary_max,
                "currency": job.currency,
                "status": job.status,
                "data_quality_status": job.data_quality_status,
                "is_duplicate": job.is_duplicate,
                "is_suspicious": job.is_suspicious,
                "source_url": job.source_url,
            }
            for job in jobs
        ]
        output = StringIO()
        pd.DataFrame(rows).to_csv(output, index=False)
        return output.getvalue().encode("utf-8-sig")

    def _cell_value(self, value: Any) -> Any:
        if pd.isna(value):
            return None
        return value

    def _jsonable(self, data: dict[str, Any]) -> dict[str, Any]:
        result: dict[str, Any] = {}
        for key, value in data.items():
            if isinstance(value, (Decimal, date, datetime)):
                result[key] = str(value)
            else:
                result[key] = value
        return result

    def _restore_types(self, data: dict[str, Any]) -> dict[str, Any]:
        restored = dict(data)
        for field in ["salary_min", "salary_max", "experience_min_years", "experience_max_years"]:
            if restored.get(field) not in (None, ""):
                restored[field] = Decimal(str(restored[field]))
        for field in ["publication_date", "expiration_date"]:
            if restored.get(field):
                restored[field] = datetime.strptime(str(restored[field]), "%Y-%m-%d").date()
        return restored

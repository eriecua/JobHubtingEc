from __future__ import annotations

from datetime import date
from pathlib import Path
import time

import pytest
from sqlalchemy import create_engine, func, select
from sqlalchemy.orm import Session

from app.database import create_tables
from app.models import ImportBatch, ImportStagingJob, Job, JobImportError, JobStatusHistory
from app.repositories import ImportBatchRepository, JobRepository, StagingJobRepository
from app.services.job_duplicate import JobDuplicateService
from app.services.job_import import JobImportService
from app.services.job_normalization import JobNormalizationService
from app.services.job_quality import JobQualityService, SuspiciousJobService
from app.services.validation import ValidationError


@pytest.fixture()
def session(tmp_path: Path) -> Session:
    engine = create_engine(f"sqlite:///{(tmp_path / 'jobs.db').as_posix()}", future=True)
    create_tables(engine)
    with Session(engine) as db_session:
        yield db_session


def valid_job(**overrides):
    data = {
        "title": "Coordinador de Produccion",
        "company": "Industrias Andinas S.A.",
        "city": "Guayaquil",
        "province": "Guayas",
        "modality": "Presencial",
        "employment_type": "Tiempo completo",
        "salary_min": 900,
        "salary_max": 1200,
        "currency": "USD",
        "salary_period": "Mensual",
        "publication_date": "2026-07-01",
        "description": "Coordinar lineas de produccion y seguimiento de indicadores operativos.",
        "responsibilities": "Coordinar personal operativo.",
        "requirements": "Excel intermedio.",
        "source": "Manual",
        "source_url": "https://empleos.example.com/vacante/1",
        "external_id": "JOB-1",
        "sector": "Manufactura",
    }
    data.update(overrides)
    return data


def csv_bytes(rows: list[dict[str, object]]) -> bytes:
    columns = [
        "title",
        "company",
        "city",
        "province",
        "modality",
        "employment_type",
        "salary_min",
        "salary_max",
        "currency",
        "salary_period",
        "publication_date",
        "description",
        "requirements",
        "source",
        "source_url",
        "external_id",
    ]
    lines = [",".join(columns)]
    for row in rows:
        values = []
        for column in columns:
            value = str(row.get(column, "")).replace('"', '""')
            values.append(f'"{value}"')
        lines.append(",".join(values))
    return ("\ufeff" + "\n".join(lines) + "\n").encode("utf-8")


def test_manual_job_create_validations_duplicates_and_confirm(session: Session) -> None:
    repo = JobRepository(session)
    job, duplicate = repo.create_job(valid_job())

    assert job.normalized_title == "coordinador de produccion"
    assert duplicate.status == "No duplicada"
    with pytest.raises(ValidationError, match="Campos obligatorios"):
        repo.create_job(valid_job(title=""))
    with pytest.raises(ValidationError, match="URL"):
        repo.create_job(valid_job(external_id="JOB-2", source_url="example.com/job"))
    with pytest.raises(ValidationError, match="salary_max"):
        repo.create_job(valid_job(external_id="JOB-3", source_url="https://empleos.example.com/vacante/3", salary_min=1200, salary_max=900))
    with pytest.raises(ValidationError, match="vencimiento"):
        repo.create_job(valid_job(external_id="JOB-4", source_url="https://empleos.example.com/vacante/4", expiration_date="2026-01-01"))
    with pytest.raises(ValidationError, match="requiere confirmacion"):
        repo.create_job(valid_job())
    duplicate_job, duplicate_result = repo.create_job(valid_job(source_url="https://empleos.example.com/vacante/1-copy"), confirm_possible_duplicate=True)
    assert duplicate_job.is_duplicate is True
    assert duplicate_result.status in {"Duplicado exacto", "Posible duplicado"}


def test_normalization_titles_company_location_and_dates() -> None:
    service = JobNormalizationService()
    data, warnings = service.normalize_job_data(valid_job(title="  Production Coordinator  ", company="Industrias Andinas S.A.", city="GYE"))

    assert data["normalized_title"] == "coordinador de produccion"
    assert data["normalized_company"] == "industrias andinas"
    assert data["city"] == "Guayaquil"
    assert data["province"] == "Guayas"
    assert data["title"] == "Production Coordinator"
    assert warnings == []
    ambiguous, date_warnings = service.parse_date("07/08/2026", "publication_date")
    assert ambiguous is None
    assert date_warnings


def test_csv_import_staging_decisions_and_export(session: Session) -> None:
    content = Path("examples/vacantes_ejemplo.csv").read_bytes()
    service = JobImportService(session)
    batch_id = service.stage_csv(content, "vacantes_ejemplo.csv")
    rows = StagingJobRepository(session).list_by_batch(batch_id)

    assert len(rows) == 6
    assert any(row.validation_status == "Invalida" for row in rows)
    assert any(row.validation_status == "Valida con advertencias" for row in rows)
    assert any(row.duplicate_status == "Duplicado exacto" for row in rows)
    service.apply_bulk_decisions(batch_id)
    stats = service.process_decisions(batch_id, confirmed=True)
    batch = ImportBatchRepository(session).get_batch(batch_id)

    assert stats["inserted_rows"] >= 3
    assert batch.status == "Completado con errores"
    exported = service.export_jobs_csv(JobRepository(session).list_jobs({}, limit=50))
    assert exported.startswith(b"\xef\xbb\xbf")
    assert b"raw_data" not in exported


def test_csv_alternative_headers_and_limits(session: Session) -> None:
    service = JobImportService(session)
    alt_content = Path("examples/vacantes_columnas_alternativas.csv").read_bytes()
    dataframe = service.read_csv_bytes(alt_content, "vacantes_columnas_alternativas.csv")
    mapping = service.infer_column_mapping(list(dataframe.columns))

    assert mapping["cargo"] == "title"
    assert mapping["empresa"] == "company"
    assert mapping["detalle"] == "description"
    with pytest.raises(ValidationError, match="vacio"):
        service.read_csv_bytes(b"title,company\n", "empty.csv")
    with pytest.raises(ValidationError, match="Solo"):
        service.read_csv_bytes(b"a,b\n1,2\n", "jobs.txt")


def test_staging_correction_and_invalid_row_not_imported(session: Session) -> None:
    batch = ImportBatchRepository(session).create_batch(source_type="CSV", filename="manual.csv")
    staging_repo = StagingJobRepository(session)
    row = staging_repo.save_row(
        import_batch_id=batch.id,
        row_number=2,
        raw_data={"title": "", "company": "X"},
        validation_status="Invalida",
        validation_errors=["Falta title"],
        duplicate_status="No duplicada",
    )
    with pytest.raises(ValidationError, match="invalida"):
        JobImportService(session).process_decisions(batch.id, confirmed=True)
    normalized, _warnings = JobNormalizationService().normalize_job_data(valid_job(external_id="FIX-1", source_url="https://empleos.example.com/fix-1"))
    staging_repo.update_parsed_data(row.id, JobImportService(session)._jsonable(normalized), "Valida")
    staging_repo.register_decision(row.id, "Importar")
    stats = JobImportService(session).process_decisions(batch.id, confirmed=True)
    assert stats["inserted_rows"] == 1


def test_duplicate_detection_exact_url_hash_probable_and_different(session: Session) -> None:
    repo = JobRepository(session)
    job, _ = repo.create_job(valid_job())
    duplicate_service = JobDuplicateService(session)
    normalized, _ = JobNormalizationService().normalize_job_data(valid_job())

    exact = duplicate_service.detect(normalized)
    assert exact.status == "Duplicado exacto"
    probable_data, _ = JobNormalizationService().normalize_job_data(
        valid_job(external_id="DIFF-1", source_url="https://empleos.example.com/diff-1", description="Coordinar indicadores operativos y lineas de produccion.")
    )
    probable = duplicate_service.detect(probable_data)
    assert probable.status in {"Posible duplicado", "Pendiente de revision", "Duplicado exacto"}
    different, _ = JobNormalizationService().normalize_job_data(
        valid_job(title="Disenador Grafico", company="Creativos Norte", city="Quito", external_id="DIFF-2", source_url="https://empleos.example.com/diff-2")
    )
    assert duplicate_service.detect(different).status == "No duplicada"


def test_quality_and_suspicious_rules() -> None:
    quality = JobQualityService()
    complete = quality.evaluate(valid_job())
    minimal = quality.evaluate({"title": "A", "company": "B", "source": "Manual", "description": "Breve"})
    invalid = quality.evaluate({"title": "", "company": "B"})
    suspicious = SuspiciousJobService().evaluate(
        {"title": "Asistente", "company": "Empresa Importante", "description": "Gana miles sin experiencia. Se solicita deposito previo."}
    )
    normal = SuspiciousJobService().evaluate(valid_job())

    assert complete.status == "Completa"
    assert minimal.status == "Minima"
    assert invalid.status == "Invalida"
    assert suspicious.is_suspicious is True
    assert normal.is_suspicious is False


def test_status_history_logical_delete_restore_and_tags(session: Session) -> None:
    repo = JobRepository(session)
    job, _ = repo.create_job(valid_job())
    repo.change_status(job.id, "Revisada", "Revision manual")
    repo.logical_delete(job.id, "No interesa")
    repo.restore(job.id, "Restaurar")
    repo.assign_tag(job.id, "Produccion")
    repo.assign_tag(job.id, "Produccion")
    history = repo.get_status_history(job.id)

    assert len(history) == 4
    assert repo.get_job(job.id).is_active is True
    assert len(repo.get_job(job.id).tag_assignments) == 1


def test_audit_scenario_a_ten_valid_rows_and_scenario_b_duplicate_second_import(session: Session) -> None:
    rows = [
        valid_job(
            external_id=f"BATCH-{index}",
            source_url=f"https://empleos.example.com/batch/{index}",
            title=f"Coordinador de Produccion {index}",
        )
        for index in range(10)
    ]
    content = csv_bytes(rows)
    service = JobImportService(session)

    first_batch_id = service.stage_csv(content, "diez_validas.csv")
    assert len(StagingJobRepository(session).list_by_batch(first_batch_id)) == 10
    with pytest.raises(ValidationError, match="Confirma"):
        service.process_decisions(first_batch_id, confirmed=False)
    service.apply_bulk_decisions(first_batch_id)
    first_stats = service.process_decisions(first_batch_id, confirmed=True)

    assert first_stats == {"inserted_rows": 10, "updated_rows": 0, "skipped_rows": 0}
    assert session.scalar(select(func.count(Job.id))) == 10

    second_batch_id = service.stage_csv(content, "diez_validas.csv")
    second_rows = StagingJobRepository(session).list_by_batch(second_batch_id)
    assert all(row.duplicate_status in {"Duplicado exacto", "Actualizacion potencial"} for row in second_rows)
    service.apply_bulk_decisions(second_batch_id)
    second_stats = service.process_decisions(second_batch_id, confirmed=True)

    assert second_stats["inserted_rows"] == 0
    assert second_stats["skipped_rows"] == 10
    assert session.scalar(select(func.count(Job.id))) == 10
    assert session.scalar(select(func.count(ImportBatch.id))) == 2


def test_audit_scenario_c_probable_duplicate_requires_explained_decision(session: Session) -> None:
    repo = JobRepository(session)
    repo.create_job(valid_job(external_id="PROB-1", source_url="https://empleos.example.com/prob-1"))
    candidate = valid_job(
        external_id="PROB-2",
        source_url="https://empleos.example.com/prob-2",
        publication_date="2026-07-03",
        description="Coordinar produccion, indicadores y equipos operativos en planta.",
    )
    duplicate = repo.find_duplicate_candidates(candidate)

    assert duplicate.status in {"Posible duplicado", "Pendiente de revision", "Duplicado exacto"}
    assert duplicate.score >= 70
    assert any("Cargo:" in item for item in duplicate.explanation)
    with pytest.raises(ValidationError, match="confirmacion"):
        repo.create_job(candidate)


def test_audit_scenario_d_critical_error_rolls_back_partial_jobs(session: Session) -> None:
    batch = ImportBatchRepository(session).create_batch(source_type="CSV", filename="fallo.csv")
    service = JobImportService(session)
    staging_repo = StagingJobRepository(session)
    first, _ = JobNormalizationService().normalize_job_data(valid_job(external_id="ROLL-1", source_url="https://empleos.example.com/roll-1"))
    broken = dict(first)
    broken["external_id"] = "ROLL-2"
    broken["source_url"] = "https://empleos.example.com/roll-2"
    broken["salary_min"] = "1200"
    broken["salary_max"] = "800"
    for index, parsed in enumerate([first, broken], start=2):
        row = staging_repo.save_row(
            import_batch_id=batch.id,
            row_number=index,
            raw_data={"row": index},
            parsed_data=service._jsonable(parsed),
            validation_status="Valida",
            duplicate_status="No duplicada",
            user_decision="Importar",
        )
        assert row.id

    with pytest.raises(ValidationError):
        service.process_decisions(batch.id, confirmed=True)

    failed_batch = ImportBatchRepository(session).get_batch(batch.id)
    assert failed_batch.status == "Fallido"
    assert session.scalar(select(func.count(Job.id))) == 0
    assert session.scalar(select(func.count(JobImportError.id))) == 1


def test_audit_scenario_e_update_potential_and_fill_empty_fields(session: Session) -> None:
    repo = JobRepository(session)
    existing, _ = repo.create_job(
        valid_job(
            external_id="UPD-1",
            source_url="https://empleos.example.com/upd-1",
            salary_min=None,
            salary_max=None,
            description="Descripcion base de la vacante.",
        )
    )
    improved = valid_job(
        external_id="UPD-1",
        source_url="https://empleos.example.com/upd-1",
        salary_min=900,
        salary_max=1200,
        description="Descripcion mucho mas completa con responsabilidades y requisitos adicionales.",
    )
    duplicate = repo.find_duplicate_candidates(improved)
    assert duplicate.status == "Actualizacion potencial"
    assert "salary_min" in duplicate.changed_fields

    batch = ImportBatchRepository(session).create_batch(source_type="CSV", filename="update.csv")
    parsed, _ = JobNormalizationService().normalize_job_data(improved)
    staging = StagingJobRepository(session).save_row(
        import_batch_id=batch.id,
        row_number=2,
        raw_data=improved,
        parsed_data=JobImportService(session)._jsonable(parsed),
        validation_status="Valida",
        duplicate_status="Actualizacion potencial",
        duplicate_job_id=existing.id,
        user_decision="Completar campos vacios",
    )
    assert staging.id
    JobImportService(session).process_decisions(batch.id, confirmed=True)
    updated = repo.get_job(existing.id)

    assert updated.salary_min == 900
    assert updated.description == "Descripcion base de la vacante."


def test_audit_scenarios_f_g_h_i_j_suspicious_ambiguous_bom_salary_and_filtered_export(session: Session) -> None:
    content = csv_bytes(
        [
            valid_job(
                external_id="BOM-1",
                source_url="https://empleos.example.com/bom-1",
                title="Técnico de Producción",
                company="Niñez Industrial",
                description="Gestionar producción con información técnica y revisión de calidad.",
            ),
            valid_job(
                external_id="AMB-1",
                source_url="https://empleos.example.com/amb-1",
                publication_date="04/05/2026",
            ),
            valid_job(
                external_id="BAD-SALARY",
                source_url="https://empleos.example.com/bad-salary",
                salary_min=1200,
                salary_max=800,
            ),
            valid_job(
                external_id="SUSP-1",
                source_url="https://empleos.example.com/susp-1",
                title="Asistente remoto",
                company="Empresa Importante",
                modality="Remota",
                description="Gana miles sin experiencia. Se solicita deposito previo para iniciar.",
            ),
        ]
    )
    service = JobImportService(session)
    batch_id = service.stage_csv(content, "excel_bom.csv")
    rows = StagingJobRepository(session).list_by_batch(batch_id)

    assert any(row.parsed_data and row.parsed_data["title"] == "Técnico de Producción" for row in rows)
    assert any(row.validation_warnings and "ambigua" in " ".join(row.validation_warnings) for row in rows)
    assert any(row.validation_status == "Invalida" and "salary_max" in " ".join(row.validation_errors or []) for row in rows)
    service.apply_bulk_decisions(batch_id)
    stats = service.process_decisions(batch_id, confirmed=True)
    assert stats["inserted_rows"] == 3

    suspicious_job = session.scalar(select(Job).where(Job.external_id == "SUSP-1"))
    assert suspicious_job.is_suspicious is True
    assert "deposito previo" in suspicious_job.suspicious_reason

    visible = JobRepository(session).list_jobs({"province": "Guayas", "modality": "Remota", "status": "Nueva"}, limit=50)
    exported = service.export_jobs_csv(visible)
    assert exported.startswith(b"\xef\xbb\xbf")
    assert b"raw_data" not in exported
    assert b"SUSP-1" not in exported
    assert b"Asistente remoto" in exported


def test_audit_volume_100_1000_and_configured_limit(session: Session) -> None:
    service = JobImportService(session)
    timings = {}
    for size in [100, 1000]:
        rows = [
            valid_job(
                external_id=f"VOL-{size}-{index}",
                source_url=f"https://empleos.example.com/vol/{size}/{index}",
                title=f"Analista de Procesos {index}",
            )
            for index in range(size)
        ]
        started = time.perf_counter()
        batch_id = service.stage_csv(csv_bytes(rows), f"volumen_{size}.csv")
        timings[size] = time.perf_counter() - started
        assert len(StagingJobRepository(session).list_by_batch(batch_id)) == size
    oversized_rows = [
        valid_job(
            external_id=f"LIMIT-{index}",
            source_url=f"https://empleos.example.com/limit/{index}",
        )
        for index in range(5001)
    ]
    with pytest.raises(ValidationError, match="maximo de filas"):
        service.read_csv_bytes(csv_bytes(oversized_rows), "limite.csv")
    assert timings[1000] >= 0

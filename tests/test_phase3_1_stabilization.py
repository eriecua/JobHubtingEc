from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

import pandas as pd
import pytest
from sqlalchemy import create_engine, inspect
from sqlalchemy.orm import Session

from app.database import create_tables
from app.models import CSVMappingProfile
from app.repositories.mapping_profile_repository import CSVMappingProfileRepository
from app.services.csv_mapping import CSVMappingService, SKIP_FIELD
from app.services.job_import import JobImportService
from app.services.validation import ValidationError
from tests.test_jobs_phase3 import csv_bytes, valid_job


def test_csv_mapping_inference_manual_override_skips_and_conflicts() -> None:
    dataframe = pd.DataFrame(
        [
            {
                "cargo": "Coordinador de Produccion",
                "empresa": "Industrias Andinas",
                "detalle": "Coordinar produccion.",
                "origen": "Manual",
                "columna_extra": "No relevante",
            }
        ]
    )
    service = CSVMappingService()
    suggestions = service.build_suggestions(
        dataframe,
        selected_mapping={"origen": "source", "columna_extra": SKIP_FIELD},
    )
    mapping = {item.original_column: item.selected_field for item in suggestions}

    assert mapping["cargo"] == "title"
    assert mapping["empresa"] == "company"
    assert mapping["detalle"] == "description"
    assert mapping["origen"] == "source"
    assert mapping["columna_extra"] == SKIP_FIELD
    assert suggestions[0].preview_values == ["Coordinador de Produccion"]
    assert service.validate_mapping(service.clean_mapping(mapping)).is_valid is True

    missing = service.validate_mapping({"cargo": "title", "empresa": "company"})
    assert missing.is_valid is False
    assert missing.missing_required_fields == ["source", "description"]

    duplicate = service.validate_mapping({"cargo": "title", "puesto": "title", "empresa": "company", "fuente": "source", "detalle": "description"})
    assert duplicate.is_valid is False
    assert duplicate.duplicate_fields == {"title": ["cargo", "puesto"]}


def test_csv_mapping_profiles_are_reusable_and_do_not_store_file_content(tmp_path: Path) -> None:
    engine = create_engine(f"sqlite:///{(tmp_path / 'mapping.db').as_posix()}", future=True)
    create_tables(engine)
    with Session(engine) as session:
        repo = CSVMappingProfileRepository(session)
        profile = repo.save_profile(
            "Bolsa ficticia",
            {"cargo": "title", "empresa": "company", "detalle": "description", "fuente": "source"},
        )
        loaded = repo.get_profile(profile.id)

        assert loaded.mapping["cargo"] == "title"
        assert not hasattr(loaded, "file_content")
        assert session.query(CSVMappingProfile).count() == 1

        repo.save_profile("Bolsa ficticia", {"puesto": "title", "empresa": "company", "detalle": "description", "fuente": "source"})
        assert session.query(CSVMappingProfile).count() == 1
        assert repo.get_by_source("Bolsa ficticia").mapping["puesto"] == "title"

        repo.delete_profile(profile.id)
        assert session.query(CSVMappingProfile).count() == 0


def test_stage_csv_rejects_missing_required_and_duplicate_mapping(tmp_path: Path) -> None:
    engine = create_engine(f"sqlite:///{(tmp_path / 'stage.db').as_posix()}", future=True)
    create_tables(engine)
    content = csv_bytes([valid_job()])
    with Session(engine) as session:
        service = JobImportService(session)
        with pytest.raises(ValidationError, match="obligatorias faltantes"):
            service.stage_csv(content, "faltantes.csv", mapping={"title": "title", "company": "company"})
        with pytest.raises(ValidationError, match="duplicadas incompatibles"):
            service.stage_csv(
                content,
                "duplicadas.csv",
                mapping={
                    "title": "title",
                    "company": "company",
                    "source": "source",
                    "description": "description",
                    "requirements": "description",
                },
            )


def test_volume_metrics_are_recorded_without_performance_thresholds(tmp_path: Path) -> None:
    engine = create_engine(f"sqlite:///{(tmp_path / 'volume.db').as_posix()}", future=True)
    create_tables(engine)
    with Session(engine) as session:
        service = JobImportService(session)
        max_rows = service.config["import_limits"]["max_rows"]
        for size in [100, 1000, max_rows]:
            rows = [
                valid_job(
                    external_id=f"METRIC-{size}-{index}",
                    source_url=f"https://empleos.example.com/metric/{size}/{index}",
                    title=f"Analista de Procesos {index}",
                )
                for index in range(size)
            ]
            _batch_id, metrics = service.stage_csv_with_metrics(csv_bytes(rows), f"metricas_{size}.csv")
            assert metrics["records_processed"] == size
            assert metrics["errors_found"] == 0
            for key in ["read_seconds", "validation_seconds", "deduplication_seconds", "save_seconds"]:
                assert key in metrics
                assert metrics[key] >= 0


def test_alembic_upgrade_current_history_and_downgrade_on_temporary_database(tmp_path: Path) -> None:
    database_path = tmp_path / "alembic_temp.db"
    env = os.environ.copy()
    env["RADAR_DATABASE_URL"] = f"sqlite:///{database_path.as_posix()}"

    upgrade = subprocess.run(
        [sys.executable, "-m", "alembic", "upgrade", "head"],
        cwd=Path(__file__).resolve().parent.parent,
        env=env,
        text=True,
        capture_output=True,
        check=False,
    )
    assert upgrade.returncode == 0, upgrade.stderr

    current = subprocess.run(
        [sys.executable, "-m", "alembic", "current"],
        cwd=Path(__file__).resolve().parent.parent,
        env=env,
        text=True,
        capture_output=True,
        check=False,
    )
    assert current.returncode == 0, current.stderr
    assert "202607030001" in current.stdout

    history = subprocess.run(
        [sys.executable, "-m", "alembic", "history"],
        cwd=Path(__file__).resolve().parent.parent,
        env=env,
        text=True,
        capture_output=True,
        check=False,
    )
    assert history.returncode == 0, history.stderr
    assert "Phase 3.1 baseline schema" in history.stdout
    assert "Phase 4 compatibility evaluation schema" in history.stdout
    assert "Phase 5 strategic prioritization schema" in history.stdout
    assert "Phase 5 application effort overrides" in history.stdout

    inspector = inspect(create_engine(f"sqlite:///{database_path.as_posix()}", future=True))
    assert "jobs" in inspector.get_table_names()
    assert "csv_mapping_profiles" in inspector.get_table_names()

    downgrade = subprocess.run(
        [sys.executable, "-m", "alembic", "downgrade", "base"],
        cwd=Path(__file__).resolve().parent.parent,
        env=env,
        text=True,
        capture_output=True,
        check=False,
    )
    assert downgrade.returncode == 0, downgrade.stderr

    subprocess.run(
        [sys.executable, "-m", "alembic", "upgrade", "head"],
        cwd=Path(__file__).resolve().parent.parent,
        env=env,
        text=True,
        capture_output=True,
        check=True,
    )

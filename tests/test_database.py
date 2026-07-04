from __future__ import annotations

from pathlib import Path

from sqlalchemy import create_engine, inspect
from sqlalchemy.orm import Session

from app.database import create_tables
from app.models.database_models import Base
from app.services.dashboard_metrics import get_dashboard_metrics


def test_create_temporary_database(tmp_path: Path) -> None:
    database_path = tmp_path / "radar_test.db"
    engine = create_engine(f"sqlite:///{database_path.as_posix()}", future=True)

    create_tables(engine)

    assert database_path.exists()


def test_create_required_tables(tmp_path: Path) -> None:
    database_path = tmp_path / "radar_tables.db"
    engine = create_engine(f"sqlite:///{database_path.as_posix()}", future=True)

    create_tables(engine)

    table_names = set(inspect(engine).get_table_names())
    assert {"jobs", "interactions", "applications", "recommendation_scores"} <= table_names


def test_dashboard_counters_without_records() -> None:
    engine = create_engine("sqlite:///:memory:", future=True)
    Base.metadata.create_all(bind=engine)

    with Session(engine) as session:
        metrics = get_dashboard_metrics(session)

    assert metrics.total_jobs == 0
    assert metrics.saved_jobs == 0
    assert metrics.applications == 0

"""Database engine, session, and initialization utilities."""

from __future__ import annotations

from collections.abc import Generator

from pathlib import Path

from sqlalchemy import create_engine, event, func, inspect, select, text
from sqlalchemy.engine import Engine
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session, sessionmaker

from app.config import get_settings
from app.models.database_models import Application, Base, Interaction, Job


def create_database_engine(database_url: str | None = None) -> Engine:
    """Create a SQLAlchemy engine for the configured database."""

    settings = get_settings()
    url = database_url or settings.database_url
    connect_args = {"check_same_thread": False} if url.startswith("sqlite") else {}
    db_engine = create_engine(url, connect_args=connect_args, future=True)
    if url.startswith("sqlite"):
        _enable_sqlite_foreign_keys(db_engine)
    return db_engine


def _enable_sqlite_foreign_keys(db_engine: Engine) -> None:
    """Enable SQLite foreign key checks for application-created engines."""

    @event.listens_for(db_engine, "connect")
    def set_sqlite_pragma(dbapi_connection, _connection_record) -> None:
        cursor = dbapi_connection.cursor()
        cursor.execute("PRAGMA foreign_keys=ON")
        cursor.close()


engine = create_database_engine()
SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False, future=True)


def create_tables(db_engine: Engine | None = None) -> None:
    """Create all database tables declared by the application models."""

    target_engine = db_engine or engine
    try:
        Base.metadata.create_all(bind=target_engine)
        ensure_phase3_job_columns(target_engine)
    except SQLAlchemyError as exc:
        raise RuntimeError("Could not create database tables.") from exc


def ensure_phase3_job_columns(db_engine: Engine | None = None) -> None:
    """Add Phase 3 job columns to existing SQLite databases without data loss."""

    target_engine = db_engine or engine
    if target_engine.dialect.name != "sqlite":
        return
    inspector = inspect(target_engine)
    if "jobs" not in inspector.get_table_names():
        return
    existing_columns = {column["name"] for column in inspector.get_columns("jobs")}
    column_definitions = {
        "normalized_company": "VARCHAR(255)",
        "source_record_id": "VARCHAR(255)",
        "country": "VARCHAR(120) NOT NULL DEFAULT 'Ecuador'",
        "city": "VARCHAR(120)",
        "location_raw": "VARCHAR(255)",
        "workplace_type": "VARCHAR(80)",
        "employment_type": "VARCHAR(80)",
        "contract_type": "VARCHAR(80)",
        "schedule_type": "VARCHAR(80)",
        "salary_period": "VARCHAR(80)",
        "salary_is_estimated": "BOOLEAN NOT NULL DEFAULT 0",
        "benefits": "TEXT",
        "responsibilities": "TEXT",
        "requirements": "TEXT",
        "education_required": "TEXT",
        "experience_min_years": "NUMERIC(4, 1)",
        "experience_max_years": "NUMERIC(4, 1)",
        "seniority_level": "VARCHAR(120)",
        "languages_required": "TEXT",
        "travel_required": "BOOLEAN",
        "relocation_required": "BOOLEAN",
        "sector": "VARCHAR(160)",
        "department": "VARCHAR(160)",
        "category": "VARCHAR(160)",
        "vacancies_count": "INTEGER",
        "captured_at": "DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP",
        "last_seen_at": "DATETIME",
        "data_quality_status": "VARCHAR(80) NOT NULL DEFAULT 'Minima'",
        "is_duplicate": "BOOLEAN NOT NULL DEFAULT 0",
        "duplicate_of_job_id": "INTEGER",
        "is_suspicious": "BOOLEAN NOT NULL DEFAULT 0",
        "suspicious_reason": "TEXT",
        "is_remote": "BOOLEAN NOT NULL DEFAULT 0",
        "is_active": "BOOLEAN NOT NULL DEFAULT 1",
        "review_status": "VARCHAR(80) NOT NULL DEFAULT 'Pendiente'",
        "notes": "TEXT",
        "import_batch_id": "INTEGER",
        "raw_data": "JSON",
        "content_hash": "VARCHAR(128)",
        "deduplication_key": "VARCHAR(500)",
    }
    with target_engine.begin() as connection:
        for column_name, ddl_type in column_definitions.items():
            if column_name not in existing_columns:
                connection.execute(text(f"ALTER TABLE jobs ADD COLUMN {column_name} {ddl_type}"))
    settings = get_settings()
    for relative_dir in ["data/imports", "data/temp", "data/exports"]:
        Path(settings.project_root / relative_dir).mkdir(parents=True, exist_ok=True)


def get_session() -> Generator[Session, None, None]:
    """Yield a database session for app and service usage."""

    session = SessionLocal()
    try:
        yield session
    finally:
        session.close()


def is_database_available(db_engine: Engine | None = None) -> bool:
    """Check whether the configured database can be reached."""

    target_engine = db_engine or engine
    try:
        with target_engine.connect():
            return True
    except SQLAlchemyError:
        return False


def get_table_names(db_engine: Engine | None = None) -> list[str]:
    """Return the table names currently available in the database."""

    target_engine = db_engine or engine
    return inspect(target_engine).get_table_names()


def get_empty_dashboard_counts(session: Session) -> dict[str, int]:
    """Return dashboard counters, safely reporting zero when no rows exist."""

    return {
        "total_jobs": session.scalar(select(func.count(Job.id))) or 0,
        "saved_jobs": session.scalar(
            select(func.count(Interaction.id)).where(Interaction.action == "guardada")
        )
        or 0,
        "applications": session.scalar(select(func.count(Application.id))) or 0,
    }

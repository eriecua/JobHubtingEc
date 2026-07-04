"""Dashboard metrics service."""

from __future__ import annotations

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.database import SessionLocal, create_tables, is_database_available
from app.models.database_models import Application, Interaction, Job
from app.schemas import DashboardMetrics, DashboardSnapshot


def get_dashboard_metrics(session: Session) -> DashboardMetrics:
    """Return minimal dashboard counters without exposing SQL to the UI."""

    total_jobs = session.scalar(select(func.count(Job.id))) or 0
    saved_jobs = session.scalar(
        select(func.count(Interaction.id)).where(Interaction.action == "guardada")
    ) or 0
    applications = session.scalar(select(func.count(Application.id))) or 0

    return DashboardMetrics(
        total_jobs=total_jobs,
        saved_jobs=saved_jobs,
        applications=applications,
    )


def get_dashboard_snapshot() -> DashboardSnapshot:
    """Create tables if needed and return the current dashboard state."""

    create_tables()
    database_available = is_database_available()
    if not database_available:
        return DashboardSnapshot(database_available=False)

    with SessionLocal() as session:
        metrics = get_dashboard_metrics(session)

    return DashboardSnapshot(database_available=True, metrics=metrics)

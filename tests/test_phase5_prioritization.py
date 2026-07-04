from __future__ import annotations

from copy import deepcopy
from datetime import date, timedelta
from pathlib import Path
import os
import subprocess
import sys
import time

from sqlalchemy import create_engine, inspect
from sqlalchemy.orm import Session

from app.config import load_priority_config
from app.database import create_tables
from app.models import JobEvaluation
from app.repositories import CareerPreferenceRepository, PrioritizationRepository, ProfileRepository, ToolRepository
from app.services.decision_service import DecisionService
from app.services.evaluation_engine import EvaluationEngineService
from app.services.prioritization import PrioritizationService
from app.services.saved_view_service import SavedViewService
from app.services.shortlist_service import ShortlistService
from app.services.urgency import UrgencyService
from app.services.validation import ValidationError
from app.ui.strategic_inbox_pages import _daily_mix
from tests.test_phase4_compatibility import _job, _profile


def _session(tmp_path: Path) -> Session:
    engine = create_engine(f"sqlite:///{(tmp_path / 'phase5.db').as_posix()}", future=True)
    create_tables(engine)
    return Session(engine)


def _evaluated_priority(session: Session, job, profile):
    EvaluationEngineService(session).evaluate_job(job.id, profile.id)
    PrioritizationService(session).prioritize_job(job.id, profile.id)
    return PrioritizationRepository(session).latest_priority(job.id, profile.id)


def test_phase5_priority_config_validation() -> None:
    config = load_priority_config()
    assert sum(config["priority_weights"].values()) == 100
    assert config["priority_thresholds"]["critical"] > config["priority_thresholds"]["high"]
    assert all(0 <= value <= 1 for value in config["daily_mix"].values())
    assert config["daily_inbox"]["max_items"] > 0

    broken = deepcopy(config)
    broken["priority_weights"]["compatibility"] = 34
    try:
        from app.config import PriorityWeights

        PriorityWeights(**broken["priority_weights"])
    except ValueError as exc:
        assert "sum 100" in str(exc)
    else:
        raise AssertionError("Broken priority weights should fail validation.")


def test_phase5_urgency_bands_and_expiration() -> None:
    config = load_priority_config()
    service = UrgencyService(config)

    class JobLike:
        status = "Activa"
        expiration_date = None

        def __init__(self, publication_date=None, expiration_date=None, status="Activa"):
            self.publication_date = publication_date
            self.expiration_date = expiration_date
            self.status = status

    today = date.today()
    fresh = service.score(JobLike(today))[0]
    seven = service.score(JobLike(today - timedelta(days=7)))[0]
    thirty = service.score(JobLike(today - timedelta(days=30)))[0]
    tomorrow = service.score(JobLike(today - timedelta(days=20), today + timedelta(days=1)))[0]
    ten_days = service.score(JobLike(today - timedelta(days=20), today + timedelta(days=10)))[0]
    unknown = service.score(JobLike(None))[0]
    expired_raw, _deadline, _reasons, _warnings, blockers = service.score(JobLike(today - timedelta(days=2), today - timedelta(days=1)))

    assert fresh > seven > thirty
    assert tomorrow > ten_days
    assert unknown > 0
    assert expired_raw == 0
    assert blockers


def test_phase5_required_scenarios_actions_precedence_and_rounding(tmp_path: Path) -> None:
    session = _session(tmp_path)
    profile = _profile(session)
    CareerPreferenceRepository(session).add_constraint(profile.id, constraint_type="Salario minimo obligatorio", operator="Mayor o igual", value="900")
    ToolRepository(session).create_or_get_tool("Power BI", "BI")
    repo = PrioritizationRepository(session)

    high = _job(session, external_id="p5-A", source_url="https://empleos.example.com/p5-A")
    review = _job(session, external_id="p5-B", source_url="https://empleos.example.com/p5-B", salary_min=None, salary_max=None, requirements=None, publication_date=None)
    growth = _job(
        session,
        external_id="p5-C",
        source_url="https://empleos.example.com/p5-C",
        title="Coordinador de Excelencia Operacional",
        requirements="Obligatorio Lean Manufacturing. Deseable Power BI. Deseable ingles.",
        sector="Manufactura",
    )
    old = _job(
        session,
        external_id="p5-D",
        source_url="https://empleos.example.com/p5-D",
        publication_date=(date.today() - timedelta(days=50)).isoformat(),
    )
    low_salary = _job(session, external_id="p5-E", source_url="https://empleos.example.com/p5-E", salary_min=600, salary_max=700)
    incomplete = _job(
        session,
        external_id="p5-F",
        source_url=None,
        salary_min=None,
        salary_max=None,
        requirements=None,
        description="Vacante general.",
    )
    urgent = _job(
        session,
        external_id="p5-G",
        source_url="https://empleos.example.com/p5-G",
        title="Analista de Logistica",
        expiration_date=(date.today() + timedelta(days=1)).isoformat(),
        salary_min=950,
        salary_max=1000,
    )

    high_priority = _evaluated_priority(session, high, profile)
    review_priority = _evaluated_priority(session, review, profile)
    growth_priority = _evaluated_priority(session, growth, profile)
    old_priority = _evaluated_priority(session, old, profile)
    low_salary_priority = _evaluated_priority(session, low_salary, profile)
    incomplete_priority = _evaluated_priority(session, incomplete, profile)
    urgent_priority = _evaluated_priority(session, urgent, profile)

    assert high_priority.priority_score >= 90
    assert high_priority.recommended_action == "Postular"
    assert review_priority.recommended_action == "Revisar"
    assert growth_priority.recommended_action in {"Explorar", "Preparar postulacion"}
    assert old_priority.priority_score < high_priority.priority_score
    assert old_priority.recommended_action == "Revisar"
    assert low_salary_priority.recommended_action == "Descartar"
    assert incomplete_priority.recommended_action in {"Revisar", "Esperar informacion"}
    assert urgent_priority.urgency_score > old_priority.urgency_score
    assert urgent_priority.priority_score > old_priority.priority_score

    daily = _daily_mix([high_priority, review_priority, growth_priority, old_priority, urgent_priority], load_priority_config())
    assert len(daily) <= load_priority_config()["daily_inbox"]["max_items"]
    assert len({item.id for item in daily}) == len(daily)
    assert high_priority in daily

    for priority in [high_priority, review_priority, growth_priority, old_priority, low_salary_priority, incomplete_priority, urgent_priority]:
        components = next(reason for reason in priority.reasons if reason["factor"] == "componentes")["detail"]
        component_sum = round(sum(component["awarded_points"] for component in components), 2)
        assert float(priority.priority_score) == component_sum
        assert 0 <= float(priority.priority_score) <= 100
        assert all(0 <= component["raw_score"] <= 1 and component["awarded_points"] <= component["weight"] for component in components)

    duplicate = _job(session, external_id="p5-duplicate", source_url="https://empleos.example.com/p5-duplicate")
    duplicate.is_duplicate = True
    session.commit()
    duplicate_priority = _evaluated_priority(session, duplicate, profile)
    assert duplicate_priority.recommended_action == "Revisar"

    no_evaluation = _job(session, external_id="p5-no-eval", source_url="https://empleos.example.com/p5-no-eval")
    PrioritizationService(session).prioritize_job(no_evaluation.id, profile.id)
    assert repo.latest_priority(no_evaluation.id, profile.id).recommended_action == "Revisar"

    stale_job = _job(session, external_id="p5-stale-eval", source_url="https://empleos.example.com/p5-stale-eval")
    EvaluationEngineService(session).evaluate_job(stale_job.id, profile.id)
    evaluation = repo.latest_evaluation(stale_job.id, profile.id)
    evaluation.is_stale = True
    session.commit()
    PrioritizationService(session).prioritize_job(stale_job.id, profile.id)
    assert repo.latest_priority(stale_job.id, profile.id).recommended_action == "Revisar"
    session.close()


def test_phase5_decisions_applications_shortlists_saved_views_and_staleness(tmp_path: Path) -> None:
    session = _session(tmp_path)
    profile = _profile(session)
    job = _job(session, external_id="p5-decision", source_url="https://empleos.example.com/p5-decision")
    priority = _evaluated_priority(session, job, profile)
    repo = PrioritizationRepository(session)

    decision = DecisionService(session).record_decision(
        job.id,
        profile.id,
        "Preparar postulacion",
        priority_id=priority.id,
        reason_code="Alta compatibilidad",
        notes="Preparar CV base ficticio.",
        follow_up_date=date.today() + timedelta(days=1),
    )
    assert decision.decision == "Preparar postulacion"
    assert repo.application_exists(job.id) is True
    assert repo.latest_priority(job.id, profile.id).is_stale is True
    assert len(repo.list_decisions(profile.id)) == 1

    try:
        DecisionService(session).record_decision(job.id, profile.id, "Postular", priority_id=priority.id)
    except ValidationError as exc:
        assert "Ya existe una postulacion" in str(exc)
    else:
        raise AssertionError("Duplicate application should be rejected.")
    assert len(repo.list_decisions(profile.id)) == 1

    fresh_priority = _evaluated_priority(session, job, profile)
    PrioritizationService(session).set_effort_override(job.id, profile.id, "Alto", "Formulario largo ficticio.")
    assert repo.get_effort_override(job.id, profile.id).effort_level == "Alto"
    assert repo.latest_priority(job.id, profile.id).is_stale is True
    PrioritizationService(session).prioritize_job(job.id, profile.id)
    effort_priority = repo.latest_priority(job.id, profile.id)
    effort_components = next(reason for reason in effort_priority.reasons if reason["factor"] == "componentes")["detail"]
    effort_component = next(component for component in effort_components if component["name"] == "application_effort")
    assert effort_component["raw_score"] == load_priority_config()["application_effort"]["Alto"]

    shortlist_service = ShortlistService(session)
    shortlist = shortlist_service.create_for_date(profile.id)
    item_a = shortlist_service.add_job(shortlist.id, job.id, fresh_priority.id, "Preparar postulacion")
    other = _job(session, external_id="p5-shortlist-other", source_url="https://empleos.example.com/p5-shortlist-other")
    other_priority = _evaluated_priority(session, other, profile)
    item_b = shortlist_service.add_job(shortlist.id, other.id, other_priority.id, "Explorar")
    moved = shortlist_service.reorder(item_b.id, 1)
    assert moved.position == 1
    assert shortlist_service.complete(item_a.id, "Completada").completion_status == "Completada"
    assert shortlist_service.archive(shortlist.id).status == "Archivada"

    view_service = SavedViewService(session)
    first = view_service.create(profile.id, "Mejores para hoy", {"recommended_action": "Postular"}, {"field": "priority_score"}, True)
    second = view_service.create(profile.id, "Pendientes de revisar", {"recommended_action": "Revisar"}, {"field": "urgency_score"}, True)
    views = repo.list_saved_views(profile.id)
    assert sum(1 for view in views if view.is_default) == 1
    assert second.is_default is True
    view_service.rename(first.id, "Mejores para esta semana")
    view_service.delete(first.id, confirmed=True)
    assert all(view.id != first.id for view in repo.list_saved_views(profile.id))
    try:
        view_service.create(profile.id, "Filtro invalido", {"campo_raro": "x"}, {"field": "priority_score"})
    except ValidationError as exc:
        assert "Filtros no permitidos" in str(exc)
    else:
        raise AssertionError("Invalid saved view filter should fail.")

    changed = deepcopy(load_priority_config())
    changed["priority_weights"] = {**changed["priority_weights"], "compatibility": 34, "application_effort": 6}
    fresh = _evaluated_priority(session, other, profile)
    assert PrioritizationService(session, changed).mark_stale_for_current_state(other.id, profile.id) is True
    assert repo.latest_priority(other.id, profile.id).is_stale is True

    fresh = _evaluated_priority(session, other, profile)
    ProfileRepository(session).update_profile(profile.id, professional_summary="Cambio de perfil para auditoria.")
    assert PrioritizationService(session).mark_stale_for_current_state(other.id, profile.id) is True

    fresh = _evaluated_priority(session, other, profile)
    CareerPreferenceRepository(session).set_preferences(
        profile.id,
        preferred_cities=["Guayaquil"],
        preferred_provinces=["Guayas"],
        accepted_modalities=["Presencial"],
        minimum_salary=950,
        expected_salary=1250,
        currency="USD",
    )
    assert PrioritizationService(session).mark_stale_for_current_state(other.id, profile.id) is True

    stalled = repo.find_stalled_priorities(profile.id, load_priority_config()["stale_decisions"], today=date.today() + timedelta(days=20))
    assert stalled
    session.close()


def test_phase5_alembic_upgrade_downgrade_on_temporary_database(tmp_path: Path) -> None:
    database_path = tmp_path / "phase5_alembic.db"
    env = os.environ.copy()
    env["RADAR_DATABASE_URL"] = f"sqlite:///{database_path.as_posix()}"
    root = Path(__file__).resolve().parent.parent

    upgrade = subprocess.run([sys.executable, "-m", "alembic", "upgrade", "head"], cwd=root, env=env, text=True, capture_output=True, check=False)
    assert upgrade.returncode == 0, upgrade.stderr
    tables = inspect(create_engine(f"sqlite:///{database_path.as_posix()}", future=True)).get_table_names()
    assert {"prioritization_runs", "job_priorities", "job_decisions", "saved_views", "daily_shortlists", "daily_shortlist_items", "application_effort_overrides"} <= set(tables)

    current = subprocess.run([sys.executable, "-m", "alembic", "current"], cwd=root, env=env, text=True, capture_output=True, check=False)
    assert "202607030001" in current.stdout

    downgrade = subprocess.run([sys.executable, "-m", "alembic", "downgrade", "202607020003"], cwd=root, env=env, text=True, capture_output=True, check=False)
    assert downgrade.returncode == 0, downgrade.stderr
    downgraded_tables = inspect(create_engine(f"sqlite:///{database_path.as_posix()}", future=True)).get_table_names()
    assert "job_priorities" in downgraded_tables
    assert "application_effort_overrides" not in downgraded_tables


def test_phase5_local_volume_verification(tmp_path: Path) -> None:
    session = _session(tmp_path)
    profile = _profile(session)
    jobs = [
        _job(
            session,
            external_id=f"p5-volume-{index}",
            source_url=f"https://empleos.example.com/p5-volume-{index}",
            title="Supervisor de Produccion" if index % 2 == 0 else "Analista de Logistica",
        )
        for index in range(10)
    ]
    evaluation_engine = EvaluationEngineService(session)
    prioritization = PrioritizationService(session)

    start = time.perf_counter()
    for job in jobs:
        evaluation_engine.evaluate_job(job.id, profile.id)
    evaluation_time = time.perf_counter() - start

    start = time.perf_counter()
    result = prioritization.prioritize_jobs([job.id for job in jobs], profile.id)
    prioritization_time = time.perf_counter() - start

    assert result["jobs_prioritized"] == 10
    assert result["jobs_failed"] == 0
    assert evaluation_time >= 0
    assert prioritization_time >= 0
    session.close()

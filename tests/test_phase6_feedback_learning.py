from __future__ import annotations

from copy import deepcopy
from datetime import date, datetime, timedelta
from pathlib import Path
import os
import subprocess
import sys

from sqlalchemy import create_engine, inspect
from sqlalchemy.orm import Session

from app.config import FeedbackLearningConfig, load_feedback_learning_config
from app.database import create_tables
from app.models import FeedbackEvent, ProfessionalProfile
from app.repositories import FeedbackRepository, PrioritizationRepository
from app.services.decision_service import DecisionService
from app.services.application_outcome_service import ApplicationOutcomeService
from app.services.feedback_service import FeedbackService
from app.services.learning_service import LearningService
from app.services.validation import ValidationError
from tests.test_phase4_compatibility import _job, _profile
from tests.test_phase5_prioritization import _evaluated_priority


def _session(tmp_path: Path) -> Session:
    engine = create_engine(f"sqlite:///{(tmp_path / 'phase6.db').as_posix()}", future=True)
    create_tables(engine)
    return Session(engine)


def test_phase6_feedback_config_validation() -> None:
    config = load_feedback_learning_config()
    assert config["learning_version"] == "phase6.1"
    assert config["feedback_signal_weights"]["outcomes"]["accepted_offer"] > config["feedback_signal_weights"]["outcomes"]["offer"]
    assert config["feedback_signal_weights"]["implicit"]["viewed_detail"] < config["feedback_signal_weights"]["explicit"]["applied"]

    broken = deepcopy(config)
    broken["feedback_signal_weights"]["explicit"]["saved"] = 9
    try:
        FeedbackLearningConfig(**broken)
    except ValueError as exc:
        assert "out of bounds" in str(exc)
    else:
        raise AssertionError("Out-of-range feedback signals should fail validation.")


def test_phase6_tables_created_on_temporary_database(tmp_path: Path) -> None:
    session = _session(tmp_path)
    table_names = set(inspect(session.bind).get_table_names())
    assert {
        "feedback_events",
        "application_outcomes",
        "learning_runs",
        "learning_metrics",
        "adjustment_proposals",
        "configuration_change_history",
    } <= table_names
    session.close()


def test_phase6_feedback_events_are_weighted_and_deduplicated(tmp_path: Path) -> None:
    session = _session(tmp_path)
    profile = _profile(session)
    job = _job(session, external_id="p6-event", source_url="https://empleos.example.com/p6-event")
    service = FeedbackService(session)

    first = service.register_event(
        profile.id,
        job.id,
        "saved",
        "Explicita",
        "Usuario",
        deduplication_key="manual:p6-event:saved",
        occurred_at=datetime(2026, 7, 1, 8, 0, 0),
    )
    second = service.register_event(
        profile.id,
        job.id,
        "saved",
        "Explicita",
        "Usuario",
        deduplication_key="manual:p6-event:saved",
        occurred_at=datetime(2026, 7, 1, 8, 0, 0),
    )
    assert first["inserted"] is True
    assert second["inserted"] is False
    assert float(first["event"].signal_value) == load_feedback_learning_config()["feedback_signal_weights"]["explicit"]["saved"]

    try:
        service.register_event(profile.id, job.id, "saved", "Explicita", "Usuario", signal_value=9)
    except ValidationError as exc:
        assert "fuera de los limites" in str(exc)
    else:
        raise AssertionError("Out-of-range explicit signal value should fail.")
    session.close()


def test_phase6_application_outcome_creates_feedback_signal_and_updates_application(tmp_path: Path) -> None:
    session = _session(tmp_path)
    profile = _profile(session)
    job = _job(session, external_id="p6-outcome", source_url="https://empleos.example.com/p6-outcome")
    application = PrioritizationRepository(session).create_application(job.id, status="Postulada", application_date=date.today() - timedelta(days=2))

    result = ApplicationOutcomeService(session).record_outcome(
        application.id,
        profile.id,
        "Entrevista",
        date.today(),
        "Entrevista inicial",
        "Contacto de reclutador",
    )
    session.refresh(application)
    assert result["outcome"].outcome_type == "Entrevista"
    assert result["feedback_event"].event_type == "interview"
    assert application.interview_date == date.today()

    try:
        ApplicationOutcomeService(session).record_outcome(
            application.id,
            profile.id,
            "Oferta",
            date.today() - timedelta(days=10),
            "Oferta",
            "Oferta",
        )
    except ValidationError as exc:
        assert "anterior a la postulacion" in str(exc)
    else:
        raise AssertionError("Outcome before application date should fail.")
    session.close()


def test_phase6_1_outcomes_reject_contradictions_and_metrics_use_unique_applications(tmp_path: Path) -> None:
    session = _session(tmp_path)
    profile = _profile(session)
    today = date.today()
    job = _job(session, external_id="p6-unique-metrics", source_url="https://empleos.example.com/p6-unique-metrics")
    application = PrioritizationRepository(session).create_application(
        job.id,
        profile_id=profile.id,
        status="Postulada",
        application_date=today - timedelta(days=5),
    )
    outcome_service = ApplicationOutcomeService(session)
    for outcome_type in ["Entrevista", "Segunda entrevista", "Entrevista final"]:
        outcome_service.record_outcome(application.id, profile.id, outcome_type, today, outcome_type, outcome_type)

    result = LearningService(session).run_analysis(profile.id, today - timedelta(days=10), today)
    metrics = {metric.metric_name: float(metric.metric_value) for metric in FeedbackRepository(session).list_metrics(result["run_id"])}
    assert metrics["entrevistas_sobre_postulaciones"] == 1.0

    terminal_job = _job(session, external_id="p6-terminal", source_url="https://empleos.example.com/p6-terminal")
    terminal_application = PrioritizationRepository(session).create_application(
        terminal_job.id,
        profile_id=profile.id,
        status="Postulada",
        application_date=today - timedelta(days=5),
    )
    outcome_service.record_outcome(terminal_application.id, profile.id, "Oferta aceptada", today, "Oferta aceptada", "Aceptada")
    try:
        outcome_service.record_outcome(terminal_application.id, profile.id, "Rechazo", today, "Rechazo", "Rechazo")
    except ValidationError as exc:
        assert "resultado terminal" in str(exc) or "resultado negativo" in str(exc)
    else:
        raise AssertionError("Contradictory terminal outcomes should fail.")
    session.close()


def test_phase6_1_implicit_events_profile_references_and_decisions_are_stabilized(tmp_path: Path) -> None:
    session = _session(tmp_path)
    profile = _profile(session)
    job = _job(session, external_id="p6-stabilized-events", source_url="https://empleos.example.com/p6-stabilized-events")
    priority = _evaluated_priority(session, job, profile)
    feedback = FeedbackService(session)

    first = feedback.register_event(
        profile.id,
        job.id,
        "viewed_detail",
        "Implicita",
        "Interfaz",
        occurred_at=datetime(2026, 7, 1, 8, 0, 0),
    )
    second = feedback.register_event(
        profile.id,
        job.id,
        "viewed_detail",
        "Implicita",
        "Interfaz",
        occurred_at=datetime(2026, 7, 1, 8, 0, 1),
    )
    assert first["inserted"] is True
    assert second["inserted"] is False

    other_profile = ProfessionalProfile(
        full_name="Perfil Secundario",
        professional_title="Otro perfil",
        country="Ecuador",
        is_primary=False,
        is_active=True,
    )
    session.add(other_profile)
    session.commit()
    try:
        feedback.register_event(other_profile.id, job.id, "saved", "Explicita", "Usuario", priority_id=priority.id)
    except ValidationError as exc:
        assert "prioridad no corresponde" in str(exc)
    else:
        raise AssertionError("Mismatched priority/profile references should fail.")

    DecisionService(session).record_decision(job.id, profile.id, "Guardar", priority_id=priority.id, reason_code="Alta compatibilidad")
    assert session.query(FeedbackEvent).filter(FeedbackEvent.event_type == "saved", FeedbackEvent.profile_id == profile.id).count() == 1
    session.close()


def test_phase6_learning_run_generates_metrics_warnings_and_no_strong_proposals_with_low_sample(tmp_path: Path) -> None:
    session = _session(tmp_path)
    profile = _profile(session)
    job = _job(session, external_id="p6-low-sample", source_url="https://empleos.example.com/p6-low-sample")
    FeedbackService(session).record_viewed_detail(profile.id, job.id)

    result = LearningService(session).run_analysis(profile.id, date.today() - timedelta(days=5), date.today())
    repo = FeedbackRepository(session)
    run = repo.get_learning_run(result["run_id"])
    metrics = repo.list_metrics(run.id)
    proposals = repo.list_proposals(profile.id)

    assert run.status == "Completado con observaciones"
    assert metrics
    assert proposals == []
    assert any("Muestra insuficiente" in warning for warning in (run.warnings_json or []))
    session.close()


def test_phase6_1_proposals_expire_deduplicate_and_require_real_outcomes(tmp_path: Path) -> None:
    session = _session(tmp_path)
    profile = _profile(session)
    today = date.today()
    repo = PrioritizationRepository(session)
    jobs_a = [
        _job(
            session,
            external_id=f"p6-guarded-a-{index}",
            source="Fuente A",
            source_url=f"https://empleos.example.com/p6-guarded-a-{index}",
            requirements="Obligatorio Excel. Minimo 2 anos de experiencia.",
        )
        for index in range(5)
    ]
    jobs_b = [
        _job(
            session,
            external_id=f"p6-guarded-b-{index}",
            source="Fuente B",
            source_url=f"https://empleos.example.com/p6-guarded-b-{index}",
            requirements="Obligatorio Excel. Minimo 2 anos de experiencia.",
        )
        for index in range(5)
    ]
    applications = [
        repo.create_application(job.id, profile_id=profile.id, status="Postulada", application_date=today - timedelta(days=3))
        for job in [*jobs_a, *jobs_b]
    ]
    for job in [*jobs_a, *jobs_b]:
        _evaluated_priority(session, job, profile)

    service = LearningService(session)
    low_result = service.run_analysis(profile.id, today - timedelta(days=10), today)
    assert low_result["proposals"] == 0
    assert any("resultados reales insuficientes" in warning for warning in low_result["warnings"])

    outcome_service = ApplicationOutcomeService(session)
    for application in applications[:3]:
        outcome_service.record_outcome(application.id, profile.id, "Entrevista", today, "Entrevista inicial", "Contacto")

    first = service.run_analysis(profile.id, today - timedelta(days=10), today)
    second = service.run_analysis(profile.id, today - timedelta(days=10), today)
    proposals = FeedbackRepository(session).list_proposals(profile.id)
    assert first["proposals"] == 1
    assert second["proposals"] == 0
    assert sum(1 for proposal in proposals if proposal.target_key == "source:Fuente A") == 1
    assert proposals[0].expires_at is not None

    proposals[0].expires_at = datetime(2026, 1, 1)
    session.commit()
    expired = service.run_analysis(profile.id, today - timedelta(days=10), today)
    assert any("propuestas vencidas" in warning for warning in expired["warnings"])
    assert FeedbackRepository(session).get_proposal(proposals[0].id).status == "Expirada"
    session.close()


def test_phase6_learning_proposals_require_review_apply_and_revert(tmp_path: Path) -> None:
    session = _session(tmp_path)
    profile = _profile(session)
    today = date.today()

    jobs_a = [
        _job(session, external_id=f"p6-source-a-{index}", source="Fuente A", source_url=f"https://empleos.example.com/p6-a-{index}")
        for index in range(5)
    ]
    jobs_b = [
        _job(session, external_id=f"p6-source-b-{index}", source="Fuente B", source_url=f"https://empleos.example.com/p6-b-{index}")
        for index in range(5)
    ]
    repo = PrioritizationRepository(session)
    applications = [repo.create_application(job.id, status="Postulada", application_date=today - timedelta(days=3)) for job in [*jobs_a, *jobs_b]]
    for job in [*jobs_a, *jobs_b]:
        priority = _evaluated_priority(session, job, profile)
        assert priority.profile_id == profile.id
    outcome_service = ApplicationOutcomeService(session)
    for application in applications[:3]:
        outcome_service.record_outcome(application.id, profile.id, "Entrevista", today, "Entrevista inicial", "Contacto")

    result = LearningService(session).run_analysis(profile.id, today - timedelta(days=10), today)
    feedback_repo = FeedbackRepository(session)
    proposals = feedback_repo.list_proposals(profile.id)
    assert result["proposals"] >= 1
    assert any(proposal.target_key == "source:Fuente A" for proposal in proposals)

    proposal = next(proposal for proposal in proposals if proposal.target_key == "source:Fuente A")
    service = LearningService(session)
    service.review_proposal(proposal.id, approve=True, reviewed_by="Usuario pruebas")
    change = service.apply_proposal(proposal.id, changed_by="Usuario pruebas")
    assert change.proposal_id == proposal.id
    assert feedback_repo.get_proposal(proposal.id).status == "Aplicada"
    reverted = service.revert_proposal(proposal.id, reverted_by="Usuario pruebas")
    assert reverted.reverted_at is not None
    assert feedback_repo.get_proposal(proposal.id).status == "Revertida"
    session.close()


def test_phase6_alembic_upgrade_downgrade_on_temporary_database(tmp_path: Path) -> None:
    database_path = tmp_path / "phase6_alembic.db"
    env = os.environ.copy()
    env["RADAR_DATABASE_URL"] = f"sqlite:///{database_path.as_posix()}"
    root = Path(__file__).resolve().parent.parent

    upgrade = subprocess.run([sys.executable, "-m", "alembic", "upgrade", "head"], cwd=root, env=env, text=True, capture_output=True, check=False)
    assert upgrade.returncode == 0, upgrade.stderr
    tables = set(inspect(create_engine(f"sqlite:///{database_path.as_posix()}", future=True)).get_table_names())
    assert {"feedback_events", "learning_runs", "adjustment_proposals"} <= tables

    current = subprocess.run([sys.executable, "-m", "alembic", "current"], cwd=root, env=env, text=True, capture_output=True, check=False)
    assert "202607030001" in current.stdout

    downgrade = subprocess.run([sys.executable, "-m", "alembic", "downgrade", "202607020004"], cwd=root, env=env, text=True, capture_output=True, check=False)
    assert downgrade.returncode == 0, downgrade.stderr
    downgraded_tables = set(inspect(create_engine(f"sqlite:///{database_path.as_posix()}", future=True)).get_table_names())
    assert "job_priorities" in downgraded_tables
    assert "feedback_events" not in downgraded_tables

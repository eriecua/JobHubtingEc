from __future__ import annotations

from datetime import date, timedelta
from pathlib import Path
import os
import subprocess
import sys

from sqlalchemy import create_engine, inspect, select
from sqlalchemy.orm import Session

from app.database import create_tables
from app.models import EvaluationComponent, JobEvaluation, JobRequirement
from app.repositories import (
    CareerPreferenceRepository,
    CertificationRepository,
    EvaluationRepository,
    ExperienceRepository,
    JobRepository,
    ProfileRepository,
    SkillRepository,
    ToolRepository,
)
from app.services.evaluation_engine import EvaluationEngineService
from app.services.evaluation_version import EvaluationVersionService
from app.services.requirement_extraction import RequirementExtractionService


def _session(tmp_path: Path) -> Session:
    engine = create_engine(f"sqlite:///{(tmp_path / 'phase4.db').as_posix()}", future=True)
    create_tables(engine)
    return Session(engine)


def _profile(session: Session):
    profile = ProfileRepository(session).create_profile(
        full_name="Perfil Ficticio",
        professional_title="Ingenieria Industrial",
        professional_summary="Produccion, operaciones y mejora continua.",
        current_city="Guayaquil",
        current_province="Guayas",
        country="Ecuador",
        years_total_experience=3,
        willing_to_travel=True,
        willing_to_relocate=False,
    )
    ExperienceRepository(session).create_experience(
        profile.id,
        company="Planta Ficticia",
        job_title="Coordinador de Produccion",
        sector="Manufactura",
        city="Guayaquil",
        start_date=date(2023, 1, 1),
        end_date=None,
        is_current=True,
        description="Gestion de personal, indicadores, inventarios y mejora continua.",
    )
    skill_repo = SkillRepository(session)
    for name, category, evidence in [
        ("Excel", "Digital", True),
        ("Indicadores de gestion", "Analitica", True),
        ("Mejora continua", "Mejora continua", True),
        ("Gestion de personal", "Liderazgo", False),
        ("Lean Manufacturing", "Mejora continua", False),
    ]:
        skill = skill_repo.create_or_get_skill(name, category)
        assigned = skill_repo.assign_skill(profile.id, skill.id, level="Intermedio", is_core_skill=True)
        if evidence:
            skill_repo.add_evidence(assigned.id, evidence_type="Proyecto", title=f"Evidencia {name}", description="Dato ficticio verificable.")
    tool_repo = ToolRepository(session)
    for name, category in [("Microsoft Excel", "Ofimatica"), ("Dynamics 365", "ERP")]:
        tool = tool_repo.create_or_get_tool(name, category)
        tool_repo.assign_tool(profile.id, tool.id, level="Intermedio")
    career = CareerPreferenceRepository(session)
    for role, priority in [
        ("Supervisor de Produccion", "Principal"),
        ("Coordinador de Produccion", "Principal"),
        ("Coordinador de Excelencia Operacional", "Exploratoria"),
        ("Analista de Logistica", "Secundaria"),
    ]:
        career.add_target_role(profile.id, role_name=role, priority=priority)
    for sector, priority in [("Manufactura", "Principal"), ("Logistica", "Secundaria")]:
        career.add_target_sector(profile.id, sector_name=sector, priority=priority)
    career.set_preferences(
        profile.id,
        preferred_cities=["Guayaquil"],
        preferred_provinces=["Guayas"],
        accepted_modalities=["Presencial", "Hibrida", "Remota"],
        minimum_salary=900,
        expected_salary=1200,
        currency="USD",
        accepts_shift_work=True,
        accepts_weekend_work=False,
        accepts_temporary_contract=True,
    )
    return profile


def _job(session: Session, **overrides):
    data = {
        "title": "Supervisor de Produccion",
        "company": "Industria Ficticia",
        "city": "Guayaquil",
        "province": "Guayas",
        "modality": "Presencial",
        "employment_type": "Tiempo completo",
        "contract_type": "Indefinido",
        "schedule_type": "Diurna",
        "salary_min": 1000,
        "salary_max": 1300,
        "currency": "USD",
        "salary_period": "Mensual",
        "publication_date": date.today().isoformat(),
        "description": "Se requiere Excel, indicadores de gestion y gestion de personal.",
        "requirements": "Obligatorio Excel. Deseable Power BI. Minimo 2 anos de experiencia. Ingenieria Industrial.",
        "responsibilities": "Supervisar personal y mejora continua.",
        "education_required": "Ingenieria Industrial",
        "experience_min_years": 2,
        "sector": "Manufactura",
        "source": "Manual",
        "source_url": f"https://empleos.example.com/{overrides.get('external_id', 'job')}",
        "external_id": overrides.get("external_id", "job"),
    }
    data.update(overrides)
    return JobRepository(session).create_job(data, confirm_possible_duplicate=True)[0]


def test_phase4_requirement_extraction_detects_required_desired_tool_experience_and_manual_priority(tmp_path: Path) -> None:
    session = _session(tmp_path)
    profile = _profile(session)
    power_bi = ToolRepository(session).create_or_get_tool("Power BI", "BI")
    sap = ToolRepository(session).create_or_get_tool("SAP", "ERP")
    job = _job(session, external_id="extract", source_url="https://empleos.example.com/extract")
    service = RequirementExtractionService(session)
    requirements = service.extract_for_job(job, persist=True)

    assert any(req["requirement_type"] == "Habilidad" and req["importance"] == "Obligatorio" and req["normalized_value"] == "excel" for req in requirements)
    assert any(req["requirement_type"] == "Herramienta" and req["importance"] == "Deseable" and req["tool_id"] == power_bi.id for req in requirements)
    assert any(req["requirement_type"] == "Experiencia" for req in requirements)
    assert any(req["requirement_type"] == "Formacion" and "ingenieria industrial" in req["raw_text"] for req in requirements)

    manual = EvaluationRepository(session).add_requirement(
        job_id=job.id,
        requirement_type="Habilidad",
        raw_text="MS Excel",
        normalized_value="excel",
        importance="Deseable",
        source_field="manual",
        extraction_method="Manual",
        extraction_confidence=1,
        is_confirmed_by_user=True,
        is_active=True,
    )
    service.extract_for_job(job, persist=True)
    updated = session.get(JobRequirement, manual.id)
    assert updated.importance == "Deseable"

    no_false = _job(
        session,
        external_id="no-false",
        source_url="https://empleos.example.com/no-false",
        requirements="No se requiere SAP para esta vacante.",
    )
    assert not any(req["normalized_value"] == "sap" for req in service.extract_for_job(no_false, persist=False))

    mixed_negation = _job(
        session,
        external_id="mixed-negation",
        source_url="https://empleos.example.com/mixed-negation",
        requirements="No se requiere SAP. Obligatorio Excel.",
    )
    mixed = service.extract_for_job(mixed_negation, persist=False)
    assert not any(req["tool_id"] == sap.id for req in mixed)
    assert any(req["normalized_value"] == "excel" for req in mixed)

    certification = _job(
        session,
        external_id="cert-extract",
        source_url="https://empleos.example.com/cert-extract",
        requirements="Obligatorio certificacion ISO 9001.",
    )
    extracted_certifications = service.extract_for_job(certification, persist=False)
    assert any(
        req["requirement_type"] == "Certificacion"
        and req["normalized_value"] == "iso 9001"
        and req["importance"] == "Obligatorio"
        for req in extracted_certifications
    )
    session.close()


def test_phase4_constraints_salary_unknown_exclusions_travel_and_relocation(tmp_path: Path) -> None:
    session = _session(tmp_path)
    profile = _profile(session)
    career = CareerPreferenceRepository(session)
    career.add_constraint(profile.id, constraint_type="Salario minimo obligatorio", operator="Mayor o igual", value="900")
    good = _job(session, external_id="good", source_url="https://empleos.example.com/good", salary_min=950, salary_max=1000)
    low = _job(session, external_id="low", source_url="https://empleos.example.com/low", salary_min=700, salary_max=800)
    unknown = _job(session, external_id="unknown", source_url="https://empleos.example.com/unknown", salary_min=None, salary_max=None)

    engine = EvaluationEngineService(session)
    good_eval = EvaluationRepository(session).get_evaluation(engine.evaluate_job(good.id, profile.id)["evaluation_id"])
    low_eval = EvaluationRepository(session).get_evaluation(engine.evaluate_job(low.id, profile.id)["evaluation_id"])
    unknown_eval = EvaluationRepository(session).get_evaluation(engine.evaluate_job(unknown.id, profile.id)["evaluation_id"])

    assert good_eval.eligibility_status == "Elegible"
    assert low_eval.eligibility_status == "No elegible"
    assert unknown_eval.eligibility_status == "Requiere revision"

    career.add_constraint(profile.id, constraint_type="Modalidad excluida", operator="Igual", value="Remota")
    remote = _job(session, external_id="remote", source_url="https://empleos.example.com/remote", modality="Remota")
    assert EvaluationRepository(session).get_evaluation(engine.evaluate_job(remote.id, profile.id)["evaluation_id"]).eligibility_status == "No elegible"

    career.add_constraint(profile.id, constraint_type="Disponibilidad para reubicarse", operator="Igual", value="Si")
    relocation = _job(session, external_id="relocation", source_url="https://empleos.example.com/relocation", relocation_required=True)
    assert EvaluationRepository(session).get_evaluation(engine.evaluate_job(relocation.id, profile.id)["evaluation_id"]).eligibility_status == "No elegible"
    session.close()


def test_phase4_fictional_scenarios_score_ranges_strengths_gaps_and_missing_data(tmp_path: Path) -> None:
    session = _session(tmp_path)
    profile = _profile(session)
    career = CareerPreferenceRepository(session)
    career.add_constraint(profile.id, constraint_type="Salario minimo obligatorio", operator="Mayor o igual", value="900")
    career.add_constraint(profile.id, constraint_type="Jornada excluida", operator="Igual", value="Nocturna")
    power_bi = ToolRepository(session).create_or_get_tool("Power BI", "BI")
    _ = power_bi
    engine = EvaluationEngineService(session)

    high = _job(session, external_id="A", source_url="https://empleos.example.com/A")
    growth = _job(
        session,
        external_id="B",
        source_url="https://empleos.example.com/B",
        title="Coordinador de Excelencia Operacional",
        requirements="Obligatorio Lean Manufacturing. Deseable Power BI. Deseable ingles.",
        sector="Manufactura",
    )
    no_eligible = _job(
        session,
        external_id="C",
        source_url="https://empleos.example.com/C",
        salary_min=600,
        salary_max=700,
        schedule_type="Nocturna",
    )
    insufficient = _job(
        session,
        external_id="D",
        source_url="https://empleos.example.com/D",
        title="Asistente de Planta",
        description="Vacante general.",
        requirements=None,
        salary_min=None,
        salary_max=None,
        city=None,
        province=None,
        modality="No especificada",
        sector=None,
        publication_date=None,
        experience_min_years=None,
    )
    low = _job(
        session,
        external_id="E",
        source_url="https://empleos.example.com/E",
        title="Ejecutivo Comercial",
        requirements="Obligatorio ventas B2B y CRM.",
        sector="Comercial",
        city="Quito",
        province="Pichincha",
        salary_min=1000,
        salary_max=1100,
    )

    high_eval = EvaluationRepository(session).get_evaluation(engine.evaluate_job(high.id, profile.id)["evaluation_id"])
    growth_eval = EvaluationRepository(session).get_evaluation(engine.evaluate_job(growth.id, profile.id)["evaluation_id"])
    no_eval = EvaluationRepository(session).get_evaluation(engine.evaluate_job(no_eligible.id, profile.id)["evaluation_id"])
    insufficient_eval = EvaluationRepository(session).get_evaluation(engine.evaluate_job(insufficient.id, profile.id)["evaluation_id"])
    low_eval = EvaluationRepository(session).get_evaluation(engine.evaluate_job(low.id, profile.id)["evaluation_id"])

    assert high_eval.total_score >= 70
    assert high_eval.strengths
    assert growth_eval.recommendation_type in {"Oportunidad de crecimiento", "Buena compatibilidad", "Exploratoria"}
    assert growth_eval.growth_opportunities
    assert no_eval.eligibility_status == "No elegible"
    assert insufficient_eval.confidence_score < high_eval.confidence_score
    assert insufficient_eval.missing_information
    assert low_eval.total_score < high_eval.total_score
    assert "Conseguiras" not in high_eval.summary_explanation
    assert session.query(EvaluationComponent).filter(EvaluationComponent.evaluation_id == high_eval.id).count() == 8
    session.close()


def test_phase4_required_certification_gap_and_manual_requirement_correction(tmp_path: Path) -> None:
    session = _session(tmp_path)
    profile = _profile(session)
    engine = EvaluationEngineService(session)
    repo = EvaluationRepository(session)

    high = _job(session, external_id="cert-base", source_url="https://empleos.example.com/cert-base")
    certification_job = _job(
        session,
        external_id="cert-gap",
        source_url="https://empleos.example.com/cert-gap",
        requirements="Obligatorio certificacion ISO 9001. Excel requerido.",
    )

    high_eval = repo.get_evaluation(engine.evaluate_job(high.id, profile.id)["evaluation_id"])
    certification_eval = repo.get_evaluation(engine.evaluate_job(certification_job.id, profile.id)["evaluation_id"])

    assert certification_eval.total_score < high_eval.total_score
    assert certification_eval.recommendation_type == "Baja compatibilidad"
    assert any(gap["requirement"] == "iso 9001" and gap["severity"] == "Critica" for gap in certification_eval.gaps)

    CertificationRepository(session).create(
        profile.id,
        name="ISO 9001",
        issuing_organization="Entidad ficticia",
        does_not_expire=True,
    )
    assert engine.mark_stale_for_current_state(certification_job.id, profile.id) is True

    engine = EvaluationEngineService(session)
    covered_eval = repo.get_evaluation(engine.evaluate_job(certification_job.id, profile.id)["evaluation_id"])
    assert covered_eval.total_score > certification_eval.total_score
    assert any(strength["requirement"] == "iso 9001" for strength in covered_eval.strengths)

    power_bi = ToolRepository(session).create_or_get_tool("Power BI", "BI")
    engine = EvaluationEngineService(session)
    manual_job = _job(
        session,
        external_id="manual-correction",
        source_url="https://empleos.example.com/manual-correction",
        requirements="Obligatorio Power BI. Excel requerido.",
    )
    before = repo.get_evaluation(engine.evaluate_job(manual_job.id, profile.id)["evaluation_id"])
    requirement = next(req for req in repo.list_requirements(manual_job.id) if req.tool_id == power_bi.id)
    repo.update_requirement(requirement.id, importance="Deseable", is_confirmed_by_user=True)

    assert engine.mark_stale_for_current_state(manual_job.id, profile.id) is True
    after = repo.get_evaluation(engine.evaluate_job(manual_job.id, profile.id)["evaluation_id"])
    updated = session.get(JobRequirement, requirement.id)

    assert updated.importance == "Deseable"
    assert updated.is_confirmed_by_user is True
    assert before.total_score != after.total_score
    session.close()


def test_phase4_recency_confidence_coverage_and_component_persistence(tmp_path: Path) -> None:
    session = _session(tmp_path)
    profile = _profile(session)
    engine = EvaluationEngineService(session)
    recent = _job(session, external_id="recent", source_url="https://empleos.example.com/recent", publication_date=(date.today() - timedelta(days=3)).isoformat())
    old = _job(session, external_id="old", source_url="https://empleos.example.com/old", publication_date=(date.today() - timedelta(days=70)).isoformat())
    unknown = _job(session, external_id="no-date", source_url="https://empleos.example.com/no-date", publication_date=None)

    recent_eval = EvaluationRepository(session).get_evaluation(engine.evaluate_job(recent.id, profile.id)["evaluation_id"])
    old_eval = EvaluationRepository(session).get_evaluation(engine.evaluate_job(old.id, profile.id)["evaluation_id"])
    unknown_eval = EvaluationRepository(session).get_evaluation(engine.evaluate_job(unknown.id, profile.id)["evaluation_id"])
    recent_recency = next(item for item in recent_eval.components if item.component_name == "recency")
    old_recency = next(item for item in old_eval.components if item.component_name == "recency")

    assert recent_recency.raw_score > old_recency.raw_score
    assert unknown_eval.data_coverage_score < recent_eval.data_coverage_score
    assert len(recent_eval.components) == 8
    session.close()


def test_phase4_versioning_stale_config_hash_batch_and_error_isolation(tmp_path: Path) -> None:
    session = _session(tmp_path)
    profile = _profile(session)
    first = _job(session, external_id="batch-1", source_url="https://empleos.example.com/batch-1")
    second = _job(session, external_id="batch-2", source_url="https://empleos.example.com/batch-2", title="Analista de Calidad")
    engine = EvaluationEngineService(session)
    result = engine.evaluate_jobs([first.id, second.id, 999999], profile.id)

    assert result["jobs_evaluated"] == 2
    assert result["jobs_failed"] == 1
    assert session.query(JobEvaluation).count() == 2

    latest = EvaluationRepository(session).get_latest_evaluation(first.id, profile.id)
    old_hash = latest.profile_snapshot_hash
    ProfileRepository(session).update_profile(profile.id, professional_summary="Perfil modificado para obsolescencia.")
    assert engine.mark_stale_for_current_state(first.id, profile.id) is True
    assert EvaluationRepository(session).get_evaluation(latest.id).is_stale is True

    config = engine.config.copy()
    config["weights"] = {**config["weights"], "growth": 9, "recency": 6}
    changed_hash = EvaluationVersionService(session, config).configuration_hash(config)
    assert changed_hash != latest.configuration_hash
    assert old_hash != EvaluationVersionService(session).profile_hash(profile)
    session.close()


def test_phase4_alembic_upgrade_and_downgrade_on_temporary_database(tmp_path: Path) -> None:
    database_path = tmp_path / "phase4_alembic.db"
    env = os.environ.copy()
    env["RADAR_DATABASE_URL"] = f"sqlite:///{database_path.as_posix()}"
    root = Path(__file__).resolve().parent.parent

    upgrade = subprocess.run([sys.executable, "-m", "alembic", "upgrade", "head"], cwd=root, env=env, text=True, capture_output=True, check=False)
    assert upgrade.returncode == 0, upgrade.stderr
    tables = inspect(create_engine(f"sqlite:///{database_path.as_posix()}", future=True)).get_table_names()
    assert {"job_requirements", "evaluation_runs", "job_evaluations", "evaluation_components"} <= set(tables)

    current = subprocess.run([sys.executable, "-m", "alembic", "current"], cwd=root, env=env, text=True, capture_output=True, check=False)
    assert "202607030001" in current.stdout

    downgrade = subprocess.run([sys.executable, "-m", "alembic", "downgrade", "202607020001"], cwd=root, env=env, text=True, capture_output=True, check=False)
    assert downgrade.returncode == 0, downgrade.stderr
    downgraded_tables = inspect(create_engine(f"sqlite:///{database_path.as_posix()}", future=True)).get_table_names()
    assert "jobs" in downgraded_tables
    assert "job_evaluations" not in downgraded_tables

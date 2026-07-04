from __future__ import annotations

from datetime import date
import os
from pathlib import Path
import subprocess
import sys

import pytest
from sqlalchemy import create_engine, func, select
from sqlalchemy.orm import Session

from app.database import create_tables
from app.models import (
    Base,
    Certification,
    EducationRecord,
    JobPreference,
    ProfessionalProfile,
    ProfileSkill,
    ProfileTool,
    Skill,
    SkillEvidence,
    TargetRole,
    TargetSector,
    Tool,
    WorkExperience,
)
from app.repositories import (
    CareerPreferenceRepository,
    CertificationRepository,
    EducationRepository,
    ExperienceRepository,
    ProfileRepository,
    SkillRepository,
    ToolRepository,
)
from app.services.profile_completeness import ProfileCompletenessService
from app.services.validation import ValidationError


@pytest.fixture()
def session(tmp_path: Path) -> Session:
    engine = create_engine(f"sqlite:///{(tmp_path / 'phase2.db').as_posix()}", future=True)
    create_tables(engine)
    with Session(engine) as db_session:
        yield db_session


def create_profile(session: Session) -> ProfessionalProfile:
    return ProfileRepository(session).create_profile(
        full_name="Erick",
        professional_title="Estudiante de Ingenieria Industrial",
        professional_summary="Resumen profesional.",
        current_city="Guayaquil",
        current_province="Guayas",
        country="Ecuador",
        willing_to_travel=True,
    )


def test_create_update_profile_and_reject_second_primary(session: Session) -> None:
    repo = ProfileRepository(session)
    profile = create_profile(session)

    updated = repo.update_profile(profile.id, professional_title="Coordinador de Produccion")

    assert updated.professional_title == "Coordinador de Produccion"
    with pytest.raises(ValidationError, match="perfil principal"):
        repo.create_profile(full_name="Otro", professional_title="Otro", country="Ecuador")


def test_optional_url_validation(session: Session) -> None:
    repo = ProfileRepository(session)

    with pytest.raises(ValidationError, match="URL valida"):
        repo.create_profile(
            full_name="Erick",
            professional_title="Industrial",
            country="Ecuador",
            linkedin_url="linkedin.com/in/erick",
        )


def test_profile_completeness_empty_partial_and_complete(session: Session) -> None:
    service = ProfileCompletenessService(session)

    empty_result = service.calculate(None)
    assert empty_result.total_percentage == 0

    profile = create_profile(session)
    partial_result = service.calculate(profile)
    assert 0 < partial_result.total_percentage < 100

    experience_repo = ExperienceRepository(session)
    experience_repo.create_experience(
        profile.id,
        company="Gurit",
        job_title="Coordinador de Produccion",
        start_date=date(2025, 6, 20),
        is_current=True,
    )
    skill_repo = SkillRepository(session)
    assignment_ids: list[int] = []
    for skill_name in ["Excel", "Mejora continua", "Lean Manufacturing", "Six Sigma", "Indicadores"]:
        skill = skill_repo.create_or_get_skill(skill_name, "Tecnica")
        assignment = skill_repo.assign_skill(profile.id, skill.id, level="Intermedio")
        assignment_ids.append(assignment.id)
    for profile_skill_id in assignment_ids[:3]:
        skill_repo.add_evidence(
            profile_skill_id,
            evidence_type="Proyecto",
            title=f"Evidencia {profile_skill_id}",
            description="Evidencia verificable.",
        )
    tool_repo = ToolRepository(session)
    tool = tool_repo.create_or_get_tool("Microsoft Excel", "Ofimatica")
    tool_repo.assign_tool(profile.id, tool.id, level="Intermedio")
    EducationRepository(session).create(
        profile.id,
        institution="",
        degree="Ingenieria Industrial",
        field_of_study="Ingenieria Industrial",
        education_level="Universitario",
        status="En curso",
    )
    CertificationRepository(session).create(
        profile.id,
        name="Six Sigma Yellow Belt",
        issuing_organization="Lean Six Sigma Institute",
        does_not_expire=True,
    )
    career_repo = CareerPreferenceRepository(session)
    career_repo.add_target_role(profile.id, role_name="Coordinador de Produccion", priority="Principal")
    career_repo.set_preferences(
        profile.id,
        preferred_cities=["Guayaquil"],
        preferred_provinces=["Guayas"],
        accepted_modalities=["Presencial"],
        currency="USD",
    )

    complete_result = service.calculate(profile)
    assert complete_result.total_percentage == 100


def test_experience_crud_and_date_validation(session: Session) -> None:
    profile = create_profile(session)
    repo = ExperienceRepository(session)

    current = repo.create_experience(
        profile.id,
        company="Gurit",
        job_title="Coordinador",
        start_date=date(2025, 6, 20),
        is_current=True,
    )
    past = repo.create_experience(
        profile.id,
        company="Otra",
        job_title="Asistente",
        start_date=date(2024, 1, 1),
        end_date=date(2024, 12, 31),
        is_current=False,
    )
    updated = repo.update_experience(past.id, people_managed=3)

    assert current.end_date is None
    assert updated.people_managed == 3
    with pytest.raises(ValidationError):
        repo.create_experience(
            profile.id,
            company="X",
            job_title="Y",
            start_date=date(2025, 1, 1),
            end_date=date(2024, 1, 1),
            is_current=False,
        )
    with pytest.raises(ValidationError, match="fecha final"):
        repo.create_experience(
            profile.id,
            company="X",
            job_title="Y",
            start_date=date(2025, 1, 1),
            is_current=False,
        )
    with pytest.raises(ValidationError, match="Confirma"):
        repo.delete_experience(past.id, confirmed=False)
    repo.delete_experience(past.id, confirmed=True)
    assert session.get(WorkExperience, past.id) is None


def test_skills_alias_duplicates_assignment_and_evidence(session: Session) -> None:
    profile = create_profile(session)
    repo = SkillRepository(session)

    excel = repo.create_or_get_skill("Excel", "Digital")
    same_excel = repo.create_or_get_skill("MS Excel", "Digital")
    assignment = repo.assign_skill(profile.id, excel.id, level="Intermedio", years_experience=1)

    assert excel.id == same_excel.id
    with pytest.raises(ValidationError, match="ya esta asignada"):
        repo.assign_skill(profile.id, excel.id, level="Intermedio")
    with pytest.raises(ValidationError, match="Nivel"):
        repo.assign_skill(profile.id, repo.create_or_get_skill("Python", "Digital").id, level="Maestro")
    evidence = repo.add_evidence(
        assignment.id,
        evidence_type="Proyecto",
        title="Automatizacion",
        description="Automatizacion de registros.",
        metric_value=4000,
        metric_unit="USD/anio",
    )
    assert evidence.metric_value == 4000
    with pytest.raises(ValidationError):
        repo.add_evidence(
            assignment.id,
            evidence_type="Proyecto",
            title="Metrica invalida",
            description="No valida",
            metric_value=-1,
        )


def test_tools_normalize_avoid_duplicates_and_assign(session: Session) -> None:
    profile = create_profile(session)
    repo = ToolRepository(session)

    excel = repo.create_or_get_tool("Excel", "Ofimatica")
    same_excel = repo.create_or_get_tool("Microsoft Excel", "Ofimatica")
    assignment = repo.assign_tool(profile.id, excel.id, level="Intermedio")

    assert excel.id == same_excel.id
    assert assignment.tool_id == excel.id
    with pytest.raises(ValidationError):
        repo.assign_tool(profile.id, excel.id, level="Intermedio")


def test_education_and_certification_validations(session: Session) -> None:
    profile = create_profile(session)
    education_repo = EducationRepository(session)
    certification_repo = CertificationRepository(session)

    record = education_repo.create(
        profile.id,
        institution="",
        degree="Ingenieria Industrial",
        field_of_study="Ingenieria Industrial",
        education_level="Universitario",
        start_date=date(2024, 1, 1),
        end_date=date(2025, 1, 1),
        status="En curso",
    )
    updated = education_repo.update(record.id, notes="Editable")
    assert updated.notes == "Editable"
    with pytest.raises(ValidationError):
        education_repo.create(
            profile.id,
            institution="",
            degree="X",
            field_of_study="Y",
            education_level="Z",
            start_date=date(2025, 1, 1),
            end_date=date(2024, 1, 1),
            status="En curso",
        )
    education_repo.delete(record.id, confirmed=True)

    cert = certification_repo.create(
        profile.id,
        name="Six Sigma Yellow Belt",
        issuing_organization="Lean Six Sigma Institute",
        issue_date=date(2024, 1, 1),
        does_not_expire=True,
    )
    assert cert.expiration_date is None
    with pytest.raises(ValidationError):
        certification_repo.update(
            cert.id,
            issue_date=date(2025, 1, 1),
            expiration_date=date(2024, 1, 1),
        )
    with pytest.raises(ValidationError):
        certification_repo.create(
            profile.id,
            name="Cert",
            issuing_organization="Org",
            issue_date=date(2025, 1, 1),
            expiration_date=date(2024, 1, 1),
        )


def test_preferences_roles_constraints_and_contradictions(session: Session) -> None:
    profile = create_profile(session)
    repo = CareerPreferenceRepository(session)

    role = repo.add_target_role(
        profile.id,
        role_name="Coordinador de Produccion",
        priority="Principal",
        minimum_salary=800,
    )
    repo.set_preferences(
        profile.id,
        preferred_cities=["Guayaquil"],
        preferred_provinces=[],
        accepted_modalities=["Remota"],
        currency="USD",
    )
    repo.add_constraint(
        profile.id,
        constraint_type="Modalidad excluida",
        operator="Igual",
        value="Remota",
    )

    assert role.normalized_role_name == "coordinador de produccion"
    assert repo.detect_basic_contradictions(profile.id) == ["Modalidad preferida y excluida: Remota"]
    with pytest.raises(ValidationError):
        repo.add_target_role(profile.id, role_name="X", priority="Invalida")
    with pytest.raises(ValidationError):
        repo.add_target_role(profile.id, role_name="X", priority="Principal", minimum_salary=-1)


def test_seed_initial_profile_is_idempotent(tmp_path: Path) -> None:
    database_path = tmp_path / "seed.db"
    env = os.environ.copy()
    env["RADAR_DATABASE_URL"] = f"sqlite:///{database_path.as_posix()}"

    for _ in range(2):
        result = subprocess.run(
            [sys.executable, "scripts/seed_initial_profile.py"],
            cwd=Path(__file__).resolve().parent.parent,
            env=env,
            check=True,
            capture_output=True,
            text=True,
        )
        assert "Perfil inicial cargado correctamente" in result.stdout

    engine = create_engine(f"sqlite:///{database_path.as_posix()}", future=True)
    with Session(engine) as db_session:
        assert db_session.scalar(select(func.count(ProfessionalProfile.id))) == 1
        assert db_session.scalar(select(func.count(WorkExperience.id))) == 1
        assert db_session.scalar(select(func.count(Skill.id))) == 15
        assert db_session.scalar(select(func.count(ProfileSkill.id))) == 15
        assert db_session.scalar(select(func.count(SkillEvidence.id))) == 3
        assert db_session.scalar(select(func.count(Tool.id))) == 5
        assert db_session.scalar(select(func.count(ProfileTool.id))) == 5
        assert db_session.scalar(select(func.count(EducationRecord.id))) == 1
        assert db_session.scalar(select(func.count(Certification.id))) == 1
        assert db_session.scalar(select(func.count(TargetRole.id))) == 13
        assert db_session.scalar(select(func.count(TargetSector.id))) == 5
        assert db_session.scalar(select(func.count(JobPreference.id))) == 1

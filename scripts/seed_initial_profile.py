"""Seed the editable initial professional profile data."""

from __future__ import annotations

from datetime import date
from pathlib import Path
import sys

PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from sqlalchemy import select

from app.database import SessionLocal, create_tables, engine
from app.models import EducationRecord, TargetRole, TargetSector
from app.repositories import (
    CareerPreferenceRepository,
    CertificationRepository,
    EducationRepository,
    ExperienceRepository,
    ProfileRepository,
    SkillRepository,
    ToolRepository,
)
from app.services.validation import ValidationError
from app.utils.normalization import normalize_text


def seed_profile() -> None:
    """Load initial editable profile data without creating duplicates."""

    create_tables(engine)
    with SessionLocal() as session:
        profile_repo = ProfileRepository(session)
        profile = profile_repo.get_main_profile()
        if profile is None:
            profile = profile_repo.create_profile(
                full_name="Erick",
                professional_title=(
                    "Estudiante de Ingenieria Industrial | Experiencia en produccion, "
                    "operaciones y mejora continua."
                ),
                professional_summary="Perfil inicial editable proporcionado por el usuario.",
                current_city="Guayaquil",
                current_province="Guayas",
                country="Ecuador",
                willing_to_travel=True,
                willing_to_relocate=None,
                availability_status="Editable",
            )

        experience_repo = ExperienceRepository(session)
        if not experience_repo.list_experiences(profile.id):
            experience_repo.create_experience(
                profile.id,
                company="Gurit - Balsaflex",
                job_title="Coordinador de Produccion",
                sector="Manufactura",
                city="Guayaquil",
                start_date=date(2025, 6, 20),
                end_date=None,
                is_current=True,
                description=(
                    "Coordinacion de areas de produccion. Gestion de personal operativo. "
                    "Seguimiento de indicadores. Control de produccion, inventario y bodega. "
                    "Reporte de informacion mediante Dynamics 365. Presentacion de resultados operativos."
                ),
                achievements=(
                    "Mejora del sistema de registros. Ahorro anual estimado superior a USD 4.000. "
                    "Automatizacion y reduccion de errores. Desarrollo de analisis estadisticos "
                    "y reportes ejecutivos."
                ),
            )

        skill_repo = SkillRepository(session)
        initial_skills = [
            ("Coordinacion de produccion", "Gestion"),
            ("Mejora continua", "Mejora continua"),
            ("Lean Manufacturing", "Mejora continua"),
            ("Six Sigma", "Calidad"),
            ("Analisis de datos", "Analitica"),
            ("Indicadores de gestion", "Analitica"),
            ("Gestion de inventarios", "Logistica"),
            ("Gestion de personal", "Liderazgo"),
            ("Productividad", "Operativa"),
            ("Excel", "Digital"),
            ("VBA", "Digital"),
            ("Dynamics 365", "Digital"),
            ("Analisis estadistico", "Analitica"),
            ("Presentaciones ejecutivas", "Comunicacion"),
            ("Optimizacion de procesos", "Mejora continua"),
        ]
        assigned_skill_ids: dict[str, int] = {}
        for skill_name, category in initial_skills:
            skill = skill_repo.create_or_get_skill(skill_name, category)
            assigned_skill_ids[skill.normalized_name] = _assign_skill_once(skill_repo, profile.id, skill.id)

        _add_evidence_once(
            skill_repo,
            assigned_skill_ids.get("excel"),
            "Herramienta desarrollada",
            "Automatizacion de registros mediante Excel y VBA",
            "Informacion inicial editable del usuario; no verificada por terceros.",
            4000,
            "USD/anio",
        )
        _add_evidence_once(
            skill_repo,
            assigned_skill_ids.get("coordinacion de produccion"),
            "Responsabilidad laboral",
            "Coordinacion de areas operativas",
            "Coordinacion de produccion, inventario, bodega e indicadores.",
        )
        _add_evidence_once(
            skill_repo,
            assigned_skill_ids.get("indicadores de gestion"),
            "Presentacion",
            "Presentacion de resultados operativos",
            "Reporte y presentacion de indicadores de produccion.",
        )

        tool_repo = ToolRepository(session)
        for tool_name, category in [
            ("Microsoft Excel", "Ofimatica"),
            ("VBA", "Programacion"),
            ("Dynamics 365", "ERP"),
            ("Google Sheets", "Ofimatica"),
            ("Notion", "Gestion de proyectos"),
        ]:
            tool = tool_repo.create_or_get_tool(tool_name, category)
            try:
                tool_repo.assign_tool(profile.id, tool.id, level="Intermedio")
            except ValidationError:
                pass

        education_repo = EducationRepository(session)
        existing_education = session.scalar(
            select(EducationRecord).where(
                EducationRecord.profile_id == profile.id,
                EducationRecord.degree == "Ingenieria Industrial",
            )
        )
        if existing_education is None:
            education_repo.create(
                profile.id,
                institution="",
                degree="Ingenieria Industrial",
                field_of_study="Ingenieria Industrial",
                education_level="Universitario",
                is_current=True,
                status="En curso",
                notes="Institucion y fechas no proporcionadas.",
            )

        certification_repo = CertificationRepository(session)
        if not any(cert.name == "Six Sigma Yellow Belt" for cert in certification_repo.list_records(profile.id)):
            certification_repo.create(
                profile.id,
                name="Six Sigma Yellow Belt",
                issuing_organization="Lean Six Sigma Institute",
                does_not_expire=False,
                notes="Fecha, codigo y URL no proporcionados.",
            )

        career_repo = CareerPreferenceRepository(session)
        for role_name, priority in [
            ("Coordinador de Produccion", "Principal"),
            ("Supervisor de Produccion", "Principal"),
            ("Coordinador de Operaciones", "Principal"),
            ("Analista de Mejora Continua", "Principal"),
            ("Ingeniero de Procesos", "Principal"),
            ("Planificador de Produccion", "Secundaria"),
            ("Analista de Procesos", "Secundaria"),
            ("Analista de Calidad", "Secundaria"),
            ("Analista de Logistica", "Secundaria"),
            ("Jefe de Produccion junior", "Secundaria"),
            ("Analista de Excelencia Operacional", "Exploratoria"),
            ("Especialista junior de mejora continua", "Exploratoria"),
            ("Coordinador de logistica", "Exploratoria"),
        ]:
            if not _target_role_exists(session, profile.id, role_name):
                career_repo.add_target_role(profile.id, role_name=role_name, priority=priority)

        for sector_name in ["Manufactura", "Madera", "Logistica", "Consumo masivo", "Alimentos"]:
            if not _target_sector_exists(session, profile.id, sector_name):
                career_repo.add_target_sector(profile.id, sector_name=sector_name, priority="Principal")

        if career_repo.get_preferences(profile.id) is None:
            career_repo.set_preferences(
                profile.id,
                preferred_cities=["Guayaquil"],
                preferred_provinces=["Guayas"],
                accepted_modalities=["Presencial", "Hibrida", "Remota"],
                currency="USD",
                accepts_shift_work=True,
                accepts_weekend_work=False,
                accepts_temporary_contract=True,
                notes="Preferencias iniciales editables.",
            )


def _assign_skill_once(repo: SkillRepository, profile_id: int, skill_id: int) -> int:
    try:
        assignment = repo.assign_skill(
            profile_id,
            skill_id,
            level="Intermedio",
            is_core_skill=True,
            self_assessed=True,
            interest_level="Alto",
        )
        return assignment.id
    except ValidationError:
        existing = [item for item in repo.list_profile_skills(profile_id) if item.skill_id == skill_id][0]
        return existing.id


def _add_evidence_once(
    repo: SkillRepository,
    profile_skill_id: int | None,
    evidence_type: str,
    title: str,
    description: str,
    metric_value: int | None = None,
    metric_unit: str | None = None,
) -> None:
    if profile_skill_id is None:
        return
    if any(evidence.title == title for evidence in repo.list_evidences(profile_skill_id)):
        return
    repo.add_evidence(
        profile_skill_id,
        evidence_type=evidence_type,
        title=title,
        description=description,
        metric_value=metric_value,
        metric_unit=metric_unit,
        source_type="Informacion inicial del usuario",
    )


def _target_role_exists(session, profile_id: int, role_name: str) -> bool:
    return (
        session.scalar(
            select(TargetRole).where(
                TargetRole.profile_id == profile_id,
                TargetRole.normalized_role_name == normalize_text(role_name),
            )
        )
        is not None
    )


def _target_sector_exists(session, profile_id: int, sector_name: str) -> bool:
    return (
        session.scalar(
            select(TargetSector).where(
                TargetSector.profile_id == profile_id,
                TargetSector.sector_name == sector_name,
            )
        )
        is not None
    )


if __name__ == "__main__":
    seed_profile()
    print("Perfil inicial cargado correctamente.")

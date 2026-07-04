from __future__ import annotations

from pathlib import Path

import pytest
from sqlalchemy import create_engine, func, select
from sqlalchemy.orm import Session

from app.database import create_tables
from app.models import EducationRecord, ProfessionalProfile, ProfileSkill, Skill, SkillEvidence, Tool, WorkExperience
from app.services.cv_document_reader import CVDocumentReader, CVReaderConfig
from app.services.cv_draft_apply_service import CVDraftApplyService
from app.services.cv_draft_validator import CVDraftValidator
from app.services.cv_profile_mapper import CVProfileMapper
from app.services.validation import ValidationError


@pytest.fixture()
def session(tmp_path: Path) -> Session:
    engine = create_engine(f"sqlite:///{(tmp_path / 'cv_ingestion.db').as_posix()}", future=True)
    create_tables(engine)
    with Session(engine) as db_session:
        yield db_session


def test_empty_or_illegible_cv_is_rejected() -> None:
    reader = CVDocumentReader(
        CVReaderConfig(
            supported_extensions=(".txt",),
            max_file_size_mb=1,
            minimum_extractable_characters=10,
        )
    )

    with pytest.raises(ValidationError, match="texto suficiente"):
        reader.extract_text("cv.txt", b"   \n")


def test_partial_cv_creates_only_detected_candidates() -> None:
    text = """
Erick Ejemplo
Estudiante de Ingenieria Industrial
Perfil profesional:
Coordinacion de produccion y mejora continua.
Habilidades:
Excel, Microsoft Excel, MS Excel, Excel avanzado, Lean Manufacturing
"""

    draft = CVProfileMapper().build_draft(text, "cv.txt")
    skill_values = [candidate.value for candidate in draft.candidates if candidate.section == "skill"]

    assert any(candidate.field == "professional_summary" for candidate in draft.candidates)
    assert skill_values.count("Excel") == 1
    assert "Lean Manufacturing" in skill_values
    assert not any(candidate.section == "experience" for candidate in draft.candidates)


def test_cv_with_experience_separates_responsibilities_and_achievements() -> None:
    text = """
Experiencia laboral:
Coordinador de Produccion - Empresa ABC | 2025-06 - Actualidad
Responsabilidades: Coordinar turnos y personal operativo.
Logros: Reduje desperdicio en 12%.
"""

    draft = CVProfileMapper().build_draft(text, "cv.txt")
    experiences = [candidate for candidate in draft.candidates if candidate.section == "experience"]

    assert len(experiences) == 1
    value = experiences[0].value
    assert value["description"] == "Coordinar turnos y personal operativo."
    assert value["achievements"] == "Reduje desperdicio en 12%."
    assert experiences[0].status == "Aceptado"
    evidences = [candidate for candidate in draft.candidates if candidate.section == "evidence"]
    assert len(evidences) == 1
    assert evidences[0].status == "Pendiente"


def test_ambiguous_experience_dates_remain_pending(session: Session) -> None:
    text = """
Experiencia laboral:
Analista de Procesos - Empresa XYZ | 2024 - 2025
Responsabilidades: Analisis de indicadores.
"""

    draft = CVProfileMapper().build_draft(text, "cv.txt")
    validated = CVDraftValidator(session).validate(draft)
    experience = next(candidate for candidate in validated.candidates if candidate.section == "experience")

    assert experience.status == "Pendiente"
    assert any("Fecha laboral ambigua" in warning for warning in experience.warnings)


def test_apply_persists_only_accepted_or_edited_candidates(session: Session) -> None:
    text = """
Erick Ejemplo
Estudiante de Ingenieria Industrial
Perfil profesional:
Perfil orientado a operaciones.
Experiencia laboral:
Coordinador de Produccion - Empresa ABC | 2025-06 - Actualidad
Responsabilidades: Coordinar produccion.
Logros: Ahorro anual de 4000 USD.
Habilidades:
Excel, MS Excel
Herramientas:
Dynamics 365
Formacion academica:
Ingenieria Industrial - Universidad Ficticia
"""
    draft = CVProfileMapper().build_draft(text, "cv.txt")
    reviewed = []
    for candidate in draft.candidates:
        data = candidate.model_dump(mode="json")
        if data["section"] == "tool":
            data["status"] = "Omitido"
        elif data["section"] == "evidence":
            data["status"] = "Editado"
            data["value"]["skill_name"] = "Mejora continua"
        elif data["section"] == "education":
            data["status"] = "Editado"
            data["value"]["field_of_study"] = "Ingenieria Industrial"
        else:
            data["status"] = "Aceptado"
        reviewed.append(data)

    result = CVDraftApplyService(session).apply(reviewed)

    assert not result.errors
    assert session.scalar(select(func.count(ProfessionalProfile.id))) == 1
    assert session.scalar(select(func.count(WorkExperience.id))) == 1
    assert session.scalar(select(func.count(ProfileSkill.id))) == 2
    assert session.scalar(select(func.count(SkillEvidence.id))) == 1
    assert session.scalar(select(func.count(Tool.id))) == 0
    assert session.scalar(select(func.count(EducationRecord.id))) == 1


def test_apply_skips_duplicate_existing_skill(session: Session) -> None:
    profile = ProfessionalProfile(
        full_name="Erick Ejemplo",
        professional_title="Industrial",
        professional_summary="",
        current_city="",
        current_province="",
        country="Ecuador",
    )
    session.add(profile)
    session.commit()
    session.refresh(profile)
    result = CVDraftApplyService(session).apply(
        [
            {
                "section": "skill",
                "field": "skill",
                "value": "Excel",
                "source_snippet": "Excel",
                "confidence": "Alta",
                "status": "Aceptado",
                "warnings": [],
            },
            {
                "section": "skill",
                "field": "skill",
                "value": "MS Excel",
                "source_snippet": "MS Excel",
                "confidence": "Media",
                "status": "Aceptado",
                "warnings": [],
            },
        ]
    )

    assert session.scalar(select(func.count(Skill.id))) == 1
    assert session.scalar(select(func.count(ProfileSkill.id))) == 1
    assert result.errors

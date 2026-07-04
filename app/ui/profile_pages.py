"""Streamlit views for the professional profile module."""

from __future__ import annotations

from datetime import date
from decimal import Decimal
import logging
from typing import Any

import streamlit as st

from app.config import load_profile_catalogs
from app.database import SessionLocal, create_tables
from app.repositories import (
    CareerPreferenceRepository,
    CertificationRepository,
    EducationRepository,
    ExperienceRepository,
    ProfileRepository,
    SkillRepository,
    ToolRepository,
)
from app.services.cv_document_reader import CVDocumentReader
from app.services.cv_draft_apply_service import CVDraftApplyService
from app.services.cv_draft_validator import CVDraftValidator
from app.services.cv_profile_mapper import CVProfileMapper
from app.services.cv_types import CVDraft
from app.services.profile_completeness import ProfileCompletenessService
from app.services.validation import ValidationError

LOGGER = logging.getLogger(__name__)


def render_profile_page() -> None:
    """Render the professional profile section."""

    create_tables()
    catalogs = load_profile_catalogs()
    st.header("Mi perfil profesional")
    st.caption("Informacion estructurada y editable para la busqueda laboral local.")

    with SessionLocal() as session:
        profile_repo = ProfileRepository(session)
        profile = profile_repo.get_main_profile()

        tabs = st.tabs(
            [
                "Resumen",
                "Importar CV",
                "Experiencia",
                "Habilidades",
                "Evidencias",
                "Herramientas",
                "Formacion",
                "Certificaciones",
                "Cargos objetivo",
                "Sectores",
                "Preferencias",
                "Restricciones",
                "Crecimiento",
            ]
        )
        with tabs[0]:
            _render_summary(profile_repo, session)
        with tabs[1]:
            _render_cv_import(profile.id if profile else None)
        if profile is None:
            for tab in tabs[2:]:
                with tab:
                    st.info("Crea primero el perfil principal en la pestana Resumen.")
            return
        with tabs[2]:
            _render_experience(profile.id)
        with tabs[3]:
            _render_skills(profile.id, catalogs)
        with tabs[4]:
            _render_evidences(profile.id, catalogs)
        with tabs[5]:
            _render_tools(profile.id, catalogs)
        with tabs[6]:
            _render_education(profile.id, catalogs)
        with tabs[7]:
            _render_certifications(profile.id)
        with tabs[8]:
            _render_target_roles(profile.id, catalogs)
        with tabs[9]:
            _render_target_sectors(profile.id, catalogs)
        with tabs[10]:
            _render_preferences(profile.id)
        with tabs[11]:
            _render_constraints(profile.id, catalogs)
        with tabs[12]:
            _render_growth(profile.id, catalogs)


def _render_summary(profile_repo: ProfileRepository, session) -> None:
    profile = profile_repo.get_main_profile()
    completeness = ProfileCompletenessService(session).calculate(profile)
    st.metric("Completitud del perfil", f"{completeness.total_percentage}%")
    if completeness.missing_components:
        st.warning("Informacion faltante: " + ", ".join(completeness.missing_components))
    for recommendation in completeness.recommendations:
        st.write(f"- {recommendation}")

    with st.form("profile_form"):
        st.subheader("Identidad profesional")
        full_name = st.text_input("Nombre", value=profile.full_name if profile else "")
        professional_title = st.text_input("Titulo profesional", value=profile.professional_title if profile else "")
        professional_summary = st.text_area("Resumen", value=profile.professional_summary if profile else "")
        current_city = st.text_input("Ciudad", value=profile.current_city if profile else "")
        current_province = st.text_input("Provincia", value=profile.current_province if profile else "")
        country = st.text_input("Pais", value=profile.country if profile else "Ecuador")
        years_total_experience = st.number_input(
            "Anios de experiencia",
            min_value=0.0,
            max_value=60.0,
            value=float(profile.years_total_experience or 0) if profile else 0.0,
            step=0.5,
        )
        availability_status = st.text_input("Disponibilidad", value=profile.availability_status or "" if profile else "")
        willing_to_travel = st.selectbox("Disponibilidad para viajar", ["No definido", "Si", "No"])
        willing_to_relocate = st.selectbox("Disponibilidad para reubicarse", ["No definido", "Si", "No"])
        remote_preference = st.text_input("Preferencia remota", value=profile.remote_preference or "" if profile else "")
        linkedin_url = st.text_input("LinkedIn URL", value=profile.linkedin_url or "" if profile else "")
        portfolio_url = st.text_input("Portafolio URL", value=profile.portfolio_url or "" if profile else "")
        submitted = st.form_submit_button("Guardar perfil")
    if submitted:
        payload = {
            "full_name": full_name,
            "professional_title": professional_title,
            "professional_summary": professional_summary,
            "current_city": current_city,
            "current_province": current_province,
            "country": country,
            "years_total_experience": Decimal(str(years_total_experience)),
            "availability_status": availability_status or None,
            "willing_to_travel": _optional_bool(willing_to_travel),
            "willing_to_relocate": _optional_bool(willing_to_relocate),
            "remote_preference": remote_preference or None,
            "linkedin_url": linkedin_url or None,
            "portfolio_url": portfolio_url or None,
        }
        _save_action(lambda: profile_repo.update_profile(profile.id, **payload) if profile else profile_repo.create_profile(**payload))

    if profile:
        st.subheader("Principales habilidades")
        skill_repo = SkillRepository(session)
        for item in skill_repo.list_profile_skills(profile.id)[:8]:
            st.write(f"- {item.skill.name} ({item.level})")
        st.subheader("Principales cargos objetivo")
        career_repo = CareerPreferenceRepository(session)
        for role in career_repo.list_target_roles(profile.id)[:8]:
            st.write(f"- {role.role_name} ({role.priority})")


def _render_cv_import(profile_id: int | None) -> None:
    st.subheader("Carga asistida desde CV")
    st.caption("El archivo se lee localmente para generar un borrador revisable. No se guarda el CV original.")
    uploaded = st.file_uploader("CV en TXT, PDF seleccionable o DOCX", type=["txt", "pdf", "docx"])
    if st.button("Crear borrador desde CV", disabled=uploaded is None):
        if uploaded is None:
            st.warning("Carga un archivo antes de crear el borrador.")
        else:
            try:
                text = CVDocumentReader().extract_text(uploaded.name, uploaded.getvalue())
                draft = CVProfileMapper().build_draft(text, uploaded.name)
                with SessionLocal() as session:
                    draft = CVDraftValidator(session).validate(draft, profile_id)
                st.session_state["cv_profile_draft"] = draft.model_dump(mode="json")
                st.success("Borrador creado. Revisa cada candidato antes de guardar.")
            except ValidationError as exc:
                st.error(str(exc))
            except Exception:
                LOGGER.exception("Unexpected CV import error")
                st.error("No se pudo analizar el CV. Revisa el formato e intenta nuevamente.")

    draft_data = st.session_state.get("cv_profile_draft")
    if not draft_data:
        st.info("Carga un CV para generar candidatos. Los datos no se guardan hasta que confirmes.")
        return

    draft = CVDraft(**draft_data)
    st.metric("Caracteres leidos", draft.text_character_count)
    if draft.warnings:
        for warning in draft.warnings:
            st.warning(warning)
    if not draft.candidates:
        return

    with st.form("cv_profile_review_form"):
        edited_candidates = []
        for index, candidate in enumerate(draft.candidates):
            edited_candidates.append(_render_cv_candidate_editor(candidate.model_dump(mode="json"), index))
        update_review = st.form_submit_button("Actualizar revision")

    if update_review:
        st.session_state["cv_profile_draft"] = CVDraft(
            source_name=draft.source_name,
            text_character_count=draft.text_character_count,
            candidates=edited_candidates,
            warnings=draft.warnings,
        ).model_dump(mode="json")
        st.success("Revision actualizada.")

    confirm = st.checkbox("Confirmo guardar solo candidatos aceptados o editados", key="cv_apply_confirm")
    if st.button("Guardar candidatos confirmados", disabled=not confirm):
        with SessionLocal() as session:
            result = CVDraftApplyService(session).apply(st.session_state["cv_profile_draft"]["candidates"])
        for item in result.saved:
            st.success(item)
        for item in result.skipped:
            st.info(item)
        for item in result.errors:
            st.error(item)
        if not result.has_errors and result.saved:
            st.session_state.pop("cv_profile_draft", None)


def _render_cv_candidate_editor(candidate: dict[str, Any], index: int) -> dict[str, Any]:
    title = f"{_section_label(candidate['section'])} - {candidate['field']} ({candidate['confidence']})"
    with st.expander(title, expanded=index < 3):
        if candidate.get("warnings"):
            for warning in candidate["warnings"]:
                st.warning(warning)
        st.caption(f"Origen: {candidate.get('source_snippet', '')}")
        candidate["status"] = st.radio(
            "Decision",
            ["Pendiente", "Aceptado", "Editado", "Omitido"],
            index=["Pendiente", "Aceptado", "Editado", "Omitido"].index(candidate.get("status", "Pendiente")),
            horizontal=True,
            key=f"cv_status_{index}_{candidate['section']}_{candidate['field']}",
        )
        value = candidate.get("value")
        if isinstance(value, dict):
            candidate["value"] = _render_cv_dict_value(candidate["section"], value, index)
        elif candidate["field"] == "professional_summary":
            candidate["value"] = st.text_area(
                "Valor candidato",
                value=str(value or ""),
                key=f"cv_value_{index}",
            )
        else:
            candidate["value"] = st.text_input(
                "Valor candidato",
                value=str(value or ""),
                key=f"cv_value_{index}",
            )
    return candidate


def _render_cv_dict_value(section: str, value: dict[str, Any], index: int) -> dict[str, Any]:
    edited = dict(value)
    if section == "experience":
        edited["job_title"] = st.text_input("Cargo", value=str(value.get("job_title") or ""), key=f"cv_exp_title_{index}")
        edited["company"] = st.text_input("Empresa", value=str(value.get("company") or ""), key=f"cv_exp_company_{index}")
        edited["start_date"] = st.text_input(
            "Fecha inicio (YYYY-MM-DD)",
            value=str(value.get("start_date") or ""),
            key=f"cv_exp_start_{index}",
        )
        edited["is_current"] = st.checkbox("Empleo actual", value=bool(value.get("is_current")), key=f"cv_exp_current_{index}")
        edited["end_date"] = ""
        if not edited["is_current"]:
            edited["end_date"] = st.text_input(
                "Fecha fin (YYYY-MM-DD)",
                value=str(value.get("end_date") or ""),
                key=f"cv_exp_end_{index}",
            )
        edited["description"] = st.text_area(
            "Responsabilidades",
            value=str(value.get("description") or ""),
            key=f"cv_exp_description_{index}",
        )
        edited["achievements"] = st.text_area(
            "Logros",
            value=str(value.get("achievements") or ""),
            key=f"cv_exp_achievements_{index}",
        )
        edited["city"] = st.text_input("Ciudad", value=str(value.get("city") or ""), key=f"cv_exp_city_{index}")
        edited["sector"] = st.text_input("Sector", value=str(value.get("sector") or ""), key=f"cv_exp_sector_{index}")
    elif section == "education":
        edited["degree"] = st.text_input("Titulo o carrera", value=str(value.get("degree") or ""), key=f"cv_edu_degree_{index}")
        edited["field_of_study"] = st.text_input(
            "Campo de estudio",
            value=str(value.get("field_of_study") or ""),
            key=f"cv_edu_field_{index}",
        )
        edited["institution"] = st.text_input(
            "Institucion",
            value=str(value.get("institution") or ""),
            key=f"cv_edu_institution_{index}",
        )
        edited["education_level"] = st.text_input(
            "Nivel educativo",
            value=str(value.get("education_level") or "Universitario"),
            key=f"cv_edu_level_{index}",
        )
        edited["status"] = st.selectbox(
            "Estado",
            ["En curso", "Completado", "Suspendido", "Incompleto"],
            index=["En curso", "Completado", "Suspendido", "Incompleto"].index(value.get("status", "En curso")),
            key=f"cv_edu_status_{index}",
        )
    elif section == "certification":
        edited["name"] = st.text_input("Certificacion", value=str(value.get("name") or ""), key=f"cv_cert_name_{index}")
        edited["issuing_organization"] = st.text_input(
            "Organizacion emisora",
            value=str(value.get("issuing_organization") or ""),
            key=f"cv_cert_org_{index}",
        )
        edited["does_not_expire"] = st.checkbox(
            "No expira",
            value=bool(value.get("does_not_expire", True)),
            key=f"cv_cert_no_expire_{index}",
        )
    elif section == "target_role":
        edited["role_name"] = st.text_input("Cargo objetivo", value=str(value.get("role_name") or ""), key=f"cv_role_{index}")
        edited["priority"] = st.selectbox(
            "Prioridad",
            ["Principal", "Secundaria", "Exploratoria"],
            index=["Principal", "Secundaria", "Exploratoria"].index(value.get("priority", "Exploratoria")),
            key=f"cv_role_priority_{index}",
        )
        edited["desired_level"] = st.text_input(
            "Nivel deseado",
            value=str(value.get("desired_level") or ""),
            key=f"cv_role_level_{index}",
        )
    elif section == "evidence":
        edited["skill_name"] = st.text_input(
            "Habilidad asociada",
            value=str(value.get("skill_name") or ""),
            key=f"cv_evidence_skill_{index}",
        )
        edited["evidence_type"] = st.selectbox(
            "Tipo de evidencia",
            ["Proyecto", "Responsabilidad laboral", "Logro", "Certificacion", "Curso", "Indicador", "Otro"],
            index=["Proyecto", "Responsabilidad laboral", "Logro", "Certificacion", "Curso", "Indicador", "Otro"].index(
                value.get("evidence_type", "Logro")
            ),
            key=f"cv_evidence_type_{index}",
        )
        edited["title"] = st.text_input("Titulo", value=str(value.get("title") or ""), key=f"cv_evidence_title_{index}")
        edited["description"] = st.text_area(
            "Descripcion",
            value=str(value.get("description") or ""),
            key=f"cv_evidence_description_{index}",
        )
        edited["metric_value"] = st.text_input(
            "Valor cuantificable opcional",
            value=str(value.get("metric_value") or ""),
            key=f"cv_evidence_metric_{index}",
        )
        edited["metric_unit"] = st.text_input(
            "Unidad opcional",
            value=str(value.get("metric_unit") or ""),
            key=f"cv_evidence_unit_{index}",
        )
    return edited


def _section_label(section: str) -> str:
    labels = {
        "profile": "Perfil",
        "experience": "Experiencia",
        "skill": "Habilidad",
        "tool": "Herramienta",
        "education": "Formacion",
        "certification": "Certificacion",
        "target_role": "Cargo objetivo",
        "evidence": "Evidencia",
    }
    return labels.get(section, section)


def _render_experience(profile_id: int) -> None:
    with SessionLocal() as session:
        repo = ExperienceRepository(session)
        st.subheader("Experiencia laboral")
        for item in repo.list_experiences(profile_id):
            with st.expander(f"{item.job_title} - {item.company}"):
                st.write(item.description or "Sin responsabilidades registradas.")
                st.write(item.achievements or "Sin logros registrados.")
                with st.form(f"edit_experience_{item.id}"):
                    edited_company = st.text_input("Empresa", value=item.company, key=f"company_{item.id}")
                    edited_job_title = st.text_input("Cargo", value=item.job_title, key=f"title_{item.id}")
                    edited_sector = st.text_input("Sector", value=item.sector or "", key=f"sector_{item.id}")
                    edited_city = st.text_input("Ciudad", value=item.city or "", key=f"city_{item.id}")
                    edited_start = st.date_input("Fecha de inicio", value=item.start_date, key=f"start_{item.id}")
                    edited_current = st.checkbox("Empleo actual", value=item.is_current, key=f"current_{item.id}")
                    edited_end = None
                    if not edited_current:
                        edited_end = st.date_input(
                            "Fecha de fin",
                            value=item.end_date or date.today(),
                            key=f"end_{item.id}",
                        )
                    edited_description = st.text_area(
                        "Responsabilidades",
                        value=item.description or "",
                        key=f"description_{item.id}",
                    )
                    edited_achievements = st.text_area(
                        "Logros",
                        value=item.achievements or "",
                        key=f"achievements_{item.id}",
                    )
                    edited_people = st.number_input(
                        "Personas gestionadas",
                        min_value=0,
                        value=item.people_managed or 0,
                        step=1,
                        key=f"people_{item.id}",
                    )
                    update_submitted = st.form_submit_button("Actualizar experiencia")
                if update_submitted:
                    _save_action(
                        lambda item_id=item.id: repo.update_experience(
                            item_id,
                            company=edited_company,
                            job_title=edited_job_title,
                            sector=edited_sector or None,
                            city=edited_city or None,
                            start_date=edited_start,
                            end_date=edited_end,
                            is_current=edited_current,
                            description=edited_description or None,
                            achievements=edited_achievements or None,
                            people_managed=edited_people or None,
                        )
                    )
                confirm = st.checkbox("Confirmo eliminar esta experiencia", key=f"delete_exp_{item.id}")
                if st.button("Eliminar experiencia", key=f"btn_exp_{item.id}"):
                    _save_action(lambda item_id=item.id, ok=confirm: repo.delete_experience(item_id, ok))

        with st.form("experience_form"):
            company = st.text_input("Empresa")
            job_title = st.text_input("Cargo")
            sector = st.text_input("Sector")
            city = st.text_input("Ciudad")
            start_date = st.date_input("Fecha de inicio", value=date.today())
            is_current = st.checkbox("Empleo actual")
            end_date = None if is_current else st.date_input("Fecha de fin", value=date.today())
            description = st.text_area("Responsabilidades")
            achievements = st.text_area("Logros")
            people_managed = st.number_input("Personas gestionadas", min_value=0, value=0, step=1)
            submitted = st.form_submit_button("Guardar experiencia")
        if submitted:
            _save_action(
                lambda: repo.create_experience(
                    profile_id,
                    company=company,
                    job_title=job_title,
                    sector=sector or None,
                    city=city or None,
                    start_date=start_date,
                    end_date=end_date,
                    is_current=is_current,
                    description=description or None,
                    achievements=achievements or None,
                    people_managed=people_managed or None,
                )
            )


def _render_skills(profile_id: int, catalogs: dict) -> None:
    with SessionLocal() as session:
        repo = SkillRepository(session)
        st.subheader("Habilidades")
        for item in repo.list_profile_skills(profile_id):
            evidence_count = len(repo.list_evidences(item.id))
            st.write(f"- {item.skill.name} | {item.level} | evidencias: {evidence_count}")
        with st.form("skill_form"):
            name = st.text_input("Habilidad")
            category = st.selectbox("Categoria", catalogs["skill_categories"])
            level = st.selectbox("Nivel", catalogs["skill_levels"], index=1)
            years = st.number_input("Anios de experiencia", min_value=0.0, value=0.0, step=0.5)
            interest = st.selectbox("Interes", [""] + catalogs["interest_levels"])
            is_core = st.checkbox("Habilidad principal")
            notes = st.text_area("Notas")
            submitted = st.form_submit_button("Asignar habilidad")
        if submitted:
            def action():
                skill = repo.create_or_get_skill(name, category)
                return repo.assign_skill(
                    profile_id,
                    skill.id,
                    level=level,
                    years_experience=Decimal(str(years)),
                    interest_level=interest or None,
                    is_core_skill=is_core,
                    self_assessed=True,
                    notes=notes or None,
                )
            _save_action(action)


def _render_evidences(profile_id: int, catalogs: dict) -> None:
    with SessionLocal() as session:
        skill_repo = SkillRepository(session)
        assignments = skill_repo.list_profile_skills(profile_id)
        if not assignments:
            st.info("Asigna primero una habilidad.")
            return
        options = {f"{item.skill.name} ({item.level})": item.id for item in assignments}
        for evidence in skill_repo.list_evidences():
            st.write(f"- {evidence.title} | {evidence.evidence_type}")
        with st.form("evidence_form"):
            selected = st.selectbox("Habilidad", list(options.keys()))
            evidence_type = st.selectbox("Tipo", catalogs["evidence_types"])
            title = st.text_input("Titulo")
            description = st.text_area("Descripcion")
            metric_value = st.number_input("Valor cuantificable", min_value=0.0, value=0.0, step=1.0)
            metric_unit = st.text_input("Unidad")
            submitted = st.form_submit_button("Guardar evidencia")
        if submitted:
            _save_action(
                lambda: skill_repo.add_evidence(
                    options[selected],
                    evidence_type=evidence_type,
                    title=title,
                    description=description,
                    metric_value=Decimal(str(metric_value)) if metric_value else None,
                    metric_unit=metric_unit or None,
                )
            )


def _render_tools(profile_id: int, catalogs: dict) -> None:
    with SessionLocal() as session:
        repo = ToolRepository(session)
        st.subheader("Herramientas")
        for item in repo.list_profile_tools(profile_id):
            st.write(f"- {item.tool.name} ({item.level})")
        with st.form("tool_form"):
            name = st.text_input("Herramienta")
            category = st.selectbox("Categoria", catalogs["tool_categories"])
            level = st.selectbox("Nivel", catalogs["skill_levels"], index=1)
            years = st.number_input("Anios de uso", min_value=0.0, value=0.0, step=0.5)
            notes = st.text_area("Notas")
            submitted = st.form_submit_button("Asignar herramienta")
        if submitted:
            def action():
                tool = repo.create_or_get_tool(name, category)
                return repo.assign_tool(profile_id, tool.id, level=level, years_experience=Decimal(str(years)), notes=notes)
            _save_action(action)


def _render_education(profile_id: int, catalogs: dict) -> None:
    with SessionLocal() as session:
        repo = EducationRepository(session)
        for record in repo.list_records(profile_id):
            st.write(f"- {record.degree} | {record.field_of_study} | {record.status}")
        with st.form("education_form"):
            institution = st.text_input("Institucion")
            degree = st.text_input("Carrera o titulo")
            field = st.text_input("Campo de estudio")
            level = st.text_input("Nivel educativo")
            is_current = st.checkbox("En curso")
            status = st.selectbox("Estado", catalogs["education_statuses"])
            notes = st.text_area("Notas")
            submitted = st.form_submit_button("Guardar formacion")
        if submitted:
            _save_action(lambda: repo.create(profile_id, institution=institution, degree=degree, field_of_study=field, education_level=level, is_current=is_current, status=status, notes=notes or None))


def _render_certifications(profile_id: int) -> None:
    with SessionLocal() as session:
        repo = CertificationRepository(session)
        for cert in repo.list_records(profile_id):
            st.write(f"- {cert.name} | {cert.issuing_organization}")
        with st.form("certification_form"):
            name = st.text_input("Certificacion")
            organization = st.text_input("Organizacion emisora")
            does_not_expire = st.checkbox("No expira")
            credential_url = st.text_input("URL de credencial")
            notes = st.text_area("Notas")
            submitted = st.form_submit_button("Guardar certificacion")
        if submitted:
            _save_action(lambda: repo.create(profile_id, name=name, issuing_organization=organization, does_not_expire=does_not_expire, credential_url=credential_url or None, notes=notes or None))


def _render_target_roles(profile_id: int, catalogs: dict) -> None:
    with SessionLocal() as session:
        repo = CareerPreferenceRepository(session)
        for role in repo.list_target_roles(profile_id):
            st.write(f"- {role.role_name} | {role.priority}")
        with st.form("target_role_form"):
            role_name = st.text_input("Cargo objetivo")
            priority = st.selectbox("Prioridad", catalogs["priorities"])
            desired_level = st.selectbox("Nivel deseado", [""] + catalogs["professional_levels"])
            minimum_salary = st.number_input("Salario minimo", min_value=0.0, value=0.0, step=50.0)
            submitted = st.form_submit_button("Guardar cargo")
        if submitted:
            _save_action(lambda: repo.add_target_role(profile_id, role_name=role_name, priority=priority, desired_level=desired_level or None, minimum_salary=Decimal(str(minimum_salary)) if minimum_salary else None))


def _render_target_sectors(profile_id: int, catalogs: dict) -> None:
    with SessionLocal() as session:
        repo = CareerPreferenceRepository(session)
        for sector in repo.list_target_sectors(profile_id):
            st.write(f"- {sector.sector_name} | {sector.priority}")
        with st.form("target_sector_form"):
            sector_name = st.text_input("Sector")
            priority = st.selectbox("Prioridad", catalogs["priorities"])
            submitted = st.form_submit_button("Guardar sector")
        if submitted:
            _save_action(lambda: repo.add_target_sector(profile_id, sector_name=sector_name, priority=priority))


def _render_preferences(profile_id: int) -> None:
    with SessionLocal() as session:
        repo = CareerPreferenceRepository(session)
        st.warning("Las preferencias influyen en el orden. Las restricciones eliminan oportunidades incompatibles.")
        preferences = repo.get_preferences(profile_id)
        if preferences:
            st.write(f"Ciudades: {', '.join(preferences.preferred_cities)}")
            st.write(f"Modalidades: {', '.join(preferences.accepted_modalities)}")
        with st.form("preferences_form"):
            cities = st.text_input("Ciudades preferidas", value=", ".join(preferences.preferred_cities) if preferences else "")
            provinces = st.text_input("Provincias preferidas", value=", ".join(preferences.preferred_provinces) if preferences else "")
            modalities = st.text_input("Modalidades aceptadas", value=", ".join(preferences.accepted_modalities) if preferences else "")
            minimum_salary = st.number_input("Salario minimo", min_value=0.0, value=0.0, step=50.0)
            expected_salary = st.number_input("Salario esperado", min_value=0.0, value=0.0, step=50.0)
            accepts_shift = st.checkbox("Acepta turnos")
            accepts_weekend = st.checkbox("Acepta fines de semana")
            accepts_temp = st.checkbox("Acepta contrato temporal")
            commute = st.number_input("Traslado maximo en minutos", min_value=0, value=0, step=5)
            submitted = st.form_submit_button("Guardar preferencias")
        if submitted:
            _save_action(
                lambda: repo.set_preferences(
                    profile_id,
                    preferred_cities=_split_values(cities),
                    preferred_provinces=_split_values(provinces),
                    accepted_modalities=_split_values(modalities),
                    minimum_salary=Decimal(str(minimum_salary)) if minimum_salary else None,
                    expected_salary=Decimal(str(expected_salary)) if expected_salary else None,
                    currency="USD",
                    accepts_shift_work=accepts_shift,
                    accepts_weekend_work=accepts_weekend,
                    accepts_temporary_contract=accepts_temp,
                    maximum_commute_minutes=commute or None,
                )
            )


def _render_constraints(profile_id: int, catalogs: dict) -> None:
    with SessionLocal() as session:
        repo = CareerPreferenceRepository(session)
        for issue in repo.detect_basic_contradictions(profile_id):
            st.error(f"Contradiccion detectada: {issue}")
        for constraint in repo.list_constraints(profile_id):
            st.write(f"- {constraint.constraint_type} {constraint.operator} {constraint.value}")
        with st.form("constraint_form"):
            constraint_type = st.selectbox("Tipo", catalogs["constraint_types"])
            operator = st.selectbox("Operador", catalogs["constraint_operators"])
            value = st.text_input("Valor")
            reason = st.text_area("Motivo")
            submitted = st.form_submit_button("Guardar restriccion")
        if submitted:
            _save_action(lambda: repo.add_constraint(profile_id, constraint_type=constraint_type, operator=operator, value=value, reason=reason or None))


def _render_growth(profile_id: int, catalogs: dict) -> None:
    with SessionLocal() as session:
        repo = CareerPreferenceRepository(session)
        for goal in repo.list_growth_goals(profile_id):
            st.write(f"- {goal.title} | {goal.status} | {goal.progress_percentage}%")
        with st.form("growth_form"):
            title = st.text_input("Objetivo")
            description = st.text_area("Descripcion")
            target_role = st.text_input("Cargo o rol asociado")
            priority = st.selectbox("Prioridad", catalogs["priorities"])
            status = st.selectbox("Estado", catalogs["goal_statuses"])
            progress = st.slider("Progreso", min_value=0, max_value=100, value=0)
            submitted = st.form_submit_button("Guardar objetivo")
        if submitted:
            _save_action(lambda: repo.add_growth_goal(profile_id, title=title, description=description, target_role=target_role or None, priority=priority, status=status, progress_percentage=progress))


def _save_action(action) -> None:
    try:
        action()
    except ValidationError as exc:
        st.error(str(exc))
    except Exception:
        LOGGER.exception("Unexpected profile UI error")
        st.error("No se pudo guardar la informacion. Revisa los datos e intenta nuevamente.")
    else:
        st.success("Informacion guardada correctamente.")


def _split_values(raw: str) -> list[str]:
    return [value.strip() for value in raw.split(",") if value.strip()]


def _optional_bool(value: str) -> bool | None:
    if value == "Si":
        return True
    if value == "No":
        return False
    return None

"""Streamlit views for deterministic compatibility evaluations."""

from __future__ import annotations

from decimal import Decimal
import logging

import streamlit as st

from app.config import load_compatibility_config
from app.database import SessionLocal, create_tables
from app.repositories import EvaluationRepository, JobRepository, ProfileRepository, SkillRepository, ToolRepository
from app.services.evaluation_engine import EvaluationEngineService
from app.services.requirement_extraction import RequirementExtractionService
from app.services.validation import ValidationError

LOGGER = logging.getLogger(__name__)


def render_compatibility_page() -> None:
    """Render compatibility evaluation UI."""

    create_tables()
    st.header("Compatibilidad")
    st.caption("Motor deterministico y explicable de compatibilidad entre perfil profesional y vacantes.")
    tabs = st.tabs(["Resumen", "Resultados", "Detalle", "Requisitos", "Evaluar"])
    with tabs[0]:
        _render_summary()
    with tabs[1]:
        _render_results()
    with tabs[2]:
        _render_detail()
    with tabs[3]:
        _render_requirements()
    with tabs[4]:
        _render_evaluate()


def _render_summary() -> None:
    with SessionLocal() as session:
        summary = EvaluationRepository(session).summary()
        by_eligibility = summary["by_eligibility"]
        cols = st.columns(5)
        cols[0].metric("Vacantes evaluadas", summary["total"])
        cols[1].metric("Obsoletas", summary["stale"])
        cols[2].metric("Compatibilidad promedio", f"{summary['average_score']:.1f}")
        cols[3].metric("Elegibles", by_eligibility.get("Elegible", 0))
        cols[4].metric("Requieren revision", by_eligibility.get("Requiere revision", 0))
        st.subheader("Distribucion por recomendacion")
        st.dataframe(
            [{"Recomendacion": key, "Cantidad": value} for key, value in summary["by_recommendation"].items()],
            use_container_width=True,
        )


def _render_results() -> None:
    with SessionLocal() as session:
        repo = EvaluationRepository(session)
        col_a, col_b, col_c = st.columns(3)
        with col_a:
            min_score = st.slider("Puntaje minimo", 0, 100, 0)
        with col_b:
            min_confidence = st.slider("Confianza minima", 0, 100, 0)
        with col_c:
            stale_filter = st.selectbox("Actualizacion", ["Todas", "Vigentes", "Obsoletas"])
        eligibility = st.selectbox("Elegibilidad", [""] + ["Elegible", "No elegible", "Requiere revision", "Informacion insuficiente"])
        recommendation = st.selectbox(
            "Recomendacion",
            ["", "Alta compatibilidad", "Buena compatibilidad", "Oportunidad de crecimiento", "Exploratoria", "Baja compatibilidad", "No recomendada", "Requiere revision"],
        )
        filters = {"min_score": min_score, "min_confidence": min_confidence}
        if stale_filter != "Todas":
            filters["is_stale"] = stale_filter == "Obsoletas"
        if eligibility:
            filters["eligibility_status"] = eligibility
        if recommendation:
            filters["recommendation_type"] = recommendation
        results = repo.list_results(filters, limit=300)
        rows = []
        for item in results:
            primary_gap = item.gaps[0]["requirement"] if item.gaps else ""
            rows.append(
                {
                    "ID": item.id,
                    "Vacante": item.job_id,
                    "Cargo": item.job.title,
                    "Empresa": item.job.company,
                    "Compatibilidad": float(item.total_score),
                    "Confianza": float(item.confidence_score),
                    "Cobertura": float(item.data_coverage_score),
                    "Elegibilidad": item.eligibility_status,
                    "Recomendacion": item.recommendation_type,
                    "Brecha principal": primary_gap,
                    "Fecha": item.created_at,
                    "Estado": "Obsoleta" if item.is_stale else "Vigente",
                }
            )
        st.dataframe(rows, use_container_width=True)


def _render_detail() -> None:
    with SessionLocal() as session:
        repo = EvaluationRepository(session)
        evaluation_id = st.number_input("ID de evaluacion", min_value=0, value=0, step=1)
        if not evaluation_id:
            st.info("Selecciona un ID de evaluacion desde la tabla de resultados.")
            return
        try:
            evaluation = repo.get_evaluation(int(evaluation_id))
        except ValidationError as exc:
            st.error(str(exc))
            return
        if evaluation.is_stale:
            st.warning("Esta evaluacion utiliza informacion anterior. Recalcule para obtener un resultado actualizado.")
        cols = st.columns(3)
        cols[0].metric("Compatibilidad", f"{float(evaluation.total_score):.0f}/100")
        cols[1].metric("Confianza", f"{float(evaluation.confidence_score):.0f}/100")
        cols[2].metric("Cobertura", f"{float(evaluation.data_coverage_score):.0f}/100")
        st.write(f"Elegibilidad: **{evaluation.eligibility_status}**")
        st.write(f"Recomendacion: **{evaluation.recommendation_type}**")
        st.text(evaluation.summary_explanation)
        st.subheader("Desglose")
        for component in evaluation.components:
            st.progress(float(component.raw_score), text=f"{component.component_name}: {float(component.awarded_points):.1f}/{component.weight}")
            st.caption(component.explanation)
        _json_section("Fortalezas", evaluation.strengths)
        _json_section("Brechas", evaluation.gaps)
        _json_section("Restricciones", evaluation.hard_constraint_results)
        _json_section("Datos faltantes", evaluation.missing_information)
        _json_section("Oportunidades de crecimiento", evaluation.growth_opportunities)
        st.write(f"Version del motor: `{evaluation.scoring_version}`")
        if st.button("Recalcular esta vacante"):
            _save_action(lambda: EvaluationEngineService(session).evaluate_job(evaluation.job_id, evaluation.profile_id))


def _render_requirements() -> None:
    st.warning("Los requisitos han sido identificados mediante reglas y pueden requerir revision humana.")
    with SessionLocal() as session:
        job_repo = JobRepository(session)
        req_repo = EvaluationRepository(session)
        jobs = job_repo.list_jobs({"is_active": True}, limit=500)
        if not jobs:
            st.info("No hay vacantes activas.")
            return
        options = {f"{job.id} - {job.title} - {job.company}": job.id for job in jobs}
        selected = st.selectbox("Vacante", list(options.keys()))
        job = job_repo.get_job(options[selected])
        if st.button("Extraer requisitos"):
            _save_action(lambda: RequirementExtractionService(session).extract_for_job(job, persist=True))
        requirements = req_repo.list_requirements(job.id, active_only=False)
        skills = {skill.name: skill.id for skill in SkillRepository(session).list_skills()}
        tools = {tool.name: tool.id for tool in ToolRepository(session).list_tools()}
        for req in requirements:
            with st.expander(f"{req.requirement_type}: {req.raw_text} ({req.importance})"):
                with st.form(f"requirement_{req.id}"):
                    req_type = st.selectbox("Tipo", _requirement_types(), index=_index(_requirement_types(), req.requirement_type))
                    raw_text = st.text_input("Texto original", value=req.raw_text)
                    normalized = st.text_input("Valor normalizado", value=req.normalized_value or "")
                    importance = st.selectbox("Importancia", _importance_options(), index=_index(_importance_options(), req.importance))
                    active = st.checkbox("Activo", value=req.is_active)
                    confirmed = st.checkbox("Confirmado por usuario", value=req.is_confirmed_by_user)
                    selected_skill = st.selectbox("Habilidad vinculada", [""] + list(skills.keys()))
                    selected_tool = st.selectbox("Herramienta vinculada", [""] + list(tools.keys()))
                    submitted = st.form_submit_button("Guardar requisito")
                if submitted:
                    _save_action(
                        lambda req_id=req.id: req_repo.update_requirement(
                            req_id,
                            requirement_type=req_type,
                            raw_text=raw_text,
                            normalized_value=normalized or None,
                            importance=importance,
                            is_active=active,
                            is_confirmed_by_user=confirmed,
                            skill_id=skills.get(selected_skill),
                            tool_id=tools.get(selected_tool),
                            extraction_method="Manual" if confirmed else req.extraction_method,
                        )
                    )
        with st.form("manual_requirement"):
            st.subheader("Agregar requisito manual")
            req_type = st.selectbox("Tipo", _requirement_types(), key="new_req_type")
            raw_text = st.text_input("Texto")
            normalized = st.text_input("Normalizado")
            importance = st.selectbox("Importancia", _importance_options(), key="new_importance")
            submitted = st.form_submit_button("Agregar")
        if submitted:
            _save_action(
                lambda: req_repo.add_requirement(
                    job_id=job.id,
                    requirement_type=req_type,
                    raw_text=raw_text,
                    normalized_value=normalized or None,
                    importance=importance,
                    source_field="manual",
                    extraction_method="Manual",
                    extraction_confidence=Decimal("1.00"),
                    is_confirmed_by_user=True,
                    is_active=True,
                )
            )


def _render_evaluate() -> None:
    with SessionLocal() as session:
        profile = ProfileRepository(session).get_main_profile()
        if profile is None:
            st.info("Crea primero un perfil profesional.")
            return
        jobs = JobRepository(session).list_jobs({"is_active": True}, limit=1000)
        options = {f"{job.id} - {job.title} - {job.company}": job.id for job in jobs}
        selected = st.multiselect("Vacantes", list(options.keys()))
        confirm = st.checkbox("Confirmo iniciar la evaluacion")
        if st.button("Evaluar seleccionadas"):
            if not confirm:
                st.warning("Confirma antes de iniciar el lote.")
            else:
                _save_action(lambda: EvaluationEngineService(session).evaluate_jobs([options[item] for item in selected], profile.id))
        if st.button("Evaluar todas las activas"):
            if not confirm:
                st.warning("Confirma antes de iniciar el lote.")
            else:
                with st.spinner("Evaluando vacantes activas..."):
                    _save_action(lambda: EvaluationEngineService(session).evaluate_all_active(profile_id=profile.id))


def _json_section(title: str, data) -> None:
    st.subheader(title)
    if data:
        st.json(data)
    else:
        st.write("Sin registros.")


def _save_action(action) -> None:
    try:
        result = action()
    except ValidationError as exc:
        st.error(str(exc))
    except Exception:
        LOGGER.exception("Compatibility UI error")
        st.error("No se pudo completar la evaluacion.")
    else:
        st.success("Accion completada correctamente.")
        if result is not None:
            st.write(result)


def _requirement_types() -> list[str]:
    return ["Habilidad", "Herramienta", "Experiencia", "Formacion", "Certificacion", "Idioma", "Modalidad", "Ubicacion", "Jornada", "Contrato", "Viaje", "Reubicacion", "Salario", "Responsabilidad", "Otro"]


def _importance_options() -> list[str]:
    return ["Obligatorio", "Deseable", "Informativo", "No determinada"]


def _index(options: list[str], value: str) -> int:
    return options.index(value) if value in options else 0

"""Streamlit views for Phase 6 supervised feedback learning."""

from __future__ import annotations

from datetime import date, timedelta

import streamlit as st

from app.config import load_feedback_learning_config
from app.database import SessionLocal, create_tables
from app.repositories import FeedbackRepository, JobRepository, ProfileRepository
from app.services.application_outcome_service import ApplicationOutcomeService
from app.services.feedback_service import FeedbackService
from app.services.learning_service import LearningService
from app.services.validation import ValidationError


def render_feedback_learning_page() -> None:
    """Render the supervised learning panel."""

    create_tables()
    st.header("Retroalimentacion y aprendizaje")
    st.caption("El aprendizaje es deterministico, supervisado y reversible. Ninguna propuesta se aplica sin aprobacion humana.")
    tabs = st.tabs(["Senales", "Resultados", "Analisis", "Propuestas", "Historial"])
    with tabs[0]:
        _render_feedback_events()
    with tabs[1]:
        _render_outcomes()
    with tabs[2]:
        _render_analysis()
    with tabs[3]:
        _render_proposals()
    with tabs[4]:
        _render_history()


def _profile_id(session) -> int | None:
    profile = ProfileRepository(session).get_main_profile()
    if profile is None:
        st.warning("Crea un perfil profesional antes de usar aprendizaje.")
        return None
    return profile.id


def _render_feedback_events() -> None:
    with SessionLocal() as session:
        profile_id = _profile_id(session)
        if profile_id is None:
            return
        config = load_feedback_learning_config()
        jobs = JobRepository(session).list_jobs({"is_active": True}, limit=200)
        if not jobs:
            st.info("No hay vacantes para registrar senales.")
            return
        options = {f"{job.id} - {job.title} - {job.company}": job for job in jobs}
        with st.form("feedback_event_form"):
            selected = st.selectbox("Vacante", list(options))
            category = st.selectbox("Categoria", config["event_categories"])
            event_type = _event_type_select(config, category)
            source = st.selectbox("Fuente", config["event_sources"], index=config["event_sources"].index("Usuario"))
            reason = st.text_input("Motivo")
            notes = st.text_area("Notas")
            submitted = st.form_submit_button("Registrar senal")
            if submitted:
                job = options[selected]
                _run_action(
                    lambda: FeedbackService(session, config).register_event(
                        profile_id=profile_id,
                        job_id=job.id,
                        event_type=event_type,
                        event_category=category,
                        source=source,
                        reason_code=reason,
                        notes=notes,
                    )
                )


def _event_type_select(config: dict, category: str) -> str:
    group = {
        "Implicita": "implicit",
        "Explicita": "explicit",
        "Resultado": "outcomes",
        "Correccion": "corrections",
        "Preferencia": "preferences",
    }[category]
    return st.selectbox("Tipo de evento", list(config["feedback_signal_weights"][group]))


def _render_outcomes() -> None:
    with SessionLocal() as session:
        profile_id = _profile_id(session)
        if profile_id is None:
            return
        repo = FeedbackRepository(session)
        config = load_feedback_learning_config()
        applications = repo.list_applications(date.today() - timedelta(days=365), date.today())
        if not applications:
            st.info("No hay postulaciones registradas.")
            return
        options = {f"{item.id} - {item.job.title} - {item.job.company}": item for item in applications}
        with st.form("application_outcome_form"):
            selected = st.selectbox("Postulacion", list(options))
            outcome_type = st.selectbox("Resultado", config["application_outcome_types"])
            outcome_date = st.date_input("Fecha del resultado", value=date.today())
            stage = st.text_input("Etapa", value=outcome_type)
            company_response = st.text_input("Respuesta de empresa", value=outcome_type)
            user_assessment = st.text_input("Evaluacion del usuario")
            salary_offered = st.number_input("Salario ofertado", min_value=0.0, value=0.0, step=50.0)
            currency = st.text_input("Moneda", value="USD")
            rejection_reason = st.text_input("Motivo de rechazo")
            notes = st.text_area("Notas")
            submitted = st.form_submit_button("Registrar resultado")
            if submitted:
                application = options[selected]
                _run_action(
                    lambda: ApplicationOutcomeService(session, config).record_outcome(
                        application.id,
                        profile_id,
                        outcome_type,
                        outcome_date,
                        stage,
                        company_response,
                        user_assessment=user_assessment,
                        salary_offered=salary_offered or None,
                        currency=currency,
                        rejection_reason=rejection_reason,
                        notes=notes,
                    )
                )


def _render_analysis() -> None:
    with SessionLocal() as session:
        profile_id = _profile_id(session)
        if profile_id is None:
            return
        default_end = date.today()
        default_start = default_end - timedelta(days=90)
        col_a, col_b = st.columns(2)
        period_start = col_a.date_input("Desde", value=default_start)
        period_end = col_b.date_input("Hasta", value=default_end)
        if st.button("Ejecutar analisis", use_container_width=True):
            _run_action(lambda: LearningService(session).run_analysis(profile_id, period_start, period_end))
        runs = FeedbackRepository(session).list_recent_runs(profile_id)
        st.dataframe(
            [
                {
                    "ID": item.id,
                    "Estado": item.status,
                    "Periodo": f"{item.period_start} a {item.period_end}",
                    "Eventos": item.feedback_events_considered,
                    "Postulaciones": item.applications_considered,
                    "Resultados": item.outcomes_considered,
                    "Propuestas": item.proposals_generated,
                    "Advertencias": "; ".join(item.warnings_json or []),
                }
                for item in runs
            ],
            use_container_width=True,
            hide_index=True,
        )
        if runs:
            selected_run = st.selectbox("Ver metricas de corrida", [run.id for run in runs])
            metrics = FeedbackRepository(session).list_metrics(selected_run)
            st.dataframe(
                [
                    {
                        "Metrica": item.metric_name,
                        "Ambito": item.metric_scope,
                        "Valor": float(item.metric_value),
                        "Muestra": item.sample_size,
                        "Confianza": item.confidence_level,
                        "Explicacion": item.explanation,
                    }
                    for item in metrics
                ],
                use_container_width=True,
                hide_index=True,
            )


def _render_proposals() -> None:
    with SessionLocal() as session:
        profile_id = _profile_id(session)
        if profile_id is None:
            return
        repo = FeedbackRepository(session)
        proposals = repo.list_proposals(profile_id)
        for proposal in proposals:
            with st.expander(f"{proposal.id} - {proposal.proposal_type} - {proposal.status}"):
                st.write(proposal.evidence_summary)
                st.write(proposal.expected_effect)
                if proposal.expires_at:
                    st.caption(f"Vence: {proposal.expires_at}")
                st.json(proposal.evidence_json)
                cols = st.columns(5)
                can_review = proposal.status in {"Pendiente", "Pospuesta"}
                can_postpone = proposal.status == "Pendiente"
                can_apply = proposal.status == "Aprobada"
                can_revert = proposal.status == "Aplicada"
                if cols[0].button("Aprobar", key=f"approve_{proposal.id}", disabled=not can_review):
                    _run_action(lambda proposal_id=proposal.id: LearningService(session).review_proposal(proposal_id, True))
                if cols[1].button("Rechazar", key=f"reject_{proposal.id}", disabled=not can_review):
                    _run_action(lambda proposal_id=proposal.id: LearningService(session).review_proposal(proposal_id, False))
                if cols[2].button("Posponer", key=f"postpone_{proposal.id}", disabled=not can_postpone):
                    _run_action(lambda proposal_id=proposal.id: LearningService(session).postpone_proposal(proposal_id))
                if cols[3].button("Aplicar", key=f"apply_{proposal.id}", disabled=not can_apply):
                    _run_action(lambda proposal_id=proposal.id: LearningService(session).apply_proposal(proposal_id))
                if cols[4].button("Revertir", key=f"revert_{proposal.id}", disabled=not can_revert):
                    _run_action(lambda proposal_id=proposal.id: LearningService(session).revert_proposal(proposal_id))


def _render_history() -> None:
    with SessionLocal() as session:
        profile_id = _profile_id(session)
        if profile_id is None:
            return
        changes = FeedbackRepository(session).list_configuration_changes(profile_id)
        st.dataframe(
            [
                {
                    "Fecha": item.changed_at,
                    "Area": item.configuration_area,
                    "Motivo": item.reason,
                    "Cambiado por": item.changed_by,
                    "Revertido": item.reverted_at,
                }
                for item in changes
            ],
            use_container_width=True,
            hide_index=True,
        )


def _run_action(action) -> None:
    try:
        result = action()
        st.success("Operacion completada.")
        if isinstance(result, dict):
            st.json({key: value for key, value in result.items() if isinstance(value, (str, int, float, bool, list, dict))})
    except ValidationError as exc:
        st.warning(str(exc))
    except Exception as exc:
        st.error(f"No se pudo completar la operacion: {exc}")

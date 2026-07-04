"""Streamlit views for the Phase 5 strategic inbox."""

from __future__ import annotations

from datetime import date
import logging

import streamlit as st

from app.config import load_priority_config
from app.database import SessionLocal, create_tables
from app.repositories import PrioritizationRepository, ProfileRepository
from app.services.decision_service import DecisionService
from app.services.prioritization import PrioritizationService
from app.services.saved_view_service import SavedViewService
from app.services.shortlist_service import ShortlistService
from app.services.validation import ValidationError

LOGGER = logging.getLogger(__name__)


def render_strategic_inbox_page() -> None:
    """Render the strategic prioritization inbox."""

    create_tables()
    st.header("Bandeja estrategica")
    st.caption("La prioridad indica donde conviene invertir tiempo ahora. No representa una garantia de contratacion.")
    tabs = st.tabs(
        [
            "Prioridad de hoy",
            "Postular",
            "Preparar",
            "Revisar",
            "Explorar",
            "Guardadas",
            "Descartadas",
            "Seguimiento",
            "Obsoletas",
            "Historial",
            "Lista diaria",
            "Vistas",
        ]
    )
    with tabs[0]:
        _render_today()
    for tab, action in [
        (tabs[1], "Postular"),
        (tabs[2], "Preparar postulacion"),
        (tabs[3], "Revisar"),
        (tabs[4], "Explorar"),
        (tabs[5], "Guardar"),
        (tabs[6], "Descartar"),
    ]:
        with tab:
            _render_action_view(action)
    with tabs[7]:
        _render_tracking()
    with tabs[8]:
        _render_stale()
    with tabs[9]:
        _render_history()
    with tabs[10]:
        _render_daily_shortlist()
    with tabs[11]:
        _render_saved_views()


def _profile_id(session) -> int | None:
    profile = ProfileRepository(session).get_main_profile()
    if profile is None:
        st.warning("Crea un perfil profesional antes de usar la bandeja estrategica.")
        return None
    return profile.id


def _render_today() -> None:
    with SessionLocal() as session:
        profile_id = _profile_id(session)
        if profile_id is None:
            return
        config = load_priority_config()
        repo = PrioritizationRepository(session)
        col_a, col_b, col_c = st.columns(3)
        if col_a.button("Priorizar activas", use_container_width=True):
            _run_action(lambda: PrioritizationService(session, config).prioritize_all_active(profile_id=profile_id))
        if col_b.button("Marcar obsoletas", use_container_width=True):
            count = 0
            for priority in repo.list_priorities({"profile_id": profile_id, "is_stale": False}, limit=500):
                if PrioritizationService(session, config).mark_stale_for_current_state(priority.job_id, profile_id):
                    count += 1
            st.info(f"Prioridades marcadas como obsoletas: {count}")
        priorities = repo.list_priorities({"profile_id": profile_id, "is_stale": False}, limit=100)
        selected = _daily_mix(priorities, config)
        _render_wip(repo, profile_id, config)
        _priority_table(selected)
        _render_priority_detail(session, repo, profile_id, selected)


def _render_action_view(action: str) -> None:
    with SessionLocal() as session:
        profile_id = _profile_id(session)
        if profile_id is None:
            return
        repo = PrioritizationRepository(session)
        priorities = repo.list_priorities({"profile_id": profile_id, "recommended_action": action, "is_stale": False}, limit=200)
        _priority_table(priorities)
        _render_priority_detail(session, repo, profile_id, priorities)


def _render_tracking() -> None:
    with SessionLocal() as session:
        profile_id = _profile_id(session)
        if profile_id is None:
            return
        repo = PrioritizationRepository(session)
        decisions = repo.list_decisions(profile_id, limit=300)
        rows = [
            {
                "Vacante": item.job.title,
                "Empresa": item.job.company,
                "Decision": item.decision,
                "Motivo": item.reason_code,
                "Seguimiento": item.follow_up_date,
                "Fecha": item.decided_at,
            }
            for item in decisions
            if item.decision in {"Postular", "Preparar postulacion"}
        ]
        st.dataframe(rows, use_container_width=True, hide_index=True)


def _render_stale() -> None:
    with SessionLocal() as session:
        profile_id = _profile_id(session)
        if profile_id is None:
            return
        repo = PrioritizationRepository(session)
        priorities = repo.list_priorities({"profile_id": profile_id, "is_stale": True}, limit=300)
        _priority_table(priorities)
        if st.button("Repriorizar obsoletas", use_container_width=True):
            ids = [priority.job_id for priority in priorities]
            if ids:
                _run_action(lambda: PrioritizationService(session).prioritize_jobs(ids, profile_id))


def _render_history() -> None:
    with SessionLocal() as session:
        profile_id = _profile_id(session)
        if profile_id is None:
            return
        decisions = PrioritizationRepository(session).list_decisions(profile_id, limit=300)
        st.dataframe(
            [
                {
                    "Fecha": item.decided_at,
                    "Vacante": item.job.title,
                    "Empresa": item.job.company,
                    "Decision": item.decision,
                    "Motivo": item.reason_code,
                    "Notas": item.notes,
                }
                for item in decisions
            ],
            use_container_width=True,
            hide_index=True,
        )


def _render_daily_shortlist() -> None:
    with SessionLocal() as session:
        profile_id = _profile_id(session)
        if profile_id is None:
            return
        service = ShortlistService(session)
        repo = PrioritizationRepository(session)
        shortlist = service.create_for_date(profile_id, date.today())
        priorities = repo.list_priorities({"profile_id": profile_id, "is_stale": False}, limit=50)
        if priorities:
            options = {f"{item.job.title} - {item.job.company}": item for item in priorities}
            selected = st.selectbox("Agregar oportunidad", list(options))
            if st.button("Agregar a lista diaria"):
                priority = options[selected]
                _run_action(lambda: service.add_job(shortlist.id, priority.job_id, priority.id, priority.recommended_action))
        items = repo.list_shortlist_items(shortlist.id)
        for item in items:
            cols = st.columns([4, 2, 2, 2])
            cols[0].write(f"{item.position}. {item.job.title} - {item.job.company}")
            cols[1].write(item.planned_action)
            cols[2].write(item.completion_status)
            new_status = cols[3].selectbox("Estado", load_priority_config()["shortlist_item_statuses"], key=f"shortlist_status_{item.id}", index=load_priority_config()["shortlist_item_statuses"].index(item.completion_status))
            if new_status != item.completion_status:
                _run_action(lambda item_id=item.id, status=new_status: service.complete(item_id, status))
        if st.button("Archivar lista del dia"):
            _run_action(lambda: service.archive(shortlist.id))


def _render_saved_views() -> None:
    with SessionLocal() as session:
        profile_id = _profile_id(session)
        if profile_id is None:
            return
        repo = PrioritizationRepository(session)
        service = SavedViewService(session)
        with st.form("saved_view_form"):
            name = st.text_input("Nombre de vista")
            action = st.selectbox("Accion recomendada", ["Todas", *load_priority_config()["actions"]])
            bucket = st.selectbox("Prioridad", ["Todas", *load_priority_config()["priority_buckets"]])
            is_default = st.checkbox("Vista predeterminada")
            submitted = st.form_submit_button("Guardar vista")
            if submitted:
                filters = {
                    "recommended_action": None if action == "Todas" else action,
                    "priority_bucket": None if bucket == "Todas" else bucket,
                }
                _run_action(lambda: service.create(profile_id, name, filters, {"field": "priority_score", "direction": "desc"}, is_default))
        views = repo.list_saved_views(profile_id)
        for view in views:
            cols = st.columns([4, 2, 2, 2])
            cols[0].write(f"{view.name}{' (predeterminada)' if view.is_default else ''}")
            cols[1].code(str(view.filters_json))
            if cols[2].button("Predeterminar", key=f"default_view_{view.id}"):
                _run_action(lambda view_id=view.id: service.set_default(view_id))
            confirm = cols[3].checkbox("Confirmar", key=f"confirm_delete_view_{view.id}")
            if cols[3].button("Eliminar", key=f"delete_view_{view.id}"):
                _run_action(lambda view_id=view.id, confirmed=confirm: service.delete(view_id, confirmed))


def _render_wip(repo: PrioritizationRepository, profile_id: int, config: dict) -> None:
    priorities = repo.list_priorities({"profile_id": profile_id, "is_stale": False}, limit=500)
    prepare = sum(1 for item in priorities if item.recommended_action == "Preparar postulacion")
    review = sum(1 for item in priorities if item.recommended_action == "Revisar")
    ready = sum(1 for item in priorities if item.recommended_action == "Postular")
    cols = st.columns(3)
    cols[0].metric("Preparar", prepare)
    cols[1].metric("Revisar", review)
    cols[2].metric("Listas para postular", ready)
    limits = config["wip_limits"]
    if prepare > limits["prepare_application"] or review > limits["review"] or ready > limits["ready_to_apply"]:
        st.warning("Hay mas trabajo en proceso que el limite sugerido. Conviene cerrar pendientes antes de acumular nuevas vacantes.")
    stalled = repo.find_stalled_priorities(profile_id, config["stale_decisions"])
    if stalled:
        st.warning(f"Vacantes estancadas: {len(stalled)}")
        st.dataframe(
            [
                {
                    "Vacante": item["priority"].job.title,
                    "Estado": item["state"],
                    "Dias": item["age_days"],
                    "Accion sugerida": item["suggested_action"],
                }
                for item in stalled[:10]
            ],
            use_container_width=True,
            hide_index=True,
        )


def _priority_table(priorities) -> None:
    rows = []
    for item in priorities:
        evaluation = item.evaluation
        rows.append(
            {
                "ID": item.id,
                "Cargo": item.job.title,
                "Empresa": item.job.company,
                "Prioridad": float(item.priority_score),
                "Compatibilidad": float(evaluation.total_score) if evaluation else None,
                "Confianza": float(evaluation.confidence_score) if evaluation else None,
                "Urgencia": float(item.urgency_score),
                "Accion": item.recommended_action,
                "Bucket": item.priority_bucket,
                "Estado": item.job.status,
                "Obsoleta": item.is_stale,
            }
        )
    st.dataframe(rows, use_container_width=True, hide_index=True)


def _render_priority_detail(session, repo: PrioritizationRepository, profile_id: int, priorities) -> None:
    if not priorities:
        st.info("No hay prioridades para esta vista.")
        return
    selected_id = st.selectbox("Detalle", [item.id for item in priorities], format_func=lambda value: _priority_label(priorities, value))
    priority = next(item for item in priorities if item.id == selected_id)
    st.subheader(priority.job.title)
    col_a, col_b, col_c, col_d = st.columns(4)
    col_a.metric("Prioridad", f"{float(priority.priority_score):.1f}")
    col_b.metric("Urgencia", f"{float(priority.urgency_score):.1f}")
    col_c.metric("Alineacion", f"{float(priority.strategic_value_score):.1f}")
    col_d.metric("Actionability", f"{float(priority.actionability_score):.1f}")
    if priority.blocking_factors:
        st.error("Bloqueos: " + "; ".join(priority.blocking_factors))
    if priority.warnings:
        st.warning("Advertencias: " + "; ".join(priority.warnings))
    st.write("Razones")
    st.dataframe(priority.reasons, use_container_width=True, hide_index=True)
    _effort_override_form(session, priority, profile_id)
    _decision_form(session, priority, profile_id)


def _decision_form(session, priority, profile_id: int) -> None:
    config = load_priority_config()
    with st.form(f"decision_form_{priority.id}"):
        decision = st.selectbox("Decision humana", config["actions"], index=config["actions"].index(priority.recommended_action) if priority.recommended_action in config["actions"] else 0)
        reason_options = [""] + sorted({reason for group in config["decision_reasons"].values() for reason in group})
        reason = st.selectbox("Motivo", reason_options)
        use_follow_up = st.checkbox("Definir seguimiento")
        follow_up = st.date_input("Fecha de seguimiento", value=date.today()) if use_follow_up else None
        notes = st.text_area("Notas")
        create_application = st.checkbox("Crear seguimiento de postulacion", value=decision in {"Postular", "Preparar postulacion"})
        submitted = st.form_submit_button("Confirmar decision")
        if submitted:
            _run_action(
                lambda: DecisionService(session).record_decision(
                    priority.job_id,
                    profile_id,
                    decision,
                    priority_id=priority.id,
                    reason_code=reason or None,
                    notes=notes,
                    follow_up_date=follow_up,
                    create_application=create_application,
                )
            )


def _effort_override_form(session, priority, profile_id: int) -> None:
    config = load_priority_config()
    current_override = PrioritizationRepository(session).get_effort_override(priority.job_id, profile_id)
    current_level = current_override.effort_level if current_override else "Desconocido"
    with st.form(f"effort_override_{priority.id}"):
        effort_level = st.selectbox(
            "Esfuerzo de postulacion",
            list(config["application_effort"].keys()),
            index=list(config["application_effort"].keys()).index(current_level),
        )
        notes = st.text_input("Nota de esfuerzo", value=current_override.notes if current_override else "")
        submitted = st.form_submit_button("Guardar esfuerzo y marcar obsoleta")
        if submitted:
            _run_action(lambda: PrioritizationService(session, config).set_effort_override(priority.job_id, profile_id, effort_level, notes))


def _priority_label(priorities, value: int) -> str:
    item = next(priority for priority in priorities if priority.id == value)
    return f"{item.job.title} - {float(item.priority_score):.1f}"


def _daily_mix(priorities, config: dict):
    inbox = config["daily_inbox"]
    max_items = int(inbox["max_items"])
    direct = [item for item in priorities if item.recommended_action == "Postular"][: int(inbox["max_direct_applications"])]
    growth = [item for item in priorities if item.recommended_action in {"Explorar", "Preparar postulacion"}][: int(inbox["max_growth_items"])]
    review = [item for item in priorities if item.recommended_action == "Revisar"][: int(inbox["max_review_items"])]
    selected = []
    for group in [direct, growth, review, priorities]:
        for item in group:
            if item.id not in {existing.id for existing in selected}:
                selected.append(item)
            if len(selected) >= max_items:
                return selected
    return selected


def _run_action(callback) -> None:
    try:
        result = callback()
        if result is not None:
            st.success(f"Operacion completada: {result}")
        else:
            st.success("Operacion completada.")
    except ValidationError as exc:
        st.warning(str(exc))
    except Exception as exc:  # pragma: no cover - UI safety net
        LOGGER.exception("Strategic inbox action failed")
        st.error(f"No se pudo completar la operacion: {exc}")

"""Streamlit entry point for Radar Laboral Adaptativo."""

from __future__ import annotations

import streamlit as st

from app.services.dashboard_metrics import get_dashboard_snapshot
from app.ui.compatibility_pages import render_compatibility_page
from app.ui.feedback_learning_pages import render_feedback_learning_page
from app.ui.job_pages import render_jobs_page
from app.ui.profile_pages import render_profile_page
from app.ui.strategic_inbox_pages import render_strategic_inbox_page


def render_dashboard() -> None:
    """Render the minimal first-phase dashboard."""

    st.title("Radar Laboral Adaptativo")

    snapshot = get_dashboard_snapshot()
    status_label = "Conectada" if snapshot.database_available else "No disponible"
    st.info("El sistema se encuentra en su primera fase.")
    st.write(f"Estado de la base de datos: **{status_label}**")

    col_total, col_saved, col_applications = st.columns(3)
    col_total.metric("Vacantes registradas", snapshot.metrics.total_jobs)
    col_saved.metric("Vacantes guardadas", snapshot.metrics.saved_jobs)
    col_applications.metric("Postulaciones", snapshot.metrics.applications)


if __name__ == "__main__":
    st.set_page_config(page_title="Radar Laboral Adaptativo", page_icon="RL", layout="centered")
    page = st.sidebar.radio(
        "Navegacion",
        ["Panel inicial", "Mi perfil profesional", "Vacantes", "Compatibilidad", "Bandeja estrategica", "Aprendizaje"],
    )
    if page == "Mi perfil profesional":
        render_profile_page()
    elif page == "Vacantes":
        render_jobs_page()
    elif page == "Compatibilidad":
        render_compatibility_page()
    elif page == "Bandeja estrategica":
        render_strategic_inbox_page()
    elif page == "Aprendizaje":
        render_feedback_learning_page()
    else:
        render_dashboard()

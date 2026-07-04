"""Streamlit views for Phase 3 job capture and import."""

from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal
import json
import logging

import streamlit as st

from app.config import PROJECT_ROOT, load_job_import_config, load_yaml_file
from app.database import SessionLocal, create_tables
from app.repositories import CSVMappingProfileRepository, ImportBatchRepository, JobRepository, JobSourceRepository, StagingJobRepository
from app.services.csv_mapping import CSVMappingService, SKIP_FIELD, SKIP_LABEL
from app.services.job_import import JobImportService
from app.services.job_quality import JobQualityService
from app.services.job_source_capture import JobSourceCaptureService
from app.services.source_security import redact_sensitive_config, validate_non_sensitive_config
from app.services.validation import ValidationError

LOGGER = logging.getLogger(__name__)


def render_jobs_page() -> None:
    """Render the job vacancy module."""

    create_tables()
    st.header("Vacantes")
    st.caption("Registro, importacion, limpieza y revision local de oportunidades laborales.")
    tabs = st.tabs(
        [
            "Nueva vacante",
            "Repositorio",
            "Importar CSV",
            "Fuentes",
            "Captura rapida",
            "EML",
            "Revisar importacion",
            "Historial de importaciones",
            "Calidad de datos",
        ]
    )
    with tabs[0]:
        _render_manual_job_form()
    with tabs[1]:
        _render_repository()
    with tabs[2]:
        _render_csv_import()
    with tabs[3]:
        _render_sources()
    with tabs[4]:
        _render_quick_capture()
    with tabs[5]:
        _render_eml_capture()
    with tabs[6]:
        _render_import_review()
    with tabs[7]:
        _render_import_history()
    with tabs[8]:
        _render_quality_view()


def _render_manual_job_form() -> None:
    config = load_job_import_config()
    st.subheader("Nueva vacante")
    with st.form("manual_job_form"):
        title = st.text_input("Cargo")
        company = st.text_input("Empresa")
        source = st.text_input("Fuente")
        description = st.text_area("Descripcion")
        city = st.text_input("Ciudad")
        province = st.text_input("Provincia")
        modality = st.selectbox("Modalidad", config["modalities"])
        employment_type = st.selectbox("Tipo de empleo", config["employment_types"])
        publication_date = st.date_input("Fecha de publicacion", value=None)
        expiration_date = st.date_input("Fecha de vencimiento", value=None)
        source_url = st.text_input("URL")
        salary_min = st.number_input("Salario minimo", min_value=0.0, value=0.0, step=50.0)
        salary_max = st.number_input("Salario maximo", min_value=0.0, value=0.0, step=50.0)
        currency = st.selectbox("Moneda", config["currencies"])
        salary_period = st.selectbox("Periodo salarial", config["salary_periods"])
        responsibilities = st.text_area("Responsabilidades")
        requirements = st.text_area("Requisitos")
        education_required = st.text_area("Educacion requerida")
        experience_min_years = st.number_input("Experiencia minima", min_value=0.0, value=0.0, step=0.5)
        sector = st.text_input("Sector")
        benefits = st.text_area("Beneficios")
        notes = st.text_area("Notas")
        confirm_duplicate = st.checkbox("Confirmo guardar aunque exista posible duplicado")
        submitted = st.form_submit_button("Guardar vacante")
    if submitted:
        payload = {
            "title": title,
            "company": company,
            "source": source,
            "description": description,
            "city": city or None,
            "province": province or None,
            "modality": modality,
            "employment_type": employment_type,
            "publication_date": publication_date,
            "expiration_date": expiration_date,
            "source_url": source_url or None,
            "salary_min": Decimal(str(salary_min)) if salary_min else None,
            "salary_max": Decimal(str(salary_max)) if salary_max else None,
            "currency": currency,
            "salary_period": salary_period,
            "responsibilities": responsibilities or None,
            "requirements": requirements or None,
            "education_required": education_required or None,
            "experience_min_years": Decimal(str(experience_min_years)) if experience_min_years else None,
            "sector": sector or None,
            "benefits": benefits or None,
            "notes": notes or None,
        }
        with SessionLocal() as session:
            _save_action(lambda: JobRepository(session).create_job(payload, confirm_duplicate))


def _render_repository() -> None:
    config = load_job_import_config()
    st.subheader("Repositorio laboral")
    st.caption("Una coincidencia alta no siempre significa que sea la misma vacante. Revise empresa, fecha, ubicacion y descripcion antes de decidir.")
    text = st.text_input("Texto libre")
    col_a, col_b, col_c = st.columns(3)
    with col_a:
        status = st.selectbox("Estado", [""] + config["job_statuses"])
    with col_b:
        quality = st.selectbox("Calidad", [""] + config["data_quality_statuses"])
    with col_c:
        suspicious = st.selectbox("Sospechosa", ["Todas", "Si", "No"])
    filters = {"text": text or None}
    if status:
        filters["status"] = status
    if quality:
        filters["data_quality_status"] = quality
    if suspicious != "Todas":
        filters["is_suspicious"] = suspicious == "Si"
    with SessionLocal() as session:
        repo = JobRepository(session)
        jobs = repo.list_jobs(filters, limit=100)
        rows = [
            {
                "ID": job.id,
                "Cargo": job.title,
                "Empresa": job.company,
                "Ubicacion": ", ".join(part for part in [job.city, job.province] if part),
                "Modalidad": job.modality,
                "Fuente": job.source,
                "Fecha": job.publication_date,
                "Salario": _salary(job),
                "Calidad": job.data_quality_status,
                "Estado": job.status,
                "Duplicado": job.is_duplicate,
                "Riesgo": job.suspicious_reason or "",
            }
            for job in jobs
        ]
        st.dataframe(rows, use_container_width=True)
        export_bytes = JobImportService(session).export_jobs_csv(jobs)
        st.download_button(
            "Exportar visibles a CSV",
            export_bytes,
            file_name=f"vacantes_exportadas_{datetime.now().strftime('%Y%m%d_%H%M')}.csv",
            mime="text/csv",
        )
        selected_id = st.number_input("ID de vacante para detalle", min_value=0, value=0, step=1)
        if selected_id:
            job = repo.get_job(int(selected_id))
            if job:
                with st.expander(f"Detalle: {job.title} - {job.company}", expanded=True):
                    st.write(job.description)
                    st.write(f"Normalizado: {job.normalized_title} | {job.normalized_company}")
                    st.write(f"Calidad: {job.data_quality_status} | Revision: {job.review_status}")
                    st.write(f"Fuente: {job.source_url or job.source}")
                    new_status = st.selectbox("Cambiar estado", config["job_statuses"], key=f"status_{job.id}")
                    if st.button("Guardar estado", key=f"save_status_{job.id}"):
                        _save_action(lambda: repo.change_status(job.id, new_status, "Cambio desde repositorio"))
                    if st.button("Eliminar logicamente", key=f"delete_job_{job.id}"):
                        _save_action(lambda: repo.logical_delete(job.id, "Eliminacion desde UI"))


def _render_csv_import() -> None:
    st.subheader("Importar CSV")
    st.caption("No se guarda automaticamente: primero se crea un area temporal de revision.")
    with SessionLocal() as session:
        service = JobImportService(session)
        mapping_service = CSVMappingService()
        profile_repo = CSVMappingProfileRepository(session)
        st.download_button("Descargar plantilla CSV", service.template_csv(), "plantilla_importacion_vacantes.csv", "text/csv")
        profiles = profile_repo.list_profiles()
        profile_options = {"Sin perfil guardado": None} | {profile.source_name: profile.id for profile in profiles}
        selected_profile_label = st.selectbox("Perfil de mapeo", list(profile_options.keys()))
        selected_profile_id = profile_options[selected_profile_label]
        selected_profile = profile_repo.get_profile(selected_profile_id) if selected_profile_id else None
        if selected_profile:
            st.caption(f"Perfil aplicado: {selected_profile.source_name}")
            delete_confirm = st.checkbox("Confirmo eliminar este perfil de mapeo")
            if st.button("Eliminar perfil de mapeo"):
                if delete_confirm:
                    _save_action(lambda: profile_repo.delete_profile(selected_profile.id))
                else:
                    st.warning("Marca la confirmacion antes de eliminar el perfil.")
        uploaded = st.file_uploader("Archivo CSV", type=["csv"])
        if uploaded is not None:
            content = uploaded.getvalue()
            try:
                dataframe = service.read_csv_bytes(content, uploaded.name)
                initial_mapping = selected_profile.mapping if selected_profile else service.infer_column_mapping(list(dataframe.columns))
                suggestions = mapping_service.build_suggestions(dataframe, selected_mapping=initial_mapping)
                field_options = [SKIP_LABEL, *mapping_service.target_fields]
                editor_rows = [
                    {
                        "Columna original": item.original_column,
                        "Campo inferido": item.inferred_field or "",
                        "Confianza": item.confidence,
                        "Campo destino": SKIP_LABEL if item.selected_field == SKIP_FIELD else item.selected_field,
                        "Vista previa": " | ".join(item.preview_values),
                    }
                    for item in suggestions
                ]
                edited_rows = st.data_editor(
                    editor_rows,
                    use_container_width=True,
                    hide_index=True,
                    disabled=["Columna original", "Campo inferido", "Confianza", "Vista previa"],
                    column_config={
                        "Campo destino": st.column_config.SelectboxColumn(
                            "Campo destino",
                            options=field_options,
                            required=True,
                        ),
                        "Confianza": st.column_config.NumberColumn("Confianza", min_value=0.0, max_value=1.0, format="%.2f"),
                    },
                )
                edited_records = (
                    edited_rows.to_dict("records")
                    if hasattr(edited_rows, "to_dict")
                    else edited_rows
                )
                selected_mapping = {
                    str(row["Columna original"]): str(row["Campo destino"])
                    for row in edited_records
                }
                clean_mapping = mapping_service.clean_mapping(selected_mapping)
                validation = mapping_service.validate_mapping(clean_mapping)
                if validation.missing_required_fields:
                    st.warning("Campos obligatorios faltantes: " + ", ".join(validation.missing_required_fields))
                if validation.duplicate_fields:
                    duplicated = [
                        f"{field}: {', '.join(columns)}"
                        for field, columns in validation.duplicate_fields.items()
                    ]
                    st.warning("Asignaciones duplicadas incompatibles: " + " | ".join(duplicated))
                st.dataframe(dataframe.head(load_job_import_config()["import_limits"]["preview_rows"]), use_container_width=True)
                profile_source_name = st.text_input("Nombre de fuente para guardar perfil", value=selected_profile.source_name if selected_profile else "")
                if st.button("Guardar perfil de mapeo"):
                    if validation.is_valid:
                        _save_action(lambda: profile_repo.save_profile(profile_source_name, clean_mapping))
                    else:
                        st.warning("Corrige el mapeo antes de guardar el perfil.")
                if st.button("Crear lote de revision", disabled=not validation.is_valid):
                    batch_id = service.stage_csv(content, uploaded.name, source_name=profile_source_name or None, mapping=clean_mapping)
                    st.success(f"Lote creado: {batch_id}. Revisa las filas antes de importar.")
            except ValidationError as exc:
                st.error(str(exc))
            except Exception:
                LOGGER.exception("CSV import UI error")
                st.error("No se pudo leer el archivo. Revisa el formato CSV.")


def _render_sources() -> None:
    st.subheader("Fuentes autorizadas")
    st.caption("Busca nuevas ofertas solo cuando pulses el boton. No hay programacion periodica en esta fase.")
    source_config = load_yaml_file(PROJECT_ROOT / "config" / "job_sources.yaml")
    source_types = [value for value in source_config["source_types"] if value not in {"CSV", "QUICK_LINK", "EML_FILE"}]
    with SessionLocal() as session:
        repo = JobSourceRepository(session)
        service = JobSourceCaptureService(session)
        with st.form("job_source_create_form"):
            name = st.text_input("Nombre de fuente")
            source_type = st.selectbox("Tipo", source_types)
            configuration_text = st.text_area(
                "Configuracion JSON sin credenciales",
                value=_default_source_configuration(source_type),
                height=160,
            )
            is_active = st.checkbox("Activa", value=True)
            submitted = st.form_submit_button("Guardar fuente")
        if submitted:
            _save_action(lambda: repo.create_source(name=name, source_type=source_type, configuration=_parse_json_config(configuration_text), is_active=is_active))

        sources = repo.list_sources()
        if not sources:
            st.info("Aun no hay fuentes configuradas.")
        for source in sources:
            with st.expander(f"{source.name} | {source.source_type} | {'Activa' if source.is_active else 'Inactiva'}"):
                st.json(_redact_sensitive(source.configuration))
                if source.last_test_status:
                    st.write(f"Ultima prueba: {source.last_test_status}")
                col_a, col_b, col_c = st.columns(3)
                with col_a:
                    if st.button("Probar conexion", key=f"test_source_{source.id}"):
                        result = service.test_source(source.id)
                        if result.ok:
                            st.success(result.message)
                        else:
                            st.warning(result.message)
                with col_b:
                    if st.button("Buscar nuevas ofertas", key=f"capture_source_{source.id}", disabled=not source.is_active):
                        _save_action(lambda source_id=source.id: f"Lote creado: {service.capture_source(source_id)}")
                with col_c:
                    if st.button("Desactivar" if source.is_active else "Activar", key=f"toggle_source_{source.id}"):
                        _save_action(lambda source_id=source.id, active=not source.is_active: repo.set_active(source_id, active))

        runs = repo.list_runs(limit=20)
        if runs:
            st.subheader("Ultimas capturas")
            st.dataframe(
                [
                    {
                        "Fuente": run.source.name if run.source else run.source_type,
                        "Estado": run.status,
                        "Encontradas": run.records_found,
                        "A staging": run.records_staged,
                        "Omitidas": run.records_skipped,
                        "Errores": run.errors_count,
                        "Lote": run.import_batch_id or "",
                    }
                    for run in runs
                ],
                use_container_width=True,
            )


def _render_quick_capture() -> None:
    st.subheader("Captura rapida por enlace")
    st.caption("Guarda el enlace en staging para completar y revisar. No se visita ni raspa la pagina.")
    with st.form("quick_link_capture_form"):
        url = st.text_input("URL de la oferta")
        title = st.text_input("Cargo opcional")
        company = st.text_input("Empresa opcional")
        city = st.text_input("Ciudad opcional")
        notes = st.text_area("Notas")
        submitted = st.form_submit_button("Enviar a revision")
    if submitted:
        with SessionLocal() as session:
            service = JobSourceCaptureService(session)
            _save_action(lambda: f"Lote creado: {service.capture_quick_link(url=url, title=title, company=company, city=city, notes=notes)}")


def _render_eml_capture() -> None:
    st.subheader("Importar correo guardado (.eml)")
    st.caption("Lee un correo exportado como archivo. No conecta a tu correo, no elimina mensajes y no sigue enlaces.")
    source_name = st.text_input("Nombre de fuente", value="EML manual")
    uploaded = st.file_uploader("Archivo EML", type=["eml"])
    if st.button("Crear lote desde EML", disabled=uploaded is None):
        if uploaded is None:
            st.warning("Carga un archivo EML primero.")
            return
        with SessionLocal() as session:
            service = JobSourceCaptureService(session)
            _save_action(lambda: f"Lote creado: {service.capture_uploaded_eml(filename=uploaded.name, content=uploaded.getvalue(), source_name=source_name or 'EML manual')}")


def _render_import_review() -> None:
    st.subheader("Revisar importacion")
    with SessionLocal() as session:
        batch_repo = ImportBatchRepository(session)
        staging_repo = StagingJobRepository(session)
        service = JobImportService(session)
        batches = batch_repo.list_batches()
        if not batches:
            st.info("No hay lotes de importacion.")
            return
        batch_options = {f"{batch.id} - {batch.filename or batch.source_type} - {batch.status}": batch.id for batch in batches}
        selected = st.selectbox("Lote", list(batch_options.keys()))
        batch_id = batch_options[selected]
        rows = staging_repo.list_by_batch(batch_id)
        st.write(f"Filas: {len(rows)}")
        if st.button("Accion masiva recomendada"):
            _save_action(lambda: service.apply_bulk_decisions(batch_id))
        for row in rows[:100]:
            with st.expander(f"Fila {row.row_number} | {row.validation_status} | {row.duplicate_status}"):
                st.json(row.parsed_data or row.raw_data)
                if row.validation_errors:
                    st.error("; ".join(row.validation_errors))
                if row.validation_warnings:
                    st.warning("; ".join(row.validation_warnings))
                decision = st.selectbox(
                    "Decision",
                    load_job_import_config()["user_decisions"],
                    key=f"decision_{row.id}",
                    index=0,
                )
                if st.button("Guardar decision", key=f"decision_btn_{row.id}"):
                    _save_action(lambda row_id=row.id, value=decision: staging_repo.register_decision(row_id, value))
        confirm = st.checkbox("Confirmo guardar las filas seleccionadas")
        if st.button("Procesar decisiones"):
            _save_action(lambda: service.process_decisions(batch_id, confirmed=confirm))


def _render_import_history() -> None:
    st.subheader("Historial de importaciones")
    with SessionLocal() as session:
        batches = ImportBatchRepository(session).list_batches()
        st.dataframe(
            [
                {
                    "ID": batch.id,
                    "Archivo": batch.filename,
                    "Estado": batch.status,
                    "Total": batch.total_rows,
                    "Validas": batch.valid_rows,
                    "Invalidas": batch.invalid_rows,
                    "Duplicadas": batch.duplicate_rows,
                    "Insertadas": batch.inserted_rows,
                    "Omitidas": batch.skipped_rows,
                }
                for batch in batches
            ],
            use_container_width=True,
        )


def _render_quality_view() -> None:
    st.subheader("Calidad de datos")
    st.caption("Las vacantes marcadas como sospechosas no se eliminan automaticamente. La decision final pertenece al usuario.")
    with SessionLocal() as session:
        jobs = JobRepository(session).list_jobs({}, limit=200)
        quality_service = JobQualityService()
        rows = []
        for job in jobs:
            result = quality_service.evaluate({column.name: getattr(job, column.name) for column in job.__table__.columns})
            rows.append(
                {
                    "ID": job.id,
                    "Cargo": job.title,
                    "Calidad": result.status,
                    "Faltantes": ", ".join(result.missing_fields),
                    "Recomendaciones": "; ".join(result.recommendations),
                    "Sospechosa": job.is_suspicious,
                }
            )
        st.dataframe(rows, use_container_width=True)


def _save_action(action) -> None:
    try:
        result = action()
    except ValidationError as exc:
        st.error(str(exc))
    except Exception:
        LOGGER.exception("Unexpected jobs UI error")
        st.error("No se pudo completar la accion. Revisa los datos e intenta nuevamente.")
    else:
        st.success("Accion completada correctamente.")
        if result is not None:
            st.write(result)


def _salary(job) -> str:
    values = [value for value in [job.salary_min, job.salary_max] if value is not None]
    if not values:
        return ""
    return f"{' - '.join(str(value) for value in values)} {job.currency}"


def _parse_json_config(raw: str) -> dict:
    try:
        data = json.loads(raw or "{}")
    except json.JSONDecodeError as exc:
        raise ValidationError("La configuracion debe ser JSON valido.") from exc
    if not isinstance(data, dict):
        raise ValidationError("La configuracion debe ser un objeto JSON.")
    validate_non_sensitive_config(data)
    return data


def _redact_sensitive(data: dict) -> dict:
    return redact_sensitive_config(data or {})


def _default_source_configuration(source_type: str) -> str:
    defaults = {
        "LOCAL_FOLDER": {"folder_path": "data/imports", "allow_reprocess": False},
        "AUTHORIZED_EMAIL": {"enabled": False, "env_prefix": "RADAR_EMAIL", "max_messages": 10},
        "RSS_ATOM": {"url": "https://example.com/feed.xml"},
        "PUBLIC_JSON_API": {
            "base_url": "https://example.com/jobs.json",
            "params": {},
            "headers": {},
            "items_path": "items",
            "field_mapping": {
                "title": "title",
                "company": "company",
                "description": "description",
                "url": "source_url",
                "id": "external_id",
            },
        },
    }
    return json.dumps(defaults.get(source_type, {}), indent=2, ensure_ascii=False)

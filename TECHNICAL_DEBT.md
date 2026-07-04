# Deuda Tecnica

## Media

- `app/database.py` mantiene `ensure_phase3_job_columns`, helper legado que puede modificar SQLite fuera de Alembic. Debe retirarse en una estabilizacion futura.
- UI de perfil y vacantes abre sesiones directamente, aunque delega reglas a repositorios/servicios. Mantener vigilancia para no mover logica de negocio a Streamlit.
- Los borradores de CV de Fase 2.1 viven en `st.session_state`; si se requiere trazabilidad, crear tablas con Alembic.

## Baja

- Git no esta disponible en la terminal actual.
- Algunas skills locales no tienen metadata completa para agentes secundarios.

## Fase 7

- El conector de correo autorizado queda desactivado por defecto hasta que existan credenciales y una decision explicita de habilitarlo.
- Las pruebas de conectores remotos deben usar respuestas simuladas; no depender de internet real.
- La validacion de carpeta local registra hash en metadata JSON existente. Si se necesita auditoria avanzada por archivo, crear una tabla especifica en una fase futura mediante Alembic.

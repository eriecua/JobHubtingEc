# Radar Laboral Adaptativo — instrucciones permanentes para Codex

## Objetivo
Aplicación local para capturar, normalizar, analizar, priorizar y dar seguimiento a oportunidades laborales. La interfaz debe ser sencilla aunque la arquitectura interna sea rigurosa.

## Arquitectura esperada
- Python y Streamlit.
- SQLAlchemy y SQLite.
- Alembic para migraciones.
- YAML para configuración.
- Pytest para pruebas.
- Lógica de negocio fuera de Streamlit.

Antes de modificar código, inspecciona la estructura real. No inventes módulos ni nombres sin comprobarlos.

## Reglas obligatorias
1. No reconstruyas el proyecto desde cero.
2. No elimines ni recrees la base local.
3. No modifiques tablas directamente: usa Alembic.
4. No declares una función terminada sin ejecutar pruebas.
5. No continúes a otra fase con errores críticos.
6. No introduzcas aprendizaje opaco ni cambios automáticos de preferencias.
7. No realices postulaciones externas automáticamente.
8. No almacenes contraseñas, tokens ni credenciales.
9. No uses rutas absolutas dependientes de una computadora.
10. Mantén compatibilidad con Windows y PowerShell.
11. Conserva el comportamiento existente salvo que el cambio lo requiera.
12. Usa bases temporales en pruebas.
13. Documenta migraciones irreversibles.
14. Evita consultas N+1 y reglas de negocio dentro de Streamlit.

## Streamlit
- Toda clave de `st.form`, `st.button`, `st.selectbox`, `st.data_editor` y widgets repetidos debe ser estable y única.
- Incluye contexto de vista e identificadores de entidad en las claves.
- No uses UUID aleatorios para esconder claves duplicadas.
- No renderices dos veces el mismo componente para la misma entidad y vista.
- Interfaz principal: Inicio, Ofertas, Postulaciones y Mi perfil.
- Mueve funciones técnicas a Configuración avanzada.

## Comandos base
```powershell
.\.venv\Scripts\Activate.ps1
python -m pytest
python -m alembic current
python -m alembic upgrade head
python -m streamlit run app\main.py
```

Si PowerShell bloquea la activación:
```powershell
Set-ExecutionPolicy -Scope Process -ExecutionPolicy Bypass
.\.venv\Scripts\Activate.ps1
```

## Flujo obligatorio
1. Inspección.
2. Diagnóstico.
3. Plan breve.
4. Cambio mínimo.
5. Pruebas focalizadas.
6. Pruebas completas.
7. Verificación de migraciones.
8. Verificación de Streamlit.
9. Resumen de archivos modificados.
10. Riesgos pendientes.

## Entrega
Informa problema, decisión técnica, archivos, pruebas, comandos y riesgos. No ocultes fallos.

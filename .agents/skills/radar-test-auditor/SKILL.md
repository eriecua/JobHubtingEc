---
name: radar-test-auditor
description: Diagnostica fallos, ejecuta pruebas y audita regresiones del Radar Laboral. Úsala ante errores, excepciones, pruebas fallidas, fases aparentemente terminadas o antes de declarar una entrega.
---

# Radar Test Auditor

## Procedimiento
1. Reproduce el mensaje exacto e identifica archivo, línea y flujo.
2. Clasifica: Streamlit, sesión, clave duplicada, base, migración, validación, importación, compatibilidad, priorización, seguimiento, configuración o entorno.
3. Formula pocas hipótesis ordenadas por probabilidad y compruébalas.
4. Aplica el cambio mínimo y añade una prueba de regresión.
5. No ocultes errores con `try/except` genérico.
6. Ejecuta:
```powershell
python -m pytest -x
python -m pytest
python -m alembic current
```
7. Para errores Streamlit, verifica rerun, dos entidades, dos vistas y claves únicas/estables.

## Formato de resultado
Error reproducido, causa raíz, evidencia, corrección, prueba añadida, resultado focalizado, resultado total y riesgo residual.

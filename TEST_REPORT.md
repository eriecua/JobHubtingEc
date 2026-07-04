# Test Report

## Baseline Antes De Fase 7

Comandos ejecutados el 2026-07-03:

```powershell
python -m alembic current
python -m alembic heads
python -m alembic history
python -m pytest
```

Resultados:

- Alembic current: `202607020006 (head)`.
- Alembic heads: `202607020006 (head)`.
- Pytest: `65 passed in 97.71s`.

## Pendiente

- Sin pendientes criticos de Fase 7.

## Fase 7

Comandos ejecutados:

```powershell
python -m pytest tests\test_phase7_job_sources.py -q
$env:RADAR_DATABASE_URL = "sqlite:///data/temp/phase7_alembic_test.db"
python -m alembic upgrade head
python -m alembic current
python -m alembic downgrade 202607020006
python -m alembic upgrade head
Remove-Item Env:\RADAR_DATABASE_URL
python -m alembic upgrade head
python -m alembic current
```

Resultados:

- Pruebas Fase 7: `6 passed`.
- Migracion temporal: upgrade, current, downgrade a `202607020006` y upgrade a head correctos.
- Base local: actualizada a `202607030001 (head)` tras respaldo.
- Suite completa: `71 passed in 99.34s`.
- Alembic current final: `202607030001 (head)`.
- Imports principales: `imports-ok`.
- Streamlit: inicio correcto en `http://localhost:8507` y se detuvo despues.

## Ajuste Fase 7 - 2026-07-04

Comandos ejecutados antes de cambios:

```powershell
python -m alembic current
python -m alembic heads
python -m alembic history
python -m pytest -x
```

Resultados baseline:

- Alembic current: `202607030001 (head)`.
- Alembic heads: `202607030001 (head)`.
- Pytest inicial: `71 passed in 85.14s`.
- Respaldo local: `data\radar_laboral.backup.phase7_plan_update.20260704075458.db`.

Pruebas focalizadas tras cambios:

```powershell
python -m pytest tests\test_phase7_job_sources.py -q
```

Resultado:

- Pruebas Fase 7: `12 passed in 8.40s`.

Verificacion final:

```powershell
python -m pytest -x
python -m pytest
$env:RADAR_DATABASE_URL = "sqlite:///data/temp/phase7_plan_update_alembic.db"
python -m alembic upgrade head
python -m alembic current
python -m alembic downgrade 202607020006
python -m alembic upgrade head
python -m alembic current
Remove-Item Env:\RADAR_DATABASE_URL
python -m alembic current
python -c "import app.main; from app.ui.job_pages import render_jobs_page; from app.services.job_source_capture import JobSourceCaptureService; from app.services.job_source_connectors import connector_for, quick_link_record; from app.repositories.job_source_repository import JobSourceRepository; from app.models import JobSource, JobSourceCaptureRun, CapturedSourceItem; print('imports-ok')"
python -m streamlit run app\main.py --server.headless true --server.port 8518
```

Resultados finales:

- `python -m pytest -x`: `77 passed in 83.93s`.
- `python -m pytest`: `77 passed in 83.46s`.
- Alembic temporal: upgrade, current, downgrade Fase 7 y upgrade a head correctos.
- Alembic current final: `202607030001 (head)`.
- Imports principales: `imports-ok`.
- Streamlit: inicio correcto en `http://localhost:8518` y se detuvo despues.

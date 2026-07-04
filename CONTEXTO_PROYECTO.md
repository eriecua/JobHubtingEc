# CONTEXTO DE CONTINUIDAD - Radar Laboral Adaptativo

Fecha de actualizacion: 2026-07-03  
Repositorio local: `C:\Users\MSI ERICK\Desktop\radar_laboral`  
Python verificado: 3.14.6  
Estado de pruebas mas reciente: `59 passed in 91.87s`  
Alembic actual: `202607020006 (head)`

## 1. Objetivo general del proyecto

Radar Laboral Adaptativo es una aplicacion local para capturar, estructurar, analizar, priorizar y dar seguimiento a oportunidades laborales en Ecuador.

El usuario inicial es un estudiante avanzado de Ingenieria Industrial con experiencia en produccion, operaciones, mejora continua, Lean Manufacturing, Six Sigma Yellow Belt, indicadores, inventarios, bodega, procesos, Excel, Dynamics 365 y proyectos de ahorro cuantificado.

El resultado final esperado es un sistema local que ayude a buscar empleo de forma ordenada y explicable:

- Registrar vacantes desde fuentes permitidas.
- Normalizar informacion.
- Eliminar duplicados.
- Comparar vacantes contra el perfil profesional.
- Calcular compatibilidad explicable.
- Priorizar oportunidades.
- Registrar decisiones, postulaciones y resultados.
- Aprender de forma controlada, con revision humana.
- Medir efectividad de la busqueda laboral.

Restriccion central: el sistema no debe postular automaticamente, no debe enviar CV ni mensajes sin aprobacion humana, no debe hacer scraping de LinkedIn ni evadir restricciones de plataformas.

## 2. Estado actual

El proyecto esta despues de Fase 6.1 y antes de implementar Fase 2.1 de carga asistida desde CV.

Porcentaje aproximado de completitud respecto a la vision total: 65 por ciento.

### Funcionalidades terminadas y verificadas

- Estructura base local con Streamlit, SQLAlchemy, SQLite, Pydantic, YAML, Alembic y Pytest.
- Configuracion general y lectura de `.env`.
- Dashboard inicial con contadores en cero cuando no hay datos.
- Perfil profesional estructurado.
- Experiencias, habilidades, evidencias, herramientas, formacion, certificaciones, cargos objetivo, sectores, preferencias, restricciones y crecimiento.
- Seed inicial de perfil idempotente.
- Registro manual de vacantes.
- Importacion CSV con staging, mapeo visual, perfiles reutilizables y confirmacion humana.
- Normalizacion inicial de vacantes.
- Deteccion local de duplicados.
- Calidad de datos y alertas de vacantes sospechosas.
- Historial de estados, etiquetas y exportacion CSV.
- Alembic formal desde Fase 3.1 hasta Fase 6.1.
- Motor deterministico de compatibilidad de Fase 4.
- Extraccion local de requisitos por reglas y alias.
- Fortalezas, brechas, datos faltantes, confianza y cobertura.
- Priorizacion estrategica de Fase 5.
- Decisiones humanas, lista diaria, vistas guardadas y seguimiento local de postulaciones.
- Retroalimentacion y aprendizaje controlado de Fase 6.
- Estabilizacion 6.1: postulaciones asociadas al perfil, propuestas con vencimiento, deduplicacion de senales y metricas corregidas.
- Skill local `radar-cv-ingestion` creada para guiar la futura Fase 2.1.
- Documento de diseno de Fase 2.1 creado en `docs/phase_2_1_cv_ingestion_design.md`.

Evidencia actual:

```powershell
python -m pytest
# 59 passed in 91.87s

python -m alembic current
# 202607020006 (head)

python -m alembic heads
# 202607020006 (head)
```

### Funcionalidades implementadas pero no verificadas completamente

- Inicio real de Streamlit en navegador no fue repetido durante esta tarea. Si fue verificado antes, no hay evidencia nueva en esta ejecucion. Si se requiere cierre de release, ejecutar `python -m streamlit run app\main.py`.
- Flujos manuales completos de UI no fueron recorridos visualmente durante esta tarea. Hay pruebas automatizadas e imports correctos, pero no captura de pantalla ni prueba manual en navegador.
- La deduplicacion manual de empresas introducidas por el usuario no pudo verificarse como operacion historica porque no se inspecciono el contenido funcional de la base real.

### Funcionalidades en desarrollo

- Fase 2.1 esta disenada, no implementada: carga asistida de perfil desde CV con borradores revisables.
- Skill `radar-cv-ingestion` existe como guia operativa, no como funcionalidad de la app.

### Funcionalidades pendientes

- Lectura local de CV `.txt`, `.pdf` con texto seleccionable y `.docx`.
- Extractor deterministico de secciones del CV.
- Borrador revisable de perfil con fuente, confianza y estado por candidato.
- UI de revision del CV.
- Aplicacion supervisada de candidatos al perfil usando repositorios.
- Persistencia opcional de borradores de importacion de perfil con Alembic.
- OCR para CVs escaneados, en una fase posterior.
- Lectura automatica de correos, si se solicita en una fase futura.
- Automatizacion programada y reportes periodicos completos.
- Benchmarks formales de volumen.

## 3. Arquitectura del proyecto

Arquitectura local por capas:

- Streamlit para UI.
- Repositorios para acceso a datos.
- Servicios para reglas de negocio.
- SQLAlchemy como ORM.
- SQLite como base local.
- Alembic para migraciones.
- YAML para configuracion.
- Pytest para verificacion.

### Arbol simplificado

```text
radar_laboral/
  app/
    main.py
    config.py
    database.py
    models/database_models.py
    repositories/
    services/
    ui/
    utils/
  alembic/
    env.py
    versions/
  config/
    profile.yaml
    profile_catalogs.yaml
    profile_completeness.yaml
    scoring_weights.yaml
    job_import.yaml
    compatibility_scoring.yaml
    priority_strategy.yaml
    feedback_learning.yaml
  data/
    radar_laboral.db
    radar_laboral.backup.*.db
    imports/
    exports/
    temp/
  docs/
    post_phase_6_1_audit.md
    phase_2_1_cv_ingestion_design.md
  examples/
  scripts/
    initialize_database.py
    seed_initial_profile.py
  tests/
  .agents/skills/
  README.md
  AGENTS.md
  requirements.txt
  run.bat
  CONTEXTO_PROYECTO.md
```

### Archivos principales

- `app/main.py`: entrada Streamlit. Define navegacion principal: Panel inicial, Mi perfil profesional, Vacantes, Compatibilidad, Bandeja estrategica y Aprendizaje.
- `app/config.py`: carga `.env`, rutas, YAML y valida configuraciones con Pydantic.
- `app/database.py`: engine, sesiones y helpers de base. Contiene deuda tecnica: `ensure_phase3_job_columns`.
- `app/models/database_models.py`: modelos SQLAlchemy de todas las fases.
- `app/repositories/*.py`: CRUD, consultas y persistencia por dominio.
- `app/services/*.py`: reglas de negocio, normalizacion, scoring, priorizacion, aprendizaje y validaciones.
- `app/ui/*.py`: pantallas Streamlit.
- `alembic/env.py`: usa metadata real de SQLAlchemy y URL desde configuracion.
- `alembic/versions/*.py`: migraciones versionadas.
- `config/*.yaml`: pesos, catalogos, alias y reglas.
- `tests/*.py`: pruebas automatizadas con bases temporales.
- `.agents/skills/*/SKILL.md`: skills locales para continuidad del proyecto.

### Flujo de datos

1. Usuario interactua con Streamlit.
2. UI abre una sesion con `SessionLocal`.
3. UI llama repositorios y servicios.
4. Servicios aplican reglas deterministicas y configuracion YAML.
5. Repositorios leen o escriben modelos SQLAlchemy.
6. SQLite persiste en `data/radar_laboral.db`.
7. Alembic gestiona cambios de esquema.
8. Tests usan bases temporales o `sqlite:///:memory:`.

### Navegacion entre paginas

En `app/main.py`:

- `Panel inicial`: dashboard minimo con estado de base y contadores.
- `Mi perfil profesional`: perfil, experiencias, habilidades, evidencias, herramientas, formacion, certificaciones, cargos, sectores, preferencias, restricciones y crecimiento.
- `Vacantes`: registro manual, repositorio, importacion CSV, staging, historial y calidad.
- `Compatibilidad`: requisitos, evaluaciones, resultados y detalle.
- `Bandeja estrategica`: prioridad diaria, acciones, seguimiento, obsoletas, historial, lista diaria y vistas.
- `Aprendizaje`: senales, resultados, analisis, propuestas e historial.

### Base de datos y almacenamiento

- Base real por defecto: `data/radar_laboral.db`.
- Respaldos detectados:
  - `data/radar_laboral.backup.phase4.db`
  - `data/radar_laboral.backup.phase5.20260702143914.db`
  - `data/radar_laboral.backup.phase5audit.20260702173150.db`
  - `data/radar_laboral.backup.phase6.20260703001007.db`
  - `data/radar_laboral.backup.dedup.20260703001939.db`
  - `data/radar_laboral.backup.phase6_1.20260703171535.db`
- Carpetas reservadas:
  - `data/imports`
  - `data/exports`
  - `data/temp`

### Servicios externos utilizados

Ninguno en la app actual.

Busqueda de palabras clave no encontro conectores activos de correo, OpenAI, embeddings, scraping, Selenium, Playwright, SMTP, IMAP, requests o HTTPX en `app`, `config`, `scripts`, `tests`, `README.md`, `docs` y `.agents`. Las coincidencias fueron documentales o campos locales como `linkedin_url`.

### Dependencias principales

`requirements.txt`:

- `streamlit>=1.37`
- `SQLAlchemy>=2.0`
- `pydantic>=2.8`
- `PyYAML>=6.0`
- `pandas>=2.2`
- `pytest>=8.2`
- `alembic>=1.13`

## 4. Trabajo realizado

### Fase 1 - Base local

Que se hizo:

- Estructura inicial.
- Streamlit minimo.
- SQLite con SQLAlchemy.
- Configuracion YAML y `.env`.
- Pruebas basicas.

Por que:

- Tener una base local, segura y verificable.

Archivos principales:

- `app/main.py`
- `app/config.py`
- `app/database.py`
- `app/models/database_models.py`
- `scripts/initialize_database.py`
- `tests/test_config.py`
- `tests/test_database.py`

Resultado:

- App local inicial funcional con contadores seguros en cero.

### Fase 2 - Perfil profesional

Que se hizo:

- Perfil principal unico.
- CRUD de experiencias.
- Habilidades normalizadas con alias.
- Evidencias por habilidad.
- Herramientas normalizadas.
- Formacion, certificaciones, cargos objetivo, sectores, preferencias, restricciones y crecimiento.
- Completitud explicable del perfil.
- Seed inicial idempotente.

Por que:

- El motor de vacantes necesita un perfil estructurado para comparar y priorizar.

Archivos principales:

- `app/ui/profile_pages.py`
- `app/repositories/profile_repository.py`
- `app/repositories/experience_repository.py`
- `app/repositories/skill_repository.py`
- `app/repositories/tool_repository.py`
- `app/repositories/education_repository.py`
- `app/repositories/career_preference_repository.py`
- `app/services/profile_completeness.py`
- `scripts/seed_initial_profile.py`
- `tests/test_profile_phase2.py`

Decisiones:

- Mantener un solo perfil principal activo.
- Usar YAML para catalogos y alias.
- No duplicar habilidades por alias.
- Separar preferencias de restricciones.

Resultado:

- Perfil editable y validado por pruebas.

### Fase 3 - Vacantes

Que se hizo:

- Registro manual de vacantes.
- Importacion CSV con staging.
- Normalizacion de cargo, empresa, ubicacion, salario y fechas.
- Deteccion de duplicados exactos y probables.
- Calidad de datos.
- Alertas de vacantes sospechosas.
- Historial de estado.
- Etiquetas.
- Exportacion CSV.

Por que:

- Capturar oportunidades de forma local, estructurada y controlada.

Archivos principales:

- `app/ui/job_pages.py`
- `app/repositories/job_repository.py`
- `app/repositories/import_repository.py`
- `app/services/job_import.py`
- `app/services/job_normalization.py`
- `app/services/job_duplicate.py`
- `app/services/job_quality.py`
- `config/job_import.yaml`
- `tests/test_jobs_phase3.py`

Resultado:

- Vacantes importables y gestionables con revision humana.

### Fase 3.1 - Estabilizacion

Que se hizo:

- Alembic formal.
- Baseline del esquema actual.
- Editor visual de mapeo CSV.
- Perfiles reutilizables de mapeo.
- Pruebas locales de volumen.

Por que:

- Resolver riesgos: falta de migraciones formales, mapeo CSV incompleto y poca claridad sobre volumen.

Archivos principales:

- `alembic/env.py`
- `alembic/versions/202607020001_phase_3_1_baseline.py`
- `app/services/csv_mapping.py`
- `app/repositories/mapping_profile_repository.py`
- `tests/test_phase3_1_stabilization.py`

Resultado:

- Alembic queda como mecanismo oficial de esquema.

### Fase 4 - Compatibilidad explicable

Que se hizo:

- Extraccion deterministica de requisitos.
- Requisitos editables.
- Motor de puntuacion sobre 100.
- Componentes: skills, experience, target_role, growth, salary, location_modality, company_sector, recency.
- Confianza y cobertura separadas.
- Fortalezas, brechas, datos faltantes y oportunidades.
- Versionado por hashes de perfil, vacante y configuracion.

Por que:

- Ninguna recomendacion debe mostrarse sin justificacion.

Archivos principales:

- `app/ui/compatibility_pages.py`
- `app/services/requirement_extraction.py`
- `app/services/compatibility_scoring.py`
- `app/services/evaluation_engine.py`
- `app/services/evaluation_version.py`
- `app/services/constraint_evaluation.py`
- `app/services/strength_gap.py`
- `app/repositories/evaluation_repository.py`
- `config/compatibility_scoring.yaml`
- `alembic/versions/202607020002_phase_4_evaluations.py`
- `tests/test_phase4_compatibility.py`

Resultado:

- Evaluaciones explicables y persistidas.

### Fase 5 - Priorizacion estrategica

Que se hizo:

- Bandeja estrategica.
- Puntuacion de prioridad separada de compatibilidad.
- Acciones recomendadas.
- Lista diaria y vistas guardadas.
- Decisiones humanas.
- Seguimiento local de postulaciones.
- Overrides de esfuerzo.

Por que:

- Ayudar a decidir donde invertir tiempo hoy.

Archivos principales:

- `app/ui/strategic_inbox_pages.py`
- `app/services/prioritization.py`
- `app/services/urgency.py`
- `app/services/strategic_alignment.py`
- `app/services/actionability.py`
- `app/services/application_effort.py`
- `app/services/decision_service.py`
- `app/repositories/prioritization_repository.py`
- `config/priority_strategy.yaml`
- `alembic/versions/202607020003_phase_5_strategic_inbox.py`
- `alembic/versions/202607020004_phase_5_effort_overrides.py`
- `tests/test_phase5_prioritization.py`

Resultado:

- Vacantes evaluadas pueden priorizarse y convertirse en decisiones locales.

### Fase 6 - Retroalimentacion y aprendizaje controlado

Que se hizo:

- Eventos de retroalimentacion.
- Resultados de postulaciones.
- Corridas de aprendizaje deterministicas.
- Metricas de conversion y ranking.
- Propuestas explicables.
- Historial de cambios.

Por que:

- Aprender de postulaciones y respuestas sin cambios automaticos descontrolados.

Archivos principales:

- `app/ui/feedback_learning_pages.py`
- `app/services/feedback_service.py`
- `app/services/application_outcome_service.py`
- `app/services/learning_service.py`
- `app/repositories/feedback_repository.py`
- `config/feedback_learning.yaml`
- `alembic/versions/202607020005_phase_6_feedback_learning.py`
- `tests/test_phase6_feedback_learning.py`

Resultado:

- Aprendizaje supervisado, con revision humana obligatoria.

### Fase 6.1 - Estabilizacion

Que se hizo:

- `applications.profile_id`.
- `adjustment_proposals.expires_at`.
- Deduplicacion de senales implicitas.
- Metricas por postulaciones unicas.
- Rechazo de referencias cruzadas entre perfiles.
- Propuestas pospuestas/expiradas.
- Aplicacion de propuestas protegida por hash de configuracion.

Por que:

- Resolver riesgos detectados en auditoria de Fase 6.

Archivos principales:

- `app/models/database_models.py`
- `app/services/feedback_service.py`
- `app/services/application_outcome_service.py`
- `app/services/learning_service.py`
- `app/services/decision_service.py`
- `app/repositories/feedback_repository.py`
- `app/repositories/prioritization_repository.py`
- `alembic/versions/202607020006_phase_6_1_stabilization.py`
- `tests/test_phase6_feedback_learning.py`

Resultado:

- Fase 6.1 verificada con pruebas completas.

### Continuidad para Fase 2.1

Que se hizo:

- Skill `radar-cv-ingestion`.
- Documento `docs/phase_2_1_cv_ingestion_design.md`.
- Auditoria post Fase 6.1 en `docs/post_phase_6_1_audit.md`.

Por que:

- Evitar que el usuario tenga que ingresar todo el CV manualmente y preparar la futura carga asistida sin tocar aun la app.

Resultado:

- Plan claro para implementar carga asistida desde CV en una proxima tarea.

## 5. Funcionalidades actuales

### Panel inicial

Usuario:

- Ve titulo, estado de base de datos, vacantes registradas, guardadas y postulaciones.

Tecnico:

- `app/main.py` llama `get_dashboard_snapshot` en `app/services/dashboard_metrics.py`.
- Los contadores usan SQLAlchemy y devuelven cero si no hay registros.

### Mi perfil profesional

Usuario:

- Crea y edita perfil.
- Registra experiencias, habilidades, evidencias, herramientas, formacion, certificaciones, cargos, sectores, preferencias, restricciones y crecimiento.

Tecnico:

- UI en `app/ui/profile_pages.py`.
- Repositorios: `ProfileRepository`, `ExperienceRepository`, `SkillRepository`, `ToolRepository`, `EducationRepository`, `CertificationRepository`, `CareerPreferenceRepository`.
- Validaciones en `app/services/validation.py`.
- Normalizacion en `app/utils/normalization.py`.

### Vacantes

Usuario:

- Registra vacantes manuales.
- Importa CSV.
- Revisa staging antes de guardar.
- Filtra, cambia estado, elimina logicamente, restaura, etiqueta y exporta.

Tecnico:

- UI en `app/ui/job_pages.py`.
- Servicios: `JobImportService`, `JobNormalizationService`, `JobDuplicateService`, `JobQualityService`, `CSVMappingService`.
- Repositorios: `JobRepository`, `ImportBatchRepository`, `StagingJobRepository`, `CSVMappingProfileRepository`.

### Compatibilidad

Usuario:

- Extrae requisitos.
- Revisa o corrige requisitos.
- Evalua vacantes.
- Ve puntaje, confianza, cobertura, fortalezas y brechas.

Tecnico:

- UI en `app/ui/compatibility_pages.py`.
- Servicios: `RequirementExtractionService`, `CompatibilityScoringService`, `EvaluationEngineService`, `ConstraintEvaluationService`, `StrengthGapService`.
- Repositorio: `EvaluationRepository`.

### Bandeja estrategica

Usuario:

- Prioriza oportunidades.
- Ve accion recomendada.
- Registra decision humana.
- Crea lista diaria y vistas guardadas.
- Sigue postulaciones locales.

Tecnico:

- UI en `app/ui/strategic_inbox_pages.py`.
- Servicios: `PrioritizationService`, `UrgencyService`, `StrategicAlignmentService`, `ActionabilityService`, `ApplicationEffortService`, `DecisionService`.
- Repositorio: `PrioritizationRepository`.

### Aprendizaje

Usuario:

- Registra senales y resultados.
- Ejecuta analisis.
- Revisa propuestas.
- Aprueba, rechaza, pospone, aplica o revierte propuestas.

Tecnico:

- UI en `app/ui/feedback_learning_pages.py`.
- Servicios: `FeedbackService`, `ApplicationOutcomeService`, `LearningService`.
- Repositorio: `FeedbackRepository`.

### Skills locales

Skills detectadas:

- `radar-cv-ingestion`
- `radar-feature-builder`
- `radar-job-import`
- `radar-project-orchestrator`
- `radar-release-check`
- `radar-safe-migrations`
- `radar-streamlit-ux`
- `radar-test-auditor`

## 6. Errores corregidos

No existe un registro historico unico con todos los mensajes exactos de error. Esta seccion recoge los problemas documentados por archivos, pruebas y contexto del proyecto.

### Falta de migraciones formales

- Mensaje/error: riesgo de no tener Alembic y modificar SQLite de forma manual.
- Causa raiz: esquema crecia por modelos y helpers sin historial formal.
- Archivos afectados: `alembic/env.py`, `alembic/versions/*`, `app/models/database_models.py`.
- Solucion aplicada: baseline Fase 3.1 y migraciones incrementales hasta Fase 6.1.
- Prevencion: todo cambio de esquema debe usar Alembic y base temporal de prueba.

### Editor visual CSV incompleto

- Mensaje/error: riesgo detectado en estabilizacion Fase 3.1.
- Causa raiz: el usuario necesitaba revisar y corregir mapeos antes de validar.
- Archivos afectados: `app/services/csv_mapping.py`, `app/ui/job_pages.py`, `app/repositories/mapping_profile_repository.py`.
- Solucion aplicada: mapeo visual con confianza, selector manual, no importar, advertencias, perfiles guardables y eliminables.
- Prevencion: mantener logica de mapeo fuera de Streamlit y probar conflictos.

### Pruebas de volumen insuficientemente documentadas

- Mensaje/error: riesgo de confundir verificaciones locales con benchmarks.
- Causa raiz: no estaba clara la naturaleza de pruebas de volumen.
- Archivos afectados: `tests/test_jobs_phase3.py`, `tests/test_phase3_1_stabilization.py`, `README.md`.
- Solucion aplicada: pruebas locales para 100, 1000 y maximo configurado, sin umbrales arbitrarios.
- Prevencion: no llamar benchmark formal a estas pruebas.

### Fase 6 con riesgos de mezcla de perfiles y metricas infladas

- Mensaje/error: auditoria de Fase 6 no aprobada.
- Causa raiz: postulaciones no quedaban suficientemente atadas al perfil y algunas metricas podian contar etapas repetidas.
- Archivos afectados: `app/models/database_models.py`, `app/services/application_outcome_service.py`, `app/services/learning_service.py`, `app/repositories/feedback_repository.py`.
- Solucion aplicada: `applications.profile_id`, validacion cruzada de referencias, metricas por postulaciones unicas y deduplicacion.
- Prevencion: toda senal/decision/resultado debe validar perfil, vacante, evaluacion, prioridad y postulacion.

### Propuestas de aprendizaje sin vencimiento claro

- Mensaje/error: riesgo de aplicar propuestas antiguas o con configuracion cambiada.
- Causa raiz: faltaba vencimiento y proteccion suficiente por hash.
- Archivos afectados: `adjustment_proposals`, `LearningService`, `FeedbackRepository`.
- Solucion aplicada: `expires_at`, estados `Pospuesta` y `Expirada`, validacion de `configuration_hash`.
- Prevencion: no aplicar propuestas si la configuracion cambio o si expiraron.

### Compatibilidad con PowerShell

- Mensaje/error observado durante esta tarea: `El operador '<' esta reservado para uso futuro`.
- Causa raiz: se intento usar sintaxis heredoc de Bash en PowerShell.
- Archivos afectados: ninguno.
- Solucion aplicada: se uso here-string de PowerShell con pipe a Python.
- Prevencion: usar comandos PowerShell nativos en este entorno.

## 7. Decisiones tecnicas importantes

- Python objetivo: 3.14.6.
- App local, no SaaS.
- SQLite en `data/radar_laboral.db`.
- Alembic es obligatorio para cambios de esquema.
- YAML contiene pesos, alias, catalogos y reglas.
- No guardar credenciales en codigo.
- No usar servicios externos de pago en primeras fases.
- No scraping de LinkedIn.
- No automatizar postulaciones externas.
- No enviar CV, correos ni mensajes sin aprobacion humana.
- El scoring debe ser explicable.
- Compatibilidad y prioridad son conceptos separados.
- La ausencia de informacion baja confianza/cobertura, no implica incumplimiento automatico.
- Perfil actual: solo un perfil principal activo.
- Las habilidades y herramientas se normalizan por aliases YAML.
- Responsabilidades y logros se guardan separados en experiencia.
- Preferencias influyen; restricciones pueden excluir.
- Aprendizaje no modifica automaticamente perfil, YAML, pesos ni postulaciones.
- Propuestas requieren revision humana.
- Tests deben usar bases temporales.
- UI no debe escribir directo a SQLite; debe usar repositorios/servicios.

### Pesos principales

Compatibilidad Fase 4:

- `skills`: 25
- `experience`: 15
- `target_role`: 15
- `growth`: 10
- `salary`: 10
- `location_modality`: 10
- `company_sector`: 10
- `recency`: 5

Prioridad Fase 5:

- `compatibility`: 35
- `confidence`: 10
- `urgency`: 15
- `strategic_alignment`: 15
- `growth_value`: 10
- `salary_location_fit`: 5
- `actionability`: 5
- `application_effort`: 5

Aprendizaje Fase 6.1:

- Version: `phase6.1`.
- Limites de senal: -2.0 a 2.0.
- Propuestas expiran en 30 dias.
- Estados de propuesta: `Pendiente`, `Aprobada`, `Rechazada`, `Aplicada`, `Revertida`, `Pospuesta`, `Expirada`.

## 8. Base de datos y modelos

Fuente principal: `app/models/database_models.py`.

### Entidades principales

| Entidad | Campos clave | Relaciones | Validaciones/estados | Uso |
|---|---|---|---|---|
| `jobs` | title, company, location, salary, description, source, status, quality, duplicate flags | import_batches, applications, requirements, evaluations, priorities, decisions | status desde `job_import.yaml`; calidad: Completa/Parcial/Minima/Invalida | Vacantes |
| `interactions` | job_id, action, reason, notes | jobs | accion local simple | Contadores e historial basico |
| `applications` | job_id, profile_id, application_date, cv_version, status, response/interview, offer_received | jobs, professional_profiles, outcomes | status desde `priority_strategy.yaml` | Seguimiento local |
| `recommendation_scores` | job_id, model_version, total_score, score_details, explanation | jobs | legado/inicial | Fase 1/score inicial |
| `professional_profiles` | full_name, professional_title, summary, location, experience, urls, is_primary | experiencias, skills, tools, education, preferences, learning | solo perfil principal activo | Perfil |
| `work_experiences` | company, job_title, dates, description, achievements, people_managed | profile | end_date >= start_date; current sin end_date | Experiencia |
| `skills` | name, normalized_name, category | profile_skills | normalized_name unico | Catalogo de habilidades |
| `profile_skills` | profile_id, skill_id, level, years, interest, core | profile, skill, evidences | unico por perfil+skill; years >= 0 | Habilidades del perfil |
| `skill_evidences` | profile_skill_id, type, title, description, metric | profile_skill | metric >= 0 | Evidencias |
| `tools` | name, category, normalized_name | profile_tools | normalized_name unico | Catalogo herramientas |
| `profile_tools` | profile_id, tool_id, level, years | profile, tool | unico por perfil+tool | Herramientas del perfil |
| `education_records` | institution, degree, field, level, dates, status | profile | end_date >= start_date | Formacion |
| `certifications` | name, organization, dates, credential, does_not_expire | profile | expiration >= issue | Certificaciones |
| `target_roles` | role_name, normalized, priority, desired_level, minimum_salary | profile | unico perfil+normalized; salary >= 0 | Cargos objetivo |
| `target_sectors` | sector_name, priority | profile | prioridad catalogada | Sectores objetivo |
| `job_preferences` | cities, provinces, modalities, salary, commute, contract flags | profile | salarios/commute >= 0 | Preferencias |
| `job_constraints` | type, operator, value, is_active | profile | catalogos YAML | Restricciones |
| `growth_goals` | title, description, target_skill, target_role, priority, progress | profile, skill | progress 0 a 100 | Crecimiento |
| `import_batches` | source, file metadata, row counts, status | staging, errors, jobs | batch_statuses YAML | Importacion CSV |
| `import_staging_jobs` | raw_data, parsed_data, validation, duplicate, decision | import_batch, duplicate_job | statuses YAML | Staging CSV |
| `job_import_errors` | batch_id, row, field, code, message, severity | batch, staging | severities YAML | Errores CSV |
| `csv_mapping_profiles` | source_name, mapping, notes | ninguno | mapping JSON | Perfiles de mapeo CSV |
| `job_status_history` | job_id, previous, new, reason, source | jobs | source YAML | Auditoria de estado |
| `job_tags` | name, normalized_name | assignments | normalized unico | Etiquetas |
| `job_tag_assignments` | job_id, tag_id | jobs, tags | unico job+tag | Etiquetas por vacante |
| `job_requirements` | job_id, type, raw_text, normalized, importance, skill/tool, confidence | job, skill, tool | active/confirmed | Requisitos Fase 4 |
| `evaluation_runs` | profile_id, version, hashes, counts, status | evaluations | versionado | Corridas de compatibilidad |
| `job_evaluations` | run, job, profile, scores, eligibility, recommendation, strengths/gaps | run, job, components | stale flag | Resultados Fase 4 |
| `evaluation_components` | evaluation_id, component, weight, raw, points, confidence, explanation | evaluation | componente explicable | Detalle score |
| `prioritization_runs` | profile_id, version, hash, counts, status | priorities | versionado | Corridas Fase 5 |
| `job_priorities` | run, job, evaluation, profile, scores, action, bucket, reasons | run, job, evaluation | stale flag; run+position unico | Bandeja |
| `job_decisions` | job, profile, priority, decision, reason, follow_up | job, profile, priority | decision_source YAML | Decision humana |
| `application_effort_overrides` | job, profile, effort_level, notes | job, profile | unico job+profile | Esfuerzo manual |
| `saved_views` | profile, name, filters_json, sort_json, default | profile | unico profile+name | Vistas guardadas |
| `daily_shortlists` | profile, date, status | profile, items | unico profile+date | Lista diaria |
| `daily_shortlist_items` | shortlist, job, priority, position, action, status | shortlist, job, priority | unico shortlist+job/position | Items diarios |
| `feedback_events` | profile, job, evaluation/priority/application, type, category, signal, key | profile, job, optional refs | deduplication_key unico | Senales |
| `application_outcomes` | application, outcome_type, date, stage, response, salary, reason | application | secuencia validada | Resultados |
| `learning_runs` | profile, version, hash, period, counts, status, warnings | profile, metrics, proposals | thresholds YAML | Aprendizaje |
| `learning_metrics` | run, metric_name, scope, sample, value, confidence, evidence | learning_run | confidence_level | Metricas |
| `adjustment_proposals` | run, profile, type, target, current/proposed, evidence, confidence, status, expires | run, profile | estados y vencimiento | Propuestas |
| `configuration_change_history` | proposal, profile, area, previous/new, reason, rollback | proposal, profile | reversible cuando aplica | Historial |

### Migraciones

- `202607020001_phase_3_1_baseline.py`: baseline del esquema.
- `202607020002_phase_4_evaluations.py`: evaluaciones y requisitos.
- `202607020003_phase_5_strategic_inbox.py`: priorizacion, decisiones, vistas/listas.
- `202607020004_phase_5_effort_overrides.py`: esfuerzo manual.
- `202607020005_phase_6_feedback_learning.py`: feedback, outcomes, learning.
- `202607020006_phase_6_1_stabilization.py`: `applications.profile_id`, `adjustment_proposals.expires_at` y estabilizacion.

## 9. Pruebas realizadas

### Comandos ejecutados en esta tarea

```powershell
python -m pytest
python -m alembic current
python -m alembic heads
python -m alembic history
python -c "import app.main; import app.database; import app.models.database_models; import app.repositories; import app.services.evaluation_engine; import app.services.prioritization; import app.services.learning_service; import app.ui.profile_pages; import app.ui.job_pages; import app.ui.compatibility_pages; import app.ui.strategic_inbox_pages; import app.ui.feedback_learning_pages; print('imports-ok')"
```

### Resultado

- `python -m pytest`: 59 passed in 91.87s.
- `python -m alembic current`: `202607020006 (head)`.
- `python -m alembic heads`: `202607020006 (head)`.
- `python -m alembic history`: historial completo disponible.
- Imports principales: `imports-ok`.

### Que se probo

- Configuracion y YAML.
- Base temporal y tablas requeridas.
- Dashboard sin registros.
- Perfil Fase 2.
- Experiencias y fechas.
- Habilidades, aliases, evidencias.
- Herramientas.
- Formacion/certificaciones.
- Preferencias, restricciones, contradicciones.
- Seed idempotente.
- Vacantes Fase 3.
- Importacion CSV, staging, decisiones, exportacion.
- Duplicados y calidad.
- Escenarios de auditoria Fase 3.
- Volumen local.
- Alembic en base temporal.
- Compatibilidad Fase 4.
- Priorizacion Fase 5.
- Feedback y aprendizaje Fase 6/6.1.

### Que no se probo en esta tarea

- Inicio visual real de Streamlit en navegador.
- Clicks manuales en cada pantalla.
- Datos reales de usuario dentro de `data/radar_laboral.db`.
- Downgrade sobre base real, correctamente evitado.
- Lectura de CV, porque aun no esta implementada.
- OCR o documentos escaneados.

## 10. Problemas conocidos y deuda tecnica

| Prioridad | Problema | Riesgo | Recomendacion |
|---|---|---|---|
| Media | `app/database.py` conserva `ensure_phase3_job_columns` | Puede modificar esquema SQLite fuera de Alembic | Crear estabilizacion para retirarlo o aislarlo tras verificar migraciones |
| Media | UI usa `SessionLocal` directamente en paginas | Puede crecer logica de acceso en Streamlit | Mantener reglas en servicios/repositorios; revisar Fase 2.1 con esta regla |
| Media | No hay carga asistida de CV | Entrada manual del perfil es lenta | Implementar Fase 2.1 |
| Media | No hay persistencia de borradores CV | Si se implementa solo en sesion, no habra trazabilidad | Decidir si usar tablas `profile_import_batches/candidates` |
| Media | No se hizo prueba visual Streamlit en esta tarea | Puede haber problemas de layout o widgets no cubiertos | Ejecutar app y recorrer flujos antes de release |
| Baja | `git` no esta disponible en esta terminal | No se pudo mostrar `git status` | Verificar cambios desde otra terminal con Git |
| Baja | Skills locales salvo `radar-cv-ingestion` no tienen `agents/openai.yaml` | Menor visibilidad en UI de skills | Generar metadata si se desea |
| Baja | Pruebas de volumen no son benchmarks | No predicen rendimiento real multiusuario o alto volumen | Hacer benchmark formal solo cuando haya fuentes automatizadas |
| Baja | No hay OCR para PDFs escaneados | CV escaneado no sera legible | Dejar OCR para fase posterior |

No se detectaron secretos versionados ni conectores externos activos en la busqueda realizada.

## 11. Proxima tarea exacta

### Tarea recomendada

Implementar Fase 2.1: carga asistida del perfil desde CV, en version minima sin persistir borradores.

### Objetivo

Permitir cargar un CV `.txt`, `.pdf` con texto seleccionable o `.docx`, extraer texto localmente, generar candidatos revisables y guardar solo datos aceptados/editados por el usuario.

### Archivos que debe revisar

- `.agents/skills/radar-cv-ingestion/SKILL.md`
- `.agents/skills/radar-cv-ingestion/references/phase_2_1_contract.md`
- `docs/phase_2_1_cv_ingestion_design.md`
- `app/ui/profile_pages.py`
- `app/repositories/profile_repository.py`
- `app/repositories/experience_repository.py`
- `app/repositories/skill_repository.py`
- `app/repositories/tool_repository.py`
- `app/repositories/education_repository.py`
- `app/repositories/career_preference_repository.py`
- `app/services/validation.py`
- `app/utils/normalization.py`
- `config/profile_catalogs.yaml`
- `tests/test_profile_phase2.py`

### Archivos que probablemente debera modificar

Si se implementa opcion minima:

- `requirements.txt`, si se agregan parsers locales para PDF/DOCX.
- `app/services/cv_document_reader.py`
- `app/services/cv_profile_extraction.py`
- `app/services/cv_profile_draft.py`
- `app/ui/profile_pages.py`
- `tests/test_profile_cv_ingestion.py`
- `README.md`

Si se decide persistir borradores:

- `app/models/database_models.py`
- `alembic/versions/<nueva_migracion>.py`
- repositorio/servicio para importacion de perfil.

### Pasos recomendados

1. Usar la skill `radar-cv-ingestion`.
2. Confirmar si se hara opcion minima sin persistencia o version con Alembic.
3. Agregar lectores locales para `.txt`, `.pdf` y `.docx`.
4. Crear servicios de extraccion conservadora.
5. Crear contrato Pydantic o dataclasses para candidatos.
6. Agregar pestana `Importar CV` en `Mi perfil profesional`.
7. Mostrar candidatos con aceptar, editar u omitir.
8. Aplicar solo candidatos aceptados/editados mediante repositorios.
9. Probar CV ficticio vacio, parcial, con experiencias, fechas ambiguas y aliases.
10. Ejecutar pruebas completas y Alembic.

### Criterios de aceptacion

- No se guarda el archivo CV original por defecto.
- No se guarda ningun dato sin confirmacion.
- No se inventan datos ausentes.
- Skills/herramientas usan alias YAML.
- Duplicados de habilidad/herramienta se impiden.
- Fechas ambiguas quedan pendientes.
- Responsabilidades y logros se mantienen separados.
- UI no escribe directo a SQLite.
- Tests pasan.
- README documenta el flujo.

### Pruebas necesarias

- CV vacio o ilegible.
- CV parcial.
- CV con experiencia, habilidades y herramientas.
- CV con `Excel`, `MS Excel`, `Microsoft Excel`.
- CV con fecha final anterior a inicial.
- CV con certificacion sin fecha.
- Usuario acepta, edita y omite.
- Aplicacion idempotente cuando el usuario intenta guardar habilidad duplicada.
- Import de modulos.
- `python -m pytest`.
- `python -m alembic current`.

### Riesgos a evitar

- No implementar IA, embeddings, correo, scraping ni OCR en esta primera version.
- No tocar base real sin respaldo.
- No agregar migracion si se elige borrador solo en sesion.
- No guardar el texto completo del CV sin aprobacion.
- No reemplazar datos existentes silenciosamente.

## 12. Plan restante

| Orden | Tarea | Prioridad | Dependencias | Complejidad | Resultado esperado | Criterio de terminado |
|---|---|---|---|---|---|---|
| 1 | Fase 2.1 carga asistida desde CV | Alta | Perfil Fase 2, skill CV | Alta | Perfil se llena desde borrador revisable | Tests CV y flujo UI |
| 2 | Estabilizar `create_tables` vs Alembic | Media | Auditoria esquema | Media | No hay cambios de esquema fuera de Alembic | Tests y migraciones pasan |
| 3 | Prueba visual Streamlit completa | Alta | App ejecutable | Media | Flujos principales recorridos | Sin errores de UI ni claves duplicadas |
| 4 | Reporte semanal/diario | Media | Vacantes, prioridades, feedback | Media | Reportes locales explicables | Tests y docs |
| 5 | Automatizacion programada local | Media | Reportes y fuentes locales | Media | Tareas programadas sin conexiones externas riesgosas | Ejecucion manual y tests |
| 6 | Importacion desde alertas de correo | Media | Politica de privacidad y conectores | Alta | Procesar alertas aprobadas | Sin envio automatico; pruebas con fixtures |
| 7 | Mejorar deduplicacion historica de empresas/vacantes | Media | Datos reales respaldados | Media | Limpieza segura y reversible | Backup, reporte, pruebas |
| 8 | Benchmarks formales | Baja | Volumen mayor o automatizacion | Alta | Medicion reproducible | Reporte formal |
| 9 | OCR para CV escaneados | Baja | Fase 2.1 estable | Alta | Soporte opcional para escaneados | Sin servicios externos por defecto |
| 10 | Empaquetado local mas amigable | Baja | App estable | Media | Instalacion simplificada Windows | Script probado |

## 13. Archivos clave para continuar

Leer primero:

- `AGENTS.md`: reglas permanentes del proyecto.
- `CONTEXTO_PROYECTO.md`: este documento.
- `README.md`: comandos y alcance actual.
- `.agents/skills/radar-cv-ingestion/SKILL.md`: guia para la siguiente tarea recomendada.
- `.agents/skills/radar-cv-ingestion/references/phase_2_1_contract.md`: contrato de borrador CV.
- `docs/phase_2_1_cv_ingestion_design.md`: diseno de Fase 2.1.
- `app/main.py`: navegacion principal.
- `app/ui/profile_pages.py`: lugar probable de la UI de Fase 2.1.
- `app/models/database_models.py`: entidades y relaciones.
- `app/config.py`: YAML y settings.
- `app/database.py`: sesiones, engine y deuda tecnica `ensure_phase3_job_columns`.
- `config/profile_catalogs.yaml`: alias y catalogos del perfil.
- `tests/test_profile_phase2.py`: patrones de prueba de perfil.
- `alembic/versions/202607020006_phase_6_1_stabilization.py`: ultima migracion aplicada.

## 14. Comandos importantes

### Crear entorno

```powershell
py -3.14 -m venv .venv
```

### Activar entorno

```powershell
.\.venv\Scripts\Activate.ps1
```

Si PowerShell bloquea activacion:

```powershell
Set-ExecutionPolicy -Scope Process -ExecutionPolicy Bypass
.\.venv\Scripts\Activate.ps1
```

### Instalar dependencias

```powershell
python -m pip install --upgrade pip
python -m pip install -r requirements.txt
```

### Configurar `.env`

```powershell
Copy-Item .env.example .env
```

### Aplicar migraciones

```powershell
python -m alembic upgrade head
python -m alembic current
python -m alembic history
```

### Inicializar base local

```powershell
python scripts\initialize_database.py
```

### Cargar perfil inicial

```powershell
python scripts\seed_initial_profile.py
```

### Ejecutar proyecto

```powershell
python -m streamlit run app\main.py
```

O:

```powershell
.\run.bat
```

### Ejecutar pruebas

```powershell
python -m pytest
python -m pytest -x
```

### Revisar migraciones en base temporal

```powershell
$env:RADAR_DATABASE_URL = "sqlite:///data/temp/alembic_test.db"
python -m alembic upgrade head
python -m alembic current
python -m alembic history
python -m alembic downgrade base
python -m alembic upgrade head
Remove-Item Env:\RADAR_DATABASE_URL
```

### Crear respaldo de base real

```powershell
Copy-Item data\radar_laboral.db data\radar_laboral.backup.$(Get-Date -Format yyyyMMddHHmmss).db
```

### Detener Streamlit

En la terminal donde corre Streamlit:

```powershell
Ctrl+C
```

### Reiniciar aplicacion

```powershell
python -m streamlit run app\main.py
```

## 15. Instruccion para el siguiente agente

### Instruccion de reanudacion

```text
Estas continuando el proyecto local "Radar Laboral Adaptativo" en Windows, ruta:
C:\Users\MSI ERICK\Desktop\radar_laboral

El proyecto es una app local de busqueda, analisis, priorizacion y seguimiento de oportunidades laborales en Ecuador. Usa Python 3.14.6, Streamlit, SQLite, SQLAlchemy, Alembic, Pydantic, YAML, Pandas y Pytest.

Estado actual:
- Fases 1 a 6.1 implementadas.
- Ultima migracion: 202607020006 (head).
- Ultima verificacion conocida: python -m pytest -> 59 passed in 91.87s.
- Alembic current y heads apuntan a 202607020006.
- Imports principales pasan.
- No hay servicios externos activos, scraping, correo, embeddings, IA ni postulacion automatica.
- Se creo la skill local radar-cv-ingestion y el diseno de Fase 2.1.

Pendiente principal:
Implementar Fase 2.1: carga asistida del perfil desde CV, en una primera version local, deterministica y supervisada.

Antes de modificar codigo lee:
1. AGENTS.md
2. CONTEXTO_PROYECTO.md
3. .agents/skills/radar-cv-ingestion/SKILL.md
4. .agents/skills/radar-cv-ingestion/references/phase_2_1_contract.md
5. docs/phase_2_1_cv_ingestion_design.md
6. app/ui/profile_pages.py
7. app/models/database_models.py
8. app/config.py
9. app/database.py
10. tests/test_profile_phase2.py

Restricciones:
- No reconstruyas el proyecto.
- No elimines ni recrees la base real.
- Crea respaldo antes de cambios importantes.
- Usa Alembic para cualquier cambio de esquema.
- No guardes archivos de CV por defecto.
- No uses IA, embeddings, OCR, correo, scraping, LinkedIn ni servicios externos en la primera version de Fase 2.1.
- No guardes ningun dato extraido del CV sin confirmacion humana.
- No escribas directo a SQLite desde Streamlit; usa servicios y repositorios.
- No automatices postulaciones ni envio de CV.

Verificacion obligatoria tras cambios:
1. python -m pytest -x
2. python -m pytest
3. python -m alembic current
4. python -m alembic history
5. Import check de modulos principales
6. Inicio de Streamlit si se modifico UI

Riesgo conocido:
app/database.py conserva ensure_phase3_job_columns, un helper legado que puede modificar SQLite fuera de Alembic. No lo uses como patron nuevo; planifica retirarlo en una estabilizacion futura.
```


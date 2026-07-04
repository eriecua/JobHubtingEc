# Radar Laboral Adaptativo

Sistema local para registrar, estructurar y seguir oportunidades laborales en Ecuador.

## Alcance actual

Fase 1:

- Aplicacion local con Streamlit.
- SQLite con SQLAlchemy.
- Configuracion YAML.
- Pruebas automatizadas.

Fase 2:

- Perfil profesional estructurado.
- Experiencia, habilidades, evidencias, herramientas, formacion, certificaciones, objetivos y preferencias.
- Carga inicial editable del perfil.

Fase 2.1:

- Carga asistida del perfil desde CV local en `.txt`, `.pdf` con texto seleccionable o `.docx`.
- Extraccion deterministica de candidatos para perfil, experiencia, habilidades, herramientas, formacion, certificaciones y cargos objetivo.
- Revision humana con aceptar, editar u omitir antes de guardar.
- Persistencia solo de candidatos confirmados usando repositorios existentes.
- No guarda el archivo original del CV ni usa OCR, IA, embeddings, correo, scraping o LinkedIn.

Fase 3:

- Registro manual de vacantes.
- Importacion CSV con staging y confirmacion humana.
- Limpieza y normalizacion inicial.
- Deteccion deterministica de duplicados.
- Calidad de datos.
- Reglas configurables de vacantes sospechosas.
- Historial de cambios de estado.
- Etiquetas.
- Exportacion CSV de vacantes filtradas.

Fase 4:

- Motor deterministico de compatibilidad entre perfil y vacantes.
- Extraccion local de requisitos por reglas y alias.
- Evaluacion de restricciones obligatorias.
- Puntuacion explicable sobre 100.
- Confianza y cobertura separadas de la compatibilidad.
- Fortalezas, brechas, datos faltantes y oportunidades de crecimiento.
- Evaluaciones versionadas con hashes de perfil, vacante y configuracion.
- Deteccion de evaluaciones obsoletas.
- Ejecucion individual y masiva.

Fase 5:

- Bandeja estrategica para transformar evaluaciones en decisiones.
- Prioridad deterministica sobre 100, separada de compatibilidad.
- Acciones recomendadas: postular, preparar, revisar, explorar, guardar, esperar informacion, descartar o posponer.
- Corridas versionadas de priorizacion con hashes de vacante, evaluacion, decision y configuracion.
- Historial de decisiones humanas sin ejecutar postulaciones externas.
- Seguimiento local de postulaciones reutilizando `applications`.
- Lista diaria de trabajo y vistas guardadas.
- Limites WIP y deteccion de prioridades obsoletas.

Fase 6:

- Registro de senales explicitas, implicitas, resultados, correcciones y preferencias.
- Resultados detallados de postulaciones asociados a `applications`.
- Corridas de aprendizaje deterministicas y versionadas.
- Metricas de conversion, ranking, calibracion y segmentos.
- Propuestas explicables con muestra, evidencia, confianza y riesgo.
- Revision humana obligatoria antes de aprobar, aplicar o revertir cambios.
- Historial versionado en base de datos; no modifica YAML ni perfil automaticamente.

Fase 7:

- Captura manual y semiautomatica de oportunidades desde fuentes autorizadas.
- Fuentes configurables: carpeta local, EML guardado, RSS/Atom, API JSON publica autorizada y captura rapida por enlace.
- El importador CSV existente se conserva como flujo principal para archivos tabulares.
- Boton `Buscar nuevas ofertas` por fuente, sin programacion periodica.
- Registros capturados pasan a staging y requieren revision humana antes de importar.
- Se conserva metadata y contenido bruto recibido para trazabilidad.
- Proteccion basica contra SSRF en fuentes HTTP: bloquea localhost, redes privadas y esquemas no HTTP(S).
- Conector de correo autorizado queda estructural, desactivado por defecto y sin credenciales en base.

No incluye lectura automatica de correos, scraping, APIs laborales, embeddings, modelos de lenguaje, machine learning, adaptacion automatica de CV, cartas, envio de correos ni postulacion automatica.

## Requisitos

- Windows con PowerShell.
- Python 3.14.6.

## Entorno

```powershell
py -3.14 -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
python -m pip install -r requirements.txt
```

## Variables locales

```powershell
Copy-Item .env.example .env
```

La base local se guarda por defecto en `data/radar_laboral.db`.

## Aplicar esquema o migraciones

Desde la Fase 3.1 el esquema se gestiona con Alembic usando la metadata real de SQLAlchemy. Los cambios futuros de estructura deben hacerse con migraciones, no modificando manualmente la base.

Antes de tocar una base existente, crea una copia de seguridad:

```powershell
Copy-Item data\radar_laboral.db data\radar_laboral.backup.$(Get-Date -Format yyyyMMddHHmmss).db
```

### Instalacion nueva

Si todavia no existe `data\radar_laboral.db`:

```powershell
python -m alembic upgrade head
python -m alembic current
python -m alembic history
```

### Base existente creada antes de Alembic

Si la base ya fue creada con versiones anteriores, primero haz copia. Para que Alembic cree solo lo que falte y marque la revision:

```powershell
Copy-Item data\radar_laboral.db data\radar_laboral.backup.db
python -m alembic upgrade head
python -m alembic current
```

Si ya verificaste manualmente que la base contiene exactamente el esquema actual, puedes hacer solo baseline sin ejecutar cambios:

```powershell
Copy-Item data\radar_laboral.db data\radar_laboral.backup.db
python -m alembic stamp head
python -m alembic current
```

Luego, para migraciones futuras:

```powershell
python -m alembic upgrade head
```

### Base temporal de pruebas

Para verificar migraciones sin tocar la base real:

```powershell
$env:RADAR_DATABASE_URL = "sqlite:///data/temp/alembic_test.db"
python -m alembic upgrade head
python -m alembic current
python -m alembic history
python -m alembic downgrade base
python -m alembic upgrade head
Remove-Item Env:\RADAR_DATABASE_URL
```

No ejecutes `downgrade` sobre la base real salvo que exista una copia de seguridad y sepas que la migracion es reversible para tus datos.

El script historico sigue disponible para inicializacion local defensiva:

```powershell
python scripts\initialize_database.py
```

## Cargar perfil inicial

```powershell
python scripts\seed_initial_profile.py
```

El script es idempotente.

## Carga asistida desde CV

En la barra lateral abre `Mi perfil profesional` y entra en la pestana `Importar CV`.

Formatos admitidos:

- `.txt`
- `.pdf` con texto seleccionable
- Word moderno `.docx`

Flujo:

1. Carga el archivo.
2. Usa `Crear borrador desde CV`.
3. Revisa cada candidato.
4. Cambia su estado a `Aceptado`, `Editado`, `Omitido` o dejalo `Pendiente`.
5. Marca la confirmacion y usa `Guardar candidatos confirmados`.

Reglas importantes:

- El archivo se lee localmente y no se guarda automaticamente.
- Los candidatos de baja confianza o con fechas ambiguas quedan pendientes.
- Las habilidades y herramientas se normalizan con aliases de `config\profile_catalogs.yaml`.
- Solo se persisten candidatos aceptados o editados.
- Si el CV es un PDF escaneado, la app mostrara un error porque OCR queda fuera del alcance actual.
- Archivos Word antiguos `.doc` no se leen directamente; conviertelos a `.docx` o PDF con texto seleccionable.

La configuracion de formatos, tamanio maximo y minimo de texto extraible esta en:

```powershell
Get-Content config\cv_ingestion.yaml
```

## Iniciar aplicacion

```powershell
python -m streamlit run app\main.py
```

Tambien puedes usar:

```powershell
.\run.bat
```

## Vacantes

En la barra lateral abre `Vacantes`.

Pantallas disponibles:

- `Nueva vacante`: registro manual con validacion.
- `Repositorio`: filtros, detalle, cambio de estado, eliminacion logica y exportacion.
- `Importar CSV`: plantilla descargable, lectura y vista previa.
- `Importar CSV`: editor visual de mapeo con campo inferido, confianza, selector manual, opcion de no importar columna, advertencias y perfiles reutilizables.
- `Revisar importacion`: staging, decisiones por fila y confirmacion final.
- `Historial de importaciones`: estadisticas por lote.
- `Calidad de datos`: faltantes, recomendaciones y riesgo.
- `Fuentes`: configura fuentes autorizadas y ejecuta `Buscar nuevas ofertas` manualmente.
- `Captura rapida`: envia un enlace a staging sin visitar ni raspar la pagina.
- `EML`: importa un correo guardado como `.eml` sin conectar a una cuenta de correo.

## Fuentes Autorizadas

En `Vacantes > Fuentes` puedes crear fuentes de captura.

Tipos iniciales:

- `LOCAL_FOLDER`: revisa una carpeta relativa dentro del proyecto. Admite `.csv`, `.json` y `.eml`; registra hash de archivo y no reprocesa el mismo archivo salvo que configures `allow_reprocess: true`.
- `RSS_ATOM`: descarga un feed autorizado con timeout y limite de tamano.
- `PUBLIC_JSON_API`: consulta una API publica autorizada con metodo `GET`, parametros permitidos y mapeo de campos.
- `AUTHORIZED_EMAIL`: queda preparado pero desactivado por defecto. No simula conexion exitosa y no guarda credenciales.

Reglas de seguridad:

- No se ejecuta scraping de LinkedIn, Computrabajo ni Multitrabajos.
- No hay login automatico, captcha solving, navegadores ocultos, proxies ni postulaciones.
- No se envian correos, mensajes ni CV.
- No hay programador periodico; eso queda para Fase 8.
- Las URLs remotas bloquean localhost, `127.0.0.1`, redes privadas y esquemas distintos de HTTP/HTTPS.
- Las redirecciones HTTP tambien se validan antes de seguirlas.
- No guardes tokens, passwords, API keys ni secretos en la configuracion JSON, tampoco dentro de `headers`.

Flujo:

1. Crea o activa una fuente.
2. Usa `Probar conexion`.
3. Pulsa `Buscar nuevas ofertas`.
4. Revisa el lote creado en `Revisar importacion`.
5. Importa solo las filas aprobadas.

La captura rapida por enlace solo guarda el enlace y los datos que escribas; no descarga la pagina.

## Formato CSV

Plantilla sugerida:

```csv
title,company,city,province,country,modality,employment_type,contract_type,salary_min,salary_max,currency,salary_period,publication_date,expiration_date,description,responsibilities,requirements,education_required,experience_min_years,experience_max_years,seniority_level,sector,source,source_url,external_id,benefits,notes
```

Tambien se admiten alias configurados en `config/job_import.yaml`, por ejemplo:

- `cargo` -> `title`
- `empresa` -> `company`
- `ciudad` -> `city`
- `sueldo` -> `salary_min`
- `link` -> `source_url`
- `detalle` -> `description`

El usuario revisa el mapeo inferido antes de crear el lote.

El editor de mapeo muestra:

- Columna original del archivo.
- Campo inferido por alias YAML.
- Confianza de la inferencia.
- Selector manual del campo de destino.
- Opcion `No importar esta columna`.
- Vista previa de valores.

No se puede crear un lote si faltan `title`, `company`, `source` o `description`, o si dos columnas apuntan al mismo campo. Los perfiles de mapeo se guardan por fuente y no almacenan el contenido del archivo CSV.

## Duplicados

La deteccion es deterministica y local:

- Exacta por `source + external_id`.
- Exacta por `source + source_url`.
- Exacta por `content_hash`.
- Probable por similitud ponderada de cargo, empresa, ciudad, fecha, fuente y descripcion.

Una coincidencia alta no siempre significa que sea la misma vacante. Revise empresa, fecha, ubicacion y descripcion antes de decidir.

## Calidad y sospecha

La calidad puede ser:

- `Completa`
- `Parcial`
- `Minima`
- `Invalida`

Las vacantes marcadas como sospechosas no se eliminan automaticamente. La decision final pertenece al usuario.

## Exportar vacantes

Desde `Vacantes > Repositorio`, usa `Exportar visibles a CSV`.

El archivo se genera con UTF-8 con BOM y excluye campos internos como JSON tecnico.

## Compatibilidad

En la barra lateral abre `Compatibilidad`.

El motor compara cada vacante con el perfil profesional principal usando reglas configurables en `config/compatibility_scoring.yaml`.

Conceptos:

- `Compatibilidad`: puntaje tecnico de ajuste sobre 100.
- `Confianza`: que tan confiable es el resultado segun datos estructurados, evidencia, valores neutrales y calidad de la informacion.
- `Cobertura`: proporcion de informacion disponible para evaluar.
- `Elegibilidad`: resultado de restricciones obligatorias antes de priorizar la vacante.
- `Recomendacion`: clasificacion final separada de la elegibilidad.

El flujo local es:

```powershell
python -m alembic upgrade head
python scripts\seed_initial_profile.py
python -m streamlit run app\main.py
```

Para evaluar:

1. En `Vacantes`, registra o importa vacantes.
2. En `Compatibilidad > Requisitos`, selecciona una vacante y usa `Extraer requisitos`.
3. Revisa, confirma, edita, desactiva o agrega requisitos manuales.
4. En `Compatibilidad > Evaluar`, selecciona vacantes y confirma la ejecucion.
5. En `Compatibilidad > Resultados`, filtra por puntaje, confianza, elegibilidad, recomendacion u obsolescencia.
6. En `Compatibilidad > Detalle`, revisa componentes, fortalezas, brechas, restricciones y datos faltantes.

Para recalcular una vacante desde la interfaz, abre el detalle de una evaluacion y usa `Recalcular esta vacante`.

Los pesos iniciales son:

```yaml
skills: 25
experience: 15
target_role: 15
growth: 10
salary: 10
location_modality: 10
company_sector: 10
recency: 5
```

La suma debe ser 100. Si modificas pesos o reglas, las nuevas evaluaciones guardaran un nuevo hash de configuracion. Las evaluaciones anteriores pueden quedar obsoletas y deben recalcularse manualmente.

La ausencia de informacion no se interpreta automaticamente como incumplimiento. En esos casos se usan valores neutrales configurables y baja la confianza/cobertura.

Las certificaciones reconocidas por la extraccion deterministica se configuran en `known_certifications` dentro del mismo archivo. Si una certificacion obligatoria no esta cubierta por el perfil, se registra como brecha critica y no se clasifica como recomendacion prioritaria.

Limitaciones del motor deterministico:

- No usa IA, embeddings ni similitud semantica.
- No inventa habilidades ni requisitos ausentes.
- No convierte monedas extranjeras ni periodos salariales incompatibles.
- No calcula distancias geograficas.
- La extraccion por reglas puede requerir revision humana.
- Las pruebas de rendimiento son verificaciones locales, no benchmarks formales.

## Bandeja estrategica

En la barra lateral abre `Bandeja estrategica`.

La prioridad responde: "Que tan conveniente es dedicar tiempo a esta vacante ahora". Usa la compatibilidad como entrada, pero tambien considera urgencia, confianza, alineacion estrategica, crecimiento, ajuste salario/ubicacion, capacidad de actuar, esfuerzo de postulacion, estado, bloqueos e historial.

La compatibilidad responde: "Que tan bien encaja el perfil con esta vacante". No es lo mismo que prioridad.

Los pesos iniciales estan en `config/priority_strategy.yaml`:

```yaml
compatibility: 35
confidence: 10
urgency: 15
strategic_alignment: 15
growth_value: 10
salary_location_fit: 5
actionability: 5
application_effort: 5
```

La suma debe ser 100. Si modificas pesos o reglas, las nuevas prioridades guardan otro hash de configuracion y las prioridades previas pueden quedar obsoletas.

Componentes:

- `Compatibilidad`: usa la ultima evaluacion vigente de Fase 4.
- `Confianza`: valora si el resultado es confiable.
- `Urgencia`: combina publicacion, vencimiento y estado.
- `Alineacion estrategica`: cargos objetivo, sectores, ciudad y objetivos de crecimiento.
- `Crecimiento`: usa el componente growth y brechas manejables.
- `Salario/ubicacion`: valora preferencias, no elegibilidad.
- `Actionability`: revisa URL, claridad, duplicados, sospecha, evaluacion vigente y aplicaciones existentes.
- `Esfuerzo`: bajo, medio, alto o desconocido; se aplica de forma inversa y no genera CV ni cartas.
- El esfuerzo puede corregirse manualmente por vacante/perfil; la correccion queda guardada y marca la prioridad como obsoleta para recalcular.

Vistas disponibles:

- `Prioridad de hoy`: maximo 10 oportunidades accionables.
- `Postular`, `Preparar`, `Revisar`, `Explorar`, `Guardadas`, `Descartadas`.
- `Seguimiento`: decisiones con postulacion o preparacion.
- `Obsoletas`: prioridades que requieren recalculo.
- `Historial`: decisiones humanas registradas.
- `Lista diaria`: trabajo del dia, reordenable y archivable.
- `Vistas`: filtros reutilizables con una vista predeterminada por perfil.

Flujo recomendado:

```powershell
python -m alembic upgrade head
python -m streamlit run app\main.py
```

1. Registra o importa vacantes.
2. Evalua compatibilidad en `Compatibilidad`.
3. En `Bandeja estrategica > Prioridad de hoy`, usa `Priorizar activas`.
4. Revisa razones, advertencias y bloqueos.
5. Confirma una decision humana con motivo, notas y fecha de seguimiento si aplica.
6. Agrega oportunidades a la lista diaria.

La decision humana se guarda en `job_decisions` y tambien queda como interaccion local. Si decides `Postular` o `Preparar postulacion`, se crea seguimiento local en `applications`; no se envia ningun correo, CV ni formulario.

Limites WIP configurables:

```yaml
prepare_application: 5
review: 10
ready_to_apply: 5
```

Cuando se superan, la interfaz muestra una advertencia pero no bloquea.

Migraciones de Fase 5:

```powershell
python -m alembic upgrade head
python -m alembic current
python -m alembic history
```

Para probar downgrade solo en base temporal o con respaldo:

```powershell
python -m alembic downgrade 202607020003
python -m alembic upgrade head
python -m alembic downgrade 202607020002
python -m alembic upgrade head
```

## Retroalimentacion y aprendizaje

En la barra lateral abre `Aprendizaje`.

Vistas disponibles:

- `Senales`: registra senales manuales o de interfaz con pesos configurados en `config\feedback_learning.yaml`.
- `Resultados`: registra respuestas, entrevistas, pruebas, ofertas, rechazos o ausencia de respuesta sobre postulaciones existentes.
- `Analisis`: ejecuta una corrida deterministica para un periodo y muestra metricas explicables.
- `Propuestas`: permite aprobar, rechazar, posponer, aplicar o revertir propuestas; las propuestas vencidas se marcan como expiradas.
- `Historial`: muestra cambios versionados registrados en `configuration_change_history`.

El aprendizaje no usa modelos opacos, embeddings ni servicios externos. Los pesos de senal solo sirven para indicadores y propuestas; no cambian automaticamente la compatibilidad, prioridad, perfil ni preferencias.

Configuracion principal:

```powershell
Get-Content config\feedback_learning.yaml
```

Migracion de Fase 6 y estabilizacion 6.1:

```powershell
python -m alembic upgrade head
python -m alembic current
python -m alembic history
```

Para probar downgrade solo en base temporal o con respaldo:

```powershell
python -m alembic downgrade 202607020004
python -m alembic upgrade head
```

Flujo recomendado:

1. Registra decisiones y postulaciones en `Bandeja estrategica`.
2. Registra resultados reales en `Aprendizaje > Resultados`.
3. Ejecuta `Aprendizaje > Analisis` cuando exista muestra suficiente.
4. Revisa evidencia, muestra, confianza y riesgo antes de aprobar una propuesta.
5. Aplica o revierte propuestas de forma manual y versionada.

Notas de Fase 6.1:

- Las postulaciones quedan asociadas al perfil profesional para evitar mezclar metricas entre perfiles.
- Las tasas de respuesta, entrevista y oferta cuentan postulaciones unicas, no cada etapa repetida.
- Las senales implicitas repetidas se deduplican por dia.
- Las propuestas respetan muestra minima, resultados reales minimos, recencia, vencimiento y deduplicacion activa.
- La aplicacion de propuestas sigue siendo supervisada: no modifica automaticamente CV, perfil, pesos ni postulaciones.

## Carpetas de datos

- `data/imports/`: espacio reservado para importaciones.
- `data/temp/`: archivos temporales.
- `data/exports/`: exportaciones locales.

Estas carpetas estan ignoradas por Git salvo `.gitkeep`. No subas datos laborales reales al repositorio.

## Datos de ejemplo

```powershell
Get-Content examples\vacantes_ejemplo.csv
Get-Content examples\vacantes_columnas_alternativas.csv
```

Contienen datos ficticios.

## Ejecutar pruebas

```powershell
python -m pytest
```

Todas las pruebas usan bases temporales y no escriben datos de prueba en `data/radar_laboral.db`.

Las pruebas de volumen locales cubren 100 filas, 1.000 filas y el maximo configurado. Registran tiempo de lectura, validacion, deduplicacion, guardado, registros procesados y errores encontrados. No son benchmarks formales ni imponen umbrales de rendimiento; los benchmarks formales quedan para fases con automatizacion de fuentes, despliegue multiusuario o volumenes mayores.

Las pruebas de compatibilidad usan bases temporales y cubren extraccion de requisitos, restricciones, puntuacion, confianza, cobertura, explicaciones, versionado, persistencia, lote y migraciones.

## Restablecer solo la base local

Haz copia antes de borrar:

```powershell
Copy-Item data\radar_laboral.db data\radar_laboral.backup.db
Remove-Item data\radar_laboral.db
python scripts\initialize_database.py
```

## Limitaciones

- La migracion base de Alembic funciona como baseline del esquema actual. Las migraciones futuras deben ser incrementales y revisadas antes de aplicarse sobre datos reales.
- No hay importacion automatica desde correo ni portales laborales.
- No hay IA, aprendizaje automatico, ranking diario automatizado ni postulaciones automaticas.

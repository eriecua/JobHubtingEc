# Fase 2.1 - Carga Asistida del Perfil Desde CV

## Objetivo

Reducir la carga manual del perfil profesional permitiendo que el usuario cargue un CV y revise datos candidatos antes de guardarlos. La fase debe ayudar a completar el perfil, no reemplazar el juicio del usuario.

## Alcance

Incluido:

- Carga local de `.txt`, `.pdf` con texto seleccionable y `.docx`.
- Extraccion local de texto.
- Borrador estructurado para perfil, experiencia, habilidades, herramientas, formacion, certificaciones, cargos objetivo y evidencias.
- Revision manual con aceptar, editar u omitir.
- Guardado solo con confirmacion humana y usando repositorios existentes.

Excluido:

- OCR de documentos escaneados.
- IA generativa, embeddings o similitud semantica.
- Lectura de correo, scraping, LinkedIn o conexiones externas.
- Generacion, modificacion, envio o postulacion automatica con CV.
- Guardado automatico del archivo original.

## Flujo Propuesto

1. El usuario abre `Mi perfil` y entra a una pestana futura `Importar CV`.
2. Carga un archivo admitido.
3. El sistema valida extension, tamanio maximo configurable y que exista texto extraible.
4. El sistema extrae texto sin guardar el archivo.
5. El sistema crea candidatos con fragmento origen, confianza y advertencias.
6. El usuario revisa por secciones:
   - identidad y resumen
   - experiencias
   - habilidades
   - herramientas
   - formacion
   - certificaciones
   - cargos objetivo
   - evidencias
7. El usuario acepta, edita u omite cada candidato.
8. El sistema valida de nuevo.
9. El sistema guarda solamente los candidatos aceptados o editados.
10. El sistema muestra resumen de guardado y pendientes.

## Componentes Fututos

- `document_reader`: lee `.txt`, `.pdf` y `.docx` localmente.
- `cv_text_extractor`: limpia texto y detecta secciones.
- `cv_profile_mapper`: convierte texto en candidatos del dominio.
- `cv_draft_validator`: aplica reglas de fechas, duplicados, alias y campos requeridos.
- `cv_draft_apply_service`: guarda datos confirmados mediante repositorios.
- `profile_pages`: agrega la revision visual sin escribir directo a SQLite.

## Contrato del Borrador

Cada candidato debe incluir:

- `section`: tipo de informacion.
- `field`: campo destino o tipo de entidad.
- `value`: valor candidato.
- `source_snippet`: fragmento corto del CV.
- `confidence`: `Alta`, `Media` o `Baja`.
- `status`: `Pendiente`, `Aceptado`, `Editado` u `Omitido`.
- `warnings`: lista de problemas comprensibles.

Reglas:

- Los candidatos de baja confianza empiezan como pendientes.
- Las fechas ambiguas no se guardan sin correccion.
- Las habilidades y herramientas usan aliases YAML antes de crear registros.
- Una habilidad no puede asignarse dos veces al mismo perfil.
- Responsabilidades y logros deben mantenerse separados.

## Persistencia

Opcion minima para primera implementacion:

- Mantener el borrador en `st.session_state`.
- Persistir solo registros aceptados/editados.
- No requiere migracion.

Opcion recomendada para trazabilidad:

- Crear con Alembic `profile_import_batches` y `profile_import_candidates`.
- Guardar metadata del lote, candidatos, estados y advertencias.
- No guardar el contenido completo del archivo ni el archivo original por defecto.

Decision recomendada: empezar con la opcion minima si se busca velocidad, y pasar a persistencia cuando se necesite historial de importaciones.

## Pruebas de Aceptacion

- CV vacio o ilegible: debe mostrar error comprensible y no guardar nada.
- CV parcial: debe crear candidatos solo para secciones detectadas.
- CV con experiencia y habilidades: debe separar experiencia, responsabilidades, logros y habilidades.
- CV con fechas ambiguas: debe dejar los candidatos pendientes.
- CV con aliases como `Excel`, `MS Excel` y `Microsoft Excel`: debe proponer una sola habilidad canonica.
- CV con certificaciones sin fecha: debe permitir candidato opcional con advertencia.
- Usuario acepta, edita y omite datos: solo lo aceptado/editado debe persistir.

## Riesgos

- PDFs escaneados necesitaran OCR en una fase futura.
- CVs con formato muy creativo pueden producir secciones incompletas.
- La extraccion deterministica sera conservadora; esto es preferible a inventar datos.
- Si se decide persistir borradores, sera necesaria una migracion Alembic.

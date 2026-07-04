---
name: radar-job-import
description: Crea, valida, importa y depura CSV de vacantes para el Radar Laboral. Úsala con la plantilla de vacantes, fuentes externas, mapeo, normalización o duplicados.
---

# Radar Job Import

## Flujo
1. Usa exactamente los encabezados y el orden de la plantilla.
2. Guarda CSV como UTF-8 con BOM para Excel en Windows.
3. Valida título, empresa, país, fuente, URL e identificador cuando existan.
4. Usa fechas ISO `YYYY-MM-DD`, salarios numéricos y URLs válidas.
5. Cuando falte un dato, déjalo vacío y documenta la limitación en `notes`.
6. No inventes salarios, experiencia, fecha o vigencia.

## Duplicados
1. Fuente + external_id.
2. URL normalizada.
3. Empresa + cargo + ciudad + fecha.
4. Similitud como advertencia, no borrado automático.

## Staging
Muestra filas válidas, inválidas y duplicadas; permite corrección; conserva origen; importa de forma idempotente.

## Pruebas
Plantilla correcta, columna faltante/extra, fecha/salario/URL inválidos, duplicado exacto/probable, comas/saltos, UTF-8 y archivo vacío.

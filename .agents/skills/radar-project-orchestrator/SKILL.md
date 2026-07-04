---
name: radar-project-orchestrator
description: Orquesta fases, funciones grandes y entregas integrales del Radar Laboral. Úsala cuando se solicite completar una fase, varias fases, una función transversal o un plan maestro. No usar para una corrección pequeña y localizada.
---

# Radar Project Orchestrator

## Objetivo
Dirigir trabajos grandes mediante checkpoints verificables, evitando pérdida de contexto y propagación de errores.

## Procedimiento
1. Lee `AGENTS.md` e inspecciona todo el repositorio.
2. Identifica modelos, servicios, repositorios, páginas, configuración, scripts, pruebas y migraciones.
3. Ejecuta pruebas, `python -m alembic current` y `python -m alembic history`.
4. Determina el estado por código y pruebas, no solo por README.
5. Crea o actualiza `MASTER_PLAN.md`, `PROGRESS.md`, `TECHNICAL_DEBT.md` y `TEST_REPORT.md`.
6. Divide el trabajo en entregables con alcance, pruebas, migraciones, criterio de aprobación y riesgos.
7. Antes de cambios importantes, registra pruebas, revisión Alembic y crea respaldo de SQLite.
8. Para cada entregable: implementa, migra, prueba, verifica Streamlit, documenta y crea checkpoint.
9. Continúa solo si no hay fallos críticos.

## Puertas de parada
Detén el avance ante pérdida potencial de datos, migración destructiva no aprobada, pruebas anteriores rotas, credenciales en código, duplicación importante o flujo principal inutilizable.

## Restricciones
- No implementes fases no solicitadas.
- No marques como finalizado algo no ejecutado.
- No reemplaces el motor determinístico por IA opaca.
- No automatices postulaciones externas.

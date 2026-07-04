---
name: radar-cv-ingestion
description: Plan, audit, or implement assisted CV-to-profile ingestion for Radar Laboral. Use when working on CV, resume, curriculum, profile import, document reading from .txt/.pdf/.docx, extraction of profile drafts, or Phase 2.1 design, while keeping the flow local, supervised, deterministic, and free of external services by default.
---

# Radar CV Ingestion

## Core Rule

Treat CV ingestion as an assisted profile-entry workflow, not as automatic profile replacement.
Always create candidate data for human review before saving anything.

## Safety Gates

1. Do not modify the Radar app unless the user explicitly asks to implement Phase 2.1 or another scoped CV-ingestion task.
2. Do not use paid APIs, external AI services, scraping, email connectors, LinkedIn, embeddings, or semantic search by default.
3. Do not store the original CV file unless the user explicitly asks for persistent document storage.
4. Do not invent missing employers, dates, skills, metrics, credentials, salaries, or responsibilities.
5. Do not overwrite existing profile data silently; present additions, updates, conflicts, and omissions separately.
6. Save only through existing repositories and services, never by writing directly to SQLite from UI code.
7. If schema changes are needed, use Alembic and protect the existing SQLite database.

## Workflow

1. Inspect the current profile architecture first: models, repositories, services, Streamlit pages, catalogs, tests, and Alembic head.
2. Separate the work into document reading, text cleanup, deterministic extraction, normalization, validation, review UI, and supervised apply.
3. Use local parsers for supported formats when implementation is requested:
   - `.txt`: plain text decode with clear encoding fallback.
   - `.pdf`: text-selectable PDF only.
   - `.docx`: document text extraction only.
4. Produce a structured draft with source snippets and confidence, not final records.
5. Normalize skills, tools, titles, sectors, and aliases with existing Radar helpers and YAML catalogs.
6. Validate dates, duplicate skills, duplicate tools, required profile fields, evidence metrics, and contradictions before save.
7. Require user confirmation per section or per item before applying changes.
8. After implementation work, run focused tests, full tests, Alembic checks, and import checks.

## Draft Contract

For detailed draft behavior, read `references/phase_2_1_contract.md` before planning or implementing CV ingestion.

Minimum candidate shape:

```text
section: profile | experience | skill | tool | education | certification | target_role | evidence
field: destination field or item type
value: extracted candidate value
source_snippet: short text fragment from the CV
confidence: Alta | Media | Baja
status: Pendiente | Aceptado | Editado | Omitido
notes: validation warnings or user-facing explanation
```

## Acceptance Rules

- Empty optional fields must not block review.
- Ambiguous data must remain pending with a warning.
- Existing profile data must be preserved unless the user confirms an update.
- Duplicate aliases must collapse to the configured canonical skill or tool.
- The final report must state what was extracted, what was not extracted, what needs review, and what was saved.

# Phase 2.1 CV Ingestion Contract

Use this reference when planning, auditing, or implementing assisted CV-to-profile ingestion.

## Boundaries

- Keep extraction local by default.
- Do not persist uploaded CV files by default.
- Do not use OCR in the first implementation.
- Do not use AI, embeddings, semantic similarity, email, scraping, LinkedIn, or automatic applications.
- Do not save extracted values without user confirmation.

## Supported Inputs

- `.txt`: plain text CV.
- `.pdf`: text-selectable PDF only; scanned PDFs must produce a clear unsupported-file message.
- `.docx`: body text extraction.

## Pipeline

1. Read file bytes from Streamlit upload without saving the file.
2. Extract text locally.
3. Split text into candidate sections.
4. Build candidate records with source snippets and confidence.
5. Normalize values with existing catalogs and helpers.
6. Validate with existing repositories/services.
7. Show a review screen with accept, edit, and omit controls.
8. Apply accepted items through repositories only.

## Candidate Sections

- Profile summary and identity.
- Work experience with responsibilities and achievements separated.
- Skills and skill evidence.
- Tools.
- Education.
- Certifications.
- Target roles suggested from titles and summary.

## Conflict Handling

- Existing values: show current value and candidate value side by side.
- Duplicate skills/tools: collapse aliases to canonical names before assignment.
- Ambiguous dates: keep pending and require manual correction.
- Missing required fields: allow draft review but block saving that item.
- Low-confidence values: default to pending, not accepted.

## Future Schema Option

Recommended for traceability: create `profile_import_batches` and `profile_import_candidates` with Alembic.
Minimum alternative: keep drafts in Streamlit session state and only persist accepted profile records.

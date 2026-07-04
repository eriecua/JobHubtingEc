from __future__ import annotations

from pathlib import Path

import pytest
from sqlalchemy import create_engine, func, select
from sqlalchemy.orm import Session

from app.database import create_tables
from app.models import CapturedSourceItem, ImportBatch, ImportStagingJob, JobSource
from app.repositories import JobSourceRepository
from app.services.job_source_capture import JobSourceCaptureService
from app.services import job_source_connectors
from app.services.job_source_connectors import AuthorizedEmailConnector, _SafeRedirectHandler
from app.services.job_source_types import CaptureContext
from app.services.source_security import sanitize_non_sensitive_headers, validate_public_http_url
from app.ui.job_pages import _parse_json_config, _redact_sensitive
from app.services.validation import ValidationError


@pytest.fixture()
def session(tmp_path: Path) -> Session:
    engine = create_engine(f"sqlite:///{(tmp_path / 'phase7.db').as_posix()}", future=True)
    create_tables(engine)
    with Session(engine) as db_session:
        yield db_session


def test_source_repository_create_test_toggle(session: Session) -> None:
    repo = JobSourceRepository(session)

    source = repo.create_source(
        name="Carpeta autorizada",
        source_type="LOCAL_FOLDER",
        configuration={"folder_path": "data/imports"},
    )
    repo.save_test_result(source.id, "Correcta")
    updated = repo.set_active(source.id, False)

    assert updated.is_active is False
    assert session.scalar(select(func.count(JobSource.id))) == 1
    assert updated.last_test_status == "Correcta"


def test_quick_link_stages_once_and_skips_repeated_link(session: Session) -> None:
    service = JobSourceCaptureService(session)

    first_batch = service.capture_quick_link(
        url="https://example.com/jobs/industrial",
        title="Coordinador de Produccion",
        company="Empresa Ejemplo",
        city="Guayaquil",
        notes="Completar requisitos manualmente.",
    )
    second_batch = service.capture_quick_link(
        url="https://example.com/jobs/industrial",
        title="Coordinador de Produccion",
        company="Empresa Ejemplo",
        city="Guayaquil",
        notes="Completar requisitos manualmente.",
    )

    first = session.get(ImportBatch, first_batch)
    second = session.get(ImportBatch, second_batch)
    assert first is not None and first.total_rows == 1
    assert second is not None and second.total_rows == 0
    assert session.scalar(select(func.count(ImportStagingJob.id))) == 1
    assert session.scalar(select(func.count(CapturedSourceItem.id))) == 2


def test_local_folder_connector_reads_json_into_staging(session: Session, tmp_path: Path) -> None:
    folder = Path("data/temp/phase7_test_single")
    absolute_folder = Path.cwd() / folder
    absolute_folder.mkdir(parents=True, exist_ok=True)
    file_path = absolute_folder / "jobs.json"
    file_path.write_text(
        """
[
  {
    "title": "Analista de Procesos",
    "company": "Empresa Local",
    "source": "Carpeta Local",
    "description": "Mejora continua y documentacion de procesos.",
    "source_url": "https://example.com/jobs/procesos",
    "external_id": "local-1"
  }
]
""",
        encoding="utf-8",
    )
    repo = JobSourceRepository(session)
    source = repo.create_source(
        name="Carpeta Local",
        source_type="LOCAL_FOLDER",
        configuration={"folder_path": folder.as_posix()},
    )

    batch_id = JobSourceCaptureService(session).capture_source(source.id)

    batch = session.get(ImportBatch, batch_id)
    assert batch is not None
    assert batch.total_rows == 1
    assert session.scalar(select(func.count(ImportStagingJob.id))) == 1
    file_path.unlink()
    absolute_folder.rmdir()


def test_local_folder_skips_same_file_and_allows_manual_reprocess(session: Session) -> None:
    folder = Path("data/temp/phase7_test_reprocess")
    absolute_folder = Path.cwd() / folder
    absolute_folder.mkdir(parents=True, exist_ok=True)
    file_path = absolute_folder / "jobs.json"
    file_path.write_text(
        """
[
  {
    "title": "Planificador de Produccion",
    "company": "Empresa Reproceso",
    "source": "Carpeta Reproceso",
    "description": "Planificacion y seguimiento de produccion.",
    "source_url": "https://example.com/jobs/planificador",
    "external_id": "reprocess-1"
  }
]
""",
        encoding="utf-8",
    )
    repo = JobSourceRepository(session)
    source = repo.create_source(
        name="Carpeta Reproceso",
        source_type="LOCAL_FOLDER",
        configuration={"folder_path": folder.as_posix()},
    )
    service = JobSourceCaptureService(session)

    first_batch_id = service.capture_source(source.id)
    second_batch_id = service.capture_source(source.id)
    repo.update_source(source.id, configuration={"folder_path": folder.as_posix(), "allow_reprocess": True})
    third_batch_id = service.capture_source(source.id)

    first = session.get(ImportBatch, first_batch_id)
    second = session.get(ImportBatch, second_batch_id)
    third = session.get(ImportBatch, third_batch_id)
    assert first is not None and first.total_rows == 1
    assert second is not None and second.total_rows == 0
    assert third is not None and third.total_rows == 1
    assert session.scalar(select(func.count(ImportStagingJob.id))) == 2
    file_path.unlink()
    absolute_folder.rmdir()


def test_uploaded_eml_extracts_job_like_message(session: Session) -> None:
    content = b"""From: alertas@example.com
Subject: Nueva vacante de Supervisor de Operaciones
Date: Fri, 03 Jul 2026 10:00:00 -0500
Content-Type: text/plain; charset=utf-8

Tenemos una oferta laboral para Supervisor de Operaciones.
Ver detalle en https://example.com/jobs/supervisor-operaciones
"""

    batch_id = JobSourceCaptureService(session).capture_uploaded_eml(
        filename="alerta.eml",
        content=content,
        source_name="Alerta EML",
    )

    row = session.scalar(select(ImportStagingJob).where(ImportStagingJob.import_batch_id == batch_id))
    assert row is not None
    assert row.raw_data["source"] == "Alerta EML"
    assert "Supervisor de Operaciones" in row.raw_data["title"]


def test_private_and_local_urls_are_blocked() -> None:
    with pytest.raises(ValidationError):
        validate_public_http_url("http://127.0.0.1:8000/jobs")
    with pytest.raises(ValidationError):
        validate_public_http_url("http://localhost/jobs")


def test_redirect_to_private_url_is_blocked_before_following() -> None:
    handler = _SafeRedirectHandler("https://example.com/jobs")
    request = job_source_connectors.urllib.request.Request("https://example.com/jobs")

    with pytest.raises(ValidationError):
        handler.redirect_request(request, None, 302, "Found", {}, "http://127.0.0.1/private")


def test_nested_sensitive_source_config_is_rejected_and_redacted() -> None:
    with pytest.raises(ValidationError):
        _parse_json_config('{"base_url": "https://example.com/jobs", "headers": {"x-api-key": "abc"}}')
    with pytest.raises(ValidationError):
        sanitize_non_sensitive_headers({"Authorization": "Bearer abc"})

    redacted = _redact_sensitive({"headers": {"x-api-key": "abc"}, "params": {"q": "industrial"}})
    assert redacted["headers"]["x-api-key"] == "***"
    assert redacted["params"]["q"] == "industrial"


def test_source_repository_rejects_sensitive_nested_configuration(session: Session) -> None:
    repo = JobSourceRepository(session)

    with pytest.raises(ValidationError):
        repo.create_source(
            name="API con secreto",
            source_type="PUBLIC_JSON_API",
            configuration={
                "base_url": "https://example.com/jobs.json",
                "headers": {"Authorization": "Bearer abc"},
            },
        )


def test_rss_connector_stages_feed_items(session: Session, monkeypatch: pytest.MonkeyPatch) -> None:
    feed = b"""<?xml version="1.0" encoding="UTF-8"?>
<rss version="2.0">
  <channel>
    <item>
      <title>Analista de Mejora Continua</title>
      <description>Lean Manufacturing e indicadores.</description>
      <link>https://example.com/jobs/mejora-continua</link>
      <guid>rss-1</guid>
      <pubDate>Fri, 03 Jul 2026 10:00:00 -0500</pubDate>
    </item>
  </channel>
</rss>
"""

    def fake_fetch(url: str, context: CaptureContext, headers: dict[str, str] | None = None) -> tuple[bytes, str]:
        return feed, url

    monkeypatch.setattr(job_source_connectors, "_fetch_url", fake_fetch)
    source = JobSourceRepository(session).create_source(
        name="Feed autorizado",
        source_type="RSS_ATOM",
        configuration={"url": "https://example.com/feed.xml"},
    )

    batch_id = JobSourceCaptureService(session).capture_source(source.id)

    row = session.scalar(select(ImportStagingJob).where(ImportStagingJob.import_batch_id == batch_id))
    assert row is not None
    assert row.parsed_data["title"] == "Analista de Mejora Continua"
    assert row.parsed_data["publication_date"] == "2026-07-03"


def test_public_json_api_connector_stages_mapped_items(session: Session, monkeypatch: pytest.MonkeyPatch) -> None:
    payload = b"""
{
  "items": [
    {
      "id": "api-1",
      "position": "Supervisor de Produccion",
      "organization": "Empresa API",
      "body": "Gestion de personal operativo y productividad.",
      "url": "https://example.com/jobs/api-1"
    }
  ]
}
"""

    def fake_fetch(url: str, context: CaptureContext, headers: dict[str, str] | None = None) -> tuple[bytes, str]:
        assert headers == {"Accept": "application/json"}
        return payload, url

    monkeypatch.setattr(job_source_connectors, "_fetch_url", fake_fetch)
    source = JobSourceRepository(session).create_source(
        name="API publica",
        source_type="PUBLIC_JSON_API",
        configuration={
            "base_url": "https://example.com/jobs.json",
            "headers": {"Accept": "application/json"},
            "items_path": "items",
            "field_mapping": {
                "id": "external_id",
                "position": "title",
                "organization": "company",
                "body": "description",
                "url": "source_url",
            },
        },
    )

    batch_id = JobSourceCaptureService(session).capture_source(source.id)

    row = session.scalar(select(ImportStagingJob).where(ImportStagingJob.import_batch_id == batch_id))
    assert row is not None
    assert row.parsed_data["title"] == "Supervisor de Produccion"
    assert row.parsed_data["source"] == "API publica"


def test_authorized_email_connector_is_disabled_by_default() -> None:
    connector = AuthorizedEmailConnector()
    result = connector.test_connection(
        CaptureContext(
            source_id=None,
            source_name="Correo",
            source_type="AUTHORIZED_EMAIL",
            configuration={},
        )
    )

    assert result.ok is False
    with pytest.raises(ValidationError):
        connector.capture(
            CaptureContext(
                source_id=None,
                source_name="Correo",
                source_type="AUTHORIZED_EMAIL",
                configuration={},
            )
        )

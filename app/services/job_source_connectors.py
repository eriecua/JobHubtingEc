"""Authorized Phase 7 source connectors."""

from __future__ import annotations

import csv
from email import policy
from email.parser import BytesParser
from email.utils import parsedate_to_datetime
from html.parser import HTMLParser
from io import StringIO
import hashlib
import json
from pathlib import Path
import re
import urllib.error
import urllib.parse
import urllib.request
import xml.etree.ElementTree as ET
from typing import Any

from app.config import PROJECT_ROOT, load_yaml_file
from app.services.job_source_types import (
    CaptureContext,
    CapturedJobRecord,
    CaptureResult,
    ConnectionTestResult,
    ConnectorCapabilities,
)
from app.services.source_security import validate_public_http_url, validate_redirect_target
from app.services.source_security import sanitize_non_sensitive_headers
from app.services.validation import ValidationError


class _TextExtractor(HTMLParser):
    """Small HTML text and link extractor that never executes content."""

    def __init__(self) -> None:
        super().__init__()
        self.skip_depth = 0
        self.text_parts: list[str] = []
        self.links: list[str] = []

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        if tag in {"script", "style"}:
            self.skip_depth += 1
            return
        if tag == "a":
            for name, value in attrs:
                if name == "href" and value:
                    self.links.append(value)

    def handle_endtag(self, tag: str) -> None:
        if tag in {"script", "style"} and self.skip_depth:
            self.skip_depth -= 1

    def handle_data(self, data: str) -> None:
        if not self.skip_depth and data.strip():
            self.text_parts.append(data.strip())

    @property
    def text(self) -> str:
        return "\n".join(self.text_parts)


class LocalFolderConnector:
    """Read authorized local folder files when the user presses capture."""

    def get_capabilities(self) -> ConnectorCapabilities:
        return ConnectorCapabilities("LOCAL_FOLDER", True, True, notes="Lee CSV, JSON y EML locales.")

    def test_connection(self, context: CaptureContext) -> ConnectionTestResult:
        folder = _safe_relative_path(context.configuration.get("folder_path"))
        if not folder.exists() or not folder.is_dir():
            return ConnectionTestResult(False, "La carpeta no existe o no es una carpeta valida.")
        return ConnectionTestResult(True, "Carpeta disponible para captura manual.")

    def capture(self, context: CaptureContext) -> CaptureResult:
        folder = _safe_relative_path(context.configuration.get("folder_path"))
        allowed = {".csv", ".json", ".eml"}
        records: list[CapturedJobRecord] = []
        errors: list[str] = []
        allow_reprocess = bool(context.configuration.get("allow_reprocess", False))
        for path in sorted(folder.iterdir()):
            if len(records) >= context.max_records:
                break
            if path.suffix.lower() not in allowed or not path.is_file():
                continue
            try:
                content = path.read_bytes()
                if len(content) > context.max_response_bytes:
                    errors.append(f"{path.name}: supera el tamano maximo.")
                    continue
                records.extend(
                    _records_from_file(
                        path.name,
                        content,
                        context.source_name,
                        path.as_posix(),
                        allow_reprocess=allow_reprocess,
                    )
                )
            except Exception as exc:
                errors.append(f"{path.name}: {exc}")
        return CaptureResult(records=records[: context.max_records], errors=errors)


class EMLFileConnector:
    """Parse a single uploaded or configured EML file."""

    def get_capabilities(self) -> ConnectorCapabilities:
        return ConnectorCapabilities("EML_FILE", True, True, notes="Extrae texto, HTML sanitizado, enlaces y adjuntos CSV.")

    def test_connection(self, context: CaptureContext) -> ConnectionTestResult:
        file_path = context.configuration.get("file_path")
        if not file_path:
            return ConnectionTestResult(True, "El archivo EML puede cargarse desde la interfaz.")
        path = _safe_relative_path(file_path)
        return ConnectionTestResult(path.exists() and path.suffix.lower() == ".eml", "Archivo EML revisado.")

    def capture(self, context: CaptureContext) -> CaptureResult:
        content = context.configuration.get("content_bytes")
        filename = context.configuration.get("filename") or "correo.eml"
        if content is None:
            path = _safe_relative_path(context.configuration.get("file_path"))
            content = path.read_bytes()
            filename = path.name
        if isinstance(content, str):
            content = content.encode("utf-8")
        return CaptureResult(records=_records_from_eml(filename, content, context.source_name))


class RSSAtomConnector:
    """Capture authorized RSS or Atom feed items."""

    def get_capabilities(self) -> ConnectorCapabilities:
        return ConnectorCapabilities("RSS_ATOM", True, True)

    def test_connection(self, context: CaptureContext) -> ConnectionTestResult:
        url = validate_public_http_url(str(context.configuration.get("url") or ""))
        content, final_url = _fetch_url(url, context)
        validate_redirect_target(url, final_url)
        try:
            ET.fromstring(content)
        except ET.ParseError as exc:
            return ConnectionTestResult(False, f"Feed invalido: {exc}")
        return ConnectionTestResult(True, "Feed valido.")

    def capture(self, context: CaptureContext) -> CaptureResult:
        url = validate_public_http_url(str(context.configuration.get("url") or ""))
        content, final_url = _fetch_url(url, context)
        validate_redirect_target(url, final_url)
        root = ET.fromstring(content)
        records = _feed_records(root, context.source_name, final_url, context.max_records)
        return CaptureResult(records=records)


class PublicJSONAPIConnector:
    """Capture records from a public authorized JSON GET endpoint."""

    def get_capabilities(self) -> ConnectorCapabilities:
        return ConnectorCapabilities("PUBLIC_JSON_API", True, True)

    def test_connection(self, context: CaptureContext) -> ConnectionTestResult:
        self._build_url(context, page=1)
        sanitize_non_sensitive_headers(context.configuration.get("headers") or {})
        return ConnectionTestResult(True, "Configuracion de API valida para GET.")

    def capture(self, context: CaptureContext) -> CaptureResult:
        records: list[CapturedJobRecord] = []
        errors: list[str] = []
        pages = min(int(context.configuration.get("max_pages") or context.max_pages), context.max_pages)
        for page in range(1, pages + 1):
            if len(records) >= context.max_records:
                break
            url = self._build_url(context, page)
            try:
                content, final_url = _fetch_url(url, context, headers=context.configuration.get("headers") or {})
                validate_redirect_target(url, final_url)
                payload = json.loads(content.decode("utf-8"))
                items = _extract_path(payload, context.configuration.get("items_path") or "")
                if not isinstance(items, list):
                    raise ValidationError("La ruta de elementos no devuelve una lista.")
                for item in items:
                    if len(records) >= context.max_records:
                        break
                    if isinstance(item, dict):
                        records.append(_record_from_json_item(item, context.configuration.get("field_mapping") or {}, context.source_name))
            except Exception as exc:
                errors.append(str(exc))
                break
        return CaptureResult(records=records, errors=errors)

    def _build_url(self, context: CaptureContext, page: int) -> str:
        base_url = validate_public_http_url(str(context.configuration.get("base_url") or ""))
        params = dict(context.configuration.get("params") or {})
        page_param = context.configuration.get("page_param")
        if page_param:
            params[str(page_param)] = str(page)
        query = urllib.parse.urlencode(params)
        separator = "&" if urllib.parse.urlparse(base_url).query else "?"
        return f"{base_url}{separator}{query}" if query else base_url


class AuthorizedEmailConnector:
    """Disabled structural connector for future authorized email access."""

    def get_capabilities(self) -> ConnectorCapabilities:
        return ConnectorCapabilities(
            "AUTHORIZED_EMAIL",
            True,
            False,
            requires_credentials=True,
            enabled_by_default=False,
            notes="Preparado pero desactivado; requiere credenciales por variables de entorno.",
        )

    def test_connection(self, context: CaptureContext) -> ConnectionTestResult:
        return ConnectionTestResult(False, "Correo autorizado desactivado. Configura credenciales y habilitacion explicita en una fase futura.")

    def capture(self, context: CaptureContext) -> CaptureResult:
        raise ValidationError("El conector de correo autorizado esta desactivado por defecto.")


def connector_for(source_type: str):
    """Return a connector for a configured source type."""

    connectors = {
        "LOCAL_FOLDER": LocalFolderConnector(),
        "EML_FILE": EMLFileConnector(),
        "RSS_ATOM": RSSAtomConnector(),
        "PUBLIC_JSON_API": PublicJSONAPIConnector(),
        "AUTHORIZED_EMAIL": AuthorizedEmailConnector(),
    }
    if source_type not in connectors:
        raise ValidationError("Tipo de fuente no soportado por conectores de captura.")
    return connectors[source_type]


def quick_link_record(url: str, source_name: str, **data: Any) -> CapturedJobRecord:
    """Build a manual quick-link record without scraping the URL."""

    normalized_url = validate_public_http_url(url)
    title = str(data.get("title") or "Cargo por completar").strip()
    company = str(data.get("company") or "Empresa por completar").strip()
    city = str(data.get("city") or "").strip()
    notes = str(data.get("notes") or "").strip()
    description = notes or f"Enlace capturado manualmente para completar: {normalized_url}"
    raw = {
        "title": title,
        "company": company,
        "city": city,
        "source": source_name,
        "source_url": normalized_url,
        "external_id": normalized_url,
        "description": description,
        "notes": notes,
    }
    return CapturedJobRecord(raw=raw, raw_content=description, external_id=normalized_url, source_uri=normalized_url)


def _safe_relative_path(raw_path: Any) -> Path:
    path_text = str(raw_path or "").strip()
    if not path_text:
        raise ValidationError("Configura una ruta relativa dentro del proyecto.")
    path = Path(path_text)
    if path.is_absolute():
        raise ValidationError("No se permiten rutas absolutas en la configuracion.")
    resolved = (PROJECT_ROOT / path).resolve()
    if not str(resolved).startswith(str(PROJECT_ROOT.resolve())):
        raise ValidationError("La ruta debe estar dentro del proyecto.")
    return resolved


def _records_from_file(
    filename: str,
    content: bytes,
    source_name: str,
    uri: str | None = None,
    *,
    allow_reprocess: bool = False,
) -> list[CapturedJobRecord]:
    suffix = Path(filename).suffix.lower()
    file_hash = hashlib.sha256(content).hexdigest()
    if suffix == ".csv":
        text = _decode_text(content)
        rows = list(csv.DictReader(StringIO(text)))
        return [
            CapturedJobRecord(
                raw={
                    **row,
                    "source": row.get("source") or source_name,
                    "_file_hash": file_hash,
                    "_allow_reprocess": allow_reprocess,
                },
                raw_content=text,
                filename=filename,
                source_uri=uri,
            )
            for row in rows
        ]
    if suffix == ".json":
        payload = json.loads(_decode_text(content))
        items = payload if isinstance(payload, list) else payload.get("items", []) if isinstance(payload, dict) else []
        records: list[CapturedJobRecord] = []
        for item in items:
            if isinstance(item, dict):
                raw_item = dict(item)
                raw_item["_file_hash"] = file_hash
                raw_item["_allow_reprocess"] = allow_reprocess
                records.append(_record_from_json_item(raw_item, {}, source_name, filename=filename, raw_content=json.dumps(item, ensure_ascii=False)))
        return records
    if suffix == ".eml":
        records = _records_from_eml(filename, content, source_name)
        for record in records:
            record.raw["_file_hash"] = file_hash
            record.raw["_allow_reprocess"] = allow_reprocess
        return records
    return []


def _records_from_eml(filename: str, content: bytes, source_name: str) -> list[CapturedJobRecord]:
    message = BytesParser(policy=policy.default).parsebytes(content)
    sender = str(message.get("from") or "")
    subject = str(message.get("subject") or "")
    date_header = str(message.get("date") or "")
    text_parts: list[str] = []
    links: list[str] = []
    attachment_records: list[CapturedJobRecord] = []
    for part in message.walk():
        content_type = part.get_content_type()
        disposition = part.get_content_disposition()
        if disposition == "attachment" and (part.get_filename() or "").lower().endswith(".csv"):
            payload = part.get_payload(decode=True) or b""
            attachment_records.extend(_records_from_file(part.get_filename() or "adjunto.csv", payload, source_name))
            continue
        if content_type == "text/plain" and disposition != "attachment":
            text_parts.append(str(part.get_content()))
        elif content_type == "text/html" and disposition != "attachment":
            extractor = _TextExtractor()
            extractor.feed(str(part.get_content()))
            text_parts.append(extractor.text)
            links.extend(extractor.links)
    text = "\n".join(part for part in text_parts if part).strip()
    links.extend(re.findall(r"https?://[^\s)>\"]+", text))
    classification = _classify_email(subject, text)
    records = list(attachment_records)
    if classification in {"alerta_laboral", "oferta_individual", "resumen_vacantes"} and text:
        records.append(
            CapturedJobRecord(
                raw={
                    "title": subject or "Oferta por revisar",
                    "company": sender or "Empresa por completar",
                    "source": source_name,
                    "description": text,
                    "source_url": links[0] if links else None,
                    "external_id": f"{sender}|{subject}|{date_header}",
                    "notes": f"Correo clasificado como {classification}.",
                },
                raw_content=text,
                external_id=f"{sender}|{subject}|{date_header}",
                source_uri=links[0] if links else None,
                filename=filename,
                warnings=[] if links else ["No se detectaron enlaces en el correo."],
            )
        )
    return records


def _classify_email(subject: str, text: str) -> str:
    key = f"{subject}\n{text}".lower()
    if any(word in key for word in ["vacante", "empleo", "oferta laboral", "postula", "job alert"]):
        if any(word in key for word in ["resumen", "alerta", "nuevas vacantes"]):
            return "resumen_vacantes"
        return "oferta_individual"
    return "irrelevante"


def _feed_records(root: ET.Element, source_name: str, feed_url: str, max_records: int) -> list[CapturedJobRecord]:
    records: list[CapturedJobRecord] = []
    channel_items = root.findall(".//item")
    atom_items = root.findall(".//{http://www.w3.org/2005/Atom}entry")
    for item in [*channel_items, *atom_items][:max_records]:
        title = _xml_text(item, "title") or _xml_text(item, "{http://www.w3.org/2005/Atom}title")
        description = _xml_text(item, "description") or _xml_text(item, "summary") or _xml_text(item, "{http://www.w3.org/2005/Atom}summary")
        link = _xml_text(item, "link") or _atom_link(item)
        guid = _xml_text(item, "guid") or _xml_text(item, "id") or link
        published = (
            _normalize_feed_date(_xml_text(item, "pubDate"))
            or _normalize_feed_date(_xml_text(item, "published"))
            or _normalize_feed_date(_xml_text(item, "updated"))
            or _normalize_feed_date(_xml_text(item, "{http://www.w3.org/2005/Atom}published"))
            or _normalize_feed_date(_xml_text(item, "{http://www.w3.org/2005/Atom}updated"))
        )
        raw = {
            "title": title or "Oferta por revisar",
            "company": source_name,
            "source": source_name,
            "source_url": link,
            "external_id": guid,
            "description": description or title or "Descripcion por completar.",
        }
        if published:
            raw["publication_date"] = published
        records.append(CapturedJobRecord(raw=raw, raw_content=ET.tostring(item, encoding="unicode"), external_id=guid, source_uri=link or feed_url))
    return records


def _record_from_json_item(
    item: dict[str, Any],
    mapping: dict[str, str],
    source_name: str,
    filename: str | None = None,
    raw_content: str | None = None,
) -> CapturedJobRecord:
    raw: dict[str, Any] = {"source": source_name}
    if mapping:
        for source_field, target_field in mapping.items():
            raw[target_field] = item.get(source_field)
    else:
        raw.update(item)
        raw["source"] = raw.get("source") or source_name
    raw_content = raw_content or json.dumps(item, ensure_ascii=False, default=str)
    return CapturedJobRecord(
        raw=raw,
        raw_content=raw_content,
        external_id=str(raw.get("external_id") or raw.get("id") or raw.get("source_url") or ""),
        source_uri=raw.get("source_url"),
        filename=filename,
    )


def _fetch_url(url: str, context: CaptureContext, headers: dict[str, str] | None = None) -> tuple[bytes, str]:
    request_headers = sanitize_non_sensitive_headers(headers)
    request = urllib.request.Request(url, headers=request_headers, method="GET")
    opener = urllib.request.build_opener(_SafeRedirectHandler(url))
    try:
        with opener.open(request, timeout=context.timeout_seconds) as response:
            final_url = response.geturl()
            data = response.read(context.max_response_bytes + 1)
    except urllib.error.URLError as exc:
        raise ValidationError(f"No se pudo descargar la fuente: {exc}") from exc
    if len(data) > context.max_response_bytes:
        raise ValidationError("La respuesta supera el tamano maximo permitido.")
    return data, final_url


class _SafeRedirectHandler(urllib.request.HTTPRedirectHandler):
    """Validate every redirect target before the client follows it."""

    def __init__(self, original_url: str) -> None:
        self.original_url = original_url

    def redirect_request(self, req, fp, code, msg, headers, newurl):  # type: ignore[override]
        current_url = getattr(req, "full_url", self.original_url)
        target_url = urllib.parse.urljoin(current_url, newurl)
        validate_redirect_target(current_url, target_url)
        return super().redirect_request(req, fp, code, msg, headers, target_url)


def _extract_path(payload: Any, path: str) -> Any:
    current = payload
    if not path:
        return current
    for part in str(path).split("."):
        if isinstance(current, dict):
            current = current.get(part)
        else:
            return None
    return current


def _xml_text(item: ET.Element, tag: str) -> str | None:
    node = item.find(tag)
    if node is None:
        return None
    return (node.text or "").strip() or None


def _atom_link(item: ET.Element) -> str | None:
    for node in item.findall("{http://www.w3.org/2005/Atom}link"):
        href = node.attrib.get("href")
        if href:
            return href
    return None


def _normalize_feed_date(value: str | None) -> str | None:
    if not value:
        return None
    try:
        parsed = parsedate_to_datetime(value)
        return parsed.date().isoformat()
    except (TypeError, ValueError):
        pass
    text = value.strip()
    if re.match(r"^\d{4}-\d{2}-\d{2}", text):
        return text[:10]
    return None


def _decode_text(content: bytes) -> str:
    for encoding in ("utf-8-sig", "utf-8", "latin-1"):
        try:
            return content.decode(encoding)
        except UnicodeDecodeError:
            continue
    raise ValidationError("No se pudo decodificar el archivo.")

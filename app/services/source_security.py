"""Security helpers for authorized remote source capture."""

from __future__ import annotations

import ipaddress
import socket
from typing import Any
from urllib.parse import urlparse

from app.services.validation import ValidationError

SENSITIVE_KEY_MARKERS = (
    "token",
    "password",
    "secret",
    "authorization",
    "api_key",
    "apikey",
    "x-api-key",
    "credential",
)


def validate_public_http_url(url: str) -> str:
    """Validate URL scheme and block localhost/private networks."""

    parsed = urlparse((url or "").strip())
    if parsed.scheme not in {"http", "https"} or not parsed.netloc:
        raise ValidationError("La URL debe usar http o https y tener dominio.")
    host = parsed.hostname
    if not host:
        raise ValidationError("La URL debe tener un host valido.")
    normalized_host = host.lower()
    if normalized_host in {"localhost", "localhost.localdomain"}:
        raise ValidationError("No se permiten URLs locales.")
    try:
        addresses = [ipaddress.ip_address(normalized_host)]
    except ValueError:
        try:
            addresses = [ipaddress.ip_address(item[4][0]) for item in socket.getaddrinfo(normalized_host, None)]
        except socket.gaierror as exc:
            raise ValidationError("No se pudo resolver el dominio de la URL.") from exc
    for address in addresses:
        if address.is_private or address.is_loopback or address.is_link_local or address.is_multicast:
            raise ValidationError("No se permiten URLs a redes privadas, locales o reservadas.")
    return parsed.geturl()


def validate_redirect_target(original_url: str, final_url: str) -> str:
    """Validate that a redirect target is also public HTTP(S)."""

    original_scheme = urlparse(original_url).scheme
    final = validate_public_http_url(final_url)
    if urlparse(final).scheme != original_scheme and original_scheme == "https":
        raise ValidationError("No se permite redireccionar de HTTPS a HTTP.")
    return final


def validate_non_sensitive_config(value: Any, path: str = "configuracion") -> None:
    """Reject credentials or tokens anywhere in a source configuration."""

    if isinstance(value, dict):
        for key, nested in value.items():
            key_text = str(key).lower()
            if any(marker in key_text for marker in SENSITIVE_KEY_MARKERS):
                raise ValidationError("No guardes credenciales, tokens ni claves sensibles en la configuracion.")
            validate_non_sensitive_config(nested, f"{path}.{key}")
    elif isinstance(value, list):
        for index, item in enumerate(value):
            validate_non_sensitive_config(item, f"{path}[{index}]")
    elif isinstance(value, str):
        lowered = value.strip().lower()
        if lowered.startswith(("bearer ", "basic ")):
            raise ValidationError("No guardes credenciales, tokens ni claves sensibles en la configuracion.")


def redact_sensitive_config(value: Any) -> Any:
    """Return a display-safe copy of a configuration object."""

    if isinstance(value, dict):
        redacted: dict[str, Any] = {}
        for key, nested in value.items():
            key_text = str(key).lower()
            if any(marker in key_text for marker in SENSITIVE_KEY_MARKERS):
                redacted[str(key)] = "***"
            else:
                redacted[str(key)] = redact_sensitive_config(nested)
        return redacted
    if isinstance(value, list):
        return [redact_sensitive_config(item) for item in value]
    return value


def sanitize_non_sensitive_headers(headers: Any) -> dict[str, str]:
    """Validate and return HTTP headers that do not contain credentials."""

    if not headers:
        return {}
    if not isinstance(headers, dict):
        raise ValidationError("Los encabezados deben configurarse como objeto JSON.")
    validate_non_sensitive_config(headers, "headers")
    return {str(key): str(value) for key, value in headers.items() if key and value}

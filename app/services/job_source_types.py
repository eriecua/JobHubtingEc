"""Shared Phase 7 connector types."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Protocol


@dataclass(frozen=True)
class ConnectorCapabilities:
    """Connector capability declaration shown to the UI and tests."""

    source_type: str
    supports_test: bool
    supports_capture: bool
    requires_credentials: bool = False
    enabled_by_default: bool = True
    notes: str = ""


@dataclass(frozen=True)
class ConnectionTestResult:
    """Result of a source connection/configuration check."""

    ok: bool
    message: str


@dataclass(frozen=True)
class CaptureContext:
    """Runtime limits and source configuration for one capture."""

    source_id: int | None
    source_name: str
    source_type: str
    configuration: dict[str, Any]
    timeout_seconds: int = 10
    max_response_bytes: int = 1_048_576
    max_records: int = 50
    max_pages: int = 3


@dataclass
class CapturedJobRecord:
    """One raw opportunity captured from an authorized source."""

    raw: dict[str, Any]
    raw_content: str | None = None
    external_id: str | None = None
    source_uri: str | None = None
    filename: str | None = None
    warnings: list[str] = field(default_factory=list)


@dataclass
class CaptureResult:
    """Connector capture result."""

    records: list[CapturedJobRecord] = field(default_factory=list)
    skipped: int = 0
    errors: list[str] = field(default_factory=list)


class JobSourceConnector(Protocol):
    """Common interface for authorized job source connectors."""

    def test_connection(self, context: CaptureContext) -> ConnectionTestResult:
        """Validate source configuration or connectivity."""

    def capture(self, context: CaptureContext) -> CaptureResult:
        """Capture records without importing them as final jobs."""

    def get_capabilities(self) -> ConnectorCapabilities:
        """Return connector capabilities."""

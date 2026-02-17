"""
DataSource protocol definitions for unified power monitoring backends.

Both HomeAssistant and KasaDevice implement these protocols,
allowing cli.py to use them interchangeably without duck-typing.
"""

from typing import Any, Protocol, runtime_checkable


@runtime_checkable
class DataSource(Protocol):
    """Protocol for power monitoring data sources."""

    def validate_connection(self) -> tuple[bool, str | None]: ...
    def get_power_usage(self) -> float | None: ...
    def get_power_trend(self, minutes: int = 5) -> dict[str, Any] | None: ...


@runtime_checkable
class CurrentCapable(Protocol):
    """Protocol for data sources that can also report current amperage."""

    def get_current_amperage(self) -> float | None: ...
    def get_current_trend(self, minutes: int = 5) -> dict[str, Any] | None: ...

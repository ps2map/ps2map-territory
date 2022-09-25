"""Custom types for the app."""

import datetime
import typing

__all__ = [
    'FacilityStatus',
    'Timestamp',
    'ServerInfo',
]

Timestamp = datetime.datetime


class FacilityStatus(typing.NamedTuple):
    """Facility status information."""

    current_faction: int
    last_capture: Timestamp
    last_capture_by: int | None


class ServerInfo(typing.NamedTuple):
    """Server ID and Census API namespace."""

    id: int
    namespace: str

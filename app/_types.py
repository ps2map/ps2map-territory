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

    faction_id: int
    last_secured: Timestamp
    owning_outfit_id: int | None


class ServerInfo(typing.NamedTuple):
    """Server ID and Census API namespace."""

    id: int
    namespace: str

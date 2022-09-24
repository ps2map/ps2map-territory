"""Custom types for the app."""

import datetime
import typing

__all__ = [
    'FacilityStatus',
    'Timestamp',
]

Timestamp = datetime.datetime


class FacilityStatus(typing.NamedTuple):
    """Facility status information."""

    current_faction: int
    last_capture: Timestamp
    last_capture_by: int | None

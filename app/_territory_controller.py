"""Zone-specific territory controllers."""

import datetime
import logging

from ._messaging import MessagingComponent
from ._types import FacilityStatus, Timestamp

_log = logging.getLogger('app')


class TerritoryController(MessagingComponent):
    """Territory controller for a given zone and server."""

    def __init__(self, server_id: int, zone_id: int) -> None:
        self._server_id = server_id
        self._zone_id = zone_id
        self._ownership: dict[int, tuple[int, Timestamp]] = {}
        self._outfits: dict[int, int] = {}

    @property
    def map_status(self) -> tuple[int, int, dict[int, FacilityStatus]]:
        """Return the current map status for this territory."""
        status: dict[int, FacilityStatus] = {}
        for facility, (faction, last_captured) in self._ownership.items():
            outfit = self._outfits.get(facility)
            status[facility] = FacilityStatus(faction, last_captured, outfit)
        return self._server_id, self._zone_id, status

    def update_ownership(self, facilities: dict[int, int]) -> int:
        """Update the ownership of all tracked facilities.

        This method will first filter out any changes between the given
        facility owners and the current owners. Any changes will be
        updated as captured at the current time, with no outfit.
        """
        now = datetime.datetime.utcnow()

        if not self._ownership:
            _log.info('initialising map for zone %d on server %d',
                      self._zone_id, self._server_id)
            self._ownership = {k: (v, now) for k, v in facilities.items()}
            return len(self._ownership)

        changes = dict(self._facility_items() - facilities.items())
        if changes:
            for facility_id, faction_id in changes.items():
                self._ownership[facility_id] = (faction_id, now)
                self._outfits.pop(facility_id, None)
            _log.info('updated %d facilities in zone %d on server %d',
                      len(changes), self._zone_id, self._server_id)

        return len(changes)

    def _facility_items(self) -> set[tuple[int, int]]:
        """Return a set of facilites to owning factions."""
        return {(k, v) for k, (v, _) in self._ownership.items()}

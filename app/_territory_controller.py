"""Zone-specific territory controllers."""

import datetime
import logging

from ._messaging import MessagingComponent
from ._types import FacilityStatus, Timestamp

__all__ = [
    'TerritoryController',
]


class TerritoryController(MessagingComponent):
    """Territory controller for a given zone and server."""

    def __init__(self, server_id: int, zone_id: int) -> None:
        super().__init__()
        self._log = logging.getLogger(
            f'app.server_{server_id}.territory_zone_{zone_id}')

        self._server_id = server_id
        self._zone_id = zone_id
        self._ownership: dict[int, tuple[int, Timestamp]] = {}
        self._outfits: dict[int, int] = {}

    @property
    def server_id(self) -> int:
        """Return the server ID of the instance."""
        return self._server_id

    @property
    def zone_id(self) -> int:
        """Return the zone ID of the instance."""
        return self._zone_id

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
        now = datetime.datetime.now(datetime.UTC)

        if not self._ownership:
            self._log.info('initialising map for zone')
            self._ownership = {k: (v, now) for k, v in facilities.items()}
            return len(self._ownership)

        changes = dict(facilities.items() - self._facility_items())
        if changes:
            for facility_id, faction_id in changes.items():
                self._ownership[facility_id] = (faction_id, now)
                self._outfits.pop(facility_id, None)
            self._log.info('updated ownership of %d facilities', len(changes))

        return len(changes)

    def _facility_items(self) -> set[tuple[int, int]]:
        """Return a set of facilites to owning factions."""
        return {(k, v) for k, (v, _) in self._ownership.items()}

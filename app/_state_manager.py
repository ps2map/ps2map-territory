"""Global state manager and event dispatcher."""

import logging

from ._messaging import MessagingComponent
from ._territory_controller import TerritoryController
from ._types import FacilityStatus

__all__ = [
    'StateManager',
]

_log = logging.getLogger('app')


class StateManager(MessagingComponent):
    """Main state manager for the territory monitoring application.

    This keeps track of all servers' zones and maintains territory
    controllers for each.
    """

    def __init__(self) -> None:
        super().__init__()
        self._territory: dict[tuple[int, int], TerritoryController] = {}

    def handle_map_poll(
            self, payload: tuple[int, int, dict[int, int]]) -> None:
        server_id, zone_id, facilities = payload
        controller = self._get_controller(server_id, zone_id)

        count = controller.update_ownership(facilities)
        if count > 0:
            self.emit('map_update', controller.map_status)

    def handle_map_update(
            self, payload: tuple[int, int, int, FacilityStatus]) -> None:
        server_id, zone_id, base_id, status = payload
        controller = self._get_controller(server_id, zone_id)

        # Ensure the correct controller has been retrieved
        if server_id != controller.server_id or zone_id != controller.zone_id:
            _log.warning('received map update for mismatched controller '
                         '(%d, %d) != (%d, %d)', server_id, zone_id,
                         controller.server_id, controller.zone_id)
            return

        # Check if the facility owner has changed (or if it was just resecured)
        old_status = controller.map_status[2].get(base_id)
        if old_status is not None:
            if old_status.faction_id == status.faction_id:
                _log.info('facility %d on zone %d on server %d was resecured '
                          'by faction %d',
                          base_id, zone_id, server_id, status.faction_id)
                # NOTE: If we start tracking time-since-resecure for potential
                # capture windows, this is where we'd do that.
                return
        else:
            _log.warning('facility %d not found on zone %d on server %d',
                         base_id, zone_id, server_id)

        # Ownership has changed OR this is the first time we've seen this base
        _log.info('facility %d on zone %d on server %d was captured by '
                  'faction %d',
                  base_id, zone_id, server_id, status.faction_id)
        if controller.update_ownership({base_id: status.faction_id}):
            self.emit('map_update', controller.map_status)

    def _get_controller(
            self, server_id: int, zone_id: int) -> TerritoryController:
        """Get the territory controller for a given server and zone ID.

        If no controller exists for the given server and zone, a new
        instance will be spun up and returned.
        """
        key = server_id, zone_id
        if key not in self._territory:
            _log.info('Creating new territory controller for zone %d on '
                      'server %d', zone_id, server_id)
            self._territory[key] = TerritoryController(server_id, zone_id)
        return self._territory[key]

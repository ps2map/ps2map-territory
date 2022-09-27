"""Global state manager and event dispatcher."""

import logging

from ._messaging import MessagingComponent
from ._territory_controller import TerritoryController

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

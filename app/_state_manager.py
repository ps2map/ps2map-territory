
import logging
from ._messaging import MessagingComponent

_log = logging.getLogger('app')


class ZoneController:
    """Dummy, to be moved to a separate module."""

    def __init__(self, server_id: int, zone_id: int) -> None:
        self._server_id = server_id
        self._zone_id = zone_id

    def update_facilities(self, facilities: dict[int, int]) -> int:
        # TODO: Filter out facilities that are have not changed
        print(f'Zone {self._zone_id} on server {self._server_id} updated')
        return 0


class StateManager(MessagingComponent):

    def __init__(self) -> None:
        super().__init__()
        self._zone_controllers: dict[tuple[int, int], ZoneController] = {}

    def handle_map_poll(
            self, payload: tuple[int, int, dict[int, int]]) -> None:
        server_id, zone_id, facilities = payload
        controller = self._get_zone_controller(server_id, zone_id)
        count = controller.update_facilities(facilities)
        if count > 0:
            _log.info('updated %d facilities for zone %d on server %d',
                      count, zone_id, server_id)

    def _get_zone_controller(
            self, server_id: int, zone_id: int) -> ZoneController:
        """Get the zone controller for a given server and zone ID.

        If no controller exists for the given server and zone, a new
        instance will be spun up and returned.
        """
        key = server_id, zone_id
        if key not in self._zone_controllers:
            self._zone_controllers[key] = ZoneController(server_id, zone_id)
        return self._zone_controllers[key]

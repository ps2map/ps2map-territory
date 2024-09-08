"""Real-time event listener for the WebSocket API endpoint.

This component listens to `FacilityControl` and `PlayerFacilityCapture`
events on the ESS WebSocket and emits them as `map_update` messages to
other components.
"""

import asyncio
import collections.abc
import logging
import typing

import auraxium
from auraxium import event

from ._messaging import MessagingComponent
from ._types import FacilityStatus, ServerInfo

__all__ = [
    'EventListener',
]


class EventListener(MessagingComponent):
    """Component for real-time event listening.

    Emits a `map_update` event each time a facility updates. Note that
    this also includes resecuring of a facility by its current owner.
    This may include duplicates as redundant event listeners are used.
    New zones can be added at any time using the :meth:`add_zone`
    method.
    """

    def __init__(self, server_info: ServerInfo,
                 census_service_id: str = 's:example',
                 startup_zones: collections.abc.Iterable[int] = ()) -> None:
        super().__init__()
        self._log = logging.getLogger(f'app.server_{server_info[0]}.event')

        self._server_info = server_info
        self._service_id = census_service_id
        self._client: auraxium.EventClient | None = None
        self._zones: set[int] = set(startup_zones)

        self._reconnect_timeout = 5.0

        try:
            loop = asyncio.get_running_loop()
        except RuntimeError as err:
            raise RuntimeError('running event loop required') from err
        loop.create_task(self._connect())
        self._log.info('event listener started')

    @property
    def server_id(self) -> int:
        """Return the ID of the server being tracked."""
        return self._server_info.id

    @property
    def zones(self) -> set[int]:
        """Return the zones being tracked on this server."""
        return self._zones

    def add_zone(self, zone_id: int) -> None:
        """Add a zone to the list of tracked zones.

        If zone already exists, do nothing.
        """
        if zone_id not in self._zones:
            self._log.info('zone %d added', zone_id)
        self._zones.add(zone_id)

    def remove_zone(self, zone_id: int) -> None:
        """Remove a zone from the list of tracked zones.

        If zone does not exist, do nothing.
        """
        if zone_id not in self._zones:
            self._log.info('zone %d removed', zone_id)
        self._zones.discard(zone_id)

    def _build_triggers(self) -> list[event.Trigger]:
        """Generate the triggers for the event client."""
        triggers: list[event.Trigger] = []

        trigger = event.Trigger(event.FacilityControl, worlds=[self.server_id])
        trigger.callback(self._handle_event)
        triggers.append(trigger)

        return triggers

    async def _connect(self) -> typing.NoReturn:
        """Create the Auraxium client and subscribe to events.

        Does not return until the coroutine is cancelled.
        """
        if self._server_info[1] != 'ps2':
            self._log.warning('real-time event listening is only supported '
                              'for PC servers at this time')

        while True:
            self._log.info('connecting to event stream')
            self._client = auraxium.EventClient(service_id=self._service_id)
            for trigger in self._build_triggers():
                self._client.add_trigger(trigger)
            self._log.debug(
                'subscribed to %d triggers', len(self._client.triggers))

            await self._client.connect()
            self._log.warning('client disconnected, reconnecting in %f.1s',
                              self._reconnect_timeout)
            await asyncio.sleep(self._reconnect_timeout)

    def _dispatch_map_update(self, zone_id: int, facility_id: int,
                             status: FacilityStatus) -> None:
        """Inject the server ID and dispatch the component message."""
        self.emit('map_update', (self.server_id, zone_id, facility_id, status))

    def _handle_event(self, evt: event.Event) -> None:
        """Dispatcher for Auraxium event callbacks."""

        # Ignore events for servers other than the one the listener is tracking
        if evt.world_id != self.server_id:
            self._log.warning('received untracked event for world %d: %s',
                              evt.world_id, evt)
            return

        # Ignore events for zones that are not being tracked by this listener
        zone_id: int | None = getattr(evt, 'zone_id', None)
        if zone_id not in self._zones:
            self._log.debug('ignoring %s event in untracked zone %d',
                            evt.__class__.__name__, zone_id)
            return

        # Dispatch the event to the appropriate handler
        if isinstance(evt, event.FacilityControl):
            self._on_facility_control(evt)
        else:
            self._log.info('ignoring unhandled event type %s', type(evt))

    def _on_facility_control(self, evt: event.FacilityControl) -> None:
        """Forward a facility control event as a component message."""
        outfit = evt.outfit_id or None
        status = FacilityStatus(evt.new_faction_id, evt.timestamp, outfit)
        self._dispatch_map_update(evt.zone_id, evt.facility_id, status)

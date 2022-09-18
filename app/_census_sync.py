"""Standalone map state syncing using the Census API REST endpoint.

This tool is designed to run in parallel to the real-time event monitor
and detect changes to the map state that may have not made it through
the event stream.

It also doubles as a fallback for detecting continent locks and unlocks
if the event stream is not sending `ContinentUnlock` events (as has
been the case for years as of 2022-09-18).
"""

import asyncio
import logging
import typing

import aiohttp
import auraxium
import yarl

from ._messaging import MessagingComponent

__all__ = [
    'CensusSync',
    'MapPollPayload',
]

MapPollPayload = typing.NamedTuple(
    'MapPollPayload', world_id=int, zone_id=int, ownership=dict[int, int])

_log = logging.getLogger('app.rest_syncer')


class CensusSync(MessagingComponent):
    """Component for synchronising the map state with the REST API.

    After initialization, call the :meth:`start` method to commence
    polling with the interval specified in the constructor.

    Other components can subscribe to receive the polled data by
    subscribing to the ``map_poll`` event.

    Every combination of zone and world gets its own message. See the
    :obj:`MapPollPayload` type for available fields.
    """

    def __init__(self, interval: float, service_id: str,
                 worlds: list[int] = [], zones: list[int] = []) -> None:
        if not worlds or not zones:
            raise ValueError('worlds and zones must be non-empty')
        super().__init__()

        self._poll_interval: float = interval
        self._poll_task: asyncio.Task[None] | None = None
        self._running: bool = False
        self._worlds: list[int] = worlds
        self._zones: list[int] = zones
        self._query = self._get_map_query(service_id)

    def _rest_received(self, map_data: MapPollPayload) -> None:
        """Dispatch a message with the given map data."""
        if self._running:
            self.dispatch('map_poll', map_data)

    def start(self) -> None:
        """Start the map syncing loop.

        Call :meth:`stop` to stop polling.
        """
        if not self._running:
            _log.debug('starting map polling')
            self._poll_task = asyncio.create_task(self._poll())
        else:
            _log.warning('map polling already running')
        self._running = True

    def stop(self) -> None:
        """Stop the map syncing loop.

        This will prevent any new loops from starting, but any
        ongoing polling operations will still finish normally.
        """
        if self._running:
            _log.debug('stopping map polling')
            if self._poll_task is not None:
                self._poll_task.cancel()
                self._poll_task = None
        else:
            _log.warning('map polling not active')
        self._running = False

    def _build_payloads(self, world_id: int, data: dict[str, typing.Any],
                        ) -> list[MapPollPayload]:
        """Process the ps2/map response and generate the payloads.

        Every zone is returned as a separate payload. Note that the
        world ID must be specified beforehand as the payload does not
        contain information about what game server it reports for.
        """
        payloads: list[MapPollPayload] = []
        for map_ in data['map_list']:

            # Extract facility ownership map
            ownership: dict[int, int] = {}
            for entry in map_['Regions']['Row']:
                row_data = entry['RowData']
                ownership[int(row_data['RegionId'])] = int(
                    row_data['FactionId'])

            payloads.append(
                MapPollPayload(world_id, int(map_['ZoneId']), ownership))
        return payloads

    async def _fetch(self) -> None:
        """Fetch the map state for all worlds and zones registered.

        Worlds are polled separately but in parellel.
        """

        # NOTE: The "ps2/map" endpoint only supports querying a single world
        # at a time. Additionally, its payload does not include the world ID,
        # so we have to use closures to capture the world ID for each request.
        zone_ids = ','.join(map(str, self._zones))

        async def fetch_world(
                world_id: int, session: aiohttp.ClientSession) -> None:
            """Closure for keeping track of the current world_id."""
            url = self._query.with_query(world_id=world_id, zone_ids=zone_ids)
            async with session.get(url) as resp:
                if resp.status != 200:
                    _log.error('failed to fetch map state for world %d: %s',
                               world_id, resp.status)
                    return
                for data in self._build_payloads(world_id, await resp.json()):
                    self._rest_received(data)

        try:
            async with aiohttp.ClientSession() as session:
                tasks = [fetch_world(w, session) for w in self._worlds]
                await asyncio.gather(*tasks)
        except Exception as err:
            _log.exception('failed to fetch map state: %s', err)

    def _get_map_query(self, service_id: str) -> yarl.URL:
        return auraxium.census.Query('map', service_id=service_id).url()

    async def _poll(self) -> None:
        while True:
            _log.debug('polling map state')
            asyncio.create_task(self._fetch())
            await asyncio.sleep(self._poll_interval)

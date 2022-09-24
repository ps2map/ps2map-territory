"""Synchronisation component using the REST API census endpoint.

This provides the initial load of the map state when the stack is
started, and also provides some resiliency against game server outages
or the websocket API missing capture events (which allegedly happens).
"""

import asyncio
import collections.abc
import logging
import typing

import aiohttp
import auraxium.census

from ._messaging import MessagingComponent

__all__ = [
    'CensusSync',
]

_log = logging.getLogger('app.rest_syncer')


class CensusSync(MessagingComponent):
    """Component for synchronising the map state with the REST API.

    Emits a `map_poll` event for each tracked zone on the given server
    in regular intervals. New zones can be added at any time using the
    :meth:`add_zone` method.
    """

    def __init__(self, server_id: int, census_namespace: str = 'ps2',
                 census_service_id: str = 's:example',
                 startup_zones: collections.abc.Iterable[int] = (),
                 polling_interval: float = 5.0,
                 polling_timeout: float = 10.0) -> None:
        super().__init__()

        # Create a sub-logger for this instance
        self._log = logging.getLogger(f'{_log.name}.world_{server_id}')
        self._namespace = census_namespace
        self._polling_interval = polling_interval
        self._polling_timeout = polling_timeout
        self._server_id = server_id
        self._service_id = census_service_id
        self._zones: set[int] = set(startup_zones)

        try:
            loop = asyncio.get_running_loop()
        except RuntimeError as err:
            raise RuntimeError('Running event loop required') from err
        loop.create_task(self._poll_hypervisor())

    @property
    def census_namespace(self) -> str:
        return self._namespace

    @property
    def server_id(self) -> int:
        return self._server_id

    @property
    def zones(self) -> set[int]:
        return self._zones

    def add_zone(self, zone_id: int) -> None:
        """Add a zone to the list of tracked zones.

        If zone already exists, do nothing.
        """
        self._zones.add(zone_id)

    def remove_zone(self, zone_id: int) -> None:
        """Remove a zone from the list of tracked zones.

        If zone does not exist, do nothing.
        """
        self._zones.discard(zone_id)

    @staticmethod
    def _parse_map(json: dict[str, typing.Any]
                   ) -> collections.abc.Iterator[tuple[int, dict[int, int]]]:
        """Convert the Census API paylaod into a more compact map.

        Returned dict is as {zone: {base: owning_faction}}.
        """
        for zone in json['map_list']:
            zone_id = int(zone['ZoneId'])
            ownership: dict[int, int] = {}
            for row_data in (r['RowData'] for r in zone['Regions']['Row']):
                region_id = int(row_data['RegionId'])
                faction_id = int(row_data['FactionId'])
                ownership[region_id] = faction_id
            yield zone_id, ownership

    async def _poll(self) -> None:
        """Poll the Census API for the current map state."""
        if not self._zones:
            self._log.info('no zones to poll for world %d', self._server_id)
            return

        # Generate the URL for the census endpoint
        query = auraxium.census.Query(
            'map', namespace=self._namespace,
            service_id=self._service_id,
            world_id=self._server_id,
            zone_ids=','.join(map(str, self._zones)))
        url = query.url(skip_checks=True)

        # Fetch the map status for all tracked zones
        async with aiohttp.ClientSession() as session:
            async with session.get(url) as resp:
                if resp.status != 200:
                    self._log.warning('census query failed: %s', resp.status)
                    return
                data = await resp.json()
        self._log.debug('census query returned %d rows', len(data))

        # Emit a map_poll event for each zone
        for zone_id, ownership in self._parse_map(data):
            self._log.debug(
                'dispatching map_poll for server %d zone %d (%d bases)',
                self._server_id, zone_id, len(ownership))
            self.dispatch('map_poll', (self._server_id, zone_id, ownership))

    async def _poll_hypervisor(self) -> typing.NoReturn:
        """Main polling loop.

        Runs forever, or until its task is cancelled.
        """
        while True:
            loop = asyncio.get_running_loop()
            loop.create_task(self._poll_wrapper(self._poll()))
            await asyncio.sleep(self._polling_interval)

    async def _poll_wrapper(self, coro: typing.Awaitable[None]) -> None:
        """Error handling wrapper for the polling coroutine.

        This silences and warns for polling timeouts, re-raises
        CancelledError, and silences and logs all other exceptions.
        """
        try:
            return await asyncio.wait_for(coro, self._polling_timeout)
        except asyncio.TimeoutError:
            self._log.warning('map polling timed out')
        except asyncio.CancelledError:
            raise
        except Exception:
            self._log.exception('exception ignored in map polling loop')

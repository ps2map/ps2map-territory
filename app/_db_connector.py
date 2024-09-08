"""Database connection handler and query executor.

No SQL outside of this module should be used in the application.
"""

import asyncio
import collections.abc
import contextlib
import logging
import typing

import psycopg
import psycopg.sql
import psycopg_pool

from .sql import (GET_MAP_REGION_FROM_FACILITY, GET_PLATFORM_FROM_WORLD,
                  GET_WORLD_ALL_TRACKED, GET_ZONE_ALL_TRACKED, UPDATE_MAP_STATE)
from ._types import FacilityStatus, Timestamp

__all__ = [
    'DbConnector',
    'DbInfo',
]

_Connection = psycopg.AsyncConnection[typing.Any]
_Pool = psycopg_pool.AsyncConnectionPool
_ConnectionContext = contextlib.AbstractAsyncContextManager[_Connection]

_log = logging.getLogger('app.db')


class DbInfo(typing.NamedTuple):
    """Database connection information."""

    host: str
    port: int
    user: str
    password: str
    database: str


class DbConnector:
    """Database connector class.

    Abstraction layer over the database driver, generates and executes
    SQL queries.
    """

    def __init__(self, db_info: DbInfo) -> None:
        self._base_cache: dict[int, int] = {}
        self._pool: _Pool | None = None
        self._ready = asyncio.Event()

        try:
            loop = asyncio.get_running_loop()
        except RuntimeError as err:
            raise RuntimeError('Running event loop required') from err
        loop.create_task(self._connect(db_info))

    @property
    def _connection(
            self) -> collections.abc.Coroutine[None, None, _ConnectionContext]:
        """Property shorthand for getting a cursor."""
        async def _wrapper() -> _ConnectionContext:
            await self._ready.wait()
            assert self._pool is not None
            return self._pool.connection()
        return _wrapper()

    async def _connect(self, db_info: DbInfo) -> None:
        """Asynchronous DB connection routine.

        Upon completion, will set the internal :attr:`_ready` event
        True. Operations requiring DB access should wait for this
        event.
        """
        conn_str = (f'host={db_info.host} '
                    f'port={db_info.port} '
                    f'user={db_info.user} '
                    f'password={db_info.password} '
                    f'dbname={db_info.database}')
        self._pool = _Pool(conn_str)
        await self._pool.wait()
        self._ready.set()

    async def map_region_from_facility(self, facility_id: int) -> int | None:
        """Fetch the base ID for a given facility ID.

        This method is cached and will return immediately if the given
        facility ID has already been looked up.
        """
        if facility_id in self._base_cache:
            return self._base_cache[facility_id]

        async with await self._connection as conn:
            async with conn.cursor() as cur:
                await cur.execute(GET_MAP_REGION_FROM_FACILITY, (facility_id,))  # type: ignore
                base_id = await cur.fetchone()

        if base_id is not None:
            self._base_cache[facility_id] = base_id[0]
            return base_id[0]
        return None

    async def get_namespace(self, server_id: int) -> str | None:
        """Retrieve the Census API namespace for a given server."""
        async with await self._connection as conn:
            async with conn.cursor() as cur:
                await cur.execute(GET_PLATFORM_FROM_WORLD, (server_id,))  # type: ignore
                namespace = await cur.fetchone()
        if namespace is None:
            return None
        platform, region = namespace
        if platform == 'pc':
            return 'ps2'
        if platform == 'ps4':
            return 'ps2ps4us' if region == 'us' else 'ps2ps4eu'
        return None

    async def fetch_worlds(self) -> list[int]:
        """Fetch all tracked servers from the database."""
        async with await self._connection as conn:
            async with conn.cursor() as cur:
                await cur.execute(GET_WORLD_ALL_TRACKED)  # type: ignore
                return [row[0] for row in await cur.fetchall()]

    async def fetch_zones(self) -> list[int]:
        """Fetch all static zones from the database."""
        async with await self._connection as conn:
            async with conn.cursor() as cur:
                await cur.execute(GET_ZONE_ALL_TRACKED)  # type: ignore
                return [row[0] for row in await cur.fetchall()]

    async def sync_zone(self, world_id: int, zone_id: int,
                        zone_data: dict[int, FacilityStatus]) -> None:

        # Generator for the SQL query items
        def param_gen() -> typing.Iterator[
                tuple[int, int, int, bool, int, int, Timestamp]]:
            for facility_id, status in zone_data.items():
                yield (facility_id, world_id, zone_id, True, status.faction_id,
                       status.owning_outfit_id or 0, status.last_secured)

        async with await self._connection as conn:
            async with conn.cursor() as cur:
                for params in param_gen():
                    try:
                        await cur.execute(UPDATE_MAP_STATE, params)  # type: ignore
                    except psycopg.IntegrityError as err:
                        await conn.rollback()
                        _log.debug('failed to set facility %d on zone %d: %s',
                                   params[2], zone_id, err)
                    else:
                        await conn.commit()

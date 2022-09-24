"""Database connection handler and query executor.

No SQL outside of this module should be used in the application.
"""

import asyncio
import collections.abc
import contextlib
import typing

import psycopg
import psycopg_pool

from ._types import FacilityStatus, Timestamp

__all__ = [
    'DbConnector',
    'DbInfo',
]

_Connection = psycopg.AsyncConnection[tuple[typing.Any, ...]]
_Cursor = psycopg.AsyncCursor[tuple[typing.Any, ...]]
_Pool = psycopg_pool.AsyncConnectionPool
_ConnectionContext = contextlib.AbstractAsyncContextManager[_Connection]


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

    async def fetch_namespace(self, server_id: int) -> str | None:
        """Retrieve the Census API namespace for a given server."""
        async with await self._connection as conn:
            async with conn.cursor() as cur:
                await cur.execute(
                    'SELECT "census_namespace" '
                    'FROM "API_static"."Server" '
                    'WHERE "id" = %s',
                    (server_id,)
                )
                namespace = await cur.fetchone()
                return namespace[0] if namespace is not None else None

    async def fetch_servers(self) -> list[int]:
        """Fetch all tracked servers from the database."""
        async with await self._connection as conn:
            async with conn.cursor() as cur:
                await cur.execute(
                    'SELECT "id" '
                    'FROM "API_static"."Server" '
                    'WHERE "tracking_enabled" = TRUE'
                )
                return [row[0] for row in await cur.fetchall()]

    async def fetch_zones(self) -> list[int]:
        """Fetch all static zones from the database."""
        async with await self._connection as conn:
            async with conn.cursor() as cur:
                await cur.execute(
                    'SELECT "id" '
                    'FROM "API_static"."Continent" '
                    'WHERE "hidden" = FALSE'
                )
                return [row[0] for row in await cur.fetchall()]

    async def sync_zone(self, server_id: int, zone_id: int,
                        zone_data: dict[int, FacilityStatus]) -> None:

        # Generator for the SQL query items
        def param_gen() -> typing.Iterator[
                tuple[int, Timestamp, int, int]]:
            for facility_id, status in zone_data.items():
                yield (status.current_faction, status.last_capture,
                       facility_id, server_id)

        async with await self._connection as conn:
            async with conn.cursor() as cur:
                await cur.executemany(
                    'UPDATE "API_dynamic"."BaseOwnership" '
                    'SET "owning_faction_id" = %s, '
                    '    "owned_since" = %s '
                    'WHERE "base_id" = %s '
                    '  AND "server_id" = %s',
                    param_gen()
                )
            # await conn.commit()

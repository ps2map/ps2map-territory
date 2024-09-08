"""Script entrypoint for the territory monitoring tool."""

import argparse
import asyncio
import collections.abc
import logging
import platform
import os

from ._census_sync import CensusSync
from ._db_connector import DbConnector, DbInfo
from ._realtime import EventListener
from ._state_manager import StateManager
from ._types import FacilityStatus, ServerInfo

_log = logging.getLogger('app')


async def _load_servers(
        conn: DbConnector) -> collections.abc.AsyncIterator[ServerInfo]:
    """Load the list of tracked game servers and namespaces.

    This first retrieves any tracked game servers from the database,
    then looks up the corresponding Census API namespace for each. For
    PC servers, this will be `ps2`, the PS4 servers have their own
    namespaces.
    """
    servers = await conn.fetch_worlds()
    for server_id in servers:
        namespace = await conn.get_namespace(server_id)
        if namespace is None:
            _log.warning('no namespace found for server: %d', server_id)
        else:
            yield ServerInfo(server_id, namespace)


async def main(db_info: DbInfo, service_id: str) -> None:
    """Async equivalent of the __main__ clause."""
    _log.info('starting up')

    # Create the database connector and wait for it to be ready
    conn = DbConnector(db_info)
    _log.info('connected to database "%s"', db_info.database)

    zones = await conn.fetch_zones()

    # Creat main event dispatcher and state manager
    state = StateManager()

    async def _map_update(
            payload: tuple[int, int, dict[int, FacilityStatus]]) -> None:
        await conn.sync_zone(*payload)
    state.subscribe('map_update', _map_update)

    # Create a REST sync task for each server
    _log.info('loading tracked servers')
    async for server_info in _load_servers(conn):
        _log.debug('loaded server %d (%s)', *server_info)
        sync = CensusSync(server_info, census_service_id=service_id,
                          startup_zones=zones, polling_interval=10.0,
                          polling_timeout=18.0)
        sync.subscribe('map_poll', state.handle_map_poll)

        listener = EventListener(server_info, census_service_id=service_id,
                                 startup_zones=zones)

        async def _wrap_listener(payload: tuple[int, int, int, FacilityStatus]) -> None:
            server, zone, facility, status = payload
            base = await conn.map_region_from_facility(facility)
            if base is None:
                _log.warning('unable to find map_region for facility %d', facility)
                return

            payload = server, zone, base, status
            state.handle_map_update(payload)
        listener.subscribe('map_update', _wrap_listener)


if __name__ == '__main__':
    # Load DB connection info defaults from environment variables
    _def_service_id = os.getenv('PS2MAP_SERVICE_ID', 's:example')
    _def_db_host = os.getenv('PS2MAP_DB_HOST', 'localhost')
    _def_db_port = int(os.getenv('PS2MAP_DB_PORT', '5432'))
    _def_db_name = os.getenv('PS2MAP_DB_NAME', 'postgres')
    _def_db_user = os.getenv('PS2MAP_DB_USER', 'postgres')
    _def_db_pass = os.getenv('PS2MAP_DB_PASS')

    # Optionally overload defaults via command line
    _parser = argparse.ArgumentParser(__doc__)
    _parser.add_argument(
        '--service-id', '-S', default=_def_service_id,
        help='Service ID for this instance (default: %(default)s)')
    _parser.add_argument(
        '--db-host', '-H', default=_def_db_host,
        help='Database host (default: %(default)s)')
    _parser.add_argument(
        '--db-port', '-P', type=int, default=_def_db_port,
        help='Database port (default: %(default)s)')
    _parser.add_argument(
        '--db-name', '-D', default=_def_db_name,
        help='Database name (default: %(default)s)')
    _parser.add_argument(
        '--db-user', '-U', default=_def_db_user,
        help='Database user (default: %(default)s)')
    _parser.add_argument(
        '--db-pass', '-W', default=_def_db_pass,
        help='Database password (default: %(default)s)')
    _parser.add_argument(
        '--log-level', '-L', default='INFO',
        help='Log level (default: %(default)s)')
    _args = _parser.parse_args()

    _service_id = _args.service_id
    _db_info = DbInfo(
        host=_args.db_host,
        port=_args.db_port,
        database=_args.db_name,
        user=_args.db_user,
        password=_args.db_pass,
    )

    # Logging configuration
    _fmt = logging.Formatter(
        '%(asctime)s [%(levelname)s] %(name)s: %(message)s')
    _fh = logging.FileHandler(filename='debug.log', encoding='utf-8')
    _sh = logging.StreamHandler()
    _fh.setFormatter(_fmt)
    _sh.setFormatter(_fmt)

    _log_level = getattr(logging, _args.log_level.upper(), None)
    if _log_level is None:
        raise ValueError(f'invalid log level: {_args.log_level}')
    _log = logging.getLogger('app')
    _log.setLevel(_log_level)
    _log.addHandler(_fh)
    _log.addHandler(_sh)

    # SelectorEventLoop is required for psycopg database driver
    if platform.system() == 'Windows':
        asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy()) # type: ignore
    else:
        asyncio.set_event_loop_policy(asyncio.DefaultEventLoopPolicy())

    _loop = asyncio.new_event_loop()
    asyncio.set_event_loop(_loop)
    _loop.create_task(main(_db_info, _service_id))

    _loop.run_forever()

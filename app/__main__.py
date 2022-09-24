"""Script entrypoint for the territory monitoring tool."""

import argparse
import asyncio
import collections.abc
import logging
import os

from ._census_sync import CensusSync
from ._db_connector import DbConnector, DbInfo
from ._state_manager import StateManager

_log = logging.getLogger('app')
_log.setLevel(logging.DEBUG)


async def _load_servers(
        conn: DbConnector) -> collections.abc.AsyncIterator[tuple[int, str]]:
    """Load the list of tracked game servers and namespaces.

    This first retrieves any tracked game servers from the database,
    then looks up the corresponding Census API namespace for each. For
    PC servers, this will be `ps2`, the PS4 servers have their own
    namespaces.
    """
    servers = await conn.fetch_servers()
    for server_id in servers:
        namespace = await conn.fetch_namespace(server_id)
        if namespace is None:
            _log.warning('no namespace found for server: %d', server_id)
        else:
            yield server_id, namespace


async def main(db_info: DbInfo, service_id: str) -> None:
    _log.info('starting up')

    # Create the database connector and wait for it to be ready
    conn = DbConnector(db_info)
    _log.info('connected to database "%s"', db_info.database)

    zones = await conn.fetch_zones()

    # Creat main event dispatcher and state manager
    state = StateManager()

    # Create a REST sync task for each server
    _log.info('loading tracked servers')
    async for server, namespace in _load_servers(conn):
        _log.debug('loaded server %d (%s)', server, namespace)
        sync = CensusSync(server, namespace, census_service_id=service_id,
                          startup_zones=zones)
        sync.subscribe('map_poll', state.handle_map_poll)

    # TODO: Create websocket clients to improve map responsiveness and add
    # resiliency for REST API outages


if __name__ == '__main__':
    # Load DB connection info defaults from environment variables
    def_service_id = os.getenv('PS2MAP_SERVICE_ID', 's:example')
    def_db_host = os.getenv('PS2MAP_DB_HOST', 'localhost')
    def_db_port = int(os.getenv('PS2MAP_DB_PORT', 5432))
    def_db_name = os.getenv('PS2MAP_DB_NAME', 'postgres')
    def_db_user = os.getenv('PS2MAP_DB_USER', 'postgres')
    def_db_pass = os.getenv('PS2MAP_DB_PASS')

    # Optionally overload defaults via command line
    parser = argparse.ArgumentParser(__doc__)
    parser.add_argument(
        '--service-id', '-S', default=def_service_id,
        help='Service ID for this instance (default: %(default)s)')
    parser.add_argument(
        '--db-host', '-H', default=def_db_host,
        help='Database host (default: %(default)s)')
    parser.add_argument(
        '--db-port', '-P', type=int, default=def_db_port,
        help='Database port (default: %(default)s)')
    parser.add_argument(
        '--db-name', '-D', default=def_db_name,
        help='Database name (default: %(default)s)')
    parser.add_argument(
        '--db-user', '-U', default=def_db_user,
        help='Database user (default: %(default)s)')
    parser.add_argument(
        '--db-pass', '-W', default=def_db_pass,
        help='Database password (default: %(default)s)')
    args = parser.parse_args()

    service_id = args.service_id
    db_info = DbInfo(
        host=args.db_host,
        port=args.db_port,
        database=args.db_name,
        user=args.db_user,
        password=args.db_pass,
    )

    # Logging configuration
    fmt = logging.Formatter(
        '%(asctime)s [%(levelname)s] %(name)s: %(message)s')
    fh_ = logging.FileHandler(filename='debug.log', encoding='utf-8')
    sh_ = logging.StreamHandler()
    fh_.setFormatter(fmt)
    sh_.setFormatter(fmt)

    # SelectorEventLoop is required for psycopg database driver
    asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())

    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    loop.create_task(main(db_info, service_id))

    loop.run_forever()

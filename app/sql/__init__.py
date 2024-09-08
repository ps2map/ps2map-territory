"""Loads SQL commands from disk and stores them for later access."""

import pathlib

__all__ = [
    'GET_MAP_REGION_FROM_FACILITY',
    'GET_PLATFORM_FROM_WORLD',
    'GET_WORLD_ALL_TRACKED',
    'GET_ZONE_ALL_TRACKED',
    'UPDATE_MAP_STATE',
]

# Relative directory to the SQL files
_SQL_DIR = pathlib.Path(__file__).parent


def _get_sql(filename: str) -> str:
    """Loads a file from disk and returns its contents."""
    with open(_SQL_DIR / filename, encoding='utf-8') as sql_file:
        return sql_file.read()

GET_MAP_REGION_FROM_FACILITY = _get_sql('get_MapRegion_fromFacility.sql')
GET_PLATFORM_FROM_WORLD = _get_sql('get_Platform_fromWorld.sql')
GET_WORLD_ALL_TRACKED = _get_sql('get_World_allTracked.sql')
GET_ZONE_ALL_TRACKED = _get_sql('get_Zone_allTracked.sql')
UPDATE_MAP_STATE = _get_sql('update_MapState.sql')

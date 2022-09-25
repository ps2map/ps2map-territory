# PS2Map Territory Manager

PS2Map backend service for territory control monitoring.

## Operation

This service is the main state governer for the territory control pipeline of the PS2Map stack. On map changes (including initial load), the delta is forwarded to the central state database to be consumed by the API and other services.

### Data aggregation

Its primary synchronisation mechanism is listening to `FacilityControl` messages on the PlanetSide 2 WebSocket. In addition to the new owning faction, these payloads provide canonical capture times and optionally a capturing outfit.

However, the event stream WebSocket is known to drop such events on occasion. To account for this, it also monitors `PlayerFacilityCapture` messages and determines the new faction based on the capturing players' faction. However, no guild capture information can be retrieved for this fallback hook.

Finally, the service also polls the Census REST API's `ps2/map` endpoint and compares its map state digest with the local map state. If differences are found, capture events are generated accordingly. This handles WebSocket API outages, as well as static zones that only just unlocked. For these fallback events, no guild capture information can be retrieved and the capture timestamp may be off by up to one polling interval.

### Zone availability status

Whenever the map changes, a check is run to see if all warpgates/starting regions are owned by the same faction. If this occurs, a zone lock/unlock event is generated.

Note that this only catches static zones opening or closing, i.e. the game's default continents. Dynamic zone instances are currently not monitored and require manual intervention.

## Scalability

The restrictions on the APIs used make handling each zone in a different service instance inefficient as the biggest workload is filtering the incoming real-time events, which can only be subscribed to on a per-server basis.

The current version additionally tracks all worlds/game servers in the same state manager. If more worlds are added or container performance becomes an issue, this service can be easily broken up into one instance per game server by replacing the `_load_servers()` call in the `__main__.py` entrypoint with a command line parameter listing the world(s) that should be monitored.

## Installation

- Python 3.10+ required.
- See `./requirements.txt` for required dependencies

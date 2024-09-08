-- Upsert the map state for a given set of facilities.
INSERT INTO "map_state"."region" (
    "id",
    "world_id",
    "zone_id",
    "enabled",
    "owner_faction_id",
    "owner_outfit_id",
    "last_capture_time"
)
VALUES (%s, %s, %s, %s, %s, %s, %s)
ON CONFLICT ("id", "world_id")
DO UPDATE SET
    "zone_id" = EXCLUDED."zone_id",
    "enabled" = EXCLUDED."enabled",
    "owner_faction_id" = EXCLUDED."owner_faction_id",
    "owner_outfit_id" = EXCLUDED."owner_outfit_id",
    "last_capture_time" = EXCLUDED."last_capture_time"
;
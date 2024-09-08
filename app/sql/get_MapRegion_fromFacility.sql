-- Get the map_region id and name for a given facility. Note that not all facilities have a map region.
SELECT
    "id"
FROM
    "game"."map_region"
WHERE
    "facility_id" = %s
;

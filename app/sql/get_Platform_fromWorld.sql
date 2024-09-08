-- Get the platform code for the given server.
SELECT
    "platform",
    "region"
FROM
    "game"."world"
WHERE
    "id" = %s
;

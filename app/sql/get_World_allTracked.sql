-- Retrieve every world.
SELECT
    "id"
FROM
    "game"."world"
WHERE
    "name" IN (
        'Ceres',
        'Genudine',
        'Osprey',
        'SolTech',
        'Wainwright'
    )
;
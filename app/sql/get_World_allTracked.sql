-- Retrieve every world.
SELECT
    "id"
FROM
    "game"."world"
WHERE
    "name" IN (
        'Connery',
        'Miller',
        'Cobalt',
        'Emerald',
        'SolTech',
        'Genudine',
        'Ceres'
    )
;
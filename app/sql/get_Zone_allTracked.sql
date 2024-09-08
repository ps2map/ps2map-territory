-- Retrieve every continent whose map state is tracked in real-time.
SELECT
    "id"
FROM
    "game"."zone"
WHERE
    "name" IN (
        'Indar',
        'Esamir',
        'Amerish',
        'Hossin',
        'Oshur'
    )
;
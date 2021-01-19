SELECT data FROM declaration
WHERE
    ft @@ to_tsquery('ftdict', $1)
    AND (
        data->'entreprise'->'effectif'->>'tranche' = '1000:'
        OR (data->'entreprise'->'effectif'->>'tranche' = '251:999' AND year >= 2020)
    )
LIMIT $2

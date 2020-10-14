SELECT data FROM declaration
WHERE
    ft @@ to_tsquery('ftdict', $1)
    AND data->'entreprise'->'effectif'->>'tranche' = '1000:'
LIMIT $2

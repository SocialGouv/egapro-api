SELECT data FROM declaration
WHERE
    ft @@ to_tsquery('ftdict', $1)
    AND data->'entreprise'->'effectif'->>'tranche' IN ('1000:', '251:999')
LIMIT $2

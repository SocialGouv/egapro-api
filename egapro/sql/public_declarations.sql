SELECT data FROM declaration
WHERE data->'entreprise'->'effectif'->>'tranche' = '1000:' OR (data->'entreprise'->'effectif'->>'tranche' = '251:999' AND year >= 2020)

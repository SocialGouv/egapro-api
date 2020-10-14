SELECT data FROM declaration
WHERE data->'entreprise'->'effectif'->>'tranche' = '1000:'

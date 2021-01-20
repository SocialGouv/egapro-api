SELECT data FROM declaration
WHERE data->'entreprise'->'effectif'->>'tranche' IN ('1000:', '251:999')

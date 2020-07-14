SELECT data FROM declaration
WHERE
    data->'informations'->>'trancheEffectifs' = '1000 et plus'
    OR (
        (data->'informations'->>'anneeDeclaration')::int=2018
        AND data->'informations'->>'trancheEffectifs' = 'Plus de 250'
        AND COALESCE((data->'effectif'->>'nombreSalariesTotal')::float, 0) >= 1000
    )

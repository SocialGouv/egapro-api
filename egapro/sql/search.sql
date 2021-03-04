SELECT
    array_agg(declaration.data ORDER BY declaration.declared_at DESC) as data,
    jsonb_object_agg(declaration.year::text, (declaration.data->'déclaration'->>'index')::int) as notes
FROM declaration
JOIN search ON declaration.siren=search.siren AND declaration.year=search.year
    {where}
GROUP BY declaration.siren
ORDER BY max(declaration.declared_at) DESC
LIMIT $1
OFFSET $2

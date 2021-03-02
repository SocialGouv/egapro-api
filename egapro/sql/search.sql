SELECT array_agg(data ORDER BY declared_at DESC) as data, jsonb_object_agg(year::text, (data->'déclaration'->>'index')::int) as notes FROM declaration WHERE siren in (
    SELECT siren FROM search
    {where}
    GROUP BY siren
    ORDER BY max(declared_at) DESC
    LIMIT $1
    OFFSET $2
)
GROUP BY siren

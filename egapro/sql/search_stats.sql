SELECT COUNT(*), avg((data->'déclaration'->>'index')::int), min((data->'déclaration'->>'index')::int), max((data->'déclaration'->>'index')::int) FROM declaration WHERE year=$1 AND siren IN (
    SELECT siren FROM search
    {where}
)

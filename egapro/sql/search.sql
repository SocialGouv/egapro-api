SELECT data FROM declaration WHERE (siren, year) in (
    SELECT siren, year FROM search
    {where}
    ORDER BY declared_at DESC
    LIMIT $1
    OFFSET $2
)

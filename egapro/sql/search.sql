SELECT data FROM search
WHERE
    {filters}
ORDER BY declared_at DESC
LIMIT $1
OFFSET $2

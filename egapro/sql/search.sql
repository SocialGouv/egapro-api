SELECT data FROM search
{where}
ORDER BY declared_at DESC
LIMIT $1
OFFSET $2

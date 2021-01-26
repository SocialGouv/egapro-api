SELECT data FROM search
WHERE
    ft @@ to_tsquery('ftdict', $1){filters}
ORDER BY declared_at DESC
LIMIT $2

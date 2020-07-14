SELECT data FROM declaration WHERE ft @@ to_tsquery('ftdict', $1) LIMIT $2

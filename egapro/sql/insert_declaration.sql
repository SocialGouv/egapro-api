INSERT INTO declaration (siren, year, last_modified, owner, data, ft)
VALUES ($1, $2, $3, $4, $5, to_tsvector('ftdict', $6))
ON CONFLICT (siren, year) DO UPDATE
SET last_modified=$3, owner=$4, data=$5, ft=to_tsvector('ftdict', $6)

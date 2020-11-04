INSERT INTO declaration (siren, year, modified_at, declared_at, owner, data, ft)
VALUES ($1, $2, $3, $4, $5, $6, to_tsvector('ftdict', $7))
ON CONFLICT (siren, year) DO UPDATE
SET modified_at=$3, declared_at=$4, owner=$5, data=$6, ft=to_tsvector('ftdict', $7)

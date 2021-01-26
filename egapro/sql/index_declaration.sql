INSERT INTO search (siren, year, declared_at, data, ft, region, departement, code_naf, note)
VALUES ($1, $2, $3, $4, to_tsvector('ftdict', $5), $6, $7, $8, $9)
ON CONFLICT (siren, year) DO UPDATE
SET declared_at=$3, data=$4, ft=to_tsvector('ftdict', $5), region=$6, departement=$7, code_naf=$8, note=$9

CREATE TABLE IF NOT EXISTS declaration
(siren TEXT, year INT, last_modified TIMESTAMP WITH TIME ZONE, owner TEXT, data JSONB, ft TSVECTOR,
PRIMARY KEY (siren, year));
CREATE INDEX IF NOT EXISTS idx_effectifs ON declaration ((data->'informations'->'trancheEffectifs'));
CREATE INDEX IF NOT EXISTS idx_ft ON declaration USING GIN (ft);

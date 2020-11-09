CREATE INDEX IF NOT EXISTS idx_effectifs ON declaration ((data->'informations'->'trancheEffectifs'));
CREATE INDEX IF NOT EXISTS idx_ft ON declaration USING GIN (ft);
CREATE INDEX IF NOT EXISTS idx_status ON declaration (declared_at) WHERE declared_at IS NOT NULL;

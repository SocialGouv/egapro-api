CREATE TABLE IF NOT EXISTS declaration
(siren TEXT, year INT, modified_at TIMESTAMP WITH TIME ZONE, declared_at TIMESTAMP WITH TIME ZONE, owner TEXT, data JSONB, ft TSVECTOR,
PRIMARY KEY (siren, year));

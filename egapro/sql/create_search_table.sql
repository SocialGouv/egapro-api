CREATE TABLE IF NOT EXISTS search
(siren TEXT, year INT, declared_at TIMESTAMP WITH TIME ZONE, data JSONB, ft TSVECTOR, region VARCHAR(2), departement VARCHAR(3), code_naf VARCHAR(6), note INT,
PRIMARY KEY (siren, year));

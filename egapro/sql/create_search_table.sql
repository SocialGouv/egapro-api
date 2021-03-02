CREATE TABLE IF NOT EXISTS search
(siren TEXT, year INT, declared_at TIMESTAMP WITH TIME ZONE, ft TSVECTOR, region VARCHAR(2), departement VARCHAR(3), section_naf CHAR, note INT,
PRIMARY KEY (siren, year));

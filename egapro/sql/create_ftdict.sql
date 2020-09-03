DO
$$BEGIN
    CREATE TEXT SEARCH CONFIGURATION ftdict (COPY=simple);
    ALTER TEXT SEARCH CONFIGURATION ftdict ALTER MAPPING FOR hword, hword_part, word WITH unaccent, simple;
EXCEPTION
   WHEN unique_violation THEN
      NULL;  -- ignore error
END;$$;

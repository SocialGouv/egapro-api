WITH search AS (SELECT siren FROM search {where}),
     count AS (SELECT COUNT(DISTINCT(siren)) FROM search),
     stats AS (SELECT avg((data->'déclaration'->>'index')::int),
                      min((data->'déclaration'->>'index')::int),
                      max((data->'déclaration'->>'index')::int)
               FROM declaration d JOIN search s ON d.siren=s.siren
               WHERE d.year=$1)
    SELECT * FROM count JOIN stats ON true;

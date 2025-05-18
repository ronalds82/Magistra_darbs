-- Desmit piemēriem visbagātāko pārveidojumu atlase
SELECT sr.data ->> 'role_1' AS role_1, sr.data ->> 'role_2' AS role_2, COUNT(*) AS cnt
FROM dict.sense_relations sr
JOIN dict.senses s1 ON s1.id = sr.sense_1_id
JOIN dict.senses s2 ON s2.id = sr.sense_2_id
JOIN dict.entries e1 ON e1.id = s1.entry_id
JOIN dict.entries e2 ON e2.id = s2.entry_id
WHERE sr.data IS NOT NULL AND sr.data ? 'role_1' AND sr.data ? 'role_2'
GROUP BY role_1, role_2
ORDER BY cnt DESC
LIMIT 10

-- Piecu piemēru atlasei
SELECT heading, heading2
FROM (

-- Vispārīga piemēru atlase no konkrētā pārveidojuma veida
SELECT DISTINCT e1.heading, e2.heading AS heading2
FROM dict.sense_relations sr
JOIN dict.senses s1 ON sr.sense_1_id = s1.id
JOIN dict.senses s2 ON sr.sense_2_id = s2.id
JOIN dict.entries e1 ON s1.entry_id  = e1.id
JOIN dict.entries e2 ON s2.entry_id  = e2.id
WHERE sr.data->>'role_1' = 'Darīt' AND sr.data->>'role_2' = 'Rezultāts'

-- Piecu piemēru atlasei
) AS subquery
ORDER BY random() 
LIMIT 5

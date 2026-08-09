

SELECT 'upstream' AS direction,
       pw.ware AS related_ware_id,
       ew.name AS related_ware_name,
       pw.production_method,
       pw.amount
FROM production_wares pw
LEFT JOIN economy_wares_base ew ON ew.ware_id = pw.ware
WHERE pw.production_ware_id = 'hullparts'

UNION ALL

SELECT 'downstream' AS direction,
       pw.production_ware_id AS related_ware_id,
       COALESCE(sb.name, ew2.name) AS related_ware_name,
       pw.production_method,
       pw.amount
FROM production_wares pw
LEFT JOIN ships_base sb ON sb.ware_id = pw.production_ware_id
LEFT JOIN economy_wares_base ew2 ON ew2.ware_id = pw.production_ware_id
WHERE pw.ware = 'hullparts'

ORDER BY direction, related_ware_name;
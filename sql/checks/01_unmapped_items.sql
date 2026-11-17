-- check: Every item name maps to one of our item IDs
-- severity: error
-- why: An unmapped name silently drops out of the forecast. Fix by adding a row to seeds/menu_alias.csv.
SELECT channel, source_item_name, count(*) AS lines, min(_source_file) AS first_seen_in
FROM clean_sales
WHERE item_id IS NULL
GROUP BY ALL
ORDER BY lines DESC;

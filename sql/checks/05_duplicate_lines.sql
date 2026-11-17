-- check: No order line arrived twice
-- severity: warn
-- why: Re-sent exports are handled (the latest copy wins), but someone should know they happened.
SELECT channel, order_id, source_item_name, count(*) AS copies, string_agg(_source_file, ' | ') AS files
FROM stg_sales_all
GROUP BY channel, order_id, source_item_name
HAVING count(*) > 1
ORDER BY copies DESC;
